import httpx
import pytest
from backend.visitors import VisitorService
from backend.tourism import TourError

def record(code='26170', name='동구', group='2', number='123.45'):
    return {'baseYmd':'20260801','signguCode':code,'signguNm':name,'touDivCd':group,'touNum':number}

def response(items, page=1, total=None, size=100):
    return {'response':{'header':{'resultCode':'0000'},'body':{'items':{'item':items},'pageNo':page,'numOfRows':size,'totalCount':len(items) if total is None else total}}}

def make(tmp_path, handler):
    return VisitorService('fake',tmp_path/'v.db',httpx.MockTransport(handler))

def test_all_pages_before_filtering_and_decimals(tmp_path):
    calls=[]
    def handler(req):
        calls.append(req)
        assert req.url.path.endswith('/DataLabService/locgoRegnVisitrDDList')
        assert req.url.params['MobileOS']=='ETC'
        assert 'signguCode' not in req.url.params
        page=int(req.url.params['pageNo'])
        item=record('11110','종로구') if page==1 else record()
        return httpx.Response(200,json=response([item],page,2,1))
    svc=make(tmp_path,handler)
    data=svc.daily('20260801')
    assert len(calls)==2 and data['rows'][0]['groups']['2']=='123.45'
    assert data['rows'][1]['groups']['2'] is None and not data['complete']
    assert not data['is_realtime']
    svc.daily('20260801'); assert len(calls)==2

@pytest.mark.parametrize('day',['20260230','2026-08-01','20990101','abc','2026081'])
def test_invalid_dates(tmp_path,day):
    with pytest.raises(TourError,match='invalid_date'):VisitorService('',tmp_path/'v.db').daily(day)

@pytest.mark.parametrize('value',['NaN','Infinity','-1','','not-a-number'])
def test_invalid_values_not_zero(tmp_path,value):
    svc=make(tmp_path,lambda _:httpx.Response(200,json=response([record(number=value)])))
    with pytest.raises(TourError,match='invalid_visitor_count'):svc.daily('20260801')

def test_zero_distinct_from_missing_and_groups_separate(tmp_path):
    items=[record(group='1',number='900'),record(group='2',number='0')]
    data=make(tmp_path,lambda _:httpx.Response(200,json=response(items))).daily('20260801')
    assert data['rows'][0]['groups']=={'1':'900','2':'0','3':None}

def test_duplicate_rejected(tmp_path):
    svc=make(tmp_path,lambda _:httpx.Response(200,json=response([record(),record()])))
    with pytest.raises(TourError,match='duplicate_record'):svc.daily('20260801')

def test_date_mismatch(tmp_path):
    row=record();row['baseYmd']='20260731'
    svc=make(tmp_path,lambda _:httpx.Response(200,json=response([row])))
    with pytest.raises(TourError,match='response_date_mismatch'):svc.daily('20260801')

def test_empty_and_unconfigured(tmp_path):
    assert VisitorService('',tmp_path/'empty.db').daily('20260801')['source_mode']=='unconfigured'
    data=make(tmp_path,lambda _:httpx.Response(200,json=response([]))).daily('20260801')
    assert data['national_records']==0 and not data['complete']
    assert all(v is None for r in data['rows'] for v in r['groups'].values())

def test_last_page_reports_actual_row_count(tmp_path):
    calls=[]
    def handler(req):
        page=int(req.url.params['pageNo']);calls.append(page)
        assert page<=2
        return httpx.Response(200,json=response([record(group='1'),record(group='2')] if page==1 else [record(group='3')],page,3,2 if page==1 else 1))
    data=make(tmp_path,handler).daily('20260801')
    assert calls==[1,2] and data['national_records']==3
