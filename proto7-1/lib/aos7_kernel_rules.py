"""kernel 的一輪規則：先把檔案系統拍成快照（snapshot），再用純函式 run_rules 算決定（spec.md 第 9 節）。"""
import copy
import os

import aos7_fs as fs


# ---------- 讀檔案系統：任務狀態（不依賴 aos7_task.py，自己判斷） ----------

def pid_alive(pid):
    """程序還在嗎？os.kill(pid, 0)；沒權限也算在。"""
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (TypeError, ValueError, OSError):
        return False
    return True


def task_state(taskdir):
    """回 'ended'／'live'／'lost'（spec 第 5 節的判斷，簡化版）。"""
    if os.path.exists(os.path.join(taskdir, "exit.json")):
        return "ended"
    pid = fs.read_json(os.path.join(taskdir, "pid.json"))
    if pid is None:
        return "live"  # 只有 birth.json＝剛起，算活
    return "live" if pid_alive(pid.get("pid")) else "lost"


def list_tasks(node):
    """列 node 下所有任務資料夾（有 birth.json 的），依 tid 排序。"""
    base = os.path.join(fs.aos_dir(node), "tasks")
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    out = []
    for tid in names:
        d = os.path.join(base, tid)
        birth = fs.read_json(os.path.join(d, "birth.json"))
        if isinstance(birth, dict):
            out.append((tid, d, birth))
    return out


def _tokens(usage):
    if isinstance(usage, dict) and isinstance(usage.get("tokens"), (int, float)):
        return usage["tokens"]
    return 0


def snapshot_node(node):
    """一個 node 的快照：回合、各任務（活不活、progress、用量、有沒有待執行的 ctl）、用量總和。"""
    rnd = fs.read_json(os.path.join(fs.aos_dir(node), "round.json")) or {}
    tasks, total = [], 0
    for tid, d, birth in list_tasks(node):
        usage = fs.read_json(os.path.join(d, "usage.json"))
        total += _tokens(usage)
        tasks.append({
            "tid": tid, "name": birth.get("name"), "birth_round": birth.get("round"),
            "alive": task_state(d) == "live",
            "progress": fs.read_json(os.path.join(d, "progress.json")),
            "has_ctl": os.path.exists(os.path.join(d, "ctl.json")),
        })
    return {"exists": os.path.isdir(fs.aos_dir(node)), "round": rnd.get("round"),
            "tasks": tasks, "usage_total": total}


def snapshot(root, node_id, self_tid, cfg, rnd):
    """整輪要看的東西一次讀好；之後 run_rules 不再碰檔案。"""
    status = fs.read_json(os.path.join(root, ".aosd", "status.json")) or {}
    snodes = status.get("nodes") or {}
    me = snapshot_node(fs.node_path(root, node_id))
    members = {}
    for rel in cfg.get("members") or []:
        mid = fs.join_id(node_id, rel)
        m = snapshot_node(fs.node_path(root, mid))
        m["paused_by_daemon"] = bool((snodes.get(mid) or {}).get("paused"))
        members[mid] = m
    return {"round": rnd, "node_id": node_id, "self_tid": self_tid,
            "self_tasks": me["tasks"], "members": members}


# ---------- 純函式：設定＋狀態＋快照 → 決定清單＋新狀態 ----------

def empty_state():
    return {"progress": {}, "usage": {}, "paused": {}, "issued": {}}


def _decision(rnd, rule, target, op, why):
    return {"round": rnd, "rule": rule, "target": target, "op": op, "why": why}


def rule_stuck(cfg, st, snap, out):
    """卡住：progress 連續 stuck_rounds 個「成員回合」沒變 → restart。"""
    n = cfg.get("stuck_rounds")
    if not isinstance(n, int) or n <= 0:
        return
    seen = set()
    for mid, m in snap["members"].items():
        paused = m.get("paused_by_daemon") or mid in st["paused"]
        for t in m["tasks"]:
            if not t["alive"] or t["progress"] is None:
                continue
            if mid == snap["node_id"] and t["tid"] == snap["self_tid"]:
                continue  # 不管自己
            key = "%s:%s" % (mid, t["tid"])
            seen.add(key)
            rec = st["progress"].get(key)
            if rec is None or rec["last"] != t["progress"]:
                st["progress"][key] = {"last": t["progress"], "same": 0, "member_round": m["round"]}
                continue
            # 成員回合有前進才算「一輪沒變」；pause 中的 node 不算（它收不到 tock，本來就不會動）
            advanced = m["round"] is None or rec["member_round"] is None or m["round"] > rec["member_round"]
            if advanced and not paused:
                rec["same"] += 1
                rec["member_round"] = m["round"]
            if rec["same"] >= n and key not in st["issued"] and not t["has_ctl"]:
                out.append(_decision(snap["round"], "stuck", key, "restart",
                                     "progress 連續 %d 回合沒變" % rec["same"]))
                st["issued"][key] = "restart"
    for key in list(st["progress"]):
        if key not in seen:
            del st["progress"][key]


def rule_budget(cfg, st, snap, out):
    """預算：成員 node 用量增量累計超過 budget_tokens → pause；cool_rounds 個 kernel 回合後 resume。"""
    budget = cfg.get("budget_tokens")
    if not isinstance(budget, (int, float)):
        return
    cool = cfg.get("cool_rounds", 3)
    rnd = snap["round"]
    for mid, m in snap["members"].items():
        if not m["exists"]:
            continue
        if mid == snap["node_id"]:
            continue  # pause 自己的 node 就再也收不到 tock、無法 resume，跳過
        total = m["usage_total"]
        u = st["usage"].get(mid)
        if u is None:
            u = st["usage"][mid] = {"last": total, "acc": 0}  # 第一次看到：當基準，不算舊帳
        else:
            u["acc"] += max(0, total - u["last"])
            u["last"] = total
        p = st["paused"].get(mid)
        if p is not None:
            if rnd - p["at"] >= cool:
                out.append(_decision(rnd, "budget", mid, "resume",
                                     "pause 後已過 %d 回合" % (rnd - p["at"])))
                del st["paused"][mid]
                u["acc"] = 0
        elif u["acc"] > budget:
            out.append(_decision(rnd, "budget", mid, "pause",
                                 "用量累計 %s > %s" % (u["acc"], budget)))
            st["paused"][mid] = {"at": rnd}


def rule_age(cfg, st, snap, out):
    """壽命：自己 node 上名字在 max_age 的活任務，活超過那麼多回合 → kill。"""
    ages = cfg.get("max_age") or {}
    rnd = snap["round"]
    for t in snap["self_tasks"]:
        lim = ages.get(t["name"])
        if not t["alive"] or not isinstance(lim, int) or not isinstance(t["birth_round"], int):
            continue
        key = "%s:%s" % (snap["node_id"], t["tid"])
        age = rnd - t["birth_round"]
        if age > lim and key not in st["issued"] and not t["has_ctl"]:
            out.append(_decision(rnd, "age", key, "kill", "活了 %d 回合 > %d" % (age, lim)))
            st["issued"][key] = "kill"


def run_rules(cfg, state, snap):
    """一輪規則。回 (decisions, new_state)；不碰檔案系統。"""
    st = empty_state()
    st.update(copy.deepcopy(state or {}))
    out = []
    rule_stuck(cfg, st, snap, out)
    rule_budget(cfg, st, snap, out)
    rule_age(cfg, st, snap, out)
    # 已下過指令的任務若已不活，就從 issued 移掉（之後同名新任務會是新 tid）
    alive = {"%s:%s" % (mid, t["tid"]) for mid, m in snap["members"].items() for t in m["tasks"] if t["alive"]}
    alive |= {"%s:%s" % (snap["node_id"], t["tid"]) for t in snap["self_tasks"] if t["alive"]}
    st["issued"] = {k: v for k, v in st["issued"].items() if k in alive}
    return out, st
