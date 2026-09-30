"""Text mentions only: never infer hazard geometry, active status or safety."""
import re
from datetime import datetime, timezone

VERSION = 'rules-1.0'
TYPES = {
    '침수·홍수': r'침수|범람|홍수', '화재·폭발': r'산불|화재|폭발',
    '붕괴·낙하': r'붕괴|낙하|산사태', '기상': r'호우|강풍|태풍|폭염|대설|풍랑|한파',
    '교통': r'교통\s*정체|차량\s*정체|교통사고',
    '야생동물': r'멧돼지|야생동물|상어', '의료 안내': r'병·?의원|병원|약국',
    '실종 안내': r'실종|찾습니다|찾고\s*있습니다',
}
ACTIONS = {
    '통제 언급': r'(?:출입|차량|교통|진입|양방향|전면)?\s*통제|접근\s*금지|진입\s*금지',
    '우회 언급': r'우회', '대피 언급': r'대피',
    '해제·종료 언급': r'(?:통제|대피|경보|주의보|특보)\s*해제|상황\s*종료|통행\s*재개',
    '정정 언급': r'정정|오발령',
}
# Only facility/road and administrative-name candidates; this is not a gazetteer.
PLACE = r'(?<![가-힣A-Za-z0-9])(?:[가-힣A-Za-z0-9·]+(?:지하차도|고가도로|친수공원|공원|터널|대교|교차로|해수욕장|대로|로\d*번길|\d+번길)|[가-힣0-9]{2,}(?:대로|로)|[가-힣]{2,}(?:동|읍|면|리)|(?:부산광역시|부산시|동구|중구|서구|영도구|동래구|금정구|부산진구|사상구|연제구|해운대구|수영구|남구|북구|강서구|사하구|기장군))(?=$|[\s,./~∼→()·]|에서|으로|부터|까지|일원|입구|인근|는|은|을|를|의|에)'
EXCLUDE_PLACES = {'대중교통','행동','이동','활동','운동','공동','일원','주의','안내','도로','병원으로','교통사고로'}
TIME = r'(?:\d{4}[-./]\d{1,2}[-./]\d{1,2}|\d{1,2}월\s*\d{1,2}일|\d{1,2}[./]\d{1,2}(?!\d)|\d{1,2}:\d{2}|(?:오전|오후)\s*\d{1,2}시(?:\s*\d{1,2}분)?|\d{1,2}시(?:\s*\d{1,2}분)?|금일|오늘|내일|당분간|추후\s*(?:안내|공지)\s*시까지|해제\s*시까지|연휴\s*기간)'


def extract_notice(message: str) -> dict:
    brackets = [m.span() for m in re.finditer(r'\[[^\]]*\]', message)]

    def hits(pattern, label=None, exclude_brackets=True):
        result=[]
        for match in re.finditer(pattern, message):
            start,end=match.span()
            # Sender labels and URLs are not incident locations or times.
            if exclude_brackets and any(a <= start < b for a,b in brackets):continue
            if any(a <= start < b for a,b in url_spans):continue
            text=match.group()
            if label=='장소명 후보' and (text in EXCLUDE_PLACES or re.search(
                r'(?:활동|행동|이동|운동|가동|작동)$|(?:침수|홍수|화재|산불|폭발|사고|정체|붕괴|호우|강풍|대설|폭우|사유|관계|예방|안전|재난|피해|주의보|특보|통제)로$',text)):
                continue
            left=max(message.rfind('\n',0,start),message.rfind('。',0,start))+1
            right=message.find('\n',end)
            result.append({'text':text,'label':label or text,'start':start,'end':end,
                           'evidence':message[left:right if right!=-1 else len(message)],
                           'verified':False})
        return result

    url_spans=[m.span() for m in re.finditer(r'https?://\S+|www\.\S+',message)]
    places=hits(PLACE,'장소명 후보')
    types=[item for label,pattern in TYPES.items() for item in hits(pattern,label)]
    actions=[item for label,pattern in ACTIONS.items() for item in hits(pattern,label)]
    times=hits(TIME,'시간 표현')
    # Keep scope phrasing verbatim instead of assigning a radius or polygon.
    scopes=hits(r'[^\n。]{0,60}(?:일원|인근|주변|양방향|전\s*구간|구간|반경\s*\d+(?:\.\d+)?\s*(?:km|m|미터|킬로미터))[^\n。]{0,60}','범위 표현',False)
    return {'method':'deterministic_rules','version':VERSION,
            'processed_at':datetime.now(timezone.utc).isoformat(),
            'places':places,'event_types':types,'actions':actions,'time_expressions':times,'scope_expressions':scopes,
            'status':'자동 추출 · 미검증','location_verified':False,'scope_verified':False,
            'requires_review':True,'safety_verified':False,
            'limitations':['표현의 존재만 추출합니다. 부정·예정·조건·예방 안내를 현재 발생 또는 해제로 확정하지 않습니다.',
                           '장소 데이터 대조·좌표 변환·영향범위 검증은 아직 수행하지 않습니다.',
                           '수신지역과 발신기관을 발생 위치로 사용하지 않습니다. 시간 표현은 절대 시각으로 추정하지 않습니다.']}
