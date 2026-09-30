const reviewDrafts=new Map();
function appendNoticeReview(card,alert){
 if(!alert.review_key)return;
 const details=node('details','','notice-review');details.append(node('summary','문자별 위치·범위 검토 기록 (로컬 관리자용)'));
 const note=node('p','수동 검토 기록입니다. 저장해도 안전 확인·통제 해제·위험필터 적용이 자동으로 이루어지지 않습니다. 원문이 변경되면 새 검토 대상으로 분리합니다.','meta');details.append(note);
 const state=node('p');state.setAttribute('role','status');details.append(state);
 const form=node('form'),inputs={},fields=[['place','확인한 장소','text'],['latitude','위도','number'],['longitude','경도','number'],['area','공식 구역·도로 구간 / 해제 확인 범위','textarea'],['evidence_url','근거 URL (http/https)','url'],['document','근거 문서명·문서번호·쪽 / 확인 근거','textarea'],['published_at','근거 발행 시각 (한국시간)','datetime-local'],['reviewer','검토자 이름 또는 내부 식별명','text'],['status','확인 상태','select'],['recheck_at','재확인 시점 (한국시간)','datetime-local']];
 const labels={unverified:'미확인',location:'위치 확인',area:'범위 확인',released:'해제 확인'};
 for(const [name,title,type] of fields){const label=node('label',title);const input=node(type==='textarea'?'textarea':type==='select'?'select':'input');if(type!=='textarea'&&type!=='select')input.type=type;if(type==='number')input.step='any';if(name==='latitude'){input.min=-90;input.max=90;}if(name==='longitude'){input.min=-180;input.max=180;}
 if(type==='select')for(const [value,text] of Object.entries(labels)){const option=node('option',text);option.value=value;input.append(option);}
 input.setAttribute('aria-label',title);if(['reviewer','recheck_at'].includes(name))input.required=true;
 label.append(input);form.append(label);inputs[name]=input;}
 const map=node('a','입력 좌표 지도 확인');map.target='_blank';map.rel='noopener noreferrer';map.hidden=true;form.append(map);
 const updateMap=()=>{const lat=Number(inputs.latitude.value),lon=Number(inputs.longitude.value);map.hidden=inputs.latitude.value===''||inputs.longitude.value===''||!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180;if(!map.hidden)map.href=`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=17/${lat}/${lon}`;};
 const save=node('button','검토 기록 저장');save.type='submit';const reload=node('button','저장 기록 다시 불러오기 · 입력 초기화');reload.type='button';form.append(save,reload);
 const history=node('div');details.append(form,history);card.append(details);
 let revision=0,loaded=false;
 const localDate=value=>value?new Date(new Date(value).getTime()+9*3600000).toISOString().slice(0,16):'';
 function show(data){
  const latest=data.latest;revision=latest?.revision||0;
  state.textContent=latest?`${labels[latest.status]} · 검토자 ${latest.reviewer} · 검토 시각 ${latest.reviewed_at} · 재확인 ${latest.recheck_at}${data.recheck_due?' · 재확인 기한 경과: 다시 검토 필요':''}`:'저장된 검토 없음 · 미확인';
  for(const [name,input] of Object.entries(inputs))input.value=['published_at','recheck_at'].includes(name)?localDate(latest?.[name]):latest?.[name]??(name==='status'?'unverified':'');
  const draft=reviewDrafts.get(alert.review_key);if(draft){for(const [name,value] of Object.entries(draft.values))inputs[name].value=value;revision=draft.revision;state.textContent+=' · 저장하지 않은 입력 복원';}
  updateMap();history.replaceChildren();
  if(data.history.length){const h=node('details');h.append(node('summary',`검토 이력 ${data.history.length}건`));for(const r of data.history){const item=node('article','','card');item.append(node('strong',`#${r.revision} ${labels[r.status]} · ${r.reviewer}`),node('p',`검토 ${r.reviewed_at} / 재확인 ${r.recheck_at}`,'meta'),node('p',`장소: ${r.place||'미입력'} · 좌표 ${r.latitude??'없음'}, ${r.longitude??'없음'}`),node('p',`범위: ${r.area||'미입력'}`),node('p',`근거: ${r.evidence_url||''} ${r.document||''} · 발행 ${r.published_at||'미입력'}`));h.append(item);}history.append(h);}
 }
 async function load(){save.disabled=true;state.textContent='검토 기록 확인 중…';try{const r=await fetch('/api/notice-reviews/'+alert.review_key);if(!r.ok)throw Error();show(await r.json());loaded=true;}catch{state.textContent='검토 기록을 불러오지 못했습니다.';}finally{save.disabled=!loaded;}}
 form.addEventListener('input',()=>{reviewDrafts.set(alert.review_key,{revision,values:Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,v.value]))});updateMap();});
 details.addEventListener('toggle',()=>{if(details.open&&!loaded)load();});reload.addEventListener('click',()=>{reviewDrafts.delete(alert.review_key);load();});
 form.addEventListener('submit',async event=>{event.preventDefault();if(!loaded)return;save.disabled=true;
 const body={revision};for(const [name,input] of Object.entries(inputs)){body[name]=['latitude','longitude'].includes(name)?(input.value===''?null:Number(input.value)):['published_at','recheck_at'].includes(name)?(input.value?input.value+':00+09:00':null):input.value;}
 try{const r=await fetch('/api/notice-reviews/'+alert.review_key,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok){state.textContent=typeof data.detail==='string'?data.detail:(data.detail||[]).map(e=>e.msg).join(' / ');return;}reviewDrafts.delete(alert.review_key);show(data);state.textContent='저장 완료 · '+state.textContent;}
 catch{state.textContent='저장에 실패했습니다. 입력은 유지됩니다.';}finally{save.disabled=false;}
 });
}
