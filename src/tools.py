"""Drug data tools backed by free public APIs (NIH RxNav + openFDA)."""

import requests
from strands import tool

RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"
OPENFDA_LABEL = "https://api.fda.gov/drug/label.json"
TIMEOUT = 15


@tool
def resolve_drug_name(drug_name: str) -> dict:
    """Resolve a drug name (brand or generic, possibly misspelled) to a
    canonical RxNorm identifier (RxCUI) plus normalized names.

    Use this FIRST for every drug the user mentions — prescriptions and
    pill bottles often have brand names or typos.
    """
    result = {"input": drug_name, "rxcui": None, "candidates": []}

    # Exact-ish lookup
    resp = requests.get(
        f"{RXNAV_BASE}/rxcui.json", params={"name": drug_name}, timeout=TIMEOUT
    )
    if resp.ok:
        ids = resp.json().get("idGroup", {}).get("rxnormId") or []
        if ids:
            result["rxcui"] = ids[0]

    # Fuzzy matching for typos / partial names
    resp = requests.get(
        f"{RXNAV_BASE}/approximateTerm.json",
        params={"term": drug_name, "maxEntries": 5},
        timeout=TIMEOUT,
    )
    if resp.ok:
        for cand in resp.json().get("approximateGroup", {}).get("candidate", []):
            result["candidates"].append(
                {"rxcui": cand.get("rxcui"), "name": cand.get("name")}
            )
        if not result["rxcui"] and result["candidates"]:
            result["rxcui"] = result["candidates"][0]["rxcui"]

    # Canonical name + drug class for the resolved RxCUI
    if result["rxcui"]:
        resp = requests.get(
            f"{RXNAV_BASE}/rxcui/{result['rxcui']}/property.json",
            params={"propName": "RxNorm Name"},
            timeout=TIMEOUT,
        )
        if resp.ok:
            props = resp.json().get("propConceptGroup", {}).get("propConcept") or []
            if props:
                result["canonical_name"] = props[0].get("propValue")

    return result


@tool
def check_drug_interactions(drug_names: list[str]) -> dict:
    """Fetch the official FDA 'drug_interactions' and warning label text for
    each drug in the list. Returns the authoritative label passages so you
    can cross-reference which OTHER drugs in the patient's list are
    mentioned (by name or by drug class, e.g. 'anticoagulants', 'NSAIDs').

    Pass ALL medications the user takes, including OTC and supplements.
    """
    if len(drug_names) < 2:
        return {"labels": {}, "note": "Need at least 2 drugs to check interactions."}

    labels = {}
    for name in drug_names:
        sections = _fetch_label_sections(name)
        if "error" in sections:
            labels[name] = {"error": sections["error"]}
        else:
            labels[name] = {
                "drug_interactions": sections.get("drug_interactions"),
                "warnings": sections.get("warnings")
                or sections.get("warnings_and_cautions"),
            }
    return {"labels": labels}


LABEL_SECTIONS = [
    "indications_and_usage",
    "dosage_and_administration",
    "warnings",
    "warnings_and_cautions",
    "boxed_warning",
    "adverse_reactions",
    "drug_interactions",
    "pregnancy",
    "do_not_use",
    "stop_use",
    "when_using",
    "ask_doctor",
]


def _fetch_label_sections(drug_name: str) -> dict:
    """Fetch raw FDA label sections for a drug name (internal helper)."""
    for field in ("openfda.generic_name", "openfda.brand_name", "openfda.substance_name"):
        try:
            resp = requests.get(
                OPENFDA_LABEL,
                params={"search": f'{field}:"{drug_name}"', "limit": 5},
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            return {"error": str(exc)}
        if not resp.ok:
            continue

        results = resp.json().get("results", [])
        if not results:
            continue

        # Prefer a single-ingredient label — a loose search can return a
        # combination product (e.g. metformin matching ZITUVIMET =
        # sitagliptin+metformin). Rank candidates: generic name containing
        # the query, fewest " AND " ingredients, then brand-name match.
        def rank(cand: dict) -> tuple:
            generic = " ".join(cand.get("openfda", {}).get("generic_name", [])).lower()
            brand = " ".join(cand.get("openfda", {}).get("brand_name", [])).lower()
            q = drug_name.lower()
            contains = q in generic or q in brand
            combo = generic.count(" and ") + generic.count(",")
            return (not contains, combo)

        label = min(results, key=rank)

        info = {"drug": drug_name, "matched_on": field}
        names = label.get("openfda", {})
        for key in ("brand_name", "generic_name", "manufacturer_name"):
            if names.get(key):
                info[key] = names[key][0]
        for section in LABEL_SECTIONS:
            text = label.get(section)
            if text:
                # Labels can be huge; keep the first chunk per section
                info[section] = text[0][:3000]
        return info

    return {"error": f"No FDA label found for '{drug_name}'"}


@tool
def get_fda_label_info(drug_name: str) -> dict:
    """Fetch official FDA drug label sections (indications, dosage, warnings,
    boxed warnings, adverse reactions) from openFDA for a drug name.
    Returns the authoritative label text that should be translated into
    plain language.
    """
    return _fetch_label_sections(drug_name)


EMERGENCY_RULES = [
    (
        ["overdose", "took too many", "too much of", "took too much",
         "double dose", "whole bottle"],
        "Possible overdose — call Poison Control at 1-800-222-1222 or emergency services NOW.",
    ),
    (
        ["chest pain", "can't breathe", "cant breathe", "trouble breathing",
         "throat closing", "face swelling", "swelling of face", "lips swelling"],
        "Possible emergency symptoms — call 911 / emergency services NOW.",
    ),
    (
        ["suicidal", "kill myself", "hurt myself", "self harm", "end it all",
         "don't want to live", "want to die"],
        "Possible crisis — call or text 988 (Suicide & Crisis Lifeline) NOW. Free, 24/7.",
    ),
    (
        ["won't stop bleeding", "severe bleeding", "vomiting blood",
         "blood in stool", "black stool", "coughing up blood"],
        "Possible internal bleeding — seek emergency care immediately.",
    ),
    (
        ["fainted", "unconscious", "seizure", "not responding"],
        "Medical emergency — call 911 / emergency services NOW.",
    ),
]


@tool
def check_for_emergency(user_text: str) -> dict:
    """Screen the patient's message for medical emergencies: overdose,
    severe symptoms, uncontrolled bleeding, or self-harm. Call this FIRST
    whenever the user mentions how they feel, symptoms they're
    experiencing, or taking too much of a medication — before doing any
    drug lookups. Returns urgent guidance that must be surfaced to the
    user ahead of everything else.
    """
    text = user_text.lower()
    flags = [msg for keywords, msg in EMERGENCY_RULES
             if any(k in text for k in keywords)]
    return {
        "emergency_detected": bool(flags),
        "flags": flags,
        "instruction": (
            "Surface these warnings FIRST, prominently, before anything else."
            if flags else "No emergency detected — proceed normally."
        ),
    }


@tool
def get_common_drug_names(rxcui: str) -> dict:
    """Get brand names and synonyms for a resolved RxCUI so the report can
    tell the user all the names their drug might appear under (important
    for patients whose pharmacy switches generics).
    """
    resp = requests.get(
        f"{RXNAV_BASE}/rxcui/{rxcui}/related.json",
        params={"rela": "tradename_of has_tradename"},
        timeout=TIMEOUT,
    )
    names = []
    if resp.ok:
        for group in resp.json().get("relatedGroup", {}).get("conceptGroup", []):
            for prop in group.get("conceptProperties", []):
                names.append(prop.get("name"))
    return {"rxcui": rxcui, "related_names": list(dict.fromkeys(names))[:10]}
