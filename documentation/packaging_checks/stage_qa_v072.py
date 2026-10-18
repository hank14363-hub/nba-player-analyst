import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

case = Path('outputs/cade-cunningham-2024-25-v072')
html = (case / 'research_book.html').read_text(encoding='utf-8')
bundle = json.loads((case / 'data_bundle.json').read_text(encoding='utf-8'))
raw = bundle['tables']['player_shots']
result = {'status': 'pending', 'errors': [], 'requests': [], 'viewports': [], 'checks': []}

def stats(page):
    return [page.locator('#' + k).inner_text() for k in ['shot-fga', 'shot-fgm', 'shot-pct', 'shot-visible']]

def rendered(page, n):
    page.wait_for_function('(n) => document.querySelector("canvas.shot-stage-canvas").dataset.renderedCount===String(n)', arg=n)

def project_on_canvas(page, x, y):
    return page.locator('.shot-stage-canvas').evaluate('''(c,xy)=>{
      const b=c.getBoundingClientRect(),depth=(xy[1]/10+5.25)/94,scale=.48+.52*depth;
      return {x:b.x+b.width/2+xy[0]/10/25*b.width*.45*scale,y:b.y+b.height*(.26+.64*depth),
              inside:depth>=0&&depth<=1};}''', [x, y])

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe')
    # The HTML is rendered in memory, with all network requests blocked. No file
    # navigation, server, credentials, browser profile or browser permission changes.
    for width, motion in [(1440,'no-preference'), (1024,'reduce'), (768,'reduce'), (390,'no-preference'), (390,'reduce')]:
        ctx = browser.new_context(viewport={'width':width,'height':1024 if width>820 else 844}, reduced_motion=motion)
        ctx.route('**/*',lambda r:r.abort())
        page = ctx.new_page();page.on('pageerror',lambda e:result['errors'].append(str(e)))
        page.on('request',lambda r:result['requests'].append(r.url))
        page.set_content(html,wait_until='load')
        page.locator('.shot-stage').scroll_into_view_if_needed();rendered(page,1457)
        assert page.locator('.shot-stage').is_visible() and page.locator('.shot-flat').is_hidden()
        assert stats(page)==['1457','684','46.9%','1457']
        assert '非真实飞行轨迹' in page.locator('.stage-caption').inner_text()
        assert page.locator('.stage-count').inner_text()=='1457'
        assert page.locator('.shot-stage-canvas').evaluate('c=>c.width>0&&c.height>0')
        assert page.locator('.shot-stage-canvas').get_attribute('data-outside-count')=='0'
        page.locator('#shot-outcome').select_option('1');rendered(page,684)
        assert stats(page)==['1457','684','46.9%','684']
        page.locator('#shot-zone').select_option('MID');rendered(page,86)
        assert stats(page)==['191','86','45.0%','86']
        page.locator('#shot-reset').click();rendered(page,1457)
        # An isolated real backcourt point remains available on the full stage.
        remote=max(raw,key=lambda r:r['LOC_Y'])
        game=str(remote['GAME_ID']).zfill(10);event=str(remote['GAME_EVENT_ID'])
        page.locator('#shot-game').select_option(game)
        page.locator('#shot-zone').select_option('BACK')
        subset=[r for r in raw if str(r['GAME_ID']).zfill(10)==game and r['SHOT_ZONE_BASIC']=='Backcourt']
        rendered(page,len(subset));page.locator('.shot-stage-canvas').scroll_into_view_if_needed()
        point=project_on_canvas(page,remote['LOC_X'],remote['LOC_Y'])
        page.mouse.click(point['x'],point['y'])
        assert page.locator('.shot-stage-canvas').get_attribute('data-active-event')==game+'/'+event
        assert game in page.locator('#shot-detail').inner_text() and event in page.locator('#shot-detail').inner_text()
        page.locator('#shot-lights').uncheck()
        page.wait_for_function('() => document.querySelector(".shot-stage-canvas").dataset.arcCount==="0"')
        page.locator('#shot-lights').check()
        # Flat mode reuses the original events and selection, with real positions.
        page.locator('[data-shot-view="flat"]').click()
        assert page.locator('.shot-flat').is_visible() and page.locator('.shot-stage').is_hidden()
        assert page.locator('.shot-event:not([hidden])').count()==len(subset)
        assert page.locator('.shot-selected').get_attribute('data-event-id')==event
        page.locator('[data-shot-view="stage"]').click();rendered(page,len(subset))
        page.locator('#shot-reset').click()
        page.locator('#shot-game').select_option('0022400002');rendered(page,15)
        baseline=stats(page);assert baseline==['15','6','40.0%','15']
        page.locator('#shot-speed').select_option('90')
        page.locator('#shot-play').click()
        page.wait_for_function('() => Number(document.querySelector(".shot-stage-canvas").dataset.progress)>=2')
        page.locator('#shot-play').click()
        at_pause=page.locator('.stage-count').inner_text();page.wait_for_timeout(220)
        assert page.locator('.stage-count').inner_text()==at_pause and stats(page)==baseline
        assert page.locator('.stage-count-label').inner_text()=='累计点亮'
        page.locator('#shot-play').click()
        page.wait_for_function('() => document.querySelector("#shot-play-progress").textContent.startsWith("完成")')
        assert page.locator('.stage-count').inner_text()=='15 / 15' and stats(page)==baseline
        page.locator('#shot-stop').click();assert page.locator('.stage-count').inner_text()=='15'
        # Raw tag conflict and empty sample remain correct in both renderings.
        page.locator('#shot-reset').click();page.locator('#shot-zone').select_option('UNRESOLVED');rendered(page,1)
        page.locator('.shot-event-button').first.focus();page.keyboard.press('Enter')
        assert 'Above the Break 3' in page.locator('#shot-detail').inner_text()
        page.locator('#shot-outcome').select_option('0');rendered(page,0)
        assert page.locator('#shot-play').is_disabled() and stats(page)==['1','1','100.0%','0']
        page.locator('#shot-reset').click();rendered(page,1457)
        if motion=='reduce':
            page.locator('.shot-event-button').first.click()
            page.wait_for_function('() => document.querySelector(".shot-stage-canvas").dataset.arcCount==="0"')
        state=page.evaluate('''() => ({width:innerWidth,
          overflow:document.documentElement.scrollWidth>innerWidth,
          cardOverflow:[...document.querySelectorAll('.shot-stage,.stage-hud,.shot-explorer,.reading-card,.commentary-card')].filter(e=>e.scrollWidth>e.clientWidth+1).length,
          canvas:document.querySelector('.shot-stage-canvas').dataset.renderedCount,
          svg:document.querySelectorAll('svg').length})''')
        assert not state['overflow'] and not state['cardOverflow'] and state['svg']==10,state
        result['viewports'].append(state)
        result['checks'].append(dict(width=width,motion=motion,perspective_rows=True,full_court=True,backcourt_click=True,
            plane_sync=True,statistics_unchanged=True,pause_resume=True,light_toggle=True,
            empty_sample=True,raw_conflict=True,reduced_motion=motion=='reduce'))
        if width in [1440,390]:
            page.locator('.shot-stage').screenshot(path=str(case/f'stage-{width}-{motion}.png'),animations='disabled',
                style='#menu-toggle,.skip,.book-back,.reading-progress{visibility:hidden!important}')
            page.locator('#shot-explorer').screenshot(path=str(case/f'explorer-{width}-{motion}.png'),animations='disabled',
                style='#menu-toggle,.skip,.book-back,.reading-progress{visibility:hidden!important}')
        page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
        page.emulate_media(media='print')
        assert page.locator('.shot-stage').is_hidden() and page.locator('.shot-flat').is_visible()
        page.emulate_media(media='screen');page.evaluate("window.dispatchEvent(new Event('afterprint'))")
        ctx.close()
    ctx=browser.new_context(java_script_enabled=False,viewport={'width':390,'height':844})
    page=ctx.new_page();page.set_content(html)
    assert page.locator('.shot-stage').is_hidden() and page.locator('.shot-flat').is_visible()
    assert page.locator('.shot-view-switch').is_hidden() and stats(page)==['1457','684','46.9%','1457']
    ctx.close();browser.close()
result['no_js']='complete_original_static_svg'
old=Path('outputs/cade-cunningham-2024-25-v071')
result['unchanged_evidence']=all(hashlib.sha256((case/f).read_bytes()).digest()==hashlib.sha256((old/f).read_bytes()).digest()
    for f in ['data_bundle.json','analysis.json','report.md','claims.json','sources.json','media_content.json'])
assert not result['errors'] and not result['requests'] and result['unchanged_evidence'],result
result['status']='pass'
(case/'stage_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
