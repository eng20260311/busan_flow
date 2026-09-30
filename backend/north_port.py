"""Historical case replay. Never infer present crowding from historical counts."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.candidates import build_courses, usable
from backend.tourism import normalize_place, TourError


def case_data(root, trends):
    path = Path(root) / 'data/north_port_case.json'
    case = json.loads(path.read_text(encoding='utf-8'))
    analysis = trends.get(8)['analysis']
    public_analysis = Path(root) / 'data/public/visitor_analysis.json'
    if analysis is None and public_analysis.exists():
        analysis = json.loads(public_analysis.read_text(encoding='utf-8'))
    case['analysis'] = analysis
    case['current_status'] = 'unverified'
    case['safety_verified'] = False
    return case


def explore(root, tour, trends, district):
    if district not in ('중구', '서구', '영도구'):
        raise ValueError('invalid_district')
    case = case_data(root, trends)
    records = {}
    public_places = Path(root) / 'data/public/tour_places.json'
    if public_places.exists():
        records = {p['id']:p for p in json.loads(public_places.read_text(encoding='utf-8'))['places']}
    with sqlite3.connect(tour.db_path) as db:
        rows = db.execute('SELECT query,payload,fetched FROM tour_cache WHERE payload IS NOT NULL ORDER BY fetched').fetchall()
    for query, payload, fetched in rows:
        operation, params = json.loads(query)
        if operation != 'areaBasedList2' or params.get('lDongRegnCd') != '26':
            continue
        for raw in json.loads(payload)['items']:
            try:
                place = normalize_place(raw)
            except TourError:
                continue
            place['fetched_at'] = datetime.fromtimestamp(fetched, timezone.utc).isoformat()
            stored = records.get(place['id'], {})
            if not place.get('image_url') and stored.get('image_url'):
                for field in ('image_url', 'image_license', 'image_source'):
                    if field in stored:
                        place[field] = stored[field]
            records[place['id']] = place
    # Exact known TourAPI record: representative coordinate, not a verified exit.
    origin = records.get('3426656')
    pool = [p for p in records.values() if p['address'].startswith(('부산광역시 '+district+' ', '부산 '+district+' '))
            and p['content_type'] in ('12','14','38') and '북항' not in p['name']]
    courses = build_courses(pool)
    # Individual discovery is not limited by the three-place course clustering.
    places = sorted((p for p in pool if usable(p)), key=lambda p: (p['content_type'], p['name'], p['id']))
    analysis = case['analysis']
    evidence = None if not analysis else {
        'start_date':analysis['start_date'], 'end_date':analysis['end_date'],
        'source_url':analysis['source_url'], 'is_realtime':False,
        'series':[s for s in analysis['series'] if s['district']==district]}
    return {'origin':'동구', 'origin_place':origin, 'district':district, 'courses':courses,
            'places':places,
            'risk':{'scenario':'north_port_historical','is_synthetic':False},
            'case_id':case['case_id'], 'alert_ids':[r['SN'] for r in case['records']],
            'source_mode':'historical_replay', 'tour_source_mode':'stored_tour_api',
            'analysis_evidence':evidence, 'safety_verified':False, 'route_verified':False,
            'reason':'북항 인접 구의 과거 방문 추이를 비교해 사용자가 탐색 지역을 선택했습니다. 관광지 묶음은 유형 다양성과 직선거리 기준이며 현재 혼잡도 순위가 아닙니다.',
            'scope':'이전에 수신한 관광지·문화시설·쇼핑 목록 범위. 최신 운영·통제·혼잡 미확인. 교통 조회는 조회 시점 기준으로 과거 경로 재현이 아닙니다.'}
