# -*- coding: utf-8 -*-
"""HAR 解密结果在内存中的表示；密钥不进入历史归档元数据。"""
from dataclasses import dataclass, field


@dataclass
class Step:
    label: str
    value: str = ""
    ok: bool = True


@dataclass
class SaveResult:
    source: str = ""
    kind: str = "har"
    runtime: str = ""
    account: str = ""
    save_id: str = ""
    server: str = ""
    version: str = ""
    captured_at: str = ""
    inner_key: str = ""  # 临时密钥，不能持久化或输出到日志
    data: dict = field(default_factory=dict)
    player: str = ""
    steps: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def nick(self):
        role = self.data.get("MainRole") or {}
        return role.get("Name") or ""

    @property
    def field_count(self):
        return len(self.data)

    def step(self, label, value="", ok=True):
        self.steps.append(Step(label, str(value), ok))
        return self

    def warn(self, msg):
        self.warnings.append(str(msg))
        return self
