---
name: plain-language-report
description: Step-by-step procedure for turning real FDA label facts (fetched via lookup_drug_facts) into a plain-language medication summary a patient can act on.
---

# Explain a medication in plain language

Follow these steps for EACH drug in the patient's list, using only what
`lookup_drug_facts` returned from NIH RxNav and openFDA:

1. Confirm the canonical name resolved by `resolve_drug_name`. If the input
   was a brand name or had a typo, note the resolved name (e.g. "lipitoor"
   → "Lipitor") — patients should know the agent corrected it.
2. State what the drug treats in one sentence, using everyday words —
   "high blood pressure", not "hypertension"; "blood thinner", not
   "anticoagulant" — from the label's `indications_and_usage`.
3. Give the label's `dosage_and_administration` guidance at a 6th-grade
   level: how often, with or without food, missed-dose instructions if the
   label states them. Never state a dose the label didn't state.
4. List the top 3–5 warnings in plain language — prioritize `boxed_warning`
   and `warnings` sections, then `adverse_reactions`.
5. List other names the drug is sold under (from `get_common_drug_names`)
   so the patient recognizes it if the pharmacy switches generics.

Rules:
- Grade-6 reading level, short sentences, second person ("you").
- Only facts that came from tool results — never general knowledge.
- If `get_fda_label_info` returned an error or a combination product,
  say so plainly and point the user to their pharmacist rather than
  guessing.
- End each drug with "Questions? Ask your pharmacist" when anything is
  unclear.
