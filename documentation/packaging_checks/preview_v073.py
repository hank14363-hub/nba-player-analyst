import io
import time
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

case=Path('outputs/cade-cunningham-2024-25-v073')
html=(case/'research_book.html').read_text(encoding='utf-8')
frames=[];stamps=[]
def visual_row(page,path):
    page.locator('.explorer-layout').scroll_into_view_if_needed()
    clip=page.locator('.explorer-layout').evaluate('''e=>{
      const r=e.getBoundingClientRect(),a=e.querySelector('figure').getBoundingClientRect(),b=e.querySelector('.shot-reading').getBoundingClientRect();
      return {x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:Math.max(a.bottom,b.bottom)-r.y};
    }''')
    png=page.locator('.explorer-layout').screenshot(animations='disabled',style='#menu-toggle,.skip,.book-back,.reading-progress{visibility:hidden!important}')
    im=Image.open(io.BytesIO(png)).convert('RGB')
    im.crop((0,0,im.width,round(clip['height']))).save(path)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe')
    page=b.new_page(viewport={'width':1440,'height':1024},reduced_motion='no-preference')
    page.route('**/*',lambda r:r.abort());page.set_content(html,wait_until='load')
    page.locator('canvas').scroll_into_view_if_needed();page.wait_for_timeout(1400)
    visual_row(page,case/'shot-research-preview.png')
    page.locator('.shot-stage').screenshot(path=str(case/'stage-preview.png'),animations='disabled')
    page.locator('#reading-scoring-3').screenshot(path=str(case/'text-jump-preview.png'),animations='disabled')
    page.locator('#reading-scoring-3 .shot-text-link').click();page.wait_for_timeout(1400)
    visual_row(page,case/'linked-midrange-preview.png')
    page.locator('#shot-reset').click()
    page.locator('canvas').scroll_into_view_if_needed();page.wait_for_timeout(1400)
    page.locator('canvas').evaluate('''c=>{const r=c.getBoundingClientRect(),depth=5.25/47,s=1-.16*depth;window.previewPoint={x:r.x+r.width/2,y:r.y+r.height*(.88-.74*depth)};}''')
    pos=page.evaluate('window.previewPoint');page.mouse.click(pos['x'],pos['y'])
    page.locator('.shot-event-summary').screenshot(path=str(case/'overlap-candidates-preview.png'),animations='disabled')
    page.locator('#shot-game').select_option('0022400223');page.locator('#shot-speed').select_option('240')
    page.locator('.shot-stage').scroll_into_view_if_needed();page.wait_for_timeout(1400);page.locator('#shot-play').click()
    for _ in range(36):
        im=Image.open(io.BytesIO(page.locator('.shot-stage').screenshot(animations='allow'))).convert('RGB')
        frames.append(im);stamps.append(time.monotonic());page.wait_for_timeout(45)
    durations=[max(40,min(500,int((stamps[i+1]-stamps[i])*1000))) for i in range(len(stamps)-1)]+[900]
    frames[0].save(case/'shot-stage-preview.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=True)
    frames[min(8,len(frames)-1)].save('work/v073/animation-frame.png')
    page.close()
    page=b.new_page(viewport={'width':390,'height':844},reduced_motion='reduce')
    page.route('**/*',lambda r:r.abort());page.set_content(html,wait_until='load')
    page.locator('.explorer-court').screenshot(path=str(case/'shot-mobile-court.png'),animations='disabled',style='#menu-toggle,.skip,.book-back,.reading-progress{visibility:hidden!important}')
    page.locator('#reading-scoring-3 .shot-text-link').click()
    page.locator('.shot-reading').screenshot(path=str(case/'shot-mobile-reading.png'),animations='disabled',style='#menu-toggle,.skip,.book-back,.reading-progress{visibility:hidden!important}')
    b.close()
print('Saved final linked research previews, overlap candidates and actual browser replay GIF')
