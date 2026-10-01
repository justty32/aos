"""node 狀態資料夾的名字：環境變數 `AOS_DIRNAME`（〔使用者方向 2026-10-01，待統一更新 spec〕
notes/verdicts/11-tick-as-unit.md 篇末）。

三態（使用者 2026-10-01 再改）：
- 沒設＝`.aos`。
- 設了但是空字串＝不用子資料夾，直接用 node／目標資料夾本身（`name()` 回 `""`，
  `os.path.join(node, "", "x")` 就是 `node/x`）。
- 其他值＝這個名字；含 `/`、或是 `.`、`..` 算用法錯（aos-tick、aos-exec 都回 1）。

只換名字，位置仍在 node／目標資料夾裡。之後 aos 所有程式都照這個變數。aos-tick 與 aos-exec 共用這一處。
"""
import os

__all__ = ["DEFAULT", "name", "error"]

DEFAULT = ".aos"


def name():
    """目前的名字（不驗；要驗先叫 error()）。沒設回 `.aos`；設成空字串回 `""`（＝資料夾本身）。"""
    n = os.environ.get("AOS_DIRNAME")
    return DEFAULT if n is None else n


def error():
    """名字不合法回一行白話，合法回 None。空字串合法。"""
    n = name()
    if "/" in n or n in (".", ".."):
        return "AOS_DIRNAME 要是單一資料夾名或空字串（不含 /、不是 . 或 ..）：%r" % n
    return None
