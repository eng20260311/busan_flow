from backend.candidates import build_courses, candidates, distance
from backend.tourism import TourError
import pytest


def place(i, lat=35.1, lon=129.04, kind='12'):
    return {'id': str(i), 'latitude': lat, 'longitude': lon, 'content_type': kind}


def test_disjoint_compact_candidates_and_unverified_flags():
    rows = [place(i, 35.1+i*.001, kind=('12','14','38')[i%3]) for i in range(6)]
    result = build_courses(rows + [rows[0]])
    assert len(result) == 2
    assert len({p['id'] for c in result for p in c['places']}) == 6
    for c in result:
        assert len(c['places']) == 3
        assert not c['safety_verified'] and not c['risk_filter_applied'] and not c['route_verified']
        assert all(distance(a,b) <= 3 for a in c['places'] for b in c['places'])


def test_invalid_distant_and_colocated_places_do_not_force_a_course():
    assert build_courses([place(1), place(2), place(3), place(4,lat=None), place(5,lat=float('nan')), place(6,lat=37), place(7,lat=35.3)]) == []


def test_stable_selection_and_distance():
    rows = [place(i, 35.1+i*.001) for i in range(6)]
    assert build_courses(rows) == build_courses(list(reversed(rows)))
    assert 1.10 < distance(place(1),place(2,lat=35.11)) < 1.12


def test_same_or_unknown_district_rejected_before_request():
    class NoCalls:
        def places(self,*args):raise AssertionError('unexpected API call')
    with pytest.raises(TourError):candidates(NoCalls(),'동구','동구')
    with pytest.raises(TourError):candidates(NoCalls(),'동구','서울')


def test_partial_source_failure_disclosed():
    class Partial:
        def places(self,district,kind,page):
            assert page == 1
            if kind=='14':raise TourError('upstream_timeout')
            return {'places':[place(kind+i,35.1+n*.001) for n,i in enumerate(('a','b','c'))],
                    'source_mode':'cached_stale','fetched_at':'2026-09-27','total':30,'has_more':True}
    result=candidates(Partial(),'동구','중구')
    assert result['status']=='partial'
    assert result['failures']==[{'type':'14','error':'upstream_timeout'}]
    assert all(s['mode']=='cached_stale' and s['has_more'] for s in result['sources'])
