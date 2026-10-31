# -*- coding: utf-8 -*-
"""烟雨观星 HAR 存档工具；不依赖模拟器、内存扫描或外部密钥缓存。"""
import sys

if sys.version_info < (3, 8):
    sys.exit("需要 Python 3.8 或更高版本")

__version__ = "1.1.0"
__all__ = ["__version__"]
