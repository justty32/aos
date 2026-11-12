# aos_eca/reseed.py - ⑧ 換台開新對話時接在題目前面的開場白（從 history 組「整理過的紀錄」）。
import json
import os

import aos_flags

from .history import history_rows


# ---- 開場白（⑧ 換台開新對話；two-machines 05）----

ONE_MAX, ONE_HEAD, ONE_TAIL = 6000, 4000, 2000              # 單則超過 ONE_MAX bytes：留頭 ONE_HEAD＋尾 ONE_TAIL

NOTE = aos_flags.aos_note("session", """this conversation continues in a new session (it moved to another machine or folder, or was restarted).
The earlier session is not available here. Below is the record aos kept of it: what you were asked and your
final answers (tool calls and their output are not included; long or old messages are shortened or left out).
The complete record is the JSON-lines file %s. The new message follows the record.
""")
NOTE_ONLY = aos_flags.aos_note("session", """this conversation continues in a new session (it moved to another machine or folder, or was restarted).
The earlier session is not available here. aos keeps a record of it (what you were asked and your final answers)
in the JSON-lines file %s; it is not attached here. The new message follows.
""")


def nbytes(text):
    return len(text.encode("utf-8"))


def shorten(text):
    """單則超過 ONE_MAX bytes：留頭 ONE_HEAD＋尾 ONE_TAIL bytes、中間一行說省了多少；照 UTF-8 切、不切壞字。"""
    raw = text.encode("utf-8")
    if len(raw) <= ONE_MAX:
        return text
    head = raw[:ONE_HEAD].decode("utf-8", "ignore")              # 切在字中間的那幾個 byte 丟掉
    tail = raw[-ONE_TAIL:].decode("utf-8", "ignore")
    return "%s\n[... %d bytes left out ...]\n%s" % (head, len(raw) - nbytes(head) - nbytes(tail), tail)


def entry(row):
    """history 一則 → 一段 `[role] content\n`；content 不是字串就印成 JSON。"""
    content = row.get("content")
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    return "[%s] %s\n" % (row.get("role") if isinstance(row.get("role"), str) else "unknown", shorten(content))


def reseed(stack, ws, limit):
    """開新對話時接在題目前面的開場白（cli_ask.ask 的 reseed；在交出去之前叫，history 還沒接這輪的 user）。
    history 空＝""。結尾一個空行。整段 ≤ limit bytes；limit 0、或說明加第一則 user 就超過＝只給說明（NOTE_ONLY）。"""
    rows = history_rows(stack)
    if not rows:
        return ""
    where = os.path.relpath(os.path.join(stack, "history.jsonl"), ws)
    only = NOTE_ONLY % where + "\n"
    if limit <= 0:
        return only
    n = len(rows)
    parts = [entry(r) for r in rows]
    sizes = [nbytes(p) for p in parts]
    first = next((i for i, r in enumerate(rows) if r.get("role") == "user"), None)
    gap = nbytes("[... %d earlier messages left out ...]\n" % n)  # 省略行最長也就這樣（K ≤ n）
    fixed = nbytes(NOTE % where + "\n--- record: %d messages, %d shown ---\n--- end of record ---\n\n" % (n, n))

    def cost(chosen):
        """chosen（排好的 index）組出來最多幾 bytes：固定段＋各則＋每個空隙一行省略。"""
        holes = sum(1 for a, b in zip([-1] + chosen, chosen + [n]) if b - a > 1)
        return fixed + sum(sizes[i] for i in chosen) + holes * gap

    chosen = [first] if first is not None else []
    if cost(chosen) > limit:
        return only
    for i in range(n - 1, -1, -1):                                  # 其餘從最新往回裝，裝不下就停
        if i == first:
            continue
        trial = sorted(chosen + [i])
        if cost(trial) > limit:
            break
        chosen = trial
    out, prev = [NOTE % where, "\n", "--- record: %d messages, %d shown ---\n" % (n, len(chosen))], -1
    for i in chosen + [n]:
        if i - prev > 1:
            out.append("[... %d earlier messages left out ...]\n" % (i - prev - 1))
        if i < n:
            out.append(parts[i])
        prev = i
    out.append("--- end of record ---\n\n")
    return "".join(out)
