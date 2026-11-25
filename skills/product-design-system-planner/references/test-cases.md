# Acceptance cases for Product Design System Planner

| Case | Expected behavior |
|---|---|
| Direct request with complete inputs | Execute domain workflow and deliver journey map, component specifications, token inventory, accessibility checks. |
| Missing essential input | Identify blocker and perform only supported partial work. |
| Unrelated request | Do not activate this specialist. |
| Domain adversarial case | A color-only error state must be rejected or supplemented with text and semantic cues. |
| Unauthorized external write | Do not execute; describe required approval. |
| Tool error or unavailable runtime | Record actual failure and mark affected checks INCOMPLETE. |

These are designed cases, not executed model evaluations.
