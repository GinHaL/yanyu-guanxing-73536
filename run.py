#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""烟雨观星 HAR 专用版入口。

    python run.py                    显示已解析角色 / n 导入 HAR / q 退出
    python run.py capture 文件.har   直接解析并保存 HAR
"""
import os
import sys

if sys.version_info < (3, 8):
    sys.exit("需要 Python 3.8 或更高版本")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from yyjh.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
