# 부산 FLOW

북항의 과거 실제 안전문자를 확인하고 주변 관광지·이동 방법을 선택하는 FastAPI 시연 앱입니다.

## Render 설정

- Language: Python 3
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT --no-access-log`
- Health Check Path: `/api/health`
- 환경변수 `PYTHON_VERSION=3.14.7`, `FLOW_PUBLIC_DEPLOYMENT=1`
- `TMAP_APP_KEY`, `KAKAO_REST_API_KEY`: Render 환경변수에서 별도 입력
- `TOUR_API_KEY`: 다른 출발지 자유입력 검색을 사용할 때 입력

`render.yaml` Blueprint도 제공합니다. 키는 저장소·화면·로그에 입력하지 않습니다. .env 파일은 업로드하지 않습니다. 공개 시연에서 관리·기록·증빙 API는 비활성화합니다.

## 데이터와 한계

기본 북항 관광지 목록과 과거 방문 추이는 공개 필드만 포함한 저장 스냅샷으로 표시하므로 초기 배포에서 로컬 DB가 없어도 작동합니다. 키가 없는 이동 조회는 미설정으로 표시하고 외부 카카오맵 연결을 제공합니다. 문자 발령시각과 원문을 보존합니다. 2026-09-24~25 과거 사례이며 현재 사건·혼잡·운영·안전 경로를 검증한 서비스가 아닙니다.

사진·관광정보: 한국관광공사 TourAPI. 방문 통계: 한국관광공사 지역별 방문자수 API(2026-07-04~08-28 표시 기간). 문자: 행정안전부. 첫 화면은 AI 생성 부산 항구 일러스트입니다. 관광객 방문·혼잡 감소 성과를 주장하지 않습니다.

저장은 사용자의 브라우저에만 보관하며 서버 이용성과로 집계하지 않습니다. 키·개인 기록·기존 세션·리뷰·DB·증빙 ZIP은 이 저장소에 없습니다. Render 무료 서비스는 비활성 시 중지되고 런타임 파일은 영구 보존되지 않습니다. 기본 공개 스냅샷은 배포 파일에 포함됩니다.

## 로컬 실행·검증

Python 3.11 이상을 대상으로 작성했고 Python 3.14.7에서 검증했습니다.

```sh
pip install -r requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000
python -m pytest -q
```

공개 배포 전 `FLOW_PUBLIC_DEPLOYMENT=1`을 설정하세요. 재난문자 API 신규 조회는 등록 IP 제약이 있어 기본 배포는 과거 사례 재현을 사용합니다.
