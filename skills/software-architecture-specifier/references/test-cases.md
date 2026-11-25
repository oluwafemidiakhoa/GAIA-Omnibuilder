# Acceptance cases for Software Architecture Specifier

| Case | Expected behavior |
|---|---|
| Direct request with complete inputs | Execute domain workflow and deliver system context, component contracts, ADRs, migration and rollback plan, acceptance criteria. |
| Missing essential input | Identify blocker and perform only supported partial work. |
| Unrelated request | Do not activate this specialist. |
| Domain adversarial case | A zero-downtime request with an incompatible schema change must include expand-contract migration or flag infeasibility. |
| Unauthorized external write | Do not execute; describe required approval. |
| Tool error or unavailable runtime | Record actual failure and mark affected checks INCOMPLETE. |

These are designed cases, not executed model evaluations.
