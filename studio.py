"""Local-only GAIA Studio. Text-only drafts; no model calls or skill activation."""
import argparse, html, io, json, secrets, tempfile, zipfile, re
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
import bridge
import studio_lab

ROOT=Path(__file__).resolve().parent

def esc(s): return html.escape(str(s), quote=True)

def package(files,name):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for k,v in sorted(files.items()):
            i=zipfile.ZipInfo(name+'/'+k,(1980,1,1,0,0,0)); i.compress_type=zipfile.ZIP_DEFLATED; i.external_attr=0o100644<<16; z.writestr(i,v)
    return b.getvalue()

class Library:
    def __init__(self, source, drafts):
        self.source=Path(source); self.drafts=Path(drafts)
        self.drafts.mkdir(parents=True,exist_ok=True)
        if self.drafts.is_symlink(): raise ValueError('invalid draft directory')
    def get(self,name):
        if not bridge.NAME.fullmatch(name): raise ValueError('invalid name')
        for root in (self.source,self.drafts):
            p=root/name
            if p.exists() or p.is_symlink():
                files, passport=bridge.inspect(p)
                passport['archive_sha256']=bridge.digest(package(files,name))
                return files,passport
        raise KeyError(name)
    def catalog(self):
        names={p.name for root in (self.source,self.drafts) for p in root.iterdir() if p.is_dir() or p.is_symlink()}
        return [self.get(n)[1] for n in sorted(names)]
    def create(self,name,description,body):
        if not bridge.NAME.fullmatch(name) or len(name)>80 or not description.strip() or len(description)>500 or '\n' in description or '\r' in description or not body.strip(): raise ValueError('invalid draft fields')
        if (self.source/name).exists() or (self.drafts/name).exists(): raise ValueError('name already exists')
        text=f'---\nname: {name}\ndescription: {description}\n---\n\n{body}\n'.encode()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/name; p.mkdir(); (p/'SKILL.md').write_bytes(text)
            bridge.inspect(p)
            dest=self.drafts/name
            dest.mkdir(exist_ok=False)
            try: (dest/'SKILL.md').write_bytes(text)
            except OSError:
                (dest/'SKILL.md').unlink(missing_ok=True); dest.rmdir(); raise
        return self.get(name)[1]

CSS='''*{box-sizing:border-box}body{margin:0;background:#f3f5f5;color:#17313a;font:15px/1.55 system-ui,sans-serif}header{background:#17313a;color:#fff;padding:22px max(24px,calc((100vw - 1160px)/2));display:flex;align-items:center;justify-content:space-between;gap:12px}header a{color:#fff;text-decoration:none;font-weight:700;letter-spacing:.05em}main{max-width:1160px;margin:auto;padding:32px 24px}h1{font:500 clamp(30px,5vw,48px)/1.12 Georgia,serif;margin:0 0 12px}h2{font-size:20px}p{max-width:72ch}a{color:#176b68}small,.muted{color:#526970}.notice{border-left:4px solid #b77929;background:#fff8e8;padding:12px 16px;margin:22px 0}.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}input,textarea{font:inherit;padding:10px;border:1px solid #a6b7b9;border-radius:5px;background:white;color:#17313a}input[type=search]{flex:1;min-width:180px}button,.button{background:#176b68;color:white;border:0;padding:10px 16px;border-radius:5px;font:inherit;font-weight:600;cursor:pointer;text-decoration:none;display:inline-block}a:focus-visible,button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #ca8a25;outline-offset:3px}.entry{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:20px;padding:18px 0;border-top:1px solid #c7d2d3}.entry h2{margin:0}.entry p{margin:5px 0}.status{font-size:12px;color:#825311}.metrics{display:flex;gap:32px;border-bottom:1px solid #c7d2d3;padding:16px 0;flex-wrap:wrap}.metrics strong{font:32px Georgia;display:block}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#e6eeee;padding:16px;border-radius:5px;font-size:13px}label{display:block;margin:14px 0 5px;font-weight:600}form.editor input,textarea{width:100%}footer{padding:24px;color:#526970;text-align:center}@media(max-width:600px){.entry{grid-template-columns:1fr;gap:5px}header{flex-wrap:wrap}}'''

def page(title,body):
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+' | GAIA Studio</title><style>'+CSS+'</style><header><a href="/">GAIA / Studio</a><a href="/lab">Assurance Laboratory</a><span>Local workspace · v0.11</span></header><main>'+body+'</main><footer>GaiaLab — local prototype. No execution authority granted.</footer></html>').encode()

def handler(lib,token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def reply(self,status,data,kind='text/html; charset=utf-8',filename=None):
            self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"); self.send_header('Referrer-Policy','same-origin')
            if filename: self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
            self.end_headers(); self.wfile.write(data)
        def host_ok(self): return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        def do_GET(self):
            if not self.host_ok(): return self.reply(403,b'Forbidden','text/plain')
            try:
                u=urlsplit(self.path); p=u.path; q=parse_qs(u.query).get('q',[''])[0][:200]
                if p=='/':
                    catalog=lib.catalog(); matches=[x for x in catalog if q.casefold() in (x['name']+' '+x['description']).casefold()]
                    rows=''.join(f'<article class="entry"><div><h2><a href="/skill/{esc(x["name"])}">{esc(x["name"].replace("-"," ").title())}</a></h2><p>{esc(x["description"])}</p><span class="status">Review required · {len(x["findings"])} static flags</span></div><div><a class="button" href="/download/{esc(x["name"])}">Download ZIP</a></div></article>' for x in matches)
                    return self.reply(200,page('Capability library',f'<h1>Capability library</h1><p>One source for reusable AI instructions. Inspect identity, review findings and export a portable package.</p><div class="metrics"><div><strong>{len(catalog)}</strong>Capabilities</div><div><strong>{sum(len(x["findings"]) for x in catalog)}</strong>Static flags</div><div><strong>0</strong>Verified platform installations</div></div><div class="notice">Static inspection is not security approval. All skills require review.</div><form class="toolbar" method="get"><input type="search" name="q" aria-label="Search skills" value="{esc(q)}" placeholder="Search capabilities"><button>Search</button><a class="button" href="/new">Create draft</a></form><p class="muted">{len(matches)} results</p>{rows or "<p>No matching skills. Try another search.</p>"}'))
                if p=='/new': return self.reply(200,page('Create draft',f'<h1>Create a skill draft</h1><p>Drafts are stored locally. No installation or execution occurs.</p><form method="post" action="/new" class="editor"><input type="hidden" name="token" value="{token}"><label for="name">Skill name (lowercase, hyphenated)</label><input id="name" name="name" required maxlength="80" pattern="[a-z][a-z0-9-]*"><label for="description">Description and trigger</label><input id="description" name="description" required maxlength="500"><label for="body">Workflow instructions</label><textarea id="body" name="body" rows="12" required maxlength="50000"></textarea><p><button>Create draft</button></p></form>'))
                parts=p.split('/')
                if len(parts)==3 and parts[1] in ('skill','download','passport','context'):
                    action,name=parts[1:]; files,passport=lib.get(name)
                    if action=='download': return self.reply(200,package(files,name),'application/zip','skill.zip')
                    if action=='passport': return self.reply(200,bridge.canonical(passport),'application/json',name+'-passport.json')
                    if action=='context': return self.reply(200,files['SKILL.md'],'text/plain; charset=utf-8',name+'.md')
                    return self.reply(200,page(name,f'<a href="/">Capability library</a><h1>{esc(name.replace("-"," ").title())}</h1><p>{esc(passport["description"])}</p><div class="notice">Review required. Behavioral effectiveness and installation not tested.</div><div class="toolbar"><a class="button" href="/download/{name}">Download ZIP</a><a class="button" href="/passport/{name}">Download passport</a><a class="button" href="/context/{name}">Download instructions</a></div><h2>Capability passport</h2><pre>{esc(json.dumps(passport,indent=2))}</pre><h2>Skill instructions (untrusted text)</h2><pre>{esc(files["SKILL.md"].decode())}</pre>'))
                return self.reply(404,page('Not found','<h1>Not found</h1><a href="/">Return to library</a>'))
            except (ValueError,KeyError,OSError,UnicodeError): return self.reply(400,page('Rejected','<h1>Request rejected</h1><p>Check the skill name, content or local library.</p><a href="/">Return to library</a>'))
        def do_POST(self):
            if not self.host_ok() or self.path!='/new': return self.reply(403,b'Forbidden','text/plain')
            origin=self.headers.get('Origin'); expected='http://'+self.headers['Host']
            if origin != expected: return self.reply(403,b'Forbidden','text/plain')
            try:
                length=int(self.headers.get('Content-Length','-1'))
                if not 0<=length<=200000 or self.headers.get('Content-Type')!='application/x-www-form-urlencoded': raise ValueError()
                data=parse_qs(self.rfile.read(length).decode(),strict_parsing=True,max_num_fields=4)
                if set(data)!={'token','name','description','body'} or any(len(v)!=1 for v in data.values()) or not secrets.compare_digest(data['token'][0],token): return self.reply(403,b'Forbidden','text/plain')
                p=lib.create(*(data[k][0] for k in ('name','description','body')))
                return self.reply(201,page('Draft created',f'<h1>Draft created</h1><p>Stored locally and awaiting review.</p><a class="button" href="/skill/{esc(p["name"])}">Inspect draft</a>'))
            except (ValueError,OSError,UnicodeError): return self.reply(400,page('Draft rejected','<h1>Draft rejected</h1><p>Use a unique name, valid text and no embedded credentials.</p><a href="/new">Try again</a>'))
    return studio_lab.extend(Handler, token, page, esc)

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--port',type=int,default=8765); p.add_argument('--drafts',type=Path,default=ROOT/'studio-drafts'); a=p.parse_args()
    lib=Library(ROOT/'skills',a.drafts); server=ThreadingHTTPServer(('127.0.0.1',a.port),handler(lib,secrets.token_urlsafe(32)))
    print(f'GAIA Studio: http://127.0.0.1:{server.server_port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__=='__main__': main()
