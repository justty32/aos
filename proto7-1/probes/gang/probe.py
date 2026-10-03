"""gang：三個合作任務要一起起、一起取消（coscheduling／gang，E-04），用現有 spawn batch 湊。

五個情境 × 兩種做法（naive＝batch 起來就做；proto＝合作式 prepare／commit，探針當協調者），各自的 node、同時跑：
  bad        batch 裡 judge 那項 argv 壞掉 → 只跳過那項，其他照起
  keepblock  node 上已有一個活的 keep「judge」；batch 的 judge 是 keep → 被擋，其他照起
  tickkill   20 個成員的 batch，探針在 tick 起到一半時 SIGKILL 那個 tick → spawn 檔沒刪，下一個 tick 整批再起
  crash      三個都起來，b 做兩步後 exit 1；naive 由探針（當 kernel）對其餘的寫 task kill
  cross      a 在 x1（200 ms）、b 與 judge 在 x2（450 ms），兩個 node 同時寫 spawn
量：成組不完整時做的工作（partial）、同一角色兩份同時做的工作（dup）、同組起動的時間差。
"""
import json
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402

PY = pl.PY
MEM = os.path.join(HERE, "member.py")
ROLES = ["a", "b", "judge"]
BIG = ["m%02d" % i for i in range(20)]
RUN_S = 3.0
DEADLINE_S = 1.2       # proto：prepare 等這麼久還沒到齊就 abort


def item(cid, role, how, crash=None, **kw):
    argv = [PY, MEM, role, how] + ([str(crash)] if crash else [])
    return dict({"name": role, "argv": argv, "mounts": {"cohort": "cohorts/" + cid}}, **kw)


def proc_ticks(root, nid):
    """這個 node 正在跑的 aos7-tick 程序。"""
    out = []
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            with open("/proc/%s/cmdline" % p, "rb") as f:
                a = f.read().split(b"\0")
        except OSError:
            continue
        if any(x.endswith(b"aos7-tick") for x in a) and root.encode() in a and nid.encode() in a:
            out.append(int(p))
    return out


def main():
    r = pl.Result("gang")
    with pl.Space("gang") as sp:
        cases = {}       # cid -> {"mode", "roles", "spawn": [(nid, [items])]}
        for mode in ("naive", "proto"):
            c = "bad-" + mode
            bad = item(c, "judge", mode)
            bad["argv"] = [PY, 5]
            cases[c] = {"mode": mode, "roles": ROLES, "spawn": [(c, [item(c, "a", mode), item(c, "b", mode), bad])]}
            c = "keepblock-" + mode
            cases[c] = {"mode": mode, "roles": ROLES,
                        "spawn": [(c, [item(c, x, mode, mode="keep") for x in ROLES])],
                        "tasks": [{"name": "judge", "mode": "keep", "argv": ["sleep", "60"]}]}
            c = "tickkill-" + mode
            cases[c] = {"mode": mode, "roles": BIG, "spawn": [(c, [item(c, x, mode) for x in BIG])], "interval": 300}
            c = "crash-" + mode
            cases[c] = {"mode": mode, "roles": ROLES,
                        "spawn": [(c, [item(c, "a", mode), item(c, "b", mode, crash=2), item(c, "judge", mode)])]}
            c = "cross-" + mode
            cases[c] = {"mode": mode, "roles": ROLES, "spawn": [(c + "/x1", [item(c, "a", mode)]),
                                                                (c + "/x2", [item(c, "b", mode), item(c, "judge", mode)])],
                        "intervals": {c + "/x2": 450}}
        for cid, cs in cases.items():
            for nid, _ in cs["spawn"]:
                sp.node(nid, cs.get("tasks", []), interval_ms=cs.get("intervals", {}).get(nid, cs.get("interval", 200)))
            os.makedirs(os.path.join(sp.root, "cohorts", cid), exist_ok=True)
        sp.start()
        sp.wait_for(lambda: all(sp.round_of(nid) >= 2 for cs in cases.values() for nid, _ in cs["spawn"]), timeout=10)

        t_spawn = {}
        killed = {}
        for cid, cs in cases.items():
            if cid.startswith("tickkill"):
                continue
            t_spawn[cid] = time.time()
            for nid, items in cs["spawn"]:
                pl.write(sp.path(nid, ".aos", "spawn", "gang.json"), {"batch": items})
        for cid in ("tickkill-naive", "tickkill-proto"):
            # 等一個 tick 開始，再寫 spawn 會趕不上；改成：先寫 spawn，抓到這個 node 的 tick 起了 ≥1 個成員就 SIGKILL 它
            nid = cid
            tdir = sp.path(nid, ".aos", "tasks")
            sp.wait_for(lambda: sp.status().get("nodes", {}).get(nid, {}).get("phase") in ("idle",), timeout=5)
            t_spawn[cid] = time.time()
            pl.write(sp.path(nid, ".aos", "spawn", "gang.json"), {"batch": cases[cid]["spawn"][0][1]})
            pid, n_at_kill = None, None
            end = time.time() + 3
            while time.time() < end and n_at_kill is None:
                if pid is None:
                    ps = proc_ticks(sp.root, nid)
                    pid = ps[0] if ps else None
                    continue
                try:
                    n = sum(1 for t in os.listdir(tdir) if t[:1] == "m")
                except OSError:
                    n = 0
                if n >= 8:
                    try:
                        os.kill(pid, signal.SIGKILL)
                        n_at_kill = n
                    except ProcessLookupError:
                        pid = None
            spawn_left = os.path.exists(sp.path(nid, ".aos", "spawn", "gang.json"))
            killed[cid] = {"成員資料夾數（kill 當下）": n_at_kill, "spawn 檔還在": spawn_left, "nid": nid}

        # proto 的協調者（探針當 kernel）；naive crash 的取消也由探針當 kernel
        state = {cid: {"commit": None, "abort": None, "cancel": None} for cid in cases}
        t_end = time.time() + RUN_S
        while time.time() < t_end:
            for cid, cs in cases.items():
                co = os.path.join(sp.root, "cohorts", cid)
                st = state[cid]
                g = pl.fs.read_jsonl(os.path.join(co, "gang.jsonl"))
                if cs["mode"] == "proto":
                    ready = set(os.listdir(os.path.join(co, "ready"))) if os.path.isdir(os.path.join(co, "ready")) else set()
                    if st["commit"] is None and st["abort"] is None:
                        if ready >= set(cs["roles"]):
                            pl.write(os.path.join(co, "commit.json"), {"epoch": 1})
                            st["commit"] = time.time()
                        elif time.time() - t_spawn[cid] > DEADLINE_S:
                            pl.write(os.path.join(co, "abort.json"), {"why": "prepare 逾時：%s 沒到" % sorted(set(cs["roles"]) - ready)})
                            st["abort"] = time.time()
                    elif st["commit"] and st["abort"] is None and any(x["ev"] == "exit" for x in g):
                        pl.write(os.path.join(co, "abort.json"), {"why": "有成員結束了，整組取消"})
                        st["abort"] = time.time()
                elif cid == "crash-naive" and st["cancel"] is None and any(x["ev"] == "exit" and x.get("code") == 1 for x in g):
                    st["cancel"] = time.time()
                    for x in g:
                        if x["ev"] == "start" and x["role"] != "b":
                            pl.write(os.path.join(pl.aos7_task.task_dir(sp.path(x["node"]), x["tid"]), "ctl.json"),
                                     {"op": "kill", "by": "probe:kernel", "why": "b 掛了，整組取消"})
            time.sleep(0.01)
        for cs in cases.values():
            for nid, _ in cs["spawn"]:
                sp.ctl("pause", node=nid)
        time.sleep(0.4)

        res = {}
        for cid, cs in cases.items():
            g = pl.fs.read_jsonl(os.path.join(sp.root, "cohorts", cid, "gang.jsonl"))
            t_stop = time.time()
            life = {}            # tid -> [role, start, end]
            for x in g:
                if x["ev"] == "start":
                    life[x["tid"] + "@" + x["node"]] = [x["role"], x["t"], t_stop]
                elif x["ev"] in ("exit", "dup-exit", "abort-exit"):
                    k = x["tid"] + "@" + x["node"]
                    if k in life:
                        life[k][2] = x["t"]
            works = [x for x in g if x["ev"] == "work"]
            partial = dup = 0
            for w in works:
                alive = [v[0] for v in life.values() if v[1] <= w["t"] < v[2]]
                if not set(cs["roles"]) <= set(alive):
                    partial += 1
                workers = {x["tid"] for x in works if x["role"] == w["role"] and abs(x["t"] - w["t"]) < 0.25}
                if len(workers) > 1:
                    dup += 1
            starts = {}
            for x in g:
                if x["ev"] == "start":
                    starts.setdefault(x["role"], []).append(x["t"])
            firsts = [min(v) for v in starts.values()]
            res[cid] = {"起的角色": len(starts), "要的角色": len(cs["roles"]),
                        "起了兩份的角色": sum(1 for v in starts.values() if len(v) > 1),
                        "work 步數": len(works), "成組不完整時的 work": partial, "同角色兩份同時 work": dup,
                        "起動時間差 ms": round((max(firsts) - min(firsts)) * 1000) if firsts else None,
                        "dup-exit": sum(1 for x in g if x["ev"] == "dup-exit"),
                        "abort-exit": sum(1 for x in g if x["ev"] == "abort-exit")}
            if cs["mode"] == "proto":
                st = state[cid]
                res[cid]["commit"] = st["commit"] is not None
                res[cid]["abort"] = st["abort"] is not None
                first_work = min((x["t"] for x in works), default=None)
                res[cid]["第一步 work 在 commit 之後"] = first_work is None or (st["commit"] is not None and first_work >= st["commit"])
            if cid == "crash-naive" and state[cid]["cancel"]:
                c0 = state[cid]["cancel"]
                ends = [v[2] for v in life.values() if v[0] != "b"]
                res[cid]["探針寫 kill → 其餘成員都結束 ms"] = round((max(ends) - c0) * 1000) if ends else None
            if cid in killed:
                k = dict(killed[cid])
                tn = sp.path(k.pop("nid"))
                k["永遠 born 的資料夾（有 birth、沒 runner.json／pid.json）"] = sorted(
                    t for t in sp.tasks(cid) if pl.aos7_task.task_state(pl.aos7_task.task_dir(tn, t)) == "born")
                res[cid].update(k)
            r.measure(cid, res[cid])
            tasks_err = [x.get("tasks_error") for nid, _ in cs["spawn"] for x in sp.rounds(nid) if x.get("tasks_error")]
            if tasks_err:
                r.measure(cid + "：tasks_error", tasks_err[0])

        n, p = res["bad-naive"], res["bad-proto"]
        r.check("bad／naive：壞的那項被跳過、其他兩個照起（現行：batch 不是全有全無）", n["起的角色"] == 2, n)
        r.check("bad／proto：judge 沒到 → prepare 逾時 abort，零步 work", p["abort"] and p["work 步數"] == 0, p)
        n, p = res["keepblock-naive"], res["keepblock-proto"]
        r.check("keepblock／naive：judge 被 keep 擋下，a、b 照起", n["起的角色"] == 2, n)
        r.check("keepblock／proto：零步 work", p["work 步數"] == 0, p)
        p = res["tickkill-proto"]
        r.check("tickkill／proto：同一角色不會兩份都做（O_EXCL 認領）", p["同角色兩份同時 work"] == 0, p)
        n, p = res["crash-naive"], res["crash-proto"]
        r.check("crash／proto：b 掛了之後整組 abort", p["abort"] and p["abort-exit"] == 2, p)
        r.check("cross／proto：所有 work 都在 commit 之後", res["cross-proto"]["第一步 work 在 commit 之後"], res["cross-proto"])
        r.check("proto 全部情境：成組不完整時的 work 0",
                all(res[c]["成組不完整時的 work"] == 0 for c in res if c.endswith("proto")),
                {c: res[c]["成組不完整時的 work"] for c in res if c.endswith("proto")})
        r.finding("spawn batch 只保證『同一回合依序起』：壞項、keep／max_live 擋下的項只跳過那項，tasks_error 記在回合總結，"
                  "成員自己不知道少了誰（E-04）")
        r.finding("tick 起到一半被殺：spawn 檔起完才刪（I-02 的至少一次），下一個 tick 整批再起，已起的角色變兩份")
        r.finding("一起取消只能逐個寫 task ctl.json，到下一個 tick／tock 才執行；跨 node 的成員各等各的回合")
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
