# -*- coding: utf-8 -*-
"""HAR 网络解密与兼容网页存档输出使用的固定常量。"""

# XXTEA 使用小端 32 位字和末尾原文长度字
XXTEA_DELTA = 0x9E3779B9
MASK32 = 0xFFFFFFFF
XXTEA_LEN_TAIL = 7
XXTEA_LEN_HEAD = 4

SAVE_VERSION_LEN = 8
MIN_HAR_VERSION = 73536

# 网络协议 realKey = acc[:5] + 中间常量 + 解开的服务端种子前 6 字节
PROTOCOL_MIDDLE = "eakec"
PROTOCOL_SEED_ZERO = "000000"
PROTOCOL_KEY_LEN = 16
PROTOCOL_INNER_MIN = 1
PROTOCOL_INNER_MAX = 128

# 这里仅用于将已解析 JSON 转成网页版兼容的 v1.8 dat.db，
# 并不是 download3 的网络解密密钥，也不从 keys.json 加载。
V18_PLATFORM_KEYS = {
    "ios": "3598gjjdtekelaw9",
    "android": "3598gjjdtekelad9",
    "pre_ios": "3598gjjdbeceead3",
    "pre_android": "3598gjjdbeceead3",
    "older": "3598gjjdchdidqz2",
    "oversea": "3598gjjdaecjjyc4",
    "korea": "3598gjjdd3tczm6d",
    "japan": "3598gjjdtekelad9",
    "test": "aaaabbbbccccdddd",
    "windows": "windows0",
}
V18_DEFAULT_PLATFORM = "android"
