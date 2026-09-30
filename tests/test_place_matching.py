import json
import sqlite3
from backend.tourism import TourService
from backend.place_matching import match_notice


def test_matching_scope_duplicates_ambiguity_and_missing_coordinates(tmp_path):
    path=tmp_path/'tour.db'
    TourService('',path)
    rows=[{'contentid':'1','title':'북항친수공원','addr1':'부산광역시 동구 중앙대로 1','lDongRegnCd':'26','mapx':'129.04','mapy':'35.1'},
          {'contentid':'2','title':'북항친수공원','addr1':'부산광역시 중구 중앙대로 2','lDongRegnCd':'26'},
          {'contentid':'3','title':'북항친수공원 전망대','addr1':'부산광역시 동구 중앙대로 3','lDongRegnCd':'26'},
          {'contentid':'4','title':'북항친수공원','addr1':'서울특별시 중구 1','lDongRegnCd':'11'}]
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO tour_cache VALUES (?,?,?,?)',(json.dumps(['areaBasedList2',{'lDongRegnCd':'26'}]),json.dumps({'items':rows}),100,100))
    result=match_notice({'original_message':'[합성] 북항친수공원 통제'},path)
    assert len(result['places'])==3
    assert [p['match_kind'] for p in result['places']]==['exact','exact','partial']
    assert result['places'][0]['has_coordinates']
    assert not result['places'][1]['has_coordinates']
    assert not result['location_verified']
    assert not match_notice({'original_message':'[동구] 안전 유의'},path)['places']
    assert not match_notice({'original_message':'부산광역시 동구 안내'},path)['places']
    assert not match_notice({'original_message':'미지의지하차도 통제'},path)['places']


def test_api_selection_is_validated_and_attached(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import create_app
    from backend.reviews import ReviewStore
    service=TourService('',tmp_path/'tour.db')
    raw={'contentid':'42','title':'북항친수공원','addr1':'부산광역시 동구 중앙대로 1','lDongRegnCd':'26','mapx':'129.04','mapy':'35.1'}
    with sqlite3.connect(service.db_path) as db:
        db.execute('INSERT INTO tour_cache VALUES (?,?,?,?)',(json.dumps(['areaBasedList2',{'lDongRegnCd':'26'}]),json.dumps({'items':[raw]}),100,100))
    app=create_app(tour_service=service)
    app.state.reviews=ReviewStore(tmp_path/'review.db')
    key=app.state.reviews.register({'alert_id':'TEST','created_at':'2026-09-28','original_message':'[합성] 북항친수공원 통제','received_regions':['부산광역시 중구']},'synthetic_demo')
    client=TestClient(app)
    assert client.get('/api/notice-places/unknown').status_code==404
    assert client.get('/api/notice-places/'+key).json()['places'][0]['district']=='동구'
    params={'notice_key':key,'place_id':'42','origin':'동구','district':'중구'}
    result=client.get('/api/candidates',params=params)
    assert result.status_code==200
    assert result.json()['notice_context']['notice']['source_kind']=='synthetic_demo'
    assert result.json()['notice_context']['selected_place']['id']=='42'
    assert client.get('/api/candidates',params=params|{'origin':'서구'}).status_code==400
    assert client.get('/api/candidates',params=params|{'place_id':'bad'}).status_code==400
    assert not result.json()['safety_verified']
