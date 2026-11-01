"""Deploy RxClear to Amazon Bedrock AgentCore Runtime via the control-plane
API — no CloudFormation/CDK required (works in locked-down accounts too).

Usage:
    .venv/bin/python deploy.py            # package + deploy + wait READY
    .venv/bin/python deploy.py --invoke   # also smoke-test the deployment
    RXCLEAR_ROLE_ARN=arn:... .venv/bin/python deploy.py   # bring your own exec role
"""

import json
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

import boto3

REGION = "us-east-1"
RUNTIME_NAME = "rxclear_agent"
ROLE_NAME = "rxclear-agent-runtime-role"
DEPS = ["strands-agents", "bedrock-agentcore", "requests", "pydantic"]
CODE_FILES = ["main.py"]
CODE_DIRS = ["src"]

ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]
s3 = boto3.client("s3", region_name=REGION)
iam = boto3.client("iam")
ac = boto3.client("bedrock-agentcore-control", region_name=REGION)


def build_zip() -> Path:
    """Vendor linux deps + copy code, zip flat (deps and code at root)."""
    staging = Path(tempfile.mkdtemp(prefix="rxclear-staging-"))
    subprocess.run(
        ["uv", "pip", "install", *DEPS, "--target", str(staging),
         "--python-version", "3.13", "--python-platform", "aarch64-manylinux2014",
         "--only-binary", ":all:"],
        check=True,
    )
    for f in CODE_FILES:
        shutil.copy(f, staging / f)
    for d in CODE_DIRS:
        shutil.copytree(d, staging / d, ignore=shutil.ignore_patterns("__pycache__"))

    zip_path = Path("rxclear-agent.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in staging.rglob("*"):
            z.write(p, p.relative_to(staging))
    shutil.rmtree(staging)
    print(f"Packaged {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB)")
    return zip_path


def ensure_role() -> str:
    override = __import__("os").environ.get("RXCLEAR_ROLE_ARN")
    if override:
        return override
    trust = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {"StringEquals": {"aws:SourceAccount": ACCOUNT}},
        }],
    }
    try:
        role = iam.create_role(RoleName=ROLE_NAME, AssumeRolePolicyDocument=json.dumps(trust))["Role"]
    except iam.exceptions.EntityAlreadyExistsException:
        role = iam.get_role(RoleName=ROLE_NAME)["Role"]
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="bedrock-invoke",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:*:{ACCOUNT}:inference-profile/*",
                ],
            }],
        }),
    )
    time.sleep(10)  # IAM propagation
    return role["Arn"]


def main() -> None:
    zip_path = build_zip()
    bucket = f"rxclear-agentcore-{ACCOUNT}"
    try:
        s3.create_bucket(Bucket=bucket)
    except (s3.exceptions.BucketAlreadyOwnedByYou, s3.exceptions.BucketAlreadyExists):
        pass
    s3.put_object(Bucket=bucket, Key="rxclear-agent.zip", Body=zip_path.read_bytes())
    print(f"Uploaded to s3://{bucket}/rxclear-agent.zip")

    role_arn = ensure_role()
    print(f"Role: {role_arn}")

    existing = {r["agentRuntimeName"]: r for r in ac.list_agent_runtimes().get("agentRuntimes", [])}
    artifact = {
        "codeConfiguration": {
            "code": {"s3": {"bucket": bucket, "prefix": "rxclear-agent.zip"}},
            "runtime": "PYTHON_3_13",
            "entryPoint": ["main.py"],
        }
    }
    if RUNTIME_NAME in existing:
        rid = existing[RUNTIME_NAME]["agentRuntimeId"]
        ac.update_agent_runtime(
            agentRuntimeId=rid, agentRuntimeArtifact=artifact, roleArn=role_arn,
            networkConfiguration={"networkMode": "PUBLIC"},
            protocolConfiguration={"serverProtocol": "HTTP"},
        )
        print(f"Updating existing runtime {rid}")
    else:
        r = ac.create_agent_runtime(
            agentRuntimeName=RUNTIME_NAME,
            agentRuntimeArtifact=artifact,
            roleArn=role_arn,
            networkConfiguration={"networkMode": "PUBLIC"},
            protocolConfiguration={"serverProtocol": "HTTP"},
            description="RxClear medication safety agent (Strands SDK)",
        )
        rid = r["agentRuntimeId"]
        print(f"Created runtime {rid}")

    for _ in range(60):
        info = ac.get_agent_runtime(agentRuntimeId=rid)
        status = info["status"]
        if status == "READY":
            break
        if status.endswith("FAILED"):
            raise SystemExit(f"Runtime failed: {info}")
        time.sleep(10)
    else:
        raise SystemExit("Timed out waiting for READY")

    arn = info["agentRuntimeArn"]
    print(f"\nREADY\n  agent_arn = \"{arn}\"")

    if "--invoke" in sys.argv:
        client = boto3.client("bedrock-agentcore", region_name=REGION)
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=arn,
            runtimeSessionId=str(uuid.uuid4()) + "x",
            payload=json.dumps({
                "medications": ["warfarin", "ibuprofen"],
                "language": "English",
            }).encode(),
            qualifier="DEFAULT",
        )
        out = "".join(c.decode() for c in resp.get("response", []))
        print("\nSmoke test response:")
        print(json.dumps(json.loads(out), indent=2)[:3000])


if __name__ == "__main__":
    main()
