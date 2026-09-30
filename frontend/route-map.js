(() => {
  const visitor = document.body.dataset.view === 'visitor';
  const el = id => document.getElementById(id);
  let map, layer, epoch = 0, controller;
  const add = (parent, tag, value) => {
    const node = document.createElement(tag); node.textContent = value; parent.append(node); return node;
  };
  function clear() {
    epoch++; controller?.abort();
    layer?.clearLayers();
    el('flow-route-panel').replaceChildren(); el('flow-place-buttons').replaceChildren();
    el('flow-map-section').hidden = true;
  }
  function render(data, panel) {
    panel.replaceChildren();
    add(panel, 'h3', `${data.origin.name} → ${data.destination.name}`);
    add(panel, 'p', visitor ? '조회 시점의 예상시간입니다. 실제 통제와 현장 안내를 확인하세요.' : data.notice);
    if (!visitor) add(panel, 'p', `최대 ${data.max_minutes}분 기준 · 지하철·버스 구분은 TMAP 반환 경로 기준입니다. 부산교통공사 실시간 정보는 연결 전입니다.`);
    const grid = add(panel, 'div', ''); grid.className = 'flow-route-grid';
    const messages = {unconfigured: '연결 미설정 · 예상시간 미확인', unavailable: '조회 실패 · 다시 선택하여 재시도 가능',
      no_route: '제공사에서 사용 가능한 경로를 받지 못함', not_returned: '반환된 경로 중 이 수단의 경로 없음 · 운행 불가를 뜻하지 않음'};
    for (const group of data.groups) {
      const card = add(grid, 'article', ''); card.className = 'flow-route-option';
      add(card, 'h4', group.label);
      if (!visitor) add(card, 'p', `${group.source} · ${group.fetched_at || '조회시각 없음'}${group.cache_hit ? ' · 5분 내 캐시' : ''}`);
      if (!group.routes.length) add(card, 'p', messages[group.status] || '이동정보 미확인');
      for (const [index, route] of group.routes.entries()) {
        const details = add(card, 'details', '');
        add(details, 'summary', visitor ? `약 ${Math.ceil(route.total_seconds / 60)}분 · 경로 보기` : `③ 경로 ${index + 1} 확인 · 약 ${Math.ceil(route.total_seconds / 60)}분 · ${route.within_limit ? '시간 조건 충족' : '시간 조건 초과'}`);
        if (group.mode === 'car') add(details, 'p', `약 ${(route.distance_m / 1000).toFixed(1)}km · 주차·승하차 시간 제외`);
        else add(details, 'p', `도보 약 ${Math.ceil(route.walk_seconds / 60)}분 · 환승 ${route.transfers}회`);
        const list = add(details, 'ol', '');
        for (const leg of route.segments) {
          const labels = {WALK:'도보', SUBWAY:'지하철', BUS:'버스', CAR:'자동차'};
          add(list, 'li', `${labels[leg.mode]} ${leg.route || ''}${leg.start ? ` · ${leg.start} → ${leg.end}` : ''} · 약 ${Math.ceil(leg.seconds / 60)}분`);
        }
        if (!route.segments.length) add(details, 'p', '제공사 상세 구간 없음 · 외부 길찾기에서 확인하세요.');
        add(details, 'p', '예상 소요시간이며 안전한 이동경로로 검증된 결과가 아닙니다.');
      }
      const link = add(card, 'a', `카카오맵에서 ${group.mode === 'car' ? '자동차' : '대중교통'} 길찾기 열기`);
      link.href = group.external_url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      link.dataset.mapViewer = 'true';
    }
    if (!visitor) add(panel, 'p', '카카오맵은 닫기 버튼이 있는 팝업으로 열립니다. 출발·도착지만 전달해 새로 검색하므로 위 경로와 다를 수 있으며 지하철/버스 전용 선택은 전달하지 않습니다. 카카오T 택시 호출 기능은 포함하지 않습니다.');
  }
  function show(data, maxMinutes, selectedIndex) {
    if (!data.origin || !data.candidates.length) return;
    el('flow-map-section').hidden = false;
    el('flow-map-note').textContent = visitor ? '장소를 선택하면 이동시간을 비교할 수 있어요. 북항 대표위치 기준이며 실제 출구와 다를 수 있습니다.' : '출발지와 관광지 위치만 표시합니다. 마커 또는 아래 장소 버튼을 선택하세요. 경로·위험구역 지도는 아닙니다.';
    const buttons = [];
    async function select(candidate, index) {
      controller?.abort(); controller = new AbortController();
      const version = ++epoch;
      buttons.forEach((button, i) => button.setAttribute('aria-pressed', String(i === index)));
      const panel = el('flow-route-panel'); panel.replaceChildren();
      add(panel, 'h3', `② ${candidate.place.name} 이동정보 조회 중…`);
      const point = p => ({name:p.name, latitude:p.latitude, longitude:p.longitude});
      try {
        const response = await fetch('/api/route-comparison', {method:'POST', signal:controller.signal,
          headers:{'Content-Type':'application/json'}, body:JSON.stringify({origin:point(data.origin), destination:point(candidate.place), max_minutes:maxMinutes})});
        if (!response.ok) throw Error('request_failed');
        const comparison = await response.json();
        if (version !== epoch) return;
        render(comparison, panel);
      } catch (error) {
        if (version === epoch && error.name !== 'AbortError') {
          panel.replaceChildren(); add(panel, 'p', '이동정보를 불러오지 못했습니다. 장소 버튼을 눌러 다시 시도하세요.');
        }
      }
    }
    data.candidates.forEach((candidate, index) => {
      const button = add(el('flow-place-buttons'), 'button', `${index + 1}. ${candidate.place.name}`);
      button.type = 'button'; button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', () => select(candidate, index)); buttons.push(button);
    });
    add(el('flow-route-panel'), 'p', '지도 마커 또는 장소 버튼을 선택하면 이동수단을 비교합니다.');
    if (Number.isInteger(selectedIndex) && data.candidates[selectedIndex]) select(data.candidates[selectedIndex], selectedIndex);
    if (!window.L) {
      el('flow-map-note').textContent = '지도를 불러오지 못했습니다. 아래 장소 버튼으로 이동정보를 비교하세요.'; return;
    }
    if (!map) {
      map = L.map('flow-map', {scrollWheelZoom:false}).setView([35.16,129.1],12);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:19,
        attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'})
        .on('tileerror', () => { el('flow-map-note').textContent = '배경 지도 일부를 불러오지 못했습니다. 장소 버튼으로 선택할 수 있습니다.'; }).addTo(map);
      layer = L.layerGroup().addTo(map);
    }
    layer.clearLayers();
    const origin = [data.origin.latitude, data.origin.longitude];
    const label = document.createElement('span'); label.textContent = `출발: ${data.origin.name}`;
    L.marker(origin, {title:`출발: ${data.origin.name}`,
      icon:L.divIcon({className:'candidate-pin flow-origin-pin', html:'출', iconSize:[30,30]})}).bindPopup(label).addTo(layer);
    const bounds = [origin];
    data.candidates.forEach((candidate, index) => {
      const p = candidate.place, coords = [p.latitude,p.longitude]; bounds.push(coords);
      const label = document.createElement('span'); label.textContent = p.name;
      L.marker(coords, {title:`${index + 1}. ${p.name} 이동 비교`,
        icon:L.divIcon({className:'candidate-pin', html:String(index + 1), iconSize:[30,30]})})
        .bindPopup(label).on('click', () => select(candidate, index))
        .on('keypress', event => { if (event.originalEvent.key === 'Enter') select(candidate, index); }).addTo(layer);
    });
    map.invalidateSize(); map.fitBounds(bounds, {padding:[30,30], maxZoom:15});
  }
  window.FlowRoutes = {clear, show};
})();
