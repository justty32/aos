"""kernel 任務包：替任務做決策的普通 keep 任務（spec.md）。

    aos7-kernel run [--dry-run] [--rounds N]   keep 任務用：等自己的 tock → 核 pending → 快照 → 規則 → 驗證 → 存 state → 送 → 核對
    aos7-kernel status <node>                  一行白話

設定 <node>/kernel/kernel.json；state 在自己的槽（$AOS7_TASK/state.json）。核心不知道這個包；控制只用核心的 ctl.json kill。
"""
import contextlib
import io
import argparse
import json
import os
import signal
import sys
import time

from aos7_kernel_state import (Stop, decisions_path, load_config, load_state, same_place,  # noqa: E402
                               save_state, slot_dir, snapshot, state_path, TOP)
from aos7_fs import BAD, N, OK, U, fact, is_int, now, test_point, write_json  # noqa: E402
from aos7_taskside import resolver, task_env, wait_tock  # noqa: E402

PROG = "aos7-kernel"
NOTIFY_MAX = 10


from aos7_kernel_rules import RULES


def flat(value):
    return " ".join(str(value).splitlines())


def error(value):
    print(flat(value), file=sys.stderr, flush=True)


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
        if not isinstance(c.get("text"), str) or not c["text"].strip() or "\n" in c["text"] or "\r" in c["text"]:
            return "text 要是非空的一行"
        if "body" in c and not isinstance(c["body"], str):
            return "body 要是字串"
    else:
        return "op 只有 kill、notify"
    return None if _jsonable(c.get("basis")) else "basis 要能存成 JSON"


# ---------- 送出與核對（spec §7） ----------

def _receipt_matches(r, p):
    """回條的原請求（id、op、run）是不是這筆意圖的。不看 result.run 來關聯：拒絕回條的 result.run 可能是新 run。"""
    return isinstance(r, dict) and r.get("id") == p["id"] and r.get("op") == "kill" and is_int(r.get("run")) and r.get("run") == p["run"]


def _result_ok(r, p):
    """相符回條的結果：True 成功（result.run 也要是原 run）｜False 失敗｜None 形狀不合（不確定）。"""
    res = r.get("result")
    if not (isinstance(res, dict) and isinstance(res.get("ok"), bool) and isinstance(res.get("msg"), str)):
        return None
    if res["ok"]:
        return True if res.get("run") == "%s#%d" % (p["target"]["slot"], p["run"]) else None
    return False


def settle_kill(env, p, resolve):
    """回 ("done", 結果, msg)｜("wait", msg)｜("sent", None)。只對 p 的原 run、原 id 動作。"""
    sd = slot_dir(env, p["target"], resolve)
    if sd is None:
        return "wait", "目標 node %s 沒掛載" % p["target"]["node"]
    cst, ctl = fact(os.path.join(sd, "ctl.json"))
    if cst == OK and isinstance(ctl, dict) and ctl.get("id") == p["id"]:
        rst, r = fact(os.path.join(sd, "ctl-done.json"))
        if rst == OK and _receipt_matches(r, p) and _result_ok(r, p) is True:
            return "done", "ok", r["result"]["msg"]
        return "sent", None
    if cst == OK or cst == BAD:
        return "wait", "控制衝突：槽裡已有別人的 ctl.json，不覆蓋"
    if cst != N:
        return "wait", "ctl.json 讀不到"
    rst, r = fact(os.path.join(sd, "ctl-done.json"))
    if rst == U or rst == BAD:   # 壞回條可能就是我們的：不確定，不補送
        return "wait", "ctl-done.json 讀不到或壞了，不確定送過沒，不補送"
    if rst == OK and _receipt_matches(r, p):
        ok = _result_ok(r, p)
        if ok is None:
            return "wait", "回條相符但結果欄位不合，不確定，不補送"
        msg = r["result"]["msg"]
        if ok:
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
        return "done", "logged", "沒設 mail，通知只記在 state 的 done（status 看得到）"
    sys.path.insert(0, os.path.join(TOP, "modules", "mail"))
    import aos7_mail   # noqa: E402
    root = os.path.normpath(os.path.join(env["node"], mail["root"]))
    body = p.get('body') or ('## 做了什麼\n監督者提醒你：「%s」。\n\n' % p['text'] +
        '## 產出（檔案路徑 / commit / 分支）\n沒有產出，這封只是提醒。\n\n'
        '## 沒做到、或證據不足的部分\n詳細原因尚待確認。\n\n'
        '## 需要對方或使用者決定的事\n請先查看下方的紀錄，再決定是否處理。')
    body += '\n\n想看細節的（給維護者）：' + state_path(env['task']) + '\n'
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            aos7_mail.send(root, mail.get("from", "kernel"), p["target"], "NEEDS-USER", p["text"],
                           body, ident=p["id"])
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
            d = {k: p[k] for k in ("id", "op", "target", "run", "text", "body", "basis", "tock") if k in p}
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
            ctx = {"v": 1, "tock": tock, "config": dict(cfg, **r), "rule": r}
            outs.append((r["name"], rules[r["name"]](ctx, json.loads(json.dumps(snap)),
                                                       json.loads(json.dumps(state["rules"].get(r["name"], {}))))))
        states, cands, why = validate(cfg, outs)
    except Exception as e:   # 規則丟例外＝這輪不提交（spec §5）
        states, cands, why = None, None, "規則 %s 丟了例外：%s: %s" % (r["name"], type(e).__name__, e)
    rec = {"tock": tock, "at": now(), "decided": [], "rejected": why, "note": None}
    if why:
        return None, [], rec
    busy = [c["target"]["slot"] for c in cands if c["op"] == "kill" and any(
        p["op"] == "kill" and same_place(p["target"], c["target"]) for p in state["pending"])]
    notes = sum(1 for p in state["pending"] if p["op"] == "notify")
    if busy or notes >= NOTIFY_MAX:
        # 整輪延後：規則狀態不存（它會以為已經出過），下一個 tock 重判（spec §5）
        rec["note"] = "延後：%s" % ("目標已有在途的 kill（%s）" % "、".join(busy) if busy
                                   else "在途通知已有 %d 封" % NOTIFY_MAX)
        return None, [], rec
    new = []
    for i, c in enumerate(cands):
        p = {"id": "k-%s-%d-%d" % (state["instance"][:8], state["rev"] + 1, i), "op": c["op"], "target": c["target"],
             "basis": c.get("basis"), "sent": False, "tock": tock, "rule": c["rule"]}
        p.update({"run": c["run"], "why": c["why"]} if c["op"] == "kill" else {k: c[k] for k in ("text", "body") if k in c})
        new.append(p)
    rec["decided"] = new
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
        error("%s: 不確定：state.json 寫不進去（%s），這個 tock 不算處理過。下一個 tock 再試" % (PROG, e))
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
        for p in rec["decided"]:      # 模擬的 id 跟正式的分開，不會被誤認成之後真的決定
            p["id"] = "dry-" + p["id"]
        print(json.dumps(rec, ensure_ascii=False))
        if rec["rejected"]:
            raise Stop(1, "規則的輸出被拒絕：%s。修好規則或 kernel.json 再試" % rec["rejected"])
        return 0
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    signal.signal(signal.SIGINT, lambda *_: stop.append(1))
    state = _settle_safe(env, cfg, state, resolve)          # ② 不等 tock
    seen = 0
    while not stop:
        t = wait_tock(env["task"], state["last_tock"], timeout=0.2, run=env["run"])
        if not is_int(t):
            continue
        load_config_same(env, rules, sha)
        state = _settle_safe(env, cfg, state, resolve)
        before = state
        state = one_tock(env, cfg, state, t, resolve, rules)
        if state is before:      # 沒存進去：水位不前進，稍後重做同一個 tock
            time.sleep(0.2)
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
        error("%s: 不確定：state.json 寫不進去（%s），在途的留著。下一個 tock 再核" % (PROG, e))
        return state


def kernel_slots(node):
    """tasks.json 裡 argv 含 aos7-kernel 的項目名（＝槽名）；讀不到回 None。"""
    st, t = fact(os.path.join(node, ".aos", "tasks.json"))
    if st not in (N, OK):
        return None
    items = t.get("tasks") if st == OK and isinstance(t, dict) and isinstance(t.get("tasks"), list) else []
    return [i["name"] for i in items if isinstance(i, dict) and isinstance(i.get("name"), str)
            and any("aos7-kernel" in str(a) for a in (i.get("argv") or []))]


def status_line(node, rules=None):
    """回 (退出碼, 一行)。"""
    cfg, sha = load_config(node, rules or RULES)
    n = len(cfg['sources'])
    slots = kernel_slots(node)
    if slots is None:
        return 3, "不確定：tasks.json 讀不到，找不到 kernel 的槽。照原樣再看一次"
    task = os.path.join(node, '.aos', 'tasks', (slots or ['kernel'])[0])
    s = load_state(task, sha, init=False)
    if not os.path.exists(state_path(task)):
        return 0, "監督 %d 件：kernel 還沒開始（等它第一次收到心跳）" % n
    parts = []
    for p in s["pending"]:
        if p.get("op") == "kill":
            parts.append("kill %s#%s %s" % (p["target"].get("slot"), p.get("run"), "等回條（可能晚一點才生效）"
                                            if p.get("sent") else "還沒送出"))
        else:
            parts.append("通知 %s 還沒寄出" % p.get("target"))
        if p.get("wait"):
            parts[-1] += "（%s）" % p["wait"]
    word = {'ok': '已 kill', 'sent': '已寄信', 'logged': '已記下', 'superseded': '目標已換 run、沒 kill',
            'rejected': 'kill 被核心拒絕', 'unknown': 'kill 結果不確定'}
    for d in s['done']:
        if d['tock'] == s['last_tock']:
            target = d['target'] if d['op'] == 'notify' else '%s#%s' % (d['target']['slot'], d['run'])
            parts.append('%s %s' % (word.get(d['result'], d['result']), target))
    rstate = s['rules'].get('supervise-brain', {})
    rule = next((r for r in cfg['rules'] if r['name'] == 'supervise-brain'), {})
    for src in cfg['sources']:
        key = src['node'] + '/' + src['slot']
        brain = rstate.get('brains', {}).get(key)
        if rstate.get('gaps', {}).get(key) or (brain and brain['gap']):
            parts.append('%s 讀不到，等它恢復' % src['node'])
        elif brain and brain['last'] - brain['since'] >= rule.get('no_progress_rounds', 6):
            notified = rstate.get('notified', {}).get(key) == brain['id'] or brain['notified']
            parts.append('%s 停在第 %d 步，停住 %d 回合%s' % (src['node'], brain['step'],
                brain['last'] - brain['since'], ('，已寄信給 ' + rule.get('notify', 'you') if cfg.get('mail')
                else '，提醒已記下') if notified and not any(p['op'] == 'notify' and isinstance(p.get('basis'), dict) and p['basis'].get('src') == key for p in s['pending']) else ''))
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
    def bad_usage(msg):
        error("%s: 用法不對（%s）。例：aos7-kernel run、aos7-kernel status house/bob" % (PROG, msg))
        sys.exit(2)
    ap.error = bad_usage
    for p in (r, s):
        p.error = bad_usage
    a = ap.parse_args(argv)
    try:
        if a.cmd == "status":
            code, line = status_line(a.node, rules)
            if code:
                error("%s: %s" % (PROG, line))
            else:
                print(flat(line))
            return code
        return cmd_run(a, rules)
    except Stop as e:
        error("%s: %s" % (PROG, e))
        return e.code
    except OSError as e:
        error("%s: 不確定：讀寫失敗（%s），已寫的 state 與在途請求都留著。照原樣再跑一次會接續" % (PROG, e))
        return 3
    except Exception as e:
        error("%s: 不確定：程式出錯（%s: %s）。照原樣再跑一次；一直這樣請人看" % (PROG, type(e).__name__, e))
        return 3
