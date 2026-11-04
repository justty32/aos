"""supervisor 探針的 kernel：Erlang 式監督（one_for_one／rest_for_one、重啟次數上限、退避、用完就升級）。

設定 `<node>/sup.json`：
  {"mode": "keep"|"spawn", "react": "tock"|"poll",
   "children": {名字: tasks.json 的一項（不含 mode）＋可選 "restart": "permanent"|"temporary"},
   "groups": [{"id", "strategy": "one_for_one"|"rest_for_one", "children": [依啟動順序],
               "ordered": bool（前一個 ready 了才起下一個）, "max_restarts", "window_rounds", "backoff": [回合...]}]}

- mode keep：起子工作＝把它加進自己 node 的 tasks.json（keep 項），退避／停用＝把它拿掉（edit_json 拿鎖）。
- mode spawn：tasks.json 只有 supervisor 自己；起子工作＝寫 `.aos/spawn/sup-*.json`。
- react tock：每收到自己的 tock 看一次（S-17「在 tick-tock 時」）；poll：每 20 ms 看一次（不等回合）。

子工作都跟 supervisor 在同一個 node（直接讀寫自己 node 的 `.aos/`）。每個決定寫一行到 `<node>/sup.jsonl`。
supervisor 自己的狀態只放記憶體（這個探針不測 supervisor 本身重起）。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_fs as fs  # noqa: E402
import aos7_task  # noqa: E402

E = fs.task_env()
NODE, TASK, TID = E["node"], E["task"], E["tid"]
AOS = os.path.join(NODE, ".aos")
POL = fs.read_json(os.path.join(NODE, "sup.json"), {}) or {}
MODE, REACT = POL["mode"], POL["react"]
CH = POL["children"]
GROUPS = POL["groups"]
GROUP_OF = {c: g for g in GROUPS for c in g["children"]}
LOG = os.path.join(NODE, "sup.jsonl")
TASKS_JSON = os.path.join(AOS, "tasks.json")

known = {}          # tid -> 子工作名字
handled = set()     # 已處理過結束的 tid
killing = set()     # 自己下 kill 的 tid
restarts = {}       # group -> [回合...]（窗口內的重啟）
nrestart = {}       # 子工作 -> 第幾次重啟（決定退避）
down = {}           # 子工作 -> {"since", "not_before"}：等著重起
failed = {}         # group -> 用完重啟次數的回合
temp_done = set()   # temporary 子工作做完了
asked = {}          # 子工作 -> 要求起的回合（還沒看到實例）


def log(ev, **kw):
    kw.update(ev=ev, t=time.time())
    fs.append_jsonl(LOG, kw)


def now_round():
    return (fs.read_json(os.path.join(AOS, "round.json"), {}) or {}).get("round") or 0


def item(c):
    it = {k: v for k, v in CH[c].items() if k != "restart"}
    it["name"] = c
    return it


def current(c):
    """子工作 c 現在活著的實例（沒處理過結束的）。"""
    for tid, n in known.items():
        if n == c and tid not in handled:
            return tid
    return None


def ready(c):
    tid = None
    try:
        with open(os.path.join(NODE, "ready", c)) as f:
            tid = f.read().strip()
    except OSError:
        return False
    return bool(tid) and tid == current(c)


def kill(tid, why):
    if tid in killing:
        return
    killing.add(tid)
    fs.write_json(os.path.join(AOS, "tasks", tid, "ctl.json"), {"op": "kill", "by": "sup:" + TID, "why": why})


def set_keep(names, on):
    """mode keep：把子工作的 keep 項加進／拿出 tasks.json（照 children 的宣告順序）。"""
    def fn(o):
        o = o if isinstance(o, dict) else {"tasks": []}
        items = [i for i in o.get("tasks", []) if i.get("name") not in names]
        if on:
            items += [dict(item(c), mode="keep") for c in names]
        o["tasks"] = items
        return o
    fs.edit_json(TASKS_JSON, fn)


def start(names, r):
    for c in names:
        down.pop(c, None)
        asked[c] = r
    if MODE == "keep":
        set_keep(names, True)
    else:
        fs.write_json(os.path.join(AOS, "spawn", "sup-r%d-%s.json" % (r, "-".join(names))),
                      {"batch": [item(c) for c in names]})
    log("start-asked", children=names, round=r)


def scan(r):
    """先處理結束（含上一輪就認得的實例），再認新出生的：keep 搶先起的新實例才分得出是「退避中被起」。"""
    for tid, c in list(known.items()):
        if tid in handled:
            continue
        st = aos7_task.task_state(os.path.join(AOS, "tasks", tid))
        if aos7_task.is_live(st):
            continue
        handled.add(tid)
        code = (fs.read_json(os.path.join(AOS, "tasks", tid, "exit.json"), {}) or {}).get("code")
        if tid in killing:
            log("child-killed", child=c, tid=tid, code=code, round=r)
            continue
        on_exit(c, tid, code, r)
    for tid, d in fs.task_dirs_of(AOS):
        if tid in known or tid == TID:
            continue
        b = fs.read_json(os.path.join(d, "birth.json"))
        if not isinstance(b, dict) or b.get("name") not in CH:
            continue
        c = b["name"]
        known[tid] = c
        by = "sup" if str(b.get("spawn") or "").startswith("sup-") or (MODE == "keep" and c in asked) else "keep"
        asked.pop(c, None)
        g = GROUP_OF[c]["id"]
        if g in failed:
            log("unsanctioned", child=c, tid=tid, birth_round=b.get("round"), why="group 已放棄", seen_round=r)
            kill(tid, "group %s 已放棄" % g)
        elif c in down:
            log("unsanctioned", child=c, tid=tid, birth_round=b.get("round"), why="退避中（not_before %d）" % down[c]["not_before"],
                seen_round=r, by=by)
            down.pop(c)          # 只能認了：它已經在跑
        elif c in temp_done:
            log("unsanctioned", child=c, tid=tid, birth_round=b.get("round"), why="temporary 已做完", seen_round=r, by=by)
        else:
            log("child-up", child=c, tid=tid, birth_round=b.get("round"), by=by, seen_round=r)


def on_exit(c, tid, code, r):
    g = GROUP_OF[c]
    gid = g["id"]
    if gid in failed:
        log("exit-ignored", child=c, tid=tid, code=code, round=r)
        return
    if CH[c].get("restart") == "temporary":
        temp_done.add(c)
        if MODE == "keep":
            set_keep([c], False)
        log("temp-exit", child=c, tid=tid, code=code, round=r)
        return
    win = [x for x in restarts.get(gid, []) if x > r - g["window_rounds"]]
    win.append(r)
    restarts[gid] = win
    if len(win) > g["max_restarts"]:
        failed[gid] = r
        for x in g["children"]:
            t = current(x)
            if t:
                kill(t, "group %s 用完重啟次數" % gid)
            down.pop(x, None)
        if MODE == "keep":
            set_keep(g["children"], False)
        fs.write_json(os.path.join(NODE, "escalation.json"),
                      {"group": gid, "round": r, "by": TID, "why": "%d 回合內重啟 %d 次，超過 %d" % (
                          g["window_rounds"], len(win), g["max_restarts"]), "last": {"child": c, "tid": tid, "code": code}})
        log("escalate", group=gid, child=c, tid=tid, code=code, round=r, restarts=win)
        return
    order = g["children"]
    affected = order[order.index(c):] if g["strategy"] == "rest_for_one" else [c]
    n = nrestart.get(c, 0)
    nrestart[c] = n + 1
    nb = r + g["backoff"][min(n, len(g["backoff"]) - 1)]
    for x in affected:
        t = current(x)
        if x != c and t:
            kill(t, "rest_for_one：%s 掛了" % c)
        down[x] = {"since": r, "not_before": nb}
    if MODE == "keep":
        set_keep(affected, False)
    log("restart-planned", group=gid, child=c, tid=tid, code=code, round=r, affected=affected, not_before=nb)


def due(r):
    """到期的重起起來；ordered 的 group 一次只起一個，而且前面的兄弟都 ready 了才起（Erlang 依序 start_link）。"""
    for g in GROUPS:
        if g["id"] in failed:
            continue
        batch = []
        for i, c in enumerate(g["children"]):
            if c in temp_done or c not in down:
                continue
            if r + 1 < down[c]["not_before"] or current(c) or c in asked:
                if g.get("ordered"):
                    break
                continue
            if g.get("ordered"):
                if all(ready(x) for x in g["children"][:i]):
                    batch.append(c)
                break
            batch.append(c)
        if batch:
            start(batch, r)


def boot(r):
    for g in GROUPS:
        for c in g["children"]:
            down[c] = {"since": r, "not_before": 0}
    log("boot", mode=MODE, react=REACT, round=r)


def main():
    r = now_round()
    boot(r)
    last_tock = (fs.read_json(os.path.join(TASK, "birth.json"), {}) or {}).get("round", 1) - 1
    while True:
        if REACT == "tock":
            last_tock = fs.wait_tock(TASK, last_tock, poll=0.01)
            r = last_tock
        else:
            time.sleep(0.02)
            r = now_round()
        scan(r)
        due(r)
        # 已經要求起、過了 3 回合還沒看到實例：再要一次（spawn 檔被擋之類）
        for c, at in list(asked.items()):
            if r - at > 3:
                asked.pop(c)
                down[c] = {"since": r, "not_before": 0}


if __name__ == "__main__":
    main()
