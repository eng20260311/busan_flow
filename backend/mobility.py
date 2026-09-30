"""TMAP transit adapter. Provider estimates are never safety or arrival guarantees."""
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
import httpx


def nonnegative(value):
    if type(value) is not int or value < 0:
        raise ValueError('invalid_number')
    return value


def parse_routes(payload):
    itineraries = payload['metaData']['plan']['itineraries']
    if not isinstance(itineraries, list):
        raise ValueError('invalid_routes')
    routes = []
    for item in itineraries:
        legs = item['legs']
        if not isinstance(legs, list) or not legs:
            raise ValueError('invalid_legs')
        segments = []
        for leg in legs:
            if leg['mode'] not in {'WALK', 'BUS', 'SUBWAY'}:
                break  # This MVP compares local bus/subway/walking routes only.
            if leg['mode'] != 'WALK' and leg.get('service') != 1:
                break  # Unknown or ended operations cannot qualify for time comparison.
            segments.append({'mode': leg['mode'], 'route': str(leg.get('route', '')),
                             'start': str(leg['start']['name']), 'end': str(leg['end']['name']),
                             'seconds': nonnegative(leg['sectionTime'])})
        else:
            total = nonnegative(item['totalTime'])
            walk = nonnegative(item['totalWalkTime'])
            if not total or walk > total:
                raise ValueError('invalid_duration')
            routes.append({'total_seconds': total, 'walk_seconds': walk,
                           'transfers': nonnegative(item['transferCount']), 'segments': segments,
                           'uses_subway': any(s['mode'] == 'SUBWAY' for s in segments),
                           'uses_bus': any(s['mode'] == 'BUS' for s in segments)})
    return sorted(routes, key=lambda r: (r['total_seconds'], r['walk_seconds'], r['transfers']))


class TransitService:
    def __init__(self, key='', transport=None, clock=monotonic):
        self.key, self.transport, self.clock = key.strip(), transport, clock
        self.cache, self.lock = {}, Lock()

    def route(self, origin, destination):
        base = {'source': 'TMAP 대중교통', 'source_url': 'https://transit.tmapmobility.com/docs/routes',
                'route_safety_verified': False, 'arrival_realtime_verified': False, 'routes': []}
        if not self.key:
            return {**base, 'status': 'unconfigured', 'fetched_at': None}
        coords = tuple(p[k] for p in (origin, destination) for k in ('longitude', 'latitude'))
        with self.lock:
            now = self.clock()
            cached = self.cache.get(coords)
            if cached and now-cached[0] < 300:
                return {**cached[1], 'cache_hit': True}
            try:
                with httpx.Client(timeout=12, transport=self.transport, follow_redirects=False) as client:
                    response = client.post('https://apis.openapi.sk.com/transit/routes',
                        headers={'appKey': self.key, 'accept': 'application/json'},
                        json=dict(zip(('startX', 'startY', 'endX', 'endY'), map(str, coords))) | {'count': 3, 'lang': 0, 'format': 'json'})
                    response.raise_for_status()
                    routes = parse_routes(response.json())
                result = {**base, 'status': 'available' if routes else 'no_route', 'routes': routes,
                          'fetched_at': datetime.now(timezone.utc).isoformat(), 'cache_hit': False}
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                result = {**base, 'status': 'unavailable', 'fetched_at': None, 'cache_hit': False}
            if len(self.cache) >= 128:
                self.cache.clear()
            self.cache[coords] = (now, result)
            return result
