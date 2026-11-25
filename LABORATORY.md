# GAIA Assurance Laboratory v0.10

Exploratory paired comparison on the public 30-case synthetic SQLite benchmark. Not a private holdout, authenticated provider experiment or production security certification.

1. Run `python laboratory.py prepare --out lab-run` once. Keep the manifest and prompts unchanged.
2. For each provider, use two fresh sessions with the same displayed model and settings. Disable browsing/tools/memory if available. Do not attach repository files or reference answers. Alternate condition order across providers; record order, date, displayed model, settings and deviations separately. The benchmark is public and contamination cannot be ruled out.
3. Paste baseline.txt into one session and assisted.txt into the other. Save the first complete raw JSON responses as separate UTF-8 files. Do not repair SQL or regenerate selectively. Record malformed/incomplete outputs as protocol failures; the current scorer rejects them rather than imputing scores.
4. Run `python laboratory.py compare --baseline chatgpt-baseline.json --assisted chatgpt-assisted.json --provider ChatGPT --model DISPLAYED_MODEL --manifest lab-run/manifest.json --out chatgpt-paired.json`. Repeat for Claude and Gemini. Labels are self-reported; retain original transcripts privately.
5. Report all paired outcomes, percentage-point difference and exact two-sided McNemar p-values descriptively. No pooled significance claim: cases share a fixture and outputs within a session are dependent. No claim of generalization or superiority. One session per condition cannot distinguish stochastic effects from intervention effects.

No API calls, dependencies, or changes to the v0.9 benchmark. Prompt hashes are SHA-256 of canonical JSON string encoding (not raw text file hashes). A local protocol hash is not an independently trusted timestamp. The code cannot authenticate actual model identity or confirm that a prompt was sent. Never label a fixture as an observed model response.
