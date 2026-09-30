import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import pytest
from backend.north_port import case_data, explore
from backend.evidence import EvidenceStore

ROOT = Path(__file__).resolve().parents[1]


class Trends:
    def get(self, weeks):
        return {'analysis':{'start_date':'20260704','end_date':'20260828','source_url':'https://www.data.go.kr/data/15101972/openapi.do','series':[]}}


def test_original_case_replay_preserves_official_text():
    result=case_data(ROOT,Trends())
    assert result['source_mode']=='historical_replay'
    assert result['current_status']=='unverified' and not result['safety_verified']
    assert {r['SN'] for r in result['records']}=={269088,269092,269099,269122,269127}
    control=next(r for r in result['records'] if r['SN']==269127)
    assert control['CRT_DT']=='2026/09/25 16:08:46'
    assert '공중보행로(육교)를 일시 차단' in control['MSG_CN']
    assert all('\ufffd' not in r['MSG_CN'] for r in result['records'])


def test_candidates_keep_historical_context_and_actual_save(tmp_path):
    path=tmp_path/'tour.db'
    items=[{'contentid':str(i),'title':'장소'+str(i),'addr1':'부산광역시 중구 중앙대로','mapy':str(35.1+i*.002),'mapx':'129.04','contenttypeid':'12'} for i in range(3)]
    items.append({'contentid':'3426656','title':'부산북항 친수공원','addr1':'부산광역시 동구 이순신대로','mapy':'35.1144','mapx':'129.0466','contenttypeid':'12'})
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE tour_cache(query TEXT,payload TEXT,fetched REAL)')
        db.execute('INSERT INTO tour_cache VALUES (?,?,?)',(json.dumps(['areaBasedList2',{'lDongRegnCd':'26'}]),json.dumps({'items':items}),100))
    tour=SimpleNamespace(db_path=path)
    data=explore(isolated_root(tmp_path),tour,Trends(),'중구')
    assert data['origin_place']['id']=='3426656'
    assert len(data['courses'])==1 and len(data['courses'][0]['places'])==3
    assert data['risk']['is_synthetic'] is False and data['analysis_evidence']['is_realtime'] is False
    assert not data['safety_verified'] and not data['route_verified']
    store=EvidenceStore(tmp_path/'events.db');s=store.start(True,'developer')['session_id'];q=store.record_query(s,data)
    store.event(s,q,data['courses'][0]['id'],'save')
    assert store.summary()['groups'][0]['scenario']=='north_port_historical'
    assert store.saved(s)[0]['is_synthetic_risk_demo'] is False
    with pytest.raises(ValueError):explore(ROOT,tour,Trends(),'동구')


def test_no_trends_does_not_invent_analysis(tmp_path):
    result=case_data(isolated_root(tmp_path),SimpleNamespace(get=lambda weeks:{'analysis':None}))
    assert result['analysis'] is None


def test_individual_places_not_limited_by_course_size_or_proximity(tmp_path):
    path=tmp_path/'tour.db'
    items=[{'contentid':str(i),'title':'place'+str(i),'addr1':'부산광역시 중구 중앙대로','mapy':str(35.0+i*.025),'mapx':'129.04','contenttypeid':'12'} for i in range(10)]
    items += [dict(items[0]), dict(items[0],contentid='invalid',mapy=''), dict(items[0],contentid='elsewhere',addr1='부산광역시 서구 중앙대로')]
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE tour_cache(query TEXT,payload TEXT,fetched REAL)')
        db.execute('INSERT INTO tour_cache VALUES (?,?,?)',(json.dumps(['areaBasedList2',{'lDongRegnCd':'26'}]),json.dumps({'items':items}),100))
    data=explore(isolated_root(tmp_path),SimpleNamespace(db_path=path),Trends(),'중구')
    assert len(data['places'])==10
    assert len({p['id'] for p in data['places']})==10
    assert all(p['has_coordinates'] for p in data['places'])
    assert not data['safety_verified']


def isolated_root(tmp_path):
    data=tmp_path/'data'
    data.mkdir(exist_ok=True)
    (data/'north_port_case.json').write_bytes((ROOT/'data/north_port_case.json').read_bytes())
    return tmp_path


def test_public_snapshot_works_without_local_cache(tmp_path):
    from backend.tourism import TourService
    tour=TourService('',tmp_path/'empty.sqlite3')
    data=explore(ROOT,tour,SimpleNamespace(get=lambda weeks:{'analysis':None}),'중구')
    assert len(data['places'])>=40
    assert data['origin_place']['id']=='3426656'
    assert data['analysis_evidence']['is_realtime'] is False


def test_public_deploy_blocks_management(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import create_app
    monkeypatch.setenv('FLOW_PUBLIC_DEPLOYMENT','1')
    with TestClient(create_app()) as client:
        for path in ['/static/admin.html','/api/evidence/export','/api/evidence/summary','/api/notice-reviews/test','/docs']:
            assert client.get(path).status_code==404
        assert client.post('/api/test-sessions',json={'consent':True,'mode':'developer'}).status_code==404
        assert client.get('/api/north-port/candidates?session_id=test').status_code==400
        assert client.get('/api/north-port').status_code==200
        assert client.get('/api/health').status_code==200
