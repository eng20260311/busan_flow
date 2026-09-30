// Recipient districts are lookup context, never event coordinates or hazard boundaries.
function appendAlertRegions(card, alert){
 const ko=lang==='ko',section=node('section','','alert-region');
 section.append(node('h4',ko?'문자 관련 지역 정보':'Area information for this notice'));
 section.append(node('p',(ko?'원문에서 인식한 장소명 단서: ':'Recognized place-name hints: ')+(alert.location_name||(ko?'확인되지 않음 · 원문 확인 필요':'Not identified; check the original notice')),'meta'));
 section.append(node('p',ko?'일부 장소명만 인식합니다. 아래 구·군은 문자 수신지역이며 실제 발생지·위험 경계가 아닙니다. 관광정보는 해당 지역을 이해하기 위한 자료로, 방문 권고가 아닙니다.':'Only a limited set of place names is recognized. Recipient districts are not incident locations or hazard boundaries. Tourism listings are context, not a recommendation to visit.','meta'));
 if(alert.location_name){
  const link=node('a',ko?'언급 장소 지도 검색 · 위치 직접 확인':'Search mentioned place on map · verify location');
  link.href='https://map.naver.com/p/search/'+encodeURIComponent('부산 '+alert.location_name.split(' / ')[0]);link.target='_blank';link.rel='noopener noreferrer';section.append(link);
 }
 const supported=['동구','중구','서구','영도구','부산진구','동래구','남구','북구','해운대구','사하구','금정구','강서구','연제구','수영구','사상구','기장군'];
 const districts=[...new Set(alert.received_regions.filter(r=>/^부산(?:광역시)?\s/.test(r)).flatMap(r=>supported.filter(d=>new RegExp('(?:^|\\s)'+d+'(?:$|\\s|,)').test(r))))];
 section.append(node('p',(ko?'수신지역: ':'Recipient areas: ')+alert.received_regions.join(', '),'meta'));
 if(!districts.length){section.append(node('p',ko?'부산의 특정 구·군이 명시되지 않아 지역별 조회를 연결하지 않았습니다. 광역·전국 문자를 임의의 구에 연결하지 않습니다.':'No specific Busan district is listed. City-wide or national notices are not assigned to an inferred district.'));card.append(section);return;}
 const details=node('details'),summary=node('summary',ko?'수신지역 관광정보·방문 추정값 보기':'Explore recipient-area listings and visitor estimates');details.append(summary);
 const select=node('select');select.setAttribute('aria-label',ko?'문자 수신지역 선택':'Select recipient district');districts.forEach(d=>{const o=node('option',d);o.value=d;select.append(o);});
 const type=node('select');type.setAttribute('aria-label',ko?'관련 관광정보 유형':'Listing type');[['12',ko?'관광지':'Attractions'],['14',ko?'문화시설':'Culture'],['38',ko?'쇼핑':'Shopping']].forEach(([value,label])=>{const o=node('option',label);o.value=value;type.append(o);});
 const button=node('button',ko?'지역 정보 조회':'Load area information');button.type='button';
 const status=node('p','','meta');status.setAttribute('role','status');const output=node('div');
 details.append(select,type,button,status,output);section.append(details);card.append(section);
 for(const control of [select,type])control.addEventListener('change',()=>{output.replaceChildren();status.textContent=ko?'조건이 변경되었습니다. 다시 조회해 주세요.':'Filters changed. Load again.';});
 button.addEventListener('click',async()=>{
  button.disabled=select.disabled=type.disabled=true;output.replaceChildren();status.textContent=ko?'조회 중…':'Loading…';
  const district=select.value;
  const results=await Promise.allSettled([
   fetch('/api/places?'+new URLSearchParams({district,content_type:type.value})).then(async r=>{if(!r.ok)throw Error();return r.json();}),
   fetch('/api/visitor-trends?weeks=8').then(async r=>{if(!r.ok)throw Error();return r.json();})
  ]);
  try{
   status.textContent=(ko?'조회한 수신지역: ':'Recipient-area lookup: ')+district;
   const tourism=results[0],trends=results[1];
   if(tourism.status==='fulfilled'){
    const data=tourism.value;
    output.append(node('p',`${ko?'관광정보':'Listings'}: ${data.places.length}/${data.total??'?'} · ${data.source_mode==='cached_stale'?(ko?'갱신 실패 · 이전 수신 기록':'Refresh failed · earlier data'):data.source_mode==='unconfigured'?(ko?'API 키 미설정':'API key not configured'):'TourAPI'} · ${data.fetched_at||''}`,'meta'));
    output.append(node('p',ko?'유형별 첫 20건 이내이며, 언급 장소 주변의 거리순 검색이 아닙니다. 운영 여부·접근 안전은 미검증입니다.':'Up to 20 first-page listings; not a proximity search around the mentioned place. Opening status and access safety are unverified.','meta'));
    const list=node('ul');for(const p of data.places){const item=node('li');item.append(node('strong',p.name),node('p',p.address,'meta'));if(p.has_coordinates){const link=node('a',ko?'장소 지도':'Place map');link.href=`https://www.openstreetmap.org/?mlat=${p.latitude}&mlon=${p.longitude}#map=16/${p.latitude}/${p.longitude}`;link.target='_blank';link.rel='noopener noreferrer';item.append(link);}list.append(item);}output.append(list);
    if(!data.places.length)output.append(node('p',ko?'표시할 관광정보가 없습니다.':'No listings available.'));
   }else output.append(node('p',ko?'관광정보 조회 실패 · 인증 또는 서버 연결 상태를 확인하세요.':'Tourism lookup failed. Check API access or server connection.'));
   if(trends.status==='fulfilled'&&trends.value.analysis&&trends.value.analysis.series.some(s=>s.district===district)){
    const a=trends.value.analysis;const date=d=>`${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}`;
    output.append(node('h4',ko?'지역 방문 추정값 · 과거 자료':'Area visitor estimates · historical data'));
    output.append(node('p',`${date(a.start_date)} ~ ${date(a.end_date)} · ${ko?'최신 자료일':'Latest data date'} ${date(a.end_date)} · ${ko?'수집':'Collected'} ${a.generated_at}`,'meta'));
    for(const series of a.series.filter(s=>s.district===district)){const p=series.points.at(-1),value=p.value===null?(ko?'미제공':'Missing'):new Intl.NumberFormat(ko?'ko-KR':'en-US',{maximumFractionDigits:2}).format(Number(p.value));output.append(node('p',`${series.group==='2'?(ko?'내국인 외지인':'Domestic nonresidents'):(ko?'외국인':'Foreign visitors')}: ${value} ${ko?'명(추정)':'(estimated people)'} · ${ko?'8주 누락':'Missing days in 8 weeks'} ${series.missing_dates.length}`));}
    output.append(node('p',ko?'문자 발령일의 방문자 수나 현재 혼잡도가 아닙니다. 수신지역 전체의 과거 추정값이며 사건 영향·안전성을 나타내지 않습니다.':'These are historical district estimates, not visitor counts on the notice date or current crowding. They do not measure incident impact or safety.','meta'));
   }else output.append(node('p',ko?'이 지역의 방문 추정값이 없거나 조회에 실패했습니다. 현재 수집 범위는 동구·중구·서구·영도구이며, 미제공은 방문자 0명을 뜻하지 않습니다.':'Visitor estimates are unavailable. Current coverage: Dong-gu, Jung-gu, Seo-gu and Yeongdo-gu. Missing data does not mean zero visitors.'));
   for(const [label,url] of [[ko?'관광정보 출처':'Tourism source','https://www.data.go.kr/data/15101578/openapi.do'],[ko?'방문자수 출처':'Visitor estimates source','https://www.data.go.kr/data/15101972/openapi.do']]){const link=node('a',label);link.href=url;link.target='_blank';link.rel='noopener noreferrer';output.append(link,node('span',' · '));}
  }finally{button.disabled=select.disabled=type.disabled=false;}
 });
}
