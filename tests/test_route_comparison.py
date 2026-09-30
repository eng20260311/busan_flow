import json
from urllib.parse import unquote

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.mobility import TransitService
from backend.route_comparison import CarService, ComparisonInput, compare_routes, parse_car


ORIGIN = {'name': '해운대/해변?&', 'latitude': 35.16, 'longitude': 129.16}
DEST = {'name': '민락수변공원', 'latitude': 35.1545, 'longitude': 129.133}


def car_payload():
    return {'routes': [{'result_code': 0, 'summary': {'duration': 900, 'distance': 4200},
                       'sections': [{'roads': [{'name': '수변로', 'duration': 800}]}]}]}


def transit_payload():
    def route(modes, seconds):
        return {'totalTime': seconds, 'totalWalkTime': 120, 'transferCount': len(modes)-1,
                'legs': [{'mode': mode, 'service': 1, 'sectionTime': 300, 'route': '테스트노선',
                          'start': {'name': '출발역'}, 'end': {'name': '도착역'}} for mode in modes]}
    return {'metaData': {'plan': {'itineraries': [route(['SUBWAY'], 1200), route(['BUS'], 1500),
                                                 route(['SUBWAY','BUS'], 1800)]}}}


def body():
    return ComparisonInput(origin=ORIGIN, destination=DEST, max_minutes=20)


def test_comparison_groups_units_limits_and_safe_external_urls():
    transit = TransitService('secret', httpx.MockTransport(lambda req: httpx.Response(200, json=transit_payload())))
    car = CarService('secret', httpx.MockTransport(lambda req: httpx.Response(200, json=car_payload())))
    result = compare_routes(body(), transit, car)
    groups = result['groups']
    assert [g['mode'] for g in groups] == ['subway', 'bus', 'mixed', 'car']
    assert [g['routes'][0]['within_limit'] for g in groups] == [True, False, False, True]
    assert groups[-1]['routes'][0]['distance_m'] == 4200
    assert '/by/car/' in groups[-1]['external_url']
    assert '해운대/해변?&' in unquote(groups[0]['external_url'])
    assert '%2F' in groups[0]['external_url'] and '%3F' in groups[0]['external_url']
    assert not result['safety_verified'] and 'secret' not in json.dumps(result)


def test_car_request_cache_and_expiry():
    calls, now = [], [0]
    def handler(req):
        calls.append(req)
        assert req.headers['Authorization'] == 'KakaoAK secret'
        assert req.url.params['origin'] == '129.16,35.16'
        assert req.url.params['roadevent'] == '0'
        return httpx.Response(200, json=car_payload())
    car = CarService('secret', httpx.MockTransport(handler), lambda: now[0])
    assert car.route(ORIGIN, DEST)['status'] == 'available'
    assert car.route(ORIGIN, DEST)['cache_hit'] and len(calls) == 1
    now[0] = 301
    assert not car.route(ORIGIN, DEST)['cache_hit'] and len(calls) == 2


@pytest.mark.parametrize('value', [-1, True, '900', None])
def test_bad_car_time_rejected(value):
    payload = car_payload(); payload['routes'][0]['summary']['duration'] = value
    with pytest.raises(ValueError): parse_car(payload)


@pytest.mark.parametrize('code,payload', [(403, {'secret':'private'}), (200, None), (200, {}), (200, {'routes':None})])
def test_car_failures_do_not_leak_or_invent_times(code, payload):
    car = CarService('secret', httpx.MockTransport(lambda req: httpx.Response(code, json=payload)))
    result = car.route(ORIGIN, DEST)
    assert result['status'] == 'unavailable' and result['routes'] == []
    assert 'secret' not in json.dumps(result) and 'private' not in json.dumps(result)


def test_timeout_and_no_route():
    def timeout(req): raise httpx.ReadTimeout('secret', request=req)
    assert CarService('secret', httpx.MockTransport(timeout)).route(ORIGIN, DEST)['status'] == 'unavailable'
    car = CarService('secret', httpx.MockTransport(lambda req: httpx.Response(200, json={'routes':[{'result_code':104}]})))
    assert car.route(ORIGIN, DEST)['status'] == 'no_route'


def test_missing_transit_category_is_not_reported_as_no_service():
    payload = transit_payload(); payload['metaData']['plan']['itineraries'] = payload['metaData']['plan']['itineraries'][:1]
    transit = TransitService('secret', httpx.MockTransport(lambda req: httpx.Response(200,json=payload)))
    result = compare_routes(body(), transit, CarService())
    assert result['groups'][0]['status'] == 'available'
    assert result['groups'][1]['status'] == 'not_returned'
    assert result['groups'][-1]['status'] == 'unconfigured'


def test_api_validates_coordinates_and_works_without_keys():
    app = create_app(transit_service=TransitService(), car_service=CarService())
    with TestClient(app) as client:
        data = body().model_dump()
        response = client.post('/api/route-comparison', json=data)
        assert response.status_code == 200
        assert all(g['status'] == 'unconfigured' and g['external_url'].startswith('https://map.kakao.com/')
                   for g in response.json()['groups'])
        for patch in ({'latitude':37}, {'longitude':0}, {'name':''}, {'url':'https://example.com'}):
            invalid = {**data, 'destination':{**DEST, **patch}}
            assert client.post('/api/route-comparison', json=invalid).status_code == 422
        assert client.get('/static/route-map.js').status_code == 200
