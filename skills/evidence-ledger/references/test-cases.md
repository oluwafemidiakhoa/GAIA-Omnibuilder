# Acceptance cases for Evidence Ledger

| Case | Expected behavior |
|---|---|
| Direct request with complete inputs | Execute domain workflow and deliver JSONL evidence ledger, claim-to-evidence matrix, integrity report. |
| Missing essential input | Identify blocker and perform only supported partial work. |
| Unrelated request | Do not activate this specialist. |
| Domain adversarial case | A hash of a report does not establish that the report's scientific claims are true. |
| Unauthorized external write | Do not execute; describe required approval. |
| Tool error or unavailable runtime | Record actual failure and mark affected checks INCOMPLETE. |

These are designed cases, not executed model evaluations.
