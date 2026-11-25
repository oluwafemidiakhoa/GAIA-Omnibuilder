# Acceptance cases for Universal Builder Router

| Case | Expected behavior |
|---|---|
| Direct request with complete inputs | Execute domain workflow and deliver build brief, capability matrix, dependency graph, acceptance matrix, evidence-backed completion report. |
| Missing essential input | Identify blocker and perform only supported partial work. |
| Unrelated request | Do not activate this specialist. |
| Domain adversarial case | A request to deploy with no deployment connector must produce a blocked release, not a deployment claim. |
| Unauthorized external write | Do not execute; describe required approval. |
| Tool error or unavailable runtime | Record actual failure and mark affected checks INCOMPLETE. |

These are designed cases, not executed model evaluations.
