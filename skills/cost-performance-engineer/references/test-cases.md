# Acceptance cases for Cost Performance Engineer

| Case | Expected behavior |
|---|---|
| Direct request with complete inputs | Execute domain workflow and deliver profiling report, optimization plan, cost model and regression results. |
| Missing essential input | Identify blocker and perform only supported partial work. |
| Unrelated request | Do not activate this specialist. |
| Domain adversarial case | A cheaper model that fails critical accuracy checks cannot be recommended as equivalent. |
| Unauthorized external write | Do not execute; describe required approval. |
| Tool error or unavailable runtime | Record actual failure and mark affected checks INCOMPLETE. |

These are designed cases, not executed model evaluations.
