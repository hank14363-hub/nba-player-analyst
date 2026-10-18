#!/usr/bin/env python3
"""Validate poster inputs, recomputed metrics, render parity and local reference links."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import math
import sys
from pathlib import Path
from common import DataError, digest, write_json
from book_contract import dictionary
from poster_contract import load_poster, POSTER_VERSION
from render_player_poster import Poster, portrait_data
from team_themes import select_theme
from validate_book import Inspector


def check(run_dir: Path,min_chars: int=1200) -> dict:
    a,claims,book,content,report_check=load_poster(run_dir,min_chars)
    manifest=dictionary(run_dir/'poster_manifest.json');errors=[]
    if manifest.get('data_kind')!=a['data_kind'] or manifest.get('poster_version')!=POSTER_VERSION:
        errors.append('Poster manifest identity/version mismatch')
    theme=manifest.get('theme',{})
    why=theme.get('selection_reason','')
    name='auto' if why in {'player_sample_or_reported_team_label','unresolved_team_neutral'} else theme.get('key','')
    custom={k:theme.get(k) for k in ('primary','accent')} if why=='explicit_custom_colors' else None
    checked=select_theme(a,name,custom)
    if checked!=theme:errors.append('Theme differs from validated palette or contains untrusted CSS values')
    poster=Poster(a,claims,book,content,checked,portrait_data(run_dir,content['portrait']),release_version=manifest.get('renderer_version'))
    html=(run_dir/'player_poster.html').read_text(encoding='utf-8')
    if html!=poster.render():errors.append('HTML differs from deterministic rendering of the current inputs')
    metrics=dictionary(run_dir/'poster_metrics.json')
    expected={'schema_version':POSTER_VERSION,'data_kind':a['data_kind'],'derived_metrics':poster.chart.derived,
              'charts':{k:{f:v for f,v in c.items() if f!='svg'} for k,c in poster.charts.items()}}
    if digest(metrics)!=digest(expected):errors.append('Poster metrics differ from deterministic recomputation')
    files=['data_bundle.json','analysis.json','sources.json','report.md','claims.json','book_content.json','poster_content.json','player_poster.html','poster_metrics.json']
    for key,c in poster.charts.items():
        if c['svg']:
            n='poster_charts/'+key+'.svg';files.append(n)
            if not (run_dir/n).is_file() or (run_dir/n).read_text(encoding='utf-8')!=c['svg']:errors.append('Chart changed: '+n)
    if content['portrait']:files.append(content['portrait']['path'])
    hashes=manifest.get('sha256',{})
    if not isinstance(hashes,dict) or set(hashes)!=set(files):
        errors.append('Manifest must hash exactly the required input and generated files')
        hashes=hashes if isinstance(hashes,dict) else {}
    for n,h in hashes.items():
        path=(run_dir/n).resolve()
        if Path(n).is_absolute() or '..' in Path(n).parts or not path.is_relative_to(run_dir.resolve()):
            errors.append('Unsafe manifest path');continue
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=h:errors.append('File changed after rendering: '+n)
    p=Inspector();p.feed(html)
    if len(p.ids)!=len(set(p.ids)):errors.append('Duplicate HTML IDs')
    if set(p.anchors)-set(p.ids):errors.append('Broken local evidence links')
    if p.remote_assets or p.unsafe_links or p.event_attributes:errors.append('Unsafe link/event or external resource')
    for mid,val in p.metric_values:
        m=poster.metrics.get(mid)
        try:
            ok=m and m['status']=='ok' and math.isclose(float(val),m['value'],rel_tol=1e-10,abs_tol=1e-10)
        except (ValueError,TypeError):ok=False
        if not ok:errors.append('Embedded value mismatch: '+mid)
    for script in p.scripts:
        h=base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        if "'sha256-"+h+"'" not in p.csp:errors.append('Script does not match CSP hash')
    if a['data_kind']=='synthetic' and 'SYNTHETIC TEST DATA' not in html:errors.append('Synthetic disclosure missing')
    return {'status':'pass' if not errors else 'fail','poster_version':POSTER_VERSION,'charts_rendered':sum(c['status']=='ok' for c in poster.charts.values()),
            'charts_missing':sum(c['status']=='missing' for c in poster.charts.values()),'theme':theme.get('key'),
            'anchor_count':len(p.anchors),'embedded_metric_instances':len(p.metric_values),'recomputed_metrics':True,
            'render_parity':html==poster.render(),'report_validation':report_check,'errors':errors,
            'warnings':['Structural and numeric reproducibility checks do not prove player evaluation, chart interpretation or tactical fit. Visual and semantic review remain required.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-dir',type=Path,required=True);p.add_argument('--min-chars',type=int,default=1200)
    args=p.parse_args()
    try:
        if args.min_chars<0:raise DataError('--min-chars must be nonnegative')
        r=check(args.run_dir,args.min_chars);write_json(args.run_dir/'poster_validation.json',r)
        print(json.dumps(r,ensure_ascii=False,indent=2));return 0 if r['status']=='pass' else 1
    except (DataError,OSError,KeyError,TypeError,ValueError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
