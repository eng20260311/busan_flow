let journey={key:null,place:null,epoch:0};
function resetJourney(){
 journey={key:null,place:null,epoch:journey.epoch+1};clearCandidates();
 $('journey-notice').textContent='문자 카드의 ‘이 문자로 장소 찾기’를 눌러 시작하세요.';
 $('journey-status').textContent='';$('journey-selection').textContent='';$('journey-places').replaceChildren();$('journey-next').disabled=true;
 $('candidate-status').textContent='일반 탐색 · 문자 연결 없음';
}
async function startNoticeJourney(alert){
 resetJourney();journey.key=alert.review_key;const epoch=journey.epoch;
 $('journey-notice').textContent=`① 선택 문자 · ${words.ko[snapshot.source_mode]} · ${alert.created_at} · ${alert.original_message}`;
 $('journey-status').textContent='② 저장된 관광정보와 장소명을 대조하고 있습니다…';
 $('notice-journey').scrollIntoView({behavior:'smooth',block:'start'});
 try{
  const response=await fetch('/api/notice-places/'+alert.review_key);if(!response.ok)throw Error();const data=await response.json();if(epoch!==journey.epoch)return;
  $('journey-status').textContent=`② 대조 대상 ${data.indexed_count}곳 · 결과 ${data.places.length}곳. ${data.scope} 이름 일치는 사건 발생 위치의 공식 확인이 아닙니다.`;
  if(!data.places.length)$('journey-places').append(node('p','장소 미확인. 관광정보 조회로 자료를 수신한 뒤 다시 대조하거나, 문자 연결을 해제하고 지역을 직접 선택해 일반 탐색하세요.'));
  for(const p of data.places){
   const card=node('article','','card');card.append(node('h3',p.name),node('p',p.address),node('p',`${p.match_kind==='exact'?'이름 일치':'부분 이름 일치 · 확인 필요'} · ${p.source} · 수신 ${p.fetched_at}`,'meta'));
   for(const m of p.matches)card.append(node('p',`추출 표현: ${m.mention} / 원문 근거: ${m.evidence}`));
   if(p.has_coordinates)card.append(candidateLink(p));
   const choose=node('button',p.has_coordinates?'이 장소 선택':'좌표 없음 · 선택 불가');choose.type='button';choose.disabled=!p.has_coordinates;
   choose.addEventListener('click',()=>{
    if(epoch!==journey.epoch)return;journey.place=p;clearCandidates();
    $('candidate-origin').value=p.district;$('candidate-scenario').value='none';
    if($('candidate-district').value===p.district)$('candidate-district').value=['동구','중구','서구','영도구'].find(d=>d!==p.district);
    $('journey-selection').textContent=`② 사용자 선택: ${p.name} · ${p.address} → ③ ${p.district} 외 지역 탐색. 발생 위치·통제 범위는 미검증입니다.`;
    $('journey-next').disabled=false;$('candidate-status').textContent='장소가 선택되었습니다. 대안 지역을 선택하고 탐색 후보를 구성하세요.';
   });card.append(choose);$('journey-places').append(card);
  }
 }catch{if(epoch===journey.epoch)$('journey-status').textContent='관광정보 대조를 불러오지 못했습니다. 다시 시도하세요.';}
}
$('journey-reset').addEventListener('click',resetJourney);
$('journey-next').addEventListener('click',()=>{if(journey.place)$('candidate-section').scrollIntoView({behavior:'smooth',block:'start'});});
$('candidate-origin').addEventListener('change',resetJourney);
function journeyContext(){return journey.place?`선택 문자 연결 · ${journey.place.name} (${journey.place.district}) 외 지역 관광정보 · 발생 위치와 후보 안전 미검증`:journey.key?'문자 장소 미선택 · 일반 지역 탐색':'일반 지역 탐색';}
