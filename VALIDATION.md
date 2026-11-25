# Release validation: v0.3 local prototype

## Observed

- Baseline: recovered v0.2 archive, incorporated CRLF correction, ran the 18 original tests on Linux. All passed (`baseline-tests.txt`). The user separately provided a Windows v0.2 transcript: 18/18 passed, 0.266 s. That transcript is not evidence of v0.3 Windows execution.
- New release: `python -m unittest discover -s tests -v` on the local Python 3.13.5/Linux environment. **50/50 passed** (`test-results.txt`), including the original 18 unchanged test definitions and 32 added tests.
- The process-interruption test launches a separate Python interpreter, exits it between the task state update and receipt append, and verifies rollback and subsequent successful resume. It does not simulate disk failure or distributed workers.
- CLI synthetic demo: one-step incomplete result, resumed PASS, zero extra attempts on repeat, valid receipt verification, default-deny zero-attempt result. Exact exit codes and output are in `demo-evidence.json`.
- All 22 bundled skill snapshots and the original test files were preserved byte for byte from the v0.2 source archive. The metadata parser was changed, not the skill content.

## Local release gates

| Gate | Verdict | Evidence |
|---|---|---|
| Legacy regression | PASS | 18 unchanged tests |
| Policy and input validation | PASS | `test_default_deny_no_dispatch`, `test_policy_validation`, `test_plan_validation`, `test_cli_default_deny` |
| Committed-attempt and step budgets | PASS | `test_persisted_budget`, `test_zero_steps`, `test_checkpoint_resume` |
| Transactional recovery | PASS | `test_transaction_rollback`, `test_process_exit_rollback`, `test_concurrent_workers` |
| Receipt bindings and integrity | PASS | `test_receipt_binding`, `test_receipt_tamper`, `test_rehashed_invalid_verdict`, `test_external_head`, `test_task_state_tamper` |
| LF/CRLF parsing and fingerprints | PASS | `test_lf_crlf_preserve_original_hash`, duplicate/delimiter checks |
| Windows v0.3 test execution | INCOMPLETE | Requires user execution |
| Authenticated external tool permissions | NOT_APPLICABLE | No external tool integration |
| Hard CPU/memory/time enforcement | NOT_TESTED / not implemented | Only bounded inputs, committed attempts and soft inter-step deadline |
| Independent execution attestation | NOT_TESTED / not implemented | Local unsigned chain only |
| Production or live AI skill orchestration | INCOMPLETE | Not implemented, not authorized |

## Risk register

- **R1: Trusted local operator boundary.** Anyone who can modify Python code, the operator policy before initialization, or the entire DB and anchor is outside the enforced application boundary. Do not expose this prototype to untrusted callers. Host authorization and execution isolation are prerequisites for an agent-facing service.
- **R2: Unsigned evidence.** Local integrity replay is not proof that an external party performed the operations. Use an independent trust anchor and authenticated receipts before making stronger claims. Matching plan expectations is not independent validation.
- **R3: Resource exhaustion.** Only bounded pure operations, size/depth/number limits, committed attempt limits, and a soft deadline are implemented. An actual sandbox, hard timeout, and process resource limits are future requirements before arbitrary code or untrusted providers.
- **R4: Crash semantics.** Uncommitted pure operations may repeat after a crash; no external side effects are supported. The budget is for committed attempts, not every CPU invocation.
- **R5: Portability and integration.** CRLF fixtures passed on Linux; Windows v0.3 execution and independent security review remain pending. The library's actual live skill activation and AI comparative benchmarks are untested.
- **R6: Privacy.** Receipts retain raw outputs and project configuration locally. No encryption, retention policy or multi-tenant isolation is supplied. Use synthetic/non-sensitive examples only.

**Release conclusion:** ready for supervised local development validation only. Production gate: INCOMPLETE; no deployment or external execution authorization.
