(() => {
  const el=id=>document.getElementById(id);
  const node=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
  let version=0, saved=[], resultData=null, kind="all", visibleCount=12;
  try { const value=JSON.parse(localStorage.getItem('flow-visitor-saved')||'[]'); if(Array.isArray(value)) saved=value.filter(x=>x&&typeof x.key==='string'&&Array.isArray(x.names)&&x.names.every(n=>typeof n==='string')).slice(0,30); } catch {}
  function renderSaved(){
    const root=el('visitor-saved');root.replaceChildren();
    if(!saved.length)root.append(node('p','마음에 드는 후보를 저장해 보세요.'));
    for(const item of saved){const card=node('article','');card.className='card';card.append(node('h3',item.district),node('p',item.names.join(' · ')));const remove=node('button','삭제');remove.type='button';remove.addEventListener('click',()=>{const next=saved.filter(x=>x.key!==item.key);try{localStorage.setItem('flow-visitor-saved',JSON.stringify(next));saved=next;renderSaved();renderPlaces();}catch{el('visitor-status').textContent='저장 목록을 변경하지 못했습니다.';}});card.append(remove);root.append(card);}
  }
  async function notices(){
    try{const r=await fetch('/api/north-port');if(!r.ok)throw Error();const data=await r.json();window.FlowDataLab.render(data.analysis);const root=el('visitor-alerts');
      const earlier=node('details','');earlier.append(node('summary','이전 문자 3건 더 보기'));
      for(const record of [...data.records].reverse()){
        const card=node('details','');card.className='card';card.open=false;
        card.append(node('summary',`${record.CRT_DT} KST · ${record.MSG_CN.includes('공중보행로')?'보행로 통제 안내':'교통정체 안내'}`));
        card.append(node('blockquote',record.MSG_CN));
        const source=node('a','공식 출처');source.href=data.source_url;source.target='_blank';source.rel='noopener noreferrer';card.append(source);
        if([269127,269122].includes(record.SN))root.append(card);else earlier.append(card);
      }root.append(earlier);
    }catch{el('visitor-datalab').textContent='데이터랩 자료를 불러오지 못했습니다. 관광지 탐색은 계속 이용할 수 있습니다.';el('visitor-alerts').append(node('p','문자를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.'));}
  }
  function reset(){version++;resultData=null;visibleCount=12;el('visitor-courses').replaceChildren();window.FlowRoutes.clear();el('visitor-status').textContent='지역을 선택하고 대체 관광지를 찾아보세요.';}
  el('visitor-district').addEventListener('change',reset);
  el('visitor-load').addEventListener('click',async()=>{
    reset();const current=version;el('visitor-load').disabled=true;el('visitor-status').textContent='관광지를 찾고 있습니다…';
    try{const r=await fetch('/api/north-port/candidates?district='+encodeURIComponent(el('visitor-district').value));if(!r.ok)throw Error();const data=await r.json();if(current!==version)return;
      el('visitor-status').textContent=`${data.district}에서 함께 살펴볼 후보 ${data.courses.length}개`;
      resultData=data;renderPlaces();
    }catch{if(current===version)el('visitor-status').textContent='관광지를 불러오지 못했습니다. 다시 시도해 주세요.';}
    finally{el('visitor-load').disabled=false;}
  });

  function safePhoto(value){try{const u=new URL(value);if(!['http:','https:'].includes(u.protocol)||u.hostname!=='tong.visitkorea.or.kr'||u.username||u.password||u.port)return null;u.protocol='https:';return u.href;}catch{return null;}}
  function renderPlaces(){
    const root=el('visitor-courses');root.replaceChildren();
    if(!resultData){const blank=node('p','지역을 선택하면 새로운 부산을 보여드릴게요.');blank.className='explore-empty';root.append(blank);return;}
    const data=resultData, all=[...new Map((data.places || data.courses.flatMap(c=>c.places)).map(p=>[p.id,p])).values()];
    const places=all.filter(p=>kind==='all'||p.content_type===kind).sort((a,b)=>Number(a.content_type)-Number(b.content_type));
    el('visitor-status').textContent=`${data.district} · 둘러볼 장소 ${places.length}곳`;
    if(!places.length){const blank=node('p','이 유형의 장소가 없습니다. 다른 유형이나 지역을 선택해 주세요.');blank.className='explore-empty';root.append(blank);}
    for(const p of places.slice(0,visibleCount)){
      const card=node('article','');card.className='place-card';
      const photo=node('div','');photo.className='place-photo';
      const fallback=()=>{photo.replaceChildren();const theme=({'12':['◎','관광 · 산책','walk'],'14':['▥','문화 · 전시','culture'],'38':['▦','쇼핑 · 골목','shopping']})[p.content_type]||['◇','부산 둘러보기','walk'];const empty=node('div','');empty.className='photo-placeholder photo-theme-'+theme[2];const icon=node('b',theme[0]);icon.setAttribute('aria-hidden','true');empty.append(icon,node('span',theme[1]),node('strong',p.name),node('small','사진 준비 중 · 유형 안내 카드'));photo.append(empty);};
      const url=safePhoto(p.image_url);
      if(url){const img=document.createElement('img');img.src=url;img.alt=p.name;img.loading='lazy';img.referrerPolicy='no-referrer';img.addEventListener('error',fallback,{once:true});const credit=node('span','사진 · 한국관광공사');credit.className='photo-credit';photo.append(img,credit);}else fallback();
      const body=node('div','');body.className='place-content';const tag=node('span',p.type_name+' · '+data.district);tag.className='place-type';const address=node('p',p.address);address.className='meta';body.append(tag,node('h3',p.name),address);
      const actions=node('div','');actions.className='place-actions';
      const select=node('button','이곳으로 이동하기 ↗');select.type='button';select.disabled=!data.origin_place;select.setAttribute('aria-label',p.name+' 이동 방법 보기');
      select.addEventListener('click',()=>{window.FlowRoutes.clear();window.FlowRoutes.show({origin:data.origin_place,candidates:[{place:p}]},60,0);el('flow-map-section').scrollIntoView({behavior:'smooth'});});
      const key=data.district+':'+p.id, save=node('button',saved.some(x=>x.key===key)?'♥ 저장됨':'♡ 저장');save.type='button';save.setAttribute('aria-label',p.name+' 저장');save.setAttribute('aria-pressed',String(saved.some(x=>x.key===key)));
      save.addEventListener('click',()=>{if(saved.some(x=>x.key===key))return;const next=[{key,district:data.district,names:[p.name]},...saved].slice(0,30);try{localStorage.setItem('flow-visitor-saved',JSON.stringify(next));saved=next;renderSaved();renderPlaces();}catch{el('visitor-status').textContent='브라우저 저장 공간을 사용할 수 없습니다.';}});
      actions.append(select,save);body.append(actions);card.append(photo,body);root.append(card);
    }
    if(places.length>visibleCount){const more=node('button',`관광지 더 보기 · ${places.length-visibleCount}곳 남음`);more.type='button';more.className='places-more';more.addEventListener('click',()=>{visibleCount+=12;renderPlaces();});root.append(more);}
  }
  for(const button of document.querySelectorAll('#visitor-themes button'))button.addEventListener('click',()=>{kind=button.dataset.kind;visibleCount=12;for(const b of document.querySelectorAll('#visitor-themes button'))b.setAttribute('aria-pressed',String(b===button));window.FlowRoutes.clear();renderPlaces();});
  renderPlaces();renderSaved();notices();

})();
