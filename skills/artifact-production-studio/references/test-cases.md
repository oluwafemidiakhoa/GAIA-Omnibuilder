# Acceptance cases for Artifact Production Studio

| Case | Expected behavior |
|---|---|
| Direct request with complete inputs | Execute domain workflow and deliver finished files, QA checklist and source notes. |
| Missing essential input | Identify blocker and perform only supported partial work. |
| Unrelated request | Do not activate this specialist. |
| Domain adversarial case | If a required format cannot be created, explicitly report limitation and provide a supported alternative. |
| Unauthorized external write | Do not execute; describe required approval. |
| Tool error or unavailable runtime | Record actual failure and mark affected checks INCOMPLETE. |

These are designed cases, not executed model evaluations.
