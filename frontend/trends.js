let trendData=null, trendJob=null, trendTimer=null, trendRequest=0;
const trendNumber=v=>v===null||v===undefined?'미제공':new Intl.NumberFormat('ko-KR',{maximumFractionDigits:2}).format(Number(v));
const trendDate=d=>`${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}`;
function trendTable(headers,rows){
 const t=node('table'),head=node('thead'),tr=node('tr');
 for(const h of headers){const cell=node('th',h);cell.scope='col';tr.append(cell);}head.append(tr);t.append(head);
 const body=node('tbody');for(const row of rows){const r=node('tr');row.forEach((v,i)=>{const c=node(i===0?'th':'td',v);if(i===0)c.scope='row';r.append(c);});body.append(r);}t.append(body);return t;
}
function trendChart(points,field,title,color){
 const ns='http://www.w3.org/2000/svg';
 const el=(tag,attrs={},text)=>{const n=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));if(text!==undefined)n.textContent=text;return n;};
 const svg=el('svg',{viewBox:'0 0 760 230',role:'img','aria-label':title,class:'trend-chart'});svg.append(el('title',{},title));
 const vals=points.filter(p=>p[field]!==null).map(p=>Number(p[field]));
 if(!vals.length){svg.append(el('text',{x:40,y:100},'표시 가능한 자료가 없습니다.'));return svg;}
 const low=field==='change_pct'?Math.min(0,...vals):0;
 let high=Math.max(0,...vals);if(high===low)high=low+1;
 const x=i=>88+i*642/Math.max(1,points.length-1),y=v=>180-(v-low)/(high-low)*150;
 for(let i=0;i<=3;i++){const v=low+(high-low)*i/3;svg.append(el('line',{x1:88,x2:730,y1:y(v),y2:y(v),stroke:'#d6e1da'}));svg.append(el('text',{x:80,y:y(v)+4,'text-anchor':'end','font-size':11},new Intl.NumberFormat('ko-KR',{maximumFractionDigits:1}).format(v)));}
 if(field==='change_pct')svg.append(el('line',{x1:88,x2:730,y1:y(0),y2:y(0),stroke:'#64756f','stroke-dasharray':'4 3'}));
 let path='',connected=false;
 points.forEach((p,i)=>{if(p[field]===null){connected=false;return;}path+=`${connected?'L':'M'}${x(i)} ${y(Number(p[field]))} `;connected=true;});
 svg.append(el('path',{d:path,fill:'none',stroke:color,'stroke-width':2}));
 points.forEach((p,i)=>{if(p[field]===null)return;const c=el('circle',{cx:x(i),cy:y(Number(p[field])),r:3,fill:color,tabindex:0});c.append(el('title',{},`${trendDate(p.date)} · ${trendNumber(p[field])}${field==='change_pct'?'%':'명'}`));svg.append(c);});
 [0,Math.floor((points.length-1)/2),points.length-1].forEach(i=>svg.append(el('text',{x:x(i),y:211,'font-size':11,'text-anchor':i===0?'start':i===points.length-1?'end':'middle'},trendDate(points[i].date))));
 return svg;
}
function renderTrends(){
 const a=trendData;$('trend-summary').replaceChildren();$('trend-charts').replaceChildren();$('trend-detail').replaceChildren();
 if(!a){$('trend-meta').textContent='아직 수집된 추이 자료가 없습니다. 최신 자료 수집을 눌러주세요.';return;}
 $('trend-meta').textContent=`표시 기간 ${trendDate(a.start_date)} ~ ${trendDate(a.end_date)} (${a.weeks}주) · 최근 제공 확인일 ${trendDate(a.end_date)} · 수집 ${a.generated_at}`;
 const missing=a.series.reduce((s,r)=>s+r.missing_dates.length,0);
 $('trend-quality').textContent=`누락 ${missing}/${a.weeks*7*8}개 값(일자×4개 구×2개 구분) · 수집 실패 ${a.failed_dates.length}일 · 이전 캐시 ${a.stale_dates.length}일. 최근일 확인 범위 ${trendDate(a.discovery.checked_from)} ~ ${trendDate(a.discovery.checked_through)}. 비교용 자료: ${trendDate(a.baseline_start)}부터. 수집 실패·이전 캐시 일수는 비교용 기간을 포함한 전체 수집 범위 기준입니다.`;
 const rows=[];
 for(const s of a.series){const p=s.points.at(-1);rows.push([s.district,s.group==='2'?'외지인':'외국인',trendNumber(p.value),p.change_pct===null?'미산출':trendNumber(p.change_pct)+'%',`${s.points.length-s.missing_dates.length}/${s.points.length}일`,`${s.unavailable_comparisons}일`]);}
 $('trend-summary').append(trendTable(['최근 제공일 기준','구분','추정 방문자','같은 요일 대비','자료 있음','변화율 미산출'],rows));
 const district=$('trend-district').value;
 const chosen=a.series.filter(s=>s.district===district);
 for(const s of chosen){const name=s.group==='2'?'외지인':'외국인',card=node('article','','card');card.append(node('h3',`${district} · ${name}`),node('p','일간 방문 추정값 (명)','meta'),trendChart(s.points,'value',`${district} ${name} 일간 방문 추이`,'#087e72'),node('p','이전 4주 같은 요일 평균 대비 변화율 (%)','meta'),trendChart(s.points,'change_pct',`${district} ${name} 같은 요일 대비 변화율`,'#99591c'));
 if(s.missing_dates.length)card.append(node('p','누락일: '+s.missing_dates.map(trendDate).join(', '),'meta'));$('trend-charts').append(card);}
 const reason={ok:'산출',missing_current:'당일 누락',missing_baseline:'기준일 누락',zero_baseline:'기준 평균 0'};
 $('trend-detail').append(trendTable(['날짜','구분','추정 방문자','이전 4주 같은 요일 평균','변화율 %','기준 관측','상태','기준 날짜'],chosen.flatMap(s=>s.points.map(p=>[trendDate(p.date),s.group==='2'?'외지인':'외국인',trendNumber(p.value),trendNumber(p.baseline_mean),p.change_pct===null?'미산출':trendNumber(p.change_pct),`${p.baseline_observations}/4`,reason[p.comparison_status],p.baseline_dates.map(trendDate).join(', ')]))));
}
async function loadTrends(){
 const request=++trendRequest;
 try{const r=await fetch('/api/visitor-trends?weeks='+$('trend-weeks').value);if(!r.ok)throw Error();const d=await r.json();if(request!==trendRequest)return;trendData=d.analysis;trendJob=d.job;renderTrends();
 const active=['discovering','collecting'].includes(d.job.status);$('trend-refresh').disabled=active;
 $('trend-status').textContent=active?`${d.job.status==='discovering'?'최근 제공일 확인 중':'자료 수집 중'} · ${d.job.checking_date||''} · ${d.job.completed}/${d.job.total}`:d.job.status==='failed'?'자료 수집에 실패했습니다. 이전 분석이 있으면 유지합니다.':trendData?'수집된 실데이터 분석입니다. 실시간 혼잡도가 아닙니다.':'';
 clearTimeout(trendTimer);if(active)trendTimer=setTimeout(loadTrends,2000);
 }catch{$('trend-status').textContent='추이 자료를 불러오지 못했습니다. 서버 연결을 확인하세요.';$('trend-refresh').disabled=false;}
}
$('trend-refresh').addEventListener('click',async()=>{ $('trend-refresh').disabled=true;try{const r=await fetch('/api/visitor-trends/refresh',{method:'POST'});if(!r.ok)throw Error();await loadTrends();}catch{$('trend-status').textContent='수집을 시작하지 못했습니다.';$('trend-refresh').disabled=false;}});
$('trend-weeks').addEventListener('change',loadTrends);$('trend-district').addEventListener('change',renderTrends);loadTrends();
