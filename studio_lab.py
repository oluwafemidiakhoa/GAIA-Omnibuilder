"""Studio assessment workspace. Offline demonstrations and manual model imports."""
import base64
import json
import re
import secrets
from urllib.parse import parse_qs, urlsplit
import assurance
import laboratory
import studio_local

MAX_JSON = 262144
MAX_FORM = 2 * MAX_JSON * 3 + 8192


class LabInputError(ValueError):
    """Safe, user-facing validation message."""


def parse_response(raw):
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > MAX_JSON:
        raise ValueError('Response exceeds the size limit.')
    raw = raw.strip().lstrip('\ufeff').strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```', raw, re.S | re.I)
    if fenced:
        raw = fenced.group(1)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key.')
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError('Non-finite JSON value.')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)


def demonstration():
    good = assurance.fixture()
    bad = assurance.fixture()
    bad['responses']['DA-01'] = {'sql': "SELECT sum(amount) FROM orders JOIN lines ON orders.id=lines.order_id WHERE status='posted' AND day<'2026-04-01'"}
    bad['responses']['DA-27'] = {'sql': 'DELETE FROM orders'}
    return {'mode': 'SYNTHETIC_DEMONSTRATION', 'reference': assurance.score(good),
            'defective': assurance.score(bad), 'provider_identity_verified': False,
            'behavioral_claim_authorized': False}


def evaluate_manual(baseline, assisted, provider, model):
    if not all(isinstance(x, str) and 0 < len(x.strip()) <= 200 for x in (provider, model)) or model.strip().upper() == 'DISPLAYED_MODEL_NAME':
        raise LabInputError('Enter the actual provider and displayed model/settings.')
    parsed = {}
    for label, raw in [('Baseline', baseline), ('Assisted', assisted)]:
        try:
            data = parse_response(raw)
            if type(data) is not dict or data.get('submission_kind') != 'MANUAL_UNVERIFIED':
                raise ValueError('Expected manual submission.')
            parsed[label.lower()] = data
            assurance.score(data)
        except (ValueError, TypeError, RecursionError, UnicodeError) as e:
            raise LabInputError(label + ': invalid JSON, wrong suite, missing cases, or invalid response shape.') from e
    result = laboratory.paired(parsed['baseline'], parsed['assisted'], provider, model)
    result['mode'] = 'MANUAL_UNVERIFIED_COMPARISON'
    result['submissions'] = parsed
    return result


def extend(base, token, page, esc):
    """Wrap the existing Studio handler without replacing its library routes."""
    def workspace(message='', values=None):
        v = values or {}
        local_form = (f'<form class="editor" action="/lab/local" method="post"><input type="hidden" name="token" value="{esc(token)}"><label for="local_model">Installed local model (exact name from ollama list)</label><input id="local_model" name="model" maxlength="100" required><p><button>Run local model comparison</button></p></form>' if studio_local.enabled() else '<p>Local inference is disabled. See STUDIO-LAB.md for offline Ollama setup.</p>')
        return page('Assurance Laboratory', f'''<h1>Assurance Laboratory</h1>
<p>Evaluate business correctness and appropriate abstention against 30 frozen synthetic cases.</p>
<div class="notice">Public benchmark. Demo fixtures are not AI results. Demo and manual scoring make no external calls. Optional local inference requires a separately configured offline runtime.</div>
<form action="/lab/demo" method="post"><input type="hidden" name="token" value="{esc(token)}"><button>Run demonstration</button> <button name="download" value="1">Download demo evidence</button></form>
<h2>Automatic local evaluation</h2><p>Two separate local model requests. No model downloads. Use only with Ollama cloud features disabled.</p>{local_form}
<h2>Prepare a model comparison</h2><p>Use two fresh conversations with the same model and settings. Copy the prompts below, then paste the first complete responses here. No files or terminal commands required.</p>
<div class="toolbar"><a class="button" href="/lab/manifest">Download protocol</a><a href="https://chatgpt.com/" target="_blank" rel="noopener noreferrer">ChatGPT</a><a href="https://claude.ai/" target="_blank" rel="noopener noreferrer">Claude</a><a href="https://gemini.google.com/" target="_blank" rel="noopener noreferrer">Gemini</a></div>
<details><summary>Baseline prompt</summary><textarea readonly aria-label="Baseline prompt" rows="8">{esc(laboratory.prompt('baseline'))}</textarea></details>
<details><summary>Assisted prompt</summary><textarea readonly aria-label="Assisted prompt" rows="8">{esc(laboratory.prompt('assisted'))}</textarea></details>
{('<p role="alert" class="notice">'+esc(message)+'</p>') if message else ''}
<form class="editor" action="/lab/compare" method="post"><input type="hidden" name="token" value="{esc(token)}">
<label for="provider">Provider</label><input id="provider" name="provider" required maxlength="200" value="{esc(v.get('provider',''))}" placeholder="ChatGPT, Claude or Gemini">
<label for="model">Displayed model and settings</label><input id="model" name="model" required maxlength="200" value="{esc(v.get('model',''))}">
<label for="baseline">Baseline response JSON</label><textarea id="baseline" name="baseline" rows="8" required>{esc(v.get('baseline',''))}</textarea>
<label for="assisted">Assisted response JSON</label><textarea id="assisted" name="assisted" rows="8" required>{esc(v.get('assisted',''))}</textarea>
<p><button>Compare responses</button> <button name="download" value="1">Download comparison evidence</button></p></form>''')

    def results(report):
        if report['mode'] == 'SYNTHETIC_DEMONSTRATION':
            b, s = report['reference'], report['defective']
            title = 'Synthetic demonstration'
            metrics = f'<div class="metrics"><div><strong>{b["passed"]}/{b["total"]}</strong>Reference fixture</div><div><strong>{s["passed"]}/{s["total"]}</strong>Defective fixture</div></div>'
            rows = ''.join(f'<p>{esc(r["id"])} — {esc(r["outcome"])}</p>' for r in s['cases'] if not r['pass'])
        else:
            title = 'Exploratory model comparison'
            metrics = f'<div class="metrics"><div><strong>{report["baseline_passed"]}/{report["total"]}</strong>Baseline</div><div><strong>{report["assisted_passed"]}/{report["total"]}</strong>Assisted</div><div><strong>{report["delta_percentage_points"]:+.1f} pp</strong>Difference</div></div><p>Wins {report["wins"]}; losses {report["losses"]}; ties {report["ties"]}; exact McNemar p = {report["exact_mcnemar_p"]:.4g}.</p>'
            rows = ''.join(f'<p>{esc(r["id"])} — {esc(r["baseline_outcome"])} / {esc(r["assisted_outcome"])}</p>' for r in report['cases'])
        encoded = base64.b64encode(assurance.canonical(report)).decode('ascii')
        return page(title, f'<h1>{title}</h1><div class="notice">Not independently verified model performance or production certification.</div>{metrics}<h2>Case outcomes</h2>{rows}<p><a class="button" download="assurance-evidence.json" href="data:application/json;base64,{encoded}">Download evidence JSON</a></p><details><summary>Evidence JSON</summary><pre>{esc(json.dumps(report,indent=2))}</pre></details><p><a href="/lab">Return to laboratory</a></p>')

    class LabHandler(base):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path not in ('/lab', '/lab/manifest'):
                return super().do_GET()
            if not self.host_ok():
                return self.reply(403,b'Forbidden','text/plain')
            if path == '/lab/manifest':
                return self.reply(200, assurance.canonical(laboratory.manifest()), 'application/json', 'lab-manifest.json')
            return self.reply(200, workspace())

        def do_POST(self):
            if self.path not in ('/lab/demo', '/lab/compare', '/lab/local'):
                return super().do_POST()
            if not self.host_ok() or self.headers.get('Origin') != 'http://'+self.headers.get('Host',''):
                return self.reply(403,b'Forbidden','text/plain')
            values = {}
            try:
                size = int(self.headers.get('Content-Length','-1'))
                if not 0 <= size <= MAX_FORM or self.headers.get('Content-Type') != 'application/x-www-form-urlencoded':
                    raise ValueError('Invalid form or size.')
                data = parse_qs(self.rfile.read(size).decode('utf-8'), keep_blank_values=True, strict_parsing=True, max_num_fields=6, errors='strict')
                if any(len(x)!=1 for x in data.values()) or not secrets.compare_digest(data.get('token',[''])[0],token):
                    return self.reply(403,b'Forbidden','text/plain')
                values = {k:x[0] for k,x in data.items() if k != 'token'}
                download = values.pop('download','')
                if download not in ('','1'):
                    raise ValueError('Invalid download option.')
                if self.path == '/lab/demo' and not values:
                    report = demonstration()
                elif self.path == '/lab/compare' and set(values)=={'baseline','assisted','provider','model'}:
                    report = evaluate_manual(**values)
                elif self.path == '/lab/local' and set(values)=={'model'}:
                    report = studio_local.compare(values['model'], parse_response)
                else:
                    raise ValueError('Missing or unexpected fields.')
                if download:
                    return self.reply(200, assurance.canonical(report), 'application/json', 'assurance-evidence.json')
                return self.reply(200, results(report))
            except LabInputError as exc:
                return self.reply(400, workspace(str(exc), {k:v for k,v in values.items() if k in ('provider','model','baseline','assisted') and len(v)<=MAX_JSON}))
            except (ValueError,TypeError,UnicodeError,RecursionError):
                # Do not echo raw parser exceptions or unbounded input.
                message = ('Local assessment rejected. Check offline configuration, installed model name and complete model JSON.' if self.path == '/lab/local' else 'Assessment rejected. Check both complete JSON responses, model labels and the frozen suite.')
                return self.reply(400, workspace(message, {k:v for k,v in values.items() if k in ('provider','model','baseline','assisted') and len(v)<=MAX_JSON}))
    return LabHandler
