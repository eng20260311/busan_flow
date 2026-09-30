"""KorService2 adapter, based on the supplied Korean manual v4.4."""
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import time
from urllib.parse import unquote
from xml.etree import ElementTree

import httpx

BASE = 'https://apis.data.go.kr/B551011/KorService2'
TYPES = {'12': '관광지', '14': '문화시설', '15': '축제공연행사', '25': '여행코스', '28': '레포츠', '32': '숙박', '38': '쇼핑', '39': '음식점'}
DISTRICTS = {'동구', '중구', '서구', '영도구'}
BUSAN_DISTRICTS = DISTRICTS | {'부산진구','동래구','남구','북구','해운대구','사하구','금정구','강서구','연제구','수영구','사상구','기장군'}
MAPPING = json.loads((Path(__file__).resolve().parents[1] / 'data/tour_classification.json').read_text(encoding='utf-8'))
CLASSIFICATION = {r['lclsSystm3']: r for r in MAPPING['records']}


class TourError(ValueError):
    pass


def parse_response(content):
    text = content.decode('utf-8-sig')
    if text.lstrip().startswith('<'):
        try:
            code = ElementTree.fromstring(text).findtext('.//returnReasonCode', '')
        except ElementTree.ParseError:
            code = ''
        # Never return arbitrary provider text or request URLs.
        raise TourError('authentication_failed' if code in {'20', '30', '31'} else 'upstream_xml_error')
    try:
        data = json.loads(text)['response']
        if data['header']['resultCode'] != '0000':
            raise TourError('upstream_error_code')
        body = data['body']
        total = int(body['totalCount'])
        page = int(body['pageNo'])
        size = int(body['numOfRows'])
        container = body.get('items')
        items = container.get('item', []) if isinstance(container, dict) else []
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list) or not all(isinstance(x, dict) for x in items):
            raise TourError('invalid_items')
        if total < 0 or page < 1 or size < 0 or (size == 0 and (total != 0 or items)) or (total > 0 and not items and (page - 1) * size < total):
            raise TourError('invalid_pagination')
        return {'items': items, 'total': total, 'page': page, 'page_size': size}
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, TourError):
            raise
        raise TourError('invalid_response') from None


def normalize_place(row):
    if not row.get('contentid') or not row.get('title'):
        raise TourError('invalid_place')
    lat = lon = None
    try:
        lon, lat = float(row.get('mapx', '')), float(row.get('mapy', ''))
        if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90) or (lon == 0 and lat == 0):
            lat = lon = None
    except (TypeError, ValueError):
        lat = lon = None
    codes = [str(row.get(k) or '') for k in ('lclsSystm1', 'lclsSystm2', 'lclsSystm3')]
    mapped = CLASSIFICATION.get(codes[2])
    kind = str(row.get('contenttypeid') or '')
    consistent = bool(mapped and mapped['contenttypeid'] == kind and mapped['lclsSystm1'] == codes[0] and mapped['lclsSystm2'] == codes[1])
    return {
        'id': str(row['contentid']), 'name': str(row['title']),
        'address': ' '.join(str(row.get(k) or '') for k in ('addr1', 'addr2')).strip(),
        'latitude': lat, 'longitude': lon, 'has_coordinates': lat is not None,
        'content_type': kind, 'type_name': TYPES.get(kind, '미확인'),
        'region_code': str(row.get('lDongRegnCd') or ''),
        'district_code': str(row.get('lDongSignguCd') or ''),
        'classification_codes': codes,
        'classification_name': mapped['small_name'] if consistent else None,
        'classification_verified': consistent,
        'modified_at_source': str(row.get('modifiedtime') or ''),
        'image_url': str(row.get('firstimage') or ''),
        'image_license': str(row.get('cpyrhtDivCd') or ''),
        'source': '한국관광공사 TourAPI', 'source_url': 'https://www.data.go.kr/data/15101578/openapi.do',
        'safety_verified': False, 'route_verified': False,
    }


class TourService:
    base_url = BASE
    mobile_os = 'WEB'
    def __init__(self, key, db_path, transport=None, clock=time):
        self.key = unquote(key.strip())  # Decode once; httpx encodes query params once.
        self.db_path, self.transport, self.clock = db_path, transport, clock
        self.lock = Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS tour_cache (query TEXT PRIMARY KEY, payload TEXT, fetched REAL, attempted REAL)')

    def _get(self, operation, params):
        if not self.key:
            raise TourError('missing_api_key')
        query = json.dumps([operation, params], sort_keys=True)
        with self.lock, sqlite3.connect(self.db_path) as db:
            now = self.clock()
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload,fetched,attempted FROM tour_cache WHERE query=?', (query,)).fetchone()
            if row and now - row[2] < (3600 if row[0] and row[1] == row[2] else 60):
                if row[0]:
                    return json.loads(row[0]), row[1], row[1] != row[2]
                raise TourError('retry_later')
            db.execute('INSERT OR REPLACE INTO tour_cache VALUES (?,?,?,?)', (query, row[0] if row else None, row[1] if row else None, now))
            db.commit()
            try:
                with httpx.Client(timeout=15, transport=self.transport, follow_redirects=False) as client:
                    response = client.get(self.base_url + '/' + operation, params={
                        'serviceKey': self.key, 'MobileOS': self.mobile_os, 'MobileApp': 'BusanFLOW',
                        '_type': 'json', **params,
                    })
                    response.raise_for_status()
                parsed = parse_response(response.content)
            except (httpx.HTTPError, UnicodeError, TourError) as exc:
                if row and row[0]:
                    return json.loads(row[0]), row[1], True
                if isinstance(exc, httpx.ConnectError):
                    reason = 'upstream_connection_failed'
                elif isinstance(exc, httpx.TimeoutException):
                    reason = 'upstream_timeout'
                elif isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {401, 403}:
                    reason = 'authentication_failed'
                elif isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                    reason = 'rate_limited'
                elif isinstance(exc, TourError):
                    reason = str(exc)  # Parser emits fixed codes only, never provider text.
                else:
                    reason = 'upstream_unavailable'
                raise TourError(reason) from None
            db.execute('UPDATE tour_cache SET payload=?, fetched=? WHERE query=?', (json.dumps(parsed, ensure_ascii=False), now, query))
            return parsed, now, False

    def places(self, district='동구', content_type='12', page=1, keyword=None):
        if district not in BUSAN_DISTRICTS or content_type not in TYPES or not 1 <= page <= 20:
            raise TourError('invalid_filter')
        if keyword is not None and (not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 80):
            raise TourError('invalid_filter')
        if not self.key:
            return {'source_mode': 'unconfigured', 'places': [], 'total': None, 'has_more': False, 'safety_verified': False}
        codes, _, codes_stale = self._get('ldongCode2', {'lDongRegnCd': '26', 'lDongListYn': 'N', 'pageNo': 1, 'numOfRows': 100})
        matches = [str(r['code']) for r in codes['items'] if r.get('name') == district and r.get('code')]
        if len(matches) != 1:
            raise TourError('district_code_unresolved')
        params = {
            'lDongRegnCd': '26', 'lDongSignguCd': matches[0], 'contentTypeId': content_type,
            'arrange': 'C', 'pageNo': page, 'numOfRows': 20,
        }
        if keyword is not None:
            params['keyword'] = keyword.strip()
            params.pop('contentTypeId')  # v4.4 keyword search uses classification filters instead.
        result, fetched, stale = self._get('searchKeyword2' if keyword is not None else 'areaBasedList2', params)
        if result['page'] != page:
            raise TourError('unexpected_page')
        places = [normalize_place(r) for r in result['items']]
        if any(p['region_code'] != '26' or p['district_code'] != matches[0] or (keyword is None and p['content_type'] != content_type) for p in places):
            raise TourError('response_filter_mismatch')
        if keyword is not None:
            places = [p for p in places if p['content_type'] == content_type]
        unique = {p['id']: p for p in places}
        return {
            'source_mode': 'cached_stale' if stale or codes_stale else 'api',
            'fetched_at': datetime.fromtimestamp(fetched, timezone.utc).isoformat(),
            'places': list(unique.values()), 'total': result['total'], 'page': page,
            'has_more': page * result['page_size'] < result['total'],
            'safety_verified': False,
        }
