#!/usr/bin/env python3
"""Export standalone shot SVGs from an evidence run; no finished article is required."""
import argparse
import json
import sys
from pathlib import Path
from calculate_metrics import analyze
from common import DataError, digest, read_json, write_json
from shot_charts import shot_visuals
from team_themes import select_theme


def render(run_dir, out, theme='auto'):
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise DataError('Figure output must be new/empty.')
    saved=read_json(run_dir/'analysis.json')
    fresh=analyze(read_json(run_dir/'data_bundle.json'),saved['request'])
    for field in ('data_kind','player','sample','target_team','metrics','shot_context'):
        if digest(fresh.get(field)) != digest(saved.get(field)):
            raise DataError('Saved evidence differs from recomputation: '+field)
    if not fresh.get('shot_context'):
        raise DataError('Complete matching shot events unavailable; no substitute location figure generated.')
    entries=shot_visuals(fresh,select_theme(fresh,theme))
    out.mkdir(parents=True,exist_ok=True)
    for key,entry in entries.items():
        (out/(key+'.svg')).write_text(entry['svg'],encoding='utf-8')
    manifest=dict(status='rendered',sample=fresh['sample'],player=fresh['player'],data_kind=fresh['data_kind'],
        coverage=fresh['shot_context']['counts'],anomalies=fresh['shot_context']['anomalies'],
        sources={sid:fresh['sources'][sid] for sid in ('P_SHOT','P_BASE')},
        figures={key:{k:v for k,v in e.items() if k!='svg'} for key,e in entries.items()})
    write_json(out/'shot_chart_manifest.json',manifest)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--theme',default='auto')
    args=p.parse_args()
    try:
        result=render(args.run_dir,args.out,args.theme)
        print(json.dumps(dict(status=result['status'],out=str(args.out.resolve()),coverage=result['coverage']),ensure_ascii=False,indent=2))
        return 0
    except (DataError,OSError,ValueError,KeyError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
