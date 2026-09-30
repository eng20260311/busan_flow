import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from fastapi.staticfiles import StaticFiles

from backend.service import AlertService
from backend.tourism import TourService, TourError
from backend.visitors import VisitorService
from backend.trends import TrendService
from backend.candidates import candidates
from backend.evidence import EvidenceStore
from backend.north_port import case_data, explore
from backend.reviews import ReviewStore, ReviewInput
from backend.extraction import extract_notice
from backend.place_matching import match_notice
from backend.mobility import TransitService
from backend.route_comparison import CarService, ComparisonInput, compare_routes
from backend.recommendations import RecommendationService, RecommendationInput, IntentService


class SessionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    consent: bool
    mode: str = Field(max_length=20)


class EventInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    session_id: str = Field(max_length=36)
    query_id: str = Field(max_length=36)
    candidate_id: str = Field(max_length=40)
    action: str = Field(max_length=10)

ROOT = Path(__file__).resolve().parent.parent


def create_app(service=None, tour_service=None, visitor_service=None, evidence_store=None, transit_service=None, intent_service=None, car_service=None):
    load_dotenv(ROOT / ".env")
    app = FastAPI(title="부산 FLOW", version="0.1.0")
    if os.getenv('FLOW_PUBLIC_DEPLOYMENT') == '1':
        @app.middleware('http')
        async def public_routes(request, call_next):
            path = request.url.path
            allowed = {('GET','/'), ('GET','/api/health'), ('GET','/api/north-port'),
                       ('GET','/api/north-port/candidates'), ('POST','/api/route-comparison'),
                       ('POST','/api/recommendations')}
            static = request.method == 'GET' and path.startswith('/static/') and path not in ('/static/admin.html', '/static/index.html')
            if (request.method,path) not in allowed and not static:
                return JSONResponse({'detail':'not_found'},status_code=404)
            if path == '/api/north-port/candidates' and 'session_id' in request.query_params:
                return JSONResponse({'detail':'recording_disabled'},status_code=400)
            return await call_next(request)
    app.state.evidence = evidence_store or EvidenceStore(ROOT/'data/runtime/evidence.sqlite3')
    app.state.reviews = ReviewStore(ROOT/'data/runtime/reviews.sqlite3')

    @app.get('/api/notice-reviews/{key}')
    def notice_review(key: str):
        try:return app.state.reviews.get(key)
        except KeyError:raise HTTPException(404,'unknown_notice') from None

    @app.post('/api/notice-reviews/{key}')
    def save_notice_review(key: str, body: ReviewInput):
        try:return app.state.reviews.save(key,body)
        except KeyError:raise HTTPException(404,'unknown_notice') from None
        except ValueError:raise HTTPException(409,'다른 검토가 저장됐습니다. 기록을 다시 불러오세요.') from None

    @app.get('/api/notice-places/{key}')
    def notice_places(key: str):
        try:notice=app.state.reviews.get(key)['notice']
        except KeyError:raise HTTPException(404,'unknown_notice') from None
        return match_notice(notice,app.state.tour_service.db_path)

    @app.post('/api/test-sessions')
    def start_session(body: SessionInput):
        try:return app.state.evidence.start(body.consent,body.mode)
        except ValueError as exc:raise HTTPException(400,str(exc)) from None

    @app.delete('/api/test-sessions/{session_id}')
    def stop_session(session_id: str):
        try:app.state.evidence.stop(session_id)
        except ValueError:raise HTTPException(400,'invalid_session') from None
        return {'stopped':True}

    @app.post('/api/interactions')
    def record_event(body: EventInput):
        try:return app.state.evidence.event(body.session_id,body.query_id,body.candidate_id,body.action)
        except ValueError as exc:raise HTTPException(400,str(exc)) from None

    @app.get('/api/saved-candidates/{session_id}')
    def saved_candidates(session_id: str):
        try:return {'saved':app.state.evidence.saved(session_id)}
        except ValueError:raise HTTPException(400,'invalid_session') from None

    @app.get('/api/evidence/summary')
    def evidence_summary():return app.state.evidence.summary()

    @app.get('/api/evidence/export')
    def evidence_export():
        return Response(app.state.evidence.bundle(ROOT),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="busan-flow-evidence.zip"'})
    app.state.alert_service = service or AlertService(
        os.getenv("SAFETY_API_KEY", "").strip(), ROOT / "data/sample_alerts.json",
        ROOT / "data/runtime/flow.sqlite3",
    )
    app.state.tour_service = tour_service or TourService(os.getenv('TOUR_API_KEY', ''), ROOT / 'data/runtime/tour.sqlite3')
    app.state.visitor_service = visitor_service or VisitorService(os.getenv('DATALAB_API_KEY') or os.getenv('TOUR_API_KEY', ''), ROOT / 'data/runtime/visitors.sqlite3')
    app.state.trend_service = TrendService(os.getenv('DATALAB_API_KEY') or os.getenv('TOUR_API_KEY',''), ROOT/'data/runtime')
    app.state.transit_service = transit_service or TransitService(os.getenv('TMAP_APP_KEY', ''))
    app.state.car_service = car_service or CarService(os.getenv('KAKAO_REST_API_KEY', ''))
    app.state.recommendation_service = RecommendationService(
        app.state.alert_service, app.state.tour_service,
        app.state.transit_service,
        intent_service or IntentService(os.getenv('OPENAI_API_KEY', ''), os.getenv('OPENAI_MODEL', '')),
    )

    @app.post('/api/route-comparison')
    def route_comparison(body: ComparisonInput):
        return compare_routes(body, app.state.transit_service, app.state.car_service)

    @app.get('/api/north-port')
    def north_port():
        return case_data(ROOT, app.state.trend_service)

    @app.get('/api/north-port/candidates')
    def north_port_candidates(district: str='중구', session_id: str | None=None):
        try:
            if session_id: app.state.evidence.check(session_id)
            data = explore(ROOT, app.state.tour_service, app.state.trend_service, district)
            if session_id: data['query_id'] = app.state.evidence.record_query(session_id, data)
            return data
        except ValueError:
            raise HTTPException(400, 'invalid_district_or_session') from None

    @app.post('/api/recommendations')
    def recommend(body: RecommendationInput):
        try:
            return app.state.recommendation_service.recommend(body)
        except ValueError:
            raise HTTPException(400, 'invalid_origin_district') from None

    @app.get('/api/visitor-trends')
    def trends(weeks: int=8):
        if weeks not in (4,8):raise HTTPException(400,'invalid_weeks')
        return app.state.trend_service.get(weeks)

    @app.get('/api/candidates')
    def explore_candidates(origin: str='동구', district: str='중구', scenario: str='none', session_id: str | None=None, notice_key: str | None=None, place_id: str | None=None):
        try:
            context=None
            if notice_key or place_id:
                if not (notice_key and place_id):raise HTTPException(400,'incomplete_notice_selection')
                try:notice=app.state.reviews.get(notice_key)['notice']
                except KeyError:raise HTTPException(404,'unknown_notice') from None
                matched=match_notice(notice,app.state.tour_service.db_path)['places']
                selected=next((p for p in matched if p['id']==place_id and p['has_coordinates']),None)
                if not selected or selected['district']!=origin:raise HTTPException(400,'invalid_notice_place_selection')
                context={'notice_key':notice_key,'notice':notice,'selected_place':selected,'selection_method':'user_selection','location_verified':False}
            if session_id:app.state.evidence.check(session_id)
            data=candidates(app.state.tour_service, origin, district, scenario)
            if context:data['notice_context']=context
            if session_id:data['query_id']=app.state.evidence.record_query(session_id,data)
            return data
        except TourError:
            raise HTTPException(400, 'invalid_filter') from None
        except ValueError:
            raise HTTPException(400, 'invalid_session') from None

    @app.post('/api/visitor-trends/refresh')
    def refresh_trends():
        return app.state.trend_service.start()

    @app.get('/api/visitors')
    def visitors(day: str):
        try:
            return app.state.visitor_service.daily(day)
        except TourError as exc:
            raise HTTPException(400 if str(exc) == 'invalid_date' else 503, str(exc)) from None

    @app.get('/api/places')
    def places(district: str = '동구', content_type: str = '12', page: int = 1):
        try:
            return app.state.tour_service.places(district, content_type, page)
        except TourError as exc:
            raise HTTPException(400 if str(exc) == 'invalid_filter' else 503, str(exc)) from None

    @app.get("/api/health")
    def health():
        return {"status": "ok", "stage": "P0", "recommendations_ready": False}

    @app.get("/api/alerts")
    def alerts():
        try:
            data=app.state.alert_service.snapshot()
            source='synthetic_demo' if data['source_mode']=='synthetic_demo' else 'historical_sample' if data['source_mode']=='historical_sample' else 'api'
            for alert in data['alerts']:
                alert['review_key']=app.state.reviews.register(alert,source)
                alert['extraction']=extract_notice(alert['original_message'])
            return data
        except (ValueError, OSError):
            raise HTTPException(503, "Alert data unavailable") from None

    @app.get("/")
    def index():
        return FileResponse(ROOT / "frontend/index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")
    return app


app = create_app()
