import json,re,math
from pathlib import Path
from collections import Counter
from playwright.sync_api import sync_playwright
case=Path('outputs/cade-cunningham-2024-25-v08');html=(case/'research_book.html').read_text(encoding='utf-8')
bundle=json.loads((case/'data_bundle.json').read_text(encoding='utf-8'))
a=json.loads((case/'analysis.json').read_text(encoding='utf-8'))
expected=Counter((min(9,math.floor((r['LOC_X']+250)/50)),min(9,math.floor((r['LOC_Y']+52.5)/50))) for r in bundle['tables']['player_shots'] if r['LOC_Y']<=417.5)
result=dict(errors=[],requests=[],widths=[],raw_fga=1457,independent_density_bins=len(expected),cohort_n=12)
hide='#menu-toggle,.skip,.book-back,.reading-progress{visibility:hidden!important}'
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe')
 for width in [1440,1024,768,390]:
  ctx=b.new_context(viewport=dict(width=width,height=1024 if width>820 else 844),reduced_motion='reduce')
  ctx.route('**/*',lambda r:r.abort());page=ctx.new_page();page.on('pageerror',lambda e:result['errors'].append(str(e)));page.on('request',lambda r:result['requests'].append(r.url))
  page.set_content(html,wait_until='load');page.evaluate('document.fonts.ready')
  core=page.locator('.cover .kpi-value [data-metric-id]').evaluate_all('els=>els.map(e=>[e.dataset.metricId,Number(e.dataset.value)])')
  assert [r[0] for r in core]==['AST_PCT','PCT_UAST_FGM','DRIVES_PER_GAME','PTS_PER75']
  assert len(page.locator('.cohort-axis-table tbody tr').all())==6
  page.locator('.cohort-roster > summary').click()
  assert page.locator('.cohort-roster tbody tr').count()==12
  assert page.locator('.target-player').count()==1
  page.locator('.cohort-roster > summary').click()
  page.locator('.cohort-sensitivity > summary').click()
  assert page.locator('.cohort-sensitivity tbody tr').count()==2
  page.locator('.cohort-sensitivity > summary').click()
  # Independent grid assignment checks every displayed cell, including empty-cell omissions.
  actual=page.locator('#density-reading svg rect:has(title)').evaluate_all('els=>els.map(e=>[Number(e.getAttribute("x")),Number(e.getAttribute("y")),e.textContent])')
  counted={(int((x-40)/40),int((y-35)/40)):int(re.search(r'出手 (\d+)',title)[1]) for x,y,title in actual}
  assert counted==dict(expected);assert sum(counted.values())==1453
  assert '视窗外 4 次' in page.locator('#density-reading').inner_text()
  # Evidence link opens its containing article/claim without relying on hidden destinations.
  link=page.locator('#role-comparison .claim-jump').filter(has_text='C30');target=link.get_attribute('href');link.click();assert page.locator(target).is_visible()
  page.locator('.cover a[href="#claim-C36"]').first.click();assert page.locator('#claim-C36').evaluate('e=>e.open')
  page.locator('#source-search').fill('EPM');assert page.locator('.source-card:not([hidden])').count()==1
  page.locator('#source-EXT_EPM_ACCESS > summary').click();assert '自定义' in page.locator('#source-EXT_EPM_ACCESS').inner_text() or 'custom' in page.locator('#source-EXT_EPM_ACCESS').inner_text()
  page.locator('#source-search').fill('')
  state=page.evaluate('''()=>({width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,
    charts:document.querySelectorAll('svg').length,
    svgTextBounds:[...document.querySelectorAll('#role-comparison svg,#density-reading svg')].flatMap(s=>[...s.querySelectorAll('text')].map(t=>{const r=t.getBBox(),v=s.viewBox.baseVal;return {text:t.textContent,bad:r.x< -1||r.x+r.width>v.width+1||r.y< -1||r.y+r.height>v.height+1};})).filter(r=>r.bad)})''')
  assert not state['overflow'];assert not state['svgTextBounds'],state
  result['widths'].append(state)
  if width in [1440,390]:
   for selector,name in [('.cover','cover-preview'),('#role-comparison','comparison-preview'),('#density-reading','density-preview')]:
    page.locator(selector).screenshot(path=str(case/f'{name}-{width}.png'),animations='disabled',style=hide)
  page.emulate_media(media='print')
  assert page.locator('#density-reading svg').is_visible()
  ctx.close()
 # No-JS still permits opening table evidence and keeps original full scatter.
 ctx=b.new_context(viewport=dict(width=390,height=844),java_script_enabled=False);page=ctx.new_page();ctx.route('**/*',lambda r:r.abort());page.set_content(html)
 assert page.locator('#role-comparison svg').count()==2
 page.locator('.cohort-roster > summary').click();assert page.locator('.target-player').is_visible()
 assert page.locator('.shot-event').count()==1457
 result['no_js']=True;ctx.close();b.close()
result['status']='pass' if not result['errors'] and not result['requests'] else 'fail'
(case/'comparison_browser_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2));assert result['status']=='pass'
