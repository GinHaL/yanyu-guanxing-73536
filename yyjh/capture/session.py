# -*- coding: utf-8 -*-
"""73536+ download3 会话密文解包（只读）。

Lua 调用链：token = MD5(platform + '_' + session + '_' + os.time())[:16]
             auto = RSA(token)
             data = Base64(XXTEA(token, Base64(version + XXTEA(inner_key,zlib(JSON)))))
此路径已在 73536/73570 四条真实下载响应中完成 JSON 端到端验证。
不保存临时 token，不在日志中输出 session/token。
"""
from __future__ import annotations
import datetime as _dt
import hashlib
from ..core import codecs, xxtea
from ..game import savefmt


def _candidate_seconds(iso_time: str, max_skew: int = 60):
    if not iso_time or not isinstance(iso_time, str):
        return
    try:
        t = _dt.datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
        if t.tzinfo is None:
            return
        base = int(t.timestamp())
    except (ValueError, OverflowError, OSError):
        return
    max_skew = min(max(int(max_skew), 0), 60)
    yield base
    for diff in range(1, max_skew + 1):
        yield base - diff
        yield base + diff


def unwrap_download3(har, entry, data_b64: str, runtime: str,
                     inner_candidates, *, max_skew: int = 60):
    """返回 (version, data_dict, inner_key)；不匹配返回 None。

    外层成功但内层密钥缺失时抛出 InnerKeyMissing，防止误报为会话失败。
    """
    if (har.header(entry, 'command') or '').strip().lower() != 'download3':
        return None
    if runtime not in ('android', 'ios'):
        return None
    session = (har.header(entry, 'session') or '').strip()
    if not (1 <= len(session) <= 128) or any(ord(c) < 33 or ord(c) > 126 for c in session):
        return None
    raw = codecs.b64d(data_b64)
    if not raw or len(raw) < 8 or len(raw) % 4:
        return None
    for stamp in _candidate_seconds(entry.get('startedDateTime'), max_skew):
        seed = f'{runtime}_{session}_{stamp}'.encode('utf-8')
        token = hashlib.md5(seed).hexdigest()[:16]
        plain = xxtea.decrypt(raw, token)
        if not plain:
            continue
        try:
            version, body = savefmt.parse_old(plain.decode('ascii'))
        except (ValueError, UnicodeDecodeError):
            continue
        data, used = savefmt.try_inner(body, inner_candidates)
        if isinstance(data, dict):
            return version, data, used
        raise savefmt.InnerKeyMissing(version, runtime, tried=len(inner_candidates))
    return None
