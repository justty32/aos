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
from aos7_fs import append_jsonl, now, read_json, task_env, wait_tock, write_json


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


def add_usage(ctx, tokens, calls=1):
    p = os.path.join(ctx["task"], "usage.json")
    u = read_json(p, {}) or {}
    write_json(p, {"tokens": int(u.get("tokens", 0)) + int(tokens or 0), "calls": int(u.get("calls", 0)) + calls})


def load_cfg(ctx):
    cfg = read_json(os.path.join(ctx["node"], "agent.json"), {}) or {}
    cfg.setdefault("name", os.path.basename(ctx["node"]))
    return cfg


def do_think(ctx, st):
    """問 LLM 拿 plan。輸入＝persona＋這次抓到的信＋（要先開口時）goal。"""
    letters = tools.read_letters(ctx["node"], st["letters"])
    cfg = load_cfg(ctx)
    mem = tools.memory(ctx["node"], cfg["memory"], skip=st["letters"]) if cfg.get("memory") else None
    rnd_before = (read_json(os.path.join(ctx["node"], ".aos", "round.json"), {}) or {}).get("round")
    # 等 LLM 期間收不到 tock、progress 不會更新：先寫明「在等 LLM，從何時起」，kernel 就不當卡住（R-3）
    write_json(os.path.join(ctx["task"], "progress.json"),
               {"round": st["round"], "state": "think", "steps": st["steps"], "llm_since": now()})
    roster = read_json(os.path.join(ctx["node"], ".aos", "roster.json"))  # kernel 寫的成員名冊（R-2），有就帶上
    res = aos7_llm.think(cfg, st["goal"], letters, ctx["node_id"], mem, roster if isinstance(roster, dict) else None)
    add_usage(ctx, res["tokens"], res.get("calls", 1))
    if "ms" in res:  # 真模型：每次呼叫記一行（花多久、跨了幾個回合、原文），事後看得懂它想了什麼
        rnd_now = (read_json(os.path.join(ctx["node"], ".aos", "round.json"), {}) or {}).get("round")
        append_jsonl(os.path.join(ctx["task"], "llm.jsonl"),
                     {"at": now(), "round": st["round"], "round_before": rnd_before, "round_after": rnd_now, "ms": res["ms"], "calls": res.get("calls", 1),
                      "tokens": res["tokens"], "note": res["note"], "letters": st["letters"],
                      "raw": (res.get("raw") or "")[:4000]})
    st["plan"] = res["plan"] if isinstance(res["plan"], list) and res["plan"] else [{"tool": "none"}]
    st["pc"] = 0
    st["last"] = "think（%s）：%d 個動作" % (res["note"], len(st["plan"]))
    save(ctx, st)
    log(ctx, st, st["last"])


def do_act(ctx, st):
    """從 pc 接著跑 plan；每做完一個存一次檔。最後搬信、用掉 goal。"""
    plan = st["plan"] or []
    while st["pc"] < len(plan):
        try:
            r = tools.do_tool(ctx, plan[st["pc"]], st["round"])
        except Exception as e:  # 工具出錯算這一步失敗，agent 不死（astra-2 二-5）
            r = "工具失敗：%s: %s" % (type(e).__name__, e)
        st["pc"] += 1
        st["last"] = r
        save(ctx, st)
        log(ctx, st, r)
    tools.move_done(ctx["node"], st["letters"])
    if st["goal"] and not st["goal"].get("wake"):
        tools.consume_goal(ctx["node"])
    save(ctx, st)


def write_progress(ctx, st):
    """給 kernel 判斷卡住：每處理一個 tock 就寫（含 round），處理不了 tock 的才會連續不變。
    另記一行 trace.jsonl（每個處理過的 tock 在什麼狀態），事後算閒置比例、被併掉的回合。"""
    p = {"round": st["round"], "state": st["state"], "steps": st["steps"]}
    write_json(os.path.join(ctx["task"], "progress.json"), p)
    append_jsonl(os.path.join(ctx["task"], "trace.jsonl"), dict(p, at=now()))


def wake_goal(ctx, st, rnd):
    """agent.json 的 "wake": {"rounds": N, "unless": "work/DONE.md"}：閒了 N 個自己的回合沒有新信、unless 的檔又還不在，
    就自己醒來想一次（goal＝{"wake": ...}）。沒設就永遠等信（預設）。"""
    w = load_cfg(ctx).get("wake")
    if not isinstance(w, dict) or not isinstance(w.get("rounds"), int):
        return None
    if w.get("unless") and os.path.exists(os.path.join(ctx["node"], w["unless"])):
        return None
    idle = rnd - st.get("active_round", 0)
    if idle < w["rounds"]:
        return None
    return {"wake": "已經 %d 回合沒有新信。看一下 memory 裡的往來：是不是有人在等你、或有事被漏掉了？需要就寄信推進，不需要就回 none。" % idle}


def on_tock(ctx, st, rnd):
    """收到第 rnd 回合的 tock：換一次狀態並做新狀態的事。回新的 st（也已存檔）。"""
    st["round"], st["tocks"] = rnd, st.get("tocks", 0) + 1
    for r in tools.flush_outbox(ctx):   # 上回合等加掛的信，掛上了就先寄
        log(ctx, st, r)
    s = st["state"]
    if s == "idle":
        names, goal = tools.list_inbox(ctx["node"]), tools.pending_goal(ctx["node"])
        if not names and not goal:
            goal = wake_goal(ctx, st, rnd)
        if names or goal:
            st.update(state="think", letters=names, goal=goal, plan=None, pc=0, steps=st["steps"] + 1,
                      active_round=rnd)
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
