#!/usr/bin/env python3
"""File mask kernel for mini (nests): in its own user and mount namespace covers the listed paths (default /run/user/<uid>, the way out through systemd --user and D-Bus) with an empty tmpfs, /dev/null or a read-only bind, keeps the chain's aos folder visible, declares aos/mask, then runs the next layer there, with the declarations locked read-only."""

import json
import os
import stat
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nest  # noqa: E402

PROG = "mask-kernel"
DEFAULT = [{"path": "/run/user/{uid}", "how": "tmpfs"}]
HOWS = ("tmpfs", "null", "ro")


def resolve(cfg):
    bad = set(cfg) - {"paths", "keep", "description"}
    if bad:
        raise ValueError("unknown keys %s (known: paths, keep)" % ", ".join(sorted(bad)))
    subst = {"uid": nest.host_file("host_uid") or str(os.getuid()), "home": os.path.expanduser("~")}
    out = []
    for i, p in enumerate(cfg.get("paths", DEFAULT)):
        if isinstance(p, str):
            p = {"path": p}
        how = p.get("how", "tmpfs")
        if how not in HOWS:
            raise ValueError("paths[%d]: how must be one of %s" % (i, ", ".join(HOWS)))
        path = os.path.normpath(str(p["path"]).format(**subst))
        if not path.startswith("/"):
            raise ValueError("paths[%d]: want an absolute path (got %s)" % (i, path))
        out.append({"path": path, "how": how})
    keep = [os.path.normpath(str(k).format(**subst)) for k in cfg.get("keep", [])]
    env = nest.env_outer()
    if env:
        keep.append(os.path.dirname(env))  # the chain's run folder: the declarations the inner layers read
    return out, keep


def under(path, folder):
    return path == folder or path.startswith(folder.rstrip("/") + "/")


def lines_for(paths, keep, covered):
    """The declaration lines of one mask layer: absent (not there, or already under an empty tmpfs an earlier
    layer of the same flattened table put up, and not in one of its holes), or how and path, then its holes.
    covered: (path, holes) of the tmpfs covers so far, updated."""
    out = []
    for p in paths:
        hidden = any(under(p["path"], c) and not any(under(p["path"], h) for h in holes) and p["path"] != c
                     for c, holes in covered)
        if hidden or not os.path.lexists(p["path"]):
            out.append("absent %s" % p["path"])
            continue
        out.append("%s %s" % (p["how"], p["path"]))
        holes = [k for k in keep if p["how"] == "tmpfs" and k.startswith(p["path"] + "/")]
        out += ["hole %s" % k for k in holes]
        if p["how"] == "tmpfs":
            covered.append((p["path"], holes))
    return out


DESCRIPTION = ("mask kernel: these paths are covered for everything inside (tmpfs = an empty folder, null = an empty "
               "file, ro = read-only); a hole is a path left visible inside a covered folder")


def stage1(opts, cfg, nxt):
    try:
        paths, keep = resolve(cfg)
    except (ValueError, KeyError) as e:
        nest.fail(PROG, "ConfigBad", str(e), 2)
    nest.need_userns(PROG, 1, "mask kernel %s" % opts["name"])
    env = nest.new_env("mask", opts["name"], opts.get("from"))
    outer = nest.decl_read(nest.env_outer(), "mask", "paths", "")
    lines = [l for l in outer.splitlines() if l.strip()] + lines_for(paths, keep, [])
    nest.declare(env, "mask", {"paths": "\n".join(lines)}, DESCRIPTION)
    os.environ["AOS_ENV"] = env
    spec = json.dumps({"paths": paths, "keep": keep})
    argv = ["unshare"] + nest.userns_args() + ["--mount", "--"] + nest.py(os.path.abspath(__file__)) + \
        ["--stage2", "--name", opts["name"], "--json", spec, "--"] + nxt
    os.execvp(argv[0], argv)


def cover(p, keep):
    path, how = p["path"], p["how"]
    if not os.path.lexists(path):
        return
    if how == "tmpfs":
        holes = []
        for k in keep:
            if k.startswith(path + "/") and os.path.exists(k):
                holes.append((k, os.open(k, nest.O_PATH)))  # opened before the cover hides it
        mode = stat.S_IMODE(os.stat(path).st_mode) if os.path.isdir(path) else 0o755
        nest.mount("tmpfs", path, "tmpfs", nest.MS_NOSUID | nest.MS_NODEV, "size=1m,mode=%o" % mode)
        for k, fd in holes:
            os.makedirs(k, exist_ok=True)
            nest.mount("/proc/self/fd/%d" % fd, k, None, nest.MS_BIND | nest.MS_REC)
            os.close(fd)
    elif how == "null":
        if os.path.isdir(path):
            raise OSError(21, "%s is a folder (use tmpfs)" % path)
        nest.mount("/dev/null", path, None, nest.MS_BIND)
    else:  # ro: bind it onto itself, then make that bind read-only (keeping the flags it already has, or EPERM)
        nest.mount(path, path, None, nest.MS_BIND | nest.MS_REC)
        nest.mount(None, path, None, nest.MS_BIND | nest.MS_REMOUNT | nest.MS_RDONLY | nest.mount_flags(path))


def stage2(opts, cfg, nxt):
    for p in cfg["paths"]:
        try:
            cover(p, cfg["keep"])
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
        return stage2(opts, cfg, nxt)
    stage1(opts, cfg, nxt)


if __name__ == "__main__":
    main()
