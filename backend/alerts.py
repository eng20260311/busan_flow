"""Conservative, deterministic normalization. Original messages are never rewritten."""
import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel

KST = timezone(timedelta(hours=9))
SOURCE_URL = "https://www.safetydata.go.kr/disaster-data/view?dataSn=228"
FOCUS_DISTRICTS = ('동구', '중구', '서구', '영도구')


def recipient_scope(regions):
    targets = [d for d in FOCUS_DISTRICTS if any(
        re.fullmatch(r'부산(?:광역시)?\s+' + d + r'(?:\s+.*)?', r.strip()) for r in regions)]
    if targets:
        return targets, 'focus'
    if any(r.strip() in {'전국', '부산', '부산광역시', '부산 전체', '부산광역시 전체'} for r in regions):
        return [], 'common'
    return [], 'other'


class PayloadError(ValueError):
    pass


class Alert(BaseModel):
    alert_id: str
    source: str = "MOIS_SAFETY_MESSAGE"
    source_url: str = SOURCE_URL
    created_at: datetime
    original_message: str
    received_regions: list[str]
    target_districts: list[str] = []
    recipient_scope: str = 'other'
    official_emergency_level: str
    event_type: str
    severity: Literal["info", "caution", "danger"]
    recommendation_mode: Literal["inform", "disperse", "avoid", "evacuate", "review"]
    location_name: str | None
    flow_summary: str
    guidance_en: str
    guidance_type: str = "rule_template_not_full_translation"
    transport_advice: str | None = None
    requires_review: bool = False
    status: str = "unverified"


def classify(message: str, level: str = "") -> tuple[str, str, str, bool]:
    # Even an apparent cancellation is reviewed: it must not automatically clear a hazard.
    compact = re.sub(r"\s+", "", message)
    if any(word in compact for word in ("통제해제", "상황종료", "대피해제", "오발령", "정정")):
        return "other", "caution", "review", True
    hazards = (
        ("flood", ("침수", "범람", "홍수")),
        ("fire", ("산불", "화재", "폭발")),
        ("structural_risk", ("붕괴", "낙하")),
        ("wildlife_hazard", ("멧돼지", "야생동물", "상어")),
    )
    kind = next((kind for kind, words in hazards if any(w in compact for w in words)), None)
    if kind or any(w in compact for w in ("대피", "출입통제", "접근금지", "진입금지")) or level in ("긴급재난", "위급재난"):
        return kind or "other", "danger", "evacuate" if "대피" in compact else "avoid", kind is None
    if any(w in compact for w in ("교통정체", "차량정체", "극심한정체", "차량이용자제")):
        return "traffic_congestion", "caution", "disperse", False
    if any(w in compact for w in ("병원", "의원", "약국", "병·의원")) and any(w in compact for w in ("안내", "운영", "진료")):
        return "medical_info", "info", "inform", False
    return "other", "caution", "review", True


GUIDANCE = {
    "disperse": ("혼잡 안내입니다. 차량 방문을 자제하고 공식 안내에 따라 대중교통 이용을 검토하세요.", "Congestion notice. Avoid driving to the affected area and consider public transport. Follow the official notice."),
    "avoid": ("위험 가능성이 있습니다. 해당 지역 접근을 피하고 공식 안내를 확인하세요.", "Potential hazard. Avoid the affected area and follow the official notice."),
    "evacuate": ("원문에 대피 관련 안내가 있습니다. 대상지역·대상자·행동요령을 원문에서 확인하세요.", "The Korean notice mentions evacuation. Check the affected area, people and instructions in the official notice."),
    "inform": ("일반 의료 안내입니다. 운영시간과 이용방법은 원문을 확인하세요.", "Medical service information. Check the original notice for hours and instructions."),
    "review": ("자동 판단이 어렵습니다. 원문 확인과 수동 검토가 필요합니다.", "Manual review required. Check the original Korean notice before making travel decisions."),
}


def normalize(payload: dict) -> list[Alert]:
    if not isinstance(payload, dict) or not isinstance(payload.get("header"), dict) or payload["header"].get("resultCode") != "00":
        raise PayloadError("invalid_response_code")
    rows = payload.get("body")
    if not isinstance(rows, list):
        raise PayloadError("invalid_body")
    seen: dict[str, dict] = {}
    alerts = []
    for row in rows:
        if not isinstance(row, dict):
            raise PayloadError("invalid_record")
        sn = row.get("SN")
        if isinstance(sn, bool) or not isinstance(sn, (str, int)) or not str(sn).strip():
            raise PayloadError("missing_id")
        sn = str(sn)
        if sn in seen:
            if seen[sn] != row:
                raise PayloadError("conflicting_duplicate_requires_review")
            continue
        seen[sn] = row
        required = ("MSG_CN", "CRT_DT", "RCPTN_RGN_NM", "EMRG_STEP_NM")
        if any(not isinstance(row.get(k), str) or not row[k].strip() for k in required):
            raise PayloadError("missing_required_field")
        try:
            created = datetime.fromisoformat(row["CRT_DT"])
        except ValueError:
            try:
                created = datetime.strptime(row["CRT_DT"], "%Y/%m/%d %H:%M:%S")
            except ValueError:
                raise PayloadError("invalid_timestamp") from None
        if created.tzinfo is None:
            created = created.replace(tzinfo=KST)
        regions = [s.strip() for s in re.split(r"[,;|]", row["RCPTN_RGN_NM"]) if s.strip()]
        if not any("부산" in s or s == "전국" for s in regions):
            continue
        message = row["MSG_CN"]
        target_districts, scope = recipient_scope(regions)
        kind, severity, mode, review = classify(message, row["EMRG_STEP_NM"])
        # Hints only: recipient districts are not hazard polygons.
        locations = [s for s in ("북항친수공원", "이순신대로", "온천동") if s in message]
        location = " / ".join(locations) or None
        ko, en = GUIDANCE[mode]
        alerts.append(Alert(
            alert_id=sn, created_at=created, original_message=message,
            received_regions=regions, official_emergency_level=row["EMRG_STEP_NM"],
            target_districts=target_districts, recipient_scope=scope,
            event_type=kind, severity=severity, recommendation_mode=mode,
            location_name=location, flow_summary=ko, guidance_en=en,
            transport_advice="public_transit" if mode == "disperse" else None,
            requires_review=review or location is None,
        ))
    return sorted(alerts, key=lambda item: item.created_at, reverse=True)
