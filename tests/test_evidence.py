import io
import json
import zipfile
import pytest
from backend.evidence import EvidenceStore


def snapshot(scenario='none'):
    return {'origin':'동구','district':'중구','risk':{'scenario':scenario,'is_synthetic':scenario!='none'},
            'courses':[{'id':'candidate-1','places':[{'name':'검증용 장소'}],'safety_verified':False}]}


def test_consent_dedup_session_ownership_and_immutable_save(tmp_path):
    store=EvidenceStore(tmp_path/'log.db')
    with pytest.raises(ValueError):store.start(False,'user_test')
    session=store.start(True,'developer')['session_id'];other=store.start(True,'developer')['session_id']
    data=snapshot();q=store.record_query(session,data)
    data['courses'][0]['places'][0]['name']='changed'
    with pytest.raises(ValueError):store.event(other,q,'candidate-1','save')
    with pytest.raises(ValueError):store.event(session,q,'candidate-2','save')
    assert store.event(session,q,'candidate-1','save')['recorded']
    assert not store.event(session,q,'candidate-1','save')['recorded']
    assert store.saved(session)[0]['course']['places'][0]['name']=='검증용 장소'
    assert EvidenceStore(tmp_path/'log.db').summary()['groups'][0]['save']==1
    store.stop(session)
    with pytest.raises(ValueError):store.event(session,q,'candidate-1','select')


def test_modes_scenarios_and_export_no_identifiers(tmp_path):
    store=EvidenceStore(tmp_path/'log.db');ids=[]
    for mode,scenario in [('developer','demo_control'),('user_test','none')]:
        s=store.start(True,mode)['session_id'];ids.append(s);store.record_query(s,snapshot(scenario))
    assert len(store.summary()['groups'])==2
    with zipfile.ZipFile(io.BytesIO(store.bundle(tmp_path))) as archive:
        report=archive.read('interaction_summary.json').decode()
        assert all(s not in report for s in ids)
        assert len(json.loads(report)['groups'])==2
        assert 'manifest.json' in archive.namelist()


def test_blocked_query_does_not_create_fictitious_selection(tmp_path):
    store=EvidenceStore(tmp_path/'log.db');s=store.start(True,'developer')['session_id']
    data=snapshot('demo_unknown');data['courses']=[];q=store.record_query(s,data)
    with pytest.raises(ValueError):store.event(s,q,'candidate-1','select')
    assert store.summary()['groups'][0]['select']==0
