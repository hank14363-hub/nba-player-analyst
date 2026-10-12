#!/usr/bin/env python3
"""Check book hashes, identity, article evidence, local anchors and embedded values."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from book_contract import dictionary, load_context, validate_content
from common import DataError, write_json


class Inspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.anchors: list[str] = []
        self.remote_assets: list[str] = []
        self.metric_values: list[tuple[str, str]] = []
        self.unsafe_links: list[str] = []
        self.event_attributes: list[str] = []
        self.svg_count = 0
        self.in_script = False
        self.scripts: list[str] = []
        self.csp = ''

    def handle_starttag(self, tag: str, attrs: list[tuple[str,str | None]]) -> None:
        a = dict(attrs)
        if a.get('id'):
            self.ids.append(a['id'])
        if tag == 'svg':
            self.svg_count += 1
        if tag == 'meta' and a.get('http-equiv','').lower() == 'content-security-policy':
            self.csp = a.get('content','')
        for key in a:
            if key.startswith('on'):
                self.event_attributes.append(key)
        href = a.get('href','') or ''
        if href.startswith('#'):
            self.anchors.append(href[1:])
        elif tag == 'a' and href and urlsplit(href).scheme.lower() not in {'http','https'}:
            self.unsafe_links.append(href)
        if tag in {'iframe','object','embed'}:
            self.remote_assets.append(tag)
        if tag in {'script','img','link','video','audio','source'}:
            src = a.get('src') or (a.get('href') if tag == 'link' else None)
            if src and not (tag == 'img' and src.startswith('data:')):
                self.remote_assets.append(src)
        if 'data-metric-id' in a:
            self.metric_values.append((a['data-metric-id'], a.get('data-value','')))
        if tag == 'script':
            self.in_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag == 'script':
            self.in_script = False

    def handle_data(self, data: str) -> None:
        if self.in_script:
            self.scripts.append(data)


def inspect_html(text: str, analysis: dict) -> dict:
    parser = Inspector()
    parser.feed(text)
    errors = []
    ids = set(parser.ids)
    if len(ids) != len(parser.ids):
        errors.append('Duplicate HTML IDs')
    broken = sorted(set(parser.anchors) - ids)
    if broken:
        errors.append('Broken fragment links: ' + ', '.join(broken))
    for n in range(1,10):
        if f'module-{n:02d}' not in ids:
            errors.append(f'Missing module-{n:02d}')
    if parser.remote_assets:
        errors.append('External resource dependency: ' + ', '.join(parser.remote_assets))
    if parser.unsafe_links or parser.event_attributes:
        errors.append('Unsafe link protocol or inline event handler')
    if '{{' in text or 'NOT_FINAL' in text:
        errors.append('Unfilled placeholders in HTML')
    if re.search(r'@import|url\(\s*[\'"]?https?://', text, flags=re.I):
        errors.append('External CSS/font dependency')
    if len(parser.scripts) != 1 or "default-src 'none'" not in parser.csp:
        errors.append('Expected one local script and a restrictive content security policy')
    if analysis['data_kind'] == 'synthetic' and 'synthetic-banner' not in text:
        errors.append('Synthetic disclosure missing')
    metrics = {m['metric_id']:m for m in analysis['metrics']}
    for mid, raw in parser.metric_values:
        m = metrics.get(mid)
        try:
            n = float(raw)
            if not m or m['status'] != 'ok' or not math.isfinite(n) or not math.isclose(n,m['value'],abs_tol=1e-10,rel_tol=1e-10):
                errors.append('Embedded metric mismatch: ' + mid)
        except (ValueError,TypeError):
            errors.append('Invalid embedded metric: ' + mid)
    return {'errors':errors,'section_count':sum(f'module-{n:02d}' in ids for n in range(1,10)),
            'anchor_count':len(parser.anchors),'svg_count':parser.svg_count,'embedded_metric_instances':len(parser.metric_values)}


def check(run_dir: Path, min_chars: int = 1200) -> dict:
    analysis, claims, report, report_check = load_context(run_dir,min_chars)
    errors = validate_content(dictionary(run_dir/'book_content.json'),analysis,claims)
    manifest = dictionary(run_dir/'book_manifest.json')
    if manifest.get('data_kind') != analysis['data_kind']:
        errors.append('Manifest data_kind differs from analysis')
    hashes = manifest.get('sha256',{})
    required = {'data_bundle.json','analysis.json','sources.json','report.md','claims.json','book_content.json','research_book.html','summary.md'}
    if not isinstance(hashes,dict) or not required.issubset(hashes):
        errors.append('Manifest is missing required file hashes')
        hashes = hashes if isinstance(hashes,dict) else {}
    for name, expected in hashes.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or (run_dir/relative).resolve().parent == run_dir.resolve().parent:
            errors.append('Unsafe manifest file path')
            continue
        path = run_dir/relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append('File changed after rendering: ' + name)
    inspection = inspect_html((run_dir/'research_book.html').read_text(encoding='utf-8'),analysis)
    errors.extend(inspection.pop('errors'))
    return {'status':'pass' if not errors else 'fail','recomputed_metrics':True,'report_validation':report_check,
            **inspection,'errors':errors,'warnings':['Passing checks verify reproducibility, IDs, registered numbers, and static output integrity, NOT semantic truth, strategy validity, or visual layout. Review desktop/mobile/print separately.']}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--min-chars',type=int,default=1200)
    args=p.parse_args()
    try:
        if args.min_chars < 0:
            raise DataError('--min-chars must be nonnegative')
        result=check(args.run_dir,args.min_chars)
        write_json(args.run_dir/'book_validation.json',result)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result['status']=='pass' else 1
    except (DataError,OSError,UnicodeError,KeyError,TypeError,ValueError) as exc:
        print('ERROR: ' + str(exc),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
