"""Check release labels separately from data-schema compatibility."""
import re
from common import SKILL_ROOT, RELEASE_VERSION, DATA_SCHEMA_VERSION, read_json

def check(root=SKILL_ROOT):
    info=read_json(root/'PACKAGE_INFO.json');release=info['release_version'];errors=[]
    for name in ('README.md','SKILL.md'):
        heading=next((line for line in (root/name).read_text(encoding='utf-8').splitlines() if line.startswith('# ')), '')
        if not re.search(r'\bv'+re.escape(release)+r'\b',heading):errors.append(name+' release heading mismatch')
    if info['data_schema']!=DATA_SCHEMA_VERSION:errors.append('Package data schema mismatch')
    return dict(status='fail' if errors else 'pass',release_version=release,data_schema=DATA_SCHEMA_VERSION,errors=errors)

if __name__=='__main__':
    import json
    result=check();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(result['status']!='pass')
