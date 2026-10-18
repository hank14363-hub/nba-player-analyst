"""Attach a historical population from an already retained CSV; offline only."""
import argparse
from copy import deepcopy
from pathlib import Path
import sys

from advanced_percentiles import attach_history, verify_files
from common import DataError, read_json, write_json
from retained_raw import copy_retained, verify_retained


def prepare(source, destination):
    if destination.exists() and any(destination.iterdir()): raise DataError('Choose a new empty destination')
    bundle=read_json(source/'data_bundle.json')
    verify_retained(bundle,source)
    result=deepcopy(bundle)
    if bundle.get('historical_epm_import'): attach_history(result,source)
    verify_files(result,source)
    destination.mkdir(parents=True,exist_ok=True)
    copy_retained(result,source,destination)
    write_json(destination/'data_bundle.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    args=p.parse_args()
    try:
        b=prepare(args.run_dir,args.out)
        print('Prepared offline bundle: '+str(args.out.resolve()))
        print('Historical population: '+str(len(b.get('advanced_percentile_populations',{}).get('historical_epm',{}).get('raw_rows',[]))))
        return 0
    except (DataError,OSError,ValueError,KeyError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr); return 2


if __name__=='__main__': raise SystemExit(main())
