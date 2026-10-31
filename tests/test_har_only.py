# -*- coding: utf-8 -*-
"""角色唯一存档、历史读取和自动载入的合成回归测试。"""
import json
import os
import sqlite3
from pathlib import Path

import pytest

from yyjh import model, report, wizard
from yyjh.config import paths
from yyjh.game import player, savefmt


def sample(account="sample-user", server="53", captured="2026-10-31T10:00:00+00:00",
           level=9):
    data = {
        "EncryptID": account, "DBVersion": 73570,
        "MainRole": {"Name": "测试角色", "Level": level},
        "SomeField": level,
    }
    result = model.SaveResult(
        source="synthetic.har", account=account,
        save_id=savefmt.save_id_of(account),
        runtime="android", server=server, version="00073570",
        data=data, captured_at=captured,
    )
    result.player = player.build(data, result.version)
    return result


def test_same_role_overwrites_latest_in_place(tmp_path):
    first = report.write_latest(sample(level=3), str(tmp_path))
    second = report.write_latest(sample(
        captured="2026-10-31T11:00:00+00:00", level=7
    ), str(tmp_path))
    assert first["dir"] == second["dir"]
    assert len([p for p in tmp_path.iterdir() if p.is_dir()]) == 1
    content = json.loads(Path(second["json"]).read_text(encoding="utf-8"))
    assert content["SomeField"] == 7
    record = wizard.list_profiles(outdir=str(tmp_path))
    assert len(record) == 1
    assert record[0]["meta"]["field_count"] == len(content)
    # 最新的导出 SQLite 仍是网页兼容的 v18 单层存档。
    with sqlite3.connect(second["db"]) as conn:
        raw = conn.execute("SELECT content FROM save").fetchone()[0]
    version, body = savefmt.parse_old(raw)
    restored, _ = savefmt.try_inner(body, [savefmt.platform_key("android")])
    assert version == "00073570"
    assert restored == content


def test_older_har_cannot_replace_newer(tmp_path):
    latest = report.write_latest(sample(), str(tmp_path))
    before = Path(latest["json"]).read_bytes()
    with pytest.raises(ValueError, match="较旧"):
        report.write_latest(sample(
            captured="2026-10-30T09:00:00+00:00", level=99
        ), str(tmp_path))
    assert Path(latest["json"]).read_bytes() == before


def test_different_account_or_server_is_different_role(tmp_path):
    report.write_latest(sample("user-a", "53"), str(tmp_path))
    report.write_latest(sample("user-b", "53"), str(tmp_path))
    report.write_latest(sample("user-a", "54"), str(tmp_path))
    assert len(wizard.list_profiles(outdir=str(tmp_path))) == 3


def test_meta_never_contains_keys(tmp_path):
    record = report.write_latest(sample(), str(tmp_path))
    text = Path(record["dir"], "dat.meta.json").read_text(encoding="utf-8")
    for key in ("real_key", "outer_key", "inner_key", "token", "psw"):
        assert f'"{key}"' not in text


def test_legacy_snapshots_list_latest_only_without_deleting_main(tmp_path, monkeypatch):
    legacy = tmp_path / "old"
    group = legacy / "android-s53-测试角色"
    for index in (1, 2):
        snap = group / f"2026103{index}-100000"
        snap.mkdir(parents=True)
        (snap / "dat.json").write_text("{}", encoding="utf-8")
        (snap / "dat.meta.json").write_text(json.dumps({
            "runtime": "android", "server": "53", "account": "sample-user",
            "save_id": savefmt.save_id_of("sample-user"),
            "nick": "测试角色", "field_count": 3,
        }), encoding="utf-8")
        os.utime(snap, (1000 + index, 1000 + index))
    new = legacy / "_har_only"
    monkeypatch.setattr(paths, "LEGACY_OUT_DIR", str(legacy))
    monkeypatch.setattr(paths, "OUT_DIR", str(new))
    rows = wizard.list_profiles()
    assert len(rows) == 1
    assert rows[0]["dir"].endswith("20261032-100000")
    assert len(list(group.iterdir())) == 2  # 保留 main 工作区历史源数据


def test_autoload_uses_selected_json(tmp_path, monkeypatch):
    home = tmp_path / "web"
    home.mkdir()
    (home / "index.html").write_text("<html><head></head><body>test</body></html>",
                                      encoding="utf-8")
    monkeypatch.setattr(paths, "TOOL_DIR", str(tmp_path))
    record = report.write_latest(sample(), str(tmp_path / "role-output"))
    path = wizard.write_autoload(record)
    html = Path(path).read_text(encoding="utf-8")
    assert "yyjh_share_save_v1" in html
    assert "localStorage.setItem" in html
    assert "sample-user" not in html  # 存档压缩，避免把账号直接注入明文脚本


def test_keytables_is_constant_only():
    from yyjh.config import keytables
    assert "po06ewkx" in keytables.suffix_order("android")
    assert not hasattr(keytables, "_load_overlay")
