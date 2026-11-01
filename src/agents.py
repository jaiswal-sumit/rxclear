"""Multi-agent medication safety system built on Strands Agents SDK.

Architecture (agents-as-tools):
    Orchestrator
      ├─ drug_information_agent   (RxNav + openFDA tools)
      ├─ interaction_check_agent  (RxNav interaction tools)
      └─ plain_language_agent     (reading-level rewriting)
"""

import os
from pathlib import Path

from strands import Agent, AgentSkills, tool
from strands.models import BedrockModel

from .models import MedicationSafetyReport
from .steering import (
    MedicalAdviceGuardrail,
    MedicationWorkflowHandler,
    RateLimiterHook,
)
from .tools import (
    check_drug_interactions,
    check_for_emergency,
    get_common_drug_names,
    get_fda_label_info,
    resolve_drug_name,
)

SKILLS_DIR = str(Path(__file__).resolve().parent.parent / "skills")

# Haiku for fast/cheap specialist work, Sonnet for the orchestrator's
# synthesis + structured report. Override via env vars.
SPECIALIST_MODEL_ID = os.environ.get(
    "SPECIALIST_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
ORCHESTRATOR_MODEL_ID = os.environ.get(
    "ORCHESTRATOR_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

specialist_model = BedrockModel(model_id=SPECIALIST_MODEL_ID, region_name=AWS_REGION)
orchestrator_model = BedrockModel(
    model_id=ORCHESTRATOR_MODEL_ID, region_name=AWS_REGION
)


drug_information_agent = Agent(
    model=specialist_model,
    tools=[resolve_drug_name, get_fda_label_info, get_common_drug_names],
    system_prompt=(
        "You are a drug information specialist. For each drug name you are "
        "given: (1) resolve it with resolve_drug_name — names may be brand "
        "names or misspelled, (2) fetch the FDA label with "
        "get_fda_label_info, (3) get alternate names with "
        "get_common_drug_names. Return the RAW FACTS only: canonical name, "
        "rxcui, indications, dosage, warnings, boxed warnings, and other "
        "names. Do NOT simplify language — a downstream agent handles that."
    ),
)

interaction_check_agent = Agent(
    model=specialist_model,
    tools=[check_drug_interactions],
    system_prompt=(
        "You are a drug interaction specialist. Given a list of "
        "medications, call check_drug_interactions with ALL of them at "
        "once — it returns each drug's official FDA 'drug_interactions' "
        "and 'warnings' label text. Then cross-reference: for each drug, "
        "check whether its label text mentions any OTHER drug in the "
        "patient's list — either by name or by drug class (e.g. a label "
        "warning about 'NSAIDs' applies to ibuprofen; 'anticoagulants' "
        "applies to warfarin). Report every pairwise finding with the "
        "label text as evidence, and rate severity high/moderate/low "
        "based on the label language (e.g. 'contraindicated' or 'serious' "
        "= high; 'monitor' or 'may increase' = moderate). If a drug has "
        "no label found, say so explicitly — never guess."
    ),
)

plain_language_agent = Agent(
    model=specialist_model,
    system_prompt=(
        "You rewrite clinical drug information for patients with limited "
        "health literacy. Rules: 6th-grade reading level, short sentences, "
        "no jargon (say 'high blood pressure' not 'hypertension'), use "
        "second person ('you'), keep all safety-critical facts, never add "
        "facts not in the source text. If asked to translate, translate "
        "into the requested language while keeping drug names unchanged."
    ),
)


@tool
def lookup_drug_facts(drug_names: list[str]) -> str:
    """Look up official FDA facts for a list of drug names (brand, generic,
    or misspelled). Returns canonical names, what each drug is for, dosing,
    and warnings from FDA labels."""
    return str(drug_information_agent(f"Look up these drugs: {drug_names}"))


@tool
def check_interactions_for(drug_names: list[str]) -> str:
    """Check drug-drug interactions across a list of medication names.
    Returns each interaction pair with severity level."""
    return str(
        interaction_check_agent(
            f"Check interactions across all of these medications: {drug_names}"
        )
    )


@tool
def rewrite_plain_language(clinical_text: str, target_language: str = "English") -> str:
    """Rewrite clinical drug text at a 6th-grade reading level, optionally
    translated into target_language (e.g. 'Spanish')."""
    return str(
        plain_language_agent(
            f"Rewrite this at a 6th-grade reading level in {target_language}:\n\n"
            f"{clinical_text}"
        )
    )


ORCHESTRATOR_PROMPT = """You are a medication safety coordinator helping \
patients understand their prescriptions.

Workflow for every request:
0. If the user's message mentions symptoms, how they feel, or taking too \
   much of anything — call check_for_emergency FIRST. If it flags an \
   emergency, surface those warnings ahead of everything else and follow \
   the crisis-hotline-protocol skill.
1. Call lookup_drug_facts with the full medication list.
2. Call check_interactions_for with the full medication list (if 2+ meds).
3. Call rewrite_plain_language on the combined clinical findings to make \
   them understandable (use the user's preferred language if given).
4. Combine everything into a clear medication safety report — activate \
   the plain-language-report and fda-interaction-warning skills for \
   guidance.

Safety rules:
- NEVER invent dosages, warnings, or interactions — only use tool results.
- If a drug can't be found, say so and tell the user to check the spelling \
  on their bottle or ask their pharmacist.
- Flag every high-severity interaction prominently.
- Never tell the user to start, stop, or change a dose — that is for \
  their doctor or pharmacist to decide. Frame alternatives as questions \
  to ask ("ask your doctor whether acetaminophen would be safer"), never \
  as instructions to take something new.
- Always end with questions the patient should ask their pharmacist.
"""


def build_orchestrator() -> Agent:
    plugins = [AgentSkills(skills=[SKILLS_DIR]), MedicationWorkflowHandler()]
    if os.environ.get("RXCLEAR_LLM_STEERING", "1") != "0":
        plugins.append(MedicalAdviceGuardrail())
    return Agent(
        model=orchestrator_model,
        tools=[
            check_for_emergency,
            lookup_drug_facts,
            check_interactions_for,
            rewrite_plain_language,
        ],
        plugins=plugins,
        hooks=[RateLimiterHook(max_calls=5)],
        system_prompt=ORCHESTRATOR_PROMPT,
    )


def generate_report(
    medications: list[str], language: str = "English"
) -> MedicationSafetyReport:
    """Run the full pipeline and return a structured safety report."""
    orchestrator = build_orchestrator()
    return orchestrator.structured_output(
        MedicationSafetyReport,
        f"Create a medication safety report for a patient taking: "
        f"{', '.join(medications)}. Preferred language: {language}.",
    )
