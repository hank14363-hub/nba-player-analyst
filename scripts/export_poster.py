#!/usr/bin/env python3
"""Optional browser PNG export: complete poster and a self-contained cover preview."""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path
from common import DataError,write_json
from validate_poster import check


def export(run_dir:Path,destination:Path,width:int=1080,browser_path:str|None=None,force:bool=False,min_chars:int=1200):
    if width<360 or width>2160:raise DataError('Width must be between 360 and 2160 CSS pixels')
    if destination.suffix.lower()!='.png':raise DataError('--out must end in .png')
    cover=destination.with_name(destination.stem+'-cover.png')
    qa=destination.with_name(destination.stem+'-export.json')
    if not force and any(p.exists() for p in (destination,cover,qa)):raise DataError('Output exists; use a new path or --force')
    result=check(run_dir,min_chars)
    if result['status']!='pass':raise DataError('Poster validation failed: '+'; '.join(result['errors']))
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DataError('Install optional requirements-print.txt plus a Playwright Chromium browser, or screenshot the HTML manually') from exc
    destination.parent.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,**({'executable_path':browser_path} if browser_path else {}))
        try:
            context=browser.new_context(viewport={'width':width,'height':900},device_scale_factor=1)
            requests=[];errors=[]
            context.route('**/*',lambda route:route.abort())
            page=context.new_page();page.on('request',lambda r: requests.append(r.url));page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_content((run_dir/'player_poster.html').read_text(encoding='utf-8'),wait_until='load')
            page.evaluate('document.fonts.ready')
            if not page.evaluate('Array.from(document.images).every(img => img.complete && img.naturalWidth > 0)'):
                raise DataError('Portrait image could not be decoded by the browser')
            overflow=page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
            if overflow or errors:raise DataError('Browser export failed layout/script checks: '+str(errors))
            page.locator('#player-poster').screenshot(path=str(destination.resolve()))
            bounds=page.locator('.verdict').bounding_box();poster=page.locator('#player-poster').bounding_box()
            height=bounds['y']+bounds['height']-poster['y']
            page.set_viewport_size({'width':width,'height':max(900,math.ceil(height))})
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(cover.resolve()),clip={'x':poster['x'],'y':poster['y'],'width':poster['width'],'height':height})
            summary={'status':'exported','width':width,'poster_height':round(poster['height']),
                     'cover_height':round(height),'external_requests':requests,'script_errors':errors,
                     'horizontal_overflow':overflow,'browser':'headless Chromium','manual_visual_review_required':True}
            write_json(qa,summary)
            return summary
        finally:browser.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--out',type=Path);p.add_argument('--width',type=int,default=1080);p.add_argument('--browser-path');p.add_argument('--force',action='store_true');p.add_argument('--min-chars',type=int,default=1200)
    args=p.parse_args()
    try:
        if args.min_chars<0:raise DataError('--min-chars must be nonnegative')
        r=export(args.run_dir,args.out or args.run_dir/'player_poster.png',args.width,args.browser_path,args.force,args.min_chars)
        print(json.dumps(r,ensure_ascii=False,indent=2));return 0
    except Exception as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
