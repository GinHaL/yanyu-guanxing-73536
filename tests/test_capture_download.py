# -*- coding: utf-8 -*-
"""HAR ≥73536 解析：纯合成输入；不包含真实账号、密钥或抓包。"""
import datetime as dt
import hashlib
import json

import pytest

from yyjh.capture import decode
from yyjh.capture.har import Har, is_download_cmd
from yyjh.core import codecs, xxtea
from yyjh.game import protocol, savefmt


def _headers(**values):
    return [{"name": key, "value": str(value)} for key, value in values.items()]


def make_har(tmp_path, version=73570, session_wrap=True, account="fake-account-007",
             captured="2026-10-31T07:00:00+00:00", missing_k=False,
             data=None, extra=True):
    stamp = dt.datetime.fromisoformat(captured)
    version_text = str(version).zfill(8)
    seed = b"abc123XYZ987"
    k = codecs.b64e(xxtea.encrypt(seed, protocol.key0(account)))
    real_key = protocol.derive(account, k)["real_key"]
    psw = "testpsw8"
    payload = data or {
        "EncryptID": account, "DBVersion": version,
        "MainRole": {"Name": "合成测试角色", "Level": 9}, "SomeField": 123,
    }
    content = savefmt.build_old(payload, version_text, psw + "po06ewkx")
    if session_wrap:
        token = hashlib.md5(
            f"android_test-session_{int(stamp.timestamp())}".encode()
        ).hexdigest()[:16]
        blob = codecs.b64e(xxtea.encrypt(content.encode("ascii"), token))
    else:
        blob = content
    body = json.dumps({
        "code": 0, "data": blob,
        "extra": codecs.b64e(xxtea.encrypt(psw.encode(), real_key)) if extra else "",
    })
    entries = [{
        "startedDateTime": (stamp - dt.timedelta(seconds=4)).isoformat(),
        "request": {"headers": _headers(command="startGame", acc=account, plat="android")},
        "response": {"status": 200, "headers": [] if missing_k else _headers(k=k),
                     "content": {"text": "{}"}},
    }, {
        "startedDateTime": stamp.isoformat(),
        "request": {"headers": _headers(command="download3", acc=account,
                                      ver=version, area=53, plat="android",
                                      session="test-session")},
        "response": {"status": 200, "headers": [], "content": {"text": body}},
    }]
    path = tmp_path / "synthetic.har"
    path.write_text(json.dumps({"log": {"entries": entries}}), encoding="utf-8")
    return path, payload


def test_download3_session_decryption_without_keys(tmp_path, monkeypatch):
    path, data = make_har(tmp_path)
    assert decode.decode(str(path)).data == data
    assert decode.decode(str(path)).version == "00073570"


def test_download3_73536_and_no_upload(tmp_path):
    path, data = make_har(tmp_path, version=73536)
    assert len(Har(str(path)).downloads()) == 1
    assert decode.decode(str(path)).data == data


def test_download3_legacy_body_at_supported_version(tmp_path):
    path, data = make_har(tmp_path, version=73536, session_wrap=False)
    assert decode.decode(str(path)).data == data


def test_old_version_rejected(tmp_path):
    path, _ = make_har(tmp_path, version=73492)
    with pytest.raises(decode.UnsupportedVersion):
        decode.decode(str(path))


def test_missing_k_rejected_without_cache_fallback(tmp_path):
    path, _ = make_har(tmp_path, missing_k=True)
    with pytest.raises(decode.DownloadFormatChanged):
        decode.decode(str(path))


def test_missing_extra_rejected(tmp_path):
    path, _ = make_har(tmp_path, extra=False)
    with pytest.raises(decode.DownloadFormatChanged):
        decode.decode(str(path))


def test_unrecognized_download_command_is_rejected(tmp_path):
    assert is_download_cmd("download3")
    assert not is_download_cmd("downloadPower")
    path, _ = make_har(tmp_path)
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["log"]["entries"][1]["request"]["headers"][0]["value"] = "upload3"
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValueError, match="download3"):
        decode.decode(str(path))


def test_wrong_encrypt_id_is_rejected(tmp_path):
    path, _ = make_har(tmp_path, data={
        "EncryptID": "wrong-account", "DBVersion": 73570,
        "MainRole": {"Name": "不匹配角色"},
    })
    with pytest.raises(decode.DownloadFormatChanged):
        decode.decode(str(path))
