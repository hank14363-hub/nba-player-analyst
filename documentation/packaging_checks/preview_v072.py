import io
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

case=Path('outputs/cade-cunningham-2024-25-v072')
html=(case/'research_book.html').read_text(encoding='utf-8')
raw=json.loads((case/'data_bundle.json').read_text(encoding='utf-8'))['tables']['player_shots']
game=Counter(str(r['GAME_ID']).zfill(10) for r in raw).most_common(1)[0][0]
frames,stamps=[],[]
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe')
    page=b.new_page(viewport={'width':1440,'height':1024},reduced_motion='no-preference')
    page.route('**/*',lambda route:route.abort());page.set_content(html,wait_until='load')
    page.locator('#shot-game').select_option(game);page.locator('#shot-speed').select_option('240')
    page.locator('.shot-stage').scroll_into_view_if_needed();page.wait_for_timeout(1400)
    page.locator('#shot-play').click()
    for _ in range(36):
        img=Image.open(io.BytesIO(page.locator('.shot-stage').screenshot(animations='allow'))).convert('RGB')
        img.thumbnail((720,660));frames.append(img);stamps.append(time.monotonic());page.wait_for_timeout(45)
    page.locator('#shot-stop').click();page.locator('#shot-reset').click()
    page.locator('.shot-stage').scroll_into_view_if_needed();page.wait_for_timeout(1400)
    png=page.locator('.shot-stage').screenshot(animations='disabled')
    image=Image.open(io.BytesIO(png)).convert('RGB');image.thumbnail((720,660));image.save(case/'stage-preview.png')
    page.locator('#shot-explorer').screenshot(path=str(case/'shot-stage-preview.png'),animations='disabled')
    b.close()
durations=[max(40,min(400,int((stamps[i+1]-stamps[i])*1000))) for i in range(len(stamps)-1)]+[900]
frames[0].save(case/'shot-stage-preview.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=True)
reference={
    'url':'https://www.bilibili.com/video/BV1LV411F7wb/',
    'title':'库里三分投篮分布',
    'page_publishing_account':'NBA篮球60帧',
    'page_published_at':'2023-10-02 15:13:17',
    'recorded_at':datetime.now().astimezone().isoformat(),
    'timestamp_scope':'Record generation time; page visually inspected earlier in this session.',
    'inspection':'Actual browser playback and paused visual samples near 18.4s and 28.4s of a 34s clip; not a complete watch.',
    'used_as':'Visual reference only: perspective wood court, luminous points/arcs, name/count header and progress strip.',
    'original_graphics_authorship':'Not independently verified; publishing account is not asserted to be original creator.',
    'adaptation':'Own drawn generic court and decorative light connections based only on the current validated Cade events.',
    'not_reused':['original frames','logos','music','Curry totals','measured trajectory claims'],
    'evidence_unchanged':True
}
(case/'style_reference.json').write_text(json.dumps(reference,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Saved perspective court PNG/GIF; example game:',game)
