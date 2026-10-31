# -*- coding: utf-8 -*-
"""HAR 解析与角色唯一存档输出；无 local / ADB / 内存或密钥缓存流程。"""
import argparse
import os

from . import report, ui
from .capture import decode as har_decode
from .config import paths


def pipeline_capture(args):
    path = paths.resolve(args.input)
    if not os.path.isfile(path):
        raise ui.UserError(f"找不到 HAR 文件：{path}")
    if not path.lower().endswith(".har"):
        raise ui.UserError("仅支持输入 .har 文件")
    ui.title("从 HAR 解析存档")
    ui.info(f"  输入：{os.path.basename(path)}")
    try:
        result = har_decode.decode(path)
        saved = report.write_latest(
            result, paths.resolve_out(args.outdir) if getattr(args, "outdir", None) else None
        )
    except har_decode.UnsupportedVersion as exc:
        raise ui.UserError(str(exc)) from exc
    except har_decode.DownloadFormatChanged as exc:
        raise ui.UserError(f"下载存档解析失败：{exc.reason}") from exc
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise ui.UserError(f"HAR 处理失败：{exc}") from exc

    ui.ok(f"完成：{result.nick or '未命名角色'} "
          f"{result.runtime}·s{result.server or '0'} "
          f"版本 {result.version}，{result.field_count} 字段")
    ui.info("  保存位置：" + paths.rel(saved["dir"]))
    return saved


def add_parsers(sub):
    p = sub.add_parser("capture", help="解析 >=73536 的 HAR 并替换该角色唯一存档")
    p.add_argument("input", metavar="抓包.har")
    p.add_argument("--outdir", help="自定义角色存档目录")
    p.set_defaults(func=pipeline_capture)
    return p
