# -*- coding: utf-8 -*-
"""HAR 专用终端提示；不包含内存爆破进度和设备管理。"""
import os
import sys
import traceback

_VERBOSE = False


def setup_console():
    if os.name == "nt":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


def configure(verbose=False, **_unused):
    global _VERBOSE
    _VERBOSE = bool(verbose)


def is_verbose():
    return _VERBOSE


def is_tty():
    return bool(sys.stdin.isatty() and sys.stdout.isatty())


def info(message=""):
    print(message)


def title(message):
    print("\n" + str(message))


def step(label, value=""):
    print(f"  {label}：{value}")


def ok(message):
    print(f"✓ {message}")


def warn(message):
    print(f"⚠ {message}")


def error(message):
    print(f"✗ {message}", file=sys.stderr)


class Cancelled(Exception):
    """用户退出向导。"""


class UserError(Exception):
    """已处理的用户错误，不直接输出敏感数据或完整异常对象。"""


def report_error(exc, verbose=False):
    error(str(exc))
    if verbose and exc.__cause__:
        # 详细模式仅打印异常类型，不转储可能携带账号/密钥的局部变量。
        error("原因类型：" + type(exc.__cause__).__name__)
