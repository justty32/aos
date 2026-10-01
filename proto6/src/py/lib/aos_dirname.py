"""node 狀態資料夾的名字：環境變數 `AOS_DIRNAME`（〔使用者方向 2026-10-01，待統一更新 spec〕
notes/verdicts/11-tick-as-unit.md 篇末）。

只換名字，位置仍在 node／目標資料夾裡。沒設或空字串＝`.aos`；含 `/`、或是 `.`、`..` 算用法錯
（碼由各程式照自己的用法錯回：aos-tick 1、aos-exec 2）。之後 aos 所有程式都照這個變數。
aos-tick 與 aos-exec 共用這一處。
"""
import os

__all__ = ["DEFAULT", "name", "error"]

DEFAULT = ".aos"


def name():
    """目前的名字（不驗；要驗先叫 error()）。"""
    return os.environ.get("AOS_DIRNAME") or DEFAULT


def error():
    """名字不合法回一行白話，合法回 None。"""
    n = name()
    if "/" in n or n in (".", ".."):
        return "AOS_DIRNAME 要是單一資料夾名（不含 /、不是 . 或 ..）：%r" % n
    return None
