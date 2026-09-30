import pytest
from backend.hazards import scenario_info, filter_places, ZONE
from backend.candidates import candidates, distance
from backend.tourism import TourError


def place(id, lat=ZONE['latitude'], lon=ZONE['longitude']):
    return {'id':id,'name':id,'latitude':lat,'longitude':lon,'content_type':'12'}


def test_inside_boundary_and_outside():
    center=place('center')
    boundary=place('boundary',ZONE['latitude']+0.001)
    outside=place('outside',ZONE['latitude']+0.02)
    info=scenario_info('demo_control')
    info['zones'][0]['radius_m']=distance(center,boundary)*1000
    assert filter_places([center,boundary,outside],info)==[outside]
    assert {p['id'] for p in info['excluded']}=={'center','boundary'}


@pytest.mark.parametrize('scenario',['demo_unknown','demo_release'])
def test_uncertain_hazard_blocks_all_candidates(scenario):
    info=scenario_info(scenario)
    assert info['blocked'] and info['review_reason']
    assert filter_places([place('far',35.2)],info)==[]
    assert len(info['excluded'])==1


def test_none_does_not_pretend_filtering_and_scenario_is_isolated():
    rows=[place('a')]
    info=scenario_info('none')
    assert filter_places(rows,info)==rows and not info['applied']
    one=scenario_info('demo_control');one['zones'][0]['radius_m']=9000
    assert scenario_info('demo_control')['zones'][0]['radius_m']==200
    with pytest.raises(TourError):scenario_info('live_safe')


def test_invalid_coordinates_are_never_treated_as_outside():
    info=scenario_info('demo_control')
    assert filter_places([place('missing',None),place('nan',float('nan'))],info)==[]
    assert len(info['excluded'])==2


def test_candidates_apply_filter_before_building_and_keep_safety_false():
    class Source:
        def places(self,district,kind,page):
            return {'places':[place('inside'),*[place(str(i),35.11+i*.001) for i in range(6)]],
                    'source_mode':'api','fetched_at':'2026-09-27','total':7,'has_more':False}
    result=candidates(Source(),'동구','중구','demo_control')
    assert result['risk_filter_applied'] and not result['safety_verified'] and not result['route_verified']
    assert result['risk']['excluded'][0]['id']=='inside'
    assert len(result['courses'])==2
    assert all(p['id']!='inside' for c in result['courses'] for p in c['places'])
    assert all(c['risk_filter_applied'] and c['is_synthetic_risk_demo'] and not c['safety_verified'] for c in result['courses'])
    blocked=candidates(Source(),'동구','중구','demo_release')
    assert blocked['courses']==[] and blocked['before_course_count']==2
