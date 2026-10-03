"""aos7-kernel：常駐任務，每收到一次 tock 跑一輪規則，把決定寫成控制檔（spec.md 第 9 節；S-16～S-18）。"""
import argparse
import os
import signal
import sys

import aos7_fs as fs
import aos7_mount
from aos7_kernel_rules import empty_state, run_rules, snapshot

STATE = "kernel-state.json"


def load_config(node):
    """讀 <node>/kernel.json；每輪重讀，人或 LLM 改檔就生效（S-01）。"""
    cfg = fs.read_json(os.path.join(node, "kernel.json"))
    return cfg if isinstance(cfg, dict) else {}


def load_state(env):
    """先找自己的 kernel-state.json；沒有就接前一任的（restart_of，否則同名最新的一個）。"""
    own = fs.read_json(os.path.join(env["task"], STATE))
    if isinstance(own, dict):
        return own
    tasks = os.path.dirname(env["task"])
    birth = fs.read_json(os.path.join(env["task"], "birth.json")) or {}
    cands = []
    if birth.get("restart_of"):
        cands.append(birth["restart_of"])
    name = birth.get("name")
    try:
        sibs = []
        for tid in os.listdir(tasks):
            b = fs.read_json(os.path.join(tasks, tid, "birth.json")) or {}
            if tid != env["tid"] and name and b.get("name") == name:
                sibs.append((b.get("round") or 0, tid))
        cands += [tid for _, tid in sorted(sibs, reverse=True)]
    except OSError:
        pass
    for tid in cands:
        st = fs.read_json(os.path.join(tasks, tid, STATE))
        if isinstance(st, dict):
            st = dict(st)
            st["inherited_from"] = tid
            return st
    return empty_state()


def apply_decision(env, d, seq, resolve):
    """把一個決定寫成控制檔：kill/restart → 任務 ctl.json；pause/resume → daemon ctl。

    別的 node 與 daemon 的控制檔一律經過掛載點寫（S-23）；自己 node 的任務直接寫。回 None＝寫了，否則回沒寫的原因。"""
    by = "%s:%s" % (env["node_id"], env["tid"])
    if d["op"] in ("pause", "resume"):
        safe = "".join(c if c.isalnum() else "_" for c in d["target"])
        name = "kernel-%s-r%d-%d-%s-%s.json" % (env["tid"], d["round"], seq, d["op"], safe)
        ctl = resolve(".aosd/ctl")
        if ctl is None:
            return "daemon 的 .aosd/ctl 沒掛載"
        fs.write_json(os.path.join(ctl, name), {"op": d["op"], "node": d["target"], "by": by, "why": d["why"]})
        return None
    node_id, tid = d["target"].rsplit(":", 1)
    rel = os.path.join("tasks", tid, "ctl.json")
    if node_id == env["node_id"]:
        path = os.path.join(fs.aos_dir(env["node"]), rel)
    else:
        aos = resolve(node_id + "/.aos")
        if aos is None:
            return "%s/.aos 沒掛載" % node_id
        path = os.path.join(aos, rel)
    if os.path.exists(path):
        return "ctl.json 已存在"  # 別人先下了，不蓋掉
    fs.write_json(path, {"op": d["op"], "by": by, "why": d["why"]})
    return None


def ask_mounts(env, cfg):
    """kernel.json 的成員（與 daemon 的 .aosd）沒掛給自己的，寫加掛請求，下個 tick 掛上（S-23、M-6）。

    所以新增成員只要改 kernel.json；掛上之前那個成員看不到（快照 mounted: false）。"""
    want = [".aosd"] + ["%s/.aos" % fs.join_id(env["node_id"], rel) for rel in cfg.get("members") or []
                        if isinstance(rel, str) and fs.join_id(env["node_id"], rel) != env["node_id"]]
    for path in want:
        st = aos7_mount.request(env["task"], path, why="kernel 要看／控制 %s" % path)
        if st != "mounted":
            print("aos7-kernel: 加掛 %s：%s" % (path, st), flush=True)


ROSTER = "roster.json"


def roster_of(env, cfg):
    """成員名冊（problems-real.md R-2，使用者選 (b)）：kernel.json 的 members，各帶 node id、收件路徑、角色一句
    （kernel.json 的 `roles`：{成員相對路徑: "一句"}，沒寫就空字串）。"""
    roles = cfg.get("roles") if isinstance(cfg.get("roles"), dict) else {}
    out = []
    for rel in cfg.get("members") or []:
        if isinstance(rel, str):
            mid = fs.join_id(env["node_id"], rel)
            out.append({"node": mid, "inbox": mid + "/inbox", "role": str(roles.get(rel, ""))})
    return {"by": env["node_id"], "members": out}


def write_rosters(env, cfg, resolve, rnd=None):
    """把名冊寫進每個成員自己的 `.aos/roster.json`（經過 kernel 已有的 `.aos` 掛載點）；內容沒變就不寫。

    寫不進去（成員搬走、掛載斷了）只在 decisions.jsonl 記一行、跳過那個成員，kernel 不死（astra-3 三-2）。"""
    ros = roster_of(env, cfg)
    for m in ros["members"]:
        aos = fs.aos_dir(env["node"]) if m["node"] == env["node_id"] else resolve(m["node"] + "/.aos")
        if aos is None:
            continue
        path = os.path.join(aos, ROSTER)
        if fs.read_json(path) != ros:
            try:
                fs.write_json(path, ros)
            except OSError as e:
                fs.append_jsonl(os.path.join(env["task"], "decisions.jsonl"),
                                {"round": rnd, "rule": "roster", "target": m["node"], "op": "write",
                                 "why": "寫名冊", "at": fs.now(), "skipped": "寫不進去：%s" % e})


def one_round(env, rnd):
    """收到第 rnd 回合的 tock：快照 → 規則 → 寫控制檔、decisions.jsonl、kernel-state.json。"""
    cfg = load_config(env["node"])
    state = load_state(env)
    ask_mounts(env, cfg)
    resolve = aos7_mount.resolver(env["task"])
    write_rosters(env, cfg, resolve, rnd)
    snap = snapshot(env["root"], env["node_id"], env["tid"], cfg, rnd, resolve)
    decisions, new = run_rules(cfg, state, snap)
    for i, d in enumerate(decisions):
        try:
            why_not = apply_decision(env, d, i, resolve)
        except OSError as e:  # 寫成員或 daemon 的控制檔失敗（掛載斷了等）：記下來，不拖垮 kernel
            why_not = "寫不進去：%s" % e
        rec = dict(d, at=fs.now())
        if why_not:
            rec["skipped"] = why_not
        fs.append_jsonl(os.path.join(env["task"], "decisions.jsonl"), rec)
    new["round"] = rnd
    new.pop("inherited_from", None)
    fs.write_json(os.path.join(env["task"], STATE), new)
    return decisions


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aos7-kernel", description="依 kernel.json 管成員 node 的任務與時間線")
    ap.add_argument("--rounds", type=int, default=0, help="收到 N 次 tock 後自行結束（0＝不限）")
    args = ap.parse_args(argv)
    try:
        env = fs.task_env()
    except KeyError as e:
        print("aos7-kernel: 缺環境變數 %s（要由 tick 啟動）" % e, file=sys.stderr)
        return 2
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    signal.signal(signal.SIGINT, lambda *_: stop.append(1))
    # 已處理過的回合記在 kernel-state.json（含接手前一任的）；tock.json 若在啟動前就到了照樣要處理
    last = load_state(env).get("round")
    last = last if isinstance(last, int) else 0
    seen = 0
    print("aos7-kernel: %s 啟動，等 tock（> %d）" % (env["tid"], last), flush=True)
    while not stop:
        r = fs.wait_tock(env["task"], last, timeout=0.2)
        if r is None:
            continue
        last = r
        ds = one_round(env, r)
        print("aos7-kernel: 回合 %d，%d 個決定" % (r, len(ds)), flush=True)
        seen += 1
        if args.rounds and seen >= args.rounds:
            print("aos7-kernel: 已收到 %d 次 tock，結束" % seen, flush=True)
            break
    return 0
