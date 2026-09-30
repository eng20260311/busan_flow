from datetime import date,timedelta
import pytest
from backend.trends import analyze, TrendService
from backend.tourism import TourError, parse_response
import json

def snapshot():
    start=date(2026,6,1)
    days={(start+timedelta(days=i)).strftime('%Y%m%d'):{'status':'api','values':{d:{'2':'100','3':'20'} for d in ('동구','중구','서구','영도구')}} for i in range(84)}
    end=max(days)
    return {'latest_available_date':end,'days':days,'generated_at':'2026-09-27T12:00:00+09:00','collection_start':'20260601','discovery':{}}

def test_prior_four_same_weekdays_no_current_leakage():
    data=snapshot();end=data['latest_available_date'];data['days'][end]['values']['동구']['2']='150'
    p=analyze(data)['series'][0]['points'][-1]
    assert p['baseline_mean']=='100' and p['change_pct']=='50.0'
    assert end not in p['baseline_dates'] and p['baseline_observations']==4

def test_missing_baseline_not_partial_average():
    data=snapshot();end=date.fromisoformat('2026-08-23');key=(end-timedelta(days=7)).strftime('%Y%m%d')
    data['days'][key]['values']['동구']['2']=None
    p=analyze(data)['series'][0]['points'][-1]
    assert p['change_pct'] is None and p['baseline_observations']==3

def test_zero_and_missing_distinguished():
    data=snapshot();last=data['latest_available_date'];data['days'][last]['values']['동구']['2']='0'
    assert analyze(data)['series'][0]['points'][-1]['change_pct']=='-100'
    data['days'][last]['values']['동구']['2']=None
    assert analyze(data)['series'][0]['points'][-1]['comparison_status']=='missing_current'

def test_zero_baseline_not_infinite():
    data=snapshot()
    for v in data['days'].values():v['values']['동구']['2']='0'
    p=analyze(data)['series'][0]['points'][-1]
    assert p['comparison_status']=='zero_baseline' and p['change_pct'] is None

def test_windows_foreign_and_warmup():
    data=snapshot();eight=analyze(data,8);four=analyze(data,4)
    assert len(eight['series'])==8 and len(four['series'][0]['points'])==28
    assert len(eight['series'][0]['points'])==56
    assert eight['series'][1]['points'][0]['baseline_mean']=='20'
    assert four['series'][0]['points']==eight['series'][0]['points'][-28:]

def test_empty_provider_page_with_zero_size():
    p={'response':{'header':{'resultCode':'0000'},'body':{'items':'','totalCount':0,'pageNo':1,'numOfRows':0}}}
    assert parse_response(json.dumps(p).encode())['items']==[]

def test_discovery_and_missing_day_collection(tmp_path):
    s=TrendService('fake',tmp_path)
    def daily(day):
        if day=='20260924':raise TourError('upstream_timeout')
        value=None if day>'20260925' else '100'
        return {'rows':[{'district':d,'groups':{'2':value,'3':value}} for d in ('동구','중구','서구','영도구')],'source_mode':'api','fetched_at':'2026-09-27T00:00:00Z'}
    s.client.daily=daily
    result=s.collect(today=date(2026,9,27))
    assert result['end_date']=='20260925'
    assert result['failed_dates']==['20260924']
    assert s.get(4)['analysis']['weeks']==4

def test_discovery_error_not_mislabelled_as_latest(tmp_path):
    s=TrendService('fake',tmp_path)
    def daily(day):raise TourError('authentication_failed')
    s.client.daily=daily
    with pytest.raises(TourError):s.collect(today=date(2026,9,27))
    assert not s.path.exists()
