"""Replay a verified completed case into a new directory with V1.00 quantiles."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

from common import DataError, digest, read_json, write_json, write_metrics_csv, now_iso
from calculate_metrics import analyze
from book_contract import load_context
from retained_raw import verify_retained


def upgrade(source, out):
    source=Path(source).resolve();out=Path(out).resolve()
    if out==source or out.is_relative_to(source) or source.is_relative_to(out):
        raise DataError('Source and output must be separate, non-nested directories')
    if out.exists():raise DataError('Refusing to overwrite an existing output directory')
    # Validate original evidence, claims and saved calculations before copying anything.
    previous,_,_,_=load_context(source)
    if not previous['request'].get('advanced_percentiles'):
        raise DataError('This migration requires a previously completed advanced-percentile case')
    bundle=read_json(source/'data_bundle.json')
    verify_retained(bundle,source)
    request=deepcopy(previous['request']);request['radar_protocol']='1.0.0'
    fresh=analyze(bundle,request)
    by={m['metric_id']:m for m in fresh['metrics']}
    changed=[m['metric_id'] for m in previous['metrics']
             if m['metric_id'] not in by or digest(m)!=digest(by[m['metric_id']])]
    if changed:raise DataError('Upgrade would change existing registered metrics: '+', '.join(changed))
    shutil.copytree(source,out,ignore=shutil.ignore_patterns('__pycache__','.git'))
    write_json(out/'analysis.json',fresh)
    write_json(out/'advanced_percentiles.json',fresh['percentile_context'])
    write_metrics_csv(out/'metrics.csv',fresh['metrics'])
    content=read_json(out/'book_content.json');content['percentile_presentation']='radar'
    write_json(out/'book_content.json',content)
    from render_research_book import build
    from validate_book import check
    from render_player_poster import build as poster
    build(out,force=True)
    result=check(out,strict_editorial=True)
    if result['status']!='pass':raise DataError('Upgraded book validation failed: '+str(result))
    if (out/'poster_content.json').exists():poster(out,force=True)
    audit=dict(protocol='1.0.0',upgraded_at=now_iso(),source=str(source),
        original_bundle_sha256=__import__('hashlib').sha256((source/'data_bundle.json').read_bytes()).hexdigest(),
        previous_metric_count=len(previous['metrics']),new_metric_count=len(fresh['metrics']),
        unchanged_existing_metrics=True,mode='retained evidence replay; no network or new collection',
        book_validation=result['status'])
    write_json(out/'radar_upgrade.json',audit)
    return audit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    import json
    print(json.dumps(upgrade(args.run_dir,args.out),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
