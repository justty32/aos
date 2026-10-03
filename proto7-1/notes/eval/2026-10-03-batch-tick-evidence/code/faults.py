#!/usr/bin/env python3
"""故障面實驗：一條線出事，同 daemon 其他線受不受影響（原樣 vs 批次）。"""
import ctypes, datetime, json, os, pathlib, shutil, signal, statistics, subprocess, sys, time
SP = pathlib.Path(__file__).resolve().parent
P71 = SP / "p71"
N = 20

def dump(p, o):
    p.parent.mkdir(parents=True, exist_ok=True); t = p.parent / (".t." + p.name); t.write_text(json.dumps(o) + "\n"); os.replace(t, p)

def ts(s): return datetime.datetime.fromisoformat(s).timestamp()

def kill_mine(root):
    key = str(root).encode()
    for d in pathlib.Path("/proc").iterdir():
        if not d.name.isdigit() or int(d.name) == os.getpid(): continue
        try:
            if key in (d / "cmdline").read_bytes() or key in (d / "environ").read_bytes(): os.kill(int(d.name), signal.SIGKILL)
        except OSError: pass

def reap():
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError: return
        if pid == 0: return

def setup(root, scen):
    for i in range(N):
        b = root / ("n%03d" % i) / ".aos"
        dump(b / "timeline.json", {"interval_ms": 100})
        tasks = []
        if scen == "sigterm-ignorer" and i == 0:
            tasks = [{"name": "stubborn", "mode": "keep", "argv": ["sh", "-c", "trap '' TERM; while :; do sleep 0.2; done"]}]
        dump(b / "tasks.json", {"tasks": tasks})
    bad = root / "n000" / ".aos"
    if scen == "stuck-io":
        pass   # 起跑後才把 round.json 換成 FIFO
    if scen == "heavy-history":
        td = bad / "tasks"
        for k in range(4000):
            d = td / ("old-r%d" % k); d.mkdir(parents=True)
            for f, o in (("birth.json", {"tid": d.name, "name": "old"}), ("exit.json", {"code": 0}), ("ended.json", {"round": 1})):
                (d / f).write_text(json.dumps(o))
    if scen == "py-exception":
        (bad / "spawn" / "x.json").mkdir(parents=True)   # tick 的 os.remove 對資料夾丟 IsADirectoryError

def run(mode, scen, k=0, par=1, seconds=8):
    ctypes.CDLL(None).prctl(36, 1, 0, 0, 0)
    root = SP / "runs" / ("f-%s-%s-%d" % (mode, scen, os.getpid()))
    shutil.rmtree(root, ignore_errors=True)
    setup(root, scen)
    env = dict(os.environ, AOS7_EVAL_MODE=mode, AOS7_BATCH_K=str(k), AOS7_BATCH_PAR=str(par))
    err = open(SP / "runs" / ("f-%s-%s.stderr" % (mode, scen)), "w")
    p = subprocess.Popen([sys.executable, str(P71 / "bin" / "aos7-daemon"), str(root)], env=env, stdout=err, stderr=err)
    t0 = time.time(); m0 = time.monotonic(); events = []; nxt = m0 + 1.0
    fifo_done = False
    while time.monotonic() - m0 < seconds:
        reap()
        now = time.monotonic()
        if scen == "stuck-io" and not fifo_done and now - m0 > 1.5:
            rp = root / "n000" / ".aos" / "round.json"
            tmp = root / "n000" / ".aos" / "fifo"
            os.mkfifo(tmp); os.replace(tmp, rp); fifo_done = True; events.append(("fifo", time.time()))
        if scen == "sigterm-ignorer" and now >= nxt:
            td = root / "n000" / ".aos" / "tasks"
            for tid in sorted(os.listdir(td)) if td.exists() else []:
                if not (td / tid / "exit.json").exists() and (td / tid / "pid.json").exists() and not (td / tid / "ctl.json").exists() and not (td / tid / "ctl-done.json").exists():
                    dump(td / tid / "ctl.json", {"op": "kill", "by": "fault"}); events.append(("kill", time.time())); break
            nxt = now + 1.0
        if scen == "kill9-action" and now >= nxt and now - m0 > 1.5:
            # 對正在跑的 tick（或批次）程序送 SIGKILL，一次
            for d in pathlib.Path("/proc").iterdir():
                if not d.name.isdigit(): continue
                try: cl = (d / "cmdline").read_bytes()
                except OSError: continue
                if str(root).encode() in cl and (b"aos7-tick" in cl or (b"aos7-batch" in cl and b"aos7-tick" in cl)):
                    os.kill(int(d.name), signal.SIGKILL); events.append(("kill9", time.time(), cl.split(b"\0")[-2].decode() if b"aos7-tick\0" in cl else "batch")); break
            if any(e[0] == "kill9" for e in events): nxt = 1e18
            else: nxt = now + 0.001
        time.sleep(0.001 if scen == "kill9-action" else 0.02)
    t1 = time.time()
    p.send_signal(signal.SIGTERM)
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill(); p.wait()
    kill_mine(root); time.sleep(0.2); reap()
    ticks, errs = {}, {}
    for line in open(root / ".aosd" / "log.jsonl"):
        try: e = json.loads(line)
        except ValueError: continue
        if e.get("ev") in ("tick", "tock"):
            if e.get("rc"): errs[e["node"]] = errs.get(e["node"], 0) + 1
            if e["ev"] == "tick": ticks.setdefault(e["node"], []).append(ts(e["at"]))
    # 出事之後（第 2 秒起）其他線的回合間隔
    cut = t0 + 2.0
    others = ["n%03d" % i for i in range(1, N)]
    iv = []
    for n in others:
        xs = [x for x in ticks.get(n, []) if x >= cut]
        iv += [(b - a) * 1000 for a, b in zip(xs, xs[1:])]
    after = {n: len([x for x in ticks.get(n, []) if x >= cut]) for n in ["n000"] + others}
    stalled = [n for n in others if after[n] == 0]
    iv.sort()
    res = {"mode": mode, "k": k, "par": par, "scen": scen, "seconds_after_fault": round(t1 - cut, 1),
           "bad_node_ticks_after": after["n000"], "others_ticks_after": {"min": min(after[n] for n in others), "p50": statistics.median(after[n] for n in others), "max": max(after[n] for n in others)},
           "others_stalled": len(stalled), "others_interval_ms": {"p50": round(statistics.median(iv), 1) if iv else None, "p95": round(iv[int(len(iv) * .95)], 1) if iv else None, "max": round(iv[-1], 1) if iv else None},
           "nodes_with_action_errors": {n: c for n, c in errs.items()}, "events": [list(map(str, e)) for e in events], "daemon_rc": p.returncode}
    print(json.dumps(res, ensure_ascii=False), flush=True)
    shutil.rmtree(root, ignore_errors=True)
    return res

if __name__ == "__main__":
    out = []
    for scen in sys.argv[1].split(","):
        for mode, k, par in (("base", 0, 1), ("bboth", 0, 1), ("bboth", 4, 4)):
            out.append(run(mode, scen, k, par))
    json.dump(out, open(SP / "ev" / ("faults-%s.json" % sys.argv[2]), "w"), ensure_ascii=False, indent=1)
