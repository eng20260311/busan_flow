(() => {
  const form = document.getElementById('flow-form');
  const result = document.getElementById('flow-result');
  const status = document.getElementById('flow-status');
  const button = document.getElementById('flow-submit');
  let generation = 0;
  function text(parent, tag, value) {
    const node = document.createElement(tag);
    node.textContent = value;
    parent.appendChild(node);
    return node;
  }
  const modes = {live: 'API 수신', api: 'API·유효 캐시', cached_stale: '오래된 수신 기록', synthetic_demo: '합성 예시', historical_sample: '과거 샘플', unavailable: '조회 실패', unconfigured: '연결 미설정'};
  form.addEventListener('input', () => {
    generation++;
    window.FlowRoutes.clear();
    result.replaceChildren();
    status.textContent = '입력값이 바뀌었습니다. 다시 조회하세요.';
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const version = ++generation;
    button.disabled = true;
    window.FlowRoutes.clear();
    result.replaceChildren();
    status.textContent = '안전문자와 관광정보를 확인하고 이동정보를 비교하고 있습니다.';
    try {
      const response = await fetch('/api/recommendations', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
        message: document.getElementById('flow-message').value,
        origin_district: document.getElementById('flow-origin-district').value,
        origin_name: document.getElementById('flow-origin-name').value,
        max_minutes: Number(document.getElementById('flow-minutes').value)
      })});
      if (!response.ok) throw new Error('request_failed');
      const data = await response.json();
      if (version !== generation) return;
      status.textContent = data.message;
      window.FlowRoutes.show(data, Number(document.getElementById('flow-minutes').value));
      const intentLabel = data.intent.mode === 'llm' ? 'LLM 연결 성공' : data.intent.status === 'unconfigured' ? '규칙 기반 · LLM 연결 미설정' : '규칙 기반 · LLM 조회 실패';
      text(result, 'p', `의도 해석: ${intentLabel} · 혼잡 근거: 사용자 제보, 실시간 측정 아님`);
      if (data.origin) text(result, 'p', `출발: ${data.origin.name} · ${data.origin.coordinate_basis}`);
      text(result, 'p', `안전문자: ${modes[data.safety.source_mode] || data.safety.source_mode} · 수신 ${data.safety.fetched_at || '미확인'} · 범위 ${data.safety.coverage || '미확인'}`);
      const notices = document.createElement('details');
      result.appendChild(notices);
      text(notices, 'summary', `안전문자 원문 ${data.safety.alerts.length}건 · 현재 사건 상태 미검증`);
      for (const alert of data.safety.alerts) {
        text(notices, 'p', `${alert.created_at} · ${alert.official_emergency_level}`);
        text(notices, 'blockquote', alert.original_message);
      }
      for (const [index, candidate] of data.candidates.entries()) {
        const card = document.createElement('article');
        card.className = 'flow-candidate';
        result.appendChild(card);
        text(card, 'h3', `${index + 1}. ${candidate.place.name} · ${candidate.place.district}`);
        text(card, 'p', candidate.place.address);
        text(card, 'p', candidate.reason);
        const mobility = candidate.mobility;
        const route = mobility.routes[0];
        if (route) {
          text(card, 'p', `조회 경로 중 최단: 약 ${Math.ceil(route.total_seconds / 60)}분 · 총 도보 ${Math.ceil(route.walk_seconds / 60)}분 · 환승 ${route.transfers}회`);
          if (candidate.transit_within_limit === false) text(card, 'p', '조회 대중교통 경로는 요청 이동시간 초과 · 자동차 비교는 지도에서 장소를 선택하세요.');
          text(card, 'p', `지하철 포함 ${route.uses_subway ? '예' : '아니요'} · 버스 포함 ${route.uses_bus ? '예' : '아니요'}`);
          const legs = document.createElement('ol'); card.appendChild(legs);
          const labels = {WALK: '도보', SUBWAY: '지하철', BUS: '버스'};
          for (const leg of route.segments) text(legs, 'li', `${labels[leg.mode]} ${leg.route} · ${leg.start} → ${leg.end} · 약 ${Math.ceil(leg.seconds / 60)}분`);
          text(card, 'p', `TMAP 조회 ${mobility.fetched_at}${mobility.cache_hit ? ' · 5분 내 캐시' : ''} · 제공사 예상시간, 실시간 도착·운행 및 경로 안전 미확인`);
        } else {
          text(card, 'p', `지하철·버스·이동시간 미확인: ${mobility.status === 'unconfigured' ? 'TMAP 연결 미설정' : mobility.status === 'no_route' ? '조회 경로 없음' : '조회 실패'}. 최대 이동시간 충족 여부도 미확인입니다.`);
        }
        text(card, 'p', `직선거리 ${candidate.straight_line_km}km · 혼잡·운영·위험구역·경로 안전 미검증`);
        const link = text(card, 'a', '장소 위치 지도');
        link.href = `https://www.openstreetmap.org/?mlat=${candidate.place.latitude}&mlon=${candidate.place.longitude}#map=16/${candidate.place.latitude}/${candidate.place.longitude}`;
        link.target = '_blank'; link.rel = 'noopener noreferrer';
      }
      for (const item of data.excluded) text(result, 'p', `후보 제외: ${item.name} · ${item.reason}`);
    } catch (_) {
      if (version === generation) status.textContent = '조회하지 못했습니다. 연결과 입력값을 확인하고 다시 시도하세요.';
    } finally { button.disabled = false; }
  });
})();
