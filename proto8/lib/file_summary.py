"""file_summary - ls、stat、view 共用的檔案摘要小件：資料夾裡有哪些 aos 標記檔、檔案時間寫成 ISO、一個 JSON 值的一句摘要。

不是工具（沒有 _entry）；只用標準庫。來由：thinking 2026-11/12/codebase-cleanup 線 F——原本 ls、stat 各一份 AOS_MARKS／aos_marks／iso，stat、view 各一份 json_summary，逐字相同。
"""
import os
import time

AOS_MARKS = ("_entry", "_entry.json", "_metainfo.json", ".env", "_tooldef.json", "tools.json", "loop.json", "fsm.json")


def aos_marks(d):
    """資料夾 d 裡有的 aos 標記檔（照 AOS_MARKS 的順序）；讀不了＝空。"""
    try:
        names = set(os.listdir(d))
    except OSError:
        return []
    return [m for m in AOS_MARKS if m in names]


def iso(t):
    """epoch 秒 → UTC ISO 字串，到毫秒、帶 +00:00。"""
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%03d+00:00" % int((t % 1) * 1000)


def json_summary(v):
    """一個 JSON 值的一句摘要：型別＋大小（物件幾個 key、陣列幾項、字串幾字），純值短的直接給。"""
    if isinstance(v, dict):
        return {"type": "object", "counter_keys": len(v)}
    if isinstance(v, list):
        return {"type": "array", "counter_items": len(v)}
    if isinstance(v, str) and len(v) > 80:
        return {"type": "string", "counter_chars": len(v), "head": v[:60]}
    names = {type(None): "null", bool: "boolean", int: "number", float: "number", str: "string"}
    return {"type": names[type(v)], "value": v}
