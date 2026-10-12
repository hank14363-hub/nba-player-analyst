/* Perspective is a presentation of known positions. Arcs are decorative links,
   never measured ball trajectories. No external code, textures or requests. */
window.createShotStage = function (explorer, onChoose, onCandidates) {
  'use strict';
  const host=explorer.querySelector('.shot-stage'),canvas=host.querySelector('canvas');
  const ctx=canvas.getContext('2d');if(!ctx)return null;
  const motion=matchMedia('(prefers-reduced-motion: reduce)');
  const flat=explorer.querySelector('.shot-flat'),layout=explorer.querySelector('.explorer-layout');
  const modeButtons=[...explorer.querySelectorAll('[data-shot-view]')];
  const counter=host.querySelector('.stage-count'),fill=host.querySelector('.stage-progress-fill');
  const status=host.querySelector('.stage-event-label'),light=explorer.querySelector('#shot-lights');
  const extent=explorer.querySelector('#shot-extent'),coverage=host.querySelector('.stage-coverage');
  let extentMode='focus';
  let rows=[],selected=null,played=new Set(),sequence=false,count=0,shown=true,inView=false;
  let frame=null,arcs=[],entryStart=0,entryDuration=0,W=900,H=570,positions=[];
  let floorCache=null;
  const key=r=>r.game+'/'+r.event;
  const name=document.querySelector('.player-name')?.textContent.trim()||'PLAYER';
  host.querySelector('.stage-player').textContent=name;
  function project(x,y,z=0){
    // Actual NBA coordinates in feet, with the far baseline at y=-5.25.
    const depth=(y+5.25)/(extentMode==='focus'?47:94),scale=1-(extentMode==='focus'?.16:.34)*depth;
    return {x:W/2+x/25*(W*.44)*scale,y:H*(.88-.74*depth)-z*H*.012*scale,scale};
  }
  const inExtent=row=>extentMode==='full'||Number(row.el.dataset.y)<=417.5;
  function setExtent(value){
    extentMode=value;extent.value=value;arcs=[];floorCache=null;resize();
  }
  function poly(points,fillColor,strokeColor,width=1){
    ctx.beginPath();points.forEach((v,i)=>{const p=project(...v);if(i)ctx.lineTo(p.x,p.y);else ctx.moveTo(p.x,p.y);});ctx.closePath();
    if(fillColor){ctx.fillStyle=fillColor;ctx.fill();}if(strokeColor){ctx.strokeStyle=strokeColor;ctx.lineWidth=width;ctx.stroke();}
  }
  function line(points,color,width=1,dashed=false){
    ctx.beginPath();points.forEach((v,i)=>{const p=project(...v);if(i)ctx.lineTo(p.x,p.y);else ctx.moveTo(p.x,p.y);});
    ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dashed?[5,5]:[]);ctx.stroke();ctx.setLineDash([]);
  }
  function arcWorld(cx,cy,r,start,end,color,width=1){
    const points=[];for(let i=0;i<=64;i++){const a=start+(end-start)*i/64;points.push([cx+r*Math.cos(a),cy+r*Math.sin(a)]);}
    line(points,color,width);
  }
  function floor(){
    ctx.clearRect(0,0,W,H);
    const backdrop=ctx.createLinearGradient(0,0,0,H);backdrop.addColorStop(0,'#101b35');backdrop.addColorStop(.65,'#14213e');backdrop.addColorStop(1,'#090f20');
    ctx.fillStyle=backdrop;ctx.fillRect(0,0,W,H);
    const glow=ctx.createRadialGradient(W/2,H*.25,0,W/2,H*.25,W*.55);
    glow.addColorStop(0,'rgba(70,112,190,.38)');glow.addColorStop(1,'rgba(30,53,101,0)');ctx.fillStyle=glow;ctx.fillRect(0,0,W,H);
    const end=extentMode==='focus'?41.75:88.75;
    poly([[-25,-5.25],[25,-5.25],[25,end],[-25,end]],'#b5a080','#7e97be',1.4);
    // Deterministic drawn maple boards, not a downloaded photographic texture.
    for(let x=-25;x<25;x+=1.4){
      const shade=Math.floor((x+25)/1.4)%3;
      poly([[x,-5.25],[Math.min(25,x+1.4),-5.25],[Math.min(25,x+1.4),end],[x,end]],
           ['#bbab91','#b3a086','#c0af92'][shade],null);
      line([[x,-5.25],[x,end]],'rgba(65,50,34,.12)',.5);
      for(let y=-5.25+((shade*7)%14);y<end;y+=17){line([[x,y],[Math.min(x+1.4,25),y]],'rgba(65,50,34,.17)',.6);}
    }
    const court='#2d4564';
    poly([[-8,-5.25],[8,-5.25],[8,13.75],[-8,13.75]],'#718697',court,1.2);
    if(extentMode==='full')poly([[-8,88.75],[8,88.75],[8,69.75],[-8,69.75]],'#718697',court,1.2);
    line([[-25,41.75],[25,41.75]],court,1.3);
    arcWorld(0,41.75,6,extentMode==='focus'?Math.PI:0,Math.PI*2,court,1.2);
    arcWorld(0,13.75,6,0,Math.PI,court,1.2);
    arcWorld(0,13.75,6,Math.PI,Math.PI*2,'#637183',.8);
    const angle=Math.acos(22/23.75),cornerY=23.75*Math.sin(angle);
    line([[-22,-5.25],[-22,cornerY]],court,1.3);line([[22,-5.25],[22,cornerY]],court,1.3);
    arcWorld(0,0,23.75,angle,Math.PI-angle,court,1.3);
    arcWorld(0,0,4,0,Math.PI,court,1);
    const nearAngle=Math.acos(22/23.75);
    if(extentMode==='full'){
      line([[-22,88.75],[-22,83.5-cornerY]],court,1.3);line([[22,88.75],[22,83.5-cornerY]],court,1.3);
      arcWorld(0,83.5,23.75,Math.PI+nearAngle,Math.PI*2-nearAngle,court,1.3);
      arcWorld(0,69.75,6,Math.PI,Math.PI*2,court,1.2);
    }
    const logo=project(0,41.75);ctx.save();ctx.translate(logo.x,logo.y);ctx.scale(1,.48);
    ctx.beginPath();ctx.arc(0,0,W*.047,0,Math.PI*2);ctx.fillStyle='#263e67';ctx.fill();ctx.strokeStyle='#d67a89';ctx.lineWidth=2;ctx.stroke();
    ctx.fillStyle='#d8e2f4';ctx.font=`600 ${W*.016}px Arial`;ctx.textAlign='center';ctx.fillText('NBA',0,W*.005);ctx.restore();
    const baseline=project(0,-3.5);ctx.fillStyle='#2c4365';ctx.font=`700 ${W*.018}px Arial`;ctx.textAlign='center';ctx.fillText('PLAYER RESEARCH',baseline.x,baseline.y+H*.025);
    floorCache=ctx.getImageData(0,0,canvas.width,canvas.height);
  }
  function hoop(){
    const p=project(0,0,10),ground=project(0,-3.3),board=project(0,-1.25,11.5);
    // A stylized display basket; no additional shot height data is inferred.
    ctx.lineCap='round';ctx.strokeStyle='#5d789f';ctx.lineWidth=5;
    ctx.beginPath();ctx.moveTo(ground.x,ground.y);ctx.lineTo(board.x,board.y+7);ctx.stroke();
    ctx.fillStyle='rgba(176,204,240,.10)';ctx.strokeStyle='#b7cbea';ctx.lineWidth=1.6;
    const bw=W*.070,bh=H*.056;ctx.fillRect(board.x-bw/2,board.y-bh,bw,bh);ctx.strokeRect(board.x-bw/2,board.y-bh,bw,bh);
    ctx.strokeRect(board.x-bw*.15,board.y-bh*.53,bw*.30,bh*.45);
    ctx.beginPath();ctx.ellipse(p.x,p.y,W*.012,H*.004,0,0,Math.PI*2);ctx.strokeStyle='#ebbd81';ctx.lineWidth=2;ctx.stroke();
    ctx.strokeStyle='rgba(231,238,249,.55)';ctx.lineWidth=.7;
    for(let i=-2;i<=2;i++){ctx.beginPath();ctx.moveTo(p.x+i*3,p.y+2);ctx.lineTo(p.x+i*2,p.y+10);ctx.stroke();}
  }
  function dot(p,color,alpha,radius,selectedPoint=false){
    ctx.globalAlpha=alpha;ctx.fillStyle=color;ctx.beginPath();ctx.arc(p.x,p.y,radius,0,Math.PI*2);ctx.fill();
    if(selectedPoint){ctx.strokeStyle='#f8e9c9';ctx.lineWidth=1.6;ctx.beginPath();ctx.arc(p.x,p.y,radius+6,0,Math.PI*2);ctx.stroke();}
    ctx.globalAlpha=1;
  }
  function draw(now){
    frame=null;if(!shown||document.hidden)return;
    if(!floorCache)floor();else ctx.putImageData(floorCache,0,0);
    const elapsed=now-entryStart,entrance=entryDuration>0&&elapsed<entryDuration;
    if(entryDuration&&!entrance)entryDuration=0;
    positions=[];
    rows.forEach((row,i)=>{
      if(!inExtent(row))return;
      const d=row.el.dataset,p=project(Number(d.x)/10,Number(d.y)/10);
      positions.push({row,x:p.x,y:p.y});
      const done=!sequence||played.has(key(row)),active=selected===row;
      const phase=entrance?Math.max(0,Math.min(1,(elapsed-i/Math.max(1,rows.length)*900)/350)):1;
      const color=row.made?'#b5e7ed':'#b94470';
      if(light.checked&&done){ctx.shadowColor=row.made?color:'#ed98b7';ctx.shadowBlur=active?14:4;}
      const radius=Math.max(W<500?2.0:1.65,p.scale*2.3),alpha=(done?.9:.13)*phase;
      if(row.made){dot(p,color,alpha,radius,active);}
      else {
        ctx.globalAlpha=alpha;ctx.strokeStyle=active?'#f6c5d5':color;ctx.lineWidth=1.35;
        ctx.beginPath();ctx.moveTo(p.x-radius,p.y-radius);ctx.lineTo(p.x+radius,p.y+radius);
        ctx.moveTo(p.x+radius,p.y-radius);ctx.lineTo(p.x-radius,p.y+radius);ctx.stroke();ctx.globalAlpha=1;
        if(active){ctx.strokeStyle='#f8e9c9';ctx.lineWidth=1.6;ctx.beginPath();ctx.arc(p.x,p.y,radius+6,0,Math.PI*2);ctx.stroke();}
      }
      ctx.shadowBlur=0;
    });
    const target=project(0,0,10);
    arcs=arcs.filter(a=>now-a.start<700);
    if(!motion.matches&&light.checked){
      arcs.forEach(a=>{
        const d=a.row.el.dataset,p=project(Number(d.x)/10,Number(d.y)/10);
        const t=(now-a.start)/700,color=a.row.made?'#d0f3ff':'#e8aabd';
        // A decorative Bezier connection. Its arc height is visual, not a metric.
        const lift=Math.min(H*.32,Math.abs(p.y-target.y)*.8+H*.12);
        const c1={x:p.x,y:p.y-lift},c2={x:target.x,y:target.y-lift*.30};
        ctx.globalAlpha=Math.max(0,(1-t)*.9);ctx.beginPath();ctx.moveTo(p.x,p.y);
        ctx.bezierCurveTo(c1.x,c1.y,c2.x,c2.y,target.x,target.y);ctx.strokeStyle=color;ctx.lineWidth=1.3;ctx.shadowColor=color;ctx.shadowBlur=9;ctx.stroke();
        const b=1-t,bx=b*b*b*p.x+3*b*b*t*c1.x+3*b*t*t*c2.x+t*t*t*target.x,by=b*b*b*p.y+3*b*b*t*c1.y+3*b*t*t*c2.y+t*t*t*target.y;
        dot({x:bx,y:by},color,.95,2.8);ctx.shadowBlur=0;ctx.globalAlpha=1;
      });
    }
    hoop();
    canvas.dataset.renderedCount=String(positions.length);canvas.dataset.totalCount=String(rows.length);canvas.dataset.extent=extentMode;canvas.dataset.progress=String(count);
    canvas.dataset.offviewCount=String(rows.length-positions.length);
    const back=rows.filter(r=>r.zone==='BACK').length;
    coverage.textContent=(extentMode==='focus'?'进攻半场':'完整全场')+' · 视窗内 '+positions.length+' / 当前显示 '+rows.length+'；视窗外 '+(rows.length-positions.length)+' 次（后场共 '+back+' 次）。'+(rows.length>positions.length?' 切换全场可查看全部；列表与统计仍含视窗外事件。':'');
    canvas.dataset.outsideCount=String(positions.filter(p=>p.x<0||p.x>W||p.y<0||p.y>H).length);
    canvas.dataset.activeEvent=selected?key(selected):'';
    canvas.dataset.arcCount=String(motion.matches||!light.checked?0:arcs.length);
    if(inView&&(entrance||arcs.length)&&!motion.matches)request();
  }
  function request(){if(shown&&!document.hidden&&frame===null)frame=requestAnimationFrame(draw);}
  function resize(){
    const bounds=host.getBoundingClientRect();if(!bounds.width)return;
    W=Math.max(240,bounds.width);H=extentMode==='full'?W*.95:(W<500?W*.95:W*.67);
    const dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(W*dpr);canvas.height=Math.round(H*dpr);
    canvas.style.height=H+'px';ctx.setTransform(dpr,0,0,dpr,0,0);floorCache=null;request();
  }
  function updateCount(){
    counter.textContent=sequence?count+' / '+rows.length:String(rows.length);
    host.querySelector('.stage-count-label').textContent=sequence?'累计点亮':'筛选事件';
    fill.style.transform='scaleX('+(sequence?count/Math.max(1,rows.length):1)+')';
    canvas.setAttribute('aria-label',name+'，投篮事件透视图，共'+rows.length+'次；详情可使用下方事件列表。');
  }
  function setMode(mode){
    shown=mode==='stage';host.hidden=!shown;flat.hidden=shown;layout.classList.toggle('stage-layout',shown);
    modeButtons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.shotView===mode)));
    arcs=[];if(frame!==null){cancelAnimationFrame(frame);frame=null;}
    if(shown){entryStart=performance.now();entryDuration=motion.matches?0:1250;resize();}
  }
  modeButtons.forEach(b=>b.addEventListener('click',()=>setMode(b.dataset.shotView)));
  extent.addEventListener('change',()=>setExtent(extent.value));
  light.addEventListener('change',()=>{arcs=[];request();});
  canvas.addEventListener('click',e=>{
    const rect=canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;
    const hits=positions.map(p=>({...p,distance:Math.hypot(x-p.x,y-p.y)})).filter(p=>p.distance<12).sort((a,b)=>a.distance-b.distance);
    if(hits.length>1&&onCandidates)onCandidates(hits.map(p=>p.row));
    else if(hits.length)onChoose(hits[0].row);
  });
  canvas.addEventListener('pointermove',e=>{
    const r=canvas.getBoundingClientRect();canvas.style.cursor=positions.some(p=>Math.hypot(e.clientX-r.left-p.x,e.clientY-r.top-p.y)<12)?'pointer':'default';
  });
  new ResizeObserver(resize).observe(host);
  if('IntersectionObserver' in window){new IntersectionObserver(entries=>entries.forEach(e=>{
    inView=e.isIntersecting;if(inView){if(entryDuration){entryStart=performance.now();}request();}
    else {arcs=[];if(frame!==null){cancelAnimationFrame(frame);frame=null;}}
  }),{threshold:.04}).observe(host);}
  motion.addEventListener('change',()=>{entryDuration=0;arcs=[];request();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){arcs=[];if(frame!==null)cancelAnimationFrame(frame);frame=null;}else request();});
  explorer.querySelector('.shot-view-switch').hidden=false;
  setMode('stage');
  return {
    setRows(next){rows=next;if(rows.length&&rows.every(row=>!inExtent(row)))setExtent('full');selected=null;played.clear();sequence=false;count=0;arcs=[];status.textContent='点击点位或列表，查看单次出手';entryStart=performance.now();entryDuration=motion.matches?0:1250;updateCount();request();},
    select(row){if(!inExtent(row))setExtent('full');selected=row;status.textContent=row.date+' · 第'+row.period+'节 '+row.clock+' · '+(row.made?'命中':'未中');if(!motion.matches&&shown&&inView&&light.checked)arcs.push({row,start:performance.now()});arcs=arcs.slice(-10);request();},
    progress(done,total){sequence=true;played=new Set(done.map(key));count=done.length;updateCount();request();},
    clear(){selected=null;played.clear();sequence=false;count=0;arcs=[];status.textContent='点击点位或列表，查看单次出手';updateCount();request();},
    pause(){arcs=[];entryDuration=0;request();},
    mode(){return shown?'stage':'flat';}, extent(value){if(value)setExtent(value);return extentMode;}
  };
};
