#!/usr/bin/env python3
"""cgroup kernel for mini (nests): makes a child cgroup under its own with cpu, memory and pids limits, moves into it, gives the inner layers their own cgroup namespace (they cannot see or raise these limits) and declares aos/cgroup; then runs the next layer there, with the declarations locked read-only."""

import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nest  # noqa: E402

PROG = "cg-kernel"
SIZE = re.compile(r"^(\d+(?:\.\d+)?)\s*([KMGT]?)B?$", re.I)
MULT = {"": 1, "K": 1 << 10, "M": 1 << 20, "G": 1 << 30, "T": 1 << 40}


def mem_bytes(v):
    if v is None or v == "":
        return None
    if isinstance(v, int):
        return v
    m = SIZE.match(str(v).strip())
    if not m:
        raise ValueError("mem %r: want bytes or a number with K, M, G (1024-based), e.g. 512M" % v)
    return int(float(m.group(1)) * MULT[m.group(2).upper()])


def cpu_pct(v):
    if v is None or v == "":
        return None
    m = re.match(r"^(\d+(?:\.\d+)?)%?$", str(v).strip())
    if not m or float(m.group(1)) <= 0:
        raise ValueError("cpu %r: want a percent of one core, e.g. 20%%" % v)
    return float(m.group(1))


def load(cfg):
    bad = set(cfg) - {"cpu", "mem", "pids", "description"}
    if bad:
        raise ValueError("unknown keys %s (known: cpu, mem, pids)" % ", ".join(sorted(bad)))
    pids = cfg.get("pids")
    if pids is not None and (not isinstance(pids, int) or pids < 1):
        raise ValueError("pids: want an integer >= 1")
    return {"cpu": cpu_pct(cfg.get("cpu")), "mem": mem_bytes(cfg.get("mem")), "pids": pids}


def show(k, v):
    if v is None:
        return "max"
    if k == "cpu":
        return "%g%%" % v
    if k == "mem":
        for u in ("G", "M", "K"):
            if v % MULT[u] == 0:
                return "%d%s" % (v // MULT[u], u)
    return str(v)


def outer_limits():
    """What the outer cgroup kernels declared (already the tightest of all of them)."""
    env = nest.env_outer()
    out = {}
    for k, conv in (("cpu", cpu_pct), ("mem", mem_bytes), ("pids", int)):
        v = nest.decl_read(env, "cgroup", k)
        out[k] = None if v in (None, "", "max") else conv(v)
    return out


def set_limits(d, c):
    def w(name, text):
        with open(os.path.join(d, name), "w") as f:
            f.write(text)
    if c["cpu"] is not None:
        w("cpu.max", "%d 100000" % max(1000, int(c["cpu"] * 1000)))
    if c["mem"] is not None:
        w("memory.max", str(c["mem"]))
        try:
            w("memory.swap.max", "0")  # otherwise it goes to swap first instead of being killed at the limit
        except FileNotFoundError:
            pass
    if c["pids"] is not None:
        w("pids.max", str(c["pids"]))


def stage1(opts, cfg, nxt):
    try:
        c = load(cfg)
    except ValueError as e:
        nest.fail(PROG, "ConfigBad", str(e), 2)
    try:
        d = nest.cg_dir()
        me = os.getpid()
        leaf = "k-%d" % me
        if not os.access(os.path.join(d, "cgroup.procs"), os.W_OK):
            raise PermissionError("%s is not ours to change (run under mini.py --kernels, which makes a delegated "
                                  "scope)" % d)
        others = [p for p in nest.cg_procs(d) if p != me]
        if not others:  # the usual case: the outer layer left us alone in its cgroup
            child = os.path.join(d, leaf)
            os.makedirs(child, exist_ok=True)
            nest.cg_move(0, child)
            nest.cg_enable(d)
            set_limits(child, c)
        elif not nest.cg_init_ns() and nest.cg_path() != "/":
            # inside someone's sandbox, next to other processes (e.g. mini started by the agent): a sibling under
            # our parent, which is still inside the namespace root, so the outer limits hold for it too
            child = os.path.join(os.path.dirname(d), leaf)
            os.makedirs(child, exist_ok=True)
            set_limits(child, c)
            nest.cg_move(0, child)
        else:
            raise RuntimeError("cgroup %s has other processes (%s) and no parent of ours to put a sibling in" % (
                d, " ".join(map(str, others[:5]))))
    except (OSError, RuntimeError) as e:
        nest.fail(PROG, "CgroupFailed", str(e))
    outer = outer_limits()
    eff = {}
    for k in ("cpu", "mem", "pids"):
        o, m = outer.get(k), c[k]
        eff[k] = m if o is None else (o if m is None else min(o, m))
        if o is not None and (m is None or m > o):
            nest.warn(PROG, "%s: %s asks %s, an outer layer gives %s; %s applies" % (
                opts["name"], k, show(k, m), show(k, o), show(k, o)))
    env = nest.new_env("cgroup", opts["name"], opts.get("from"))
    nest.declare(env, "cgroup", {
        "cpu": show("cpu", eff["cpu"]), "mem": show("mem", eff["mem"]), "pids": show("pids", eff["pids"]),
        "asked": "cpu %s mem %s pids %s" % (show("cpu", c["cpu"]), show("mem", c["mem"]), show("pids", c["pids"])),
        "namespace": "own (you see your cgroup as /, cannot raise these limits or move out)",
    }, "cgroup kernel: cpu (percent of one core), mem, pids for everything inside; the tightest of all layers "
       "applies")
    os.environ["AOS_ENV"] = env
    argv = ["unshare"] + nest.userns_args() + ["--mount", "--cgroup", "--"] + nest.py(os.path.abspath(__file__)) + \
        ["--stage2", "--name", opts["name"], "--"] + nxt
    os.execvp(argv[0], argv)


def stage2(opts, nxt):
    """In the new user, mount and cgroup namespaces: our cgroup is the root now; lock the declarations."""
    try:
        nest.cg_remount()
        nest.cg_layout("inner")
    except (OSError, RuntimeError) as e:
        nest.fail(PROG, "CgroupFailed", "inside: %s" % e)
    nest.lock_env(PROG)
    try:
        os.execvp(nxt[0], nxt)
    except OSError as e:
        nest.fail(PROG, "ExecFailed", "%s: %s" % (nxt[0], e.strerror), 127)


def main():
    opts, cfg, nxt = nest.parse(PROG, sys.argv[1:])
    if opts.get("stage2"):
        return stage2(opts, nxt)
    stage1(opts, cfg, nxt)


if __name__ == "__main__":
    main()
