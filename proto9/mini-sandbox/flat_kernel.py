#!/usr/bin/env python3
"""Flattened layer for mini (nests): cgroup and mask kernels that sit next to each other in a chain (no net or llm kernel between them), set up by one program in one user namespace: one cgroup with the tightest limits of them all, every mask path mounted in the order written (one table), each of them still declared in its own folder and its own line of .aos/kernels (with flattened = the layers done together); then the next layer, with the declarations locked read-only."""

import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cg_kernel  # noqa: E402
import mask_kernel  # noqa: E402
import nest  # noqa: E402

PROG = "flat-kernel"
KINDS = ("cgroup", "mask")


def tightest(cs):
    """cpu, mem, pids: the smallest any of these layers asks (None = no limit)."""
    out = {}
    for k in ("cpu", "mem", "pids"):
        v = [c[k] for c in cs if c[k] is not None]
        out[k] = min(v) if v else None
    return out


def stage1(cfg, nxt):
    layers = cfg.get("layers")
    if not isinstance(layers, list) or not layers or not all(
            isinstance(l, dict) and l.get("kind") in KINDS and isinstance(l.get("name"), str) for l in layers):
        nest.fail(PROG, "ConfigBad", "want {\"layers\": [{\"kind\": \"cgroup\"|\"mask\", \"name\": ..., \"from\": ..., "
                  "\"config\": {...}}, ...]}", 2)
    parsed = []
    for l in layers:
        try:
            parsed.append(cg_kernel.load(l.get("config") or {}) if l["kind"] == "cgroup" else
                          mask_kernel.resolve(l.get("config") or {}))
        except (ValueError, KeyError, TypeError) as e:
            nest.fail(PROG, "ConfigBad", "%s: %s" % (l["name"], e), 2)
    names = ", ".join(l["name"] for l in layers)
    nest.need_userns(PROG, 1, "flattened layer (%s)" % names)
    cgs = [p for l, p in zip(layers, parsed) if l["kind"] == "cgroup"]
    if cgs:  # one cgroup, the tightest of them all (nested ones would give the same: each limit is the smallest)
        try:
            cg_kernel.enter_child(tightest(cgs))
        except (OSError, RuntimeError) as e:
            nest.fail(PROG, "CgroupFailed", str(e))
    try:
        with open(os.path.join(os.environ["AOS_ENV"], ".aos", "kernels")) as f:
            first = len([x for x in f.read().splitlines() if x.strip()]) + 1
    except (KeyError, OSError):
        nest.fail(PROG, "ArgumentsBad", "AOS_ENV is not set (start kernels through mini.py --kernels)", 2)
    nums = list(range(first, first + len(layers)))
    eff, covered, table = cg_kernel.outer_limits(), [], []
    for l, p in zip(layers, parsed):  # each layer declared as if it had run alone, in order
        env = nest.new_env(l["kind"], l["name"], l.get("from"))
        nest.ME["flat"] = nums
        if l["kind"] == "cgroup":
            eff = cg_kernel.effective(p, eff)
            nest.declare(env, "cgroup", cg_kernel.cell(eff, p), cg_kernel.DESCRIPTION)
        else:
            paths, keep = p
            outer = nest.decl_read(nest.env_outer(), "mask", "paths", "")
            lines = [x for x in outer.splitlines() if x.strip()] + mask_kernel.lines_for(paths, keep, covered)
            nest.declare(env, "mask", {"paths": "\n".join(lines)}, mask_kernel.DESCRIPTION)
            table += [dict(x, keep=keep) for x in paths]
        os.environ["AOS_ENV"] = env
    argv = ["unshare"] + nest.userns_args() + ["--mount"] + (["--cgroup"] if cgs else []) + ["--"] + \
        nest.py(os.path.abspath(__file__)) + ["--stage2", "--json", json.dumps({"cg": bool(cgs), "table": table}),
                                              "--"] + nxt
    os.execvp(argv[0], argv)


def stage2(cfg, nxt):
    """In the new user and mount (and cgroup) namespace: our cgroup is the root now; mount the table in order (a
    later path under an earlier tmpfs finds nothing there, as it would one layer further in); lock the
    declarations."""
    if cfg.get("cg"):
        try:
            nest.cg_remount()
            nest.cg_layout("inner")
        except (OSError, RuntimeError) as e:
            nest.fail(PROG, "CgroupFailed", "inside: %s" % e)
    for p in cfg.get("table", []):
        try:
            mask_kernel.cover(p, p["keep"])
        except OSError as e:
            nest.fail(PROG, "MaskFailed", "%s %s: %s" % (p["how"], p["path"], e))
    nest.lock_env(PROG)
    try:
        os.execvp(nxt[0], nxt)
    except OSError as e:
        nest.fail(PROG, "ExecFailed", "%s: %s" % (nxt[0], e.strerror), 127)


def main():
    opts, cfg, nxt = nest.parse(PROG, sys.argv[1:])
    if opts.get("stage2"):
        return stage2(cfg, nxt)
    stage1(cfg, nxt)


if __name__ == "__main__":
    main()
