"""holds 探針的任務：用法 python3 ctrlr.py <角色> <naive|holds>

角色：
  burn     line node 的工作（keep）：每收到一個 tock，`<node>/usage.json` 的 tokens +10
  budget   預算 kernel（ctrl node）：line 的用量比基準多 60 → 要停 5 個自己的回合，之後放開、基準重設
  freeze   管理 kernel（ctrl node）：自己的第 15～35 回合要停（凍結窗口）
  arbiter  只在 holds 模式：把 `<ctrl>/holds/*.json` 合成現有的單一 pause／resume

naive：budget、freeze 各自直接寫 daemon 控制檔 pause／resume（經 mnt/aosd）。
holds：budget、freeze 只寫／刪自己的 hold 檔 `<ctrl>/holds/<owner>.json`；arbiter 每 20 ms 對帳：
  有 hold → 要停；沒有 → 要跑。只解自己停的：看 daemon log.jsonl 最後一筆 pause／resume 是誰下的，
  別人（不走 holds 的人或程式）下的 pause 當成一個外部 hold，不去 resume。
每個角色意圖改變時寫一行到 `<ctrl>/intents.jsonl`：{"who", "on", "t", "round"}。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_fs as fs  # noqa: E402

E = fs.task_env()
NODE, TASK, TID = E["node"], E["task"], E["tid"]
ROLE, MODE = sys.argv[1], sys.argv[2]
MNT = os.path.join(TASK, "mnt")
WORLD = E["node_id"].split("/")[0]          # naive／holds
LINE = WORLD + "/line"
BY = "%s:%s" % (E["node_id"], ROLE)
SEQ = [0]


def intent(on, r, **kw):
    fs.append_jsonl(os.path.join(NODE, "intents.jsonl"), dict(kw, who=ROLE, on=on, t=time.time(), round=r))


def daemon_ctl(op, why):
    SEQ[0] += 1
    fs.write_json(os.path.join(MNT, "aosd", "ctl", "%s-%s-%d-%d.json" % (ROLE, TID, os.getpid(), SEQ[0])),
                  {"op": op, "node": LINE, "by": BY, "why": why})


def hold(on, why):
    p = os.path.join(NODE, "holds", ROLE + ".json")
    if on:
        fs.write_json(p, {"owner": ROLE, "node": LINE, "kind": "pause_timeline", "why": why, "at": fs.now()})
    else:
        try:
            os.remove(p)
        except FileNotFoundError:
            pass


def want(on, r, why):
    intent(on, r, why=why)
    if MODE == "naive":
        daemon_ctl("pause" if on else "resume", why)
    else:
        hold(on, why)


def tocks():
    last = (fs.read_json(os.path.join(TASK, "birth.json"), {}) or {}).get("round", 1) - 1
    while True:
        last = fs.wait_tock(TASK, last)
        yield last


def burn():
    for _ in tocks():
        fs.edit_json(os.path.join(NODE, "usage.json"), lambda o: {"tokens": (o or {}).get("tokens", 0) + 10})


def budget():
    base, on, until = None, False, 0
    for r in tocks():
        tokens = (fs.read_json(os.path.join(MNT, "line", "usage.json"), {}) or {}).get("tokens", 0)
        if base is None:
            base = tokens
        if not on and tokens - base >= 60:
            on, until = True, r + 5
            want(True, r, "用量 %d 超過基準 %d＋60" % (tokens, base))
        elif on and r >= until:
            on, base = False, tokens
            want(False, r, "冷卻 5 回合到期")


def freeze():
    on = False
    for r in tocks():
        if not on and 15 <= r < 35:
            on = True
            want(True, r, "凍結窗口 15～35")
        elif on and r >= 35:
            on = False
            want(False, r, "凍結窗口結束")


def last_pause_by():
    """daemon log.jsonl 最後一筆對 line 的 pause／resume：(op, by)。log 只看尾端。"""
    for e in reversed(fs.tail_jsonl(os.path.join(MNT, "aosd", "log.jsonl"), 400)):
        if e.get("ev") == "ctl" and e.get("node") == LINE and e.get("op") in ("pause", "resume") and e.get("ok"):
            return e["op"], e.get("by")
    return None, None


def arbiter():
    alog = os.path.join(NODE, "arbiter.jsonl")
    last_write = (None, 0.0)
    while True:
        time.sleep(0.02)
        holds = []
        try:
            names = sorted(n for n in os.listdir(os.path.join(NODE, "holds")) if n.endswith(".json") and not n.startswith("."))
        except OSError:
            names = []
        for n in names:
            h = fs.read_json(os.path.join(NODE, "holds", n))
            if isinstance(h, dict) and h.get("node") == LINE:
                holds.append(h.get("owner"))
        st = (fs.read_json(os.path.join(MNT, "aosd", "status.json"), {}) or {}).get("nodes", {}).get(LINE, {})
        paused = st.get("paused")
        if paused is None:
            continue
        op, by = last_pause_by()
        external = paused and op == "pause" and by != BY
        if external:
            holds.append("external:%s" % by)
        desired = bool(holds)
        if desired == paused:
            continue
        if last_write[0] == desired and time.time() - last_write[1] < 0.3:
            continue                          # 剛寫過，等 daemon 處理
        daemon_ctl("pause" if desired else "resume", "holds：%s" % (holds or "沒有"))
        last_write = (desired, time.time())
        fs.append_jsonl(alog, {"op": "pause" if desired else "resume", "holds": holds, "t": time.time(),
                               "was_by": by, "fix_external_resume": desired and op == "resume" and by != BY})


{"burn": burn, "budget": budget, "freeze": freeze, "arbiter": arbiter}[ROLE]()
