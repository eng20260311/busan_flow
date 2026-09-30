"""Explicit synthetic scenarios. Geometry is manually authored, never inferred from recipient regions."""
from backend.alerts import classify
from backend.tourism import TourError

ZONE = {'id': 'DEMO-ZONE-1', 'name': '광복로 주변 가상 통제구역',
        'latitude': 35.0986398717, 'longitude': 129.0327400915, 'radius_m': 200,
        'geometry_source': '개발자가 설정한 시연용 원형 구역. 실제 통제 경계가 아님.'}
SCENARIOS = {
    'demo_control': {'message': '[합성 시연] 광복로 주변 화재로 출입통제. 해당 구역 접근을 피하세요.', 'zone': ZONE},
    'demo_unknown': {'message': '[합성 시연] 부산 일대 화재 신고. 정확한 발생 위치와 영향 범위는 확인 중입니다.', 'zone': None},
    'demo_release': {'message': '[합성 시연] 광복로 주변 통제해제 안내. 이전 사건과의 일치 여부 및 종료 범위는 확인되지 않았습니다.', 'zone': ZONE},
}


def scenario_info(scenario):
    if scenario == 'none':
        return {'scenario': 'none', 'is_synthetic': False, 'applied': False, 'blocked': False,
                'zones': [], 'excluded': [], 'review_reason': None}
    if scenario not in SCENARIOS:
        raise TourError('invalid_filter')
    item = SCENARIOS[scenario]
    kind, severity, action, review = classify(item['message'])
    reason = ('위치·영향 범위 불명: 후보 구성을 보류하고 수동 검토합니다.' if item['zone'] is None
              else '통제해제 사건 일치·종료 범위 미확인: 자동 복구하지 않고 후보 구성을 보류합니다.' if action == 'review' else None)
    return {'scenario': scenario, 'is_synthetic': True, 'applied': True,
            'alert_id': 'SYNTHETIC-'+scenario, 'original_message': item['message'],
            'event_type': kind, 'severity': severity, 'action': action,
            'blocked': bool(reason), 'review_reason': reason,
            'zones': [dict(item['zone'])] if item['zone'] else [], 'excluded': [],
            'note': '실제 관광정보에 합성 문자와 가상 위험구역을 적용한 시연입니다. 실제 재난 발령·통제 상황이 아닙니다.'}


def filter_places(places, info):
    from backend.candidates import distance, usable
    if not info['applied']:
        return places
    kept = []
    for place in places:
        hit = []
        if usable(place):
            hit = [z['id'] for z in info['zones'] if distance(place, z)*1000 <= z['radius_m']+1e-6]
        if info['blocked'] or hit or not usable(place):
            info['excluded'].append({'id': place['id'], 'name': place.get('name',place['id']),
                                     'zone_ids': hit,
                                     'reason': info['review_reason'] if info['blocked'] else
                                     '좌표 미확인 또는 범위 밖' if not usable(place) else '시연용 통제구역 내부 또는 경계'})
        else:
            kept.append(place)
    return kept
