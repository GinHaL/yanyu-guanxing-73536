# -*- coding: utf-8 -*-
"""HAR 内层存档格式及网页版兼容输出；不解原始 dat.db 外层。"""
import hashlib
import json
import re

from ..config import constants
from ..core import codecs, xxtea

OLD = "old"
_VERSION_RE = re.compile(r"^\d{8}$")


class InnerKeyMissing(ValueError):
    """会话层已解开，但 HAR 的 psw 与已知渠道后缀均未通过校验。"""

    def __init__(self, version, runtime, marker="", tried=0, fmt=OLD):
        super().__init__(f"版本 {version} 的内层密钥未通过验证（候选 {tried} 个）")
        self.version = version
        self.runtime = runtime
        self.marker = marker
        self.tried = tried
        self.format = fmt


def parse_old(content):
    """解析 Base64(8 位版本号 + 内层 XXTEA 密文)。"""
    raw = codecs.b64d(content)
    if not raw or len(raw) < constants.SAVE_VERSION_LEN + 8:
        raise ValueError("存档内容不完整或不是合法 Base64")
    version = raw[:constants.SAVE_VERSION_LEN].decode("ascii", "replace")
    body = raw[constants.SAVE_VERSION_LEN:]
    if not _VERSION_RE.fullmatch(version) or len(body) % 4:
        raise ValueError("存档版本头或密文长度非法")
    return version, body


def try_inner(body, candidates):
    """验证内层 XXTEA → zlib → JSON；不信任仅通过长度字的候选。"""
    seen = set()
    for key in candidates:
        if not key or key in seen:
            continue
        seen.add(key)
        compressed = xxtea.decrypt(body, key)
        if not compressed:
            continue
        plain = codecs.zlib_d(compressed)
        if plain is None:
            continue
        try:
            result = json.loads(plain.decode("utf-8"))
        except (UnicodeError, ValueError):
            continue
        if isinstance(result, dict):
            return result, key
    return None, None


def build_old(data, version, inner_key, level=6):
    """将已验证的 JSON 重新封装成网页版可读的初版数据。"""
    version = str(version)
    if not _VERSION_RE.fullmatch(version):
        raise ValueError("输出版本必须为 8 位数字")
    packed = codecs.zlib_c(json.dumps(
        data, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8"), level)
    return codecs.b64e(version.encode("ascii") + xxtea.encrypt(packed, inner_key))


def platform_key(runtime):
    keys = constants.V18_PLATFORM_KEYS
    return keys.get(runtime) or keys[constants.V18_DEFAULT_PLATFORM]


def save_id_of(account):
    return hashlib.md5(account.encode("utf-8")).hexdigest()


def server_from_json(data):
    value = (data or {}).get("ServerID")
    return "" if value is None else str(value)
