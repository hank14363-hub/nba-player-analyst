/* Descriptive readings derived from the same validated events as the chart.
   Neither outcome display, perspective nor replay changes these denominators. */
window.createShotResearch = function(explorer, api) {
  'use strict';
  const panel=explorer.querySelector('.shot-reading'),body=explorer.querySelector('#shot-region-body');
  const summary=explorer.querySelector('#shot-reading-summary'),boundary=explorer.querySelector('#shot-reading-boundary');
  const context=explorer.querySelector('#shot-context'),back=explorer.querySelector('#shot-return');
  const candidates=explorer.querySelector('.shot-candidates'),candidateList=explorer.querySelector('#shot-candidate-list');
  const labels=Object.fromEntries([...explorer.querySelector('#shot-zone').options].map(o=>[o.value,o.textContent]));
  const codes=['RA','PAINT','MID','LC3','RC3','ATB3','BACK','UNRESOLVED'].filter(code=>labels[code]);
  const explanations={
    all:'位置回答从哪里终结。要解释选择是否合理，还需回到防守、传球窗口与回合时钟。',
    RA:'近筐结果不包含造犯规后的罚球收益，也没有区分接触强度和协防压力。',
    PAINT:'油漆区其余位置涵盖不同终结方式；位置标签不能单独识别抛投、突破或挡拆任务。',
    MID:'中距离可能来自主动选择，也可能是回合末收尾；这些事件没有记录替代传球机会。',
    LC3:'底角结果容易受有限样本影响；位置不能证明是空位或接球出手。',
    RC3:'底角结果容易受有限样本影响；位置不能证明是空位或接球出手。',
    ATB3:'弧顶和两翼合并统计，没有区分持球与接球、空位与受压。',
    BACK:'后场远距出手单列保留；不能据此评价常规三分能力。',
    UNRESOLVED:'官方区域与投篮类型标签冲突；保留原值，计入总体，区域表单列。',
    '2PT':'按官方投篮类型选择两分，仍包含标签冲突记录；两分结果不等于突破能力。',
    '3PT':'按官方投篮类型选择三分；不能从位置反推持球、接球或受助攻分类。'
  };
  let hits=[],candidatePage=0;const size=6;
  function clearCandidates(){hits=[];candidates.hidden=true;candidateList.replaceChildren();}
  function renderCandidates(){
    candidates.hidden=false;candidateList.replaceChildren();
    explorer.querySelector('#shot-candidate-title').textContent='邻近位置 · '+hits.length+' 次出手';
    hits.slice(candidatePage*size,(candidatePage+1)*size).forEach(row=>{
      const button=document.createElement('button');button.type='button';button.className='shot-candidate-button';
      button.dataset.eventKey=row.game+'/'+row.event;
      button.textContent=row.date+' · 第'+row.period+'节 '+row.clock+' · '+(row.made?'命中':'未中')+' · #'+row.event;
      button.addEventListener('click',()=>api.pick(row));candidateList.append(button);
    });
    explorer.querySelector('#shot-candidate-page').textContent=(candidatePage+1)+' / '+Math.ceil(hits.length/size);
    explorer.querySelector('#shot-candidate-prev').disabled=candidatePage===0;
    explorer.querySelector('#shot-candidate-next').disabled=(candidatePage+1)*size>=hits.length;
  }
  explorer.querySelector('#shot-candidate-prev').addEventListener('click',()=>{candidatePage--;renderCandidates();});
  explorer.querySelector('#shot-candidate-next').addEventListener('click',()=>{candidatePage++;renderCandidates();});
  explorer.querySelector('#shot-candidate-close').addEventListener('click',clearCandidates);
  explorer.querySelector('#shot-all-zones').addEventListener('click',()=>api.applyZone('all',false));
  document.querySelectorAll('a.shot-text-link').forEach(link=>link.addEventListener('click',event=>{
    if(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||event.button!==0)return;
    const code=link.dataset.shotZone;if(!labels[code])return;
    event.preventDefault();api.applyZone(code,true);
    context.textContent='来自正文：'+link.dataset.shotTitle+'。已切换为完整赛季的对应样本，显示命中与未中。';
    back.href='#'+link.dataset.shotReturn;back.hidden=false;
    location.hash='shot-explorer';
    explorer.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
    summary.setAttribute('tabindex','-1');summary.focus({preventScroll:true});
  }));
  panel.hidden=false;
  return {
    clearCandidates,
    candidates(rows){
      api.pause();if(rows.length===1){clearCandidates();api.pick(rows[0]);return;}
      hits=rows;candidatePage=0;renderCandidates();
      candidateList.querySelector('button')?.focus({preventScroll:true});
    },
    update(base,sample,code){
      clearCandidates();context.textContent='当前筛选的描述性读数；可点击区域继续检查。';back.hidden=true;
      const made=sample.reduce((n,r)=>n+r.made,0),share=base.length?sample.length/base.length*100:null;
      if(!sample.length){summary.textContent='当前比赛与区域没有出手。命中率为 N/A，不能把无样本解释为零命中率。';}
      else {
        const leader=codes.map(zone=>({zone,n:sample.filter(r=>r.zone===zone).length})).sort((a,b)=>b.n-a.n)[0];
        summary.textContent=(code==='all'?'所选比赛样本':labels[code])+'：'+sample.length+' 次出手，'+made+' 次命中，命中率 '+(made/sample.length*100).toFixed(1)+'%。'+
          (code==='all'&&leader?.n?'出手最多的区域为'+labels[leader.zone]+'（'+leader.n+' 次，'+(leader.n/sample.length*100).toFixed(1)+'%）。':
          '占所选比赛全部出手的 '+share.toFixed(1)+'%。');
      }
      boundary.textContent=(explanations[code]||explanations.all)+(sample.length<30?' 当前样本少于三十次，只作描述。':'')+' 当前没有同口径联盟区域基准，不据此判断区域强弱。';
      body.replaceChildren();
      codes.forEach(zone=>{
        const group=base.filter(r=>r.zone===zone),n=group.length,fgm=group.reduce((v,r)=>v+r.made,0);
        const tr=document.createElement('tr');tr.dataset.zone=zone;tr.dataset.fga=String(n);tr.dataset.fgm=String(fgm);
        const th=document.createElement('th');th.scope='row';const button=document.createElement('button');button.type='button';
        button.dataset.zoneFilter=zone;button.textContent=labels[zone];button.setAttribute('aria-pressed',String(code===zone));button.addEventListener('click',()=>api.applyZone(zone,false));th.append(button);tr.append(th);
        for(const text of [String(n),base.length?(n/base.length*100).toFixed(1)+'%':'N/A',n?(fgm/n*100).toFixed(1)+'%'+(n<30?'†':''):'N/A']){
          const td=document.createElement('td');td.textContent=text;tr.append(td);
        }
        if(code===zone)tr.classList.add('region-active');body.append(tr);
      });
      const related=explorer.querySelector('#shot-related');related.replaceChildren();
      const links=[...document.querySelectorAll('.reading-card .shot-text-link')].filter(a=>a.dataset.shotZone===code);
      if(links.length){
        const heading=document.createElement('strong');heading.textContent='对应正文判断';related.append(heading);
        links.forEach(link=>{const a=document.createElement('a');a.href='#'+link.dataset.shotReturn;a.textContent=link.dataset.shotTitle+' ↑';related.append(a);});
      }
    }
  };
};
