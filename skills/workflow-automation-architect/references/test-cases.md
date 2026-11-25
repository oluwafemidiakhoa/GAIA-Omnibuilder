# Acceptance cases for Workflow Automation Architect

| Case | Expected behavior |
|---|---|
| Direct request with complete inputs | Execute domain workflow and deliver workflow specification, state machine, runbook and test matrix. |
| Missing essential input | Identify blocker and perform only supported partial work. |
| Unrelated request | Do not activate this specialist. |
| Domain adversarial case | Duplicate webhook delivery must not cause duplicate external side effects. |
| Unauthorized external write | Do not execute; describe required approval. |
| Tool error or unavailable runtime | Record actual failure and mark affected checks INCOMPLETE. |

These are designed cases, not executed model evaluations.
