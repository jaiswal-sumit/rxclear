---
name: crisis-hotline-protocol
description: What to do when check_for_emergency flags a crisis — overdose, severe symptoms, bleeding, or self-harm.
---

# Crisis hotline protocol

When `check_for_emergency` returns `emergency_detected: true`:

1. **Stop the normal report flow.** Do not continue with drug
   explanations or interaction summaries until the crisis guidance is
   surfaced.
2. **Show the crisis guidance first and verbatim.** Every flag from the
   tool goes to the top of the response — poison control numbers, 911,
   or the 988 crisis line as applicable. The tool's wording is
   authoritative; do not paraphrase or soften it.
3. **Use urgent, direct language.** "Call now" — not "you may want to
   consider contacting". This is the one place urgency beats warmth.
4. **Do not reassure.** Never say "it's probably nothing" or estimate
   whether the emergency is real. The deterministic tool flagged it;
   treat it as real.
5. **After the crisis block**, you may add one line: "Once you're safe,
   come back and we can go over your medications." Then optionally
   continue the report if the situation is ambiguous — but crisis
   guidance always stays first.

Rules:
- Every flag must appear in `urgent_flags` in the final report.
- Repeat hotline numbers exactly as the tool returned them — never
  invent a different number.
