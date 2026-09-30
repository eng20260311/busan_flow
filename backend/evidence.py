"""Local opt-in event journal. Counts interactions, never visits or unique people."""
import csv
import hashlib
import io
import json
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class EvidenceStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, mode TEXT NOT NULL, created TEXT NOT NULL, active INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS queries(id TEXT PRIMARY KEY, session TEXT NOT NULL REFERENCES sessions(id), created TEXT NOT NULL, snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(query_id TEXT NOT NULL REFERENCES queries(id), candidate TEXT NOT NULL, action TEXT NOT NULL, created TEXT NOT NULL, UNIQUE(query_id,candidate,action));
            ''')

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def start(self, consent, mode):
        if consent is not True or mode not in ('developer', 'user_test'):
            raise ValueError('consent_required')
        session = str(uuid.uuid4())
        with self.connect() as db:
            db.execute('INSERT INTO sessions VALUES (?,?,?,1)', (session, mode, now()))
        return {'session_id': session, 'mode': mode}

    def check(self, session):
        with self.connect() as db:
            row = db.execute('SELECT * FROM sessions WHERE id=? AND active=1',(session,)).fetchone()
        if not row:
            raise ValueError('invalid_session')
        return row

    def stop(self, session):
        self.check(session)
        with self.connect() as db:
            db.execute('UPDATE sessions SET active=0 WHERE id=?',(session,))

    def record_query(self, session, data):
        self.check(session)
        query = str(uuid.uuid4())
        with self.connect() as db:
            db.execute('INSERT INTO queries VALUES (?,?,?,?)',(query, session, now(), json.dumps(data,ensure_ascii=False)))
            db.execute('INSERT INTO events VALUES (?,?,?,?)',(query,'','view',now()))
        return query

    def event(self, session, query, candidate, action):
        self.check(session)
        if action not in ('select','save'):
            raise ValueError('invalid_action')
        with self.connect() as db:
            row=db.execute('SELECT snapshot FROM queries WHERE id=? AND session=?',(query,session)).fetchone()
            if not row or candidate not in {c['id'] for c in json.loads(row['snapshot'])['courses']}:
                raise ValueError('unknown_candidate')
            changed=db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?)',(query,candidate,action,now())).rowcount
        return {'recorded':bool(changed),'action':action}

    def saved(self, session):
        self.check(session)
        with self.connect() as db:
            rows=db.execute("SELECT q.snapshot,e.candidate,e.created FROM events e JOIN queries q ON q.id=e.query_id WHERE q.session=? AND e.action='save' ORDER BY e.created DESC",(session,)).fetchall()
        result=[]
        for row in rows:
            data=json.loads(row['snapshot'])
            result.append({'saved_at':row['created'],'origin':data['origin'],'district':data['district'],
                           'scenario':data['risk']['scenario'],'is_synthetic_risk_demo':data['risk']['is_synthetic'],
                           'course':next(c for c in data['courses'] if c['id']==row['candidate'])})
        return result

    def summary(self):
        with self.connect() as db:
            rows=db.execute('SELECT s.mode,q.id,q.session,q.snapshot,e.action,e.candidate FROM events e JOIN queries q ON q.id=e.query_id JOIN sessions s ON s.id=q.session').fetchall()
        groups={}
        for row in rows:
            snapshot=json.loads(row['snapshot']);scenario=snapshot['risk']['scenario']
            key=(row['mode'],scenario)
            g=groups.setdefault(key,{'mode':key[0],'scenario':scenario,'sessions':set(),'queries':set(),'view':0,'select':0,'save':0})
            g['sessions'].add(row['session']);g['queries'].add(row['id']);g[row['action']]+=1
        results=[{**g,'sessions':len(g['sessions']),'queries':len(g['queries'])} for _,g in sorted(groups.items())]
        return {'generated_at':now(),'groups':results,
                'definition':'조회 완료 요청 수와 후보별 선택·저장 이벤트. 동일 조회·후보·동작 중복은 1건. 세션은 참여자 수가 아님.',
                'limitations':'모드는 기록자가 선언합니다. 실제 사용자 신원·고유 인원·방문·분산 효과·만족도를 검증하지 않습니다.'}

    def bundle(self, root):
        summary=self.summary()
        files={'interaction_summary.json':json.dumps(summary,ensure_ascii=False,indent=2).encode('utf-8')}
        output=io.StringIO();writer=csv.DictWriter(output,fieldnames=['mode','scenario','sessions','queries','view','select','save']);writer.writeheader();writer.writerows(summary['groups'])
        files['interaction_summary.csv']=output.getvalue().encode('utf-8-sig')
        names=['NORTH_PORT_CASE_STUDY.md','DEMO_SCRIPT.md','SUBMISSION_CHECKLIST.md','YEONGDO_WEEKEND_ANALYSIS.md','VISITOR_TRENDS.md','EXPLORATION_CANDIDATES.md','HAZARD_DEMO.md','EVIDENCE_GUIDE.md','MAP_ROUTE_FLOW.md']
        for name in names:
            path=Path(root)/'docs'/name
            if path.exists():files['docs/'+name]=path.read_bytes()
        for name in ['analyze_yeongdo_weekends.py']:
            path=Path(root)/'tools'/name
            if path.exists():files['reproduce/'+name]=path.read_bytes()
        provenance=[]
        for name in ['visitor_trends.json','yeongdo_weekend_sensitivity.json','candidate_check.json']:
            path=Path(root)/'data/runtime'/name
            if path.exists():
                provenance.append({'local_source':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                                   'note':'로컬 입력 식별용 해시. 원본 API 응답을 이 ZIP에 포함하지 않음.'})
        files['source_provenance.json']=json.dumps(provenance,ensure_ascii=False,indent=2).encode('utf-8')
        # Reviewed public fields and curated captures only; never export private folders.
        for name in ['data/north_port_case.json','artifacts/north-port/validation.json','artifacts/north-port/visitor_analysis.json','artifacts/north-port/candidates.json']:
            path=Path(root)/name
            if path.exists(): files[name]=path.read_bytes()
        for name in ['01-case.png','02-trends.png','03-candidates.png','04-routes.png','05-records.png','06-map-popup.png']:
            path=Path(root)/'artifacts/north-port'/name
            if path.exists(): files['captures/'+name]=path.read_bytes()
        files['README.txt']=('부산 FLOW 로컬 검증 자료 묶음\n개발 검증과 실제 사용자 테스트 모드를 분리했습니다. user_test가 없으면 실제 사용자 성과는 미확보입니다.\n합성 위험 시연은 실제 재난 증빙이 아닙니다. 방문 증가·혼잡 감소·안전 보장 성과를 입증하지 않습니다.\n개인별 로그·세션 식별자·API 키·IP·원본 DB는 포함하지 않습니다. 공개 게시 또는 공모전 제출은 수행하지 않았습니다.\n').encode('utf-8')
        manifest={'generated_at':summary['generated_at'],'files':{name:hashlib.sha256(body).hexdigest() for name,body in files.items()}}
        files['manifest.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,body in files.items():archive.writestr(name,body)
        return output.getvalue()
