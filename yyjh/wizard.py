# -*- coding: utf-8 -*-
"""HAR 专用交互入口：列出唯一角色，按 n 解析新 HAR，按 q 退出。"""
import argparse
import base64
import json
import os
import time
import webbrowser
import zlib
from pathlib import Path

from . import __version__, ui
from .config import paths

SHARE_KEY = "yyjh_share_save_v1"
SHARE_META_KEY = "yyjh_share_save_meta_v1"
AUTOLOAD_NAME = "_autoload_last.html"


def web_index():
    return os.path.join(paths.TOOL_DIR, "web", "index.html")


def _read_meta(directory):
    try:
        with open(os.path.join(directory, "dat.meta.json"), encoding="utf-8") as stream:
            result = json.load(stream)
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def _read_record(directory, source):
    db_file = os.path.join(directory, "dat.db")
    json_file = os.path.join(directory, "dat.json")
    if not os.path.isfile(db_file) and not os.path.isfile(json_file):
        return None
    meta = _read_meta(directory)
    return {
        "dir": directory, "db": db_file if os.path.isfile(db_file) else None,
        "json": json_file if os.path.isfile(json_file) else None,
        "meta": meta, "source": source,
        "mtime": os.path.getmtime(directory),
    }


def _identity(row):
    """同账号、平台、区服仅显示一条；旧数据缺身份时用原目录兜底。"""
    from .game.savefmt import save_id_of
    meta = row["meta"]
    account = meta.get("account") or ""
    save_id = meta.get("save_id") or (save_id_of(account) if account else "")
    runtime = meta.get("runtime") or "unknown"
    server = str(meta.get("server") or "")
    if save_id:
        return runtime, server, save_id
    # 旧快照缺 meta 时，以原归档组作为身份，仍然只显示最新快照。
    group = (Path(row["dir"]).parent.name if row["source"] == "legacy"
             else Path(row["dir"]).name)
    return ("legacy", "", group)


def list_profiles(outdir=None):
    """兼容旧快照，但 test 自己只保存一份；不删除 main 原有历史文件。"""
    root = outdir or paths.OUT_DIR
    by_id = {}
    if os.path.isdir(paths.LEGACY_OUT_DIR) and outdir is None:
        for group in os.scandir(paths.LEGACY_OUT_DIR):
            if not group.is_dir() or group.name.startswith(".") or group.name.startswith("_"):
                continue
            for snap in os.scandir(group.path):
                if not snap.is_dir():
                    continue
                record = _read_record(snap.path, "legacy")
                if record:
                    key = _identity(record)
                    old = by_id.get(key)
                    if old is None or record["mtime"] > old["mtime"]:
                        by_id[key] = record
    if os.path.isdir(root):
        for item in os.scandir(root):
            if not item.is_dir() or item.name.startswith(".") or item.name.startswith("_"):
                continue
            record = _read_record(item.path, "test")
            if record:
                by_id[_identity(record)] = record  # test 记录优先于 main 的旧快照
    return sorted(by_id.values(), key=lambda row: row["mtime"], reverse=True)


def describe(row):
    meta = row["meta"]
    nick = meta.get("nick") or os.path.basename(row["dir"])
    runtime = meta.get("runtime") or "?"
    server = meta.get("server") or "?"
    fields = meta.get("field_count")
    date = str(meta.get("generated_at") or "")
    if date and len(date) >= 16:
        stamp = date[:16].replace("T", " ")
    else:
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(row["mtime"]))
    return f"{nick}  {runtime}·s{server}  {stamp}" + (f"  {fields} 字段" if fields is not None else "")


def _pack_save(data):
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(zlib.compress(raw, 9)).decode("ascii")


def write_autoload(row):
    """沿用网页版现有的 localStorage 接口，角色切换时自动载入对应 JSON。"""
    path = row.get("json") if row else None
    if not path or not os.path.isfile(path):
        return None
    index = web_index()
    if not os.path.isfile(index):
        return None
    with open(path, encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or not data:
        return None
    with open(index, encoding="utf-8") as stream:
        html = stream.read()
    if "</head>" not in html:
        raise ValueError("网页版缺少 </head>，无法自动载入")

    meta = row.get("meta") or {}
    seed = {
        "version": str(meta.get("version") or ""),
        "platform": str(meta.get("runtime") or "android"),
        "channel": str(meta.get("channel") or ""),
        "format": "json-local",
        "fileName": os.path.basename(row.get("db") or path),
        "importedAt": int(time.time() * 1000),
    }
    def safe_json(value):
        # 防止文件名等任意字符串结束内联 script 标签。
        return json.dumps(value, ensure_ascii=True).replace("<", "\\u003c")
    script = (
        '<script>(function(){try{'
        'localStorage.setItem(' + safe_json(SHARE_KEY) + ',' +
        safe_json(_pack_save(data)) + ');'
        'localStorage.setItem(' + safe_json(SHARE_META_KEY) + ',' +
        safe_json(json.dumps(seed, ensure_ascii=False)) + ');'
        '}catch(e){console.error("自动载入存档失败");}})();</script>'
    )
    target = os.path.join(os.path.dirname(index), AUTOLOAD_NAME)
    with open(target, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(html.replace("</head>", script + "\n</head>", 1))
    return target


def open_web(row):
    """使用系统默认浏览器打开网页版；无 JSON 时使用原始首页。"""
    from . import webapp
    try:
        shared = os.path.join(os.path.dirname(web_index()), "shared")
        webapp.write_bundle(shared)
    except (OSError, ValueError) as exc:
        ui.warn(f"网页计算线程刷新失败：{exc}")
    target = web_index()
    if row:
        try:
            autoload = write_autoload(row)
            if autoload:
                target = autoload
            else:
                ui.warn("该角色缺少有效 dat.json，将打开网页版供手动导入")
        except (OSError, ValueError) as exc:
            ui.warn(f"历史角色载入准备失败：{exc}")
    if not os.path.isfile(target):
        raise ui.UserError("网页版入口 web/index.html 不存在")
    url = Path(target).absolute().as_uri()
    if not webbrowser.open(url):
        ui.warn("浏览器未自动打开，请手动打开：" + target)
        return False
    ui.ok("已打开网页版" + ("，并自动载入角色" if target != web_index() else ""))
    return True


def _import_har(args):
    from .layer2 import pipeline_capture
    raw = input("请输入 HAR 文件路径（可拖入文件，q 取消）：").strip()
    if raw.lower() in ("q", "quit", "exit") or not raw:
        return
    request = argparse.Namespace(input=paths.strip_quotes(raw), outdir=args.outdir)
    row = pipeline_capture(request)
    open_web(row)


def pipeline_start(args):
    if not ui.is_tty() and not os.environ.get("YYJH_WIZARD_TTY"):
        raise ui.UserError("当前不是交互终端，请使用 python run.py capture 文件.har")
    while True:
        ui.title(f"烟雨观星 · HAR 存档工具 v{__version__}")
        roles = list_profiles(getattr(args, "outdir", None))
        if roles:
            ui.info("已解析角色（默认最新）：")
            for number, row in enumerate(roles, 1):
                ui.info(f"  [{number}] {describe(row)}")
        else:
            ui.info("（暂无已解析角色）")
        ui.info("")
        ui.info("  [n] 解析 HAR")
        ui.info("  [q] 退出")
        try:
            command = input("请选择（直接回车默认第一个角色）：").strip().lower()
        except EOFError:
            return 0
        if command in ("q", "quit", "exit"):
            return 0
        if command == "n":
            try:
                _import_har(args)
                return 0
            except ui.Cancelled:
                return 0
            except (ui.UserError, OSError, ValueError) as exc:
                ui.report_error(exc if isinstance(exc, ui.UserError)
                                else ui.UserError(str(exc)), ui.is_verbose())
                continue
        if command == "" and roles:
            return 0 if open_web(roles[0]) else 2
        if command.isdigit() and 1 <= int(command) <= len(roles):
            return 0 if open_web(roles[int(command) - 1]) else 2
        ui.warn("输入无效，请输入角色编号、n 或 q")


def add_parsers(sub):
    p = sub.add_parser("start", help="选择历史角色或解析 HAR")
    p.add_argument("--outdir", help="自定义角色数据目录")
    p.set_defaults(func=pipeline_start)
    return p
