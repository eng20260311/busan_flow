import pytest
from backend.alerts import recipient_scope, normalize


@pytest.mark.parametrize('regions,expected',[
 (['부산광역시 동구','부산광역시 중구'],(['동구','중구'],'focus')),
 (['부산광역시 동구','부산광역시 동구'],(['동구'],'focus')),
 (['부산 서구','부산광역시 영도구'],(['서구','영도구'],'focus')),
 (['대구광역시 동구','부산광역시 금정구'],([],'other')),
 (['부산광역시 동래구'],([],'other')),
 (['부산광역시','전국'],([],'common')),
 (['부산광역시 전체'],([],'common')),
 (['부산광역시','부산광역시 동구'],(['동구'],'focus')),
])
def test_recipient_scope(regions,expected):
    assert recipient_scope(regions)==expected


def test_scope_uses_recipients_not_message_location():
    payload={'header':{'resultCode':'00'},'body':[{'SN':'scope-test','CRT_DT':'2026-09-28 01:00:00',
      'MSG_CN':'[합성 테스트] 동구에서 행사 안내','RCPTN_RGN_NM':'부산광역시 금정구','EMRG_STEP_NM':'안전안내'}]}
    alert=normalize(payload)[0]
    assert alert.target_districts==[] and alert.recipient_scope=='other'
