let tourResult = null, tourLoading = false, tourFailed = false, tourErrorCode = '';
const tourErrors = {
 ko: {upstream_connection_failed:'서버가 관광정보 API에 연결하지 못했습니다. 서버의 외부 네트워크 접근을 확인해야 합니다.',upstream_timeout:'관광정보 API 응답 시간이 초과됐습니다. 잠시 후 다시 조회하세요.',authentication_failed:'관광정보 API 인증 또는 이용 권한을 확인해야 합니다.',rate_limited:'관광정보 API 호출 한도에 도달했습니다. 잠시 후 다시 조회하세요.',retry_later:'앞선 조회가 실패해 잠시 대기 중입니다. 1분 후 다시 조회하세요.'},
 en: {upstream_connection_failed:'The server could not connect to the tourism API. Check server network access.',upstream_timeout:'The tourism API timed out. Please try again shortly.',authentication_failed:'Check tourism API credentials and service permissions.',rate_limited:'The tourism API rate limit was reached. Please try again later.',retry_later:'Waiting after a failed request. Please retry in one minute.'}
};
const tourLabels = {
 ko: {title:'부산 관광지 탐색',note:'관광정보 조회 결과입니다. 위험구역·이동경로·운영 여부는 검증 전입니다.',district:'지역',type:'유형',load:'관광정보 조회',loading:'조회 중…',missing:'TOUR_API_KEY 설정이 필요합니다. 합성 관광지를 대신 표시하지 않습니다.',error:'관광정보를 불러오지 못했습니다. 인증 상태와 네트워크를 확인하세요.',stale:'갱신 실패 · 이전 수신 기록',api:'TourAPI 수신 기록',more:'첫 페이지 결과입니다. 전체 목록이 아닙니다.',empty:'해당 조건의 관광정보가 없습니다.',source:'한국관광공사 · 원본 서비스 안내',unverified:'분류 확인 필요',types:['관광지','문화시설','쇼핑','음식점','레포츠','숙박','축제·행사','여행코스'],districts:['동구','중구','서구','영도구']},
 en: {title:'Explore places in Busan',note:'Tourism listings only. Hazard areas, routes and opening status have not been verified.',district:'District',type:'Type',load:'Load tourism listings',loading:'Loading…',missing:'TOUR_API_KEY is not configured. No synthetic places are substituted.',error:'Could not load tourism listings. Check API access and network.',stale:'Refresh failed · Earlier response',api:'TourAPI response',more:'First page only. This is not the full list.',empty:'No tourism listings match these filters.',source:'Korea Tourism Organization · Source service',unverified:'Classification needs review',types:['Attractions','Culture','Shopping','Food','Leisure','Accommodation','Festivals','Courses'],districts:['Dong-gu','Jung-gu','Seo-gu','Yeongdo-gu']}
};
function renderPlaces(){
 const w=tourLabels[lang];$('places-title').textContent=w.title;$('places-note').textContent=w.note;$('district-label').textContent=w.district;$('type-label').textContent=w.type;$('load-places').textContent=w.load;
 Array.from($('district').options).forEach((o,i)=>{o.value=tourLabels.ko.districts[i];o.textContent=w.districts[i];});
 Array.from($('tour-type').options).forEach((o,i)=>o.textContent=w.types[i]);
 $('places').replaceChildren();$('places-status').textContent='';
 if(tourLoading){$('places-status').textContent=w.loading;return;}
 if(tourFailed){$('places-status').textContent=tourErrors[lang][tourErrorCode]||w.error;return;}
 if(!tourResult)return;
 if(tourResult.source_mode==='unconfigured'){$('places-status').textContent=w.missing;return;}
 $('places-status').textContent=`${tourResult.source_mode==='cached_stale'?w.stale:w.api} · ${tourResult.fetched_at} · ${tourResult.total}${tourResult.has_more?' · '+w.more:''}`;
 if(!tourResult.places.length)$('places-status').textContent+=' · '+w.empty;
 for(const p of tourResult.places){
  const card=node('article','','card');card.append(node('h3',p.name),node('p',p.address),node('p',`${p.type_name} · ${p.classification_name||w.unverified}`,'meta'));
  const link=node('a',w.source);link.href=p.source_url;link.target='_blank';link.rel='noopener noreferrer';card.append(link);$('places').append(card);
 }
}
$('load-places').addEventListener('click',async()=>{
 tourLoading=true;tourFailed=false;tourResult=null;for(const id of ['load-places','district','tour-type'])$(id).disabled=true;renderPlaces();
 try{tourErrorCode='';const q=new URLSearchParams({district:$('district').value,content_type:$('tour-type').value});const r=await fetch('/api/places?'+q);const body=await r.json();if(!r.ok){tourErrorCode=body.detail;throw new Error('unavailable');}tourResult=body;}
 catch{tourFailed=true;}finally{tourLoading=false;for(const id of ['load-places','district','tour-type'])$(id).disabled=false;renderPlaces();}
});
for(const id of ['district','tour-type'])$(id).addEventListener('change',()=>{tourResult=null;tourFailed=false;renderPlaces();});
$('language').addEventListener('click',renderPlaces);renderPlaces();
