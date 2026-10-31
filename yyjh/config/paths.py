# -*- coding: utf-8 -*-
"""本地输入及 HAR 角色存档路径；与 main 的旧快照目录隔离。"""
import os

TOOL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEGACY_OUT_DIR = os.path.join(TOOL_DIR, "output")
OUT_DIR = os.path.join(LEGACY_OUT_DIR, "_har_only")


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def strip_quotes(value):
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1].strip()
    return text


def resolve(path):
    path = os.path.expanduser(strip_quotes(path))
    if os.path.isabs(path) or os.path.exists(path):
        return os.path.abspath(path)
    return os.path.abspath(os.path.join(TOOL_DIR, path))


def resolve_out(path):
    return os.path.abspath(os.path.expanduser(path))


def rel(path):
    try:
        return os.path.relpath(path, TOOL_DIR)
    except ValueError:
        return str(path)
