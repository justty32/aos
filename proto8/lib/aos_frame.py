#!/usr/bin/env python3
"""frame 查找（C-46）：從 frame（預設 cwd）照 `frame.json` 的 `parent` 鏈往上找名字。純標準庫。
（10-15 晚從 aos_agent_lib.py 拆出來；aos_agent_lib 照樣 re-export chain／lookup／lookup_dir。）
"""
import json
import os

__all__ = ["MAX_CHAIN", "chain", "lookup", "lookup_dir"]

MAX_CHAIN = 16                                 # frame.json 的 parent 最多往上找幾層


def chain(start=None):
    """frame（start，預設 cwd）→ 找名字的資料夾順序：自己、frame.json 的 parent、parent 的 parent…（C-46）。
    parent 的相對路徑從那個 frame.json 所在的資料夾算；繞圈（realpath 重複）或超過 MAX_CHAIN 層就停。"""
    d, out = os.path.realpath(start or os.getcwd()), []
    while d and d not in out and len(out) < MAX_CHAIN:
        out.append(d)
        try:
            with open(os.path.join(d, "frame.json"), encoding="utf-8") as f:
                parent = json.load(f).get("parent")
        except (OSError, ValueError, AttributeError):
            break
        if not (isinstance(parent, str) and parent):
            break
        d = os.path.realpath(os.path.join(d, parent))
    return out


def lookup(name, start=None):
    """照 chain() 的順序找 name（檔或資料夾），回第一個找到的絕對路徑；都沒有＝None。"""
    for d in chain(start):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def lookup_dir(name, start=None):
    """資料夾值逐項找：各層 name/ 底下的項目聯集，同名以近的為準（＝追加＋蓋過）。回 {項目名: 絕對路徑}。"""
    out = {}
    for d in chain(start):
        p = os.path.join(d, name)
        if os.path.isdir(p):
            for n in sorted(os.listdir(p)):
                if not n.startswith("."):
                    out.setdefault(n, os.path.join(p, n))
    return out
