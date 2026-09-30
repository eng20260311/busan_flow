"""Geographical exploration candidates; no safety or road routing inference."""
from math import radians, sin, cos, asin, sqrt, isfinite
from backend.tourism import DISTRICTS, TourError
from backend.hazards import scenario_info, filter_places


def distance(a, b):
    lat1, lat2 = radians(a['latitude']), radians(b['latitude'])
    dlat = lat2-lat1
    dlon = radians(b['longitude']-a['longitude'])
    return 6371 * 2 * asin(min(1, sqrt(sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2)))


def usable(p):
    try:
        lat, lon = p['latitude'], p['longitude']
        return isfinite(lat) and isfinite(lon) and 34.8 <= lat <= 35.4 and 128.8 <= lon <= 129.4
    except (KeyError, TypeError):
        return False


def build_courses(places):
    # Stable order and unique IDs; each candidate is a compact group of 3 distinct places.
    pool = {p['id']: p for p in places if usable(p)}
    courses = []
    while len(pool) >= 3 and len(courses) < 2:
        options = []
        for seed in sorted(pool):
            route = [pool[seed]]
            for _ in range(2):
                near = [p for p in pool.values() if p['id'] not in {r['id'] for r in route}
                        and all(0.05 <= distance(p, r) <= 3 for r in route)]
                if not near:
                    break
                near.sort(key=lambda p: (p['content_type'] in {r['content_type'] for r in route}, distance(route[-1], p), p['id']))
                route.append(near[0])
            if len(route) == 3:
                length = sum(distance(route[i], route[i+1]) for i in range(2))
                options.append((-len({p['content_type'] for p in route}), length, seed, route))
        if not options:
            break
        _, length, _, route = min(options, key=lambda x: x[:3])
        courses.append({'id': f'candidate-{len(courses)+1}', 'places': route,
                        'straight_line_km': round(length, 2), 'safety_verified': False,
                        'route_verified': False, 'risk_filter_applied': False,
                        'reason': '관광지·문화시설·쇼핑 유형의 다양성과 장소 간 직선거리를 기준으로 묶었습니다.'})
        for p in route:
            pool.pop(p['id'])
    return courses


def candidates(service, origin, district, scenario='none'):
    if origin not in DISTRICTS or district not in DISTRICTS or origin == district:
        raise TourError('invalid_filter')
    risk = scenario_info(scenario)
    places, sources, failures = [], [], []
    for kind in ('12', '14', '38'):
        try:
            data = service.places(district, kind, 1)
            places.extend(data['places'])
            sources.append({'type': kind, 'mode': data['source_mode'], 'fetched_at': data.get('fetched_at'),
                            'returned': len(data['places']), 'total': data.get('total'), 'has_more': data['has_more']})
        except TourError as exc:
            failures.append({'type': kind, 'error': str(exc)})
    unique = {p['id']: p for p in places}
    before = build_courses(list(unique.values()))
    eligible = filter_places(list(unique.values()), risk)
    courses = build_courses(eligible) if not risk['blocked'] else []
    for course in courses:
        course['risk_filter_applied'] = risk['applied']
        course['is_synthetic_risk_demo'] = risk['is_synthetic']
    return {'origin': origin, 'district': district, 'courses': courses,
            'risk': risk, 'eligible_count': sum(usable(p) for p in eligible), 'before_course_count': len(before),
            'sources': sources, 'failures': failures, 'pool_count': len(unique),
            'excluded_coordinates': sum(not usable(p) for p in unique.values()),
            'status': 'partial' if failures else 'unconfigured' if sources and all(s['mode']=='unconfigured' for s in sources) else 'ok',
            'scope': '유형별 첫 20건 이내에서 구성한 후보입니다. 전체 관광지 순위가 아닙니다.',
            'safety_verified': False, 'risk_filter_applied': risk['applied'], 'route_verified': False}
