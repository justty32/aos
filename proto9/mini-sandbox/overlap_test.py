#!/usr/bin/env python3
"""Tests for overlapping and flattened kernel chains (the seven answers of 11-27 night) and the two bugs: one of each kernel file, merge (never looser) and KernelMergeBad, two llm kernels not chained refused, use/replace/without, uid innermost (same number once, different numbers refused), cgroup and mask kernels flattened (same limits as nested; one mask table; the agent cannot undo it), the user namespace count checked before anything starts, .aos/effective with blame and .aos/lock.json, --explain, --diff, one summary line for looser settings; bug a (the namespace wall: a clean failure, nothing left over) and bug b (three net kernels with different rates: the quota counts what went through); PASS/FAIL/info lines."""

import sys

sys.dont_write_bytecode = True  # before importing accept: keep the repo free of __pycache__

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

import accept as A  # noqa: E402  (test servers)
import stack_test as S  # noqa: E402  (mini runner, snapshot, check_argv, record)

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.expanduser("~/.aos/scratch/proto9-mini-1127/overlap")
MINI = os.path.join(HERE, "mini.py")
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


def make_kernels(pa, pb, pc):
    kernel("t/cg", "cg_kernel.py", {"cpu": "20%", "mem": "200M", "pids": 40})
    kernel("t/cg-high", "cg_kernel.py", {"cpu": "60%", "mem": "300M", "pids": 200})
    kernel("t/cg-loose", "cg_kernel.py", {"cpu": "80%", "mem": "500M", "pids": 100})
    kernel("t/cg3", "cg_kernel.py", {"mem": "300M"})
    # 1: the same kernel through two bundles
    bundle("t/b1", ["t/cg", "aos/llm/fake"])
    bundle("t/b2", ["aos/mask/ssh", "aos/llm/fake"])
    # 2: merge
    kernel("t/mcg/a", "cg_kernel.py", {"cpu": "20%", "mem": "400M", "pids": 80})
    kernel("t/mcg/b", "cg_kernel.py", {"cpu": "60%", "mem": "200M", "pids": 30})
    bundle("t/mcg", [{"merge": ["a", "b"]}])
    kernel("t/mnet/ab", "net_kernel.py", {"host_ports": [pa, pb], "quota": "5mb"})
    kernel("t/mnet/ac", "net_kernel.py", {"host_ports": [pa, pc], "quota": "3mb"})
    bundle("t/mnet", [{"merge": ["ab", "ac"]}])
    kernel("t/llm-a", "llm_kernel.py", {"upstream": "fake", "models": ["fake-model"], "limit": 3})
    kernel("t/llm-url", "llm_kernel.py", {"upstream": "http://127.0.0.1:%d/v1" % pa, "models": ["fake-model"],
                                          "limit": 5})
    bundle("t/mbad-llm", [{"merge": ["t/llm-a", "t/llm-url"]}])
    kernel("t/own", os.path.join(BASE, "orphan.py"), {})
    bundle("t/mbad-own", [{"merge": ["t/cg", "t/own"]}])
    bundle("t/mbad-kind", [{"merge": ["t/cg", "aos/mask/ssh"]}])
    # 3: two llm kernels
    kernel("t/llm-b", "llm_kernel.py", {"upstream": "fake", "models": ["fake-model"], "limit": 5})
    kernel("t/llm-c", "llm_kernel.py", {"upstream": "outer", "models": ["fake-model"], "limit": 5})
    # 4: use / replace / without
    bundle("t/dev", [{"use": "aos/base", "replace": {"cg": "t/cg-high"}, "without": ["aos/llm/fake"]},
                     "aos/mask/ssh"])
    bundle("t/devbad", [{"use": "aos/base", "replace": {"nope": "t/cg-high"}}])
    # 5: uid
    kernel("t/uid1b", "uid_kernel.py", {"uid": 1})
    kernel("t/uid2", "uid_kernel.py", {"uid": 2})
    bundle("t/pu1", ["t/cg", "aos/uid/1"])
    bundle("t/pu2", ["aos/mask/ssh", "t/uid1b"])
    # 6: flattening: the ten cgroup kernels of scale-report, and their tightest one alone
    for i, (cpu, mem, pids) in enumerate(((90, 400, 80), (70, 380, 75), (85, 350, 70), (40, 330, 65), (60, 250, 60),
                                          (95, 300, 55), (50, 320, 50), (80, 360, 45), (75, 390, 52), (65, 270, 58))):
        kernel("t/f/cg%d" % (i + 1), "cg_kernel.py", {"cpu": "%d%%" % cpu, "mem": "%dM" % mem, "pids": pids})
    kernel("t/f/cg-flat", "cg_kernel.py", {"cpu": "40%", "mem": "250M", "pids": 45})
    d = os.path.join(BASE, "files")
    kernel("t/f/mk1", "mask_kernel.py", {"paths": [{"path": d + "/secret", "how": "tmpfs"}], "keep": [d + "/secret/d"]})
    kernel("t/f/mk2", "mask_kernel.py", {"paths": [{"path": d + "/file.txt", "how": "null"}]})
    kernel("t/f/mk3", "mask_kernel.py", {"paths": [{"path": d + "/ro", "how": "ro"}]})
    kernel("t/f/mk4", "mask_kernel.py", {"paths": [{"path": d + "/secret/a", "how": "null"}]})  # under mk1's cover
    kernel("t/f/mk-one", "mask_kernel.py", {"paths": [{"path": d + "/secret", "how": "tmpfs"},
                                                      {"path": d + "/file.txt", "how": "null"},
                                                      {"path": d + "/ro", "how": "ro"}], "keep": [d + "/secret/d"]})
    for i in range(1, 14):
        kernel("t/deep/n%d" % i, "net_kernel.py", {"host_ports": [pa]})
    for i in range(1, 101):  # 100 layers, cgroup and mask taking turns
        if i % 2:
            kernel("t/many/%d" % i, "cg_kernel.py", {"cpu": "%d%%" % (30 + i), "mem": "%dM" % (300 + i), "pids": 50 + i})
        else:
            kernel("t/many/%d" % i, "mask_kernel.py", {"paths": [{"path": d + "/many/%d" % i, "how": "tmpfs"}]})
    # bug a: the wall
    kernel("t/w/1", "llm_kernel.py", {"upstream": "fake", "models": ["fake-model"], "limit": 5})
    for i in range(2, 35):
        kernel("t/w/%d" % i, "llm_kernel.py", {"upstream": "outer", "models": ["fake-model"], "limit": 5})
    kernel("t/w/net", "net_kernel.py", {"host_ports": [pa]})
    # bug b: three net kernels with different rates (scale-report section 2)
    kernel("t/n3/outer", "net_kernel.py", {"host_ports": [pa, pb], "down": "32mbit", "quota": "60mb"})
    kernel("t/n3/mid", "net_kernel.py", {"host_ports": [pa, pb], "down": "16mbit", "quota": "40mb"})
    kernel("t/n3/inner", "net_kernel.py", {"host_ports": [pa], "down": "24mbit", "quota": "25mb"})


def make_files():
    d = os.path.join(BASE, "files")
    for p in ("secret/d", "ro", "many"):
        os.makedirs(os.path.join(d, p), exist_ok=True)
    for p, t in (("secret/a", "A"), ("secret/b", "B"), ("secret/d/c", "C"), ("file.txt", "FILE"), ("ro/r", "R")):
        with open(os.path.join(d, p), "w") as f:
            f.write(t)
    for i in range(2, 101, 2):
        os.makedirs(os.path.join(d, "many", str(i)), exist_ok=True)
        with open(os.path.join(d, "many", str(i), "x"), "w") as f:
            f.write("x")
    with open(os.path.join(BASE, "orphan.py"), "w") as f:  # a kernel of your own that fails and leaves a child
        f.write("import subprocess, sys\nsubprocess.Popen(['sleep', '300'])\nsys.exit(3)\n")


def dirs_now():
    return sorted(d for d in os.listdir("/tmp") if d.startswith("aos-mini-"))


def layers(out):
    return [l[len("# layer "):].split("  (file ")[0] for l in out.splitlines() if l.startswith("# layer ")]


def notes(text):
    return [l.split("note: ", 1)[1] if "note: " in l else l[len("mini: "):] for l in text.splitlines()
            if l.startswith(("# note: ", "mini: ")) and ": error: " not in l]


def refused(name, kernels, code, want_in_err, flags=(), env=None):
    """Refused before anything runs: exit 2, the error code, nothing started."""
    marker = os.path.join(BASE, name + ".ran")
    before = dirs_now()
    r = S.mini(name.replace("_", "-"), kernels, ["sh", "-c", "touch %s" % marker], flags=flags, env=env)
    last = (r.err.strip().splitlines() or ["-"])[-1]
    ok = r.rc == 2 and code in last and all(w in last for w in want_in_err) and not os.path.exists(marker) and \
        dirs_now() == before
    record(name, ok, "[%s%s] exit %s, ran: %s; %s" % (",".join(kernels), " " + " ".join(flags) if flags else "", r.rc,
                                                      os.path.exists(marker), last[:300]))
    return r


def env_dump(files):
    """sh: print each $AOS_ENV-relative file as one json line {path: text}, then exec the rest."""
    py = ("import json,os;e=os.environ.get('AOS_ENV','/');print(json.dumps({p:(open(os.path.join(e,p)).read() if "
          "os.path.exists(os.path.join(e,p)) else None) for p in %r}))" % (files,))
    return ["sh", "-c", 'python3 -I -c "$0"; exec "$@"', py]


def first_json(out):
    for l in out.splitlines():
        if l.startswith("{"):
            try:
                return json.loads(l)
            except ValueError:
                pass
    return {}


# ---------------------------------------------------------------- 1. the same kernel twice

def q1_dedup():
    log("\n== h. 1: the same kernel file twice: kept once (the outer one), one line")
    r = S.mini("h-dedup-dry", ["t/b1", "t/b2"], ["true"], flags=("--dry-run",))
    got, n = layers(r.out), notes(r.out)
    record("h_dedup_dry", r.rc == 0 and got == ["1: cgroup t/cg from t/b1", "2: llm aos/llm/fake from t/b1",
                                                "3: mask aos/mask/ssh from t/b2",
                                                "4: mask aos/mask/run-user (added by mini)"] and
           "aos/llm/fake appears twice (from t/b1, t/b2); kept the outer one" in n,
           "[t/b1,t/b2 --dry-run] layers %s; notes %s" % (got, n))
    r = S.mini("h-dedup-run", ["aos/base", "aos/base"], env_dump([".aos/kernels"]) +
               S.check_argv({"llm": {"posts": 2}}))
    j, k = r.j or {}, first_json(r.out).get(".aos/kernels") or ""
    others = j.get("llm_other_socks", {})
    record("h_dedup_run", k.splitlines() == ["cgroup aos/base/cg from aos/base", "mask aos/base/mask from aos/base",
                                             "llm aos/llm/fake from aos/base"] and j.get("llm_codes") == [200, 200]
           and not any(v == 200 for v in others.values()) and r.err.count("appears twice") == 3,
           "[aos/base,aos/base] .aos/kernels %s; brain %s; other llm sockets reachable: %s; lines saying so: %d" % (
               k.splitlines(), j.get("llm_codes"), [p for p, v in others.items() if v == 200],
               r.err.count("appears twice")))


# ---------------------------------------------------------------- 2. merge

def q2_merge(pa, pb, pc):
    log("\n== i. 2: merge: one layer, never looser; what cannot be compared is refused")
    r = S.mini("i-merge-cg", ["t/mcg"], env_dump([".aos/kernels", ".aos/effective/cgroup/blame"]) +
               S.check_argv({"cpu": 1.5, "pids": 60, "mem": 400}), flags=("--no-auto-mask",))
    j, d = r.j or {}, first_json(r.out)
    lim = 0.15 <= j.get("cpu_ratio", 0) <= 0.25 and j.get("mem_end") == "killed by signal 9" and \
        j.get("mem_reached_mb", 999) < 200 and j.get("forked", 99) < 30
    record("i_merge_cg", lim and (d.get(".aos/kernels") or "").splitlines() == ["cgroup t/mcg/a+t/mcg/b from t/mcg"],
           "[merge 20%%/400M/80 + 60%%/200M/30] one layer %s; cpu %s, mem %s at %s MB, forked %s; blame %s" % (
               (d.get(".aos/kernels") or "").splitlines(), j.get("cpu_ratio"), j.get("mem_end"),
               j.get("mem_reached_mb"), j.get("forked"), (d.get(".aos/effective/cgroup/blame") or "").splitlines()))
    r = S.mini("i-merge-net", ["t/mnet"], env_dump([".aos/kernels"]) + S.check_argv(
        {"tcp": [[HOST, pa], [HOST, pb], [HOST, pc]], "get": [HOST, pa, 4_000_000, 10]}), flags=("--no-auto-mask",))
    j, d = r.j or {}, first_json(r.out)
    t = {p: j.get("tcp %s:%d" % (HOST, p)) for p in (pa, pb, pc)}
    got = j.get("get_bytes", -1)
    record("i_merge_net", (d.get(".aos/kernels") or "").splitlines() == ["net t/mnet/ab+t/mnet/ac from t/mnet"] and
           t[pa] == "ok" and t[pb] != "ok" and t[pc] != "ok" and 2_000_000 < got < 3_000_000,
           "[merge A,B 5mb + A,C 3mb] layers %s (one pasta); A %s, B %s, C %s; asked 4 MB, got %d before the cut" % (
               (d.get(".aos/kernels") or "").splitlines(), t[pa], "ok" if t[pb] == "ok" else "closed",
               "ok" if t[pc] == "ok" else "closed", got))
    refused("i_merge_bad_llm", ["t/mbad-llm"], "KernelMergeBad", ["upstream differs"])
    refused("i_merge_bad_own", ["t/mbad-own"], "KernelMergeBad", ["not one of mini's own kernels"])
    refused("i_merge_bad_kind", ["t/mbad-kind"], "KernelMergeBad", ["kinds differ"])


# ---------------------------------------------------------------- 3. two llm kernels

def q3_llm():
    log("\n== j. 3: two llm kernels that are not chained: refused; chained: the outer socket is hidden")
    refused("j_llm_unchained", ["t/llm-a", "t/llm-b"], "KernelOrderBad", ['"upstream": "outer"', "t/llm-b"])
    refused("j_llm_unchained_dry", ["t/llm-a", "t/llm-b"], "KernelOrderBad", ['"upstream": "outer"'],
            flags=("--dry-run",))
    r = S.mini("j-llm-chained", ["t/llm-a", "t/llm-c"], S.check_argv({"llm": {"posts": 4}}))
    j = r.j or {}
    others = j.get("llm_other_socks", {})
    record("j_llm_chained", j.get("llm_codes") == [200, 200, 200, 429] and len(others) == 1 and
           all(v != 200 for v in others.values()),
           "[t/llm-a (3), t/llm-c upstream outer (5)] codes %s; the outer socket from inside: %s" % (
               j.get("llm_codes"), list(others.values())))


# ---------------------------------------------------------------- 4. use / replace / without

def q4_replace():
    log("\n== k. 4: use + replace + without")
    r = S.mini("k-dry", ["t/dev"], ["true"], flags=("--dry-run",))
    got, n = layers(r.out), notes(r.out)
    files = [l.split("  (file ")[1].rstrip(")") for l in r.out.splitlines() if l.startswith("# layer ")]
    record("k_replace_dry", r.rc == 0 and got == ["1: cgroup t/cg-high from t/dev",
                                                  "2: mask aos/base/mask from t/dev>aos/base",
                                                  "3: mask aos/mask/ssh from t/dev"] and
           any("aos/base/cg replaced by t/cg-high" in x for x in n) and
           any("left out aos/llm/fake" in x for x in n) and files[0].endswith("/t/cg-high.json"),
           "[t/dev --dry-run] layers %s; notes %s; first file %s" % (got, n, files[:1]))
    r = S.mini("k-run", ["t/dev"], S.check_argv({"cpu": 1.5, "mem": 400, "llm": {"posts": 1}}))
    j = r.j or {}
    record("k_replace_run", 0.5 <= j.get("cpu_ratio", 0) <= 0.7 and j.get("mem_end") == "killed by signal 9" and
           200 < j.get("mem_reached_mb", 0) < 300 and "llm_decl" in j,
           "[t/dev] cpu %s (60%%), mem %s at %s MB (300M), brain: %s" % (
               j.get("cpu_ratio"), j.get("mem_end"), j.get("mem_reached_mb"), str(j.get("llm_decl"))[:40]))
    refused("k_replace_bad", ["t/devbad"], "KernelBundleBad", ["no 'nope'", "cg, mask, aos/llm/fake"])


# ---------------------------------------------------------------- 5. uid

def q5_uid():
    log("\n== l. 5: uid innermost; the same number once; different numbers refused")
    r = S.mini("l-moved", ["aos/uid/1", "t/cg"], env_dump([".aos/kernels"]) + S.check_argv({}))
    j, k = r.j or {}, (first_json(r.out).get(".aos/kernels") or "").splitlines()
    record("l_uid_moved", r.rc == 0 and j.get("uid") == 1 and k[-1:] == ["uid aos/uid/1"] and
           "moved aos/uid/1 innermost" in r.err,
           "[aos/uid/1,t/cg] exit %s, uid %s, .aos/kernels %s; said: %s" % (r.rc, j.get("uid"), k,
                                                                        "moved aos/uid/1 innermost" in r.err))
    r = S.mini("l-same", ["t/pu1", "t/pu2"], env_dump([".aos/kernels"]) + S.check_argv({}))
    j, k = r.j or {}, (first_json(r.out).get(".aos/kernels") or "").splitlines()
    record("l_uid_same_once", r.rc == 0 and j.get("uid") == 1 and [l.split()[0] for l in k] ==
           ["cgroup", "mask", "mask", "uid"] and "uid 1 appears twice" in r.err,
           "[t/pu1 (cg, uid 1), t/pu2 (mask, another uid 1)] exit %s, uid %s, .aos/kernels %s; %s" % (
               r.rc, j.get("uid"), k, next((l for l in r.err.splitlines() if "appears" in l), "")))
    refused("l_uid_clash", ["aos/uid/1", "t/uid2"], "KernelUidClash", ["uid 1", "uid 2"])


# ---------------------------------------------------------------- 6. flattening

def q6_flatten():
    log("\n== m. 6: cgroup and mask kernels next to each other run as one layer: the same limits, one table")
    ten = ["t/f/cg%d" % i for i in range(1, 11)]
    spec = {"cpu": 2, "pids": 60, "mem": 400}
    res = {}
    for name, ks in (("ten", ten), ("one", ["t/f/cg-flat"])):
        t0 = time.monotonic()
        r = S.mini("m-cg-" + name, ks, env_dump([".aos/interfaces/aos/cgroup/flattened",
                                                 ".aos/interfaces/aos/cgroup/layer"]) + S.check_argv(spec),
                   flags=("--no-auto-mask",))
        res[name] = (r.j or {}, first_json(r.out), time.monotonic() - t0)
    (a, da, ta), (b, db, tb) = res["ten"], res["one"]
    ok = abs(a.get("cpu_ratio", 9) - b.get("cpu_ratio", 0)) < 0.05 and a.get("forked") == b.get("forked") and \
        a.get("mem_end") == b.get("mem_end") == "killed by signal 9" and \
        abs(a.get("mem_reached_mb", 0) - b.get("mem_reached_mb", 999)) <= 20
    record("m_cg_ten_vs_one", ok and (da.get(".aos/interfaces/aos/cgroup/flattened") or "").split() ==
           [str(i) for i in range(1, 11)],
           "10 layers flattened: cpu %s, forked %s, mem %s at %s MB, %.1fs (cell layer %s, flattened %s); 1 layer "
           "40%%/250M/45: cpu %s, forked %s, mem %s at %s MB, %.1fs" % (
               a.get("cpu_ratio"), a.get("forked"), a.get("mem_end"), a.get("mem_reached_mb"), ta,
               (da.get(".aos/interfaces/aos/cgroup/layer") or "").strip(),
               (da.get(".aos/interfaces/aos/cgroup/flattened") or "").strip(), b.get("cpu_ratio"), b.get("forked"),
               b.get("mem_end"), b.get("mem_reached_mb"), tb))
    d = os.path.join(BASE, "files")
    look = ("import json,os,ctypes;d=%r;o={}\n"
            "o['secret']=sorted(os.listdir(d+'/secret'))\n"
            "o['hole']=open(d+'/secret/d/c').read() if os.path.exists(d+'/secret/d/c') else None\n"
            "o['file']=open(d+'/file.txt').read()\n"
            "try:\n open(d+'/ro/x','w').write('x');o['ro']='wrote'\n"
            "except OSError as e:\n o['ro']=e.strerror\n"
            "l=ctypes.CDLL(None,use_errno=True)\n"
            "o['umount']=[os.strerror(ctypes.get_errno()) if l.umount2(p.encode(),2) else 'ok' for p in "
            "(d+'/secret',d+'/file.txt',d+'/ro')]\n"
            "o['remount_rw']=os.strerror(ctypes.get_errno()) if l.mount(None,(d+'/ro').encode(),None,32|4096,None) "
            "else 'ok'\n"
            "print(json.dumps(o))" % d)
    seen = {}
    for name, ks in (("table", ["t/f/mk1", "t/f/mk2", "t/f/mk3", "t/f/mk4"]), ("one", ["t/f/mk-one"])):
        r = S.mini("m-mask-" + name, ks, ["sh", "-c", 'python3 -I -c "$0"; exec "$@"', look] + env_dump(
            [".aos/interfaces/aos/mask/paths", ".aos/interfaces/aos/mask/flattened"]) + S.check_argv({"lock": {}}),
            flags=("--no-auto-mask",))
        seen[name] = (first_json(r.out), [json.loads(l) for l in r.out.splitlines() if l.startswith("{")][1:2],
                      r.j or {})
    (t, td, tj), (o, od, oj) = seen["table"], seen["one"]
    td = td[0] if td else {}
    want = {"secret": ["d"], "hole": "C", "file": "", "ro": "Read-only file system"}
    same = all(t.get(k) == o.get(k) == v for k, v in want.items())
    held = all(x != "ok" for x in t.get("umount", ["ok"]) + [t.get("remount_rw", "ok")])
    decl = (td.get(".aos/interfaces/aos/mask/paths") or "").splitlines()
    import bundle_test as B
    bad = B.lock_ok(tj)
    record("m_mask_table", same and held and not bad and len(decl) == 5 and decl[-1].startswith("absent ") and
           (td.get(".aos/interfaces/aos/mask/flattened") or "").split() == ["1", "2", "3", "4"],
           "4 mask kernels as one table vs 1 kernel with the same paths: %s vs %s; the agent undoing it: umount %s, "
           "remount rw %s, lock %s; declared %s" % (
               {k: t.get(k) for k in want}, {k: o.get(k) for k in want}, t.get("umount"), t.get("remount_rw"),
               "held" if not bad else bad, [l.replace(d, "~F") for l in decl]))
    log("\n== m. 6: the user namespaces are counted before anything starts")
    deep = ["t/deep/n%d" % i for i in range(1, 14)]
    for name, flags in (("m_userns_refused", ()), ("m_userns_refused_dry", ("--dry-run",))):
        before = S.snapshot(())
        r = refused(name, deep, "KernelTooDeep", ["needs 28", "net 13 x 2", "the 24 allowed here"], flags=flags)
        after = S.snapshot(())
        new = {k: v for k, v in after.items() if (set(v) - set(before[k]))}
        if new:
            record(name + "_left", False, "left: %s" % new)
    many = ["t/many/%d" % i for i in range(1, 101)]
    t0 = time.monotonic()
    r = S.mini("m-many", many, env_dump([".aos/effective/cgroup/blame", ".aos/kernels"]) +
               S.check_argv({"cpu": 1.5, "secret": os.path.join(d, "many", "100", "x")}), timeout=300)
    j, dd = r.j or {}, first_json(r.out)
    blame = (dd.get(".aos/effective/cgroup/blame") or "").splitlines()
    n = len((dd.get(".aos/kernels") or "").splitlines())
    record("m_hundred_layers", r.rc == 0 and n == 101 and 0.25 <= j.get("cpu_ratio", 0) <= 0.36 and
           "No such file" in j.get("secret", "") and blame[:1] == ["cpu 31% <- layer 1 t/many/1"],
           "[100 kernels, cgroup and mask taking turns: one layer] exit %s in %.1fs; .aos/kernels %d lines; cpu %s "
           "(31%%); the 100th mask: %s; blame %s" % (r.rc, time.monotonic() - t0, n, j.get("cpu_ratio"),
                                                     j.get("secret"), blame[:3]))


# ---------------------------------------------------------------- 7. effective, blame, lock, --explain, --diff

def q7_effective():
    log("\n== n. 7: .aos/effective and blame, .aos/lock.json, --explain, --diff, one line for looser settings")
    files = [".aos/effective/cgroup/cpu", ".aos/effective/cgroup/mem", ".aos/effective/cgroup/blame",
             ".aos/effective/llm/blame", ".aos/effective/mask/paths", ".aos/lock.json"]
    r = S.mini("n-eff", ["aos/base", "t/cg3"], env_dump(files) + ["true"])
    d = first_json(r.out)
    blame = (d.get(".aos/effective/cgroup/blame") or "").splitlines()
    try:
        lock = json.loads(d.get(".aos/lock.json") or "{}")
    except ValueError:
        lock = {}
    rs = lock.get("layers", [])
    sha_ok = bool(rs) and all(x["sha256"] == hashlib.sha256(open(x["file"], "rb").read()).hexdigest() for x in rs
                              if isinstance(x["file"], str) and os.path.isfile(x["file"]))
    record("n_effective_blame", (d.get(".aos/effective/cgroup/mem") or "").strip() == "300M" and blame == [
        "cpu 20% <- layer 1 aos/base/cg from aos/base", "mem 300M <- layer 4 t/cg3",
        "pids 64 <- layer 1 aos/base/cg from aos/base"] and "limit 50 <- layer 3 aos/llm/fake from aos/base (its own "
        "ledger)" in (d.get(".aos/effective/llm/blame") or ""),
        "[aos/base,t/cg3] cgroup blame %s; llm %s; mask paths %s" % (
            blame, (d.get(".aos/effective/llm/blame") or "").splitlines()[:1],
            (d.get(".aos/effective/mask/paths") or "").splitlines()))
    record("n_lock", [(x["layer"], x["kind"], x["name"], x["from"]) for x in rs] == [
        (1, "cgroup", "aos/base/cg", "aos/base"), (2, "mask", "aos/base/mask", "aos/base"),
        (3, "llm", "aos/llm/fake", "aos/base"), (4, "cgroup", "t/cg3", "")] and sha_ok and
        rs[3]["config"] == {"mem": "300M"} and lock.get("plan") == [[1, 2], [3], [4]],
        "layers %s; sha256 match the files: %s; plan %s; userns %s" % (
            [(x["layer"], x["kind"], x["name"]) for x in rs], sha_ok, lock.get("plan"), lock.get("userns")))
    lockfile = os.path.join(BASE, "A.lock")
    with open(lockfile, "w") as f:
        f.write(d.get(".aos/lock.json") or "{}")
    ex = subprocess.run([sys.executable, MINI, "--explain", "--kernels", "aos/base,t/cg3,t/cg-loose,aos/uid/1"],
                        capture_output=True, text=True)
    want = ["mem 300M <- layer 4 t/cg3", "flatten plan: 4 real layers instead of 6", "user namespaces: 5 needed",
            "looser than an outer layer (the outer one applies): 3", "layer 5 t/cg-loose: cpu 80%"]
    record("n_explain", ex.returncode == 0 and all(w in ex.stdout for w in want),
           "--explain: has %s; missing %s" % (len([w for w in want if w in ex.stdout]),
                                              [w for w in want if w not in ex.stdout]))
    df = subprocess.run([sys.executable, MINI, "--diff", lockfile, "aos/base,t/cg-loose"], capture_output=True,
                        text=True)
    same = subprocess.run([sys.executable, MINI, "--diff", lockfile, "aos/base,t/cg3"], capture_output=True,
                          text=True)
    lines = df.stdout.splitlines()
    record("n_diff", df.returncode == 1 and "+ layer 4 cgroup t/cg-loose (new)" in lines and
           "- layer 4 cgroup t/cg3 (gone)" in lines and any(l.startswith("= effective cgroup/mem: 300M -> 500M")
                                                             for l in lines) and same.returncode == 0,
           "--diff A.lock aos/base,t/cg-loose: exit %s %s; against the same names: exit %s %s" % (
               df.returncode, lines, same.returncode, same.stdout.strip()))
    r = S.mini("n-looser", ["t/cg", "t/cg-loose"], ["true"])
    lines = [l for l in r.err.splitlines() if "looser" in l or "applies" in l]
    record("n_looser_one_line", r.rc == 0 and lines == ["mini: 3 setting(s) written looser than an outer layer's; the "
                                                        "outer ones apply (details: mini.py --explain)"],
           "[t/cg 20%%/200M/40, t/cg-loose 80%%/500M/100] stderr lines about it: %s" % lines)


# ---------------------------------------------------------------- bug a: the wall

def bug_a():
    log("\n== o. bug a: past the user namespace wall (the count before starting switched off): a clean failure")
    wall = {"MINI_USERNS_MAX": "99"}
    for name, ks in (("o_wall_llm34", ["t/w/%d" % i for i in range(1, 35)]),
                     ("o_wall_net_gate", ["t/w/%d" % i for i in range(1, 33)] + ["t/w/net"])):
        marker = os.path.join(BASE, name + ".ran")
        before = S.snapshot(())
        t0 = time.monotonic()
        r = S.mini(name.replace("_", "-"), ks, ["sh", "-c", "touch %s" % marker], env=wall, timeout=180)
        sec = time.monotonic() - t0
        time.sleep(1)
        after = S.snapshot(())
        new = {k: (sorted(set(after[k]) - set(before[k])) if k != "procs" else
                   [c for p, c in after[k].items() if p not in before[k]]) for k in after}
        err = [l for l in r.err.splitlines() if "UsernsFull" in l]
        record(name, r.rc not in (0, None) and sec < 60 and err and not os.path.exists(marker) and
               not any(new.values()),
               "[%s: more than 33 user namespaces] exit %s in %.1fs; ran: %s; %s; left: %s" % (
                   "32 llm + 1 net kernel" if "net" in ks[-1] else "%d llm kernels" % len(ks), r.rc, sec,
                   os.path.exists(marker),
                   (err or ["no UsernsFull line: " + r.err.strip()[-200:]])[0][:230],
                   {k: v for k, v in new.items() if v} or "nothing"))
    before = S.snapshot(())
    t0 = time.monotonic()
    r = S.mini("o-orphan", ["t/own"], ["true"], timeout=60, flags=("--no-auto-mask",))
    sec = time.monotonic() - t0
    time.sleep(1)
    after = S.snapshot(())
    left = [c for p, c in after["procs"].items() if p not in before["procs"]]
    sleeps = subprocess.run(["pgrep", "-f", "^sleep 300$"], capture_output=True, text=True).stdout.split()
    record("o_orphan_swept", r.rc == 3 and sec < 20 and not left and not sleeps and
           set(after["units"]) == set(before["units"]),
           "[a kernel of your own exits 3 leaving 'sleep 300' on our stdout] mini back in %.1fs, exit %s; left: %s; "
           "sleep 300 still there: %s" % (sec, r.rc, left or "nothing", sleeps or "no"))


# ---------------------------------------------------------------- bug b: three net kernels, different rates

def bug_b(pa):
    log("\n== p. bug b: three net kernels (32/16/24 mbit; 60/40/25 MB): the middle quota counts what went through")
    look = ("import json,os,glob,socket,time\n"
            "def get(n,sec):\n"
            " c=socket.create_connection(('%s',%d),timeout=5);c.sendall(b'GET /bytes/%%d HTTP/1.0\\r\\n\\r\\n'%%n)\n"
            " t0=time.monotonic();got=-1;h=b''\n"
            " while time.monotonic()-t0<sec:\n"
            "  c.settimeout(max(0.05,sec-(time.monotonic()-t0)))\n"
            "  try: d=c.recv(1<<20)\n"
            "  except OSError: break\n"
            "  if not d: break\n"
            "  if got<0:\n"
            "   h+=d\n"
            "   if b'\\r\\n\\r\\n' in h: got=len(h.split(b'\\r\\n\\r\\n',1)[1])\n"
            "  else: got+=d and len(d)\n"
            " c.close();return max(got,0),time.monotonic()-t0\n"
            "def st():\n"
            " run=os.path.dirname(os.environ['AOS_ENV']);o={}\n"
            " for f in sorted(glob.glob(run+'/*-net-*/status')):\n"
            "  d=dict(l.split(': ',1) for l in open(f).read().splitlines() if ': ' in l)\n"
            "  o[f.split('/')[-2].split('-')[0]]=[int(d.get('quota_used',0)),d.get('down_dropped','?')]\n"
            " return o\n"
            "g1,t1=get(100*10**6,4);time.sleep(1.5);s1=st()\n"
            "g2,t2=get(40*10**6,25);time.sleep(1.5);s2=st()\n"
            "print(json.dumps({'g1':g1,'t1':t1,'s1':s1,'g2':g2,'t2':t2,'s2':s2}))\n" % (HOST, pa))
    r = S.mini("p-net3", ["t/n3/outer", "t/n3/mid", "t/n3/inner"], ["python3", "-I", "-c", look], timeout=120,
               flags=("--no-auto-mask",))
    j = r.j or {}
    s1, s2 = j.get("s1", {}), j.get("s2", {})
    g1, g2 = j.get("g1", 0), j.get("g2", 0)
    mid1 = (s1.get("2") or [0])[0]
    drops = sorted({str(v[1]) for v in list(s1.values()) + list(s2.values())})
    ok = g1 / max(j.get("t1", 4), 0.1) > 1.4e6 and mid1 < 1.1 * g1 + 2_500_000 and \
        23_000_000 < g1 + g2 <= 25_000_000 and drops == ["packets 0"]
    record("p_net3_quota", ok, "4 s: got %d (%.2f MB/s), quota used outer/mid/inner %s; then asked 40 MB: got %d, "
           "total %d (inner quota 25 MB), used %s; drops %s" % (
               g1, g1 / max(j.get("t1", 4), 0.1) / 1e6, [v[0] for _, v in sorted(s1.items())], g2, g1 + g2,
               [v[0] for _, v in sorted(s2.items())], drops))


def main():
    ap = argparse.ArgumentParser(description="Tests for overlapping and flattened kernel chains and bugs a, b.")
    ap.add_argument("--pasta", help="pasta binary (default: on PATH, else %s)" % A.DEFAULT_PASTA)
    ap.add_argument("--keep", action="store_true", help="keep %s afterwards" % BASE)
    ap.add_argument("--only", help="comma-separated parts: q1..q7, a, b")
    a = ap.parse_args()
    pasta = a.pasta or shutil.which("pasta") or A.DEFAULT_PASTA
    if not os.access(pasta, os.X_OK):
        sys.exit("overlap_test: error: PastaMissing no pasta at %s (install passt, or --pasta PATH)" % pasta)
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE)
    S.BASE = BASE  # S.mini runs in BASE by default; snapshot marks
    os.environ["MINI_PASTA"] = pasta
    os.environ["MINI_KERNELS_PATH"] = os.path.join(BASE, "kernels")
    os.environ["AOS_HOME"] = S.AOS_HOME
    os.environ.pop("AOS_ENV", None)
    os.environ.pop("MINI_USERNS_MAX", None)
    servers = [A.start_server() for _ in range(3)]
    pa, pb, pc = (s.server_address[1] for s in servers)
    before = S.snapshot((pa, pb, pc))
    log("test servers on the host: A %d, B %d, C %d (inside %s:<port>)" % (pa, pb, pc, HOST))
    make_files()
    make_kernels(pa, pb, pc)
    parts = [("q1", q1_dedup, ()), ("q2", q2_merge, (pa, pb, pc)), ("q3", q3_llm, ()), ("q4", q4_replace, ()),
             ("q5", q5_uid, ()), ("q6", q6_flatten, ()), ("q7", q7_effective, ()), ("a", bug_a, ()),
             ("b", bug_b, (pa,))]
    only = set(a.only.split(",")) if a.only else None
    t0 = time.monotonic()
    try:
        for name, f, args in parts:
            if not only or name in only:
                f(*args)
    finally:
        for s in servers:
            s.shutdown()
            s.server_close()
    time.sleep(1)
    after = S.snapshot((pa, pb, pc))
    left = {k: (sorted(set(after[k]) - set(before[k])) if k != "procs" else
                {p: c for p, c in after[k].items() if p not in before[k]}) for k in after}
    probes = [d for d in os.listdir("/tmp") if d.startswith("aos-probe-")]
    open_ports = [p for p in (pa, pb, pc) if socket.socket().connect_ex(("127.0.0.1", p)) == 0]
    record("cleanup", not any(left.values()) and not probes and not open_ports,
           "left over: %s; probe folders %s; test servers open: %s" % (
               {k: v for k, v in left.items() if v} or "nothing", probes or "none", open_ports or "none"))
    fails = [n for n, t in RESULTS if t == "FAIL"]
    log("\nSUMMARY %s (%d PASS, %d FAIL, %d info, %.0fs)%s" % (
        "ok" if not fails else "FAILED", sum(t == "PASS" for _, t in RESULTS), len(fails),
        sum(t == "info" for _, t in RESULTS), time.monotonic() - t0, ": " + ", ".join(fails) if fails else ""))
    if not a.keep and not fails:
        shutil.rmtree(BASE, ignore_errors=True)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
