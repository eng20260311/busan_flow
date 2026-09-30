function appendNoticeExtraction(card,alert){
 const start=node('button','이 문자로 장소 찾기');start.type='button';start.addEventListener('click',()=>startNoticeJourney(alert));card.append(start);
 const data=alert.extraction;if(!data)return;
 const panel=node('details','','notice-review');
 panel.append(node('summary','문자 자동 추출 · 미검증'));
 panel.append(node('p','원문 표현을 규칙으로 추출했습니다. LLM·지도 대조는 사용하지 않았으며 발생·해제·안전 여부를 확정하지 않습니다.','meta'));
 const groups=[['places','장소명 후보'],['event_types','재난·안내 유형 표현'],['actions','통제·우회·대피·해제 표현'],['time_expressions','시간 표현'],['scope_expressions','범위 표현']];
 for(const [key,title] of groups){
  panel.append(node('h4',title));
  const items=data[key];
  if(!items.length){panel.append(node('p','인식된 표현 없음 · 원문 확인 필요','meta'));continue;}
  const list=node('ul');
  for(const item of items){const li=node('li');li.append(node('strong',`${item.label}: ${item.text}`));const proof=node('details');proof.append(node('summary','원문 근거 보기'),node('p',item.evidence,'original'));li.append(proof);list.append(li);}panel.append(list);
 }
 for(const text of data.limitations)panel.append(node('p',text,'meta'));
 panel.append(node('p',`추출 규칙 ${data.version} · 처리 시각 ${data.processed_at} · 수동 검토 기록과 별도`,'meta'));
 card.append(panel);
}
