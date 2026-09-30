let visitorResult, visitorLoading=false, visitorError=false;
function renderVisitors(){
 const en=lang==='en';
 $('visitors-title').textContent=en?'Daily regional visitor estimates':'지역별 일간 방문 통계';
 $('visitors-note').textContent=en?'Mobile-network estimates, not real-time crowd levels or measured tourist counts. Do not add districts together. Missing data is not zero. Unit: estimated people, displayed to two decimal places.':'이동통신 기반 추정값입니다. 실시간 혼잡도나 관광객 실측값이 아닙니다. 지역 간 합산하지 않으며, 미제공은 0명이 아닙니다. 단위: 명(추정), 화면은 소수 둘째 자리까지 표시합니다.';
 $('visitor-day-label').textContent=en?'Date':'조회일';$('load-visitors').textContent=en?'Load visitor estimates':'방문 통계 조회';
 $('visitors-result').replaceChildren();$('visitors-status').textContent='';
 if(visitorLoading){$('visitors-status').textContent=en?'Loading national pages…':'전국 자료 페이지를 확인하는 중…';return;}
 if(visitorError){$('visitors-status').textContent=en?'Could not verify the full response. Check API access, date and network.':'전체 응답을 검증하지 못했습니다. API 권한·조회일·네트워크를 확인하세요.';return;}
 if(!visitorResult)return;
 if(visitorResult.source_mode==='unconfigured'){$('visitors-status').textContent=en?'API key required.':'방문자수 API 인증키 설정이 필요합니다.';return;}
 const d=visitorResult;
 $('visitors-status').textContent=`${d.date} · ${en?'Received':'수신'} ${d.fetched_at} · ${d.source_mode==='cached_stale'?(en?'Stale cache':'이전 캐시'):(en?'API data':'API 자료')} · ${d.complete?(en?'All 12 district/group values available':'4개 구·3개 구분 모두 확인'):(en?'Some values unavailable':'일부 자료 미제공')}`;
 const table=node('table'),thead=node('thead'),header=node('tr');
 for(const h of en?['District','Residents (estimate)','Domestic non-residents (estimate)','Foreign visitors (estimate)']:['지역','현지인 추정','외지인 추정','외국인 추정']){const th=node('th',h);th.scope='col';header.append(th);}
 thead.append(header);table.append(thead);const body=node('tbody');
 const names={'동구':'Dong-gu','중구':'Jung-gu','서구':'Seo-gu','영도구':'Yeongdo-gu'};
 for(const r of d.rows){const tr=node('tr');const th=node('th',en?names[r.district]:r.district);th.scope='row';tr.append(th);for(const g of ['1','2','3'])tr.append(node('td',r.groups[g]===null?(en?'Unavailable':'미제공'):new Intl.NumberFormat(en?'en-US':'ko-KR',{maximumFractionDigits:2}).format(Number(r.groups[g]))));body.append(tr);}
 table.append(body);$('visitors-result').append(table);const a=node('a',en?'Korea Tourism Organization · Source':'한국관광공사 · 데이터 출처');a.href=d.source_url;a.target='_blank';a.rel='noopener noreferrer';$('visitors-result').append(a);
}
$('load-visitors').addEventListener('click',async()=>{
 visitorLoading=true;visitorError=false;visitorResult=null;$('load-visitors').disabled=true;$('visitor-day').disabled=true;renderVisitors();
 try{const r=await fetch('/api/visitors?'+new URLSearchParams({day:$('visitor-day').value.replaceAll('-','')}));if(!r.ok)throw new Error('unavailable');visitorResult=await r.json();}catch{visitorError=true;}
 finally{visitorLoading=false;$('load-visitors').disabled=false;$('visitor-day').disabled=false;renderVisitors();}
});
$('visitor-day').addEventListener('change',()=>{visitorResult=null;visitorError=false;renderVisitors();});
$('language').addEventListener('click',renderVisitors);renderVisitors();
