"""Opt-in Ollama loopback adapter. No downloads, credentials, cloud endpoints or retries."""
import http.client
import json
import os
import re
import threading
import time
import assurance
import laboratory

MAX_BODY = 2_000_000
TIMEOUT = 120
OPTIONS = {'temperature': 0, 'seed': 42, 'num_ctx': 8192, 'num_predict': 4096}
RUN_LOCK = threading.Lock()


def enabled():
    # This is an opt-in, not proof that the separately running daemon is offline.
    return os.environ.get('GAIA_ENABLE_LOCAL_MODEL') == '1' and os.environ.get('OLLAMA_NO_CLOUD') == '1'


def request(path, payload=None):
    if path not in ('/api/tags', '/api/chat'):
        raise ValueError('Unsupported local endpoint.')
    connection = http.client.HTTPConnection('127.0.0.1', 11434, timeout=TIMEOUT)
    try:
        connection.request('GET' if payload is None else 'POST', path,
                           body=None if payload is None else assurance.canonical(payload),
                           headers={'Content-Type': 'application/json', 'Connection': 'close'})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('Local runtime rejected the request.')
        raw = response.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise ValueError('Local runtime response too large.')
        return json.loads(raw)
    except (OSError, http.client.HTTPException, ValueError, RecursionError) as exc:
        raise ValueError('Local runtime unavailable or returned invalid data.') from exc
    finally:
        connection.close()


def compare(model, parse_response):
    if not enabled():
        raise ValueError('Local inference is disabled. See setup instructions.')
    if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)?', model) or len(model)>100 or 'cloud' in model.lower():
        raise ValueError('Enter an installed non-cloud model name from ollama list.')
    if not RUN_LOCK.acquire(blocking=False):
        raise ValueError('Another local assessment is already running.')
    try:
        tags = request('/api/tags')
        models = tags.get('models', []) if type(tags) is dict else []
        matching = [m for m in models if type(m) is dict and m.get('name') == model and isinstance(m.get('digest'), str) and re.fullmatch(r'(?:sha256:)?[a-f0-9]{64}', m['digest']) and type(m.get('size')) is int and m['size'] > 0 and not m.get('remote_host') and not m.get('remote_model')]
        if len(matching) != 1:
            raise ValueError('Model not found in the installed local model list; no download attempted.')
        model_digest = matching[0]['digest']
        submissions, usage = {}, {}
        for condition in ('baseline', 'assisted'):
            started = time.monotonic()
            response = request('/api/chat', {'model':model, 'messages':[{'role':'user','content':laboratory.prompt(condition)}], 'stream':False, 'format':'json', 'options':OPTIONS, 'keep_alive':0})
            try:
                if response['model'] != model or response['done'] is not True or response.get('done_reason') != 'stop':
                    raise ValueError('Incomplete local response or model mismatch.')
                submission = parse_response(response['message']['content'])
                if type(submission) is not dict or submission.get('submission_kind') != 'MANUAL_UNVERIFIED':
                    raise ValueError('Invalid submission kind.')
                assurance.score(submission)
            except (ValueError, KeyError, TypeError, RecursionError, UnicodeError) as exc:
                raise ValueError(condition.title()+': local model returned incomplete or invalid benchmark JSON. No score fabricated.') from exc
            submissions[condition] = submission
            usage[condition] = {'elapsed_seconds': round(time.monotonic()-started,3), **{key:response[key] for key in ('prompt_eval_count','eval_count') if type(response.get(key)) is int and response[key]>=0}}
        final_tags = request('/api/tags')
        if type(final_tags) is not dict or not any(type(m) is dict and m.get('name')==model and m.get('digest')==model_digest for m in final_tags.get('models',[])):
            raise ValueError('Installed model digest changed during the run.')
        report = laboratory.paired(submissions['baseline'], submissions['assisted'], 'Ollama loopback', model)
        report.update(mode='LOCAL_RUNTIME_UNVERIFIED', local_model_digest_reported=model_digest,
                      local_only_configuration_independently_verified=False, generation_options=OPTIONS.copy(),
                      usage=usage, submissions=submissions)
        return report
    finally:
        RUN_LOCK.release()
