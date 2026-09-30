"""Decode official JSON responses and XML-only gateway errors safely."""
import json
from xml.etree import ElementTree

ERRORS = {
    '20': 'access_denied', '22': 'rate_limited', '30': 'unregistered_key',
    '31': 'expired_key', '32': 'unregistered_ip', '33': 'missing_key',
    '10': 'invalid_parameters', '11': 'missing_parameters', '02': 'timeout',
}


class SafetyResponseError(ValueError):
    def __init__(self, code):
        self.code = code if code in ERRORS else 'unknown'
        self.reason = ERRORS.get(code, 'invalid_response')
        super().__init__(self.reason)


def decode_response(content):
    text = content.decode('utf-8-sig')
    if text.lstrip().startswith('<'):
        try:
            root = ElementTree.fromstring(text)
            code = root.findtext('.//returnReasonCode') or root.findtext('.//resultCode') or ''
        except ElementTree.ParseError:
            code = ''
        raise SafetyResponseError(code.strip())
    try:
        payload = json.loads(text)
        code = payload['header']['resultCode']
    except (ValueError, KeyError, TypeError):
        raise SafetyResponseError('') from None
    if code != '00':
        raise SafetyResponseError(str(code))
    return payload
