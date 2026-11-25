"""Metadata discovery only. Never imports or executes skill content."""
import argparse, hashlib, json, re
from pathlib import Path

NAME = re.compile(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z')
CAPS = {
'universal-builder-router':'orchestration','skill-factory':'skill-creation','evaluation-verification-lab':'verification','evidence-ledger':'provenance','failure-recovery-engineer':'recovery','benchmark-laboratory':'benchmarking','innovation-validation-lab':'innovation','software-architecture-specifier':'architecture','enterprise-database-engineer':'database','connector-integration-planner':'integration','deployment-release-manager':'deployment','security-threat-modeler':'security','cost-performance-engineer':'optimization','workflow-automation-architect':'automation','scientific-experiment-designer':'experiment-design','data-analysis-pipeline':'data-analysis','ml-model-engineer':'machine-learning','knowledge-system-architect':'knowledge-retrieval','business-operations-planner':'operations','product-design-system-planner':'product-design','artifact-production-studio':'artifacts','technical-communication-studio':'documentation'}

def inventory(root):
    root=Path(root)
    if not root.is_dir(): raise ValueError('skill directory missing')
    records=[]
    for folder in sorted(root.iterdir()):
        if not folder.is_dir(): continue
        path=folder/'SKILL.md'
        if folder.is_symlink() or path.is_symlink(): raise ValueError('symlink refused')
        if not path.is_file(): continue
        with path.open('rb') as f: raw=f.read(65537)
        if len(raw)>65536: raise ValueError('entrypoint too large')
        # Parse only the deliberately restricted single-line metadata format.
        # Keep original bytes for hashing, including Windows CRLF newlines.
        lines=raw.decode('utf-8').replace('\r\n','\n').split('\n')
        if lines[0]!='---' or '---' not in lines[1:]: raise ValueError('invalid frontmatter')
        end=lines.index('---',1)
        fields=lines[1:end]
        names=[line[6:] for line in fields if line.startswith('name: ')]
        desc=[line[13:] for line in fields if line.startswith('description: ')]
        if (len(fields)!=2 or names!=[folder.name] or not NAME.fullmatch(folder.name)
                or len(desc)!=1 or not desc[0].strip() or any('\r' in line for line in fields)):
            raise ValueError('unsupported metadata format')
        records.append(dict(name=folder.name,description=desc[0],capability=CAPS.get(folder.name),sha256=hashlib.sha256(raw).hexdigest(),runtime_status='UNKNOWN'))
    return records

def route(records, requested):
    if not isinstance(requested,list) or any(not isinstance(c,str) or not c for c in requested): raise ValueError('capabilities must be a list of nonempty strings')
    return [{'capability':c,'status':'METADATA_ONLY' if any(r['capability']==c for r in records) else 'MISSING','specialists':[r['name'] for r in records if r['capability']==c],'execution_authorized':False} for c in dict.fromkeys(requested)]

def main():
    p=argparse.ArgumentParser(); p.add_argument('--skills',default=str(Path(__file__).parent/'skills')); p.add_argument('capability',nargs='*'); a=p.parse_args()
    records=inventory(a.skills); print(json.dumps(route(records,a.capability) if a.capability else records,indent=2))
if __name__=='__main__': main()
