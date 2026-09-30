"""Daily district visitor estimates. No real-time congestion or cross-area sums."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re

from backend.tourism import TourService, TourError, DISTRICTS

GROUPS = {'1': '현지인', '2': '외지인', '3': '외국인'}
KST = timezone(timedelta(hours=9))


class VisitorService(TourService):
    base_url = 'https://apis.data.go.kr/B551011/DataLabService'
    mobile_os = 'ETC'
    page_size = 100

    def daily(self, day):
        try:
            if not re.fullmatch(r'\d{8}', day):
                raise ValueError()
            selected = datetime.strptime(day, '%Y%m%d').date()
            if selected >= datetime.now(KST).date():
                raise ValueError()
        except (TypeError, ValueError):
            raise TourError('invalid_date') from None
        if not self.key:
            return {'source_mode': 'unconfigured', 'date': day, 'rows': [], 'complete': False}
        rows, stale, fetched = {}, False, []
        total = None
        raw_count = 0
        seen = {}
        # Manual specifies date filters only. Retrieve every national page before filtering Busan.
        for page in range(1, 21):
            result, timestamp, was_stale = self._get('locgoRegnVisitrDDList', {
                'startYmd': day, 'endYmd': day, 'numOfRows': self.page_size, 'pageNo': page,
            })
            if result['page'] != page or (total is not None and total != result['total']):
                raise TourError('inconsistent_pagination')
            total = result['total']
            raw_count += len(result['items'])
            stale |= was_stale
            fetched.append(timestamp)
            for row in result['items']:
                if str(row.get('baseYmd')) != day:
                    raise TourError('response_date_mismatch')
                code, group = str(row.get('signguCode', '')), str(row.get('touDivCd', ''))
                identity = (day, code, group)
                if identity in seen:
                    # A repeated record across pages may conceal a missing record.
                    raise TourError('duplicate_record')
                seen[identity] = True
                if not re.fullmatch(r'\d{5}', code) or group not in GROUPS:
                    raise TourError('invalid_record')
                if not code.startswith('26') or row.get('signguNm') not in DISTRICTS:
                    continue
                try:
                    number = Decimal(str(row['touNum']))
                    if not number.is_finite() or number < 0:
                        raise ValueError()
                except (KeyError, ValueError, InvalidOperation):
                    raise TourError('invalid_visitor_count') from None
                name = row['signguNm']
                if name in rows and rows[name]['district_code'] != code:
                    raise TourError('district_code_conflict')
                district = rows.setdefault(name, {'district': name, 'district_code': code, 'groups': {}})
                district['groups'][group] = str(number)  # Preserve source decimal precision.
            # DataLab reports numOfRows=actual returned rows on the final page.
            if raw_count >= total:
                break
        else:
            raise TourError('page_limit_exceeded')
        if raw_count != total:
            raise TourError('incomplete_response')
        output = []
        for name in ('동구', '중구', '서구', '영도구'):
            item = rows.get(name, {'district': name, 'district_code': None, 'groups': {}})
            item['groups'] = {g: item['groups'].get(g) for g in GROUPS}
            output.append(item)
        return {
            'source_mode': 'cached_stale' if stale else 'api', 'date': day,
            'fetched_at': datetime.fromtimestamp(min(fetched), KST).isoformat(),
            'rows': output, 'complete': all(v is not None for r in output for v in r['groups'].values()),
            'national_records': total, 'pages': page, 'groups': GROUPS,
            'is_realtime': False, 'metric': 'daily_mobile_network_estimate',
            'source_url': 'https://www.data.go.kr/data/15101972/openapi.do',
        }
