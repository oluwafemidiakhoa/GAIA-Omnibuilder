# GAIA Studio 0.11: Assurance Laboratory

Run `python studio.py` and open http://127.0.0.1:8765. Click **Assurance Laboratory** in the header. Existing skill library and export routes are unchanged. No API keys or paid service calls are used by the default workspace.

## Demonstration (one click)
Click **Run demonstration**. The two hand-authored fixtures should score 30/30 and 28/30, respectively. These are synthetic verification fixtures, not AI performance evidence. A JSON evidence download is available from the results page. The demo intentionally contains a wrong aggregation and a prohibited request.

## Existing AI subscriptions (manual browser bridge)
Expand the baseline and assisted prompts. Submit each in a separate fresh conversation, same displayed model/settings, no browsing or tools. Paste both complete responses into the respective Studio fields; fenced JSON is accepted. Record provider and displayed model. Click **Compare responses**. Studio validates the suite, exact case coverage and response format, scores both responses and shows the paired result. Download JSON evidence including the submitted response objects. No Notepad or PowerShell JSON files needed. Existing ChatGPT/Claude/Gemini subscriptions are not API access; these web chats are not automatically controlled by Studio. Identity and independence remain unverified.

## Automatic local model mode (optional, no cloud inference)
Requires an already installed and running Ollama daemon, an already downloaded local model and sufficient hardware/RAM. GAIA never downloads models, sets up Ollama, creates credentials or calls public provider endpoints. Before enabling, disable cloud features on the actual daemon (see https://docs.ollama.com/faq). On Windows, quit existing Ollama and in a PowerShell window run:

```powershell
$env:OLLAMA_NO_CLOUD = '1'
ollama serve
```

Verify the daemon's log says `Ollama cloud disabled: true`. In another PowerShell window, in the GAIA repo, run:

```powershell
ollama list
$env:OLLAMA_NO_CLOUD = '1'
$env:GAIA_ENABLE_LOCAL_MODEL = '1'
python studio.py
```

Enter the exact installed non-cloud name from `ollama list` in the local form. The runtime adapter uses only `127.0.0.1:11434` via direct HTTP, lists installed models, checks the reported model digest before and after two separate chat requests, requests JSON, uses identical generation settings, and refuses partial responses. No retries or model pulls. The 120-second socket timeout is per network operation, not a hard total wall-clock deadline. If the daemon is configured differently from the launcher environment, this adapter cannot independently attest that it is offline; **do not enable it until you verified the actual daemon setting**. Model digest and usage are runtime-reported. Local hardware performance and live adapter compatibility are not established by mocked tests. Disable by restarting Studio without `GAIA_ENABLE_LOCAL_MODEL=1`.

## Evidence and security limits
The public frozen suite is unchanged. Both conditions use the same model label/settings; run order is baseline then assisted, not randomized. Reports preserve case-level outcomes, paired exact McNemar p-value and hashes. No claims of independent behavioral superiority or production security certification are authorized. All SQL executes only on the bounded synthetic SQLite fixture. Responses are treated as untrusted data. Studio inherits loopback binding, Host/Origin/CSRF protections, input limits and escaped HTML; it is not suitable for public deployment. Result data is not automatically persisted. Download it to retain the evidence. Never paste customer data or secrets. Evidence links are generated from the report without another inference run.

## Validation and rollback
Run `python -m unittest discover -s tests -v`. Local-runtime tests use mocked responses, not live model inference. Revert the v0.11 change set or return to the prior v0.10 commit; the frozen suite and scorer are unchanged.
