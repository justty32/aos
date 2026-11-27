"""File-replacement costs, all inside `unshare -Urm` (no root): static covers bind/tmpfs/null/ro/bindro from 0 to N mounts, overlayfs up to 500 layers, the mount-max wall, and one-layer-per-namespace vs one flattened table."""

import errno
import json
import os
import subprocess
import sys
import time

from common import (HERE, MNT_DETACH, MS_BIND, MS_NODEV, MS_NOSUID, MS_RDONLY, MS_REMOUNT, PY, Lat, best_ms,
                    collect, fstype, inner_emit, make_private, mount, mountinfo_lines, r2, umount)

D = "a/b/c/d/e/f/g/h/i/j"  # ten folders deep


def build_tree(work, ndirs):
    """tree/plain, src, rep, deep: a ten-deep x.txt each; tree/m/d<i> folders and tree/n/f<i> files as mount points."""
    t = os.path.join(work, "tree")
    for top, text in (("plain", "hello\n"), ("src", "hello\n"), ("rep", "replaced\n"), ("deep", "hello\n")):
        os.makedirs(os.path.join(t, top, D), exist_ok=True)
        with open(os.path.join(t, top, D, "x.txt"), "w") as f:
            f.write(text)
    os.makedirs(os.path.join(t, "m"), exist_ok=True)
    os.makedirs(os.path.join(t, "n"), exist_ok=True)
    for i in range(ndirs):
        p = os.path.join(t, "m", "d%d" % i)
        if not os.path.isdir(p):
            os.mkdir(p)
        q = os.path.join(t, "n", "f%d" % i)
        if not os.path.exists(q):
            open(q, "w").close()
    return t


def in_ns(work, sub, args, timeout=600):
    """Run `bench.py _in SUB ARGS` in a fresh user+mount namespace; its records."""
    cmd = ["unshare", "-Urm", PY, "-B", os.path.join(HERE, "bench.py"), "_in", sub, json.dumps(args)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=work)
    recs = collect(r.stdout)
    if r.returncode != 0 and not recs:
        recs = [{"bench": sub, "error": (r.stderr.strip().splitlines() or ["rc %d" % r.returncode])[-1]}]
    return recs


# ------------------------------------------------------------------ static covers

def fs(work, quick):
    kinds = ["bind", "tmpfs", "null", "ro", "bindro"]
    ns = [0, 100, 1000] if quick else [0, 10, 100, 1000, 5000]
    tree = build_tree(work, max(ns))
    lat = Lat(work)
    out = []
    for k in kinds:
        for n in ns:
            if n == 0 and k != "bind":
                continue  # "no mounts" once is enough
            out += in_ns(work, "fs", {"tree": tree, "kind": k if n else "none", "n": n, "lat": lat.bin,
                                     "reps": 5000 if quick else 20000})
    for r in out:
        r["tree_fs"] = fstype(tree)
    return out


def fs_inner(a):
    tree, kind, n = a["tree"], a["kind"], a["n"]
    lat = Lat.__new__(Lat)
    lat.bin, lat.timer = a["lat"], "c" if a["lat"] else "python"
    make_private()
    mount(os.path.join(tree, "rep", D, "x.txt"), os.path.join(tree, "deep", D, "x.txt"), None, MS_BIND)
    src = os.path.join(tree, "src")
    t0 = time.perf_counter()
    for i in range(n):
        d = "%s/m/d%d" % (tree, i)
        if kind == "bind":
            mount(src, d, None, MS_BIND)
        elif kind == "tmpfs":
            mount("tmpfs", d, "tmpfs", MS_NOSUID | MS_NODEV, "size=1m")
        elif kind == "null":
            mount("/dev/null", "%s/n/f%d" % (tree, i), None, MS_BIND)
        elif kind == "ro":
            mount(d, d, None, MS_BIND)
            mount(None, d, None, MS_BIND | MS_REMOUNT | MS_RDONLY)
        elif kind == "bindro":
            mount(src, d, None, MS_BIND)
            mount(None, d, None, MS_BIND | MS_REMOUNT | MS_RDONLY)
    tm = (time.perf_counter() - t0) * 1000
    plain = os.path.join(tree, "plain", D, "x.txt")
    deep = os.path.join(tree, "deep", D, "x.txt")
    crossed = os.path.join(tree, "m", "d%d" % (n - 1), D, "x.txt") if kind in ("bind", "bindro") and n else plain
    reps = a["reps"]
    o = lat.run("open", reps, plain, crossed, deep)
    s = lat.run("stat", reps, plain)
    m = lat.run("miss", reps, os.path.join(tree, "plain", D, "nope"))
    best = 1e9
    for _ in range(3):
        t = time.perf_counter()
        with open("/proc/self/mountinfo") as f:
            f.read()
        best = min(best, time.perf_counter() - t)
    inner_emit({"bench": "fs", "case": kind, "n": n, "timer": lat.timer, "mount_total_ms": r2(tm),
                "per_mount_us": r2(tm * 1000 / n, 1) if n else None, "mountinfo_lines": mountinfo_lines(),
                "read_mountinfo_ms": r2(best * 1000, 3), "open_plain_us": o[0]["median_us"],
                "open_crossed_us": o[1]["median_us"], "open_deep_replaced_us": o[2]["median_us"],
                "stat_us": s[0]["median_us"], "miss_us": m[0]["median_us"],
                "unshare_Urm_true_ms": best_ms(["unshare", "-Urm", "true"])[0]})


# ------------------------------------------------------------------ overlayfs

def overlay(work, quick):
    ks = [0, 1, 5, 20] if quick else [0, 1, 2, 5, 20, 100, 500, 501]
    ov = os.path.join(work, "ov")
    os.makedirs(os.path.join(ov, "bottom"), exist_ok=True)
    for j in range(2000):
        open(os.path.join(ov, "bottom", "b%d" % j), "w").write("x\n")
    for i in range(max(ks)):
        os.makedirs(os.path.join(ov, "l%d" % i), exist_ok=True)
    open(os.path.join(ov, "l0", "c"), "w").write("top\n")
    for d in ("up", "work"):
        os.makedirs(os.path.join(ov, d), exist_ok=True)
    lat = Lat(work)
    return in_ns(work, "overlay", {"ov": ov, "ks": ks, "lat": lat.bin, "reps": 5000 if quick else 20000})


def overlay_inner(a):
    ov, lat = a["ov"], Lat.__new__(Lat)
    lat.bin, lat.timer = a["lat"], "c" if a["lat"] else "python"
    make_private()
    os.chdir(ov)  # relative lowerdir names: the old mount API takes one page (4096 bytes) of options
    for k in a["ks"]:
        rec = {"bench": "overlay", "case": "ro-lowers", "n": k, "timer": lat.timer}
        if k == 0:
            mnt, tm = os.path.join(ov, "bottom"), 0.0
        else:
            mnt = os.path.join(ov, "mnt%d" % k)
            os.makedirs(mnt, exist_ok=True)
            lowers = ["l%d" % i for i in range(k - 1)] + ["bottom"]
            data = "lowerdir=" + ":".join(lowers) + ("" if k > 1 else ",upperdir=up,workdir=work")
            t0 = time.perf_counter()
            try:
                mount("overlay", mnt, "overlay", 0, data)
            except OSError as e:
                rec.update({"error": "mount: %s %s" % (errno.errorcode.get(e.errno, e.errno), e.strerror),
                            "options_len": len(data)})
                inner_emit(rec)
                continue
            tm = (time.perf_counter() - t0) * 1000
        first, bad = lat.first_open_mean(["%s/b%d" % (mnt, j) for j in range(1, 2000)])
        hot = lat.run("open", a["reps"], ("%s/c" % mnt) if k > 1 else "%s/b0" % mnt, "%s/b0" % mnt)
        miss = lat.run("miss", a["reps"], "%s/nope" % mnt)
        rec.update({"mount_ms": r2(tm, 3), "first_open_mean_us": r2(first), "first_open_bad": bad,
                    "hot_open_top_us": hot[0]["median_us"], "hot_open_bottom_us": hot[1]["median_us"],
                    "miss_us": miss[0]["median_us"]})
        inner_emit(rec)
        if k:
            umount(mnt, MNT_DETACH)


# ------------------------------------------------------------------ mount-max

def mountmax(work, quick):
    os.makedirs(os.path.join(work, "wall"), exist_ok=True)
    lat = Lat(work)
    tree = build_tree(work, 0)
    return in_ns(work, "mountmax", {"wall": os.path.join(work, "wall"), "tree": tree, "lat": lat.bin})


def mountmax_inner(a):
    lat = Lat.__new__(Lat)
    lat.bin, lat.timer = a["lat"], "c" if a["lat"] else "python"
    make_private()
    big, src = a["wall"], os.path.join(a["tree"], "src")
    mount("tmpfs", big, "tmpfs", 0, "size=200m,nr_inodes=300000")
    for i in range(110000):
        os.mkdir("%s/%d" % (big, i))
    t0, n, err = time.perf_counter(), 0, None
    try:
        for i in range(110000):
            mount(src, "%s/%d" % (big, i), None, MS_BIND)
            n += 1
    except OSError as e:
        err = "errno %d %s" % (e.errno, e.strerror)
    t = time.perf_counter() - t0
    o = lat.run("open", 5000, os.path.join(a["tree"], "plain", D, "x.txt"), "%s/%d/%s/x.txt" % (big, n - 1, D))
    best = 1e9
    for _ in range(3):
        t1 = time.perf_counter()
        with open("/proc/self/mountinfo") as f:
            f.read()
        best = min(best, time.perf_counter() - t1)
    inner_emit({"bench": "mountmax", "case": "bind-until-refused", "n": n, "error": err, "bind_total_s": r2(t),
                "per_mount_us": r2(t / max(n, 1) * 1e6), "mountinfo_lines": mountinfo_lines(),
                "open_plain_us": o[0]["median_us"], "open_crossed_us": o[1]["median_us"],
                "read_mountinfo_ms": r2(best * 1000), "unshare_Urm_true_ms": best_ms(["unshare", "-Urm", "true"])[0]})
    t1 = time.perf_counter()
    umount(big, MNT_DETACH)
    inner_emit({"bench": "mountmax", "case": "umount-l-all", "n": n, "ms": r2((time.perf_counter() - t1) * 1000)})


# ------------------------------------------------------------------ one namespace per layer vs one flattened table

def flat(work, quick):
    """Synthetic file layers (layer.py, a lean python like a small kernel): each layer = python + a new
    user+mount ns + one tmpfs (what a mask kernel costs); flat = one python covering all n in one ns. Both end
    with the agent's own extra ns, which must not be able to undo the covers."""
    layered = [1, 10] if quick else [1, 10, 30]
    flats = [10, 1000]
    tree = build_tree(work, max(flats + layered))
    lay = os.path.join(HERE, "layer.py")
    out = []
    for case, ns in (("one-ns-per-layer", layered), ("one-table", flats)):
        for n in ns:
            argv = ["layer", tree, "0", str(n)] if case == "one-ns-per-layer" else ["flat", tree, str(n)]
            t = time.perf_counter()
            r = subprocess.run(["unshare", "-Urm", PY, "-I", "-B", lay] + argv, capture_output=True, text=True,
                               timeout=300)
            ms = (time.perf_counter() - t) * 1000
            rec = {"bench": "flat", "case": case, "n": n, "total_ms": r2(ms, 1), "leaf_ok": "leaf-ok" in r.stdout,
                   "agent_could_umount": "umount-worked" in r.stdout,
                   "error": None if r.returncode == 0 else r.stderr.strip()[-200:]}
            if case == "one-ns-per-layer":
                rec["per_layer_ms"] = r2(ms / n, 2)
            out.append(rec)
    return out


INNER = {"fs": fs_inner, "overlay": overlay_inner, "mountmax": mountmax_inner}

if __name__ == "__main__":
    sys.exit("run bench.py, not this file")
