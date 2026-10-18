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
      const panel=panels[active], shape=panel.querySelector('.radar-shape');
      if(shape) {
        const length=shape.getTotalLength();
        shape.animate([{strokeDasharray:length,strokeDashoffset:length,fillOpacity:0},
                       {strokeDasharray:length,strokeDashoffset:0,fillOpacity:.20}],
                      {duration:1100,easing:'cubic-bezier(.16,1,.3,1)'});
      }
      panel.querySelectorAll('.radar-marker').forEach((el,i)=>el.animate([{opacity:0},{opacity:1}],
        {duration:400,delay:i*65,easing:'ease-out'}));
      panel.querySelectorAll('.is-league-leader .radar-axis-value').forEach(el=>el.animate(
        [{opacity:.4},{opacity:1}],{duration:1000,iterations:1,easing:'ease-out'}));
      panel.querySelectorAll('.is-league-leader .radar-marker-halo').forEach(el=>el.animate(
        [{r:'5px',opacity:0},{r:'17px',opacity:.9,offset:.4},{r:'24px',opacity:0}],
        {duration:1400,iterations:1,easing:'ease-out'}));
      panel.querySelectorAll('.radar-leader-strip').forEach(el=>el.animate(
        [{boxShadow:'0 0 0px #f3ce5d00'},{boxShadow:'0 0 24px #f3ce5d60',offset:.4},
         {boxShadow:'0 0 0px #f3ce5d00'}],{duration:1500,iterations:1,easing:'ease-out'}));
      panel.querySelectorAll('.radar-award-score,.radar-award-rank').forEach(el=>el.animate(
        [{opacity:0,transform:'translateY(14px)'},{opacity:1,transform:'translateY(0)'}],
        {duration:850,easing:'cubic-bezier(.16,1,.3,1)'}));
      panel.querySelectorAll('.radar-award-shine').forEach(el=>el.animate(
        [{opacity:0,transform:'translateX(0) skewX(-22deg)'},
         {opacity:.8,offset:.35},{opacity:0,transform:'translateX(460%) skewX(-22deg)'}],
        {duration:1200,delay:180,easing:'ease-in-out'}));
      const sweep=studio.querySelector('.radar-light-sweep');
      if(sweep)sweep.animate([
        {opacity:0,transform:'translateX(-180%) skewX(-18deg)'},
        {opacity:1,offset:.42},{opacity:0,transform:'translateX(260%) skewX(-18deg)'}],
        {duration:1300,iterations:1,easing:'ease-in-out'});
      const portrait=studio.querySelector('.radar-portrait img');
      if(portrait)portrait.animate([{transform:'scale(1.055)'},{transform:'scale(1)'}],
        {duration:1400,easing:'cubic-bezier(.16,1,.3,1)'});
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
      }
      axes.forEach((axis,i)=>{
        axis.addEventListener('click',()=>select(axis));
        axis.addEventListener('focus',()=>select(axis));
        axis.addEventListener('keydown',e=>{
          if(e.key==='Enter'||e.key===' '){e.preventDefault();select(axis);}
          if(e.key==='ArrowRight'||e.key==='ArrowDown'){e.preventDefault();axes[(i+1)%axes.length].focus();}
          if(e.key==='ArrowLeft'||e.key==='ArrowUp'){e.preventDefault();axes[(i+axes.length-1)%axes.length].focus();}
        });
      });
    });
    studio.querySelector('.radar-replay').addEventListener('click',()=>{entered=true;animate();});
    motion.addEventListener('change',()=>{if(motion.matches)cancel();});
    document.addEventListener('visibilitychange',()=>{if(document.hidden)cancel();});
    const requested=panels.findIndex(panel=>'#'+panel.id===location.hash);
    const highlighted=panels.findIndex(panel=>panel.querySelector('.radar-award'));
    activate(requested>=0?requested:Math.max(0,highlighted));
    const observer=new IntersectionObserver(entries=>{
      if(entries.some(entry=>entry.isIntersecting)){entered=true;animate();observer.disconnect();}
    },{threshold:.18});
    observer.observe(studio);
  });
})();
