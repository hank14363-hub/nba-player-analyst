#!/usr/bin/env python3
"""Advisory Chinese copy review. No automatic edits, truth scoring, or semantic guarantees."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

from common import SKILL_ROOT, read_json, DataError

def load_rules(path=None):
    rules=read_json(path or SKILL_ROOT/'references/language_rules.json')
    if rules.get('schema_version')!='0.1.0':raise DataError('Unknown language rule schema')
    if not isinstance(rules.get('rule_version'),str) or not rules['rule_version']:raise DataError('Missing language rule version')
    if not isinstance(rules.get('jargon'),dict) or not all(isinstance(k,str) and isinstance(v,str) and k and v for k,v in rules['jargon'].items()):raise DataError('Invalid jargon rules')
    if not isinstance(rules.get('terms'),dict) or not all(isinstance(k,str) and k and isinstance(v,list) and v and all(isinstance(h,str) and h for h in v) for k,v in rules['terms'].items()):raise DataError('Invalid term rules')
    if not isinstance(rules.get('strong_labels'),list) or not rules['strong_labels'] or not all(isinstance(v,str) and v for v in rules['strong_labels']):raise DataError('Invalid strong-label rules')
    return rules

RULES=load_rules()
JARGON=RULES['jargon']
TERMS=RULES['terms']
STRONG_LABELS='|'.join(re.escape(v) for v in RULES['strong_labels'])
LIMITATION = '仅为规则提示，不证明表达已足够通俗或结论真实；不自动改写，不修改数据。'


def readable_lines(text: str):
    """Ignore code blocks and reference definitions; retain original line numbers."""
    fenced = False
    for number,line in enumerate(text.splitlines(),1):
        if line.lstrip().startswith('```'):
            fenced = not fenced
            continue
        if fenced or re.match(r'^\s*\[[^\]]+\]:',line):
            continue
        # Remove citation IDs, but not normal prose or measurements.
        yield number,re.sub(r'\[(?:P_|T_|TR_|EXT_|C\d)[^\]]*\]','',line)


def review_text(text: str, location: str='text') -> list[dict]:
    issues=[]
    lines=list(readable_lines(text))
    def add(rule,line,excerpt,suggestion):
        issues.append({'rule':rule,'location':location,'line':line,
                       'excerpt':excerpt[:150],'suggestion':suggestion})
    for number,line in lines:
        for word,tip in JARGON.items():
            if word in line:add('abstract_phrase',number,word,tip)
        for sentence in re.split(r'(?<=[。！？!?])',line):
            if len(re.sub(r'\s','',sentence))>110:
                add('long_sentence',number,sentence,'检查是否能拆成两句；不可为缩短而删除条件、来源或统计口径。')
        for match in re.finditer(STRONG_LABELS,line):
            prefix=line[max(0,match.start()-10):match.start()]
            if not re.search(r'不|没有|避免|禁止|别',prefix):
                add('strong_label',number,match.group(),'检查是否有足够比较证据，必要时改写为具体任务表现。')
    joined='\n'.join(line for _,line in lines)
    for term,hints in TERMS.items():
        m=re.search(r'(?<![A-Za-z])'+re.escape(term)+r'%?(?![A-Za-z])',joined)
        if m and not any(h in joined[max(0,m.start()-70):m.end()+70] for h in hints):
            number=next((n for n,l in lines if re.search(r'(?<![A-Za-z])'+re.escape(term)+r'(?![A-Za-z])',l)),1)
            add('unexplained_abbreviation',number,term,'首次出现时增加简短中文解释，别只展开英文全称。')
    return issues


def prose_fields(obj, prefix=''):
    """Review editorial prose only, never IDs, numeric facts, provenance, or identity."""
    skip={'schema_version','status','data_kind','identity','portrait','commentary_research','claim_ids','challenge_ids',
          'executive_claim_ids','summary_claim_ids','dimension','id','metric_ids','source_ids'}
    if isinstance(obj,dict):
        for key,value in obj.items():
            if key not in skip:yield from prose_fields(value,prefix+'.'+key if prefix else key)
    elif isinstance(obj,list):
        for index,value in enumerate(obj):yield from prose_fields(value,f'{prefix}[{index}]')
    elif isinstance(obj,str):yield prefix,obj


def review_run(run_dir:Path) -> dict:
    run_dir=Path(run_dir)
    report=(run_dir/'report.md').read_text(encoding='utf-8')
    issues=review_text(report,'report.md');checked=['report.md']
    for name in ('book_content.json','poster_content.json'):
        path=run_dir/name
        if not path.exists():continue
        obj=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(obj,dict):raise ValueError(name+' must contain an object')
        for location,text in prose_fields(obj):issues.extend(review_text(text,name+':'+location))
        checked.append(name)
    return {'review_version':RULES['rule_version'],'status':'review_suggested' if issues else 'no_heuristic_warnings',
            'checked_files':checked,'issue_count':len(issues),'issues':issues,
            'manual_review_required':True,'automatic_edits':False,'limitation':LIMITATION}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',required=True,type=Path)
    args=parser.parse_args()
    try:
        result=review_run(args.run_dir)
        (args.run_dir/'language_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0  # Warnings are editorial advice, not a blocking factual validator.
    except (OSError,ValueError,UnicodeError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
