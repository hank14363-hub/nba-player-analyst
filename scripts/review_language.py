#!/usr/bin/env python3
"""Advisory Chinese copy review. No automatic edits, truth scoring, or semantic guarantees."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

JARGON = {
    '机会转化结果': '说清是得分效率，还是某种出手的成功率。',
    '终结负荷': '可写成承担多少得分或进攻结束任务，保留原来口径。',
    '主控结论': '说明能否承担主要组织任务，不用抽象名词代替判断。',
    '角色迁移': '说清换了球队或分工后，哪些表现还需要验证。',
    '分担创造': '说明是分担持球组织，还是接球后继续处理。',
    '无球试验': '说明具体尝试什么无球分工。',
    '共同在场阵容': '可写成场上的整套阵容。',
    '因果贡献': '说明这些变化有多少能归因于球员本人。',
    '多维度赋能': '写出实际帮助了哪种进攻或防守任务。',
    '证据边界': '明确说还缺什么资料、哪些判断暂时不能下。',
}
TERMS = {
    'TS': ('真实命中率', '两分、三分和罚球'),
    'rTS': ('相对真实命中率', '百分点'),
    'eFG': ('有效命中率',),
    'USG': ('使用率',),
    'ORTG': ('进攻效率', '每百回合得分', '每100回合得分'),
    'DRTG': ('防守效率', '每百回合失分', '每100回合失分'),
}
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
        for match in re.finditer(r'完美适配|全面碾压|毫无短板|无敌|联盟顶级',line):
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
    skip={'schema_version','status','data_kind','identity','portrait','claim_ids','challenge_ids',
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
    return {'review_version':'0.3.1','status':'review_suggested' if issues else 'no_heuristic_warnings',
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
