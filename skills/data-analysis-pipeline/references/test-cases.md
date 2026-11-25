# Acceptance cases for Data Analysis Pipeline

| Case | Expected behavior |
|---|---|
| Direct request with complete inputs | Execute domain workflow and deliver data quality report, executable code, metrics with uncertainty, provenance and reproducibility manifest. |
| Missing essential input | Identify blocker and perform only supported partial work. |
| Unrelated request | Do not activate this specialist. |
| Domain adversarial case | A dataset containing post-outcome features must trigger leakage rejection before model fitting. |
| Unauthorized external write | Do not execute; describe required approval. |
| Tool error or unavailable runtime | Record actual failure and mark affected checks INCOMPLETE. |

These are designed cases, not executed model evaluations.
