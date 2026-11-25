# Acceptance cases for Scientific Experiment Designer

| Case | Expected behavior |
|---|---|
| Direct request with complete inputs | Execute domain workflow and deliver protocol, power assumptions, analysis plan, falsification criteria, metadata plan. |
| Missing essential input | Identify blocker and perform only supported partial work. |
| Unrelated request | Do not activate this specialist. |
| Domain adversarial case | Missing effect sizes must yield sensitivity analysis rather than invented empirical estimates. |
| Unauthorized external write | Do not execute; describe required approval. |
| Tool error or unavailable runtime | Record actual failure and mark affected checks INCOMPLETE. |

These are designed cases, not executed model evaluations.
