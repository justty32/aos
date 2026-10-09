"""kernel 任務包：替任務做決策的普通 keep 任務（spec.md）。

    aos7-kernel run [--dry-run] [--rounds N]   keep 任務用：等自己的 tock → 核 pending → 快照 → 規則 → 驗證 → 存 state → 送 → 核對
    aos7-kernel status <node>                  一行白話

設定 <node>/kernel/kernel.json；state 在自己的槽（$AOS7_TASK/state.json）。核心不知道這個包；控制只用核心的 ctl.json kill。
"""
import argparse
import json
import os
import signal
import sys

from aos7_kernel_state import (Stop, config_path, decisions_path, load_config, load_state, same_place,  # noqa: E402
                               save_state, slot_dir, snapshot, state_path, TOP)
from aos7_fs import BAD, N, OK, U, fact, is_int, now, test_point, write_json  # noqa: E402
from aos7_taskside import resolver, task_env, wait_tock  # noqa: E402

PROG = "aos7-kernel"


# ---------- 規則註冊（spec §5；薄入口可再注入） ----------

def noop(ctx, snap, rstate):
    """什麼都不做的規則（測試、只觀測用）。"""
    return rstate, []


RULES = {"noop": noop}
try:   # 真規則在 aos7_kernel_rules.py（KR1）；還沒有就只有 noop
    import aos7_kernel_rules as _rules   # noqa: E402
    if callable(getattr(_rules, "supervise_brain", None)):
        RULES["supervise-brain"] = _rules.supervise_brain
except ImportError:
    pass


# ---------- 驗證（spec §5） ----------

def _jsonable(x):
    try:
        json.dumps(x, ensure_ascii=False)
        return True
    except (TypeError, ValueError):
        return False


def validate(cfg, outs):
    """outs＝[(規則名, 回傳值)]。回 (新規則狀態 dict, 合併後候選 list, 錯誤字串或 None)。有錯＝整份不提交。"""
    states, cands = {}, []
    for name, out in outs:
        if not (isinstance(out, tuple) and len(out) == 2):
            return None, None, "規則 %s 要回 (rstate, candidates)" % name
        rs, cs = out
        if not isinstance(rs, dict) or not _jsonable(rs):
            return None, None, "規則 %s 的 rstate 要是能存成 JSON 的物件" % name
        if not isinstance(cs, list):
            return None, None, "規則 %s 的 candidates 要是 list" % name
        for c in cs:
            why = _bad_candidate(cfg, c)
            if why:
                return None, None, "規則 %s 的候選不合：%s：%s" % (name, why, json.dumps(c, ensure_ascii=False, default=str)[:200])
            cands.append(dict(c, rule=name))
        states[name] = rs
    merged = []
    for c in cands:
        if c["op"] == "kill":
            other = [m for m in merged if m["op"] == "kill" and same_place(m["target"], c["target"])]
            if other and other[0]["run"] != c["run"]:
                return None, None, "矛盾：同一目標 %s 要 kill 兩個不同的 run（%d、%d）" % (
                    c["target"]["slot"], other[0]["run"], c["run"])
            if other:
                continue
        elif any(m["op"] == "notify" and m["target"] == c["target"] and m["text"] == c["text"] for m in merged):
            continue
        merged.append(c)
    return states, merged, None


def _bad_candidate(cfg, c):
    if not isinstance(c, dict):
        return "不是物件"
    if c.get("op") == "kill":
        if not any(same_place(c.get("target"), t) for t in cfg["targets"]):
            return "target 不在 targets 裡"
        if not is_int(c.get("run")):
            return "run 要是整數"
        if not isinstance(c.get("why"), str):
            return "why 要是字串"
    elif c.get("op") == "notify":
        if not isinstance(c.get("target"), str) or not c["target"]:
            return "notify 的 target 要是收件名"
        if not isinstance(c.get("text"), str) or not c["text"].strip() or "\n" in c["text"]:
            return "text 要是非空的一行"
    else:
        return "op 只有 kill、notify"
    return None if _jsonable(c.get("basis")) else "basis 要能存成 JSON"


# ---------- 送出與核對（spec §7） ----------

def _receipt_matches(r, p):
    return isinstance(r, dict) and r.get("id") == p["id"] and r.get("op") == "kill" and r.get("run") == p["run"] \
        and isinstance(r.get("result"), dict)


def settle_kill(env, p, resolve):
    """回 ("done", 結果, msg)｜("wait", msg)｜("sent", None)。只對 p 的原 run、原 id 動作。"""
    sd = slot_dir(env, p["target"], resolve)
    if sd is None:
        return "wait", "目標 node %s 沒掛載" % p["target"]["node"]
    cst, ctl = fact(os.path.join(sd, "ctl.json"))
    if cst == OK and isinstance(ctl, dict) and ctl.get("id") == p["id"]:
        rst, r = fact(os.path.join(sd, "ctl-done.json"))
        if rst == OK and _receipt_matches(r, p) and r["result"].get("ok") is True:
            return "done", "ok", str(r["result"].get("msg", ""))
        return "sent", None
    if cst == OK or cst == BAD:
        return "wait", "控制衝突：槽裡已有別人的 ctl.json，不覆蓋"
    if cst != N:
        return "wait", "ctl.json 讀不到"
    rst, r = fact(os.path.join(sd, "ctl-done.json"))
    if rst == U:
        return "wait", "ctl-done.json 讀不到"
    if rst == OK and _receipt_matches(r, p):
        res = r["result"]
        msg = str(res.get("msg", ""))
        if res.get("ok") is True:
            return "done", "ok", msg
        return "done", ("unknown" if msg.startswith("unknown") else "rejected"), msg
    bst, birth = fact(os.path.join(sd, "birth.json"))
    if bst == N or (bst == OK and isinstance(birth, dict) and is_int(birth.get("run")) and birth["run"] != p["run"]):
        return "done", "superseded", "目標槽的 run 已不是 %d（%s），不轉向新 run" % (
            p["run"], "槽空了" if bst == N else "現在是 %d" % birth["run"])
    if bst != OK:
        return "wait", "目標 birth.json 讀不到"
    test_point("kernel-before-ctl")
    write_json(os.path.join(sd, "ctl.json"), {"op": "kill", "run": p["run"], "id": p["id"],
                                              "by": "kernel/%s" % env["tid"], "why": p.get("why", "")})
    test_point("kernel-after-ctl")
    return "sent", None


def settle_notify(env, cfg, p):
    mail = cfg.get("mail")
    if not mail:
        return "done", "logged", "沒設 mail，只寫在 decisions.json"
    sys.path.insert(0, os.path.join(TOP, "modules", "mail"))
    import aos7_mail   # noqa: E402
    root = os.path.normpath(os.path.join(env["node"], mail["root"]))
    try:
        aos7_mail.send(root, mail.get("from", "kernel"), p["target"], "NEEDS-USER", p["text"],
                       "kernel %s 的通知（依據：%s）" % (env["tid"], json.dumps(p.get("basis"), ensure_ascii=False)[:500]),
                       ident=p["id"])
    except (OSError, ValueError) as e:
        return "wait", "寄信失敗：%s" % e
    test_point("kernel-after-mail")
    return "done", "sent", "已寄 NEEDS-USER 給 %s" % p["target"]


def settle(env, cfg, state, resolve):
    """核所有 pending（spec §6 ②、⑥、⑦）。有變就存 state（失敗丟 OSError，呼叫的人保留舊的）。回新 state。
    等待的原因記在那筆 pending 的 `wait`（給 status 看），不蓋 last_error（那是規則與提交的錯）。"""
    pend, done, changed = [], list(state["done"]), False
    for p in state["pending"]:
        try:
            r = settle_kill(env, p, resolve) if p["op"] == "kill" else settle_notify(env, cfg, p)
        except OSError as e:
            r = ("wait", "寫不進去：%s" % e)
        if r[0] == "done":
            d = {k: p[k] for k in ("id", "op", "target", "run", "tock") if k in p}
            done.append(dict(d, result=r[1], msg=r[2], at=now()))
            changed = True
            continue
        q = dict(p, sent=True) if r[0] == "sent" else dict(p)
        q.pop("wait", None)
        if r[0] == "wait":
            q["wait"] = r[1]
        changed = changed or q != p
        pend.append(q)
    if not changed:
        return state
    new = dict(state, pending=pend, done=done, rev=state["rev"] + 1)
    test_point("kernel-before-settle-save")
    return save_state(env["task"], new)


# ---------- 一個 tock（spec §6 ③～⑤） ----------

def decide(env, cfg, state, tock, resolve, rules=None):
    """快照 → 規則 → 驗證。回 (新規則狀態, 新 pending, decisions.json 內容)；被拒時新規則狀態是 None。"""
    rules = rules or RULES
    snap = snapshot(env, cfg, resolve)
    outs = []
    try:
        for r in cfg["rules"]:
            ctx = {"v": 1, "tock": tock, "config": dict(cfg, **r)}
            outs.append((r["name"], rules[r["name"]](ctx, json.loads(json.dumps(snap)),
                                                       json.loads(json.dumps(state["rules"].get(r["name"], {}))))))
        states, cands, why = validate(cfg, outs)
    except Exception as e:   # 規則丟例外＝這輪不提交（spec §5）
        states, cands, why = None, None, "規則 %s 丟了例外：%s: %s" % (r["name"], type(e).__name__, e)
    rec = {"tock": tock, "at": now(), "decided": [], "rejected": why, "note": None}
    if why:
        return None, [], rec
    new, skipped = [], []
    for i, c in enumerate(cands):
        if c["op"] == "kill" and any(p["op"] == "kill" and same_place(p["target"], c["target"])
                                     for p in state["pending"]):
            skipped.append(c["target"]["slot"])
            continue
        p = {"id": "k-%s-%d-%d" % (state["instance"][:8], state["rev"] + 1, i), "op": c["op"], "target": c["target"],
             "basis": c.get("basis"), "sent": False, "tock": tock, "rule": c["rule"]}
        p.update({"run": c["run"], "why": c["why"]} if c["op"] == "kill" else {"text": c["text"]})
        new.append(p)
    rec["decided"] = new
    if skipped:
        rec["note"] = "目標已有在途的 kill，略過：%s" % "、".join(skipped)
    return states, new, rec


def one_tock(env, cfg, state, tock, resolve, rules=None):
    """處理一個新 tock：存 state（一次 rename）之後才送。回新 state；存不進去回原 state（水位不前進）。"""
    states, new, rec = decide(env, cfg, state, tock, resolve, rules)
    nxt = dict(state, last_tock=tock, rev=state["rev"] + 1)
    nxt["last_error"] = rec["rejected"]
    if states is not None:
        nxt["rules"] = dict(state["rules"], **states)
        nxt["pending"] = state["pending"] + new
    test_point("kernel-before-state")
    try:
        nxt = save_state(env["task"], nxt)
    except OSError as e:
        print("%s: 不確定：state.json 寫不進去（%s），這個 tock 不算處理過。下一個 tock 再試" % (PROG, e),
              file=sys.stderr, flush=True)
        return state
    test_point("kernel-after-state")
    try:
        write_json(decisions_path(env["task"]), rec)
    except OSError:
        pass   # 只給人看，寫不進去不影響恢復
    return nxt


# ---------- 指令 ----------

def cmd_run(args, rules=None):
    rules = rules or RULES
    try:
        env = task_env()
    except (KeyError, ValueError) as e:
        raise Stop(2, "缺環境變數 %s。run 要由核心起（tasks.json 的 keep 項目），例：aos7-ctl add <node> "
                      "'{\"name\":\"kernel\",\"mode\":\"keep\",\"argv\":[\"python3\",\"%s\",\"run\"]}'"
                      % (e, os.path.join(TOP, "packs", "kernel", "bin", "aos7-kernel")))
    resolve = resolver(env["task"])
    cfg, sha = load_config(env["node"], rules)
    state = load_state(env["task"], sha, init=not args.dry_run)
    if args.dry_run:
        _, new, rec = decide(env, cfg, state, state["last_tock"], resolve, rules)
        print(json.dumps(rec, ensure_ascii=False))
        return 0
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    signal.signal(signal.SIGINT, lambda *_: stop.append(1))
    state = _settle_safe(env, cfg, state, resolve)          # ② 不等 tock
    seen = 0
    while not stop:
        t = wait_tock(env["task"], state["last_tock"], timeout=0.2, run=env["run"])
        if t is None:
            continue
        load_config_same(env, rules, sha)
        state = _settle_safe(env, cfg, state, resolve)
        before = state
        state = one_tock(env, cfg, state, t, resolve, rules)
        if state is before:      # 沒存進去：等下一個 tock
            continue
        state = _settle_safe(env, cfg, state, resolve)
        seen += 1
        if args.rounds and seen >= args.rounds:
            break
    return 0


def load_config_same(env, rules, sha):
    _, now_sha = load_config(env["node"], rules)
    if now_sha != sha:
        raise Stop(1, "kernel.json 在跑的時候改了，停止新的決定，在途的留著。改回原樣就接續；"
                      "要換設定，等 pending 清空後刪掉 state.json 與 decisions.json")


def _settle_safe(env, cfg, state, resolve):
    try:
        return settle(env, cfg, state, resolve)
    except OSError as e:
        print("%s: 不確定：state.json 寫不進去（%s），在途的留著。下一個 tock 再核" % (PROG, e), file=sys.stderr, flush=True)
        return state


def kernel_slots(node):
    """tasks.json 裡 argv 含 aos7-kernel 的項目名（＝槽名）。"""
    st, t = fact(os.path.join(node, ".aos", "tasks.json"))
    items = t.get("tasks") if st == OK and isinstance(t, dict) and isinstance(t.get("tasks"), list) else []
    return [i["name"] for i in items if isinstance(i, dict) and isinstance(i.get("name"), str)
            and any("aos7-kernel" in str(a) for a in (i.get("argv") or []))]


def status_line(node):
    """回 (退出碼, 一行)。"""
    cst, cfg = fact(config_path(node))
    if cst == N:
        return 2, "這個 node 沒有 kernel/kernel.json。給有裝 kernel 的 node，例：aos7-kernel status house/bob"
    if cst != OK or not isinstance(cfg, dict) or not isinstance(cfg.get("sources"), list):
        return 3, "不確定：kernel.json 讀不到或不合。看一下 %s" % config_path(node)
    n = len(cfg["sources"])
    slots = kernel_slots(node) or ["kernel"]
    sst, s = fact(state_path(os.path.join(node, ".aos", "tasks", slots[0])))
    if sst == N:
        return 0, "監督 %d 件：kernel 還沒開始（等它第一次收到心跳）" % n
    if sst != OK or not isinstance(s, dict) or not isinstance(s.get("pending"), list):
        return 3, "不確定：kernel 的 state.json 讀不到。照原樣再看一次；一直這樣請人看 %s" % slots[0]
    parts = []
    for p in s["pending"]:
        if p.get("op") == "kill":
            parts.append("kill %s#%s %s" % (p["target"].get("slot"), p.get("run"), "等回條（可能晚一點才生效）"
                                            if p.get("sent") else "還沒送出"))
        else:
            parts.append("通知 %s 還沒寄出" % p.get("target"))
        if p.get("wait"):
            parts[-1] += "（%s）" % p["wait"]
    recent = [d for d in s.get("done", []) if d.get("tock") == s.get("last_tock")]
    word = {"ok": "已 kill", "sent": "已寄信", "logged": "已記下", "superseded": "目標已換 run、沒 kill",
            "rejected": "kill 被核心拒絕", "unknown": "kill 結果不確定"}
    for d in recent:
        parts.append("%s %s" % (word.get(d.get("result"), d.get("result")),
                                d.get("target") if d.get("op") == "notify" else "%s#%s" % (d["target"].get("slot"), d.get("run"))))
    if s.get("last_error"):
        parts.append("上次出錯：%s" % s["last_error"])
    return 0, "監督 %d 件：%s" % (n, "；".join(parts) if parts else "都在動，沒有要處理的")


def main(argv=None, rules=None):
    ap = argparse.ArgumentParser(prog=PROG, description="替任務做決策的 keep 任務（第一版：監督、綁 run 的 kill、通知）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="keep 任務用：每個 tock 跑一次規則")
    r.add_argument("--dry-run", action="store_true", help="只印會做的決定，什麼都不寫")
    r.add_argument("--rounds", type=int, default=0, help=argparse.SUPPRESS)
    s = sub.add_parser("status", help="一行白話看 kernel 在做什麼")
    s.add_argument("node")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "status":
            code, line = status_line(a.node)
            if code:
                print("%s: %s" % (PROG, line), file=sys.stderr)
            else:
                print(line)
            return code
        return cmd_run(a, rules)
    except Stop as e:
        print("%s: %s" % (PROG, e), file=sys.stderr, flush=True)
        return e.code
