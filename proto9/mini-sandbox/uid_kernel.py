#!/usr/bin/env python3
"""uid kernel for mini (nests): runs the next layer as uid N (outside: one of your subordinate ids) with no supplementary groups, no capabilities and no_new_privs, and declares aos/uid (locked read-only, like every kernel's); must be the last kernel, because the layers after it can no longer read your 700 home or write the cgroup files."""

import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nest  # noqa: E402

PROG = "uid-kernel"


def stage2(nxt):
    """In the new user and mount namespace, still uid 0 there (you): lock the declarations, then switch."""
    nest.lock_env(PROG)
    try:
        os.execvp(nxt[0], nxt)
    except OSError as e:
        nest.fail(PROG, "ExecFailed", "%s: %s" % (nxt[0], e.strerror), 127)


def main():
    opts, cfg, nxt = nest.parse(PROG, sys.argv[1:])
    if opts.get("stage2"):
        return stage2(nxt)
    bad = set(cfg) - {"uid", "description"}
    uid = cfg.get("uid")
    if bad or not isinstance(uid, int) or uid < 1:
        nest.fail(PROG, "ConfigBad", "want {\"uid\": N} with N >= 1 (a subordinate id; 0 = you, no kernel needed)", 2)
    sub = nest.host_subuid()
    if sub and uid > sub[1]:
        nest.fail(PROG, "NoSubids", "uid %d is outside your %d subordinate ids" % (uid, sub[1]), 2)
    nest.need_userns(PROG, 1, "uid kernel %s" % opts["name"])
    env = nest.new_env("uid", opts["name"], opts.get("from"))
    nest.declare(env, "uid", {"uid": str(uid), "outside": str(sub[0] + uid - 1) if sub else "unknown"},
                 "uid kernel: everything inside runs as this uid (outside: one of your subordinate ids), without "
                 "groups or capabilities")
    os.environ["AOS_ENV"] = env
    argv = ["unshare"] + nest.userns_args() + ["--mount", "--"] + nest.py(os.path.abspath(__file__)) + \
        ["--stage2", "--", "setpriv", "--reuid=%d" % uid, "--regid=%d" % uid, "--clear-groups", "--inh-caps=-all",
         "--bounding-set=-all", "--no-new-privs", "--"] + nxt
    os.execvp(argv[0], argv)


if __name__ == "__main__":
    main()
