let testSession=null;
try{testSession=JSON.parse(sessionStorage.getItem('flow-test-session')||'null');}catch{}
function testState(){
 window.resetNorthPort?.();
 if(testSession){$('test-mode').value=testSession.mode;$('test-consent').checked=true;}
 for(const id of ['test-mode','test-consent','start-test'])$(id).disabled=!!testSession;
 $('stop-test').disabled=!testSession;
 $('test-status').textContent=testSession?`${testSession.mode==='developer'?'개발 검증':'실제 사용자 테스트(선언 모드)'} 기록 중 · 새로 구성한 후보부터 기록합니다.`:'기록 꺼짐 · 기록 시작 후 후보를 다시 구성하면 선택·저장할 수 있습니다.';
}
async function savedCandidates(){
 const root=$('saved-candidates');root.replaceChildren();
 if(!testSession){root.append(node('p','진행 중인 기록 세션이 없습니다.'));return;}
 try{const r=await fetch('/api/saved-candidates/'+encodeURIComponent(testSession.session_id));if(!r.ok)throw Error();const data=await r.json();
 if(!data.saved.length)root.append(node('p','저장한 후보가 없습니다.'));
 for(const item of data.saved){const card=node('article','','card');card.append(node('strong',`${item.origin} → ${item.district} · ${item.scenario==='north_port_historical'?'북항 과거 실제 사례':item.is_synthetic_risk_demo?'합성 위험구역 시연':'일반 탐색'}`),node('p',item.course.places.map(p=>p.name).join(' → ')),node('p',`저장 시각 ${item.saved_at} · 안전·경로 미검증`,'meta'));root.append(card);}
 }catch{root.append(node('p','저장 목록을 불러오지 못했습니다. 기록 세션과 서버 연결을 확인하세요.'));}
}
async function recordCandidateAction(data,course,action,button){
 if(!testSession||!data.query_id){$('test-status').textContent='기록 동의 후 후보를 다시 구성해 주세요.';return;}
 button.disabled=true;
 try{const r=await fetch('/api/interactions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:testSession.session_id,query_id:data.query_id,candidate_id:course.id,action})});if(!r.ok)throw Error();const result=await r.json();button.textContent=action==='save'?'저장됨':'선택 기록됨';
 $('test-status').textContent=result.recorded?'기록을 저장했습니다. 실제 방문이나 분산 효과를 의미하지 않습니다.':'이미 기록된 동작입니다. 중복 집계하지 않았습니다.';
 if(action==='save')await savedCandidates();
 }catch{button.disabled=false;$('test-status').textContent='기록하지 못했습니다. 연결을 확인한 뒤 다시 시도하세요.';}
}
$('start-test').addEventListener('click',async()=>{
 if(!$('test-consent').checked){$('test-status').textContent='기록 내용을 확인하고 동의해 주세요.';return;}
 $('start-test').disabled=true;
 try{const r=await fetch('/api/test-sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({consent:true,mode:$('test-mode').value})});if(!r.ok)throw Error();testSession=await r.json();sessionStorage.setItem('flow-test-session',JSON.stringify(testSession));testState();clearCandidates();await savedCandidates();}
 catch{$('test-status').textContent='기록 시작에 실패했습니다.';$('start-test').disabled=false;}
});
$('stop-test').addEventListener('click',async()=>{
 try{const r=await fetch('/api/test-sessions/'+encodeURIComponent(testSession.session_id),{method:'DELETE'});if(!r.ok)throw Error();testSession=null;sessionStorage.removeItem('flow-test-session');$('test-consent').checked=false;testState();clearCandidates();await savedCandidates();}
 catch{$('test-status').textContent='기록 종료에 실패했습니다. 다시 시도하세요.';}
});
async function evidenceSummary(){
 const root=$('evidence-summary');root.replaceChildren();
 try{const r=await fetch('/api/evidence/summary');if(!r.ok)throw Error();const data=await r.json();
 root.append(node('p',data.definition),node('p',data.limitations,'meta'));
 if(!data.groups.some(g=>g.mode==='user_test'))root.append(node('strong','실제 사용자 테스트 기록 없음 · 사용자 성과 미확보'));
 for(const g of data.groups)root.append(node('p',`${g.mode==='developer'?'개발 검증':'실제 사용자 테스트(선언 모드)'} / ${g.scenario==='north_port_historical'?'북항 과거 실제 사례':g.scenario==='none'?'일반 탐색':'합성 시연 '+g.scenario}: 세션 ${g.sessions}, 조회 ${g.view}, 선택 ${g.select}, 저장 ${g.save}`));
 }catch{root.append(node('p','집계를 불러오지 못했습니다.'));}
}
$('refresh-evidence').addEventListener('click',evidenceSummary);testState();savedCandidates();
