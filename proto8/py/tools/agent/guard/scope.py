#!/usr/bin/env python3
# scope - the write scope of one agent, from one source: realpath($AOS_WS) plus $AOS_WRITE_ALLOW may be written;
# the agent's own stack, $AOS_CD, every stack and definition on the daemon table, the daemon folder, the product
# folders under $AOS_HOME, $AOS_WRITE_DENY and the guard config's deny_roots may not; the rules (deny_parts,
# proc-stack, definition-marker, no-hash-outside-json, no-tilde) apply on top. Used by the guard (guard.py) and by
# anything else that needs the same list (for example a shell sandbox): python3 scope.py, or _entry --scope, prints it as JSON.
import json, os, sys, time

HELP = """usage: scope.py   (or: _entry --scope)
Print the write scope of the calling agent as one JSON object on stdout and exit 0:
  {"version": 1,
   "allow": [{"path": P, "from": "AOS_WS" | "AOS_WRITE_ALLOW"}, ...],
   "deny":  [{"path": P, "from": "AOS_STACK" | "AOS_CD" | "definition" | "daemon-table" | "AOS_DAEMON"
                                | "AOS_HOME" | "AOS_WRITE_DENY" | "guard.json"}, ...],
   (the guard adds "event", the stack field of the hook event; --scope reads no event)
   "deny_parts": [".git", ...],
   "rules": [{"name": "deny_parts", "parts": [".git"]}, {"name": "proc-stack"},
             {"name": "definition-marker", "marker": "interfaces.json"},
             {"name": "no-hash-outside-json", "json_tools": [...]}, {"name": "no-tilde"}]}
Every path is absolute and resolved (realpath). A path may be written when it is at or under an allow path,
not at or under a deny path, has no part equal to one of deny_parts, and passes every rule. version changes
only when the meaning of a key changes or a rule is added; a reader should refuse a version or a rule name it
does not know. The rules are not folders: the guard applies them to the
path itself, and no config lifts them (deny_parts is the config's own list, default .git):
  deny_parts            a path part equal to one of the parts
  proc-stack            a path part named .stack; or, walking up its realpath, a folder holding procs_state.json
                        (a daemon stack) or a folder D whose parent is named procs and whose grandparent holds
                        procs_state.json (D is a proc stack)
  definition-marker     walking up its realpath, a folder holding interfaces.json (an agent definition)
  no-hash-outside-json  a tool path with # is refused, except in the json tools listed (they cut FILE#/POINTER)
  no-tilde              a tool path starting with ~ is refused (tools do not expand ~)
Read from the environment:
  AOS_WS           the workspace (required); always allowed
  AOS_WRITE_ALLOW  more folders that may be written, separated by %(sep)r; ~ is the home folder,
                   a relative entry counts from AOS_WS
  AOS_WRITE_DENY   folders that may never be written, same form
  AOS_STACK        the agent's stack (a hook or tool cell <stack>/hookeds/<name> or <stack>/tools/<name>
                   counts as <stack>); always denied
  AOS_CD           the folder of the running program (the guard's own folder in a hook); denied when set
  AOS_DAEMON       the daemon stack: denied as a whole; every row of its procs_state.json names a stack and a
                   definition folder, all denied (the definition of the row holding AOS_STACK is "definition").
                   No procs_state.json = no rows. A procs_state.json that cannot be read (also after one more
                   try) or has a row without a stack string = error TableBad: nothing is printed
  AOS_HOME         the product tree: its lib, templates, knowledge, cpp, py, bin and include folders are denied
  AOS_GUARD_CFG    the guard config (JSON); its deny_roots are denied. A config with write_roots is refused.
exit codes: 0 printed; 1 error ("scope: error: CODE reason": WsMissing, CfgMissing, CfgBad, TableBad).
"""

SCOPE_VERSION = 1                  # the shape of the --scope JSON; a reader refuses versions it does not know
STACK_CELLS = ("hookeds", "tools")   # a hook or tool runs with AOS_STACK = <stack>/<cell kind>/<name>
JSON_TOOLS = ("json_set", "json_add", "json_del", "json_multi_set")   # the only write tools that cut FILE#/POINTER
HOME_PARTS = ("lib", "templates", "knowledge", "cpp", "py", "bin", "include")   # product folders under AOS_HOME
DEF_MARKER = "interfaces.json"     # a folder holding this file is an agent definition (rule definition-marker)

# Where stacks sit (proto8 knowledge):
#   aos/world.md#  the daemon is "$AOS_DAEMON (the daemon's own stack folder)"; a proc's stack is its RAM.
#   `aos/cli/agent.md#/ctl add: attach one agent`  "--stack DIR chooses its stack (default <daemon stack>/procs/<name>/)";
#   `aos/cli/daemon.md#/add: attach a proc`  "aos-daemon-ctl -d /srv/d where --stack tick   # /srv/d/procs/tick";
#   `aos/cli/safety.md#/Removing an agent`  "deleted stack /.../stacks/root/procs/ann".
#   `aos/cli/mcp.md#/Serving a registry`  "stack = --stack > $AOS_STACK > WS/.stack/"; aos/cli/parts/exec.md#
#   "ws=/tmp/w stack=/tmp/w/.stack/"; aos/cli/_description.md#  the daemon defaults to "./.stack".
# The marker of a daemon stack is procs_state.json (its table; the knowledge pages do not name the file: it is
# the file read_table below and aos-agent ctl read, py/docs/05-commands/03-aos-daemon-ctl.md; its procs_requests key is the
# ctl mailbox of aos/cli/parts/daemon.md#).
STATE_FILE = "procs_state.json"
STACK_PART = ".stack"


class ScopeError(Exception):
    def __init__(self, code, why):
        Exception.__init__(self, "%s %s" % (code, why))
        self.code, self.why = code, why


def environ(env):
    return os.environ if env is None else env


def expand(p, env=None):
    """"~" and "~/..." are the home folder (HOME from env); "~user" is left as written. Only for environment
    and config entries: tools do not expand ~ in their arguments (the guard refuses such arguments)."""
    if p == "~" or p.startswith("~/"):
        home = environ(env).get("HOME") or os.path.expanduser("~")
        return home + p[1:]
    return p


def resolve(p, ws, env=None, home=True):
    """~ expanded (only when home is true: environment and config entries), relative to ws, symlinks and ".."
    resolved. Tool arguments pass home=False: the tools take ~ literally."""
    raw = p
    if home:
        p = expand(p, env)
    if not os.path.isabs(p):
        if not ws:
            raise ScopeError("WsMissing", "AOS_WS is not set, so the relative path %s cannot be placed" % raw)
        p = os.path.join(ws, p)
    return os.path.realpath(p)


def under(path, roots):
    return any(path == r or path.startswith(r.rstrip("/") + "/") for r in roots)


def own_stack(env=None):
    """The agent's stack from AOS_STACK, with a hook or tool cell <stack>/hookeds/<name> stripped; "" when unset."""
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
    parts = cfg.get("deny_parts", [".git"])
    if not isinstance(parts, list) or not all(isinstance(x, str) and x for x in parts):
        raise ScopeError("CfgBad", "deny_parts in the guard config must be a list of folder names")
    return cfg


def deny_parts(cfg):
    return list(cfg.get("deny_parts", [".git"]))


TABLE_RETRY_S = 0.05   # one more read after this pause, as daemon_ctl does (the main file and its shards are separate files)


def _table_once(daemon):
    with open(os.path.join(daemon, STATE_FILE), encoding="utf-8") as f:
        procs = json.load(f).get("procs")
    if isinstance(procs, dict) and isinstance(procs.get("$ref"), list):
        out = {}
        for ref in procs["$ref"]:
            with open(os.path.join(daemon, ref), encoding="utf-8") as f:
                out.update(json.load(f))
        procs = out
    if not isinstance(procs, dict):
        raise ValueError("procs is not an object")
    for row in procs.values():
        # the daemon writes every row as an object with "stack" a non-empty string and "def" a string or null
        # (directives go into "as_written"); anything else is a broken table, not a row to skip
        if not isinstance(row, dict) or not isinstance(row.get("stack"), str) or not row["stack"] \
                or not (row.get("def") is None or isinstance(row.get("def"), str)):
            raise ValueError("a row has no stack string, or a def that is not a string or null")
    return procs


def read_table(daemon):
    """The procs of a daemon's procs_state.json (shards {"$ref": [...]} joined); None when the file does not
    exist (no daemon table: not started yet, or procs_state off). A file that exists but cannot be read or has a
    broken row is read once more after a short pause; still bad = ScopeError TableBad (the caller blocks)."""
    if not os.path.isfile(os.path.join(daemon, STATE_FILE)):
        return None
    for attempt in range(2):
        try:
            return _table_once(daemon)
        except (OSError, ValueError, AttributeError, TypeError) as e:
            if attempt:
                raise ScopeError("TableBad", "the daemon table (%s of AOS_DAEMON) cannot be read: %s"
                                 % (STATE_FILE, getattr(e, "strerror", None) or e))
            time.sleep(TABLE_RETRY_S)


def daemon_folder(env=None):
    """realpath(AOS_DAEMON) (a relative value counts from AOS_WS, as the tools run there); None when unset or
    when it is relative and AOS_WS is not set."""
    e = environ(env)
    d = e.get("AOS_DAEMON", "")
    if not d:
        return None
    try:
        return resolve(d, e.get("AOS_WS", ""), env)
    except ScopeError:
        return None


def table_rows(env=None):
    """[(stack, def)] for every row of the daemon table, each resolved (relative values count from the daemon
    folder; a "#..." tail is cut); a null def is None. [] when AOS_DAEMON is unset or the table file does not
    exist; a table file that cannot be read = ScopeError TableBad (read_table).
    The table is read directly even when AOS_KERNEL is set: the file is there either way."""
    daemon = daemon_folder(env)
    if not daemon:
        return []
    procs = read_table(daemon)
    if procs is None:
        return []
    rows = []
    for row in procs.values():
        got = []
        for k in ("stack", "def"):
            v = row.get(k)
            v = v.split("#", 1)[0] if isinstance(v, str) else ""
            got.append(os.path.realpath(os.path.join(daemon, v)) if v else None)
        rows.append(tuple(got))
    return rows


def definition(env=None):
    """The agent's definition folder: the "def" of the daemon table row whose stack holds AOS_STACK (the deepest
    one, as aos-agent ctl who does). None when there is no daemon, no table, no row or no def."""
    raw = environ(env).get("AOS_STACK", "")
    if not raw:
        return None
    me = os.path.realpath(raw)
    best, depth = None, -1
    for st, d in table_rows(env):
        if st and d and under(me, [st]) and len(st) > depth:
            best, depth = d, len(st)
    return best


def proc_stack(real):
    """The stack folder a resolved path real is at or under (rule proc-stack), else None. Walks up from real
    (missing tail parts simply hold no file): the first path part named .stack ends a stack; a folder holding
    procs_state.json is a daemon stack (all of it, its procs_requests too); a folder D whose parent is named
    procs and whose grandparent holds procs_state.json is a proc stack. The deepest match is named. A folder
    named procs without the marker above it is an ordinary folder."""
    parts = real.split("/")
    if STACK_PART in parts:
        return "/".join(parts[:parts.index(STACK_PART) + 1])
    d = real
    while True:
        up = os.path.dirname(d)
        if os.path.isfile(os.path.join(d, STATE_FILE)):
            return d
        if up != d and os.path.basename(up) == "procs" and os.path.isfile(os.path.join(os.path.dirname(up), STATE_FILE)):
            return d
        if up == d:
            return None
        d = up


def definition_marker(real):
    """The definition folder a resolved path real is at or under (rule definition-marker), else None: walking
    up from real, the first folder holding interfaces.json."""
    d = real
    while True:
        if os.path.isfile(os.path.join(d, DEF_MARKER)):
            return d
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def rules(cfg):
    """The checks that are not plain folders, as the guard applies them (see HELP)."""
    return [{"name": "deny_parts", "parts": deny_parts(cfg)}, {"name": "proc-stack"},
            {"name": "definition-marker", "marker": DEF_MARKER},
            {"name": "no-hash-outside-json", "json_tools": list(JSON_TOOLS)}, {"name": "no-tilde"}]


def write_scope(env=None, stack=None):
    """{"version": 1, "allow": [{"path", "from"}], "deny": [{"path", "from"}], "deny_parts": [...],
    "rules": [{"name", ...}]} for the environment env
    (default os.environ). stack = the "stack" field of a hook event (the guard passes it; the hook runner
    writes it and the agent's arguments cannot change it): denied too, from "event". The rules are not
    enumerated as paths: the guard applies them to one path (proc_stack, definition_marker).
    Raises ScopeError (WsMissing, CfgMissing, CfgBad, TableBad)."""
    e = environ(env)
    ws = e.get("AOS_WS", "")
    if not ws:
        raise ScopeError("WsMissing", "AOS_WS is not set, so the write scope is unknown")
    cfg = load_cfg(env)
    allow = [{"path": os.path.realpath(expand(ws, env)), "from": "AOS_WS"}]
    for p in split_list(e.get("AOS_WRITE_ALLOW")):
        allow.append({"path": resolve(p, ws, env), "from": "AOS_WRITE_ALLOW"})
    deny = []

    def add(path, src, once=False):
        if path and not (once and any(x["path"] == path for x in deny)):
            deny.append({"path": path, "from": src})

    st = own_stack(env)
    if st:
        add(resolve(st, ws, env), "AOS_STACK")
    if stack:
        add(resolve(own_stack({"AOS_STACK": stack}), ws, env), "event", once=True)
    if e.get("AOS_CD"):
        add(resolve(e["AOS_CD"], ws, env), "AOS_CD")
    add(definition(env), "definition")
    for row_stack, row_def in table_rows(env):   # every row: a neighbour's stack and definition alike
        add(row_stack, "daemon-table", once=True)
        add(row_def, "daemon-table", once=True)
    add(daemon_folder(env), "AOS_DAEMON")
    if e.get("AOS_HOME"):
        top = resolve(e["AOS_HOME"], ws, env)
        for part in HOME_PARTS:
            if os.path.isdir(os.path.join(top, part)):
                add(os.path.realpath(os.path.join(top, part)), "AOS_HOME")
    for p in split_list(e.get("AOS_WRITE_DENY")):
        add(resolve(p, ws, env), "AOS_WRITE_DENY")
    roots = cfg.get("deny_roots", [])
    if not isinstance(roots, list):
        raise ScopeError("CfgBad", "deny_roots in the guard config must be a list of paths")
    for p in roots:
        if isinstance(p, str) and p:
            add(resolve(p, ws, env), "guard.json")
    return {"version": SCOPE_VERSION, "allow": allow, "deny": deny, "deny_parts": deny_parts(cfg), "rules": rules(cfg)}


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
