# GAIA Studio 0.8

Local, single-operator prototype. Python 3.10+, standard library only.

```
python -m unittest discover -s tests -v
python studio.py
```

Open http://127.0.0.1:8765 in a browser. Stop with Ctrl+C. Optional `--port 8766` and `--drafts PATH`.

Search the 22 bundled capabilities, open a skill, review its unsigned passport and text, download its ZIP, passport or instructions, or create a new text-only draft. Drafts persist under `studio-drafts/`; existing names cannot be overwritten. Drafts require independent review. The ZIP for a newly created draft contains SKILL.md only; platform-specific metadata or resources must be added before native installation if required. Use `bridge.py` for full bundled library exports.

Security: loopback bind, exact Host checks, same-origin POST and per-process CSRF token, bounded form input, text escaping, CSP, no-store, no dynamic execution, bridge static checks. These controls are not multi-user authentication or production isolation. Keep the local filesystem trusted. A local attacker or process may access files and the service. No public hosting, archive upload, arbitrary scripts, version editing, model evaluation, signatures, billing or cloud accounts. No browser rendering/accessibility audit performed. No live provider requests. Do not publish this local server to the internet.

Design: slate/teal workspace, serif editorial heading, compact searchable list, explicit review-required labels, mobile layout and keyboard focus. The existing runtime and bridge are retained. Source: v0.7 release archive, not a current remote checkout. Tests: 98 existing + 11 new, observed 109 passing on Linux. Windows validation pending. No remote changes.
