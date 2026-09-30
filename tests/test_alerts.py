import copy
import json
from pathlib import Path

import pytest

from backend.alerts import PayloadError, normalize

SAMPLE = Path(__file__).resolve().parents[1] / "data/sample_alerts.json"


@pytest.fixture
def payload():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_provider_slash_timestamp_preserves_original(payload):
    payload['body'][0]['CRT_DT']='2026/09/25 09:00:06'
    result={a.alert_id:a for a in normalize(payload)}
    assert result['DEMO-001'].created_at.isoformat()=='2026-09-25T09:00:06+09:00'
    assert payload['body'][0]['CRT_DT']=='2026/09/25 09:00:06'


def test_invalid_slash_date_rejected(payload):
    payload['body'][0]['CRT_DT']='2026/02/30 09:00:06'
    with pytest.raises(PayloadError,match='invalid_timestamp'):normalize(payload)


def test_original_unicode_and_classifications(payload):
    result = {a.alert_id: a for a in normalize(payload)}
    assert result["DEMO-001"].original_message == payload["body"][0]["MSG_CN"]
    assert result["DEMO-001"].flow_summary != result["DEMO-001"].original_message
    assert (result["DEMO-001"].severity, result["DEMO-001"].recommendation_mode) == ("caution", "disperse")
    assert result["DEMO-001"].transport_advice == "public_transit"
    assert (result["DEMO-002"].severity, result["DEMO-002"].recommendation_mode) == ("danger", "avoid")
    assert (result["DEMO-003"].severity, result["DEMO-003"].event_type) == ("info", "medical_info")
    assert result["DEMO-001"].created_at.utcoffset().total_seconds() == 9 * 3600


def test_deduplicate_only_same_sn_and_keep_repeat_notices(payload):
    payload["body"].append(copy.deepcopy(payload["body"][0]))
    repeat = copy.deepcopy(payload["body"][0])
    repeat["SN"] = "DEMO-005"
    payload["body"].append(repeat)
    assert len(normalize(payload)) == 5


def test_conflicting_duplicate_needs_review(payload):
    changed = copy.deepcopy(payload["body"][0])
    changed["MSG_CN"] = "정정"
    payload["body"].append(changed)
    with pytest.raises(PayloadError, match="conflicting_duplicate"):
        normalize(payload)


@pytest.mark.parametrize("message,kind,mode", [
    ("북항친수공원 교통정체 및 침수 위험", "flood", "avoid"),
    ("북항친수공원 화재 발생. 즉시 대피", "fire", "evacuate"),
    ("병원 안내. 인근 산불 발생", "fire", "avoid"),
    ("온천동 출입 통제", "other", "avoid"),
    ("북항친수공원 미확인 안내", "other", "review"),
    ("온천동 출입통제 해제", "other", "review"),
    ("온천동 멧돼지 출몰 문자 오발령 정정", "other", "review"),
])
def test_hazard_priority_and_unknowns(payload, message, kind, mode):
    payload["body"] = [payload["body"][0]]
    payload["body"][0]["MSG_CN"] = message
    alert = normalize(payload)[0]
    assert (alert.event_type, alert.recommendation_mode) == (kind, mode)
    assert alert.status == "unverified"


def test_unknown_location_is_not_recipient_district(payload):
    payload["body"] = [payload["body"][0]]
    payload["body"][0]["MSG_CN"] = "교통정체 안내"
    alert = normalize(payload)[0]
    assert alert.location_name is None
    assert alert.requires_review


def test_other_city_filtered_national_preserved(payload):
    payload["body"][0]["RCPTN_RGN_NM"] = "서울특별시 중구"
    payload["body"][1]["RCPTN_RGN_NM"] = "전국"
    assert {a.alert_id for a in normalize(payload)} == {"DEMO-002", "DEMO-003", "DEMO-004"}


@pytest.mark.parametrize("field,value", [("SN", None), ("MSG_CN", ""), ("CRT_DT", "nonsense"), ("RCPTN_RGN_NM", None)])
def test_bad_record_rejected(payload, field, value):
    payload["body"][0][field] = value
    with pytest.raises(PayloadError):
        normalize(payload)


@pytest.mark.parametrize("bad", [{}, {"header": {"resultCode": "99"}, "body": []}, {"header": {"resultCode": "00"}, "body": None}])
def test_bad_response_rejected(bad):
    with pytest.raises(PayloadError):
        normalize(bad)
