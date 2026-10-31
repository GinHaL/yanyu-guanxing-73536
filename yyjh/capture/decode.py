# -*- coding: utf-8 -*-
"""HAR ≥73536 的 download3 解密。

三种临时密钥均取自 HAR + 固定算法/渠道常量；不读历史密钥文件，
不调用 ADB、Frida 或内存扫描。仅在 JSON 完整验证后返回数据。
"""
import json
import re
from datetime import datetime, timezone

from .. import model
from ..config import constants, keytables
from ..core import codecs, xxtea
from ..game import player, protocol, savefmt
from .har import Har
from .session import unwrap_download3


class UnsupportedVersion(ValueError):
    """HAR 存档版本低于受支持的最低版本。"""


class DownloadFormatChanged(ValueError):
    """存在 download3，但数据未通过当前支持的格式验证。"""

    def __init__(self, version="", reason="下载内容无法解密", size=0, cmd="download3"):
        self.version = version
        self.reason = reason
        self.size = size
        self.cmd = cmd
        super().__init__(f"版本 {version or '未知'} 的 {cmd} 无法解密：{reason}")


def _capture_time(entry):
    text = entry.get("startedDateTime") or ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return ""
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def _download_entries(har):
    """按采集时间优先取最新的 download3；其他命令不推测为存档。"""
    items = [e for e in har.entries
             if (har.header(e, "command") or "").strip().lower() == "download3"]
    return sorted(items, key=lambda e: _capture_time(e), reverse=True)


def _session_keys(har, account, entry):
    """同账号、同次会话的 k 优先；不使用其他账号的响应密钥。"""
    current = _capture_time(entry)
    seen = set()
    rows = []
    for candidate in har.entries:
        k = har.header(candidate, "k", "response")
        if not k:
            continue
        owner = (har.header(candidate, "acc") or "").strip()
        if owner and owner != account:
            continue
        stamp = _capture_time(candidate)
        # 优先选择该次下载之前、时间最近的一条；其余同账号候选备用。
        priority = (bool(stamp and current and stamp <= current), stamp or "")
        rows.append((priority, k))
    for _priority, value in sorted(rows, key=lambda row: row[0], reverse=True):
        if value not in seen:
            seen.add(value)
            yield value


def _response_json(entry, real_key):
    response = (entry.get("response") or {}).get("content") or {}
    body = response.get("text") or ""
    if not isinstance(body, str) or not body:
        return None
    try:
        obj = json.loads(body)
        if isinstance(obj, dict):
            return obj
    except ValueError:
        pass
    encoded = codecs.b64d(body)
    if encoded:
        decrypted = xxtea.decrypt(encoded, real_key)
        if decrypted:
            try:
                obj = json.loads(decrypted.decode("utf-8"))
                return obj if isinstance(obj, dict) else None
            except (UnicodeError, ValueError):
                pass
    return None


def _recover_psw(response, real_key):
    extra = response.get("extra")
    if not isinstance(extra, str):
        return None
    encrypted = codecs.b64d(extra)
    plain = xxtea.decrypt(encrypted, real_key) if encrypted else None
    return plain.decode("ascii") if plain and re.fullmatch(rb"[A-Za-z0-9]{8}", plain) else None


def _try_download(har, entry):
    request_version = (har.header(entry, "ver") or "").strip()
    if request_version.isdigit() and int(request_version) < constants.MIN_HAR_VERSION:
        raise UnsupportedVersion(f"仅支持存档版本 ≥{constants.MIN_HAR_VERSION}，此 HAR 为 {request_version}")
    if (entry.get("response") or {}).get("status") != 200:
        raise DownloadFormatChanged(request_version, "下载响应不是 HTTP 200")

    account = (har.header(entry, "acc") or "").strip()
    if not account:
        raise DownloadFormatChanged(request_version, "download3 请求缺少账号字段 acc")
    runtime = (har.header(entry, "plat") or "").strip().lower()
    if runtime not in ("android", "ios"):
        # download3 未必包含 plat，取同账号其它请求的明确平台字段。
        for related in har.entries:
            if har.header(related, "acc") == account:
                candidate = (har.header(related, "plat") or "").strip().lower()
                if candidate in ("android", "ios"):
                    runtime = candidate
                    break
    if runtime not in ("android", "ios"):
        runtime = "ios" if protocol.is_ios(account) else "android"

    last_reason = "找不到同账号有效的 k 响应头"
    last_size = 0
    for k_header in _session_keys(har, account, entry):
        try:
            real_key = protocol.derive(account, k_header)["real_key"]
        except (ValueError, TypeError, KeyError):
            last_reason = "协议密钥无法派生"
            continue
        payload = _response_json(entry, real_key)
        if not payload or payload.get("code", 0) not in (0, "0"):
            last_reason = "下载响应不是有效的存档 JSON"
            continue
        psw = _recover_psw(payload, real_key)
        if not psw:
            last_reason = "extra 无法恢复 8 位版本密码段"
            continue
        data_b64 = payload.get("data")
        if not isinstance(data_b64, str) or not data_b64:
            last_reason = "下载响应缺少 data"
            continue
        encrypted = codecs.b64d(data_b64)
        last_size = len(encrypted) if encrypted else 0
        if not encrypted or len(encrypted) < 12:
            last_reason = "data 不是完整的 Base64 密文"
            continue
        inner_keys = [psw + suffix for suffix in keytables.suffix_order(runtime)]
        inner_keys.append(psw)  # 兼容 XXTEA 对不足 16 字符密钥的补零规则

        # 较新 download3：会话 Token 解开外层，随后验证内层。
        # 若确实为旧明文版本头，则仅允许 ≥73536，避免回退到旧版 HAR 处理。
        legacy = bool(re.fullmatch(rb"\d{8}", encrypted[:8]))
        if legacy:
            version = encrypted[:8].decode("ascii")
            if int(version) < constants.MIN_HAR_VERSION or len(encrypted[8:]) % 4:
                raise UnsupportedVersion("不支持此版本或密文结构")
            data, used = savefmt.try_inner(encrypted[8:], inner_keys)
        else:
            try:
                result = unwrap_download3(har, entry, data_b64, runtime, inner_keys)
            except savefmt.InnerKeyMissing:
                result = None
                last_reason = "会话层已解开，但版本内层密钥验证失败"
            if result is None:
                data, version, used = None, request_version.zfill(8), None
            else:
                version, data, used = result

        if data is None:
            if last_reason == "找不到同账号有效的 k 响应头":
                last_reason = "会话层或内层解密验证失败"
            continue
        if int(version) < constants.MIN_HAR_VERSION:
            raise UnsupportedVersion(f"仅支持存档版本 ≥{constants.MIN_HAR_VERSION}")
        declared = data.get("DBVersion")
        if declared is not None and (not str(declared).isdigit() or int(declared) != int(version)):
            last_reason = "存档真实版本号与解密版本头不一致"
            continue
        identified = data.get("EncryptID")
        if identified and str(identified) != account:
            last_reason = "解密 JSON 的账号与 HAR 不匹配"
            continue

        save = model.SaveResult(
            source=har.path, runtime=runtime, account=account,
            save_id=savefmt.save_id_of(account),
            server=str(har.header(entry, "area") or savefmt.server_from_json(data)),
            version=version, captured_at=_capture_time(entry),
            inner_key=used, data=data,
        )
        save.player = player.build(data, version)
        save.step("HAR", "download3 数据完整")
        save.step("协议层", "realKey 已通过响应验证")
        save.step("会话层", "通过" if not legacy else "旧明文版本头")
        save.step("内层", "XXTEA、zlib 和 JSON 全部通过")
        return save

    version_label = request_version.zfill(8) if request_version.isdigit() else request_version
    raise DownloadFormatChanged(version_label, last_reason, size=last_size)


def decode(har_path, index=None, real_key=None, inner_key=None, avatar_field="auto"):
    """解析最新有效 download3；为兼容旧调用保留参数但不接受手工密钥。"""
    if any(value is not None for value in (index, real_key, inner_key)):
        raise ValueError("HAR 专用版只接受 HAR 自主派生密钥，不支持手工密钥或 upload 索引")
    har = Har(har_path)
    entries = _download_entries(har)
    if not entries:
        raise ValueError("HAR 中没有 download3 存档响应；只支持版本 ≥73536 的下载存档")
    failures = []
    excluded = 0
    for entry in entries:
        try:
            return _try_download(har, entry)
        except UnsupportedVersion:
            excluded += 1
        except DownloadFormatChanged as exc:
            failures.append(exc)
    if excluded == len(entries):
        raise UnsupportedVersion(f"所有下载记录都低于 {constants.MIN_HAR_VERSION} 或不受支持")
    if failures:
        raise failures[0]
    raise DownloadFormatChanged(reason="无有效下载存档")
