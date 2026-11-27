"""What a mini --kernels chain gives the agent after all its layers, computed before anything starts: the effective value of each limit and which layer decided it (blame), the settings an inner layer wrote looser than an outer one (the outer one applies), the lock (every layer's file, hash and config), mini.py --explain and --diff; written into $AOS_ENV/.aos/effective/ and .aos/lock.json."""

import json
import os

import cg_kernel
import chain
import net_kernel

DESCRIPTION = ("what the agent gets after all layers, computed by mini.py before it started them: one folder per kind, "
               "one file per field; blame says which layer decided each value (mini.py --explain prints the same)")


# ------------------------------------------------------------ the lock: every layer, as it will run

def records(ks, groups, first, outer=()):
    """One record per layer (the lock): layer, kind, name, from, file, sha256, config; plus real (which real layer
    it runs in: the same number for layers flattened together), auto, replaced, merged when they apply. outer: the
    records of an outer chain (mini started inside a sandbox), numbered before ours."""
    out = [dict(r, outer=True) for r in outer]
    real = {}
    for gi, g in enumerate(groups):
        for i in g:
            real[i] = gi + 1
    for i, k in enumerate(ks):
        files = k["file"] if isinstance(k["file"], list) else [k["file"]]
        r = {"layer": first + i, "kind": k["kind"], "name": k["name"], "from": ">".join(k.get("from") or []),
             "file": k["file"], "sha256": [chain.sha256(f) for f in files] if len(files) > 1 else chain.sha256(files[0]),
             "config": k["config"], "real": real.get(i, 0)}
        if len(groups[real[i] - 1]) > 1:
            r["flattened"] = [first + j for j in groups[real[i] - 1]]
        for x in ("auto", "replaced"):
            if k.get(x):
                r[x] = k[x]
        if k.get("merged"):
            r["merged"] = [m["name"] for m in k["merged"]]
        out.append(r)
    return out


def who(r):
    return "layer %d %s%s" % (r["layer"], r["name"], " from " + r["from"] if r.get("from") else "")


# ------------------------------------------------------------ effective values

class Eff:
    """kind -> {field: [value lines]}, blame: kind -> [lines], looser: [lines]."""

    def __init__(self):
        self.v, self.blame, self.looser = {}, {}, []

    def put(self, kind, field, values, blames):
        self.v.setdefault(kind, {})[field] = values
        self.blame.setdefault(kind, []).extend(blames)

    def loose(self, r, text):
        if not r.get("outer"):
            self.looser.append("%s: %s" % (who(r), text))


def subst():
    """{uid} and {home} as the mask kernel fills them in."""
    try:
        uid = open(os.path.join(os.environ.get("AOS_ENV") or "/", ".aos", "host_uid")).read().strip()
    except OSError:
        uid = ""
    return {"uid": uid or str(os.getuid()), "home": os.path.expanduser("~")}


def cgroup(e, rs):
    rs = [r for r in rs if r["kind"] == "cgroup"]
    if not rs:
        return
    cur = {"cpu": None, "mem": None, "pids": None}
    by = {}
    for r in rs:
        try:
            c = cg_kernel.load(r["config"] or {})
        except ValueError:
            continue
        for f in cur:
            v = c[f]
            if v is None:
                continue
            if cur[f] is None or v < cur[f]:
                cur[f], by[f] = v, r
            elif v > cur[f]:
                e.loose(r, "%s %s (an outer layer gives %s)" % (f, cg_kernel.show(f, v), cg_kernel.show(f, cur[f])))
    for f in ("cpu", "mem", "pids"):
        val = cg_kernel.show(f, cur[f])
        e.put("cgroup", f, [val], ["%s %s <- %s" % (f, val, who(by[f]) if f in by else "(no layer sets it)")])


def mask(e, rs):
    rs = [r for r in rs if r["kind"] == "mask"]
    if not rs:
        return
    s, paths, holes, seen = subst(), [], [], set()
    for r in rs:
        c = r["config"] or {}
        for p in c.get("paths", [{"path": "/run/user/{uid}", "how": "tmpfs"}]):
            p = {"path": p} if isinstance(p, str) else p
            try:
                line = "%s %s" % (p.get("how", "tmpfs"), os.path.normpath(str(p["path"]).format(**s)))
            except (KeyError, IndexError, ValueError):
                line = "%s %s" % (p.get("how", "tmpfs"), p.get("path"))
            if line not in seen:
                seen.add(line)
                paths.append((line, r))
        for k in c.get("keep", []):
            try:
                holes.append((os.path.normpath(str(k).format(**s)), r))
            except (KeyError, IndexError, ValueError):
                holes.append((str(k), r))
    e.put("mask", "paths", [l for l, _ in paths], ["paths %s <- %s" % (l, who(r)) for l, r in paths])
    if holes:
        e.put("mask", "holes", [h for h, _ in holes], ["holes %s <- %s" % (h, who(r)) for h, r in holes])


def net(e, rs):
    """The net kernels the agent's traffic goes through: those after the last llm kernel that cut the network (an
    llm kernel inside a net kernel gives the layers inside an empty network)."""
    nets, cut = [], None
    for r in rs:
        if r["kind"] == "net":
            nets.append(r)
        elif r["kind"] == "llm" and nets:
            nets, cut = [], r
    if not nets:
        if cut:
            e.put("net", "network", ["none"], ["network none <- %s (an llm kernel inside a net kernel: only lo "
                                               "further in)" % who(cut)])
        return
    allow, hp, rate, quota = None, None, {}, []
    for r in nets:
        c = r["config"] or {}
        mine = [norm(x) for x in c.get("allow", [])]
        mhp = list(c.get("host_ports", []))
        if allow is None:
            allow, hp = [(x, r) for x in mine], [(x, r) for x in mhp]
        else:
            new = [(y, w if y == x else r) for x, w in allow for y in chain.allow_and([x], mine)]
            for y in mine:
                if not any(chain.allow_and([y], [x]) == [y] for x, _ in allow):
                    e.loose(r, "allow %s %s %s (more than the outer layers let through)" % (
                        y["proto"], y["to"], y["port"]))
            newhp = []
            for x, w in hp:
                for y in chain.host_ports_and([x], mhp):
                    newhp.append((y, w if chain.port_range(y) == chain.port_range(x) else r))
            for y in mhp:
                lo, hi = chain.port_range(y)
                if not any(lo >= chain.port_range(x)[0] and hi <= chain.port_range(x)[1] for x, _ in hp):
                    e.loose(r, "host port %s (the outer layers do not let it through)" % (
                        y["port"] if isinstance(y, dict) else y))
            allow, hp = new, newhp
        for f, conv in (("down", net_kernel.rate_bits), ("up", net_kernel.rate_bits)):
            if c.get(f) is None:
                continue
            if f not in rate or conv(c[f]) < conv(rate[f][0]):
                rate[f] = (c[f], r)
            elif conv(c[f]) > conv(rate[f][0]):
                e.loose(r, "%s %s (an outer layer gives %s)" % (f, c[f], rate[f][0]))
        if c.get("quota") is not None:
            q = net_kernel.size_bytes(c["quota"])
            if quota and q > min(x for x, _ in quota):
                e.loose(r, "quota %d bytes (an outer layer gives %d)" % (q, min(x for x, _ in quota)))
            quota.append((q, r))
    e.put("net", "network", ["through %d net kernel(s)" % len(nets)],
          ["network through %d net kernel(s) <- %s" % (len(nets), ", ".join(who(r) for r in nets))])
    e.put("net", "allow", ["%s %s %s" % (x["proto"], x["to"], x["port"]) for x, _ in allow],
          ["allow %s %s %s <- %s" % (x["proto"], x["to"], x["port"], who(w)) for x, w in allow])
    hps = [("%s %s" % (x.get("proto", "tcp"), x["port"]) if isinstance(x, dict) else "tcp %s" % x, w) for x, w in hp]
    e.put("net", "host_ports", [x for x, _ in hps], ["host_ports %s <- %s" % (x, who(w)) for x, w in hps])
    for f in ("down", "up"):
        if f in rate:
            e.put("net", f, [rate[f][0]], ["%s %s <- %s" % (f, rate[f][0], who(rate[f][1]))])
    if quota:  # each layer counts on its own; the smallest is the most the agent can get
        e.put("net", "quota", [str(min(q for q, _ in quota))],
              ["quota %d <- %s (its own counter)" % (q, who(r)) for q, r in quota])


def norm(x):
    """An allow rule as chain.allow_and writes it (to as a network, port as N or LO-HI, proto)."""
    return chain.allow_and([x], [x])[0]


def llm(e, rs):
    rs = [r for r in rs if r["kind"] == "llm"]
    if not rs:
        return
    models, limits = None, []
    for r in rs:
        c = r["config"] or {}
        mine = c.get("models") or []
        mine = [mine] if isinstance(mine, str) else mine
        if models is None:
            models = [(m, r) for m in mine]
        else:
            for m in mine:
                if m not in [x for x, _ in models]:
                    e.loose(r, "model %s (an outer llm kernel does not take it)" % m)
            models = [(m, w) for m, w in models if m in mine]
        lim = c.get("limit")
        if isinstance(lim, int):
            if limits and lim > min(x for x, _ in limits):
                e.loose(r, "limit %d requests (an outer llm kernel gives %d)" % (lim, min(x for x, _ in limits)))
            limits.append((lim, r))
    e.put("llm", "models", [m for m, _ in models], ["models %s <- %s" % (m, who(w)) for m, w in models])
    if limits:
        e.put("llm", "limit", [str(min(x for x, _ in limits))],
              ["limit %d <- %s (its own ledger)" % (x, who(r)) for x, r in limits])
    up = str((rs[0]["config"] or {}).get("upstream") or "outer")
    e.put("llm", "upstream", [up], ["upstream %s <- %s" % (up, who(rs[0]))])


def uid(e, rs):
    rs = [r for r in rs if r["kind"] == "uid"]
    if rs:
        u = str((rs[-1]["config"] or {}).get("uid"))
        e.put("uid", "uid", [u], ["uid %s <- %s" % (u, who(rs[-1]))])


def compute(rs):
    e = Eff()
    for f in (cgroup, mask, net, llm, uid):
        f(e, rs)
    return e


def write(aosdir, e, lock):
    """.aos/effective/<kind>/<field> and blame, .aos/lock.json."""
    top = os.path.join(aosdir, "effective")
    os.makedirs(top, exist_ok=True)
    with open(os.path.join(top, "description"), "w") as f:
        f.write(DESCRIPTION + "\n")
    for kind, fields in e.v.items():
        d = os.path.join(top, kind)
        os.makedirs(d, exist_ok=True)
        for k, vals in fields.items():
            with open(os.path.join(d, k), "w") as f:
                f.write("".join(v + "\n" for v in vals))
        with open(os.path.join(d, "blame"), "w") as f:
            f.write("".join(l + "\n" for l in e.blame.get(kind, [])))
    with open(os.path.join(aosdir, "lock.json"), "w") as f:
        json.dump(lock, f, indent=1)
        f.write("\n")


# ------------------------------------------------------------ --explain and --diff

def explain(lock, e, notes, limit_line, out):
    rs = lock["layers"]
    p = lambda s="": print(s, file=out)
    p("# %d layers after expanding bundles%s" % (len([r for r in rs if not r.get("outer")]),
                                                 " (and %d outside, from $AOS_ENV)" % len([r for r in rs if r.get("outer")])
                                                 if any(r.get("outer") for r in rs) else ""))
    for r in rs:
        f = r["file"] if isinstance(r["file"], str) else " + ".join(r["file"])
        extra = [x for x in ("outside" if r.get("outer") else "", "added by mini" if r.get("auto") else "",
                             "replaces " + r["replaced"] if r.get("replaced") else "",
                             "merged from " + ", ".join(r["merged"]) if r.get("merged") else "") if x]
        p("  layer %-3d %-6s %s%s  file %s%s" % (r["layer"], r["kind"], r["name"], " from " + r["from"] if r["from"]
                                               else "", f, " (%s)" % "; ".join(extra) if extra else ""))
    for n in notes:
        p("  note: %s" % n["text"])
    p("flatten plan: %d real layers instead of %d: %s" % (len(lock["plan"]), len([r for r in rs if not r.get("outer")]),
                                                          "  ".join(lock["plan_text"])))
    p("user namespaces: %s" % limit_line)
    p("effective (what the agent gets)  <- who decided it")
    for kind in ("cgroup", "mask", "net", "llm", "uid"):
        for l in e.blame.get(kind, []):
            p("  %-6s %s" % (kind, l))
    if e.looser:
        p("looser than an outer layer (the outer one applies): %d" % len(e.looser))
        for l in e.looser:
            p("  %s" % l)


def load_lock(path):
    with open(path) as f:
        return json.load(f)


def diff(a, b, out):
    """Two locks: layers new, gone, changed (config fields), moved; then the effective values that differ. Returns
    whether anything differs."""
    p = lambda s: print(s, file=out)
    la = {r["name"]: r for r in a["layers"] if not r.get("outer")}
    lb = {r["name"]: r for r in b["layers"] if not r.get("outer")}
    changed = False
    for n in list(la) + [n for n in lb if n not in la]:
        x, y = la.get(n), lb.get(n)
        if not x:
            p("+ layer %d %s %s (new)" % (y["layer"], y["kind"], n))
        elif not y:
            p("- layer %d %s %s (gone)" % (x["layer"], x["kind"], n))
        else:
            cx, cy = x["config"] or {}, y["config"] or {}
            for f in sorted(set(cx) | set(cy)):
                if cx.get(f) != cy.get(f):
                    p("~ %s: %s %s -> %s" % (n, f, json.dumps(cx.get(f)), json.dumps(cy.get(f))))
                    changed = True
            if x["layer"] != y["layer"]:
                p("~ %s: moved layer %d -> %d" % (n, x["layer"], y["layer"]))
                changed = True
            if x.get("sha256") != y.get("sha256") and cx == cy:
                p("~ %s: file changed (same config): %s" % (n, y["file"]))
                changed = True
            continue
        changed = True
    ea, eb = compute(a["layers"]).v, compute(b["layers"]).v
    for kind in sorted(set(ea) | set(eb)):
        fa, fb = ea.get(kind, {}), eb.get(kind, {})
        for f in sorted(set(fa) | set(fb)):
            if fa.get(f) != fb.get(f):
                p("= effective %s/%s: %s -> %s" % (kind, f, " | ".join(fa.get(f, ["(none)"])) or "(empty)",
                                                  " | ".join(fb.get(f, ["(none)"])) or "(empty)"))
                changed = True
    if not changed:
        p("same: %d layers, same files and configs" % len(la))
    return changed
