(() => {
  const districts = ['동구', '중구', '서구', '영도구'];
  const dateLabel = s => `${s.slice(0,4)}.${s.slice(4,6)}.${s.slice(6,8)}`;
  const number = v => v === null ? '자료 없음' : Math.round(v).toLocaleString('ko-KR');
  function weekly(analysis, group) {
    const start = analysis?.start_date || '';
    if (!/^\d{8}$/.test(start) || !Array.isArray(analysis?.series)) return [];
    const startMs = Date.UTC(+start.slice(0,4), +start.slice(4,6)-1, +start.slice(6,8));
    const rows = [];
    for (let w=0;w<8;w++) {
      const dates = Array.from({length:7},(_,d)=>new Date(startMs+(w*7+d)*86400000).toISOString().slice(0,10).replaceAll('-',''));
      if (dates[6] > analysis.end_date) break;
      const values = districts.map(district => {
        const points = analysis.series.find(s=>s.district===district && s.group===group)?.points || [];
        const vals = dates.map(date=>points.find(p=>p.date===date)?.value);
        if(vals.some(v=>v===null || v===undefined || v==='' || !Number.isFinite(Number(v)) || Number(v)<0)) return null;
        return vals.reduce((a,v)=>a+Number(v),0)/7;
      });
      rows.push({start:dates[0],end:dates[6],values});
    }
    return rows;
  }
  function render(analysis) {
    const root=document.getElementById('visitor-datalab');
    const node=(tag,text,cls)=>{const e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e;};
    root.replaceChildren();
    root.append(node('h3','한국관광 데이터랩으로 살펴본 지역별 방문 추이'));
    if(!analysis?.series?.length){root.append(node('p','비교할 과거 방문 자료가 없습니다.'));return;}
    root.append(node('p',`${dateLabel(analysis.start_date)}–${dateLabel(analysis.end_date)} · 저장된 과거 통계`,'datalab-meta'));
    const label=node('label','방문자 구분 '),select=document.createElement('select');
    for(const [v,t] of [['2','외지인'],['3','외국인']]){const o=node('option',t);o.value=v;select.append(o);}label.append(select);root.append(label);
    const content=node('div','');root.append(content);
    const draw=()=>{
      content.replaceChildren();const rows=weekly(analysis,select.value),last=rows.at(-1),prev=rows.at(-2);
      if(!last){content.append(node('p','7일 단위로 비교할 자료가 없습니다.'));return;}
      content.append(node('p',`${dateLabel(last.start)}–${dateLabel(last.end)} 일평균 방문자 추정치 · 명`,'datalab-meta'));
      const grid=node('div','','datalab-grid');
      districts.forEach((district,i)=>{
        const card=node('div','','datalab-region');card.append(node('b',district+(i===0?' · 북항 출발 지역':'')),node('strong',number(last.values[i])));
        const current=last.values[i],before=prev?.values[i];
        const change=current!==null && before!==null && before!==undefined && before>0 ? (current/before-1)*100 : null;
        card.append(node('span',change===null?'직전 7일 비교 불가':`직전 7일 대비 ${change>0?'+':''}${change.toFixed(1)}%`));
        if(i>0){const button=node('button',`${district} 관광지 보기`);button.type='button';button.addEventListener('click',()=>{const districtSelect=document.getElementById('visitor-district');districtSelect.value=district;districtSelect.dispatchEvent(new Event('change'));document.getElementById('visitor-load').click();});card.append(button);}grid.append(card);
      });content.append(grid);
      const detail=document.createElement('details');detail.append(node('summary','8주 방문 추이 비교 보기'));
      const wrap=node('div','','datalab-table-wrap'),table=document.createElement('table');table.append(node('caption',`${select.options[select.selectedIndex].text} · 각 7일 구간의 일평균 방문자 추정치(명)`));
      const head=document.createElement('thead'),hr=document.createElement('tr');for(const title of ['기간',...districts]){const th=node('th',title);th.scope='col';hr.append(th);}head.append(hr);table.append(head);
      const body=document.createElement('tbody');rows.forEach(row=>{const tr=document.createElement('tr'),th=node('th',`${dateLabel(row.start).slice(5)}–${dateLabel(row.end).slice(5)}`);th.scope='row';tr.append(th);row.values.forEach(v=>tr.append(node('td',number(v))));body.append(tr);});table.append(body);wrap.append(table);detail.append(wrap,node('p','7일 모두 값이 있을 때만 평균을 계산하며, 표시값은 반올림합니다. 구간별·지역별 방문자는 중복될 수 있어 합산하지 않습니다.','datalab-meta'));content.append(detail);
    };select.addEventListener('change',draw);draw();
    root.append(node('p','방문 추이를 비교해 둘러볼 지역을 선택해 보세요. 과거 방문량은 현재 혼잡도·운영 여부·안전성을 뜻하지 않습니다.','datalab-note'));
    const source=node('a','출처: 한국관광 데이터랩 · 지역별 방문자수 API ↗');source.href='https://www.data.go.kr/data/15101972/openapi.do';source.target='_blank';source.rel='noopener noreferrer';root.append(source);
  }
  if(typeof window!=='undefined')window.FlowDataLab={render};
  if(typeof module!=='undefined')module.exports={weekly};
})();
