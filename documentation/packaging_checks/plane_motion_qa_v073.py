import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

case = Path('outputs/cade-cunningham-2024-25-v073')
html = (case / 'research_book.html').read_text(encoding='utf-8')
raw = json.loads((case / 'data_bundle.json').read_text(encoding='utf-8'))['tables']['player_shots']
game = '0022400002'
subset = sorted([r for r in raw if str(r['GAME_ID']).zfill(10) == game], key=lambda r: (
    r['PERIOD'], -int(r['MINUTES_REMAINING']) * 60 - int(r['SECONDS_REMAINING']), r['GAME_EVENT_ID']))
expected = [str(r['GAME_EVENT_ID']) for r in subset]
result = {'status': 'pending', 'errors': [], 'requests': [], 'cases': []}

def stats(page):
    return [page.locator('#' + x).inner_text() for x in ['shot-fga', 'shot-fgm', 'shot-pct', 'shot-visible']]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe')
    for width, preference in [(1440, 'no-preference'), (390, 'no-preference'), (390, 'reduce')]:
        ctx = browser.new_context(viewport={'width': width, 'height': 1024 if width > 820 else 844}, reduced_motion=preference)
        ctx.route('**/*', lambda route: route.abort())
        page = ctx.new_page()
        page.on('pageerror', lambda e: result['errors'].append(str(e)))
        page.on('request', lambda r: result['requests'].append(r.url))
        page.set_content(html, wait_until='load')
        page.evaluate('''() => {
          window.entered = new Set(); window.order = [];
          const explorer=document.getElementById('shot-explorer');
          explorer.addEventListener('animationstart',e=>{if(e.animationName==='shot-pop'){
            const d=e.target.closest('.shot-event').dataset; entered.add(d.gameId+'/'+d.eventId);
          }});
          new MutationObserver(()=>{const el=explorer.querySelector('.shot-selected');if(el){
            const id=el.dataset.eventId;if(window.order.at(-1)!==id)window.order.push(id);
          }}).observe(explorer.querySelector('svg'),{subtree:true,attributes:true,attributeFilter:['class']});
        }''')
        page.locator('[data-shot-view="flat"]').click()
        page.locator('.explorer-court').evaluate("e=>e.scrollIntoView({behavior:'instant',block:'start'})")
        if preference == 'no-preference':
            page.wait_for_function('() => window.entered.size===1457')
            page.wait_for_function("() => document.querySelectorAll('.shot-enter').length===0")
            assert page.locator('.shot-glyph').evaluate_all('els=>els.every(e=>getComputedStyle(e).opacity!=="0")')
        else:
            assert page.evaluate('window.entered.size') == 0
            assert page.locator('.shot-glyph').evaluate_all('els=>els.every(e=>e.getAnimations().length===0)')
        assert stats(page) == ['1457', '684', '46.9%', '1457']
        # Every data point remains inside the tighter complete-court viewport.
        assert page.locator('.explorer-court svg').evaluate('''s=>{
          const b=s.viewBox.baseVal;return [...s.querySelectorAll('.shot-event')].every(e=>{
            const x=Number(e.dataset.svgX),y=Number(e.dataset.svgY);return x-2>=b.x&&x+2<=b.x+b.width&&y-2>=b.y&&y+2<=b.y+b.height;
          });}''')
        page.locator('#shot-game').select_option(game)
        page.locator('#shot-speed').select_option('90')
        page.locator('#shot-play').click()
        page.wait_for_function("() => document.querySelectorAll('.shot-replayed').length>=2")
        page.locator('#shot-play').click()
        paused = page.locator('.shot-replayed').count()
        page.wait_for_timeout(300)
        assert page.locator('.shot-replayed').count() == paused
        assert page.locator('#shot-play').get_attribute('aria-pressed') == 'false'
        assert stats(page)[:3] == [str(len(subset)), str(sum(r['SHOT_MADE_FLAG'] for r in subset)), '40.0%']
        # Resume, finish, and compare observed sequence with raw period/clock ordering.
        page.locator('#shot-play').click()
        page.wait_for_function("() => document.getElementById('shot-play-progress').textContent.startsWith('完成')")
        assert page.evaluate('window.order') == expected, page.evaluate('window.order')
        assert page.locator('.shot-replayed').count() == len(subset)
        assert page.locator('.shot-event:not([hidden])').count() == len(subset)
        assert page.locator('.shot-focus').is_visible()
        if preference == 'reduce':
            assert page.locator('.shot-focus-ring').evaluate('e=>e.getAnimations().length') == 0
        # Starting over works; changing a filter cancels timers and clears old state.
        page.locator('#shot-play').click()
        page.locator('#shot-zone').select_option('MID')
        assert page.locator('#shot-play').get_attribute('aria-pressed') == 'false'
        assert page.locator('.shot-replayed').count() == 0
        page.wait_for_timeout(200)
        assert page.locator('.shot-selected').count() == 0
        # Restore fully opaque overview and prevent an empty replay.
        page.locator('#shot-reset').click()
        page.locator('#shot-zone').select_option('UNRESOLVED')
        page.locator('#shot-outcome').select_option('0')
        assert page.locator('#shot-play').is_disabled()
        assert stats(page) == ['1', '1', '100.0%', '0']
        page.locator('#shot-reset').click()
        # Selection is keyboard accessible and uses the same raw location.
        page.locator('#shot-game').select_option(game)
        page.locator('.shot-event-button').first.focus()
        page.keyboard.press('Enter')
        chosen = page.locator('.shot-selected')
        assert chosen.count() == 1
        assert page.locator('.shot-event-button[aria-pressed="true"]').count() == 1
        assert page.locator('.shot-focus-core').get_attribute('cx') == chosen.get_attribute('data-svg-x')
        if preference == 'no-preference':
            assert page.locator('.shot-focus-ring').evaluate('e=>e.getAnimations().length') == 1
        # Leaving the chart pauses, without silently restarting on return.
        page.locator('#shot-play').click()
        page.locator('#cover').evaluate("e=>e.scrollIntoView({behavior:'instant'})")
        page.wait_for_function("() => document.getElementById('shot-play').getAttribute('aria-pressed')==='false'")
        page.locator('#shot-explorer').evaluate("e=>e.scrollIntoView({behavior:'instant',block:'start'})")
        page.locator('#shot-stop').click()
        assert not page.locator('#shot-explorer').evaluate('e=>e.classList.contains("shot-replaying")')
        assert page.locator('.shot-focus').is_hidden()
        # Desktop/mobile screenshots of the full redesigned widget.
        page.locator('.shot-event-button').first.click()
        page.locator('#shot-explorer').screenshot(path=str(case / f'v073-plane-{width}-{preference}-shots.png'), animations='disabled')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert page.locator('#shot-explorer').evaluate('e=>e.scrollWidth<=e.clientWidth+1')
        # Print stops playback and emits the complete filtered sample, without halos.
        page.locator('#shot-play').click()
        page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
        assert page.locator('#shot-play').get_attribute('aria-pressed') == 'false'
        assert page.locator('.shot-replayed').count() == 0
        assert page.locator('.shot-event:not([hidden])').count() == len(subset)
        page.evaluate("window.dispatchEvent(new Event('afterprint'))")
        result['cases'].append(dict(width=width, motion=preference, all_events_animate=preference=='no-preference',
            sequence_matches_raw=True, pause_resume=True, filter_cancels_replay=True,
            empty_replay_disabled=True, statistics_unchanged=True, keyboard_selection=True,
            full_court_bounds=True, offscreen_pauses=True, print_restores_overview=True, no_overflow=True))
        ctx.close()
    ctx = browser.new_context(java_script_enabled=False, viewport={'width': 390, 'height': 844})
    page = ctx.new_page(); page.set_content(html)
    assert page.locator('.shot-playback').is_hidden()
    assert stats(page) == ['1457', '684', '46.9%', '1457']
    assert page.locator('.shot-event').count() == 1457
    result['no_js'] = 'full_static_court_and_stats'
    ctx.close(); browser.close()
result['raw_unchanged'] = all(hashlib.sha256((case / f).read_bytes()).digest() == hashlib.sha256((Path('outputs/cade-cunningham-2024-25-v07') / f).read_bytes()).digest()
    for f in ['data_bundle.json', 'analysis.json', 'claims.json', 'report.md', 'media_content.json', 'sources.json'])
assert not result['errors'] and not result['requests'] and result['raw_unchanged'], result
result['status'] = 'pass'
(case / 'plane_motion_validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
