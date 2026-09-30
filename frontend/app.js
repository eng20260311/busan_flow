let lang = 'ko', snapshot, loadError = false;
let alertDistrict = 'all';
const $ = id => document.getElementById(id);
const words = {
  ko: {title:'북항의 실제 문자에서,\n다음 목적지까지.',intro:'공식 행동요령 → 과거 방문 추이 → 대체 관광지 탐색 → 지도 확인 → 선택·저장',list:'안전문자 확인',refresh:'새로 확인',synthetic_demo:'안전문자 합성 예시 · 실제 발령이 아닙니다',historical_sample:'과거 샘플 모드 · 현재 상황이 아닙니다',live:'API 수신 데이터 · 현장 안전을 보장하지 않습니다',cached_stale:'API 갱신 실패 또는 지연 · 이전 수신 기록입니다',limit:'사건의 현재 지속·종료 여부와 위험구역은 검증되지 않았습니다. 서비스 안내는 원문 번역이 아닌 규칙 기반 참고문입니다.',original:'한국어 원문 / 합성 예시는 별도 표시',guidance:'FLOW 안내 · 규칙 템플릿',source:'출처와 API 안내',next:'다음 개발 단계',nextCopy:'탐색 후보·지도·합성 위험구역 제외·선택·저장 로그 구현 완료. 다음은 실제 사용자 테스트와 제출 자료 검토입니다. 현재 안전·실제 이동경로는 미검증입니다.',error:'데이터를 불러오지 못했습니다. 다시 확인해 주세요.',empty:'조회된 부산 문자가 없습니다. 안전이 확인되었다는 뜻은 아닙니다.',info:'일반정보',caution:'주의',danger:'위험',review:'수동 검토 필요',unverified:'현재 상태 미확인',fetched:'API 수신',latest:'최근 발령',none:'없음',coverage:'조회 범위',sample_only:'예시 데이터',partial_or_unknown:'일부 또는 미확인',complete_page:'요청 범위 내 한 페이지',loading:'데이터 확인 중…'},
  en: {title:'North Port notices.\nExplore your next stop.',intro:'Historical North Port case replay. The case walkthrough is currently available in Korean.',list:'Safety notices',refresh:'Refresh',synthetic_demo:'Synthetic safety notices · Not real official notices',historical_sample:'Historical sample · Not the current situation',live:'Data received from API · On-site safety is not verified',cached_stale:'Refresh failed or delayed · Showing an earlier API response',limit:'Event status and hazard boundaries are unverified. English guidance uses rule templates and is not a full translation of the original notice.',original:'Korean original / synthetic examples labelled separately',guidance:'FLOW guidance · Rule template',source:'Source and API information',next:'Next development steps',nextCopy:'Exploration map, synthetic hazard demo, selection/save logs and evidence export are available. Next: real user testing and submission review. Safety and routes remain unverified.',error:'Unable to load data. Please try again.',empty:'No Busan notices returned. This does not confirm safety.',info:'Information',caution:'Caution',danger:'Danger',review:'Manual review required',unverified:'Current status unverified',fetched:'API received',latest:'Latest notice',none:'None',coverage:'Coverage',sample_only:'Sample only',partial_or_unknown:'Partial or unknown',complete_page:'One page within requested scope',loading:'Loading…'}
};
function node(tag, text, cls){const e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e;}
function render(){
  const w=words[lang];document.documentElement.lang=lang;$('language').textContent=lang==='ko'?'English':'한국어';
  $('busan-hero-caption').textContent=lang==='ko'?'부산 항구 풍경을 모티프로 한 AI 생성 일러스트 · 실시간 현장 사진이 아닙니다':'AI-generated illustration inspired by Busan harbor · Not a live photograph';
  $('busan-hero-image').alt=lang==='ko'?'부산의 바다와 항구, 해안 도시를 모티프로 만든 일러스트':'Illustration inspired by Busan’s sea, harbor and coastal city';
  $('title').textContent=w.title;$('title').style.whiteSpace='pre-line';$('intro').textContent=w.intro;$('list-title').textContent=w.list;$('refresh').textContent=w.refresh;$('next-title').textContent=w.next;$('next-copy').textContent=w.nextCopy;
  $('footer').textContent=lang==='ko'?'부산 FLOW · 원문 출처: 행정안전부 재난안전데이터공유플랫폼 · 개발용 미리보기':'Busan FLOW · Source: MOIS Safety Data Platform · Development preview';
  if(!snapshot)return;
  const reasons={unregistered_ip:['재난문자 API 오류 32: 현재 접속 IP가 등록되지 않았습니다. 이용신청의 허용 IP를 확인하세요.','Safety API error 32: the current public IP is not registered. Check the allowed IP in your service application.'],unregistered_key:['재난문자 API에 등록되지 않은 키입니다.','The safety API key is not registered.'],expired_key:['재난문자 API 키의 이용기간이 만료됐습니다.','The safety API key has expired.'],rate_limited:['재난문자 API 호출 한도를 초과했습니다.','The safety API request limit has been reached.']};
  $('api-reason').textContent=reasons[snapshot.failure_reason]?.[lang==='ko'?0:1]||'';
  $('mode').textContent=w[snapshot.source_mode];$('metadata').textContent=`${w.fetched}: ${snapshot.fetched_at||w.none} · ${w.latest}: ${snapshot.latest_alert_at||w.none} · ${w.coverage}: ${w[snapshot.coverage]}`;$('limit').textContent=w.limit;
  for(const id of ['alerts','common-alerts','other-alerts','alert-district-filters'])$(id).replaceChildren();
  $('status').textContent=snapshot.alerts.length?'':w.empty;
  const ko=lang==='ko',focus=snapshot.alerts.filter(a=>a.recipient_scope==='focus');
  const names={동구:'Dong-gu',중구:'Jung-gu',서구:'Seo-gu',영도구:'Yeongdo-gu'};
  $('focus-alert-title').textContent=ko?'부산 4개 구 안전문자':'Safety notices for four Busan districts';
  $('focus-alert-note').textContent=ko?'문자 수신지역 기준입니다. 발신기관·사건 발생지·위험 경계를 뜻하지 않습니다. 여러 구에 발송된 문자는 한 번만 표시합니다.':'Grouped by recipient district, not issuing authority, incident location or hazard boundary. Multi-district notices appear once.';
  for(const district of ['all','동구','중구','서구','영도구']){
    const count=district==='all'?focus.length:focus.filter(a=>a.target_districts.includes(district)).length;
    const label=district==='all'?(ko?'4개 구 전체':'All four'):(ko?district:names[district]);
    const button=node('button',`${label} (${count})`);button.type='button';button.setAttribute('aria-pressed',String(alertDistrict===district));button.addEventListener('click',()=>{alertDistrict=district;render();});$('alert-district-filters').append(button);
  }
  const shown=focus.filter(a=>alertDistrict==='all'||a.target_districts.includes(alertDistrict));
  $('focus-alert-status').textContent=shown.length?(ko?`${shown.length}건 표시 · 구별 건수에는 같은 문자가 중복 포함될 수 있습니다.`:`${shown.length} notices shown; district counts may overlap.`):(ko?'현재 수신된 조회 범위에 해당 구 문자가 없습니다. 안전이 확인되었다는 뜻은 아닙니다.':'No matching notices in the received query scope. This does not establish safety.');
  const common=snapshot.alerts.filter(a=>a.recipient_scope==='common'),other=snapshot.alerts.filter(a=>a.recipient_scope!=='focus'&&a.recipient_scope!=='common');
  $('common-alert-title').textContent=`${ko?'광역 공통 안내 · 부산 전체·전국 등':'Common notices · city-wide/national'} (${common.length})`;
  $('other-alert-title').textContent=`${ko?'그 밖의 지역 문자':'Other recipient areas'} (${other.length})`;
  for(const a of snapshot.alerts){
    if(a.recipient_scope==='focus'&&alertDistrict!=='all'&&!a.target_districts.includes(alertDistrict))continue;
    const target=a.recipient_scope==='focus'?'alerts':a.recipient_scope==='common'?'common-alerts':'other-alerts';
    const card=node('article','','card'),head=node('div','','card-head');
    head.append(node('span',w[a.severity],'badge '+a.severity),node('time',a.created_at));card.append(head);
    if(a.recipient_scope==='focus'){
      const regions=node('div','','recipient-badges');regions.append(node('strong',ko?'수신지역 ':'Recipient districts '));
      for(const district of a.target_districts)regions.append(node('span',ko?district:names[district],'badge district-badge'));card.append(regions);
    }
    card.append(node('h3',a.location_name||(lang==='ko'?'위치 확인 필요':'Location needs review')));
    card.append(node('p',w.original,'label'),node('p',a.original_message,'original'),node('p',w.guidance,'label'),node('p',lang==='ko'?a.flow_summary:a.guidance_en,'guidance'));
    card.append(node('p',`${a.official_emergency_level} · ${a.received_regions.join(', ')} · ${w.unverified}${a.requires_review?' · '+w.review:''}`,'meta'));
    const source=node('a',w.source);source.href=a.source_url;source.target='_blank';source.rel='noopener noreferrer';card.append(source);appendNoticeExtraction(card,a);appendAlertRegions(card,a);appendNoticeReview(card,a);$(target).append(card);
  }
  if(loadError){$('mode').textContent=w.cached_stale;$('status').textContent=w.error;}
}
async function refresh(){
  $('refresh').disabled=true;$('status').textContent=words[lang].loading;
  try{const r=await fetch('/api/alerts');if(!r.ok)throw new Error('unavailable');snapshot=await r.json();loadError=false;render();}
  catch{loadError=true;if(snapshot)render();$('status').textContent=words[lang].error;}
  finally{$('refresh').disabled=false;}
}
$('language').addEventListener('click',()=>{lang=lang==='ko'?'en':'ko';render();});$('refresh').addEventListener('click',refresh);render();refresh();
