"""Tear down every AWS resource deploy.py creates.

    .venv/bin/python teardown.py            # asks for confirmation
    .venv/bin/python teardown.py --yes      # skip confirmation
"""

import sys
import time

import boto3

REGION = "us-east-1"
RUNTIME_NAME = "rxclear_agent"
ROLE_NAME = "rxclear-agent-runtime-role"

ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]
BUCKET = f"rxclear-agentcore-{ACCOUNT}"

s3 = boto3.client("s3", region_name=REGION)
iam = boto3.client("iam")
ac = boto3.client("bedrock-agentcore-control", region_name=REGION)
logs = boto3.client("logs", region_name=REGION)


def delete_runtime() -> None:
    runtimes = ac.list_agent_runtimes().get("agentRuntimes", [])
    match = [r for r in runtimes if r["agentRuntimeName"] == RUNTIME_NAME]
    if not match:
        print(f"Runtime {RUNTIME_NAME}: not found, skipping")
        return
    rid = match[0]["agentRuntimeId"]
    ac.delete_agent_runtime(agentRuntimeId=rid)
    print(f"Runtime {rid}: deleting", end="", flush=True)
    for _ in range(60):
        try:
            status = ac.get_agent_runtime(agentRuntimeId=rid)["status"]
        except ac.exceptions.ResourceNotFoundException:
            break
        if status == "DELETING":
            print(".", end="", flush=True)
            time.sleep(5)
        else:
            break
    print(" done")

    # Best-effort: runtime CloudWatch log groups
    for prefix in (f"/aws/bedrock-agentcore/runtimes/{rid}",):
        try:
            for lg in logs.describe_log_groups(logGroupNamePrefix=prefix).get("logGroups", []):
                logs.delete_log_group(logGroupName=lg["logGroupName"])
                print(f"Log group {lg['logGroupName']}: deleted")
        except Exception as e:
            print(f"Log group cleanup skipped: {e}")


def delete_bucket() -> None:
    try:
        s3.head_bucket(Bucket=BUCKET)
    except Exception:
        print(f"Bucket {BUCKET}: not found, skipping")
        return
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET):
        objs = [{"Key": o["Key"]} for o in page.get("Contents", [])]
        if objs:
            s3.delete_objects(Bucket=BUCKET, Delete={"Objects": objs})
    s3.delete_bucket(Bucket=BUCKET)
    print(f"Bucket {BUCKET}: deleted")


def delete_role() -> None:
    try:
        iam.get_role(RoleName=ROLE_NAME)
    except iam.exceptions.NoSuchEntityException:
        print(f"Role {ROLE_NAME}: not found, skipping")
        return
    for p in iam.list_role_policies(RoleName=ROLE_NAME).get("PolicyNames", []):
        iam.delete_role_policy(RoleName=ROLE_NAME, PolicyName=p)
    for p in iam.list_attached_role_policies(RoleName=ROLE_NAME).get("AttachedPolicies", []):
        iam.detach_role_policy(RoleName=ROLE_NAME, PolicyArn=p["PolicyArn"])
    iam.delete_role(RoleName=ROLE_NAME)
    print(f"Role {ROLE_NAME}: deleted")


if __name__ == "__main__":
    if "--yes" not in sys.argv:
        confirm = input(
            f"Delete runtime '{RUNTIME_NAME}', bucket '{BUCKET}', and role "
            f"'{ROLE_NAME}' in account {ACCOUNT}? [y/N] "
        )
        if confirm.lower() != "y":
            raise SystemExit("Aborted.")
    delete_runtime()
    delete_bucket()
    delete_role()
    print("Teardown complete.")
