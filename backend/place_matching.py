"""Match extracted mentions against previously received TourAPI records."""
import json
import re
import sqlite3
from datetime import datetime, timezone
from backend.extraction import extract_notice
from backend.tourism import normalize_place, TourError, DISTRICTS


def name_key(value):
    return re.sub(r'[^가-힣a-z0-9]', '', value.casefold())


def match_notice(notice, db_path):
    mentions=extract_notice(notice['original_message'])['places']
    records={}
    with sqlite3.connect(db_path) as db:
        rows=db.execute('SELECT query,payload,fetched FROM tour_cache WHERE payload IS NOT NULL ORDER BY fetched').fetchall()
    for query,payload,fetched in rows:
        operation,params=json.loads(query)
        if operation!='areaBasedList2' or params.get('lDongRegnCd')!='26':continue
        for raw in json.loads(payload)['items']:
            try:p=normalize_place(raw)
            except TourError:continue
            if p['region_code']!='26':continue
            district=re.match(r'^부산(?:광역시)?\s+(\S+)\s',p['address']+' ')
            if not district or district[1] not in DISTRICTS:continue
            p.update(district=district[1],fetched_at=datetime.fromtimestamp(fetched,timezone.utc).isoformat())
            records[p['id']]=p
    matches=[]
    for p in records.values():
        title=name_key(p['name'])
        evidence=[]
        for m in mentions:
            key=name_key(m['text'])
            if m['text'] in DISTRICTS or len(key)<3:continue
            kind='exact' if key==title else 'partial' if key in title or title in key else None
            if kind:evidence.append({'mention':m['text'],'kind':kind,'evidence':m['evidence']})
        if evidence:matches.append(p|{'matches':evidence,'match_kind':'exact' if any(e['kind']=='exact' for e in evidence) else 'partial'})
    matches.sort(key=lambda p:(p['match_kind']!='exact',p['name'],p['id']))
    return {'places':matches,'mentions':mentions,'indexed_count':len(records),'source_mode':'stored_tour_api',
            'scope':'이전에 수신한 부산 4개 구 관광정보만 대조합니다. 전체 관광지·도로 검색이 아니며 최신 상태는 미확인입니다.',
            'location_verified':False,'safety_verified':False}
