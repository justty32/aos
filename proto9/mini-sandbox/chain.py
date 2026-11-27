"""Turns mini.py --kernels names into the chain that runs: finds names ($MINI_KERNELS_PATH, then $AOS_HOME/kernels), expands bundles (a folder whose _chain.json lists names, {"merge": [...]} or {"use": B, "replace": {...}, "without": [...]}), keeps one of each kernel file (the outer one), puts the uid kernel innermost, refuses orders that would let the agent around an llm kernel, adds the /run/user mask, groups neighbouring cgroup and mask kernels into one flattened layer, and counts the user namespaces it all needs."""

import hashlib
import ipaddress
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CHAIN = "_chain.json"   # a folder with this file is a bundle: one name that stands for a chain of kernels
MAX_BUNDLE_DEPTH = 8    # bundles inside bundles, at most this deep
KINDS = {"cg_kernel.py": "cgroup", "net_kernel.py": "net", "mask_kernel.py": "mask", "uid_kernel.py": "uid",
         "llm_kernel.py": "llm"}
AUTO_MASK = "aos/mask/run-user"
AUTO_MASK_FOR = ("cgroup", "net", "llm")  # limits that one call over D-Bus to systemd --user would get around
FLAT = ("cgroup", "mask")                 # kinds with no process of their own: neighbours are set up together
USERNS_COST = {"flat": 1, "cgroup": 1, "mask": 1, "uid": 1, "llm": 1, "net": 2, "other": 1}
USERNS_KEEP = 9   # nested user namespaces kept free for the agent's own sandboxes: 33 - 9 = 24 from the machine


class KernelError(ValueError):
    """Finding, expanding or checking kernel names went wrong; code is the error code mini prints (exit 2)."""

    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


# ------------------------------------------------------------ finding one name

def kernel_dirs():
    """Where names are looked up, first match wins: the folders in $MINI_KERNELS_PATH (separated by :), then
    $AOS_HOME/kernels."""
    dirs = [d for d in os.environ.get("MINI_KERNELS_PATH", "").split(":") if d]
    if os.environ.get("AOS_HOME"):
        dirs.append(os.path.join(os.environ["AOS_HOME"], "kernels"))
    return dirs


def kernel_program(prog, jsonfile):
    """A bare file name (cg_kernel.py) is one of mini's own programs, next to mini.py; otherwise $VARS and ~ are
    expanded and a relative path is relative to the folder of the kernel's json file."""
    if "/" not in prog and "$" not in prog:
        return os.path.join(HERE, prog)
    p = os.path.expanduser(os.path.expandvars(prog))
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(os.path.dirname(jsonfile), p))


def is_path(name):
    return name.startswith(("/", "./", "../", "~")) or name.endswith(".json")


def check_name(name):
    if ".." in name.split("/") or not name.strip("/") or "//" in name or name.startswith("_") or "/_" in name:
        raise KernelError("KernelNotFound", "kernel name %r: want a/b/c (no .., no part starting with _)" % name)


def lookup(name, dirs):
    """A name in these folders, first folder that has it wins: ("file", NAME.json) or ("bundle", NAME/). Both in one
    folder is an error: which one is meant is not guessed."""
    for d in dirs:
        f, b = os.path.join(d, name + ".json"), os.path.join(d, name)
        hf, hb = os.path.isfile(f), os.path.isfile(os.path.join(b, CHAIN))
        if hf and hb:
            raise KernelError("KernelNameClash", "kernel %s: both %s (one kernel) and %s/ (a bundle, it has %s) "
                              "exist; rename one of them" % (name, f, b, CHAIN))
        if hf:
            return "file", f
        if hb:
            return "bundle", b
    raise KernelError("KernelNotFound", "kernel %s: not found in %s" % (name, ":".join(dirs)))


def load_kernel(name, path):
    """One kernel file -> {name, kind, program, config, file, from}."""
    try:
        with open(path) as f:
            k = json.load(f)
    except ValueError as e:
        raise KernelError("KernelNotFound", "kernel %s (%s): %s" % (name, path, e))
    if not isinstance(k, dict) or not isinstance(k.get("program"), str):
        raise KernelError("KernelNotFound", "kernel %s (%s): want {\"program\": ..., \"config\": {...}}" % (name, path))
    bad = set(k) - {"description", "program", "config"}
    if bad:
        raise KernelError("KernelNotFound", "kernel %s: unknown keys %s" % (name, ", ".join(sorted(bad))))
    prog = kernel_program(k["program"], path)
    if not os.path.isfile(prog):
        raise KernelError("KernelNotFound", "kernel %s: program %s not found" % (name, prog))
    kind = KINDS.get(os.path.basename(prog), "other") if os.path.dirname(prog) == HERE else "other"
    return {"name": name, "kind": kind, "program": prog, "config": k.get("config", {}), "file": path, "from": []}


def resolve(entry, bundle=None):
    """A name -> (full name, "file" or "bundle", path). At the top (--kernels) and for a name with a / inside a
    bundle: looked up in $MINI_KERNELS_PATH, then $AOS_HOME/kernels. Inside a bundle (bundle = (its name, its
    folder)), a name without / (or starting with ./) is one of the bundle's own: cg in aos/base is aos/base/cg, found
    in that folder only. A path (/..., ~..., ....json; at the top also ./...) is that file or bundle folder."""
    if bundle and (entry.startswith("./") or "/" not in entry):
        local = entry[2:] if entry.startswith("./") else entry
        check_name(local)
        bname, bdir = bundle
        kind, path = lookup(local, [bdir])
        return (bname.rstrip("/") + "/" + local if not is_path(bname) else os.path.join(bdir, local)), kind, path
    if entry.startswith(("/", "~")) or (not bundle and is_path(entry)):
        path = os.path.abspath(os.path.expanduser(entry))
        if os.path.basename(path) == CHAIN and os.path.isfile(path):
            return entry, "bundle", os.path.dirname(path)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, CHAIN)):
            return entry, "bundle", path
        if not os.path.isfile(path):
            raise KernelError("KernelNotFound", "kernel %s: no such file (or folder with %s)" % (entry, CHAIN))
        return entry, "file", path
    check_name(entry)
    dirs = kernel_dirs()
    if not dirs:
        raise KernelError("KernelNotFound", "kernel %s: nowhere to look (set AOS_HOME, whose kernels/ holds the "
                          "kernels by name, or MINI_KERNELS_PATH)" % entry)
    kind, path = lookup(entry, dirs)
    return entry, kind, path


def entry_ok(e):
    """A chain entry: a name, {"merge": [entries]}, or {"use": name, "replace": {name: entry}, "without": [names]}."""
    if isinstance(e, str):
        return bool(e.strip())
    if not isinstance(e, dict):
        return False
    if set(e) == {"merge"}:
        return isinstance(e["merge"], list) and len(e["merge"]) >= 2 and all(entry_ok(x) for x in e["merge"])
    if "use" in e and not set(e) - {"use", "replace", "without"}:
        r, w = e.get("replace", {}), e.get("without", [])
        return isinstance(e["use"], str) and isinstance(r, dict) and all(entry_ok(v) for v in r.values()) and \
            isinstance(w, list) and all(isinstance(x, str) for x in w)
    return False


def load_chain(name, folder):
    path = os.path.join(folder, CHAIN)
    try:
        with open(path) as f:
            c = json.load(f)
    except (OSError, ValueError) as e:
        raise KernelError("KernelBundleBad", "bundle %s: %s: %s" % (name, path, e))
    if not isinstance(c, dict) or set(c) - {"description", "chain"}:
        raise KernelError("KernelBundleBad", "bundle %s: %s: want {\"description\": ..., \"chain\": [names, "
                          "outermost first]}" % (name, path))
    chain = c.get("chain")
    if not isinstance(chain, list) or not chain or not all(entry_ok(x) for x in chain):
        raise KernelError("KernelBundleBad", "bundle %s: %s: chain must be a non-empty list of names, {\"merge\": "
                          "[two or more]} or {\"use\": NAME, \"replace\": {NAME: NAME}, \"without\": [NAME]}" % (
                              name, path))
    return [x.strip() if isinstance(x, str) else x for x in chain]


# ------------------------------------------------------------ expanding (bundles, use/replace/without, merge)

class Expander:
    """Expands names into kernels, outermost first; notes: what it did on the way (replaced, left out), each
    {"text": ..., "run": print it on a normal run too}."""

    def __init__(self):
        self.notes = []

    def name(self, entry, bundle=None, stack=()):
        """One chain entry -> its kernels. stack: the bundles we are inside, as (name, real folder); a bundle that
        is already in it is a loop, more than MAX_BUNDLE_DEPTH is too deep."""
        if isinstance(entry, dict):
            if "merge" in entry:
                return [self.merge(entry["merge"], bundle, stack)]
            return self.use(entry, bundle, stack)
        full, kind, path = resolve(entry, bundle)
        if kind == "file":
            k = load_kernel(full, path)
            k["from"] = [n for n, _ in stack]
            return [k]
        return self.bundle(full, path, stack)

    def enter(self, full, path, stack):
        real = os.path.realpath(path)
        trail = [n for n, _ in stack] + [full]
        if real in [r for _, r in stack]:
            raise KernelError("KernelBundleLoop", "bundles include each other: %s" % " -> ".join(trail))
        if len(stack) >= MAX_BUNDLE_DEPTH:
            raise KernelError("KernelBundleTooDeep", "bundles nested more than %d deep: %s" % (
                MAX_BUNDLE_DEPTH, " -> ".join(trail)))
        return tuple(stack) + ((full, real),)

    def bundle(self, full, path, stack, replace=None, without=(), where=None, ctx=None):
        """A bundle's chain expanded in place. With use: replace (its chain's name -> an entry, read where the use
        is written: ctx) and without (its chain's names left out)."""
        inner = self.enter(full, path, stack)
        chain, replace = load_chain(full, path), replace or {}
        names = [e for e in chain if isinstance(e, str)]
        for k in list(replace or {}) + list(without):
            if k not in names:
                raise KernelError("KernelBundleBad", "%s: %s has no %r in its chain to replace or leave out (it has: "
                                  "%s)" % (where or "--kernels", full, k, ", ".join(names) or "no plain names"))
        out = []
        for e in chain:
            if isinstance(e, str) and e in without:
                gone = self.name(e, (full, path), inner)
                self.notes.append({"text": "%s: left out %s (without, in %s)" % (
                    where, ", ".join(k["name"] for k in gone), full), "run": False})
                continue
            if isinstance(e, str) and e in replace:
                old = self.name(e, (full, path), inner)
                new = self.name(replace[e], ctx, stack)
                for k in new:
                    k["replaced"] = ",".join(k2["name"] for k2 in old)
                self.notes.append({"text": "%s: %s replaced by %s (%s)" % (
                    where, ", ".join(k["name"] for k in old), ", ".join(k["name"] for k in new),
                    ", ".join(k["file"] if isinstance(k["file"], str) else "+".join(k["file"]) for k in new)),
                    "run": False})
                out += new
                continue
            out += self.name(e, (full, path), inner)
        return out

    def use(self, e, bundle, stack):
        full, kind, path = resolve(e["use"], bundle)
        where = stack[-1][0] if stack else "--kernels"
        if kind != "bundle":
            raise KernelError("KernelBundleBad", "%s: use %s: want a bundle (a folder with %s), %s is one kernel" % (
                where, e["use"], CHAIN, path))
        return self.bundle(full, path, stack, e.get("replace", {}), e.get("without", []), where, bundle)

    def merge(self, entries, bundle, stack):
        members = []
        for e in entries:
            ks = self.name(e, bundle, stack)
            if len(ks) != 1:
                raise KernelError("KernelMergeBad", "merge: %s stands for %d kernels (%s); merge takes single kernels "
                                  "of one kind" % (e, len(ks), ", ".join(k["name"] for k in ks)))
            members += ks
        return merged(members)


# ------------------------------------------------------------ merge: one layer out of several of one kind, never looser

def port_range(spec):
    if isinstance(spec, dict):
        spec = spec.get("port")
    a, _, b = str(spec).partition("-")
    return int(a), int(b or a)


def show_range(lo, hi):
    return lo if lo == hi else "%d-%d" % (lo, hi)


def nets_and(a, b):
    a, b = ipaddress.ip_network(str(a), strict=False), ipaddress.ip_network(str(b), strict=False)
    if a.version != b.version:
        return None
    return a if a.subnet_of(b) else (b if b.subnet_of(a) else None)


def ranges_and(a, b):
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    return (lo, hi) if lo <= hi else None


def allow_and(xs, ys):
    """Allow rules both lists let through (by address range and port range, not by text)."""
    out = []
    for x in xs:
        for y in ys:
            if x.get("proto", "tcp") != y.get("proto", "tcp"):
                continue
            n, p = nets_and(x["to"], y["to"]), ranges_and(port_range(x), port_range(y))
            if n and p:
                r = {"to": str(n), "port": show_range(*p), "proto": x.get("proto", "tcp")}
                if r not in out:
                    out.append(r)
    return out


def host_ports_and(xs, ys):
    out = []
    for x in xs:
        for y in ys:
            px = x.get("proto", "tcp") if isinstance(x, dict) else "tcp"
            py_ = y.get("proto", "tcp") if isinstance(y, dict) else "tcp"
            p = ranges_and(port_range(x), port_range(y)) if px == py_ else None
            if p:
                r = show_range(*p) if px == "tcp" else {"port": show_range(*p), "proto": px}
                if r not in out:
                    out.append(r)
    return out


def smallest(vals, conv):
    v = [x for x in vals if x is not None]
    return min(v, key=conv) if v else None


def same(names, key, vals):
    if len({json.dumps(v, sort_keys=True) for v in vals}) > 1:
        raise KernelError("KernelMergeBad", "merge %s: %s differs (%s); a merge can only take the tighter of two "
                          "values, these cannot be compared: keep them as two layers, or make them the same" % (
                              ", ".join(names), key, " vs ".join(json.dumps(v) for v in vals)))
    return vals[0]


def merge_cgroup(names, cs):
    import cg_kernel
    p = [cg_kernel.load(c) for c in cs]
    out = {}
    for k in ("cpu", "mem", "pids"):
        v = [x[k] for x in p if x[k] is not None]
        if v:
            out[k] = min(v) if k == "pids" else cg_kernel.show(k, min(v))
    return out


def merge_mask(names, cs):
    hides = ("tmpfs", "null")
    paths, order = {}, []
    for c in cs:
        for p in c.get("paths", [{"path": "/run/user/{uid}", "how": "tmpfs"}]):
            p = {"path": p} if isinstance(p, str) else p
            key, how = os.path.normpath(str(p["path"])), p.get("how", "tmpfs")
            if key not in paths:
                paths[key] = how
                order.append(key)
            elif paths[key] != how:
                if paths[key] in hides and how in hides:
                    raise KernelError("KernelMergeBad", "merge %s: %s is covered as tmpfs (a folder) in one and null "
                                      "(a file) in another" % (", ".join(names), key))
                if how in hides:
                    paths[key] = how
    keeps = [[os.path.normpath(str(k)) for k in c.get("keep", [])] for c in cs]
    covers = [[os.path.normpath(str((p if isinstance(p, dict) else {"path": p})["path"])) for p in
               c.get("paths", [{"path": "/run/user/{uid}"}]) if (p if isinstance(p, dict) else {}).get("how", "tmpfs")
               == "tmpfs"] for c in cs]
    keep = []
    for k in [k for ks in keeps for k in ks]:
        # a hole stays only if every layer that covers a folder above it leaves the same hole (as when nested)
        if k not in keep and all(k in kp for kp, cv in zip(keeps, covers) if any(k.startswith(c + "/") for c in cv)):
            keep.append(k)
    out = {"paths": [{"path": k, "how": paths[k]} for k in order]}
    if keep:
        out["keep"] = keep
    return out


def merge_net(names, cs):
    import net_kernel
    out = {}
    allow = [r for r in cs[0].get("allow", [])]
    hp = list(cs[0].get("host_ports", []))
    for c in cs[1:]:
        allow, hp = allow_and(allow, c.get("allow", [])), host_ports_and(hp, c.get("host_ports", []))
    out["allow"], out["host_ports"] = allow, hp
    for k, conv in (("quota", net_kernel.size_bytes), ("up", net_kernel.rate_bits), ("down", net_kernel.rate_bits),
                    ("burst", int), ("max_attach", int), ("status_interval", float)):
        v = smallest([c.get(k) for c in cs], conv)
        if v is not None:
            out[k] = v
    for k in ("subnet", "host_addr"):
        v = [c[k] for c in cs if k in c]
        if v:
            out[k] = same(names, k, v)
    unknown = set(k for c in cs for k in c) - set(out) - {"description", "allow", "host_ports"}
    if unknown:
        raise KernelError("KernelMergeBad", "merge %s: unknown net keys %s" % (", ".join(names), ", ".join(unknown)))
    return out


def merge_llm(names, cs):
    models = [m for m in (cs[0].get("models") or []) if all(m in (c.get("models") or []) for c in cs[1:])]
    if not models:
        raise KernelError("KernelMergeBad", "merge %s: no model is allowed by all of them (%s)" % (
            ", ".join(names), " vs ".join(",".join(c.get("models") or []) for c in cs)))
    out = {"models": models, "limit": min(c.get("limit", 0) for c in cs)}
    up = same(names, "upstream", [c.get("upstream") or "outer" for c in cs])
    if up != "outer":
        out["upstream"] = up
    for k in ("state", "fake_script"):
        v = same(names, k, [c.get(k) for c in cs])
        if v is not None:
            out[k] = v
    return out


def merge_uid(names, cs):
    return {"uid": same(names, "uid", [c.get("uid") for c in cs])}


MERGE = {"cgroup": merge_cgroup, "mask": merge_mask, "net": merge_net, "llm": merge_llm, "uid": merge_uid}


def merged(members):
    """Several kernels of one kind -> one kernel whose config is never looser than nesting them would be."""
    names = [k["name"] for k in members]
    kinds = {k["kind"] for k in members}
    if "other" in kinds:
        raise KernelError("KernelMergeBad", "merge %s: %s is not one of mini's own kernels (its program is %s); mini "
                          "does not know how to merge its settings" % (", ".join(names), next(
                              k["name"] for k in members if k["kind"] == "other"), next(
                              k["program"] for k in members if k["kind"] == "other")))
    if len(kinds) != 1:
        raise KernelError("KernelMergeBad", "merge %s: kinds differ (%s); merge takes kernels of one kind" % (
            ", ".join(names), ", ".join("%s %s" % (k["kind"], k["name"]) for k in members)))
    kind = kinds.pop()
    try:
        cfg = MERGE[kind](names, [k["config"] or {} for k in members])
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        if isinstance(e, KernelError):
            raise
        raise KernelError("KernelMergeBad", "merge %s: %s" % (", ".join(names), e))
    return {"name": "+".join(names), "kind": kind, "program": members[0]["program"], "config": cfg,
            "file": [k["file"] for k in members], "from": members[0]["from"], "merged": members}


# ------------------------------------------------------------ after expanding: one of each, uid last, checks, the mask

def file_key(k):
    files = k["file"] if isinstance(k["file"], list) else [k["file"]]
    return tuple(os.path.realpath(f) if os.path.isfile(f) else f for f in files)


def where_from(k):
    return ">".join(k["from"]) if k.get("from") else "--kernels"


def dedup(ks, notes):
    """The same kernel file twice (two bundles both use aos/llm/fake): keep the outermost, say so in one line."""
    seen, out = {}, []
    for k in ks:
        key = file_key(k)
        if key in seen:
            seen[key].append(k)
            continue
        seen[key] = [k]
        out.append(k)
    for same_ in seen.values():
        if len(same_) > 1:
            n = len(same_)
            notes.append({"text": "%s appears %s (from %s); kept the outer one" % (
                same_[0]["name"], "twice" if n == 2 else "%d times" % n, ", ".join(where_from(k) for k in same_)),
                "run": True})
    return out


def uid_last(ks, notes):
    """At most one uid number; the uid kernel goes innermost (the layers after it could not read your home)."""
    us = [k for k in ks if k["kind"] == "uid"]
    if not us:
        return ks
    nums = []
    for k in us:
        n = (k["config"] or {}).get("uid")
        if n not in nums:
            nums.append(n)
    if len(nums) > 1:
        raise KernelError("KernelUidClash", "uid kernels with different numbers: %s; keep one of them (leave one out of "
                          "--kernels, or {\"use\": ..., \"without\": [...]} in a %s)" % (
                              ", ".join("%s (uid %s, from %s)" % (k["name"], (k["config"] or {}).get("uid"),
                                                                    where_from(k)) for k in us), CHAIN))
    rest = [k for k in ks if k["kind"] != "uid"]
    if len(us) > 1:
        notes.append({"text": "uid %s appears %s (%s); kept the outer one" % (
            nums[0], "twice" if len(us) == 2 else "%d times" % len(us), ", ".join("%s from %s" % (k["name"], where_from(k)) for k in us)), "run": True})
    if ks.index(us[0]) != len(rest):
        notes.append({"text": "moved %s innermost (nothing may run after a uid kernel: the layers after it could not "
                      "read your home)" % us[0]["name"], "run": True})
    return rest + [us[0]]


def shown(k):
    """aos/base/cg (from aos/base)."""
    return k["name"] + (" (from %s)" % ">".join(k["from"]) if k.get("from") else "")


def llm_unchained(ks):
    """Two llm kernels where the inner one does not go through the outer one (upstream other than "outer"): the
    agent would have two budgets, or one around the other. One sentence for the first such pair, or None."""
    llms = [k for k in ks if k["kind"] == "llm"]
    for outer, inner in zip(llms, llms[1:]):
        up = (inner["config"] or {}).get("upstream")
        if up not in (None, "", "outer"):
            return ("%s (llm kernel) sits inside %s (llm kernel) but does not go through it (its upstream is %r): the "
                    "agent would get two budgets, or one around the other. Set \"upstream\": \"outer\" in %s, or "
                    "keep only one of the two" % (shown(inner), shown(outer), up, inner["name"]))
    return None


def port_in(spec, port):
    """A net kernel port spec (4000, "4000", "4000-4010", or {"port": ...}) covers this port?"""
    try:
        lo, hi = port_range(spec)
        return lo <= port <= hi
    except ValueError:
        return False


def lets_through(c, ip, port):
    """Which part of a net kernel's config lets tcp to ip:port through: "host_ports" (this machine's loopback),
    "allow list", or None. Loopback inside is the sandbox's own lo, so for it only host_ports count."""
    if ip.is_loopback:
        return "host_ports" if any(port_in(p, port) for p in c.get("host_ports") or []) else None
    for r in c.get("allow") or []:
        try:
            to = ipaddress.ip_network(str(r.get("to")), strict=False)
        except (AttributeError, ValueError):
            continue
        if r.get("proto", "tcp") == "tcp" and port_in(r, port) and ip.version == to.version and ip in to:
            return "allow list"
    return None


def llm_bypasses(ks):
    """An llm kernel whose upstream is ip:port, and a net kernel further in that lets that very ip:port through
    (host_ports for this machine's loopback, an allow rule for any other address): the agent could talk to the
    upstream directly, around the llm kernel's count and model list. One sentence per such pair."""
    out = []
    for i, k in enumerate(ks):
        up = str(k["config"].get("upstream", "")) if k["kind"] == "llm" else ""
        m = re.match(r"^https?://(\[[^]]*\]|[^/:]+)(?::(\d+))?(/|$)", up)
        if not m:
            continue
        host, port = m.group(1).strip("[]"), int(m.group(2) or (443 if up.startswith("https") else 80))
        try:
            ip = ipaddress.ip_address("127.0.0.1" if host == "localhost" else host)
        except ValueError:
            continue  # a host name: no address to compare with
        for n in ks[i + 1:]:
            how = lets_through(n["config"], ip, port) if n["kind"] == "net" else None
            if how:
                out.append("%s (net kernel) lets %s:%d through (its %s), and it sits inside %s (llm kernel), whose "
                           "upstream is %s: the agent could reach the upstream directly, around the llm kernel's count "
                           "and model list. Put %s before %s in --kernels (outside it), or take port %d out of its %s"
                           % (shown(n), host, port, how, shown(k), up, n["name"], k["name"], port, how))
    return out


def covers_run_user(k):
    """Does this mask kernel cover /run/user/<uid> (its default when it lists no paths)?"""
    paths = k["config"].get("paths")
    if paths is None:
        return True
    return any((p if isinstance(p, str) else p.get("path", "")).rstrip("/") in ("/run/user/{uid}",
               "/run/user/%d" % os.getuid(), "/run/user") for p in paths)


def add_auto_mask(ks):
    """With a cgroup, net or llm kernel on and nothing covering /run/user/<uid>: add aos/mask/run-user, innermost
    (just before a uid kernel, which must stay last), so nothing inside can ask systemd --user over D-Bus for a
    process outside every limit. Returns the new list and whether it added one."""
    if not any(k["kind"] in AUTO_MASK_FOR for k in ks) or any(k["kind"] == "mask" and covers_run_user(k) for k in ks):
        return ks, False
    try:
        m = Expander().name(AUTO_MASK)
        if len(m) != 1 or m[0]["kind"] != "mask":
            raise ValueError("not one mask kernel")
        m = m[0]
    except (OSError, ValueError):  # not in the kernels folders: the same thing, built in
        m = {"name": AUTO_MASK, "kind": "mask", "program": os.path.join(HERE, "mask_kernel.py"),
             "config": {"paths": [{"path": "/run/user/{uid}", "how": "tmpfs"}]}, "file": "(built in)", "from": []}
    m = dict(m, auto=True)
    at = next((i for i, k in enumerate(ks) if k["kind"] == "uid"), len(ks))
    return ks[:at] + [m] + ks[at:], True


# ------------------------------------------------------------ flattening and counting user namespaces

def plan(ks):
    """Groups of neighbouring kernels that run as one layer: a run of cgroup and mask kernels (no net or llm kernel
    in between: their programs are counted in the cgroup outside them, and a mask written before them hides things
    from them too) is one flattened layer; every other kernel is its own. Returns lists of indexes into ks."""
    out = []
    for i, k in enumerate(ks):
        if out and k["kind"] in FLAT and all(ks[j]["kind"] in FLAT for j in out[-1]):
            out[-1].append(i)
        else:
            out.append([i])
    return out


def group_kind(ks, g):
    return "flat" if len(g) > 1 else ks[g[0]]["kind"]


def userns_needed(ks, groups):
    """Nested user namespaces this chain makes: cgroup, mask, uid, llm and a flattened layer 1 each, net 2 (its outer
    netns's own and the inner layer's), a kernel of your own 1 (a guess), the innermost step 1 (2 when no kernel at
    all: one more to lock the declarations). Returns (total, [(what, n), ...])."""
    parts = [("%s %s" % (group_kind(ks, g), "+".join(ks[i]["name"] for i in g) if len(g) < 4 else
                         "%s..%s (%d)" % (ks[g[0]]["name"], ks[g[-1]]["name"], len(g))),
              USERNS_COST[group_kind(ks, g)]) for g in groups]
    parts.append(("innermost step", 1 if ks else 2))
    return sum(n for _, n in parts), parts


def userns_summary(ks, groups):
    """The same count by kind: "net 13 x 2, flat 1, innermost step 1"."""
    by = {}
    for g in groups:
        by.setdefault(group_kind(ks, g), [0, USERNS_COST[group_kind(ks, g)]])[0] += 1
    return ", ".join("%s %s" % (k, "%d x %d" % (n, c) if n > 1 else c) for k, (n, c) in by.items()) + \
        ", innermost step %d" % (1 if ks else 2)


def sha256(f):
    try:
        with open(f, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return ""


def expand_all(names, auto_mask=True):
    """--kernels names -> (kernels, notes, auto mask added?). Raises KernelError."""
    ex = Expander()
    ks = []
    for n in names:
        ks += ex.name(n)
    ks = dedup(ks, ex.notes)
    ks = uid_last(ks, ex.notes)
    msg = llm_unchained(ks)
    if msg:
        raise KernelError("KernelOrderBad", msg + ". Nothing was started.")
    bad = llm_bypasses(ks)  # before anything runs (--dry-run too): this order is refused, not warned about
    if bad:
        more = " (and %d more like it)" % (len(bad) - 1) if len(bad) > 1 else ""
        raise KernelError("KernelOrderBad", "%s%s. Nothing was started." % (bad[0], more))
    added = False
    if auto_mask:
        ks, added = add_auto_mask(ks)
    return ks, ex.notes, added
