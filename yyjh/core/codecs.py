# -*- coding: utf-8 -*-
"""HAR 数据使用的 Base64 / zlib 编解码。"""
import base64
import binascii
import zlib


def b64d(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.encode("ascii", "ignore")
    value = bytes(c for c in value if c not in b" \t\r\n")
    if len(value) % 4:
        value += b"=" * (4 - len(value) % 4)
    try:
        return base64.b64decode(value, validate=False)
    except (binascii.Error, ValueError):
        return None


def b64e(raw):
    return base64.b64encode(raw).decode("ascii")


def zlib_d(raw):
    try:
        return zlib.decompress(raw)
    except zlib.error:
        return None


def zlib_c(raw, level=6):
    return zlib.compress(raw, level)
