from pathlib import Path
from playwright.sync_api import sync_playwright
import json,hashlib
root=Path('work/forward-v072')
raw=json.loads((root/'run/data_bundle.json').read_text(encoding='utf-8'))['tables']['player_shots']
html=(root/'run/research_book.html').read_text(encoding='utf-8')
errors=[];requests=[];result=[]
def stats(q,rows,outcome='all'):
    hits=sum(r['SHOT_MADE_FLAG'] for r in rows)
    count=len(rows) if outcome=='all' else sum(str(r['SHOT_MADE_FLAG'])==outcome for r in rows)
    vals=[q.locator('#shot-'+k).inner_text() for k in ['fga','fgm','pct','visible']]
    expected=[str(len(rows)),str(hits),f'{hits/len(rows)*100:.1f}%' if rows else 'N/A',str(count)]
    assert vals==expected,(vals,expected)
    assert q.locator('.shot-event:not([hidden])').count()==count
    q.wait_for_function('n=>document.querySelector("canvas").dataset.renderedCount===String(n)',arg=count)
    assert q.locator('canvas').get_attribute('data-outside-count')=='0'
    return vals
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    for width,motion in [(1440,'no-preference'),(390,'no-preference'),(390,'reduce')]:
        ctx=b.new_context(viewport={'width':width,'height':1000},reduced_motion=motion)
        ctx.route('**/*',lambda r:r.abort())
        q=ctx.new_page();q.on('pageerror',lambda e:errors.append(str(e)));q.on('request',lambda r:requests.append(r.url))
        q.set_content(html,wait_until='load');q.evaluate('() => document.fonts.ready')
        canvas=q.locator('.shot-stage-canvas');canvas.scroll_into_view_if_needed()
        initial=stats(q,raw)
        points=q.locator('.shot-event').evaluate_all('es=>es.map(e=>({...e.dataset}))')
        originals={(str(r['GAME_ID']).zfill(10),str(r['GAME_EVENT_ID'])):r for r in raw}
        for e in points:
            r=originals[(e['gameId'],e['eventId'])]
            assert float(e['x'])==r['LOC_X'] and float(e['y'])==r['LOC_Y'] and int(e['made'])==r['SHOT_MADE_FLAG']
        q.locator('#shot-zone').select_option('BACK')
        backs=[r for r in raw if r['SHOT_ZONE_BASIC']=='Backcourt']
        stats(q,backs)
        canvas.scroll_into_view_if_needed()
        q.wait_for_timeout(1450)
        q.locator('.shot-stage').screenshot(path=str(root/f'backcourt-{width}-{motion}.png'),animations='disabled')
        # Click the original most distant backcourt event on the visible canvas.
        r=max(backs,key=lambda x:x['LOC_Y'])
        size=canvas.bounding_box();w=size['width'];h=size['height']
        depth=(r['LOC_Y']/10+5.25)/94
        x=w/2+(r['LOC_X']/10)/25*(w*.45)*(.48+.52*depth)
        y=h*(.26+.64*depth)
        canvas.click(position={'x':x,'y':y})
        q.wait_for_function('key=>document.querySelector("canvas").dataset.activeEvent===key',arg=str(r['GAME_ID']).zfill(10)+'/'+str(r['GAME_EVENT_ID']))
        assert str(r['GAME_EVENT_ID']) in q.locator('#shot-detail').inner_text()
        q.locator('[data-shot-view="flat"]').click()
        assert q.locator('.shot-flat').is_visible() and not q.locator('.shot-stage').is_visible()
        assert q.locator('.shot-selected').get_attribute('data-event-id')==str(r['GAME_EVENT_ID'])
        q.locator('[data-shot-view="stage"]').click()
        canvas.scroll_into_view_if_needed()
        assert q.locator('.shot-stage').is_visible()
        q.locator('#shot-reset').click();q.locator('#shot-game').select_option('0022400002')
        game=[r for r in raw if str(r['GAME_ID']).zfill(10)=='0022400002']
        sample=stats(q,game)
        q.locator('#shot-outcome').select_option('1');stats(q,game,'1')
        q.locator('#shot-outcome').select_option('all');stats(q,game)
        canvas.scroll_into_view_if_needed()
        q.locator('#shot-speed').select_option('700')
        # Use existing button without causing Playwright to scroll away from court.
        q.locator('#shot-play').evaluate('e=>e.click()')
        first=min(game,key=lambda r:(r['PERIOD'],-(r['MINUTES_REMAINING']*60+r['SECONDS_REMAINING']),r['GAME_EVENT_ID']))
        q.wait_for_function('() => document.querySelector("canvas").dataset.progress==="1"')
        assert q.locator('canvas').get_attribute('data-active-event')==str(first['GAME_ID']).zfill(10)+'/'+str(first['GAME_EVENT_ID'])
        q.locator('#shot-play').evaluate('e=>e.click()')
        count=q.locator('canvas').get_attribute('data-progress')
        q.wait_for_timeout(950)
        assert q.locator('canvas').get_attribute('data-progress')==count
        assert q.locator('canvas').get_attribute('data-arc-count')=='0'
        assert [q.locator('#shot-'+k).inner_text() for k in ['fga','fgm','pct','visible']]==sample
        q.locator('#shot-lights').uncheck()
        q.locator('#shot-play').evaluate('e=>e.click()')
        q.wait_for_function('n=>Number(document.querySelector("canvas").dataset.progress)>Number(n)',arg=count)
        assert q.locator('canvas').get_attribute('data-arc-count')=='0'
        q.locator('#shot-play').evaluate('e=>e.click()')
        q.locator('#shot-outcome').select_option('0')
        assert q.locator('#shot-play').get_attribute('aria-pressed')=='false'
        stats(q,game,'0')
        q.locator('#shot-zone').select_option('UNRESOLVED')
        stats(q,[],'0');assert q.locator('#shot-play').is_disabled()
        q.locator('#shot-reset').click();q.locator('#shot-game').select_option('0022400002')
        canvas.scroll_into_view_if_needed()
        q.locator('#shot-speed').select_option('90');q.locator('#shot-play').evaluate('e=>e.click()')
        q.wait_for_function('() => document.getElementById("shot-play-progress").textContent.startsWith("完成")')
        assert q.locator('canvas').get_attribute('data-progress')=='15'
        assert not q.locator('#shot-play').get_attribute('aria-pressed')=='true'
        stats(q,game)
        q.locator('.shot-stage').screenshot(path=str(root/f'complete-{width}-{motion}.png'),animations='disabled')
        q.locator('#shot-stop').evaluate('e=>e.click()')
        q.wait_for_function('() => document.querySelector("canvas").dataset.progress==="0"')
        if motion=='reduce':
            assert q.locator('canvas').get_attribute('data-arc-count')=='0'
            assert q.locator('.shot-enter').count()==0
        assert not q.evaluate('() => document.documentElement.scrollWidth>innerWidth')
        assert '非真实飞行轨迹' in q.locator('.stage-caption').inner_text()
        q.evaluate('() => window.dispatchEvent(new Event("beforeprint"))')
        q.emulate_media(media='print')
        assert q.locator('.shot-flat').is_visible() and not q.locator('.shot-stage').is_visible()
        q.emulate_media(media='screen')
        q.evaluate('() => window.dispatchEvent(new Event("afterprint"))')
        result.append(dict(width=width,motion=motion,initial=initial,game=sample,backcourtEvents=len(backs),status='pass'))
        ctx.close()
    b.close()
assert not errors and not requests
(root/'results.json').write_text(json.dumps(dict(checks=result,errors=errors,requests=requests),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
