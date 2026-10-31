# -*- coding: utf-8 -*-
"""只读取 HAR 的存档下载请求与会话头，不处理上传和设备。"""
import json
import re

DOWNLOAD_CMD_RE = re.compile(r"^download(?:_auto)?\d*$", re.I)


def is_download_cmd(command):
    return bool(DOWNLOAD_CMD_RE.fullmatch((command or "").strip()))


class Har:
    def __init__(self, path):
        self.path = path
        with open(path, encoding="utf-8-sig") as stream:
            content = json.load(stream)
        entries = (content.get("log") or {}).get("entries") if isinstance(content, dict) else None
        if not isinstance(entries, list):
            raise ValueError("不是合法的 HAR：缺少 log.entries")
        self.entries = entries

    @staticmethod
    def header(entry, name, where="request"):
        source = entry.get(where) or {}
        for row in source.get("headers") or []:
            if (row.get("name") or "").lower() == name.lower():
                return str(row.get("value") or "").strip()
        return None

    def downloads(self):
        return [entry for entry in self.entries
                if is_download_cmd(self.header(entry, "command"))]
