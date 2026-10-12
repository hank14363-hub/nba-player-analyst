#!/usr/bin/env python3
"""Optional A4 export using Playwright; does not install anything or access websites."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
from common import DataError, read_json
from validate_book import check


def export(run_dir: Path, destination: Path, executable: str | None = None, force: bool = False, min_chars: int = 1200) -> None:
    if destination.exists() and not force:
        raise DataError('PDF already exists; choose a new --out path or explicitly use --force')
    if destination.suffix.lower() != '.pdf':
        raise DataError('--out must end in .pdf')
    result = check(run_dir,min_chars)
    if result['status'] != 'pass':
        raise DataError('Book checks failed: ' + '; '.join(result['errors']))
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DataError('Optional dependency missing. Install requirements-print.txt and a Playwright Chromium browser, or print the HTML manually using your browser.') from exc
    kind = read_json(run_dir/'analysis.json')['data_kind']
    label = 'SYNTHETIC TEST DATA / NOT REAL NBA ANALYSIS' if kind == 'synthetic' else 'NBA PLAYER RESEARCH / CHECK SOURCES AND LIMITATIONS'
    destination.parent.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, **({'executable_path':executable} if executable else {}))
        try:
            context = browser.new_context(viewport={'width':1440,'height':1024})
            context.route('**/*',lambda route:route.abort())
            page = context.new_page()
            # Self-contained content: no local file navigation or external resources needed.
            page.set_content((run_dir/'research_book.html').read_text(encoding='utf-8'),wait_until='load')
            page.evaluate('document.fonts.ready')
            page.emulate_media(media='print')
            page.pdf(path=str(destination.resolve()),format='A4',prefer_css_page_size=True,print_background=True,
                     display_header_footer=True,header_template='<div></div>',
                     footer_template='<div style="font-family:Arial;font-size:8px;color:#666;width:100%;padding:0 17mm;display:flex;justify-content:space-between"><span>' + label + '</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
        finally:
            browser.close()


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',required=True,type=Path)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--browser-path',help='Optional explicit path to an installed Chromium/Chrome executable')
    parser.add_argument('--force',action='store_true')
    parser.add_argument('--min-chars',type=int,default=1200)
    args=parser.parse_args()
    try:
        if args.min_chars < 0:
            raise DataError('--min-chars must be nonnegative')
        destination=args.out or args.run_dir/'research_book.pdf'
        export(args.run_dir,destination,args.browser_path,args.force,args.min_chars)
        print('PDF ready: ' + str(destination.resolve()))
        print('Inspect rendered pages before sharing. Browser/font differences can affect pagination.')
        return 0
    except Exception as exc:
        print('ERROR: ' + str(exc),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
