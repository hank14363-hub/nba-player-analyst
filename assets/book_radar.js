(() => {
  'use strict';
  document.querySelectorAll('.radar-studio').forEach(studio => {
    const tabs=[...studio.querySelectorAll('[role="tab"]')];
    const panels=[...studio.querySelectorAll('[role="tabpanel"]')];
    const motion=matchMedia('(prefers-reduced-motion: reduce)');
    let active=0,entered=false;
    const cancel=()=>studio.querySelectorAll('*').forEach(el=>el.getAnimations().forEach(a=>a.cancel()));
    function animate() {
      cancel();
      if(motion.matches||document.hidden)return;
      const panel=panels[active],shape=panel.querySelector('.radar-shape');
      if(shape){const length=shape.getTotalLength();shape.animate([
        {strokeDasharray:length,strokeDashoffset:length},
        {strokeDasharray:length,strokeDashoffset:0}],{duration:1100,easing:'cubic-bezier(.16,1,.3,1)'});}
      const lit=panel.querySelector('.radar-lit');
      if(lit)lit.animate([{opacity:0},{opacity:1}],{duration:1000,easing:'ease-out'});
      panel.querySelectorAll('.radar-marker').forEach((el,i)=>el.animate([{opacity:0},{opacity:1}],
        {duration:350,delay:i*55,easing:'ease-out'}));
      panel.querySelectorAll('.radar-award').forEach(el=>el.animate([
        {opacity:.4,transform:'translateY(8px)'},{opacity:1,transform:'translateY(0)'}],
        {duration:850,easing:'ease-out'}));
      panel.querySelectorAll('.radar-award-shine').forEach(el=>el.animate([
        {opacity:0,transform:'translateX(0) skewX(-22deg)'},
        {opacity:.7,offset:.35},{opacity:0,transform:'translateX(460%) skewX(-22deg)'}],
        {duration:1200,delay:150,easing:'ease-in-out'}));
      const sweep=studio.querySelector('.radar-light-sweep');
      if(sweep)sweep.animate([{opacity:0,transform:'translateX(-180%) skewX(-18deg)'},
        {opacity:1,offset:.42},{opacity:0,transform:'translateX(310%) skewX(-18deg)'}],
        {duration:1300,easing:'ease-in-out'});
    }
    function activate(index,focus=false) {
      active=index;
      tabs.forEach((tab,i)=>{tab.setAttribute('aria-selected',String(i===index));tab.tabIndex=i===index?0:-1;});
      panels.forEach((panel,i)=>panel.hidden=i!==index);
      if(focus)tabs[index].focus();
      if(entered)animate();
    }
    tabs.forEach((tab,i)=>{
      tab.addEventListener('click',()=>activate(i));
      tab.addEventListener('keydown',e=>{
        let next=null;
        if(e.key==='ArrowRight')next=(i+1)%tabs.length;
        if(e.key==='ArrowLeft')next=(i+tabs.length-1)%tabs.length;
        if(e.key==='Home')next=0;
        if(e.key==='End')next=tabs.length-1;
        if(next!==null){e.preventDefault();activate(next,true);}
      });
    });
    panels.forEach(panel=>{
      const axes=[...panel.querySelectorAll('.radar-axis')];
      function select(axis) {
        axes.forEach(el=>el.classList.toggle('is-selected',el===axis));
        panel.querySelector('.radar-focus-label').textContent=axis.dataset.axisLabel;
        panel.querySelector('.radar-focus-raw').textContent=axis.dataset.axisRaw;
        panel.querySelector('.radar-focus-percentile').textContent=axis.dataset.axisPercentile;
        panel.querySelector('.radar-focus-note').textContent=axis.dataset.axisNote;
        const container=panel.querySelector('.radar-focus-rings');
        const rings=JSON.parse(axis.dataset.axisRings),p=Number(axis.dataset.axisPercentile.slice(1));
        container.replaceChildren();
        if(!rings.length){const span=document.createElement('span');span.className='rings-missing';
          span.textContent='环上分位参考值缺失；需从保留原始总体重新计算，不作估填。';container.append(span);}
        rings.forEach(ring=>{const span=document.createElement('span'),label=document.createElement('small'),value=document.createElement('b');
          if(p>=ring.level)span.className='is-reached';label.textContent='P'+ring.level;value.textContent=ring.display;
          span.append(label,value);container.append(span);});
      }
      axes.forEach((axis,i)=>{
        axis.addEventListener('click',()=>select(axis));
        axis.addEventListener('focus',()=>select(axis));
        axis.addEventListener('keydown',e=>{
          let next=null;
          if(e.key==='Enter'||e.key===' '){e.preventDefault();select(axis);}
          if(e.key==='ArrowRight'||e.key==='ArrowDown')next=(i+1)%axes.length;
          if(e.key==='ArrowLeft'||e.key==='ArrowUp')next=(i+axes.length-1)%axes.length;
          if(e.key==='Home')next=0;
          if(e.key==='End')next=axes.length-1;
          if(next!==null){e.preventDefault();axes[next].focus();}
        });
      });
      panel.querySelectorAll('.radar-table-axis').forEach(button=>button.addEventListener('click',()=>select(axes[Number(button.dataset.axisIndex)])));
      if(axes.length)select(axes[Number(panel.dataset.initialAxis)||0]);
    });
    studio.querySelector('.radar-replay').addEventListener('click',()=>{entered=true;animate();});
    const zoom=studio.querySelector('.radar-zoom');
    zoom.addEventListener('click',()=>{
      const enlarged=studio.querySelector('.radar-deck').classList.toggle('is-zoomed');
      zoom.setAttribute('aria-pressed',String(enlarged));zoom.textContent=enlarged?'恢复全图':'放大罗盘';
      panels.forEach(panel=>{const viewport=panel.querySelector('.radar-chart-viewport');
        viewport.scrollLeft=enlarged?(viewport.scrollWidth-viewport.clientWidth)/2:0;});
    });
    const ringToggle=studio.querySelector('.radar-ring-toggle');
    ringToggle.addEventListener('click',()=>{
      const hidden=studio.querySelector('.radar-deck').classList.toggle('hide-ring-ticks');
      ringToggle.setAttribute('aria-pressed',String(!hidden));
      ringToggle.textContent=hidden?'环上刻度：关':'环上刻度：开';
    });
    studio.querySelector('.radar-download').addEventListener('click',()=>{
      const copy=panels[active].querySelector('svg').cloneNode(true);
      copy.querySelectorAll('.radar-axis').forEach(axis=>{axis.removeAttribute('tabindex');axis.removeAttribute('role');});
      if(studio.querySelector('.hide-ring-ticks'))copy.querySelectorAll('.radar-ring-tick').forEach(tick=>tick.remove());
      const data=new XMLSerializer().serializeToString(copy);
      const url=URL.createObjectURL(new Blob([data],{type:'image/svg+xml;charset=utf-8'}));
      const link=document.createElement('a');link.href=url;link.download=panels[active].id+'.svg';
      document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
    motion.addEventListener('change',()=>{if(motion.matches)cancel();});
    document.addEventListener('visibilitychange',()=>{if(document.hidden)cancel();});
    const requested=panels.findIndex(panel=>'#'+panel.id===location.hash);
    const highlighted=panels.findIndex(panel=>panel.querySelector('.radar-award'));
    activate(requested>=0?requested:Math.max(0,highlighted));
    if('IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>{
      if(entries.some(entry=>entry.isIntersecting)){entered=true;animate();observer.disconnect();}
    },{threshold:.1});observer.observe(studio);}
  });
})();
