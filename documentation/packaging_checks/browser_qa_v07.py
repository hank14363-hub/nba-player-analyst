import json,hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright

case=Path('outputs/cade-cunningham-2024-25-v07');html=(case/'research_book.html').read_text(encoding='utf-8')
bundle=json.loads((case/'data_bundle.json').read_text(encoding='utf-8'));rows=bundle['tables']['player_shots']
result=dict(errors=[],requests=[],viewports=[],filter_checks=[])

def snap(page):
    return [page.locator('#'+key).inner_text() for key in ['shot-fga','shot-fgm','shot-pct','shot-visible']]

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    for width in [1440,1024,768,390]:
        ctx=browser.new_context(viewport=dict(width=width,height=1024 if width>820 else 844),reduced_motion='reduce')
        ctx.route('**/*',lambda r:r.abort());page=ctx.new_page()
        page.on('pageerror',lambda e:result['errors'].append(str(e)));page.on('request',lambda r:result['requests'].append(r.url))
        page.set_content(html,wait_until='load');page.evaluate('document.fonts.ready')
        assert snap(page)==['1457','684','46.9%','1457'],snap(page)
        page.locator('#shot-outcome').select_option('1');assert snap(page)==['1457','684','46.9%','684'];assert page.locator('.shot-event:not([hidden])').count()==684
        assert page.locator('.shot-event[hidden]').first.evaluate("e=>getComputedStyle(e).display==='none'")
        page.locator('#shot-outcome').select_option('0');assert snap(page)==['1457','684','46.9%','773']
        page.locator('#shot-reset').click()
        page.locator('#shot-zone').select_option('MID');assert snap(page)==['191','86','45.0%','191']
        page.locator('#shot-outcome').select_option('1');assert snap(page)==['191','86','45.0%','86']
        page.locator('#shot-reset').click()
        game=str(rows[0]['GAME_ID']).zfill(10);subset=[r for r in rows if str(r['GAME_ID']).zfill(10)==game]
        page.locator('#shot-game').select_option(game);s=snap(page);assert s[0]==str(len(subset)) and s[1]==str(sum(r['SHOT_MADE_FLAG'] for r in subset))
        page.locator('#shot-reset').click();page.locator('#shot-zone').select_option('UNRESOLVED');assert snap(page)[0]=='1'
        page.locator('.shot-event-button').first.click();detail=page.locator('#shot-detail').inner_text();assert '0022400881' in detail and '637' in detail and 'Above the Break 3' in detail and '2PT Field Goal' in detail
        page.locator('#shot-outcome').select_option('0');assert snap(page)[3]=='0';assert page.locator('#shot-next').is_disabled()
        page.locator('#shot-reset').click();page.locator('#shot-next').click();assert '第 2 /' in page.locator('#shot-page').inner_text()
        page.locator('.shot-event-button').first.focus();page.keyboard.press('Enter');assert page.locator('#shot-detail').inner_text()!='请选择一个事件。'
        page.locator('#shot-reset').click()
        page.locator('#source-search').fill('McKeone');assert page.locator('.source-card:not([hidden])').count()==1
        page.locator('.commentary-card a[href="#source-EXT_LYONS"]').click();page.wait_for_function("() => document.getElementById('source-EXT_LYONS').open")
        assert page.locator('#source-search').input_value()==''
        assert page.locator('#source-EXT_LYONS').inner_text().find('2025-05-02')>=0
        assert not page.locator('#full-article').evaluate('e=>e.open')
        page.locator('#full-article > summary').click();assert page.locator('#full-article').evaluate('e=>e.open')
        page.locator('#full-article > summary').click()
        state=page.evaluate('''() => ({width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,
          cards:document.querySelectorAll('.reading-card').length,svg:document.querySelectorAll('svg').length,
          horizontalOverflow:[...document.querySelectorAll('.reading-card,.commentary-card,.shot-explorer')].filter(e=>e.scrollWidth>e.clientWidth+1).length,
          svgTextOverflow:[...document.querySelectorAll('svg')].flatMap(s=>[...s.querySelectorAll('text')].filter(t=>{const b=t.getBBox();return b.x< -1||b.x+b.width>s.viewBox.baseVal.width+1})).length,
          articleCharts:document.querySelectorAll('.article-chart').length,articleCollapsed:!document.getElementById('full-article').open,
          imageLoaded:[...document.querySelectorAll('.cover img')].every(i=>i.complete&&i.naturalWidth>0)})''')
        result['viewports'].append(state);result['filter_checks'].append(dict(width=width,whole_season=True,outcome_keeps_denominator=True,midrange=True,game_counts=True,conflict_preserved=True,zero_result=True,pagination=True,keyboard_event=True,article_sources=True))
        if width in [1440,390]:
            for selector,name in [('#reading-scoring-1','story'),('#shot-explorer','explorer'),('#module-08','commentary')]:
                page.locator(selector).evaluate("e=>e.scrollIntoView({behavior:'instant',block:'start'})")
                page.screenshot(path=str(case/f'v07-{width}-{name}.png'),animations='disabled')
        ctx.close()
    ctx=browser.new_context(viewport=dict(width=390,height=844),java_script_enabled=False)
    page=ctx.new_page();page.set_content(html);result['no_js']=dict(points=page.locator('.shot-event').count(),static_stats=snap(page),controls_hidden=not page.locator('.shot-controls').is_visible(),article_accessible=page.locator('#full-article > summary').is_visible())
    ctx.close();browser.close()
old=Path('outputs/cade-cunningham-2024-25-v061')
result['unchanged_raw_stats']=all(hashlib.sha256((old/f).read_bytes()).digest()==hashlib.sha256((case/f).read_bytes()).digest() for f in ['data_bundle.json','analysis.json','media_content.json'])
result['status']='pass' if not result['requests'] and not result['errors'] and result['unchanged_raw_stats'] and all(not x['overflow'] and not x['horizontalOverflow'] and not x['svgTextOverflow'] and x['svg']==10 and x['cards']==13 and x['articleCollapsed'] and x['imageLoaded'] for x in result['viewports']) else 'fail'
(case/'browser_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));assert result['status']=='pass'
