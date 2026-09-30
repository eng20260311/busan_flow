"""Compare provider estimates; external links recalculate routes, not safety."""
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field

from backend.mobility import nonnegative


class RoutePoint(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=34.8, le=35.4)
    longitude: float = Field(ge=128.8, le=129.4)


class ComparisonInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    origin: RoutePoint
    destination: RoutePoint
    max_minutes: int = Field(default=60, ge=5, le=180)


def external_link(origin, destination, mode):
    def point(p):
        return f"{quote(p['name'], safe='')},{p['latitude']},{p['longitude']}"
    return f"https://map.kakao.com/link/by/{'car' if mode == 'car' else 'traffic'}/{point(origin)}/{point(destination)}"


def parse_car(payload):
    items = payload['routes']
    if not isinstance(items, list):
        raise ValueError('invalid_routes')
    routes = []
    for item in items:
        if item['result_code'] != 0:
            continue
        summary = item['summary']
        duration = nonnegative(summary['duration'])
        if not duration:
            raise ValueError('invalid_duration')
        # Display steps and summaries; map geometry is outside this implementation.
        segments = []
        for section in item.get('sections', []):
            for road in section.get('roads', []):
                segments.append({'mode': 'CAR', 'route': str(road.get('name') or '이름 없는 도로'),
                                 'seconds': nonnegative(road['duration'])})
        routes.append({'total_seconds': duration, 'distance_m': nonnegative(summary['distance']),
                       'segments': segments})
    return sorted(routes, key=lambda r: r['total_seconds'])


class CarService:
    def __init__(self, key='', transport=None, clock=monotonic):
        self.key, self.transport, self.clock = key.strip(), transport, clock
        self.cache, self.lock = {}, Lock()

    def route(self, origin, destination):
        base = {'source': '카카오모빌리티 자동차 길찾기', 'routes': [],
                'fetched_at': None, 'route_safety_verified': False}
        if not self.key:
            return {**base, 'status': 'unconfigured'}
        coords = tuple(p[k] for p in (origin, destination) for k in ('longitude', 'latitude'))
        with self.lock:
            cached = self.cache.get(coords)
            if cached and self.clock() - cached[0] < 300:
                return {**cached[1], 'cache_hit': True}
            try:
                with httpx.Client(timeout=12, transport=self.transport, follow_redirects=False) as client:
                    response = client.get('https://apis-navi.kakaomobility.com/v1/directions',
                        headers={'Authorization': 'KakaoAK ' + self.key},
                        params={'origin': f'{coords[0]},{coords[1]}',
                                'destination': f'{coords[2]},{coords[3]}',
                                'alternatives': 'true', 'summary': 'false', 'roadevent': 0})
                    response.raise_for_status()
                    routes = parse_car(response.json())
                result = {**base, 'routes': routes, 'status': 'available' if routes else 'no_route',
                          'fetched_at': datetime.now(timezone.utc).isoformat(), 'cache_hit': False}
            except (httpx.HTTPError, ValueError, TypeError, KeyError):
                result = {**base, 'status': 'unavailable', 'cache_hit': False}
            if len(self.cache) >= 128:
                self.cache.clear()
            self.cache[coords] = (self.clock(), result)
            return result


def compare_routes(body, transit, car):
    origin, destination = body.origin.model_dump(), body.destination.model_dump()
    public = transit.route(origin, destination)
    driving = car.route(origin, destination)
    groups = []
    for mode, label in [('subway', '지하철 + 도보'), ('bus', '버스 + 도보'),
                        ('mixed', '지하철·버스 혼합'), ('car', '자동차')]:
        provider = driving if mode == 'car' else public
        rows = []
        for route in provider['routes']:
            kind = ('car' if mode == 'car' else 'mixed' if route['uses_subway'] and route['uses_bus']
                    else 'subway' if route['uses_subway'] else 'bus' if route['uses_bus'] else 'walk')
            if kind == mode:
                rows.append({**route, 'within_limit': route['total_seconds'] <= body.max_minutes * 60})
        groups.append({'mode': mode, 'label': label, 'source': provider['source'],
                       'status': ('available' if rows else 'not_returned') if provider['status'] == 'available' else provider['status'],
                       'fetched_at': provider.get('fetched_at'), 'cache_hit': provider.get('cache_hit', False),
                       'routes': rows, 'external_url': external_link(origin, destination, mode)})
    return {'origin': origin, 'destination': destination, 'groups': groups, 'safety_verified': False,
            'max_minutes': body.max_minutes,
            'notice': '제공사가 반환한 경로만 비교합니다. 현재 안전·운영·실시간 도착은 미검증입니다. 외부 길찾기는 경로를 새로 계산합니다.'}
