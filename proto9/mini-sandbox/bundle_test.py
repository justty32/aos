#!/usr/bin/env python3
"""Tests for kernel bundles (a name that is a folder whose _chain.json lists more names) and the fixed per-kernel cell (name, layer, status, from) and the read-only lock on the declarations: expansion order, a bundle inside a bundle, loops and too deep refused, bundles mixed with single names, a file and a bundle of the same name refused, the auto mask and KernelOrderBad after expanding, .aos/kernels and the cells agreeing, the agent trying to undo the lock (as itself and from a namespace of its own), the live status files; PASS/FAIL/info lines."""

import sys

sys.dont_write_bytecode = True  # before importing accept: keep the repo free of __pycache__

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import time  # noqa: E402

import accept as A  # noqa: E402  (test servers)
import stack_test as S  # noqa: E402  (mini runner, snapshot, check_argv, record)

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.expanduser("~/.aos/scratch/proto9-mini-1127/bundle")
HOST = "169.254.77.1"
RESULTS = S.RESULTS
record = S.record
log = S.log


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)


def kernel(name, program, config):
    write_json(os.path.join(BASE, "kernels", name + ".json"), {"description": "test " + name, "program": program,
                                                               "config": config})


def bundle(name, chain):
    write_json(os.path.join(BASE, "kernels", name, "_chain.json"), {"description": "test bundle " + name,
                                                                    "chain": chain})


def make_kernels(pa):
    kernel("t/cg", "cg_kernel.py", {"cpu": "20%", "mem": "200M", "pids": 40})
    kernel("t/net-a", "net_kernel.py", {"host_ports": [pa]})
    bundle("t/nest", ["aos/base", "net"])                     # a bundle inside a bundle, plus one of its own
    kernel("t/nest/net", "net_kernel.py", {"host_ports": [pa]})
    bundle("t/loop-a", ["t/loop-b"])
    bundle("t/loop-b", ["t/loop-a"])
    bundle("t/self", ["t/self"])
    for i in range(1, 10):                                   # t/d1 -> t/d2 -> ... -> t/d9 -> a mask: 9 bundles deep
        bundle("t/d%d" % i, ["t/d%d" % (i + 1)] if i < 9 else ["aos/mask/run-user"])
    kernel("t/clash", "cg_kernel.py", {"cpu": "50%"})         # t/clash.json and t/clash/ with a _chain.json
    bundle("t/clash", ["aos/mask/ssh"])
    bundle("t/cgonly", ["cg"])                                # only a cgroup kernel: mini adds the mask after expanding
    kernel("t/cgonly/cg", "cg_kernel.py", {"cpu": "20%", "mem": "200M", "pids": 40})
    bundle("t/badorder", ["up", "net"])                       # llm then a net kernel that lets its upstream through
    kernel("t/badorder/up", "llm_kernel.py", {"upstream": "http://127.0.0.1:%d/v1" % pa, "models": ["m"], "limit": 1})
    kernel("t/badorder/net", "net_kernel.py", {"host_ports": [pa]})


def dirs_now():
    return sorted(d for d in os.listdir("/tmp") if d.startswith("aos-mini-"))


def layers(out):
    return [l[len("# layer "):].split("  (file ")[0] for l in out.splitlines() if l.startswith("# layer ")]


def refused(name, kernels, code, want_in_err, flags=()):
    """A name that must be refused before anything runs: exit 2, the error code, nothing started."""
    marker = os.path.join(BASE, name + ".ran")
    before = dirs_now()
    r = S.mini(name.replace("_", "-"), kernels, ["sh", "-c", "touch %s" % marker], flags=flags)
    last = (r.err.strip().splitlines() or ["-"])[-1]
    ok = r.rc == 2 and code in last and all(w in last for w in want_in_err) and not os.path.exists(marker) and \
        dirs_now() == before and (not flags or not r.out.strip())
    record(name, ok, "[%s%s] exit %s, ran: %s; %s" % (",".join(kernels), " " + " ".join(flags) if flags else "", r.rc,
                                                      os.path.exists(marker), last[:260]))


def lock_ok(j, prefix=""):
    """Every attempt on the declarations failed, both as the agent and from a namespace of its own (covering it
    with a tmpfs there is fine: only its own view), and nothing changed."""
    bad = []
    for where in ("lock_agent", "lock_nested"):
        for k, v in (j.get(where) or {"missing": "ok"}).items():
            if v == "ok" and k not in ("open_tree_clone", "clone_move_mount", "cover_with_tmpfs", "cover_then_write"):
                bad.append("%s %s" % (where[5:], k))
    if not j.get("lock_unchanged"):
        bad.append("changed: %s" % j.get("lock_changed"))
    return bad


def cells_match(j):
    """For each kind, its cell is the innermost line of that kind in .aos/kernels: same name, layer = line number,
    same from."""
    lines = j.get("lock_kernels") or []
    bad = []
    for kind, cell in (j.get("lock_cells") or {}).items():
        nums = [i + 1 for i, l in enumerate(lines) if l.split()[0] == kind]
        if not nums:
            bad.append("%s: no line" % kind)
            continue
        n = nums[-1]
        parts = lines[n - 1].split()
        frm = parts[3] if len(parts) > 3 and parts[2] == "from" else None
        if cell.get("layer") != str(n) or cell.get("name") != parts[1] or cell.get("from") != frm:
            bad.append("%s: cell %s vs line %d %r" % (kind, cell, n, lines[n - 1]))
    return bad


def escape_env():
    return ["env", "XDG_RUNTIME_DIR=%s" % os.environ.get("XDG_RUNTIME_DIR", ""),
            "DBUS_SESSION_BUS_ADDRESS=%s" % os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")]


def expansion(pa):
    log("\n== f. bundles: how names expand")
    want = ["cgroup aos/base/cg from aos/base", "mask aos/base/mask from aos/base", "llm aos/llm/fake from aos/base"]
    before = dirs_now()
    r = S.mini("f-dry", ["aos/base"], ["true"], flags=("--dry-run",))
    got = layers(r.out)
    record("f_expand_dry", r.rc == 0 and got == ["%d: %s" % (i + 1, w) for i, w in enumerate(want)] and
           r.out.count("  (file ") == 3 and "added aos/mask" not in r.err and dirs_now() == before,
           "[aos/base --dry-run] layers %s; a file on each: %s; auto mask: %s (its own mask covers /run/user)" % (
               got, r.out.count("  (file "), "added aos/mask" in r.err))
    r = S.mini("f-nested-dry", ["t/nest"], ["true"], flags=("--dry-run",))
    want_n = ["cgroup aos/base/cg from t/nest>aos/base", "mask aos/base/mask from t/nest>aos/base",
              "llm aos/llm/fake from t/nest>aos/base", "net t/nest/net from t/nest"]
    got = layers(r.out)
    record("f_nested_dry", r.rc == 0 and got == ["%d: %s" % (i + 1, w) for i, w in enumerate(want_n)],
           "[t/nest = aos/base + its own net] layers %s" % got)
    refused("f_loop", ["t/loop-a"], "KernelBundleLoop", ["t/loop-a -> t/loop-b -> t/loop-a"])
    refused("f_loop_self", ["t/self"], "KernelBundleLoop", ["t/self -> t/self"])
    refused("f_too_deep", ["t/d1"], "KernelBundleTooDeep", ["more than 8", "t/d1 -> t/d2", "t/d9"])
    r = S.mini("f-depth8", ["t/d2"], ["true"], flags=("--dry-run",))
    got = layers(r.out)
    record("f_depth_8_ok", r.rc == 0 and got == ["1: mask aos/mask/run-user from " + ">".join(
        "t/d%d" % i for i in range(2, 10))], "[t/d2, 8 bundles deep --dry-run] exit %s, layers %s" % (r.rc, got))
    refused("f_clash", ["t/clash"], "KernelNameClash", ["t/clash.json", "t/clash/", "rename"])
    refused("f_clash_dry", ["t/clash"], "KernelNameClash", ["rename"], flags=("--dry-run",))
    refused("f_order_bad_expanded", ["t/badorder"], "KernelOrderBad", ["t/badorder/net (from t/badorder)",
                                                                       "t/badorder/up (from t/badorder)"])
    refused("f_order_bad_expanded_dry", ["t/badorder"], "KernelOrderBad", ["t/badorder/net"], flags=("--dry-run",))


def runs(pa):
    log("\n== f. bundles that run; the cells and the lock")
    spec = {"tcp": [[HOST, pa]], "llm": {"posts": 1}, "lock": {"status_wait": 2.5}}
    r = S.mini("f-nested-run", ["t/nest"], S.check_argv(spec), timeout=120)
    j = r.j or {}
    want = ["cgroup aos/base/cg from t/nest>aos/base", "mask aos/base/mask from t/nest>aos/base",
            "llm aos/llm/fake from t/nest>aos/base", "net t/nest/net from t/nest"]
    a = j.get("tcp %s:%d" % (HOST, pa))
    record("f_nested_run", j.get("lock_kernels") == want and a == "ok" and j.get("llm_codes") == [200] and
           "added aos/mask" not in r.err,
           "[t/nest] .aos/kernels %s; A %s; brain %s; exit %s %s" % (j.get("lock_kernels"), a, j.get("llm_codes"),
                                                                     r.rc, r.err.strip()[-200:] if not j else ""))
    bad = cells_match(j)
    record("f_cells_match", bool(j) and not bad, "cells %s%s" % (j.get("lock_cells"), "; " + "; ".join(bad) if bad
                                                                  else ""))
    bad = lock_ok(j)
    record("g_lock_bundle", bool(j) and not bad, "agent: %s; own ns: %s; unchanged %s%s" % (
        j.get("lock_agent"), j.get("lock_nested"), j.get("lock_unchanged"), "; FAILED: " + ", ".join(bad) if bad else ""))
    live = j.get("lock_live") or {}
    heads = {k: v["before"][:2] for k, v in live.items()}
    ok = set(live) == {"llm", "net"} and all(v["moved"] and v["before"][0] == "state: running" and
                                              v["before"][1].startswith("updated: ") for v in live.values())
    ok = ok and live["llm"]["after"][2] != live["llm"]["before"][2]
    record("g_status_live", ok, "first lines %s; llm %s -> %s; net updated %s -> %s (read-only for the agent, still "
           "kept up to date from outside)" % (heads, live.get("llm", {}).get("before", ["", "", ""])[2],
                                              live.get("llm", {}).get("after", ["", "", ""])[2],
                                              live.get("net", {}).get("before", ["", ""])[1][9:],
                                              live.get("net", {}).get("after", ["", ""])[1][9:]))

    r = S.mini("f-mixed", ["aos/base", "t/net-a", "aos/mask/ssh"], S.check_argv({"tcp": [[HOST, pa]],
                                                                                  "llm": {"posts": 1}, "lock": {}}))
    j = r.j or {}
    want = ["cgroup aos/base/cg from aos/base", "mask aos/base/mask from aos/base", "llm aos/llm/fake from aos/base",
            "net t/net-a", "mask aos/mask/ssh"]
    a = j.get("tcp %s:%d" % (HOST, pa))
    bad = cells_match(j)
    record("f_mixed", j.get("lock_kernels") == want and a == "ok" and j.get("llm_codes") == [200] and not bad,
           "[aos/base,t/net-a,aos/mask/ssh] .aos/kernels %s; A %s; brain %s; cells %s" % (
               j.get("lock_kernels"), a, j.get("llm_codes"), "match" if not bad else bad))

    unit = "mini-bdl-auto-%d.service" % os.getpid()
    r = S.mini("f-auto-mask", ["t/cgonly"], escape_env() + S.check_argv(
        {"escape": [unit, os.path.join(BASE, "auto.escape")], "lock": {}}))
    j = r.j or {}
    blocked = not str(j.get("escape_busctl", "rc 0")).startswith("rc 0")
    want = ["cgroup t/cgonly/cg from t/cgonly", "mask aos/mask/run-user"]
    record("f_auto_mask_expanded", "added aos/mask/run-user" in r.err and j.get("lock_kernels") == want and blocked,
           "[t/cgonly = its cg only] mini added the mask: %s; .aos/kernels %s; escape %s (busctl %s)" % (
               "added aos/mask/run-user" in r.err, j.get("lock_kernels"), "blocked" if blocked else "OPEN",
               str(j.get("escape_busctl"))[:50]))
    S.escape_stop(unit)


def lock_more():
    log("\n== g. the read-only lock without kernels, with uid 1, and with the way out left open")
    r = S.mini("g-lock-none", [], S.check_argv({"lock": {}}))
    j = r.j or {}
    bad = lock_ok(j)
    record("g_lock_no_kernels", bool(j) and not bad and j.get("lock_kernels") == [],
           "[no --kernels: the innermost step locks 0-root itself] agent: %s; own ns: %s%s" % (
               j.get("lock_agent"), j.get("lock_nested"), "; FAILED: " + ", ".join(bad) if bad else ""))
    r = S.mini("g-lock-uid", ["aos/base-low", "aos/uid/1"], S.check_argv({"lock": {}}))
    j = r.j or {}
    bad = lock_ok(j)
    record("g_lock_uid1", bool(j) and not bad and j.get("uid") == 1,
           "[aos/base-low,aos/uid/1] uid %s; agent: %s%s" % (j.get("uid"), j.get("lock_agent"),
                                                              "; FAILED: " + ", ".join(bad) if bad else ""))
    unit = "mini-bdl-esc-%d.service" % os.getpid()
    r = S.mini("g-lock-escape", ["t/cg"], escape_env() + S.check_argv({"lock": {"escape_unit": unit}}),
               flags=("--no-auto-mask",))
    j = r.j or {}
    e = j.get("lock_escape") or {}
    through = "pwned from outside" in " ".join(e.get("kernels_now", []))
    record("g_lock_escape_no_mask", True, "[t/cg --no-auto-mask] inside: %s; out through D-Bus (%s), a process "
           "outside appended to .aos/kernels: %s" % ("held" if not lock_ok(j) else "BROKEN", e.get("busctl", "-")[:40],
                                                    "YES, the lock does not cover that way" if through else "no"),
           must=False)
    S.escape_stop(unit)


def main():
    ap = argparse.ArgumentParser(description="Tests for kernel bundles, the per-kernel cells and the read-only lock.")
    ap.add_argument("--pasta", help="pasta binary (default: on PATH, else %s)" % A.DEFAULT_PASTA)
    ap.add_argument("--keep", action="store_true", help="keep %s afterwards" % BASE)
    a = ap.parse_args()
    pasta = a.pasta or shutil.which("pasta") or A.DEFAULT_PASTA
    if not os.access(pasta, os.X_OK):
        sys.exit("bundle_test: error: PastaMissing no pasta at %s (install passt, or --pasta PATH)" % pasta)
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE)
    S.BASE = BASE  # S.mini runs in BASE by default
    os.environ["MINI_PASTA"] = pasta
    os.environ["MINI_KERNELS_PATH"] = os.path.join(BASE, "kernels")
    os.environ["AOS_HOME"] = S.AOS_HOME
    os.environ.pop("AOS_ENV", None)
    srv = A.start_server()
    pa = srv.server_address[1]
    before = S.snapshot((pa,))
    log("test server on the host: A 127.0.0.1:%d (inside %s:%d)" % (pa, HOST, pa))
    make_kernels(pa)
    t0 = time.monotonic()
    try:
        expansion(pa)
        runs(pa)
        lock_more()
    finally:
        srv.shutdown()
        srv.server_close()
    time.sleep(1)
    after = S.snapshot((pa,))
    left = {k: (sorted(set(after[k]) - set(before[k])) if k != "procs" else
                {p: c for p, c in after[k].items() if p not in before[k]}) for k in after}
    probes = [d for d in os.listdir("/tmp") if d.startswith("aos-probe-")]
    open_port = socket.socket().connect_ex(("127.0.0.1", pa)) == 0
    record("cleanup", not any(left.values()) and not probes and not open_port,
           "left over: %s; probe folders %s; test server open: %s" % (
               {k: v for k, v in left.items() if v} or "nothing", probes or "none", open_port))
    fails = [n for n, t in RESULTS if t == "FAIL"]
    log("\nSUMMARY %s (%d PASS, %d FAIL, %d info, %.0fs)%s" % (
        "ok" if not fails else "FAILED", sum(t == "PASS" for _, t in RESULTS), len(fails),
        sum(t == "info" for _, t in RESULTS), time.monotonic() - t0, ": " + ", ".join(fails) if fails else ""))
    if not a.keep and not fails:
        shutil.rmtree(BASE, ignore_errors=True)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
