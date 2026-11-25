# GAIA Data Agent Assurance — development kit

Scope: synthetic SQLite, one tenant, 30 fixed development cases (24 correctness, 6 explicit abstention). Monetary values are integer cents; Q1 is calendar Q1 2026. Exact typed row multiset scoring ignores ordering but preserves duplicates. Denial cases are never dispatched. Reference SQL is a hand-authored fixture, not model output. The literal expected rows are manually derived from the synthetic business records and may be independently reviewed. This is a public development suite, not a blinded or held-out benchmark. A hash binds the data, rules, questions and oracle but does not prove chronology or external identity.

Acceptance: all 30 reference cases pass; wrong aggregation fails; duplicate rows fail; non-SELECT, ATTACH, PRAGMA, multi-statement, unapproved tables/functions, and recursive queries are rejected; malformed/duplicate/incomplete responses and mismatched suite hashes are rejected. Existing 109 tests must remain passing. No paid API use, no production connection, no real customer data.

Python 3.11+ (SQLite setlimit). From repository root:

```
python -m unittest discover -s tests -v
python assurance.py suite --out assurance-suite.json
python assurance.py fixture --out assurance-reference.json
python assurance.py score --submission assurance-reference.json --out assurance-report.json
```

For an exploratory model assessment, provide ONLY the generated suite (not reference/oracle), and optionally the synthetic rows if the agent cannot inspect a database. Ask for one JSON object with suite_sha256, submission_kind MANUAL_UNVERIFIED, and responses mapping every case ID to exactly {"sql":"..."} or {"abstain":true}. Save the original response separately. Do not alter it to make tests pass. Score using the same command with a different output name. The evaluator does not authenticate model identity, detect training contamination, verify text answers, measure agent latency, or test actual production authorization. The tenant is physically filtered before execution; real row-level security and SQL Server semantics are not tested. This process is not a general-purpose hostile-code sandbox; use synthetic local data only. SQLite authorizer and VM instruction limit are bounded defense-in-depth, not OS isolation. Output files are created exclusively, not overwritten. The score command returns 0 for a structurally valid assessment even if cases fail; inspect the report. No claims of customer demand or production readiness.

Commercial use: show the synthetic evidence as a demo. A paid pilot requires customer-defined metric semantics, separately approved test data and environments, a private held-out suite, independent adjudication, and agreed scope. Do not upload employer or customer data.
