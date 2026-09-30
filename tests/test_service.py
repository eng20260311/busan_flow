import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.service import AlertService, INTERVAL

SAMPLE = Path(__file__).resolve().parents[1] / "data/sample_alerts.json"


def service(tmp_path, key="", handler=None, clock=lambda: 1790478000):
    return AlertService(key, SAMPLE, tmp_path / "flow.sqlite3", httpx.MockTransport(handler) if handler else None, clock)


def upstream_response():
    payload = json.loads(SAMPLE.read_text(encoding="utf-8"))
    payload.pop("_meta")
    return payload


def test_no_key_is_explicit_synthetic_demo(tmp_path):
    data = service(tmp_path).snapshot()
    assert data["source_mode"] == "synthetic_demo"
    assert data["fetched_at"] is None
    assert not data["safety_verified"]


def test_success_utf8_cache_restart_and_archive_dedup(tmp_path):
    calls = []
    clock = [1790478000]
    def handler(request):
        calls.append(request)
        assert request.url.params["rgnNm"] == "부산광역시"
        return httpx.Response(200, content=json.dumps(upstream_response(), ensure_ascii=False).encode("utf-8"))
    first = service(tmp_path, "test-only-key", handler, lambda: clock[0])
    result = first.snapshot()
    assert result["source_mode"] == "live"
    assert "북항친수공원" in result["alerts"][0]["original_message"]
    first.snapshot()
    restarted = service(tmp_path, "test-only-key", handler, lambda: clock[0])
    restarted.snapshot()
    assert len(calls) == 1
    clock[0] += INTERVAL
    restarted.snapshot()
    assert len(calls) == 2
    with restarted.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM raw_alerts").fetchone()[0] == 4
        assert "test-only-key" not in str(db.execute("SELECT * FROM state").fetchall())


@pytest.mark.parametrize("failure", ["timeout", "http", "code", "malformed", "encoding"])
def test_failure_fallback_no_secret_and_no_immediate_retry(tmp_path, failure):
    calls = []
    def handler(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("sensitive upstream URL with test-only-key", request=request)
        if failure == "http":
            return httpx.Response(403)
        if failure == "code":
            return httpx.Response(200, json={"header": {"resultCode": "99"}})
        if failure == "encoding":
            return httpx.Response(200, content=b"\xff")
        return httpx.Response(200, content=b"not json")
    instance = service(tmp_path, "test-only-key", handler)
    result = instance.snapshot()
    assert result["source_mode"] == "synthetic_demo"
    assert result["fetch_status"] == "upstream_unavailable"
    assert "test-only-key" not in json.dumps(result)
    instance.snapshot()
    assert len(calls) == 1


def test_failure_after_success_uses_marked_stale_cache(tmp_path):
    clock = [1790478000]
    successful = [True]
    def handler(request):
        return httpx.Response(200, json=upstream_response()) if successful[0] else httpx.Response(503)
    instance = service(tmp_path, "test-only-key", handler, lambda: clock[0])
    initial = instance.snapshot()
    clock[0] += INTERVAL
    successful[0] = False
    stale = instance.snapshot()
    assert stale["source_mode"] == "cached_stale"
    assert stale["fetched_at"] == initial["fetched_at"]


def test_partial_page_disclosed(tmp_path):
    payload = upstream_response()
    payload["totalCount"] = 400
    instance = service(tmp_path, "test-only-key", lambda _: httpx.Response(200, json=payload))
    assert instance.snapshot()["coverage"] == "partial_or_unknown"


def test_empty_success_is_not_replaced_with_fake_alerts(tmp_path):
    payload = {"header": {"resultCode": "00"}, "body": [], "totalCount": 0}
    instance = service(tmp_path, "test-only-key", lambda _: httpx.Response(200, json=payload))
    result = instance.snapshot()
    assert result["source_mode"] == "live" and result["alerts"] == []


def test_http_routes_and_static_files(tmp_path):
    with TestClient(create_app(service(tmp_path))) as client:
        assert client.get("/api/health").json()["stage"] == "P0"
        assert client.get("/api/alerts").json()["source_mode"] == "synthetic_demo"
        assert "부산 FLOW" in client.get("/").text
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/.env").status_code == 404
        assert client.get("/data/runtime/flow.sqlite3").status_code == 404
