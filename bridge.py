"""Offline skill distribution. No activation, network, or trust grants."""
import argparse, hashlib, json, re, stat, zipfile
from pathlib import Path

NAME = re.compile(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z')
PART = re.compile(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*\Z')
MAX_FILE = 65536
MAX_TOTAL = 1048576
MAX_FILES = 64
RESERVED = {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}

def digest(b): return hashlib.sha256(b).hexdigest()
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def safe_part(p):
    return bool(PART.fullmatch(p)) and not p.endswith('.') and p.split('.')[0].upper() not in RESERVED

def inspect(folder):
    folder=Path(folder)
    if folder.is_symlink() or not folder.is_dir() or not NAME.fullmatch(folder.name): raise ValueError('invalid skill folder')
    files={}; seen=set(); total=0; findings=[]
    for p in sorted(folder.rglob('*')):
        rel=p.relative_to(folder); key=rel.as_posix(); folded=key.casefold()
        if not all(safe_part(x) for x in rel.parts) or folded in seen: raise ValueError('unsafe or colliding path')
        seen.add(folded)
        if p.is_symlink(): raise ValueError('symlink refused')
        if p.is_dir(): continue
        if not stat.S_ISREG(p.stat().st_mode): raise ValueError('nonregular file')
        if len(files)>=MAX_FILES: raise ValueError('file count exceeded')
        with p.open('rb') as f: raw=f.read(MAX_FILE+1)
        total+=len(raw)
        if len(raw)>MAX_FILE or total>MAX_TOTAL: raise ValueError('size exceeded')
        if p.suffix.lower() not in {'.md','.txt','.yaml','.yml','.json'}: raise ValueError('unsupported executable or binary resource')
        text=raw.decode('utf-8');
        if '\x00' in text: raise ValueError('binary content')
        if re.search(r'(?:sk-proj-|sk-ant-|AIza)[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----',text): raise ValueError('potential embedded secret')
        if re.search(r'ignore (?:all |previous |prior )?(?:rules|instructions)|(?:curl|wget)\s+https?://|\b(?:eval|exec)\s*\(',text,re.I): findings.append({'file':key,'rule':'instruction_or_execution_pattern'})
        files[key]=raw
    if 'SKILL.md' not in files: raise ValueError('missing entrypoint')
    lines=files['SKILL.md'].decode('utf-8').splitlines()
    if not lines or lines[0]!='---' or '---' not in lines[1:]: raise ValueError('invalid frontmatter')
    end=lines.index('---',1); fields={}
    for line in lines[1:end]:
        k,sep,v=line.partition(': ')
        if not sep or k not in {'name','description'} or k in fields or not v.strip(): raise ValueError('unsupported metadata')
        fields[k]=v
    if set(fields)!={'name','description'} or fields['name']!=folder.name: raise ValueError('metadata mismatch')
    manifest={k:digest(v) for k,v in files.items()}
    passport={'schema':'gaia-capability-passport-v1','name':folder.name,'description':fields['description'],'files':manifest,'content_sha256':digest(canonical(manifest)), 'static_review':'REVIEW_REQUIRED','findings':findings,'publisher_authenticated':False,'behavioral_evaluation':'NOT_TESTED','platform_installation':'NOT_TESTED','execution_authorized':False,'signed':False}
    return files,passport

def archive(path,files):
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,raw in sorted(files.items()):
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=0o100644<<16
            z.writestr(info,raw)

def export(root,out):
    root=Path(root); out=Path(out)
    if not root.is_dir() or root.is_symlink(): raise ValueError('invalid root')
    if out.resolve().is_relative_to(root.resolve()): raise ValueError('output inside source')
    items=[inspect(p) for p in sorted(root.iterdir()) if p.is_dir() or p.is_symlink()]
    if not items: raise ValueError('empty library')
    out.mkdir(parents=True,exist_ok=False)
    catalog=[]
    for files,p in items:
        n=p['name']; target=out/n; target.mkdir()
        archive(target/'skill.zip',{n+'/'+k:v for k,v in files.items()})
        for base in (out/'codex'/'.agents'/'skills',out/'claude-code'/'.claude'/'skills'):
            for k,v in files.items():
                dest=base/n/k; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(v)
        (target/'context.md').write_bytes(files['SKILL.md'])
        p['archive_sha256']=digest((target/'skill.zip').read_bytes())
        p['export_formats']=['portable_zip','codex_directory','claude_code_directory','generic_context']
        (target/'passport.json').write_bytes(canonical(p)+b'\n'); catalog.append(p)
    (out/'catalog.json').write_bytes(canonical(catalog)+b'\n')
    return catalog

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--skills',default='skills'); p.add_argument('--out',required=True); a=p.parse_args()
    try: print(json.dumps({'exported':len(export(a.skills,a.out)), 'installation_verified':False,'execution_authorized':False},indent=2))
    except (ValueError,OSError,UnicodeError) as e: p.exit(1,'Export rejected: '+type(e).__name__+'\n')
if __name__=='__main__': main()
