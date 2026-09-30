import pytest
from backend.extraction import extract_notice


def test_extract_locations_actions_time_and_evidence():
    message='[합성 예시] 영도구 봉래지하차도 침수로 9월 28일 14:30부터 양방향 통제. 우회 바랍니다. [부산광역시]'
    result=extract_notice(message)
    assert {x['text'] for x in result['places']}=={'영도구','봉래지하차도'}
    assert {x['label'] for x in result['actions']}=={'통제 언급','우회 언급'}
    assert '14:30' in {x['text'] for x in result['time_expressions']}
    assert result['scope_expressions']
    for group in ('places','actions','event_types','time_expressions','scope_expressions'):
        for item in result[group]:
            assert message[item['start']:item['end']]==item['text']
            assert item['text'] in item['evidence']
            assert not item['verified']
    assert not result['location_verified'] and not result['scope_verified']


@pytest.mark.parametrize('message',[
    '침수 없음. 통제 해제 예정입니다.', '통제 해제되지 않았습니다.',
    '호우 시 대피 바랍니다.', '내일 10시 통제 예정.', '상황 종료 안내 정정합니다.',
])
def test_mentions_never_establish_active_or_released_state(message):
    result=extract_notice(message)
    assert result['requires_review'] and not result['safety_verified']
    assert result['status']=='자동 추출 · 미검증'
    assert 'active' not in result and 'released' not in result


def test_sender_urls_and_generic_words_are_not_locations():
    result=extract_notice('이동 및 야외활동 자제. https://example.com/영도구/9.28 [부산광역시 동구]')
    assert result['places']==[]
    assert result['time_expressions']==[]


def test_unrecognized_text_does_not_invent_fields():
    result=extract_notice('자세한 안내를 확인하세요.')
    assert not any(result[x] for x in ('places','actions','event_types','time_expressions','scope_expressions'))


def test_existing_sample_places_and_medical_notice():
    assert {x['text'] for x in extract_notice('이순신대로 북항친수공원 입구 차량정체')['places']}=={'이순신대로','북항친수공원'}
    result=extract_notice('추석 연휴기간 문여는 병·의원 및 약국을 확인하세요[보건복지부]')
    assert not result['places']
    assert {x['label'] for x in result['event_types']}=={'의료 안내'}


def test_api_attaches_extraction_without_manual_review(tmp_path):
    from fastapi.testclient import TestClient
    from backend.main import create_app
    from backend.reviews import ReviewStore
    class SampleService:
        def snapshot(self):
            return {'source_mode':'synthetic_demo','alerts':[{'alert_id':'TEST-EXTRACT',
                'created_at':'2026-09-28','original_message':'[합성] 북항친수공원 차량 통제',
                'received_regions':['부산광역시 동구']}]}
    app=create_app(service=SampleService())
    app.state.reviews=ReviewStore(tmp_path/'review.db')
    client=TestClient(app)
    alert=client.get('/api/alerts').json()['alerts'][0]
    assert alert['extraction']['places'][0]['text']=='북항친수공원'
    assert client.get('/api/notice-reviews/'+alert['review_key']).json()['latest'] is None
