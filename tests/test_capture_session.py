# -*- coding: utf-8 -*-
import datetime as dt
import hashlib
import pytest
from yyjh.capture.session import unwrap_download3
from yyjh.core import codecs, xxtea
from yyjh.game import savefmt

class FakeHar:
    @staticmethod
    def header(entry, name):
        return entry['headers'].get(name)

def fixture(shift=0, session='1234567890', runtime='android'):
    now = dt.datetime(2026, 10, 30, 8, 14, 45, tzinfo=dt.timezone.utc)
    entry = {'headers': {'command': 'download3', 'session': session},
             'startedDateTime': (now + dt.timedelta(seconds=shift)).isoformat()}
    data = {'DBVersion': 73570, 'Synthetic': 'Only test data'}
    inner = 'xi9iz9h4po06ewkx'
    content = savefmt.build_old(data, '00073570', inner)
    token = hashlib.md5(f'{runtime}_{session}_{int(now.timestamp())}'.encode()).hexdigest()[:16]
    payload = codecs.b64e(xxtea.encrypt(content.encode('ascii'), token))
    return entry, payload, data, inner

def test_exact_second():
    e, raw, expected, key = fixture()
    assert unwrap_download3(FakeHar(), e, raw, 'android', [key]) == ('00073570', expected, key)

def test_har_time_skew():
    e, raw, expected, key = fixture(shift=3)
    assert unwrap_download3(FakeHar(), e, raw, 'android', [key])[1] == expected

def test_wrong_session_not_accepted():
    e, raw, expected, key = fixture()
    e['headers']['session'] = 'wrong'
    assert unwrap_download3(FakeHar(), e, raw, 'android', [key], max_skew=1) is None

def test_inner_key_missing_is_distinct():
    e, raw, expected, key = fixture()
    with pytest.raises(savefmt.InnerKeyMissing):
        unwrap_download3(FakeHar(), e, raw, 'android', ['not-the-right-key'])

def test_wrong_command_not_attempted():
    e, raw, expected, key = fixture()
    e['headers']['command'] = 'download2'
    assert unwrap_download3(FakeHar(), e, raw, 'android', [key]) is None
