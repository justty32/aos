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


def list_tasks(aos):
    """列 `<aos>/tasks/` 下所有任務資料夾（有 birth.json 的），依 tid 排序。aos＝某 node 的 .aos（可能是掛載點）。"""
    base = os.path.join(aos, "tasks")
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


def snapshot_node(aos):
    """一個 node 的快照：回合、各任務（活不活、progress、用量、有沒有待執行的 ctl）、用量總和。

    aos＝那個 node 的 `.aos`（自己的直接給；成員的經過掛載點；沒掛載＝None，當作不存在）。"""
    if aos is None:
        return {"exists": False, "mounted": False, "round": None, "tasks": [], "usage_total": 0}
    rnd = fs.read_json(os.path.join(aos, "round.json")) or {}
    tasks, total = [], 0
    for tid, d, birth in list_tasks(aos):
        usage = fs.read_json(os.path.join(d, "usage.json"))
        total += _tokens(usage)
        tasks.append({
            "tid": tid, "name": birth.get("name"), "birth_round": birth.get("round"),
            "alive": task_state(d) == "live",
            "progress": fs.read_json(os.path.join(d, "progress.json")),
            "has_ctl": os.path.exists(os.path.join(d, "ctl.json")),
        })
    return {"exists": os.path.isdir(aos), "mounted": True, "round": rnd.get("round"),
            "tasks": tasks, "usage_total": total}


def snapshot(root, node_id, self_tid, cfg, rnd, resolve):
    """整輪要看的東西一次讀好；之後 run_rules 不再碰檔案。

    自己的 node 直接讀；別的 node 與 daemon 的 status.json 一律經過 resolve（掛載點，S-23），沒掛載就看不到。"""
    sp = resolve(".aosd/status.json")
    status = (fs.read_json(sp) if sp else None) or {}
    snodes = status.get("nodes") or {}
    me = snapshot_node(fs.aos_dir(fs.node_path(root, node_id)))
    members = {}
    for rel in cfg.get("members") or []:
        mid = fs.join_id(node_id, rel)
        m = me if mid == node_id else snapshot_node(resolve(mid + "/.aos"))
        m = dict(m)
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
    """卡住：progress 連續 stuck_rounds 個「成員回合」沒變 → restart。

    progress 寫著 `llm_since`（agent 正在等 LLM）的不算卡住；要管就另設 `llm_stuck_rounds`（problems-real.md R-3）。"""
    n0, nl = cfg.get("stuck_rounds"), cfg.get("llm_stuck_rounds")
    if not (isinstance(n0, int) and n0 > 0) and not (isinstance(nl, int) and nl > 0):
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
            llm = isinstance(t["progress"], dict) and t["progress"].get("llm_since")
            n = nl if llm else n0
            if not isinstance(n, int) or n <= 0:
                continue
            if rec["same"] >= n and key not in st["issued"] and not t["has_ctl"]:
                out.append(_decision(snap["round"], "stuck", key, "restart",
                                     "progress 連續 %d 回合沒變%s" % (rec["same"], "（在等 LLM，從 %s 起）" % llm if llm else "")))
                st["issued"][key] = "restart"
    for key in list(st["progress"]):
        if key not in seen:
            del st["progress"][key]


def rule_budget(cfg, st, snap, out):
    """預算：成員 node 用量增量累計超過 budget_tokens → pause；cool_rounds 個 kernel 回合後 resume（限速）。

    總額：成員 node 用量總和（含已結束的任務）超過 cap_tokens → pause，不自動 resume；人改 kernel.json
    （調高或拿掉 cap_tokens）後才 resume（problems-real.md R-4）。
    kernel 自己 pause 的，自己負責到期 resume，不管對方還在不在 members（astra-2 二-7）。"""
    budget, cap = cfg.get("budget_tokens"), cfg.get("cap_tokens")
    has_budget = isinstance(budget, (int, float))
    has_cap = isinstance(cap, (int, float))
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
        if p is not None and p.get("cap"):
            if not has_cap or total <= cap:
                out.append(_decision(rnd, "cap", mid, "resume", ("用量 %s ≤ cap_tokens %s" % (total, cap) if has_cap else "kernel.json 拿掉了 cap_tokens（用量 %s）" % total)))
                del st["paused"][mid]
                u["acc"] = 0
        elif has_cap and total > cap:
            out.append(_decision(rnd, "cap", mid, "pause",
                                 "用量總和 %s > cap_tokens %s；不會自動恢復，要人改 kernel.json" % (total, cap)))
            st["paused"][mid] = {"at": rnd, "cap": True}
        elif p is not None:
            if rnd - p["at"] >= cool:
                out.append(_decision(rnd, "budget", mid, "resume",
                                     "pause 後已過 %d 回合" % (rnd - p["at"])))
                del st["paused"][mid]
                u["acc"] = 0
        elif has_budget and u["acc"] > budget:
            out.append(_decision(rnd, "budget", mid, "pause",
                                 "用量累計 %s > %s" % (u["acc"], budget)))
            st["paused"][mid] = {"at": rnd}
    # 已不在 members 的：限速的 pause 照樣到期 resume；總額的 pause 沒有到期，留著
    for mid, p in list(st["paused"].items()):
        if mid in snap["members"] or p.get("cap"):
            continue
        if rnd - p["at"] >= cool:
            out.append(_decision(rnd, "budget", mid, "resume",
                                 "pause 後已過 %d 回合（已不在 members，自己下的 pause 自己收）" % (rnd - p["at"])))
            del st["paused"][mid]
            if mid in st["usage"]:
                st["usage"][mid]["acc"] = 0  # 同在冊的分支：resume 後累計歸零（astra-3 三-1）


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
