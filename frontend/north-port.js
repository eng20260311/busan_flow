(() => {
  let generation = 0;
  const fmt = n => n == null ? '미제공' : Number(n).toLocaleString('ko-KR', {maximumFractionDigits:1});
  const day = d => `${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}`;
  function reset() {
    generation++; $('north-courses').replaceChildren(); window.FlowRoutes.clear();
    $('north-status').textContent = '조건 또는 기록 설정이 바뀌었습니다. 북항 대체 후보를 다시 조회하세요.';
  }
  window.resetNorthPort = reset;
  $('north-district').addEventListener('change', reset);
  document.querySelector('a[href="#trend-section"]').addEventListener('click', () => {$('other-tools').open = true;});
  async function init() {
    try {
      const response = await fetch('/api/north-port'); if (!response.ok) throw Error();
      const data = await response.json();
      const root = $('north-alerts');
      root.append(node('p', data.provenance, 'meta'));
      for (const r of data.records) {
        const card = node('details', '', 'card');
        if (r.SN === 269127 || r.SN === 269122) card.open = true;
        card.append(node('summary', `${r.CRT_DT} KST · ${r.EMRG_STEP_NM} · SN ${r.SN}`));
        card.append(node('p', '실제 발령 원문 · 수정하지 않은 기록', 'meta'), node('blockquote', r.MSG_CN), node('p', `수신지역: ${r.RCPTN_RGN_NM}`, 'meta'));
        const quote = r.MSG_CN.includes('공중보행로') ? '방문객께서는 일반도로 횡단보도를 이용해 주시기 바랍니다.' : r.MSG_CN.includes('차량 이용을 자제') ? '방문객께서는 차량 이용을 자제하고 가급적 대중교통을 이용하여 주시기 바랍니다.' : '방문객께서는 대중교통을 이용해 주시기 바랍니다.';
        if (r.MSG_CN.includes(quote)) card.append(node('strong', '당시 공식 행동요령 · 원문 발췌'), node('p', quote));
        card.append(node('p', 'FLOW 해석: 당시 안내를 확인하고 다른 지역의 관광정보를 탐색합니다. 현재 통제 해제·보행 동선 안전은 확인되지 않았습니다.', 'meta'));
        root.append(card);
      }
      const source=node('a','공식 데이터 출처 · 행정안전부');source.href=data.source_url;source.target='_blank';source.rel='noopener noreferrer';root.append(source);
      const a = data.analysis, stats = $('north-stats');
      if (!a) stats.append(node('p','방문 추이 자료 없음 · 통계 근거를 제시하지 않습니다.'));
      else {
        stats.append(node('p',`${day(a.start_date)} ~ ${day(a.end_date)} · 8주 · 이동통신 기반 일간 방문 추정값(명) · 수집 ${a.generated_at}`));
        const rows = a.series.map(s => {
          const p=s.points.at(-1);
          return [s.district, s.group==='2'?'외지인':'외국인',fmt(p.value),p.change_pct===null?'미산출':fmt(p.change_pct)+'%',`${s.points.length-s.missing_dates.length}/${s.points.length}`];
        });
        const wrap=node('div','','table-scroll');wrap.append(trendTable(['지역','구분','최근 제공일 추정값','이전 4주 같은 요일 대비','관측일'],rows));stats.append(wrap);
        const detail=node('details');detail.append(node('summary','4개 구 방문 추이 그래프 · 외지인과 외국인 별도'));
        for (const s of a.series) {detail.append(node('h4',`${s.district} · ${s.group==='2'?'외지인':'외국인'}`),trendChart(s.points,'value',`${s.district} 방문 추이`,'#087e72'));}stats.append(detail);
        stats.append(node('p','자료 기간은 9월 북항 사건 이전입니다. 현재 혼잡·사건 인과효과·실제 분산 실적으로 해석하지 않습니다. 지역·일자 간 고유 방문자 합산 없음.','meta'));
        const source=node('a','방문 통계 출처 · 한국관광공사');source.href=a.source_url;source.target='_blank';source.rel='noopener noreferrer';stats.append(source);
      }
      $('north-status').textContent='과거 사례 준비 완료 · 지역을 선택하고 후보를 살펴보세요.';
    } catch { $('north-status').textContent='북항 사례를 불러오지 못했습니다. 서버 연결을 확인하세요.'; }
  }
  $('north-load').addEventListener('click', async () => {
    reset(); const version=generation;
    $('north-load').disabled=true; $('north-status').textContent='저장된 실제 관광정보에서 후보를 구성하고 있습니다…';
    try {
      const params=new URLSearchParams({district:$('north-district').value});
      if (testSession) params.set('session_id',testSession.session_id);
      const r=await fetch('/api/north-port/candidates?'+params); if(!r.ok)throw Error();
      const data=await r.json(); if(version!==generation)return;
      $('north-status').textContent=`동구 북항 → ${data.district} · 후보 ${data.courses.length}개. ${data.scope}`;
      for(const [i,course] of data.courses.entries()) {
        const card=node('article','','card');card.append(node('h4',`북항 대체 후보 ${i+1} · ${data.district}`),node('p',data.reason));
        card.append(node('p',data.analysis_evidence?`근거 기간 ${day(data.analysis_evidence.start_date)} ~ ${day(data.analysis_evidence.end_date)} · 위 지역별 방문 추이 참고`:'방문 추이 근거 없음 · 관광정보만 표시','meta'));
        const list=node('ol');for(const p of course.places)list.append(node('li',`${p.name} · ${p.address} · 관광정보 수신 ${p.fetched_at}`));card.append(list);
        card.append(node('p',`장소 간 직선거리 합 ${course.straight_line_km}km · 실제 이동거리 아님 · 운영·혼잡·안전 미확인`,'meta'));
        const map=node('button',`후보 ${i+1} 지도·이동 비교`);map.type='button';map.disabled=!data.origin_place;
        map.addEventListener('click',()=>{
          window.FlowRoutes.clear();window.FlowRoutes.show({origin:data.origin_place,candidates:course.places.map(place=>({place}))},60);
          $('flow-map-note').textContent+=' 북항 TourAPI 대표좌표 기준이며 실제 출구가 아닙니다. 당시 육교 통제 반영 여부는 미검증입니다.';
          $('flow-map-section').scrollIntoView({behavior:'smooth'});
        });card.append(map);
        for(const action of ['select','save']) {
          const b=node('button',`북항 후보 ${i+1} ${action==='select'?'선택':'저장'}`);b.type='button';b.disabled=!testSession||!data.query_id;
          b.addEventListener('click',()=>recordCandidateAction(data,course,action,b));card.append(b);
        }
        $('north-courses').append(card);
      }
      if(!data.courses.length)$('north-courses').append(node('p','저장된 자료에서 후보를 구성하지 못했습니다. 관광정보 조회 도구에서 자료를 확보하세요.'));
      if(!data.origin_place)$('north-courses').append(node('p','북항 대표좌표 자료가 없어 이동 비교를 보류합니다.'));
    }catch{if(version===generation)$('north-status').textContent='후보 조회 실패 · 기록 세션 또는 서버 상태를 확인하세요.';}
    finally{$('north-load').disabled=false;}
  });
  init();
})();
