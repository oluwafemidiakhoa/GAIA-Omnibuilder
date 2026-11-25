# GAIA Omnibuilder OS 0.3

**Controlled local execution prototype.** Python 3.10 or later; no third-party Python dependencies, API keys, or cloud services. Keep the working v0.2 folder and databases unchanged. The new runner requires a separate database.

## Quick start (Windows Command Prompt)

Extract the archive to its own folder. Adjust the path if you choose a different extraction location.

```cmd
cd /d "%USERPROFILE%\Downloads\GAIA-Omnibuilder-OS-0.3\gaia-os-v03"
python -m unittest discover -s tests -v
python registry.py architecture database verification
python controlled.py operations
python controlled.py --db demo-v03.db init demo.json --policy demo-policy.json
python controlled.py --db demo-v03.db run --max-steps 1
python controlled.py --db demo-v03.db run
python controlled.py --db demo-v03.db verify
python controlled.py --db demo-v03.db receipts > demo-v03-receipts.json
```

The first run intentionally stops after one committed task; it returns `INCOMPLETE` (exit 1). The second resumes the remaining task and should return `PASS` (exit 0). Verify should report `valid: true`. If the project already exists, do not initialize it again; use `status`, `run`, or a new database name. On Linux/macOS, enter the extracted directory and use the same Python commands. The package includes actual Linux test and smoke-run evidence; **v0.3 execution on Windows remains to be verified by the user**.

### Demonstrate default deny

```cmd
python controlled.py --db denied-v03.db init demo.json
python controlled.py --db denied-v03.db run
python controlled.py --db denied-v03.db verify
```

Expected: `INCOMPLETE`, zero attempts used; the first task has blocker `DENIED`. The database's internally consistent ledger can still verify. This is a successful policy-denial demonstration, not a successful task execution. Exit 1 from the denied run is intentional.

### Save Windows regression evidence

```cmd
python -m unittest discover -s tests -v > windows-validation-v03.txt 2>&1
type windows-validation-v03.txt
```

## Architecture and authorization

`registry.py` indexes 22 bundled metadata snapshots; it does not load or execute instructions and does not query the live ChatGPT Skills library. These snapshots are unchanged from the v0.2 archive. LF and CRLF parsing is tested while fingerprinting the original bytes. The restricted parser accepts exactly two single-line metadata fields (`name`, `description`), not arbitrary YAML.

`controlled.py` is the new local execution broker. It has three fixed, pure operations:

| Operation | Capability | Arguments | Result |
|---|---|---|---|
| `sum` | `local.compute.sum` | `{"values":[1,2]}` | `3` |
| `echo` | `local.data.echo` | `{"value": ...}` | supplied value |
| `collect` | `local.data.collect` | `{}` | object of passed dependency results |

Local operation names are **not** the specialist capability labels. A metadata match never authorizes execution. There is no provider integration, arbitrary command execution, dynamic import, network access, skill invocation, or external action broker. The three operations run in the Python process, not in a sandbox.

The local operator supplies a policy file at initialization. `demo-policy.json` permits only `sum` and `collect`, with two committed attempts and at most eight tasks. Omission of the policy results in an empty allowlist and zero attempts. Policy is stored and hashed with the plan. Neither a plan nor a later `run` command can replace it. A changed policy requires a new project database. This is an application-level operator policy, not authenticated identity, host-issued approval, or OS-level isolation. Do not give untrusted callers direct Python or filesystem access.

## Resource and recovery rules

- Maximum 64 tasks per plan, at most 64 committed attempts, 256 KiB input-file limit, 16 KiB individual JSON arguments/expectations/results, bounded depth/nodes/numbers. The policy may reduce the task and attempt limits. JSON duplicate keys and non-finite values are rejected on CLI file ingestion.
- `--max-steps` bounds attempts committed per run; `--max-seconds` is a **soft** deadline checked between steps, not a hard task kill or resource quota. SQLite lock waits and a single operation can exceed it. No OS CPU, memory, filesystem or network quota is enforced.
- Each attempted task is terminal PASS or FAIL. No automatic retry of completed failures. Dependents cannot run unless all dependencies pass. Independent eligible tasks may still run. Denied and budget-exhausted tasks remain pending with explicit blockers.
- SQLite `BEGIN IMMEDIATE` serializes step transitions; task state and receipt append commit together. An interrupted transaction rolls back, so an uncommitted pure computation may be repeated. The attempt budget counts committed receipts, not all CPU invocations. No exactly-once guarantee for external side effects; such operations are not supported.
- A new invocation resumes unfinished eligible tasks using the stored policy and attempt budget. Completed tasks do not generate another committed execution receipt. Both legacy and controlled runners reject each other's database schemas.

## Evidence and completion

The receipt chain begins with hashes of the canonical plan and policy. Execution receipts bind operation and local capability, task ID, committed attempt number, plan/policy hashes, arguments plus prior dependency results, expectation, result, outcome and verdict. Verification replays receipt/state transitions and checks the chain and all bindings without invoking operations. It does not independently reproduce the computation. PASS is based on the plan author's expected output; an operation error cannot pass by matching an error-shaped expectation.

`verify --expected-head HASH` optionally checks an independently retained head for that exact version of the ledger. This is not digital signing. An attacker with control of the DB, source code, and trust anchor can forge evidence. The local chain alone cannot resist a consistent full rewrite or rollback. Receipt payloads contain raw results: use synthetic or non-sensitive data, and do not put credentials, confidential production data or personal records in project inputs. No identity signing, external anchor service, independent evaluator or production authorization is supplied.

Exit codes: 0 completed/valid/initialized; 1 incomplete, failed or invalid verification; 2 invalid input or operational error. `verify` checks integrity, not whether all tasks passed. `status` and `run` return task completion verdicts.

## Files

- `controlled.py`: new policy-gated runner and CLI.
- `gaia.py`: legacy deterministic runner retained for regression compatibility. It has no v0.3 policy gate and must not be used for controlled projects. Its schema guard prevents accidental reuse of a controlled DB.
- `registry.py`, `skills/`: bundled metadata discovery; not a live skill execution adapter.
- `demo.json`, `demo-policy.json`: synthetic demo and explicit policy.
- `tests/`: original 18 tests plus 32 additional tests for policy, budgets, receipts, portability, CLI, concurrency and process interruption.
- `test-results.txt`, `baseline-tests.txt`, `demo-evidence.json`, `VALIDATION.md`: observed local evidence and residual risks.
- `release-manifest.json`: SHA-256 digest of each packaged file other than the manifest itself. This is an unsigned local manifest.

## Scope and next milestone

This is a disposable local engineering prototype, not production-ready agent infrastructure. The v0.2 code was recovered from its prior archive; the Windows newline correction was incorporated and the original test files preserved. No production resource, local user files, external service, repository, credential or installed ChatGPT skill has been modified by this release. No external connector or AI model provider was invoked. Windows v0.3 validation and independent security review are outstanding. The next milestone is a read-only AI provider adapter that produces validated proposed plans, with cost accounting and operator-controlled execution. Provider requests must not be allowed to grant themselves authority.
