#!/usr/bin/env python3
"""idle_cost.py [--root DAEMON_STACK] [--seconds N] [--json FILE] - how much CPU each aos-loop of a running tree costs (read only).

idle-polling 第 0 刀（使用者 11-24「閒置輪詢這塊就是乖乖用C++重寫」；規劃 thinking/2026-11/24/閒置輪詢C++重寫-1124/04 的「開工前」第 3 條）：
把 11-24 報告（wf/ws/eca-aos/eca-aos-core/report-1124.md 第 3 節）的量法包成常備腳本，每刀做完跑一次、數字記進 progress 的 idle-polling。

What it does: walks the daemon tables from --root down (procs_state.json, at most 5 levels) to name every row; finds every
running aos-loop (its pid, or the child of the aos-daemon whose pid is on a row); takes two snapshots of /proc/<pid>/stat
N seconds apart and prints, per loop, the cores its finished children used (cutime+cstime: the bodies it started each round)
plus its own (utime+stime). Groups by kind (eca, fsm, kernel, clock, sweeper, other: by the files in the row's def folder, see kind_of),
adds each aos-daemon's body (llm kernel, kernel station: the daemon's own children, kind daemon-body), and prints the
whole machine's busy cores and the aos-daemon processes' own share.

Reads only /proc/<pid>/{stat,cmdline} and the daemon tables; never environ, history, mailboxes or queues.
Limits: a body still running at the second snapshot is not counted yet (cutime counts children once they exit), so a busy
agent in a long round shows low; run it when the tree is idle, or read busy rows with that in mind. The script itself costs
almost nothing (two snapshots and a sleep).
Output: a TAB table (name, kind, cores) sorted by cost, a per-kind summary and the totals; --json FILE also writes everything.
Exit 0; 1 with "idle_cost: error: ..." when --root has no procs_state.json.
"""
import argparse
import collections
import json
import os
import sys
import time

TICK = os.sysconf("SC_CLK_TCK")
MAX_DEPTH = 5


def stat(pid):
    try:
        with open("/proc/%d/stat" % pid) as f:
            s = f.read()
    except OSError:
        return None
    f = s[s.rindex(")") + 2:].split()
    return {"comm": s[s.index("(") + 1:s.rindex(")")], "ppid": int(f[1]), "start": int(f[19]),
            "self": int(f[11]) + int(f[12]), "kids": int(f[13]) + int(f[14])}


def pids():
    return [int(x) for x in os.listdir("/proc") if x.isdigit()]


def rows_of(daemon):
    try:
        with open(os.path.join(daemon, "procs_state.json")) as f:
            procs = json.load(f).get("procs") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    if isinstance(procs.get("$ref"), list):
        merged = {}
        for ref in procs["$ref"]:
            try:
                with open(os.path.join(daemon, ref)) as f:
                    merged.update(json.load(f))
            except (OSError, ValueError):
                pass
        procs = merged
    return {n: r for n, r in procs.items() if isinstance(r, dict)}


def kind_of(name, row, daemon):
    """What kind of body: by the files in its definition folder (the row's def, relative to its daemon), not by names:
    cli.json = eca, fsm.json = fsm, kernel.json = kernel; _clock / _sweeper by name; a row whose stack is a daemon = daemon."""
    leaf = name.rsplit("/", 1)[-1]
    if leaf in ("_clock", "_sweeper"):
        return leaf.lstrip("_")
    d = row.get("def")
    if isinstance(d, str) and d:
        d = os.path.realpath(os.path.join(daemon, d))
        for f, kind in (("cli.json", "eca"), ("fsm.json", "fsm"), ("kernel.json", "kernel")):
            if os.path.isfile(os.path.join(d, f)):
                return kind
        return "other"
    return "daemon"


def names(root):
    """pid on a table row -> {name, kind}; walks into rows whose stack is a daemon."""
    out = {}

    def walk(daemon, prefix, depth):
        for name, row in rows_of(daemon).items():
            stack = os.path.realpath(os.path.join(daemon, str(row.get("stack") or "").split("#")[0]))
            full = prefix + name
            if isinstance(row.get("pid"), int):
                out[row["pid"]] = {"name": full, "kind": kind_of(full, row, daemon)}
            if depth < MAX_DEPTH and os.path.isfile(os.path.join(stack, "procs_state.json")):
                walk(stack, full + "/", depth + 1)
    walk(root, "", 1)
    return out


def loops(table):
    """running aos-loop pid -> {name, kind}: a row's pid, or the aos-loop child of a row's aos-daemon wrapper."""
    found = {}
    for pid in pids():
        st = stat(pid)
        if not st or st["comm"] != "aos-loop":
            continue
        who = table.get(pid) or table.get(st["ppid"])
        found[pid] = dict(who) if who else {"name": "(not on a table: pid %d)" % pid, "kind": "unlisted"}
    return found


def cpu_line():
    with open("/proc/stat") as f:
        for line in f:
            if line.startswith("cpu "):
                return [int(x) for x in line.split()[1:]]
    return []


def main():
    ap = argparse.ArgumentParser(prog="idle_cost", description="CPU of each aos-loop of a running tree (read only).")
    ap.add_argument("--root", default=os.path.expanduser("~/aos-home/.stack"), help="the root daemon's stack (default ~/aos-home/.stack)")
    ap.add_argument("--seconds", type=float, default=60.0, help="how long to measure (default 60)")
    ap.add_argument("--json", help="also write the numbers to this file")
    o = ap.parse_args()
    root = os.path.realpath(os.path.expanduser(o.root))
    if not os.path.isfile(os.path.join(root, "procs_state.json")):
        print("idle_cost: error: no procs_state.json in %s (give the root daemon's stack with --root)" % root, file=sys.stderr)
        return 1
    table = names(root)
    found = loops(table)
    daemons = [p for p in pids() if (stat(p) or {}).get("comm") == "aos-daemon"]
    a = {p: stat(p) for p in list(found) + daemons}
    c0, t0 = cpu_line(), time.time()
    time.sleep(o.seconds)
    b = {p: stat(p) for p in a}
    c1, dur = cpu_line(), time.time() - t0
    rows = []
    for pid, who in found.items():
        x, y = a.get(pid), b.get(pid)
        if not x or not y or x["start"] != y["start"]:
            continue                                        # gone or restarted meanwhile
        cores = (y["kids"] + y["self"] - x["kids"] - x["self"]) / TICK / dur
        rows.append(dict(who, pid=pid, cores=cores))
    for pid in daemons:                                     # a daemon with a body (llm kernel, kernel station): its body runs as its
        x, y = a.get(pid), b.get(pid)                       # child each round; long-lived children (the loops) only count once they exit
        if not x or not y or x["start"] != y["start"]:
            continue
        cores = (y["kids"] - x["kids"]) / TICK / dur
        if cores >= 0.005:
            who = table.get(pid) or {"name": "(daemon pid %d)" % pid}
            rows.append({"name": who["name"], "kind": "daemon-body", "pid": pid, "cores": cores})
    rows.sort(key=lambda r: -r["cores"])
    dcores = sum((b[p]["self"] - a[p]["self"]) / TICK / dur for p in daemons if a.get(p) and b.get(p))
    delta = [y - x for x, y in zip(c0, c1)]
    total = sum(delta) or 1
    busy = (total - delta[3] - (delta[4] if len(delta) > 4 else 0)) / total * (os.cpu_count() or 1)
    for r in rows:
        print("%s\t%s\t%.3f" % (r["name"], r["kind"], r["cores"]))
    groups = collections.OrderedDict()
    for r in rows:
        g = groups.setdefault(r["kind"], [0, 0.0])
        g[0] += 1
        g[1] += r["cores"]
    print()
    print("kind\tloops\tcores")
    for k, (n, c) in sorted(groups.items(), key=lambda kv: -kv[1][1]):
        print("%s\t%d\t%.2f" % (k, n, c))
    loops_total = sum(r["cores"] for r in rows if r["kind"] != "daemon-body")
    bodies = sum(r["cores"] for r in rows if r["kind"] == "daemon-body")
    print()
    print("measured %.1f s: %d aos-loop using %.2f cores; daemon bodies (kernels) %.2f cores; %d aos-daemon own %.2f cores; "
          "machine busy %.2f of %d cores" % (dur, sum(1 for r in rows if r["kind"] != "daemon-body"), loops_total, bodies,
                                             len(daemons), dcores, busy, os.cpu_count() or 1))
    if o.json:
        with open(o.json, "w") as f:
            json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "seconds": dur, "root": root, "loops": rows,
                       "kinds": {k: {"loops": n, "cores": c} for k, (n, c) in groups.items()},
                       "loops_cores": loops_total, "daemon_body_cores": bodies, "daemon_cores": dcores, "machine_busy_cores": busy,
                       "cpus": os.cpu_count()}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
