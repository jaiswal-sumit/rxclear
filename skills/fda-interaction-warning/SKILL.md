---
name: fda-interaction-warning
description: How to communicate a drug interaction finding backed by FDA label text — severity, plain-language explanation, and a safe next action.
---

# Responding to a drug interaction

When `check_interactions_for` returns FDA label text and the interaction
agent surfaces a finding, follow these steps:

1. **Lead with severity.** High-severity findings go first, prominently,
   before per-drug explanations. Use clear framing: "Important: these two
   don't mix safely."
2. **Explain the mechanism plainly.** One or two sentences on WHY it's
   risky, at a 6th-grade level (e.g. "both thin your blood, so bleeding
   becomes harder to stop") — drawn from the label text the tool returned.
3. **Name the safer question, not the prescription.** Never tell the user
   to stop or start anything — instead tell them exactly who to contact
   and what to ask ("Call your doctor today and ask whether a different
   pain reliever like acetaminophen is safer for you").
4. **Cite the evidence.** Say explicitly that the warning comes from the
   official FDA drug label — and quote or paraphrase the actual label
   line the tool returned (e.g. "ibuprofen's label warns NSAIDs can cause
   severe stomach bleeding when taken with a blood thinner"). This is
   what separates a verified warning from a guess.
5. **Class-level warnings count.** If a label warns about a drug class
   (NSAIDs, anticoagulants, MAOIs), apply it to every drug in that class
   on the patient's list and say so explicitly.

Rules:
- Never soften a high-severity finding.
- Never invent interactions the tool didn't return.
- If a drug's label had no `drug_interactions` section, say "no
  interaction listed on this drug's FDA label" — not "these are safe
  together".
