import json
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.tourism import CLASSIFICATION, TourService, TourError, normalize_place, parse_response


def payload(items, total=None, page=1):
    return {'response': {'header': {'resultCode': '0000'}, 'body': {'items': {'item': items}, 'totalCount': len(items) if total is None else total, 'pageNo': page, 'numOfRows': 20}}}


def place():
    return {'contentid':'test-1','title':'테스트 장소','contenttypeid':'12','mapx':'129.04','mapy':'35.1','lDongRegnCd':'26','lDongSignguCd':'170','lclsSystm1':'NA','lclsSystm2':'NA04','lclsSystm3':'NA040500'}


def test_mapping_merged_cells_and_special_type():
    assert len(CLASSIFICATION) == 240
    assert CLASSIFICATION['AC050200']['lclsSystm1'] == 'AC'
    assert CLASSIFICATION['AC050200']['contenttypeid'] == '28'  # Camping is leisure, not lodging.
    assert CLASSIFICATION['AC050200']['foreign_contenttypeid'] == '75'


def test_origin_keyword_search_uses_documented_filters(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.path.endswith('ldongCode2'):
            return httpx.Response(200, json=payload([{'code': '170', 'name': '동구'}]))
        assert request.url.path.endswith('searchKeyword2')
        assert request.url.params['keyword'] == '테스트 장소'
        assert request.url.params['lDongSignguCd'] == '170'
        assert 'contentTypeId' not in request.url.params
        shopping = place() | {'contentid': 'shopping', 'contenttypeid': '38'}
        return httpx.Response(200, json=payload([place(), shopping]))
    service = TourService('test-key', tmp_path/'tour.sqlite3', httpx.MockTransport(handler))
    result = service.places('동구', '12', keyword='테스트 장소')
    assert [p['id'] for p in result['places']] == ['test-1']
    assert len(calls) == 2
    assert CLASSIFICATION['FD050100']['contenttypeid'] == '39'


def test_normalization_coordinates_and_classification():
    result = normalize_place(place())
    assert result['latitude'] == 35.1 and result['longitude'] == 129.04
    assert result['classification_verified'] and not result['safety_verified']


@pytest.mark.parametrize('coordinate',['','nan','inf','999'])
def test_bad_coordinates_are_unusable(coordinate):
    row=place();row['mapx']=coordinate
    assert not normalize_place(row)['has_coordinates']


def test_mapping_conflict_not_silently_rewritten():
    row=place();row['contenttypeid']='39'
    assert not normalize_place(row)['classification_verified']
    assert normalize_place(row)['content_type']=='39'


def test_singleton_empty_and_result_code():
    assert len(parse_response(json.dumps(payload(place(), 1)).encode())['items'])==1
    assert parse_response(json.dumps(payload([])).encode())['items']==[]
    data=payload([]);data['response']['header']['resultCode']='00'
    with pytest.raises(TourError):parse_response(json.dumps(data).encode())


def test_xml_error_does_not_leak_text():
    with pytest.raises(TourError,match='authentication_failed'):
        parse_response(b'<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</returnReasonCode><errMsg>secret</errMsg></cmmMsgHeader></OpenAPI_ServiceResponse>')


def test_api_case_encoding_pagination_and_cache(tmp_path):
    calls=[]
    def handler(request):
        calls.append(request)
        assert request.url.params['serviceKey']=='fake+a/b='
        assert request.url.params['MobileApp']=='BusanFLOW'
        assert request.url.params['_type']=='json'
        if request.url.path.endswith('ldongCode2'):
            return httpx.Response(200,json=payload([{'code':'170','name':'동구'}]))
        assert request.url.params['lDongRegnCd']=='26'
        assert request.url.params['lDongSignguCd']=='170'
        assert request.url.params['contentTypeId']=='12'
        return httpx.Response(200,json=payload([place()],total=40))
    svc=TourService('fake%2Ba%2Fb%3D',tmp_path/'t.db',httpx.MockTransport(handler))
    result=svc.places();svc.places()
    assert len(calls)==2 and result['has_more']
    assert 'fake' not in json.dumps(result)


def test_stale_cache_after_failure(tmp_path):
    clock=[10000];fail=[False]
    def handler(request):
        if fail[0]:return httpx.Response(503)
        return httpx.Response(200,json=payload([{'code':'170','name':'동구'}] if request.url.path.endswith('ldongCode2') else [place()]))
    svc=TourService('fake',tmp_path/'t.db',httpx.MockTransport(handler),lambda:clock[0])
    assert svc.places()['source_mode']=='api'
    fail[0]=True;clock[0]+=3601
    assert svc.places()['source_mode']=='cached_stale'


def test_unconfigured_and_api_filter_validation(tmp_path):
    svc=TourService('',tmp_path/'t.db')
    with TestClient(create_app(tour_service=svc)) as client:
        assert client.get('/api/places').json()['source_mode']=='unconfigured'
        assert client.get('/api/places?district=서울').status_code==400
        assert client.get('/api/places?page=0').status_code==400


def test_out_of_region_rejected(tmp_path):
    row=place();row['lDongRegnCd']='11'
    def handler(request):
        return httpx.Response(200,json=payload([{'code':'170','name':'동구'}] if request.url.path.endswith('ldongCode2') else [row]))
    svc=TourService('fake',tmp_path/'t.db',httpx.MockTransport(handler))
    with pytest.raises(TourError,match='filter_mismatch'):svc.places()


@pytest.mark.parametrize('kind,expected',[('connect','upstream_connection_failed'),('timeout','upstream_timeout'),('auth','authentication_failed'),('limit','rate_limited')])
def test_safe_actionable_error_codes(tmp_path,kind,expected):
    def handler(request):
        if kind=='connect':raise httpx.ConnectError('secret URL key',request=request)
        if kind=='timeout':raise httpx.ReadTimeout('secret URL key',request=request)
        return httpx.Response(403 if kind=='auth' else 429)
    svc=TourService('secret',tmp_path/'t.db',httpx.MockTransport(handler))
    with pytest.raises(TourError) as error:svc.places('동구','38')
    assert str(error.value)==expected


def test_donggu_shopping_request(tmp_path):
    row=place();row.update(contenttypeid='38',lclsSystm1='SH',lclsSystm2='',lclsSystm3='')
    def handler(request):
        if request.url.path.endswith('ldongCode2'):return httpx.Response(200,json=payload([{'code':'170','name':'동구'}]))
        assert request.url.params['contentTypeId']=='38'
        return httpx.Response(200,json=payload([row],total=32))
    data=TourService('fake',tmp_path/'t.db',httpx.MockTransport(handler)).places('동구','38')
    assert data['total']==32 and data['places'][0]['type_name']=='쇼핑'
