# -*- coding: utf-8 -*-
"""每角色只保存最新一次成功解密的 HAR；输出目录独立于 main 旧快照。"""
import datetime as dt
import json
import os
import re
import shutil
import tempfile
import uuid

from .config import paths
from .game import savefmt
from .localdb import sqlitedb


def _safe(value):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(value or ""))[:30].strip("._") or "0"


def _time(value):
    if not value:
        return None
    try:
        value = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return value.astimezone(dt.timezone.utc) if value.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def profile_directory(res):
    """账号 MD5 前缀与区服用于目录命名，角色名称可变但归档路径不变。"""
    return f"{_safe(res.runtime)}-s{_safe(res.server)}-{res.save_id[:12]}"


def _existing_meta(directory):
    path = os.path.join(directory, "dat.meta.json")
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _record(directory, meta):
    return {
        "dir": directory,
        "meta": meta,
        "json": os.path.join(directory, "dat.json"),
        "db": os.path.join(directory, "dat.db"),
        "mtime": os.path.getmtime(directory),
    }


def write_latest(res, outdir=None):
    """先在临时目录写入全部有效文件，再原子切换角色目录。

    有完整可比较的 HAR 采集时间时拒绝较旧输入。发生写入错误则恢复旧目录。
    不复制、删除 main 原来的 output/<角色>/<时间戳> 历史档。
    """
    if not isinstance(res.data, dict) or not res.data or not res.account:
        raise ValueError("未得到完整 JSON，拒绝覆盖已解析角色")
    root = paths.ensure_dir(outdir or paths.OUT_DIR)
    target = os.path.join(root, profile_directory(res))
    previous = _existing_meta(target)
    if previous and previous.get("save_id") not in (None, res.save_id):
        raise ValueError("角色目录标识发生冲突，拒绝覆盖")
    if previous and previous.get("server") not in (None, res.server):
        raise ValueError("区服标识发生冲突，拒绝覆盖")
    old_time, new_time = _time(previous.get("captured_at")), _time(res.captured_at)
    if old_time and new_time and new_time < old_time:
        raise ValueError("该 HAR 的下载时间早于已保存角色的 HAR，拒绝回退旧存档")

    stage = tempfile.mkdtemp(prefix="._har_stage_", dir=root)
    backup = None
    try:
        json_path = os.path.join(stage, "dat.json")
        with open(json_path, "w", encoding="utf-8", newline="\n") as fp:
            json.dump(res.data, fp, ensure_ascii=False, separators=(",", ":"))
        content = savefmt.build_old(res.data, res.version, savefmt.platform_key(res.runtime))
        sqlitedb.write_save(os.path.join(stage, "dat.db"),
                            res.save_id, content, res.player)
        # 密钥只用于解密；历史列表的 meta 绝不写 realKey/psw/token/innerKey。
        meta = {
            "runtime": res.runtime,
            "account": res.account,
            "save_id": res.save_id,
            "server": res.server,
            "nick": res.nick,
            "version": res.version,
            "field_count": res.field_count,
            "captured_at": res.captured_at,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source_file": os.path.basename(res.source),
            "save_format": "v18",
        }
        with open(os.path.join(stage, "dat.meta.json"), "w",
                  encoding="utf-8", newline="\n") as fp:
            json.dump(meta, fp, ensure_ascii=False, indent=2)
        if os.path.exists(target):
            backup = target + ".previous." + uuid.uuid4().hex
            os.replace(target, backup)
        try:
            os.replace(stage, target)
        except OSError:
            if backup and os.path.exists(backup):
                os.replace(backup, target)
            raise
        stage = None
        if backup and os.path.isdir(backup):
            shutil.rmtree(backup, ignore_errors=True)
        return _record(target, meta)
    finally:
        if stage and os.path.isdir(stage):
            shutil.rmtree(stage, ignore_errors=True)
