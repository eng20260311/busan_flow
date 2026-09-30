"""Recent visitor trends with four strictly prior same-weekday observations."""
import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Lock, Thread

from backend.visitors import VisitorService, KST
from backend.tourism import TourError

DISTRICTS = ('동구', '중구', '서구', '영도구')
SOURCE = 'https://www.data.go.kr/data/15101972/openapi.do'


def analyze(snapshot, weeks=8):
    if weeks not in (4, 8):
        raise TourError('invalid_weeks')
    end = datetime.strptime(snapshot['latest_available_date'], '%Y%m%d').date()
    start = end - timedelta(days=weeks * 7 - 1)
    days = snapshot['days']
    series = []
    for district in DISTRICTS:
        for group in ('2', '3'):
            def value(day):
                raw = days.get(day, {}).get('values', {}).get(district, {}).get(group)
                return Decimal(raw) if raw is not None else None
            points = []
            for offset in range(weeks * 7):
                day = start + timedelta(days=offset)
                key = day.strftime('%Y%m%d')
                current = value(key)
                baseline_dates = [(day - timedelta(days=7 * i)).strftime('%Y%m%d') for i in range(1,5)]
                history = [value(d) for d in baseline_dates]
                observed = sum(v is not None for v in history)
                mean = sum(history, Decimal(0)) / 4 if observed == 4 else None
                change = (current / mean - 1) * 100 if current is not None and mean is not None and mean > 0 else None
                status = 'ok' if change is not None else ('missing_current' if current is None else 'missing_baseline' if mean is None else 'zero_baseline')
                points.append({'date':key,'value':str(current) if current is not None else None,
                               'baseline_mean':str(mean) if mean is not None else None,
                               'change_pct':str(change) if change is not None else None,
                               'baseline_observations':observed,'baseline_dates':baseline_dates,
                               'comparison_status':status,'data_status':days.get(key,{}).get('status','missing')})
            series.append({'district':district,'group':group,'points':points,
                           'missing_dates':[p['date'] for p in points if p['value'] is None],
                           'unavailable_comparisons':sum(p['change_pct'] is None for p in points)})
    return {'weeks':weeks,'start_date':start.strftime('%Y%m%d'),'end_date':end.strftime('%Y%m%d'),
            'series':series,'generated_at':snapshot['generated_at'],
            'baseline_start':(start-timedelta(days=28)).strftime('%Y%m%d'),
            'discovery':snapshot['discovery'],'collection_start':snapshot['collection_start'],
            'source_url':SOURCE,'method':'(value / mean(t-7,t-14,t-21,t-28) - 1) * 100',
            'missing_policy':'Require all four baseline dates; never fill missing values with zero.',
            'failed_dates':[d for d,v in days.items() if v['status']=='request_failed'],
            'stale_dates':[d for d,v in days.items() if v['status']=='cached_stale'],
            'observed_dates':[d for d,v in days.items() if v.get('values')],
            'is_realtime':False}


class TrendService:
    def __init__(self, key, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'visitor_trends.json'
        self.client = VisitorService(key,self.directory/'trend_pages.sqlite3')
        self.client.page_size = 1000
        self.lock = Lock()
        self.state = {'status':'idle','completed':0,'total':84}

    def get(self, weeks=8):
        with self.lock:
            state = dict(self.state)
        result = {'job':state, 'analysis':None}
        if self.path.exists():
            result['analysis'] = analyze(json.loads(self.path.read_text(encoding='utf-8')), weeks)
        return result

    def start(self):
        with self.lock:
            if self.state['status'] in ('discovering','collecting'):
                return dict(self.state)
            # Avoid repeated full collections from UI clicks; existing results remain inspectable.
            if self.path.exists():
                stamp = datetime.fromisoformat(json.loads(self.path.read_text(encoding='utf-8'))['generated_at'])
                if (datetime.now(KST)-stamp).total_seconds() < 3600:
                    return {'status':'cached','completed':84,'total':84}
            self.state = {'status':'discovering','completed':0,'total':84}
        Thread(target=self._run,daemon=True).start()
        return dict(self.state)

    def _progress(self, **kwargs):
        with self.lock:self.state.update(kwargs)

    def _run(self):
        try:
            self.collect()
        except Exception:
            # Do not expose exceptions, request URLs or credentials to clients.
            self._progress(status='failed',error='collection_failed')

    def collect(self, today=None):
        today = today or datetime.now(KST).date()
        if not self.client.key:
            raise TourError('missing_api_key')
        discovered = None
        checked = []
        for ago in range(1,91):
            day = (today-timedelta(days=ago)).strftime('%Y%m%d')
            self._progress(status='discovering',checking_date=day)
            data = self.client.daily(day)
            checked.append(day)
            if any(r['groups'].get(g) is not None for r in data['rows'] for g in ('2','3')):
                discovered = (day,data)
                break
        if discovered is None:
            raise TourError('no_recent_data_within_90_days')
        end = datetime.strptime(discovered[0],'%Y%m%d').date()
        start = end-timedelta(days=83)  # 8 weeks displayed + 4 weeks baseline.
        days = {}
        for offset in range(84):
            day=(start+timedelta(days=offset)).strftime('%Y%m%d')
            self._progress(status='collecting',checking_date=day,completed=offset,total=84)
            try:
                data=discovered[1] if day==discovered[0] else self.client.daily(day)
                days[day]={'status':data['source_mode'],'fetched_at':data['fetched_at'],
                           'values':{r['district']:{g:r['groups'][g] for g in ('2','3')} for r in data['rows']}}
            except TourError:
                days[day]={'status':'request_failed','values':{}}
        snapshot={'latest_available_date':discovered[0],'collection_start':start.strftime('%Y%m%d'),
                  'generated_at':datetime.now(KST).isoformat(),'days':days,
                  'discovery':{'checked_from':checked[0],'checked_through':checked[-1],
                               'checked_dates':checked,'rule':'Most recent day with at least one target district/group observation; partial dates retained.'}}
        tmp=self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(tmp,self.path)
        self._progress(status='complete',completed=84,total=84)
        return analyze(snapshot)
