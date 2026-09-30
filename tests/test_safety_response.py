import json
import pytest
from backend.safety_response import decode_response, SafetyResponseError
from backend.service import AlertService
from pathlib import Path
import httpx

@pytest.mark.parametrize('code,reason',[('32','unregistered_ip'),('30','unregistered_key'),('31','expired_key'),('22','rate_limited')])
def test_xml_gateway_error(code,reason):
    with pytest.raises(SafetyResponseError) as caught:
        decode_response(f'<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>{code}</returnReasonCode><errMsg>secret-key-and-ip</errMsg></cmmMsgHeader></OpenAPI_ServiceResponse>'.encode())
    assert caught.value.reason==reason
    assert 'secret' not in str(caught.value)

def test_valid_json_preserved():
    data={'header':{'resultCode':'00'},'body':[{'MSG_CN':'부산 원문'}]}
    assert decode_response(json.dumps(data,ensure_ascii=False).encode('utf-8'))==data

def test_ip_failure_retained_without_secret(tmp_path):
    sample=Path(__file__).resolve().parents[1]/'data/sample_alerts.json'
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,content=b'<root><returnReasonCode>32</returnReasonCode></root>')
    svc=AlertService('private-key',sample,tmp_path/'s.db',httpx.MockTransport(handler))
    data=svc.snapshot()
    assert data['failure_reason']=='unregistered_ip'
    assert data['source_mode']=='synthetic_demo'
    assert 'private-key' not in json.dumps(data)
    assert svc.snapshot()['failure_reason']=='unregistered_ip'
    assert len(calls)==1
