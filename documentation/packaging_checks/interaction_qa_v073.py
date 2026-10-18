import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

case=Path('outputs/cade-cunningham-2024-25-v073')
html=(case/'research_book.html').read_text(encoding='utf-8')
raw=json.loads((case/'data_bundle.json').read_text(encoding='utf-8'))['tables']['player_shots']
zones={'Restricted Area':'RA','In The Paint (Non-RA)':'PAINT','Mid-Range':'MID','Left Corner 3':'LC3','Right Corner 3':'RC3','Above the Break 3':'ATB3','Backcourt':'BACK'}
def zone(r):
    value=zones[r['SHOT_ZONE_BASIC']]
    if (value in ['RA','PAINT','MID'] and r['SHOT_TYPE']!='2PT Field Goal') or (value in ['LC3','RC3','ATB3'] and r['SHOT_TYPE']!='3PT Field Goal'):
        return 'UNRESOLVED'
    return value
result={'status':'pending','errors':[],'requests':[],'cases':[]}
def stats(page):
    return [page.locator('#'+k).inner_text() for k in ['shot-fga','shot-fgm','shot-pct','shot-visible']]
def wait_canvas(page,n):
    page.wait_for_function('(n)=>document.querySelector("canvas").dataset.renderedCount===String(n)',arg=n)
def point(page,r,full=False):
    # Project independently from raw LOC_X/LOC_Y into the documented display view.
    return page.locator('canvas').evaluate('''(c,v)=>{
      const b=c.getBoundingClientRect(),depth=(v.y/10+5.25)/(v.full?94:47),s=1-(v.full?.34:.16)*depth;
      return {x:b.x+b.width/2+v.x/10/25*b.width*.44*s,y:b.y+b.height*(.88-.74*depth)};
    }''',{'x':r['LOC_X'],'y':r['LOC_Y'],'full':full})
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe')
    for width,motion in [(1440,'no-preference'),(1024,'reduce'),(768,'reduce'),(390,'no-preference'),(390,'reduce')]:
        ctx=browser.new_context(viewport={'width':width,'height':1024 if width>820 else 844},reduced_motion=motion)
        ctx.route('**/*',lambda r:r.abort())
        page=ctx.new_page();page.on('pageerror',lambda e:result['errors'].append(str(e)));page.on('request',lambda r:result['requests'].append(r.url))
        page.set_content(html,wait_until='load');page.locator('canvas').scroll_into_view_if_needed()
        wait_canvas(page,sum(r['LOC_Y']<=417.5 for r in raw))
        assert stats(page)==['1457','684','46.9%','1457']
        assert '后场共 4 次' in page.locator('.stage-coverage').inner_text()
        assert page.locator('canvas').get_attribute('data-total-count')=='1457'
        assert page.locator('canvas').get_attribute('data-offview-count')==str(sum(r['LOC_Y']>417.5 for r in raw))
        assert page.locator('canvas').get_attribute('data-outside-count')=='0'
        assert '483' in page.locator('#shot-reading-summary').inner_text()
        # Every static event is checked against the original row, not its own summary.
        dom=page.locator('.shot-event').evaluate_all('els=>els.map(e=>[e.dataset.gameId,Number(e.dataset.eventId),Number(e.dataset.x),Number(e.dataset.y),Number(e.dataset.made)])')
        assert set(map(tuple,dom))=={(str(r['GAME_ID']).zfill(10),r['GAME_EVENT_ID'],r['LOC_X'],r['LOC_Y'],r['SHOT_MADE_FLAG']) for r in raw}
        # Region structure always uses the game sample, even while one region/outcome is selected.
        for game_id in ['all','0022400002','0022400223']:
            page.locator('#shot-game').select_option(game_id)
            base=raw if game_id=='all' else [r for r in raw if str(r['GAME_ID']).zfill(10)==game_id]
            for code in ['all','MID','3PT','2PT','UNRESOLVED']:
                page.locator('#shot-zone').select_option(code)
                sample=[r for r in base if code=='all' or zone(r)==code or (code=='3PT' and r['SHOT_TYPE']=='3PT Field Goal') or (code=='2PT' and r['SHOT_TYPE']=='2PT Field Goal')]
                made=sum(r['SHOT_MADE_FLAG'] for r in sample)
                expected=[str(len(sample)),str(made),f'{made/len(sample)*100:.1f}%' if sample else 'N/A']
                for outcome in ['all','1','0']:
                    page.locator('#shot-outcome').select_option(outcome)
                    shown=sample if outcome=='all' else [r for r in sample if str(r['SHOT_MADE_FLAG'])==outcome]
                    assert stats(page)==expected+[str(len(shown))],(width,game_id,code,outcome,stats(page))
                    readings=page.locator('#shot-region-body tr').evaluate_all('rows=>rows.map(r=>({zone:r.dataset.zone,fga:Number(r.dataset.fga),fgm:Number(r.dataset.fgm),cells:[...r.cells].map(c=>c.textContent)}))')
                    for row in readings:
                        group=[r for r in base if zone(r)==row['zone']]
                        assert row['fga']==len(group) and row['fgm']==sum(r['SHOT_MADE_FLAG'] for r in group)
                        assert row['cells'][2]==(f'{len(group)/len(base)*100:.1f}%' if base else 'N/A')
                        if not group:assert row['cells'][3]=='N/A'
                    assert sum(row['fga'] for row in readings)==len(base)
        page.locator('#shot-reset').click();page.locator('[data-zone-filter="MID"]').click()
        assert stats(page)==['191','86','45.0%','191']
        assert '回合末' in page.locator('#shot-reading-boundary').inner_text()
        page.locator('#shot-outcome').select_option('1')
        assert stats(page)==['191','86','45.0%','86']
        page.locator('#shot-all-zones').click();assert stats(page)==['1457','684','46.9%','684']
        # Text jump restores the full-season sample and both outcomes, then returns to its exact card.
        page.locator('#shot-game').select_option('0022400002')
        link=page.locator('#reading-scoring-3 .shot-text-link');link.click()
        assert stats(page)==['191','86','45.0%','191'] and page.locator('#shot-game').input_value()=='all'
        assert '完整赛季' in page.locator('#shot-context').inner_text()
        assert page.locator('#shot-return').get_attribute('href')=='#reading-scoring-3'
        page.locator('#shot-return').click();assert page.evaluate('location.hash')=='#reading-scoring-3'
        page.locator('#full-article').evaluate('e=>e.open=true')
        article_link=page.locator('.full-article .shot-text-link[data-shot-zone="3PT"]').first
        target=article_link.get_attribute('data-shot-return');article_link.click()
        assert stats(page)==['418','149','35.6%','418']
        page.locator('#full-article').evaluate('e=>e.open=false')
        page.locator('#shot-return').click();page.wait_for_function('()=>document.querySelector("#full-article").open')
        assert page.evaluate('location.hash')=='#'+target
        # Real overlapping positions expose candidates in BOTH views.
        page.locator('#shot-reset').click();page.locator('#shot-extent').select_option('focus');page.locator('canvas').scroll_into_view_if_needed();wait_canvas(page,1453)
        center=min((r for r in raw if r['LOC_Y']<=417.5),key=lambda r:abs(r['LOC_X'])+abs(r['LOC_Y']))
        pos=point(page,center);page.mouse.click(pos['x'],pos['y'])
        assert page.locator('.shot-candidates').is_visible()
        assert page.locator('.shot-candidate-button').count()>1
        candidate=page.locator('.shot-candidate-button').first;key=candidate.get_attribute('data-event-key');candidate.click()
        assert page.locator('canvas').get_attribute('data-active-event')==key
        assert key.split('/')[1] in page.locator('#shot-detail').inner_text()
        page.locator('#shot-candidate-next').click();assert page.locator('#shot-candidate-page').inner_text().startswith('2 /')
        page.locator('#shot-candidate-close').click();assert page.locator('.shot-candidates').is_hidden()
        page.locator('[data-shot-view="flat"]').click();page.locator('.shot-flat svg').scroll_into_view_if_needed()
        d=page.locator('.shot-event').filter(has=page.locator('title'))
        flatpoint=page.locator('.shot-flat svg').evaluate('''(s,v)=>{const p=new DOMPoint(240+v.x*.54,68.35+v.y*.54).matrixTransform(s.getScreenCTM());return {x:p.x,y:p.y};}''',{'x':center['LOC_X'],'y':center['LOC_Y']})
        page.mouse.click(flatpoint['x'],flatpoint['y']);assert page.locator('.shot-candidates').is_visible()
        # Selecting a real offview/backcourt event reveals the full court without changing sample.
        page.locator('[data-shot-view="stage"]').click();page.locator('#shot-zone').select_option('BACK')
        assert stats(page)==['4','0','0.0%','4']
        wait_canvas(page,4);assert page.locator('#shot-extent').input_value()=='full'
        page.locator('.shot-event-button').first.click();wait_canvas(page,4)
        assert page.locator('#shot-extent').input_value()=='full'
        assert page.locator('canvas').get_attribute('data-offview-count')=='0'
        page.locator('#shot-reset').click();page.locator('canvas').scroll_into_view_if_needed();wait_canvas(page,1457)
        assert page.locator('canvas').get_attribute('data-outside-count')=='0'
        page.locator('.shot-stage').screenshot(path=str(case/f'full-{width}-{motion}.png'),animations='disabled')
        page.locator('#shot-extent').select_option('focus');wait_canvas(page,1453)
        page.locator('#shot-explorer').screenshot(path=str(case/f'explorer-{width}-{motion}.png'),animations='disabled',style='#menu-toggle,.skip,.book-back,.reading-progress{visibility:hidden!important}')
        # Replay remains chronological, pause stops progress, and lights are optional.
        page.locator('#shot-game').select_option('0022400002');page.locator('#shot-speed').select_option('90')
        page.locator('#shot-play').click();page.wait_for_function('()=>Number(document.querySelector("canvas").dataset.progress)>=2')
        page.locator('#shot-play').click();progress=page.locator('canvas').get_attribute('data-progress');page.wait_for_timeout(280)
        assert progress==page.locator('canvas').get_attribute('data-progress') and stats(page)==['15','6','40.0%','15']
        assert page.locator('canvas').get_attribute('data-arc-count')=='0'
        page.locator('#shot-lights').uncheck();page.locator('#shot-play').click()
        page.wait_for_function('()=>document.querySelector("#shot-play-progress").textContent.startsWith("完成")')
        assert page.locator('.stage-count').inner_text()=='15 / 15' and stats(page)==['15','6','40.0%','15']
        page.locator('#shot-reset').click();page.locator('#shot-zone').select_option('UNRESOLVED');page.locator('#shot-outcome').select_option('0')
        assert page.locator('#shot-play').is_disabled() and stats(page)==['1','1','100.0%','0']
        page.locator('#shot-reset').click()
        state=page.evaluate('''()=>({overflow:document.documentElement.scrollWidth>innerWidth,cardOverflow:[...document.querySelectorAll('.shot-reading,.stage-hud,.shot-explorer,.shot-candidates')].filter(e=>e.scrollWidth>e.clientWidth+1).length})''')
        assert not state['overflow'] and not state['cardOverflow'],state
        page.evaluate('window.dispatchEvent(new Event("beforeprint"))');page.emulate_media(media='print')
        assert page.locator('.shot-stage').is_hidden() and page.locator('.shot-flat').is_visible()
        assert page.locator('.shot-event:not([hidden])').count()==1457
        result['cases'].append({'width':width,'motion':motion,'raw_events':1457,'filter_combinations_checked':45,'region_denominators':True,'focus_and_full':True,'overlap_in_both_views':True,'text_and_article_roundtrip':True,'backcourt_auto_reveal':True,'replay_and_print':True,'overflow':state})
        ctx.close()
    for mode in ['no_js','no_canvas']:
        ctx=browser.new_context(viewport={'width':390,'height':844},java_script_enabled=mode!='no_js',reduced_motion='reduce')
        ctx.route('**/*',lambda r:r.abort())
        if mode=='no_canvas':ctx.add_init_script('HTMLCanvasElement.prototype.getContext=()=>null;')
        page=ctx.new_page()
        page.set_content(html)
        assert page.locator('.shot-stage').is_hidden() and page.locator('.shot-flat').is_visible()
        assert page.locator('.shot-event').count()==1457 and stats(page)==['1457','684','46.9%','1457']
        if mode=='no_js':assert page.locator('.shot-reading').is_hidden()
        else:
            page.locator('#shot-zone').select_option('MID');assert stats(page)==['191','86','45.0%','191']
        result[mode]='pass';ctx.close()
    browser.close()
unchanged=['data_bundle.json','analysis.json','claims.json','report.md','sources.json','media_content.json','player_poster.png','player_poster.html']
result['unchanged_evidence']=all(hashlib.sha256((case/n).read_bytes()).digest()==hashlib.sha256((Path('outputs/cade-cunningham-2024-25-v072')/n).read_bytes()).digest() for n in unchanged)
assert not result['errors'] and not result['requests'] and result['unchanged_evidence'],result
result['status']='pass';(case/'interaction_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
