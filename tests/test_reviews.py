from datetime import datetime,timedelta,timezone
import pytest
from pydantic import ValidationError
from backend.reviews import ReviewStore,ReviewInput


def body(**changes):
    return ReviewInput(**({'revision':0,'reviewer':'TEST','status':'unverified','recheck_at':datetime.now(timezone.utc)+timedelta(days=1)}|changes))


def test_notice_version_source_separation_and_history(tmp_path):
    store=ReviewStore(tmp_path/'review.db');alert={'alert_id':'1','created_at':'2026-09-28','original_message':'[합성] 테스트','received_regions':['부산광역시 동구']}
    key=store.register(alert,'synthetic_demo');assert store.register(alert,'api')!=key
    assert store.register(alert|{'original_message':'변경'},'synthetic_demo')!=key
    one=store.save(key,body());assert one['latest']['revision']==1
    with pytest.raises(ValueError):store.save(key,body())
    assert len(store.save(key,body(revision=1))['history'])==2
    assert not store.get(key)['safety_verified']
    assert ReviewStore(tmp_path/'review.db').get(key)['notice']['original_message']==alert['original_message']
    with pytest.raises(KeyError):store.save('unknown',body())


@pytest.mark.parametrize('changes',[{'status':'location'},{'latitude':35.1},{'latitude':100,'longitude':129},{'evidence_url':'javascript:alert(1)'},{'recheck_at':datetime.now(timezone.utc)-timedelta(days=1)}])
def test_incomplete_or_invalid_verification_rejected(changes):
    with pytest.raises(ValidationError):body(**changes)


def test_release_requires_scope_and_source_date():
    fields={'status':'released','place':'테스트','latitude':35.1,'longitude':129.1,'document':'합성 검증 문서','published_at':datetime.now(timezone.utc)-timedelta(hours=1)}
    with pytest.raises(ValidationError):body(**fields)
    assert body(**fields,area='합성 도로 구간').status=='released'


def test_review_api_roundtrip_and_conflict(tmp_path):
    from fastapi.testclient import TestClient
    from backend.main import create_app
    app=create_app()
    app.state.reviews=ReviewStore(tmp_path/'reviews.db')
    key=app.state.reviews.register({'alert_id':'TEST','created_at':'2026-09-28','original_message':'[합성] API 검증','received_regions':['부산광역시 동구']},'synthetic_demo')
    client=TestClient(app)
    url='/api/notice-reviews/'+key
    assert client.get(url).json()['latest'] is None
    payload=body().model_dump(mode='json')
    saved=client.post(url,json=payload)
    assert saved.status_code==200
    assert saved.json()['latest']['reviewed_at']
    assert client.get(url).json()['latest']['reviewer']=='TEST'
    assert client.post(url,json=payload).status_code==409
    assert client.post(url,json=payload|{'status':'area'}).status_code==422
    assert client.get('/api/notice-reviews/missing').status_code==404


def test_recheck_due_retains_original_status(tmp_path):
    import json,sqlite3
    store=ReviewStore(tmp_path/'reviews.db')
    key=store.register({'alert_id':'TEST','created_at':'2026-09-28','original_message':'[합성] 기한 경과','received_regions':[]},'synthetic_demo')
    record=store.save(key,body())['latest']
    record['recheck_at']=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE reviews SET payload=? WHERE key=?',(json.dumps(record),key))
    result=store.get(key)
    assert result['recheck_due']
    assert result['latest']['status']=='unverified'
    assert not result['safety_verified']
