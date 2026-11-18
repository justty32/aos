"""walk - 嵌套走表（02 §2.5）：從一張 daemon 表起廣度優先往下，表裡哪一列的 stack 自己也是 daemon（有 procs_state.json）就再列它那張；
記走過的 stack 防繞圈、最深 5 層、最多 500 隻，超過就停並標 truncated。

認「它底下還有一張表」的做法照現碼：aos-agent ctl 的 need_table（ctl/shared.py）就是看 <D>/procs_state.json 在不在來認 D 是不是 daemon 的 stack，
列那張表用 `aos-agent --daemon <那列的 stack> ctl ls --json`（給了 --daemon 就不問 AOS_KERNEL）。列表怎麼叫由呼叫者給（list_table），這裡只走。"""
import collections
import os

from . import Fail

STATE = "procs_state.json"
MAX_DEPTH = 5
MAX_PROCS = 500


def is_daemon(stack):
    return isinstance(stack, str) and bool(stack) and os.path.isfile(os.path.join(stack, STATE))


def walk(list_table, deep=False, top=None, max_depth=MAX_DEPTH, max_procs=MAX_PROCS):
    """list_table(daemon 的 stack 或 None＝照環境找的那張) → 列的串列（每列至少 name、stack）。
    回 {"rows": [列＋path（上層名/…/名）＋depth（1 起）＋table（那張表的 daemon stack，頂層＝top）], "truncated", "skipped": [{table, code, reason}]}。
    頂層表列不了＝Fail 往外丟；下層表列不了＝記進 skipped、照走別的。top＝頂層那台的 stack（知道就給，防繞回來）。"""
    rows, skipped, truncated = [], [], False
    seen = {os.path.realpath(top)} if top else set()
    queue = collections.deque([(top, 1, "")])
    while queue:
        table, depth, prefix = queue.popleft()
        try:
            listed = list_table(table)
        except Fail as e:
            if depth == 1:
                raise
            skipped.append({"table": table, "code": e.code, "reason": str(e)})
            continue
        for r in listed:
            if len(rows) >= max_procs:
                truncated = True
                break
            name = str(r.get("name"))
            row = dict(r, path=prefix + name, depth=depth, table=table)
            rows.append(row)
            stack = r.get("stack")
            if not deep or not is_daemon(stack):
                continue
            real = os.path.realpath(stack)
            if real in seen:
                continue
            seen.add(real)
            if depth >= max_depth:
                truncated = True
                continue
            queue.append((stack, depth + 1, row["path"] + "/"))
        if truncated and len(rows) >= max_procs:
            break
    return {"rows": rows, "truncated": truncated, "skipped": skipped}
