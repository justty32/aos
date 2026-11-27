#!/usr/bin/env python3
"""Entry of perf/: measures what kernels and file covers cost (fs, overlay, mountmax, flat, fuse, fusehang, sock, userns, cgdepth, mini, pisandbox), prints one JSON line per result (with machine, Linux version, commit, time) and a table for people."""
# usage:
#   python3 bench.py --quick                     # the small set, about a minute; mini only cg,mask x 1,5
#   python3 bench.py fs overlay                  # just these (full size)
#   python3 bench.py mini --kinds cg,mask,llm --layers 1,5,10
#   python3 bench.py --out results.jsonl all     # JSON lines appended to a file, table on stdout
# Standard library only, plus lat.c built with cc if there is one (else a Python timer, marked "timer": "python").
# No root: user namespaces (unshare -Urm), systemd --user scopes (cgdepth, mini). Leaves nothing behind: its temp
# folder /tmp/aos-perf-* is removed at the end (--keep keeps it).
import argparse
import json
import os
import shutil
import sys
import tempfile
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common  # noqa: E402
import dynbench  # noqa: E402
import fsbench  # noqa: E402
import minibench  # noqa: E402
import nsbench  # noqa: E402
import pisandbox  # noqa: E402

ALL = ["fs", "overlay", "flat", "fuse", "sock", "userns", "cgdepth", "mini", "pisandbox", "mountmax", "fusehang"]
QUICK = ["fs", "overlay", "flat", "fuse", "sock", "userns", "cgdepth", "mini", "pisandbox"]
HIDE = {"bench", "case", "n", "time", "host", "how", "load1", "comm", "stderr_first", "note", "timer", "quick"}


def fmt(v):
    if isinstance(v, float):
        return ("%.3g" % v) if abs(v) < 100 else "%.0f" % v
    if isinstance(v, (list, dict)):
        return json.dumps(v)[:40]
    return str(v)


def table(recs):
    """One block per bench: rows = cases, columns = what that bench measured."""
    lines, by = [], {}
    for r in recs:
        by.setdefault(r.get("bench", "?"), []).append(r)
    for b, rs in by.items():
        cols = []
        for r in rs:
            for k in r:
                if k not in HIDE and k not in cols:
                    cols.append(k)
        head = ["case", "n"] + cols
        rows = [[fmt(r.get("case", "")), fmt(r.get("n", ""))] + [fmt(r[c]) if c in r else "" for c in cols]
                for r in rs]
        w = [max(len(h), *(len(x[i]) for x in rows)) for i, h in enumerate(head)]
        lines.append("== %s" % b)
        lines.append("  ".join(h.ljust(w[i]) for i, h in enumerate(head)))
        for x in rows:
            lines.append("  ".join(c.ljust(w[i]) for i, c in enumerate(x)))
        lines.append("")
    return "\n".join(lines)


def remove(work):
    """rm -r, also through folders overlayfs leaves with mode 000 (its workdir/work)."""
    for dp, dns, _ in os.walk(work):
        for d in dns:
            try:
                os.chmod(os.path.join(dp, d), 0o700)
            except OSError:
                pass
    shutil.rmtree(work, ignore_errors=True)
    if os.path.exists(work):
        print("warning: could not remove all of %s" % work, file=sys.stderr)


def inner(argv):
    """bench.py _in NAME JSONARGS: the part of a bench that runs inside a namespace or a scope."""
    table_ = dict(fsbench.INNER, **dynbench.INNER, **nsbench.INNER)
    table_[argv[1]](json.loads(argv[2]))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "_in":
        return inner(sys.argv[1:])
    ap = argparse.ArgumentParser(description="Measure what aos kernels and file covers cost; JSON lines + a table.")
    ap.add_argument("what", nargs="*", help="benches: %s, or all (default: all but mountmax and fusehang; with "
                    "--quick: %s)" % (", ".join(ALL), ", ".join(QUICK)))
    ap.add_argument("--quick", action="store_true", help="small sizes, seconds per bench")
    ap.add_argument("--kinds", default=None, help="mini: kernel kinds, comma separated: cg, mask, mix, llm, net "
                    "(default cg,mask)")
    ap.add_argument("--layers", default=None, help="mini: layer counts, comma separated (default 1,5; full 1,5,10)")
    ap.add_argument("--auto-mask", action="store_true", help="mini: let mini add its /run/user mask (default off)")
    ap.add_argument("--dir", default=None, help="parent of the temp folder (default /tmp); the file system type "
                    "matters for fs (tmpfs vs disk)")
    ap.add_argument("--out", help="append JSON lines here (then the table goes to stdout)")
    ap.add_argument("--keep", action="store_true", help="keep the temp folder")
    a = ap.parse_args()
    what = a.what or (QUICK if a.quick else [x for x in ALL if x not in ("mountmax", "fusehang")])
    if what == ["all"]:
        what = ALL
    bad = [w for w in what if w not in ALL]
    if bad:
        ap.error("unknown bench %s (want: %s)" % (", ".join(bad), ", ".join(ALL)))
    kinds = (a.kinds or "cg,mask").split(",")
    layers = [int(x) for x in (a.layers or ("1,5" if a.quick else "1,5,10")).split(",")]
    work = tempfile.mkdtemp(prefix="aos-perf-", dir=a.dir)
    sink = open(a.out, "a") if a.out else sys.stdout
    tab_out = sys.stdout if a.out else sys.stderr
    recs = []
    try:
        for w in what:
            t = time.perf_counter()
            try:
                if w == "mini":
                    rs = minibench.mini(work, a.quick, kinds, layers, auto_mask=a.auto_mask)
                elif w == "pisandbox":
                    rs = pisandbox.pisandbox(work, a.quick)
                else:
                    mod = fsbench if w in ("fs", "overlay", "mountmax", "flat") else \
                        dynbench if w in ("fuse", "fusehang", "sock") else nsbench
                    rs = getattr(mod, w)(work, a.quick)
            except Exception as e:  # noqa: BLE001 - one bench failing must not stop the others
                rs = [{"bench": w, "error": "%s: %s" % (type(e).__name__, e)}]
            for r in rs:
                r.setdefault("bench", w)
                r["quick"] = a.quick
                r = common.stamp(r)
                recs.append(r)
                sink.write(json.dumps(r, ensure_ascii=False) + "\n")
                sink.flush()
            print("bench %s: %d record(s), %.1fs" % (w, len(rs), time.perf_counter() - t), file=sys.stderr,
                  flush=True)
    finally:
        if a.out:
            sink.close()
        if a.keep:
            print("kept %s" % work, file=sys.stderr)
        else:
            remove(work)
    h = common.host()
    print("\nmachine: %s (%d cpus), Linux %s, %s; commit %s; %s" % (
        h["cpu"], h["cpus"], h["kernel"], h["os"], h["commit"], "quick" if a.quick else "full"), file=tab_out)
    print(table(recs), file=tab_out)


if __name__ == "__main__":
    main()
