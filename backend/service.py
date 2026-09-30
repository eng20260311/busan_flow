"""Single-page upstream polling with durable cooldown and local raw-record archive."""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from time import time

import httpx

from backend.alerts import KST, PayloadError, normalize
from backend.safety_response import decode_response, SafetyResponseError

BASE_URL = "https://www.safetydata.go.kr/V2/api/DSSP-IF-00247"
INTERVAL = 900


class AlertService:
    def __init__(self, api_key: str, sample_path: Path, db_path: Path, transport=None, clock=time):
        self.api_key, self.sample_path, self.db_path = api_key, sample_path, db_path
        self.transport, self.clock = transport, clock
        self.lock = Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS raw_alerts (sn TEXT PRIMARY KEY, record TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def _state(self, db, key, default=None):
        row = db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def _set(self, db, key, value):
        db.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (key, str(value)))

    def snapshot(self):
        with self.lock:
            return self._snapshot()

    def store_verified_payload(self, payload, fetched_at):
        normalize(payload)
        total = payload.get('totalCount')
        complete = str(total).isdigit() and int(total) == len({str(r['SN']) for r in payload['body']})
        with self.connect() as db:
            for row in payload['body']:
                db.execute('INSERT OR IGNORE INTO raw_alerts VALUES (?, ?)',
                           (str(row['SN']), json.dumps(row, ensure_ascii=False)))
            self._set(db,'payload',json.dumps(payload,ensure_ascii=False))
            self._set(db,'fetched_at',fetched_at)
            self._set(db,'coverage','complete_page' if complete else 'partial_or_unknown')
            self._set(db,'fetch_status','ok')
            self._set(db,'failure_reason','')

    def _snapshot(self):
        now = self.clock()
        if self.api_key:
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                last = float(self._state(db, "last_attempt", "-1000000000"))
                should_fetch = now - last >= INTERVAL
                if should_fetch:
                    # Claim the request before network I/O so failures/restarts also count.
                    self._set(db, "last_attempt", now)
                    self._set(db, "fetch_status", "refresh_in_progress")
            if should_fetch:
                try:
                    with httpx.Client(timeout=12, transport=self.transport, follow_redirects=False) as client:
                        response = client.get(BASE_URL, params={
                            "serviceKey": self.api_key, "returnType": "json", "pageNo": 1,
                            "numOfRows": 100, "rgnNm": "부산광역시",
                            "crtDt": (datetime.fromtimestamp(now, KST) - timedelta(days=1)).strftime("%Y%m%d"),
                        })
                        response.raise_for_status()
                        payload = decode_response(response.content)
                    self.store_verified_payload(payload, now)
                except (httpx.HTTPError, UnicodeError, ValueError) as exc:
                    # Never include exception text: upstream URLs can contain serviceKey.
                    with self.connect() as db:
                        self._set(db, "fetch_status", "upstream_unavailable")
                        reason = exc.reason if isinstance(exc, SafetyResponseError) else ('connection_failed' if isinstance(exc, httpx.ConnectError) else 'response_or_network_error')
                        self._set(db, "failure_reason", reason)
        with self.connect() as db:
            cached = self._state(db, "payload") if self.api_key else None
            fetched = self._state(db, "fetched_at") if cached else None
            fetch_status = self._state(db, "fetch_status") if self.api_key else "missing_api_key"
            last_attempt = self._state(db, "last_attempt") if self.api_key else None
            coverage = self._state(db, "coverage", "partial_or_unknown")
            failure_reason = self._state(db, "failure_reason", "") if self.api_key else "missing_key"
        if cached:
            payload = json.loads(cached)
            source_mode = "live" if fetch_status == "ok" and now - float(fetched) < INTERVAL else "cached_stale"
        else:
            payload = json.loads(self.sample_path.read_text(encoding="utf-8"))
            source_mode = "synthetic_demo" if payload.get("_meta", {}).get("is_synthetic", True) else "historical_sample"
            coverage = "sample_only"
        alerts = normalize(payload)
        latest = max((a.created_at for a in alerts), default=None)
        return {
            "source_mode": source_mode,
            "fetch_status": fetch_status,
            "failure_reason": failure_reason,
            "fetched_at": datetime.fromtimestamp(float(fetched), KST).isoformat() if fetched else None,
            "latest_alert_at": latest.isoformat() if latest else None,
            "next_fetch_allowed_at": datetime.fromtimestamp(float(last_attempt) + INTERVAL, KST).isoformat() if last_attempt else None,
            "poll_interval_seconds": INTERVAL,
            "coverage": coverage,
            "safety_verified": False,
            "alerts": [a.model_dump(mode="json") for a in alerts],
        }
