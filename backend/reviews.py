"""Local manual review journal bound to immutable notice content versions."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    revision: int = Field(ge=0)
    place: str = Field(default='',max_length=300)
    latitude: float | None = Field(default=None,ge=-90,le=90)
    longitude: float | None = Field(default=None,ge=-180,le=180)
    area: str = Field(default='',max_length=3000)
    evidence_url: str = Field(default='',max_length=2000)
    document: str = Field(default='',max_length=1000)
    published_at: datetime | None = None
    reviewer: str = Field(min_length=1,max_length=100)
    status: Literal['unverified','location','area','released']
    recheck_at: datetime

    @model_validator(mode='after')
    def validate_review(self):
        now=datetime.now(timezone.utc)
        if not self.recheck_at.tzinfo or self.recheck_at <= now:
            raise ValueError('재확인 시점은 시간대가 있는 미래 시각이어야 합니다.')
        if self.published_at and (not self.published_at.tzinfo or self.published_at > now):
            raise ValueError('발행 시각은 시간대가 있는 현재 이전 시각이어야 합니다.')
        if self.evidence_url:
            from urllib.parse import urlsplit
            url=urlsplit(self.evidence_url)
            if url.scheme not in ('http','https') or not url.hostname or url.username or url.password:
                raise ValueError('근거 URL은 인증정보 없는 http/https 주소여야 합니다.')
        if (self.latitude is None)!=(self.longitude is None):
            raise ValueError('위도와 경도를 함께 입력하세요.')
        if self.status!='unverified':
            if not self.place or self.latitude is None or not (self.evidence_url or self.document) or not self.published_at:
                raise ValueError('확인 상태에는 장소·좌표·근거 URL 또는 문서·발행 시각이 필요합니다.')
        if self.status in ('area','released') and not self.area:
            raise ValueError('범위·해제 확인에는 공식 구역 또는 도로 구간이 필요합니다.')
        return self


class ReviewStore:
    def __init__(self,path):
        self.path=path;path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(path) as db:
            db.executescript('CREATE TABLE IF NOT EXISTS notices(key TEXT PRIMARY KEY, payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS reviews(key TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(key,revision));')

    def register(self,alert,source):
        record={k:alert[k] for k in ('alert_id','created_at','original_message','received_regions')}
        record['source_kind']=source
        text=json.dumps(record,ensure_ascii=False,sort_keys=True)
        key=hashlib.sha256(text.encode()).hexdigest()
        with sqlite3.connect(self.path) as db:db.execute('INSERT OR IGNORE INTO notices VALUES (?,?)',(key,text))
        return key

    def get(self,key):
        with sqlite3.connect(self.path) as db:
            notice=db.execute('SELECT payload FROM notices WHERE key=?',(key,)).fetchone()
            if not notice:raise KeyError('unknown_notice')
            rows=db.execute('SELECT payload FROM reviews WHERE key=? ORDER BY revision DESC',(key,)).fetchall()
        history=[json.loads(r[0]) for r in rows]
        latest=history[0] if history else None
        return {'notice':json.loads(notice[0]),'latest':latest,'history':history,
                'recheck_due':bool(latest and datetime.fromisoformat(latest['recheck_at'])<=datetime.now(timezone.utc)),
                'safety_verified':False,'automated_filter_applied':False}

    def save(self,key,body):
        record=body.model_dump(mode='json')
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM notices WHERE key=?',(key,)).fetchone():raise KeyError('unknown_notice')
            current=db.execute('SELECT COALESCE(MAX(revision),0) FROM reviews WHERE key=?',(key,)).fetchone()[0]
            if current!=body.revision:raise ValueError('revision_conflict')
            record.update(revision=current+1,reviewed_at=datetime.now(timezone.utc).isoformat())
            db.execute('INSERT INTO reviews VALUES (?,?,?)',(key,current+1,json.dumps(record,ensure_ascii=False)))
        return self.get(key)
