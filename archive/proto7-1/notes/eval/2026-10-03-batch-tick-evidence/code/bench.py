#!/usr/bin/env python3
"""批次 tick 評估 harness（scratchpad 用）。
python3 bench.py --mode base --count 100 --work each3 --seconds 15 [--k 0 --par 1] --out ev/xxx.json
"""
import argparse, ctypes, datetime, json, os, pathlib, resource, shutil, signal, statistics, subprocess, sys, time

SP = pathlib.Path(__file__).resolve().parent
P71 = SP / "p71"

def dump(p, o):
    p.parent.mkdir(parents=True, exist_ok=True); t = p.parent / (".t." + p.name); t.write_text(json.dumps(o, ensure_ascii=False, indent=1) + "\n"); os.replace(t, p)

def st(xs):
    if not xs: return {"n": 0}
    x = sorted(xs)
    return {"n": len(x), "p50": round(statistics.median(x), 1), "p95": round(x[min(len(x)-1, int(len(x)*.95))], 1), "max": round(x[-1], 1)}

def cpu_busy():
    v = [int(a) for a in open("/proc/stat").readline().split()[1:]]
    idle = v[3] + v[4]
    return sum(v) - idle, sum(v)

def ts(s):
    return datetime.datetime.fromisoformat(s).timestamp()

def mine(root):
    out = []
    key = str(root).encode()
    for d in pathlib.Path("/proc").iterdir():
        if not d.name.isdigit() or int(d.name) == os.getpid(): continue
        try:
            if key in (d / "cmdline").read_bytes() or key in (d / "environ").read_bytes(): out.append(int(d.name))
        except OSError: pass
    return out

def reap():
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0: return

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--mode", default="base"); a.add_argument("--count", type=int, default=50)
    a.add_argument("--work", default="each3"); a.add_argument("--seconds", type=float, default=15)
    a.add_argument("--k", type=int, default=0); a.add_argument("--par", type=int, default=1)
    a.add_argument("--interval", type=int, default=100); a.add_argument("--out", required=True)
    a.add_argument("--keepers", type=int, default=5)
    args = a.parse_args()
    ctypes.CDLL(None).prctl(36, 1, 0, 0, 0)   # subreaper：孤兒 runner／任務的 CPU 也算進來
    root = SP / "runs" / ("%s-%s-%d-%d" % (args.mode, args.work, args.count, os.getpid()))
    if root.exists(): shutil.rmtree(root)
    for i in range(args.count):
        b = root / ("n%03d" % i) / ".aos"
        dump(b / "timeline.json", {"interval_ms": args.interval})
        tasks = [{"name": "p%d" % j, "mode": "each", "argv": ["/bin/sleep", "0.01"]} for j in range(3)] if args.work == "each3" else []
        if i < args.keepers:
            tasks.append({"name": "keeper", "mode": "keep", "argv": ["/bin/sleep", "1000"]})
        dump(b / "tasks.json", {"tasks": tasks})
    env = dict(os.environ, AOS7_EVAL_MODE=args.mode, AOS7_BATCH_K=str(args.k), AOS7_BATCH_PAR=str(args.par),
               AOS7_CFLOOR_BIN=str(SP / "ctick"), AOS7_BATCH_STATS=str(root / "batch-stats.jsonl"))
    env.pop("AOS7_AUDIT", None)
    u0 = resource.getrusage(resource.RUSAGE_CHILDREN); c0 = cpu_busy()
    t0 = time.time(); m0 = time.monotonic()
    err = open(root / "daemon.stderr", "w")
    p = subprocess.Popen([sys.executable, str(P71 / "bin" / "aos7-daemon"), str(root)], env=env, stdout=err, stderr=err)
    sent_d, sent_t = [], []
    nxt = m0 + 1; k = 0
    while time.monotonic() - m0 < args.seconds:
        reap()
        if time.monotonic() >= nxt:
            k += 1
            dump(root / ".aosd" / "ctl" / ("probe-%03d.json" % k), {"op": "rescan", "by": "bench", "sent": time.time()})
            sent_d.append("probe-%03d.json" % k)
            # 任務 ctl：殺一個 keeper（tick 處理）
            if args.keepers:
                nd = root / ("n%03d" % (k % args.keepers)) / ".aos" / "tasks"
                try:
                    for tid in sorted(os.listdir(nd)):
                        if tid.startswith("keeper") and not (nd / tid / "exit.json").exists() and not (nd / tid / "ctl-done.json").exists() and (nd / tid / "pid.json").exists():
                            dump(nd / tid / "ctl.json", {"op": "kill", "by": "bench", "sent": time.time()})
                            sent_t.append(str(nd / tid)); break
                except OSError: pass
            nxt = time.monotonic() + 1
        time.sleep(0.05)
    t1 = time.time(); c1 = cpu_busy()
    p.send_signal(signal.SIGTERM)
    try: p.wait(timeout=60)
    except subprocess.TimeoutExpired: p.kill(); p.wait()
    time.sleep(0.3)
    for pid in mine(root):
        try: os.kill(pid, signal.SIGKILL)
        except OSError: pass
    time.sleep(0.2); reap()
    u1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    # 分析
    ticks = {}
    errs = 0
    for line in open(root / ".aosd" / "log.jsonl"):
        try: e = json.loads(line)
        except ValueError: continue
        if e.get("ev") in ("tick", "tock") and e.get("rc"): errs += 1
        if e.get("ev") == "tick":
            t = ts(e["at"])
            if t <= t1: ticks.setdefault(e["node"], []).append(t)
    ivs = []
    for n, xs in ticks.items(): ivs += [(b - a) * 1000 for a, b in zip(xs, xs[1:])]
    per = [len(ticks.get("n%03d" % i, [])) for i in range(args.count)]
    dctl = []
    for n in sent_d:
        d = json.load(open(root / ".aosd" / "ctl-done" / n)) if (root / ".aosd" / "ctl-done" / n).exists() else None
        if d: dctl.append((ts(d["result"]["at"]) - d["sent"]) * 1000)
    tctl = []; tctl_lost = 0
    for tdp in sent_t:
        f = pathlib.Path(tdp) / "ctl-done.json"
        if f.exists():
            d = json.load(open(f))
            if "sent" in d: tctl.append((ts(d["result"]["at"]) - d["sent"]) * 1000)
            else: tctl_lost += 1
        else: tctl_lost += 1
    win = t1 - t0
    bstats = [json.loads(l) for l in open(root / "batch-stats.jsonl")] if (root / "batch-stats.jsonl").exists() else []
    bs = {}
    for b in bstats:
        bs.setdefault(b["prog"], []).append(b)
    res = {"mode": args.mode, "k": args.k, "par": args.par, "work": args.work, "count": args.count, "window_s": round(win, 2),
           "rounds_total": sum(per), "rounds_per_s": round(sum(per) / win, 1),
           "ticks_per_node": {"min": min(per), "p50": statistics.median(per), "max": max(per)},
           "interval_ms": st(ivs), "daemon_ctl_ms": st(dctl), "task_ctl_ms": st(tctl), "task_ctl_unanswered": tctl_lost,
           "cpu_cores_rusage": round(((u1.ru_utime + u1.ru_stime) - (u0.ru_utime + u0.ru_stime)) / (time.time() - t0), 2),
           "cpu_cores_system": round((c1[0] - c0[0]) / max(1, (c1[1] - c0[1])) * os.cpu_count(), 2),
           "action_rc_nonzero": errs, "daemon_rc": p.returncode, "load1_end": os.getloadavg()[0],
           "batch": {k2: {"n": len(v), "size": st([x["n"] for x in v]), "ms": st([x["ms"] for x in v])} for k2, v in bs.items()}}
    dump(pathlib.Path(args.out), res)
    print(json.dumps(res, ensure_ascii=False))
    shutil.rmtree(root, ignore_errors=True)

if __name__ == "__main__":
    main()
