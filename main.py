"""AgentCore Runtime entrypoint for RxClear.

Accepts:
    {"medications": ["warfarin", "ibuprofen"], "language": "Spanish"}
    {"prompt": "warfarin, ibuprofen"}            (comma-separated fallback)
    {"prompt": "{\"medications\": [...]}"}        (JSON-string fallback)

Deploy with: .venv/bin/python deploy.py
"""

import json

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from src.agents import generate_report

app = BedrockAgentCoreApp()


def _parse_payload(payload: dict) -> tuple[list[str], str]:
    language = payload.get("language", "English")
    meds = payload.get("medications")
    if not meds:
        raw = payload.get("prompt", "")
        try:
            parsed = json.loads(raw)
            meds = parsed.get("medications")
            language = parsed.get("language", language)
        except (TypeError, json.JSONDecodeError):
            pass
        if not meds:
            meds = [m.strip() for m in raw.split(",") if m.strip()]
    if not meds:
        raise ValueError("Provide 'medications' (list) or 'prompt' (comma-separated names).")
    return meds, language


@app.entrypoint
def invoke(payload, context):
    meds, language = _parse_payload(payload)
    report = generate_report(meds, language=language)
    return report.model_dump()


if __name__ == "__main__":
    app.run()
