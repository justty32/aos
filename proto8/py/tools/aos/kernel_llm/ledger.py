# 問腦的逐封帳 ledger.jsonl：只留成本與時間，不存請求內容；used.json 壞了時從它重算。
import json
import os
import time

from aos import tool_io


def append(stack, name, proc, reply):
    """追加一列；寫不了只提醒，不影響回信與收信。"""
    path = os.path.join(stack, "ledger.jsonl")
    proc = proc if isinstance(proc, dict) else {}
    finished = time.time()
    mounted = proc.get("mounted_at")
    elapsed = None
    if isinstance(mounted, (int, float)) and not isinstance(mounted, bool):
        elapsed = max(0, int((finished - mounted) * 1000.0))
    entry = {"id": name, "endpoint": proc.get("endpoint"), "sender": proc.get("sender"),
             "model": reply.get("model"), "seen_at": proc.get("seen_at"), "mounted_at": mounted,
             "finished_at": finished, "elapsed_ms": elapsed, "usage": reply.get("usage"),
             "code": reply["error"]["code"] if "error" in reply else None,
             "child": reply.get("child"), "switched": proc.get("switched", False)}
    if proc.get("reasoning_effort") is not None:                 # 這封帶了思考程度、包也收了（11-21）
        entry["reasoning_effort"] = proc["reasoning_effort"]
    try:
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(line)
    except (OSError, ValueError, TypeError) as error:
        tool_io.warn("cannot append ledger: %s (%s)" % (path, error))


def read_rows(stack):
    """讀整份 ledger.jsonl 給重算用量（used.json 壞了時；11-19 基底體檢 P5）：照本檔的讀法，跳過壞行、同 id 只留最後一行。
    回 (各行, 跳過的壞行數)；檔不在或讀不了回 None（算不出來，不能當成 0）。"""
    path = os.path.join(stack, "ledger.jsonl")
    try:
        with open(path, "rb") as stream:
            lines = stream.read().splitlines()
    except OSError:
        return None
    rows, skipped = {}, 0
    for raw in lines:
        try:
            row = json.loads(raw)
        except (ValueError, UnicodeError):
            row = None
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            skipped += 1 if raw.strip() else 0
            continue
        rows.pop(row["id"], None)                   # 同 id 重收：留最後一行
        rows[row["id"]] = row
    return list(rows.values()), skipped
