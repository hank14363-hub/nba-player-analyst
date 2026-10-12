(() => {
  'use strict';
  const nav = document.getElementById('toc');
  const toggle = document.getElementById('menu-toggle');
  const links = [...nav.querySelectorAll('a[href^="#"]')];
  const sections = links.map(a => document.querySelector(a.getAttribute('href'))).filter(Boolean);
  function closeMenu() { nav.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false'); }
  toggle.addEventListener('click', () => { const open = nav.classList.toggle('open'); toggle.setAttribute('aria-expanded', String(open)); });
  links.forEach(a => a.addEventListener('click', closeMenu));
  document.getElementById('print-button').addEventListener('click', () => window.print());
  let pending = false;
  function updateActive() {
    const threshold = window.innerHeight * .30;
    const current = sections.filter(s => s.getBoundingClientRect().top <= threshold).at(-1) || sections[0];
    links.forEach(a => { const active = a.hash === '#' + current.id; a.classList.toggle('active', active); if (active) a.setAttribute('aria-current','location'); else a.removeAttribute('aria-current'); });
    const progress = document.getElementById('reading-progress-bar');
    if (progress) progress.style.transform = `scaleX(${Math.min(1, window.scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight))})`;
    pending = false;
  }
  window.addEventListener('scroll', () => { if (!pending) { pending = true; requestAnimationFrame(updateActive); } }, {passive:true});
  updateActive();
  const explorer=document.getElementById('shot-explorer');
  if (explorer) {
    const controls=explorer.querySelector('.shot-controls');
    const game=document.getElementById('shot-game'), zone=document.getElementById('shot-zone'), outcome=document.getElementById('shot-outcome');
    const marks=[...explorer.querySelectorAll('.shot-event')];
    const events=marks.map(el=>({el,game:el.dataset.gameId,event:el.dataset.eventId,zone:el.dataset.zone,made:Number(el.dataset.made),date:el.dataset.date,period:el.dataset.period,clock:el.dataset.clock}));
    const list=document.getElementById('shot-event-list'),detail=document.getElementById('shot-detail');
    let visible=[],page=0,selected=null;const pageSize=12;
    const motion=matchMedia('(prefers-reduced-motion: reduce)');
    const play=document.getElementById('shot-play'),stop=document.getElementById('shot-stop'),speed=document.getElementById('shot-speed');
    const progress=document.getElementById('shot-play-progress'),focus=explorer.querySelector('.shot-focus');
    let playing=false,timer=null,replay=[],cursor=0,entryFrame=null,entryPending=true;
    let stage=null,research=null;
    const zoneLabel=()=>zone.selectedOptions[0].textContent;
    function clearFocus() {
      focus.querySelectorAll('circle').forEach(el=>el.getAnimations().forEach(a=>a.cancel()));
      focus.setAttribute('hidden','');
    }
    function spotlight(row) {
      clearFocus();focus.removeAttribute('hidden');
      focus.setAttribute('stroke',row.made?'#26796f':'#ba5865');
      focus.querySelectorAll('circle').forEach(el=>{el.setAttribute('cx',row.el.dataset.svgX);el.setAttribute('cy',row.el.dataset.svgY);});
      if(!motion.matches)focus.querySelector('.shot-focus-ring').animate([
        {opacity:.9,transform:'scale(.5)'},{opacity:0,transform:'scale(2.3)'}
      ],{duration:650,easing:'cubic-bezier(.16,.65,.3,1)',fill:'forwards'});
    }
    function animateEntry() {
      if(entryFrame!==null)cancelAnimationFrame(entryFrame);
      marks.forEach(el=>el.classList.remove('shot-enter'));
      if(motion.matches||document.hidden)return;
      entryFrame=requestAnimationFrame(()=>{
        entryFrame=null;visible.forEach((row,i)=>{row.el.dataset.beat=String(i%12);row.el.classList.add('shot-enter');});
      });
    }
    explorer.addEventListener('animationend',e=>{
      if(e.animationName==='shot-pop')e.target.closest('.shot-event')?.classList.remove('shot-enter');
    });
    function pauseReplay() {
      clearTimeout(timer);timer=null;playing=false;play.setAttribute('aria-pressed','false');
      stage?.pause();
      play.textContent=cursor&&cursor<replay.length?'继续点亮':'逐次点亮';
      if(cursor&&cursor<replay.length)progress.textContent='已暂停 · '+cursor+' / '+replay.length;
    }
    function restoreOverview() {
      pauseReplay();replay=[];cursor=0;explorer.classList.remove('shot-replaying');
      marks.forEach(el=>el.classList.remove('shot-replayed','shot-enter'));
      if(entryFrame!==null){cancelAnimationFrame(entryFrame);entryFrame=null;}
      if(selected)selected.el.classList.remove('shot-selected');selected=null;
      list.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed','false'));
      clearFocus();detail.textContent='请选择一个事件。';stop.disabled=true;
      play.textContent='逐次点亮';progress.textContent='等待回放';
      stage?.clear();
    }
    function orderEvents(a,b) {
      const seconds=r=>{const [m,s]=r.clock.split(':').map(Number);return m*60+s;};
      return a.date.localeCompare(b.date)||a.game.localeCompare(b.game)||Number(a.period)-Number(b.period)||seconds(b)-seconds(a)||Number(a.event)-Number(b.event);
    }
    function stepReplay() {
      if(!playing)return;
      const row=replay[cursor++];row.el.classList.add('shot-replayed');choose(row);
      page=Math.floor(visible.indexOf(row)/pageSize);drawList();
      progress.textContent='点亮 '+cursor+' / '+replay.length;
      stage?.progress(replay.slice(0,cursor),replay.length);
      if(cursor>=replay.length){pauseReplay();play.textContent='重新点亮';progress.textContent='完成 · '+cursor+' / '+replay.length;}
      else timer=setTimeout(stepReplay,Number(speed.value));
    }
    play.addEventListener('click',()=>{
      if(playing){pauseReplay();return;}
      if(!visible.length)return;
      if(!replay.length||cursor>=replay.length){restoreOverview();replay=[...visible].sort(orderEvents);}
      playing=true;explorer.classList.add('shot-replaying');stop.disabled=false;
      play.textContent='暂停点亮';play.setAttribute('aria-pressed','true');stepReplay();
    });
    stop.addEventListener('click',()=>{restoreOverview();drawList();});
    speed.addEventListener('change',()=>{if(playing){clearTimeout(timer);timer=setTimeout(stepReplay,Number(speed.value));}});
    document.addEventListener('visibilitychange',()=>{if(document.hidden)pauseReplay();});
    window.addEventListener('beforeprint',restoreOverview);
    motion.addEventListener('change',()=>{
      pauseReplay();marks.forEach(el=>el.classList.remove('shot-enter'));clearFocus();
      if(selected)spotlight(selected);
    });
    if('IntersectionObserver' in window){
      const shotObserver=new IntersectionObserver(entries=>entries.forEach(entry=>{
        if(entry.isIntersecting&&entryPending){entryPending=false;animateEntry();}
        if(!entry.isIntersecting)pauseReplay();
      }),{threshold:.04});shotObserver.observe(explorer.querySelector('.explorer-court'));
    }
    function choose(row) {
      if(selected)selected.el.classList.remove('shot-selected');
      selected=row;row.el.classList.add('shot-selected');
      row.el.classList.remove('shot-enter');spotlight(row);
      stage?.select(row);
      list.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.eventKey===row.game+'/'+row.event)));
      const d=row.el.dataset;
      detail.replaceChildren();
      const heading=document.createElement('strong');heading.textContent=row.date+' · '+(row.made?'命中':'未中');detail.append(heading);
      for(const text of ['比赛 '+row.game+' / 事件 '+row.event,'第'+row.period+'节 · 剩余 '+row.clock,'官方区域：'+d.originalZone,'官方类型：'+d.originalType,'坐标 ('+d.x+', '+d.y+')，单位0.1英尺']) {
        const p=document.createElement('p');p.textContent=text;detail.append(p);
      }
      if(row.zone==='UNRESOLVED'){const p=document.createElement('p');p.textContent='区域与两/三分类型冲突，保留原值，单列处理。';detail.append(p);}
    }
    function drawList() {
      list.replaceChildren();
      visible.slice(page*pageSize,(page+1)*pageSize).forEach(row=>{
        const button=document.createElement('button');button.type='button';button.className='shot-event-button';
        button.dataset.eventKey=row.game+'/'+row.event;button.setAttribute('aria-pressed',String(selected===row));
        button.textContent=row.date+' · '+row.clock+' · '+(row.made?'命中':'未中')+' · #'+row.event;
        button.addEventListener('click',()=>{pauseReplay();choose(row);});list.append(button);
      });
      const pages=Math.ceil(visible.length/pageSize);
      document.getElementById('shot-page').textContent=visible.length?'第 '+(page+1)+' / '+pages+' 页':'没有匹配事件';
      document.getElementById('shot-prev').disabled=page===0;
      document.getElementById('shot-next').disabled=page+1>=pages;
    }
    function filterShots() {
      restoreOverview();
      const base=events.filter(r=>game.value==='all'||r.game===game.value);
      const sample=base.filter(r=>zone.value==='all'||r.zone===zone.value||(zone.value==='3PT'&&r.el.dataset.three==='1')||(zone.value==='2PT'&&r.el.dataset.three==='0'));
      const hits=sample.reduce((n,r)=>n+r.made,0);
      visible=sample.filter(r=>outcome.value==='all'||String(r.made)===outcome.value).sort((a,b)=>b.date.localeCompare(a.date)||Number(b.event)-Number(a.event));
      const kept=new Set(visible.map(r=>r.el));events.forEach(r=>{if(kept.has(r.el))r.el.removeAttribute('hidden');else r.el.setAttribute('hidden','');});
      document.getElementById('shot-fga').textContent=sample.length;
      document.getElementById('shot-fgm').textContent=hits;
      document.getElementById('shot-pct').textContent=sample.length?(hits/sample.length*100).toFixed(1)+'%':'N/A';
      document.getElementById('shot-visible').textContent=visible.length;
      document.getElementById('shot-scope').textContent=game.selectedOptions[0].textContent+' / '+zoneLabel()+'；命中率分母为这组样本全部出手，显示结果筛选只改变图上事件。'+(sample.length<30?' 少样本：只作描述，不判断稳定能力。':'');
      if(selected){selected.el.classList.remove('shot-selected');selected=null;}detail.textContent='请选择一个事件。';
      page=0;drawList();
      play.disabled=!visible.length;
      stage?.setRows(visible);
      research?.update(base,sample,zone.value);
      entryPending=true;
      const rect=explorer.querySelector('.explorer-court').getBoundingClientRect();
      if(rect.top<innerHeight&&rect.bottom>0){entryPending=false;animateEntry();}
    }
    [game,zone,outcome].forEach(el=>el.addEventListener('change',filterShots));
    explorer.querySelector('.shot-flat').addEventListener('click',e=>{
      const svg=e.target.closest('svg');if(!svg)return;
      const matrix=svg.getScreenCTM();if(!matrix)return;
      const hits=visible.map(row=>{const p=new DOMPoint(Number(row.el.dataset.svgX),Number(row.el.dataset.svgY)).matrixTransform(matrix);return {row,d:Math.hypot(e.clientX-p.x,e.clientY-p.y)};}).filter(h=>h.d<12).sort((a,b)=>a.d-b.d);
      if(hits.length)research?.candidates(hits.map(h=>h.row));
    });
    document.getElementById('shot-reset').addEventListener('click',()=>{game.value='all';zone.value='all';outcome.value='all';filterShots();});
    document.getElementById('shot-prev').addEventListener('click',()=>{page=Math.max(0,page-1);drawList();});
    document.getElementById('shot-next').addEventListener('click',()=>{page++;drawList();});
    research=window.createShotResearch?.(explorer,{
      applyZone:(value,reset)=>{if(reset){game.value='all';outcome.value='all';}zone.value=value;filterShots();},
      pick:row=>{pauseReplay();choose(row);page=Math.max(0,Math.floor(visible.indexOf(row)/pageSize));drawList();},pause:pauseReplay
    });
    stage=window.createShotStage?.(explorer,row=>{research?.clearCandidates();pauseReplay();choose(row);},rows=>research?.candidates(rows));
    controls.hidden=false;explorer.querySelector('.explorer-events').hidden=false;explorer.querySelector('.shot-playback').hidden=false;filterShots();
  }
  window.addEventListener('resize', updateActive, {passive:true});
  const search = document.getElementById('source-search');
  function filterSources() {
    if (!search) return;
    const query = search.value.trim().toLowerCase();
    const cards = [...document.querySelectorAll('.source-card')];
    let found = 0;
    cards.forEach(card => { card.hidden = !card.dataset.sourceSearch.includes(query); if (!card.hidden) found++; });
    document.querySelectorAll('.source-group').forEach(group => group.hidden = !group.querySelector('.source-card:not([hidden])'));
    document.getElementById('source-count').textContent = query ? `找到 ${found} 个来源；清空搜索可恢复全部。` : '按研究问题分组；点击来源卡查看口径、查阅时间及原始链接。';
  }
  if (search) search.addEventListener('input', filterSources);
  const mediaButtons = [...document.querySelectorAll('.media-toggle')];
  function animateMedia(button, playing) {
    const picture = button.closest('.court-media').querySelector('img');
    picture.src = playing ? picture.dataset.animatedSrc : picture.dataset.posterSrc;
    button.setAttribute('aria-pressed', String(playing));
    button.textContent = playing ? button.dataset.pauseLabel : button.dataset.playLabel;
  }
  mediaButtons.forEach(button => button.addEventListener('click', () => animateMedia(button, button.getAttribute('aria-pressed') !== 'true')));
  document.addEventListener('visibilitychange', () => { if (document.hidden) mediaButtons.forEach(button => animateMedia(button, false)); });
  if ('IntersectionObserver' in window) {
    const mediaObserver = new IntersectionObserver(entries => entries.forEach(entry => {
      if (!entry.isIntersecting) { const button = entry.target.querySelector('.media-toggle'); if (button) animateMedia(button, false); }
    }));
    document.querySelectorAll('.court-media').forEach(figure => mediaObserver.observe(figure));
    if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
      document.body.classList.add('motion-enabled');
      const reveal = new IntersectionObserver(entries => entries.forEach(entry => {
        if (entry.isIntersecting) { entry.target.classList.add('is-visible'); reveal.unobserve(entry.target); }
      }), {rootMargin:'0px 0px 50px 0px',threshold:.04});
      document.querySelectorAll('.module-head,.figure,.court-media,.panel,.strategy').forEach(el => { el.classList.add('reveal'); reveal.observe(el); });
    }
  }
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeMenu();
    if (!e.altKey || !['ArrowUp','ArrowDown'].includes(e.key) || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) || document.activeElement.isContentEditable) return;
    const active = Math.max(0, links.findIndex(a => a.classList.contains('active')));
    const next = Math.min(sections.length-1,Math.max(0,active + (e.key === 'ArrowDown' ? 1 : -1)));
    e.preventDefault(); sections[next].scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
  });
  function revealTarget() {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { return; }
    const target = document.getElementById(id);
    if (target) {
      if (target.classList.contains('source-card') && search && target.hidden) { search.value=''; filterSources(); }
      let ancestor = target;
      while (ancestor) { if (ancestor.tagName === 'DETAILS') ancestor.open=true; ancestor=ancestor.parentElement; }
      requestAnimationFrame(() => target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth', block:'start'}));
    }
  }
  window.addEventListener('hashchange', revealTarget);
  revealTarget();
  let opened = [];
  window.addEventListener('beforeprint', () => { mediaButtons.forEach(button=>animateMedia(button,false)); opened = [...document.querySelectorAll('details:not([open])')]; opened.forEach(d => d.open = true); });
  window.addEventListener('afterprint', () => { opened.forEach(d => d.open = false); opened = []; });
})();
