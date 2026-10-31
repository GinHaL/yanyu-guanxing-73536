# -*- coding: utf-8 -*-
"""仅用于将 HAR 明文重新生成网页版兼容的 SQLite dat.db。"""
import os
import sqlite3

SCHEMA = "CREATE TABLE save (id VARCHAR PRIMARY KEY, content VARCHAR, player VARCHAR)"


def write_save(path, save_id, content, player):
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        raise FileExistsError("输出暂存文件已存在")
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA page_size = 1024")
        conn.execute("PRAGMA auto_vacuum = 0")
        conn.execute('PRAGMA encoding = "UTF-8"')
        conn.execute(SCHEMA)
        conn.execute("INSERT INTO save (id,content,player) VALUES (?,?,?)",
                     (save_id, content, player))
        conn.commit()
    finally:
        conn.close()
    return path
