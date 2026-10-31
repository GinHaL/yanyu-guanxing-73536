# -*- coding: utf-8 -*-
"""HAR 动态恢复 psw 后，只需在源码内尝试已知渠道后缀。

不读取、不写入 keys.json / keys.local.json。新增渠道必须经真实样本验证，
不能把旧版本预存密码当成动态提取的结果。
"""

CHANNEL_SUFFIXES = {
    "po06ewkx": "安卓官服",
    "cgkmi4cq": "先行服",
    "yoqkmrtj": "iOS",
    "meeo0wmk": "新服",
    "tekelad9": "历史 Android 渠道",
}

_PREFERRED = {
    "android": ("po06ewkx", "cgkmi4cq", "meeo0wmk", "tekelad9", "yoqkmrtj"),
    "ios": ("yoqkmrtj", "meeo0wmk", "po06ewkx", "cgkmi4cq", "tekelad9"),
}


def suffix_order(runtime):
    """候选按平台排序，是否有效以完整 zlib/JSON 校验为准。"""
    return list(_PREFERRED.get(runtime, tuple(CHANNEL_SUFFIXES)))
