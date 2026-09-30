let candidateMap=null,candidateLayer=null,candidateRisk=null;
let candidateEpoch=0;
function clearCandidates(){
 candidateEpoch++;
 $('candidate-courses').replaceChildren();$('candidate-sources').replaceChildren();
 $('candidate-risk').replaceChildren();candidateRisk=null;
 if(candidateLayer)candidateLayer.clearLayers();
 $('candidate-map-title').textContent='후보를 구성하면 장소 위치가 표시됩니다';
 $('candidate-map-status').textContent='지도 번호는 목록 순서입니다. 경로·이동시간 안내가 아닙니다.';
}
function showCandidateMap(course,index){
 $('candidate-map-title').textContent=course.places.length?`탐색 후보 ${index+1} · 장소 위치${candidateRisk?.is_synthetic?' · 합성 위험구역 시연':''}`:'합성 시연 구역 · 후보 구성 보류';
 if(!window.L){$('candidate-map-status').textContent='지도를 불러오지 못했습니다. 아래 장소 목록의 개별 지도 링크를 이용하세요.';return;}
 if(!candidateMap){
  candidateMap=L.map('candidate-map',{scrollWheelZoom:false}).setView([35.10,129.04],13);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).on('tileerror',()=>{$('candidate-map-status').textContent='배경 지도 일부를 불러오지 못했습니다. 위치 번호와 장소 목록을 참고하세요.';}).addTo(candidateMap);
  candidateLayer=L.layerGroup().addTo(candidateMap);
 }
 candidateLayer.clearLayers();
 const bounds=course.places.map(p=>[p.latitude,p.longitude]);
 for(const z of candidateRisk?.zones||[]){
  const label=node('div',`[합성 시연] ${z.name} · 반경 ${z.radius_m}m · 실제 통제 경계 아님`);
  const circle=L.circle([z.latitude,z.longitude],{radius:z.radius_m,color:'#b33a31',fillColor:'#d9574b',fillOpacity:0.2,dashArray:'6 4'}).bindPopup(label).addTo(candidateLayer);
  bounds.push([circle.getBounds().getSouth(),circle.getBounds().getWest()],[circle.getBounds().getNorth(),circle.getBounds().getEast()]);
 }
 for(const [i,p] of course.places.entries()){
  const content=node('div');content.append(node('strong',`${i+1}. ${p.name}`),node('p',p.address));
  L.marker([p.latitude,p.longitude],{icon:L.divIcon({className:'candidate-pin',html:String(i+1),iconSize:[30,30]}),title:`${i+1}. ${p.name}`}).bindPopup(content).addTo(candidateLayer);
 }
 candidateMap.invalidateSize();if(bounds.length)candidateMap.fitBounds(bounds,{padding:[35,35],maxZoom:16});
}
function candidateLink(p){
 const link=node('a','개별 장소 지도 열기');
 link.href=`https://www.openstreetmap.org/?mlat=${p.latitude}&mlon=${p.longitude}#map=17/${p.latitude}/${p.longitude}`;link.target='_blank';link.rel='noopener noreferrer';return link;
}
function renderCandidates(data){
 candidateRisk=data.risk;
 if(candidateRisk?.applied){
  const notice=node('section','','notice');notice.append(node('strong','합성 문자·가상 위험구역 시연 — 실제 재난이 아닙니다'),node('p',candidateRisk.original_message),node('p',`필터 전 후보 ${data.before_course_count}개 → 적용 후 ${data.courses.length}개 · 제외/보류 장소 ${candidateRisk.excluded.length}개 · 구성 가능 장소 ${data.eligible_count}개`));
  notice.append(node('p',candidateRisk.review_reason||'가상 구역 내부·경계의 장소를 제외했습니다. 구역 밖 장소와 연결 경로의 안전을 보장하지 않습니다.'));
  if(candidateRisk.zones.length)notice.append(node('p','빨간 점선 원: 개발자가 설정한 반경 200m 시연 구역. 문자 수신지역으로부터 추정한 경계가 아닙니다.'));
  if(candidateRisk.excluded.length){const details=node('details'),summary=node('summary',`제외·보류 장소와 이유 ${candidateRisk.excluded.length}개`),list=node('ul');candidateRisk.excluded.forEach(p=>list.append(node('li',`${p.name} — ${p.reason}`)));details.append(summary,list);notice.append(details);}
  $('candidate-risk').append(notice);
 }else $('candidate-risk').append(node('p','위험지역 제외 미적용 · 현재 안전 미검증','meta'));
 $('candidate-status').textContent=`${data.origin} → ${data.district} · 탐색 후보 ${data.courses.length}개 · 조회 장소 ${data.pool_count}개 · 좌표 미확인/범위 밖 ${data.excluded_coordinates}개 제외. ${data.scope}`;
 if(data.status==='unconfigured')$('candidate-status').textContent='관광정보 API 키 설정이 필요합니다.';
 if(data.failures.length)$('candidate-status').textContent+=` ${data.failures.length}개 유형 조회 실패로 일부 자료만 사용했습니다.`;
 if(candidateRisk?.blocked)$('candidate-status').textContent+=' 합성 시연: 위치 또는 해제 범위 확인 전 후보 구성을 보류합니다.';
 else if(!data.courses.length)$('candidate-status').textContent+=' 조건에 맞는 장소 3곳을 확보하지 못해 후보를 구성하지 않았습니다.';
 data.courses.forEach((course,i)=>{
  const card=node('article','','card');card.append(node('h3',`탐색 후보 ${i+1} · ${data.district}`),node('p',course.reason),node('p',`목록 순서의 직선거리 합계 약 ${course.straight_line_km}km · 실제 이동거리·소요시간 아님`,'meta'));
  const list=node('ol');for(const p of course.places){const item=node('li');item.append(node('strong',p.name),node('p',`${p.type_name} · ${p.address}`),candidateLink(p));list.append(item);}card.append(list);
  const button=node('button',`후보 ${i+1} 지도 보기`);button.type='button';button.addEventListener('click',()=>showCandidateMap(course,i));card.append(button);$('candidate-courses').append(card);
  for(const action of ['select','save']){const control=node('button',`후보 ${i+1} ${action==='select'?'선택':'저장'}`);control.type='button';control.disabled=!testSession||!data.query_id;control.addEventListener('click',()=>recordCandidateAction(data,course,action,control));card.append(control);}
 });
 for(const s of data.sources)$('candidate-sources').append(node('p',`${s.type==='12'?'관광지':s.type==='14'?'문화시설':'쇼핑'} · ${s.returned}/${s.total??'미확인'}건 · ${s.mode==='cached_stale'?'갱신 실패: 이전 기록 사용':s.mode==='unconfigured'?'키 미설정':'TourAPI 수신 기록'} · ${s.fetched_at||'수신 없음'}`));
 const source=node('a','관광정보 출처 · 한국관광공사');source.href='https://www.data.go.kr/data/15101578/openapi.do';source.target='_blank';source.rel='noopener noreferrer';$('candidate-sources').append(source);
 if(data.courses.length)showCandidateMap(data.courses[0],0);
 else if(candidateRisk?.zones.length)showCandidateMap({places:[]},0);
 else if(candidateRisk?.blocked)$('candidate-map-title').textContent='위치 불명 · 구역을 그리지 않고 후보 구성 보류';
}
$('load-candidates').addEventListener('click',async()=>{
 if(journey.key&&!journey.place){$('candidate-status').textContent='먼저 문자 관련 장소를 선택하거나 문자 연결을 해제하세요.';return;}
 clearCandidates();const origin=$('candidate-origin').value,district=$('candidate-district').value;
 const epoch=candidateEpoch,context=journeyContext();
 const selection=journey.place?{notice_key:journey.key,place_id:journey.place.id}:{};
 if(origin===district){$('candidate-status').textContent='대안 탐색 지역은 기존 관심 지역과 다르게 선택해 주세요.';return;}
 const scenario=$('candidate-scenario').value;
 const ids=['load-candidates','candidate-origin','candidate-district','candidate-scenario'];ids.forEach(id=>$(id).disabled=true);$('candidate-status').textContent='실제 관광정보를 조회하여 탐색 후보를 구성하고 있습니다…';
 try{const params=new URLSearchParams({origin,district,scenario,...selection});if(testSession)params.set('session_id',testSession.session_id);const response=await fetch('/api/candidates?'+params);if(!response.ok)throw Error();const data=await response.json();if(epoch!==candidateEpoch)return;renderCandidates(data);$('candidate-status').textContent=context+' · '+$('candidate-status').textContent;}
 catch{if(epoch===candidateEpoch)$('candidate-status').textContent='탐색 후보를 불러오지 못했습니다. 서버 연결과 관광정보 API 상태를 확인하세요.';}
 finally{ids.forEach(id=>$(id).disabled=false);}
});
for(const id of ['candidate-origin','candidate-district','candidate-scenario'])$(id).addEventListener('change',()=>{clearCandidates();$('candidate-status').textContent='조건이 변경되었습니다. 탐색 후보 구성 버튼을 눌러주세요.';});
