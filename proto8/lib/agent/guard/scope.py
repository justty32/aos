#!/usr/bin/env python3
# scope - the write scope of one agent, from one source: realpath($AOS_WS) plus $AOS_WRITE_ALLOW may be written;
# the agent's own stack, $AOS_CD, the agent's definition folder (from the daemon table), $AOS_WRITE_DENY and the
# guard config's deny_roots may not. Used by the guard (guard.py) and by anything else that needs the same list
# (for example a shell sandbox): python3 scope.py, or _entry --scope, prints it as JSON.
import json, os, sys

HELP = """usage: scope.py   (or: _entry --scope)
Print the write scope of the calling agent as one JSON object on stdout and exit 0:
  {"allow": [{"path": P, "from": "AOS_WS" | "AOS_WRITE_ALLOW"}, ...],
   "deny":  [{"path": P, "from": "AOS_STACK" | "AOS_CD" | "definition" | "AOS_WRITE_DENY" | "guard.json"}, ...]}
Every path is absolute and resolved (realpath). A path may be written when it is at or under an allow path
and not at or under a deny path. Read from the environment:
  AOS_WS           the workspace (required); always allowed
  AOS_WRITE_ALLOW  more folders that may be written, separated by %(sep)r; ~ is the home folder,
                   a relative entry counts from AOS_WS
  AOS_WRITE_DENY   folders that may never be written, same form
  AOS_STACK        the agent's stack (a hook or tool cell <stack>/hooks/<name> or <stack>/tools/<name>
                   counts as <stack>); always denied
  AOS_CD           the folder of the running program (the guard's own folder in a hook); denied when set
  AOS_DAEMON       the daemon stack: its procs_state.json row for this stack names the definition folder,
                   which is denied (skipped when AOS_KERNEL is set or the row cannot be read)
  AOS_GUARD_CFG    the guard config (JSON); its deny_roots are denied. A config with write_roots is refused.
exit codes: 0 printed; 1 error ("scope: error: CODE reason").
"""

STACK_CELLS = ("hooks", "tools")   # a hook or tool runs with AOS_STACK = <stack>/<cell kind>/<name>


class ScopeError(Exception):
    def __init__(self, code, why):
        Exception.__init__(self, "%s %s" % (code, why))
        self.code, self.why = code, why


def environ(env):
    return os.environ if env is None else env


def expand(p, env=None):
    """"~" and "~/..." are the home folder (HOME from env); "~user" is left as written."""
    if p == "~" or p.startswith("~/"):
        home = environ(env).get("HOME") or os.path.expanduser("~")
        return home + p[1:]
    return p


def resolve(p, ws, env=None):
    """~ expanded, relative to ws, symlinks and ".." resolved."""
    raw, p = p, expand(p, env)
    if not os.path.isabs(p):
        if not ws:
            raise ScopeError("WsMissing", "AOS_WS is not set, so the relative path %s cannot be placed" % raw)
        p = os.path.join(ws, p)
    return os.path.realpath(p)


def under(path, roots):
    return any(path == r or path.startswith(r.rstrip("/") + "/") for r in roots)


def own_stack(env=None):
    """The agent's stack from AOS_STACK, with a hook or tool cell <stack>/hooks/<name> stripped; "" when unset."""
    st = environ(env).get("AOS_STACK", "")
    if not st:
        return ""
    st = os.path.normpath(st)
    if os.path.basename(os.path.dirname(st)) in STACK_CELLS:
        st = os.path.dirname(os.path.dirname(st))
    return st


def split_list(value):
    return [x for x in (value or "").split(os.pathsep) if x]


def load_cfg(env=None):
    """The guard config from AOS_GUARD_CFG; {} when unset. Missing file, bad JSON, not an object or a
    write_roots key = ScopeError (a config error must block, never allow)."""
    path = environ(env).get("AOS_GUARD_CFG", "")
    if not path:
        return {}
    # messages name the variable, never its value (the guard prints no environment values)
    if not os.path.isfile(path):
        raise ScopeError("CfgMissing", "AOS_GUARD_CFG is set but does not name a file")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except OSError as e:
        raise ScopeError("CfgBad", "cannot read the guard config (AOS_GUARD_CFG): %s" % (e.strerror or type(e).__name__))
    except ValueError as e:
        raise ScopeError("CfgBad", "the guard config (AOS_GUARD_CFG) is not JSON: %s" % e)
    if not isinstance(cfg, dict):
        raise ScopeError("CfgBad", "the guard config (AOS_GUARD_CFG) is not a JSON object")
    if "write_roots" in cfg:
        raise ScopeError("CfgBad", "the guard config (AOS_GUARD_CFG) has write_roots, which is no longer read: the "
                         "folders an agent may write are AOS_WS plus AOS_WRITE_ALLOW (separated by %r); move them "
                         "there and drop the key" % os.pathsep)
    return cfg


def read_table(daemon):
    """The procs of a daemon's procs_state.json (shards {"$ref": [...]} joined); None if it cannot be read."""
    try:
        with open(os.path.join(daemon, "procs_state.json"), encoding="utf-8") as f:
            procs = json.load(f).get("procs")
        if isinstance(procs, dict) and isinstance(procs.get("$ref"), list):
            out = {}
            for ref in procs["$ref"]:
                with open(os.path.join(daemon, ref), encoding="utf-8") as f:
                    out.update(json.load(f))
            procs = out
    except (OSError, ValueError, AttributeError, TypeError):
        return None
    return procs if isinstance(procs, dict) else None


def definition(env=None):
    """The agent's definition folder: the "def" of the daemon table row whose stack holds AOS_STACK (the deepest
    one, as aos-agent ctl who does). Only $AOS_DAEMON/procs_state.json is read directly; with AOS_KERNEL set the
    table must be asked for by letter, which a hook does not do, so the result is None. None also when there is
    no daemon, no row or no def."""
    e = environ(env)
    daemon, raw = e.get("AOS_DAEMON", ""), e.get("AOS_STACK", "")
    if not daemon or not os.path.isabs(daemon) or not raw or e.get("AOS_KERNEL"):
        return None
    daemon = os.path.realpath(daemon)
    procs = read_table(daemon)
    if procs is None:
        return None
    me = os.path.realpath(raw)
    best, depth = None, -1
    for row in procs.values():
        if not isinstance(row, dict):
            continue
        st, d = row.get("stack"), row.get("def")
        if not isinstance(st, str) or not st or not isinstance(d, str) or not d:
            continue
        st = os.path.realpath(os.path.join(daemon, st.split("#", 1)[0]))
        if under(me, [st]) and len(st) > depth:
            best, depth = os.path.realpath(os.path.join(daemon, d.split("#", 1)[0])), len(st)
    return best


def write_scope(env=None):
    """{"allow": [{"path", "from"}], "deny": [{"path", "from"}]} for the environment env (default os.environ).
    Raises ScopeError (WsMissing, CfgMissing, CfgBad)."""
    e = environ(env)
    ws = e.get("AOS_WS", "")
    if not ws:
        raise ScopeError("WsMissing", "AOS_WS is not set, so the write scope is unknown")
    cfg = load_cfg(env)
    allow = [{"path": os.path.realpath(expand(ws, env)), "from": "AOS_WS"}]
    for p in split_list(e.get("AOS_WRITE_ALLOW")):
        allow.append({"path": resolve(p, ws, env), "from": "AOS_WRITE_ALLOW"})
    deny = []
    st = own_stack(env)
    if st:
        deny.append({"path": resolve(st, ws, env), "from": "AOS_STACK"})
    if e.get("AOS_CD"):
        deny.append({"path": resolve(e["AOS_CD"], ws, env), "from": "AOS_CD"})
    d = definition(env)
    if d:
        deny.append({"path": d, "from": "definition"})
    for p in split_list(e.get("AOS_WRITE_DENY")):
        deny.append({"path": resolve(p, ws, env), "from": "AOS_WRITE_DENY"})
    roots = cfg.get("deny_roots", [])
    if not isinstance(roots, list):
        raise ScopeError("CfgBad", "deny_roots in the guard config must be a list of paths")
    for p in roots:
        if isinstance(p, str) and p:
            deny.append({"path": resolve(p, ws, env), "from": "guard.json"})
    return {"allow": allow, "deny": deny}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] in (["-h"], ["--help"]):
        sys.stdout.write(HELP % {"sep": os.pathsep})
        return 0
    if argv:
        sys.stderr.write("scope: error: ArgumentsBad takes no arguments (see --help)\n")
        return 1
    try:
        scope = write_scope()
    except ScopeError as e:
        sys.stderr.write("scope: error: %s %s\n" % (e.code, e.why))
        return 1
    sys.stdout.write(json.dumps(scope, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
