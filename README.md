# RxClear

**Understand your medications in plain language.**

RxClear is a multi-agent AI system that turns confusing prescription labels
into plain-language safety reports — flagging dangerous drug interactions
and telling patients exactly what to ask their pharmacist. Every claim in a
report is grounded in official FDA label data and NIH drug identifiers,
never the model's memory.

Built on the [Strands Agents SDK](https://github.com/strands-agents/sdk-python)
and Amazon Bedrock.

## Why

- Medication errors harm ~1.3 million people in the US every year (FDA).
- Nearly 9 in 10 US adults struggle with health literacy at some point —
  prescription labels are written far above the average reading level.
- Polypharmacy patients (5+ medications) face the highest interaction risk
  and are disproportionately elderly, low-income, or non-English-speaking.

RxClear reads a medication list the way a patient would type it — brand
names, generics, even misspellings — and produces a report anyone can
understand, in their own language.

## Features

- **Plain-language drug summaries** — what each medication does, how to take
  it, and key warnings, rewritten at a 6th-grade reading level
- **Drug interaction warnings** — pairwise checks across the full medication
  list, cross-referenced against official FDA `drug_interactions` and
  `warnings` label text, including drug-*class* warnings (a warfarin label
  warning about "NSAIDs" correctly flags ibuprofen)
- **Typo-tolerant name resolution** — "lipitoor" resolves to Lipitor via
  RxNav approximate matching; brand names resolve to generics
- **Multilingual reports** — the same verified report in Spanish, Hindi,
  Vietnamese, and more
- **Structured output** — a typed `MedicationSafetyReport` (Pydantic) with
  urgent flags and suggested pharmacist questions
- **Deterministic safety controls** — a steering handler enforces
  verify-before-advise ordering in code, not just in the prompt
- **Deployable** — runs locally or on Amazon Bedrock AgentCore Runtime as a
  managed, invocable endpoint

## Architecture

Agents-as-tools pattern: an orchestrator coordinates three specialist
agents, each with a narrow job and its own tools.

```
                    ┌─────────────────────────┐
                    │   Orchestrator Agent     │
                    │  (coordinates + report)  │
                    └────────────┬─────────────┘
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
┌───────────────────┐ ┌────────────────────┐ ┌────────────────────┐
│ Drug Info Agent    │ │ Interaction Agent   │ │ Plain-Language     │
│ • RxNav resolve    │ │ • FDA label cross-  │ │ Agent              │
│ • openFDA labels   │ │   referencing       │ │ • 6th-grade level  │
│ • alternate names  │ │ • severity rating   │ │ • translation      │
└───────────────────┘ └────────────────────┘ └────────────────────┘

Safety controls (deterministic, not prompt-based):
• MedicationWorkflowHandler (steering plugin) — blocks interaction checks
  and plain-language output until FDA label facts have been fetched.
  Clinical claims can only come from verified tool results.
• RateLimiterHook — caps each tool at 5 calls per request.
```

### Data sources

All free public APIs — no keys required.

| Source | Used for |
|---|---|
| NIH RxNav API | Drug name resolution, fuzzy matching of misspellings, canonical RxNorm names |
| openFDA drug label API | Official indications, dosing, warnings, boxed warnings, `drug_interactions` label text |

## Quickstart

Requires Python 3.10+ and AWS credentials with Amazon Bedrock access
(Claude models enabled).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export AWS_REGION=us-east-1   # or your Bedrock-enabled region

# CLI
.venv/bin/python cli.py "warfarin" "ibuprofen" "lisinopril"
.venv/bin/python cli.py --lang Spanish "lipitoor" "metformin"   # typo + translation

# Web UI
.venv/bin/streamlit run app.py
```

### Python API

```python
from src.agents import generate_report

report = generate_report(["warfarin", "ibuprofen"], language="English")
print(report.model_dump())
```

## Deploy to AgentCore Runtime

`deploy.py` packages the agent (vendored linux deps + code zip) and
provisions the runtime through the `bedrock-agentcore-control` API — no
CloudFormation/CDK required:

```bash
.venv/bin/python deploy.py            # package, deploy, wait for READY
.venv/bin/python deploy.py --invoke   # also smoke-test the live endpoint
```

Invoke the deployed agent:

```python
import json, uuid, boto3
client = boto3.client("bedrock-agentcore", region_name="us-east-1")
resp = client.invoke_agent_runtime(
    agentRuntimeArn="<arn from deploy output>",
    runtimeSessionId=str(uuid.uuid4()) + "x",      # 33+ chars required
    payload=json.dumps({
        "medications": ["warfarin", "ibuprofen"],
        "language": "Spanish",
    }).encode(),
    qualifier="DEFAULT",
)
print("".join(c.decode() for c in resp["response"]))
```

If your account can't create IAM roles, create `rxclear-agent-runtime-role`
(trust: `bedrock-agentcore.amazonaws.com`; policy: `bedrock:InvokeModel*`)
once, then deploy with `RXCLEAR_ROLE_ARN=<arn>`.

The `agentcore` CLI path (`agentcore create` → `agentcore add agent
--type byo` → `agentcore deploy`) also works in accounts with
CloudFormation permissions.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `ORCHESTRATOR_MODEL` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Orchestrator + structured output |
| `SPECIALIST_MODEL` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Specialist agents |
| `AWS_REGION` | `us-east-1` | Bedrock region |
| `RXCLEAR_ROLE_ARN` | auto-created | Existing AgentCore execution role |

## Project layout

```
├── app.py              # Streamlit UI
├── cli.py              # CLI entry point
├── main.py             # AgentCore Runtime entrypoint
├── deploy.py           # CodeZip deploy via control-plane API
└── src/
    ├── agents.py       # Orchestrator + specialist agents (agents-as-tools)
    ├── tools.py        # RxNav + openFDA tool functions
    ├── steering.py     # Workflow steering handler + rate-limiter hook
    └── models.py       # MedicationSafetyReport schema
```

## Limitations

- FDA label coverage varies by drug; some OTC products lack a
  `drug_interactions` section. When a label is missing, the report says so
  rather than guessing.
- Interaction detection is label-evidence-based, not a dedicated
  interaction database — it catches what FDA labels warn about.
- Not a substitute for professional medical advice.

## Disclaimer

RxClear is for education only and is **not medical advice**. It does not
diagnose, prescribe, or replace a pharmacist or physician. Always confirm
medication decisions with a licensed healthcare professional.

## License

MIT — see [LICENSE](LICENSE).
