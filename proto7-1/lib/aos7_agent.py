"""aos7-agent：idle → think → act → idle 的狀態機任務，每收到一次 tock 換一次狀態（spec.md 第 10 節，S-16、S-19）。

做事的時機：收到 tock 先決定換到哪個狀態、存檔，再「做新狀態的事」（think＝問 LLM、act＝跑工具），
做完存檔等下一個 tock。所以 state.json 寫著 think 就表示「這回合在想」。
被 kill 後重啟：先接前一個同名任務的 state.json，沒做完的 think／act 補做（recover）。
"""
import argparse
import json
import os
import signal
import sys

import aos7_agent_tools as tools
import aos7_llm
from aos7_fs import now, read_json, task_env, wait_tock, write_json


class Stop(Exception):
    """收到 SIGTERM／SIGINT。"""


def fresh_state():
    return {"state": "idle", "round": 0, "steps": 0, "tocks": 0, "plan": None, "pc": 0,
            "letters": [], "goal": None, "last": "剛出生", "from": None}


def load_state(ctx):
    """自己的 state.json；沒有就找同 node 同名、回合最新的前任任務接著跑；都沒有就新的。"""
    st = read_json(os.path.join(ctx["task"], "state.json"))
    if isinstance(st, dict) and st.get("state") in ("idle", "think", "act"):
        return st
    me = read_json(os.path.join(ctx["task"], "birth.json"), {}) or {}
    tasks_dir = os.path.dirname(ctx["task"])
    best = None
    try:
        tids = os.listdir(tasks_dir)
    except OSError:
        tids = []
    for tid in tids:
        d = os.path.join(tasks_dir, tid)
        if d == ctx["task"]:
            continue
        b = read_json(os.path.join(d, "birth.json"), {}) or {}
        old = read_json(os.path.join(d, "state.json"))
        if b.get("name") != me.get("name") or not isinstance(old, dict) or old.get("state") not in ("idle", "think", "act"):
            continue
        if best is None or old.get("round", 0) > best[1].get("round", 0):
            best = (tid, old)
    if best is None:
        return fresh_state()
    st = dict(fresh_state(), **best[1])
    st["from"] = best[0]
    st["last"] = "接續前任 %s（它停在 %s）" % (best[0], st["state"])
    return st


def save(ctx, st):
    write_json(os.path.join(ctx["task"], "state.json"), st)


def log(ctx, st, msg):
    """一行 JSON 印到 stdout（aos7-run 收進 out.log）。"""
    print(json.dumps({"at": now(), "round": st["round"], "state": st["state"], "msg": msg}, ensure_ascii=False),
          flush=True)


def add_usage(ctx, tokens):
    p = os.path.join(ctx["task"], "usage.json")
    u = read_json(p, {}) or {}
    write_json(p, {"tokens": int(u.get("tokens", 0)) + int(tokens or 0), "calls": int(u.get("calls", 0)) + 1})


def load_cfg(ctx):
    cfg = read_json(os.path.join(ctx["node"], "agent.json"), {}) or {}
    cfg.setdefault("name", os.path.basename(ctx["node"]))
    return cfg


def do_think(ctx, st):
    """問 LLM 拿 plan。輸入＝persona＋這次抓到的信＋（要先開口時）goal。"""
    letters = tools.read_letters(ctx["node"], st["letters"])
    res = aos7_llm.think(load_cfg(ctx), st["goal"], letters, ctx["node_id"])
    add_usage(ctx, res["tokens"])
    st["plan"] = res["plan"] if isinstance(res["plan"], list) and res["plan"] else [{"tool": "none"}]
    st["pc"] = 0
    st["last"] = "think（%s）：%d 個動作" % (res["note"], len(st["plan"]))
    save(ctx, st)
    log(ctx, st, st["last"])


def do_act(ctx, st):
    """從 pc 接著跑 plan；每做完一個存一次檔。最後搬信、用掉 goal。"""
    plan = st["plan"] or []
    while st["pc"] < len(plan):
        r = tools.do_tool(ctx, plan[st["pc"]], st["round"])
        st["pc"] += 1
        st["last"] = r
        save(ctx, st)
        log(ctx, st, r)
    tools.move_done(ctx["node"], st["letters"])
    if st["goal"]:
        tools.consume_goal(ctx["node"])
    save(ctx, st)


def write_progress(ctx, st):
    """給 kernel 判斷卡住：每處理一個 tock 就寫（含 round），處理不了 tock 的才會連續不變。"""
    write_json(os.path.join(ctx["task"], "progress.json"),
               {"round": st["round"], "state": st["state"], "steps": st["steps"]})


def on_tock(ctx, st, rnd):
    """收到第 rnd 回合的 tock：換一次狀態並做新狀態的事。回新的 st（也已存檔）。"""
    st["round"], st["tocks"] = rnd, st.get("tocks", 0) + 1
    s = st["state"]
    if s == "idle":
        names, goal = tools.list_inbox(ctx["node"]), tools.pending_goal(ctx["node"])
        if names or goal:
            st.update(state="think", letters=names, goal=goal, plan=None, pc=0, steps=st["steps"] + 1)
            save(ctx, st)
            do_think(ctx, st)
    elif s == "think":
        st.update(state="act", pc=0, steps=st["steps"] + 1)
        save(ctx, st)
        do_act(ctx, st)
    else:
        st.update(state="idle", plan=None, pc=0, letters=[], goal=None, steps=st["steps"] + 1, last="回到 idle")
    save(ctx, st)
    write_progress(ctx, st)
    return st


def recover(ctx, st):
    """重啟時補做：停在 think 但沒 plan → 再想一次；停在 act → 從 pc 接著做（pc 那一步可能重做）。"""
    if st["state"] == "think" and st.get("plan") is None:
        log(ctx, st, "recover：think 沒想完，重想")
        do_think(ctx, st)
    elif st["state"] == "act":
        log(ctx, st, "recover：act 從第 %d 步接著做" % st.get("pc", 0))
        do_act(ctx, st)
    return st


def _stop(signum, frame):
    raise Stop()


def run(ctx, rounds=None, poll=0.02):
    """主迴圈：等 tock → on_tock；rounds 給了就處理那麼多次 tock 後結束。"""
    st = load_state(ctx)
    save(ctx, st)
    log(ctx, st, "啟動：%s" % st["last"])
    recover(ctx, st)
    write_progress(ctx, st)
    handled = 0
    while rounds is None or handled < rounds:
        r = wait_tock(ctx["task"], st["round"], poll=poll, timeout=0.5)
        if r is None:
            continue
        st = on_tock(ctx, st, r)
        handled += 1
    log(ctx, st, "處理完 %d 次 tock，結束" % handled)
    return st


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aos7-agent", description="狀態機 agent：每個 tock 換一次狀態（讀 AOS7_* 環境變數）")
    ap.add_argument("--rounds", type=int, default=None, help="收到 N 次 tock 後自行結束")
    args = ap.parse_args(argv)
    try:
        ctx = task_env()
    except KeyError as e:
        print("aos7-agent: 缺環境變數 %s（要由 aos7-tick 起）" % e, file=sys.stderr)
        return 2
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    try:
        run(ctx, args.rounds)
    except Stop:
        print(json.dumps({"at": now(), "msg": "收到 SIGTERM，結束"}, ensure_ascii=False), flush=True)
    return 0
