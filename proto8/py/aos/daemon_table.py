"""daemon_table - read a daemon's procs_state.json from the files alone (no letter to the daemon or kernel): its rows as (stack, def), and the definition folder of the agent whose stack holds a path. Shared by the guard's write scope and ws_write."""
# 11-23 線 eca-aos-core-1123：從 py/tools/agent/guard/scope.py 搬來（使用者「1.補。」，ws_write 經 aos-tools 叫時要擋叫方的定義夾，
# 照 guard 的做法讀 daemon 表），scope.py 改用這份，不留兩套。訊息與行為跟搬之前一樣。
import json
import os
import time

STATE_FILE = "procs_state.json"   # the daemon's table (py/docs/05-commands/03-aos-daemon-ctl.md)
TABLE_RETRY_S = 0.05              # one more read after this pause, as daemon_ctl does (the main file and its shards are separate files)


class TableError(Exception):
    """code TableBad: the table file exists but cannot be read (also after one more try) or has a broken row."""
    def __init__(self, code, why):
        Exception.__init__(self, "%s %s" % (code, why))
        self.code, self.why = code, why


def environ(env):
    return os.environ if env is None else env


def expand(p, env=None):
    """"~" and "~/..." are the home folder (HOME from env); "~user" is left as written. Only for environment
    and config entries: tools do not expand ~ in their arguments."""
    if p == "~" or p.startswith("~/"):
        home = environ(env).get("HOME") or os.path.expanduser("~")
        return home + p[1:]
    return p


def under(path, roots):
    return any(path == r or path.startswith(r.rstrip("/") + "/") for r in roots)


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
    broken row is read once more after a short pause; still bad = TableError TableBad (the caller decides)."""
    if not os.path.isfile(os.path.join(daemon, STATE_FILE)):
        return None
    for attempt in range(2):
        try:
            return _table_once(daemon)
        except (OSError, ValueError, AttributeError, TypeError) as e:
            if attempt:
                raise TableError("TableBad", "the daemon table (%s of AOS_DAEMON) cannot be read: %s"
                                 % (STATE_FILE, getattr(e, "strerror", None) or e))
            time.sleep(TABLE_RETRY_S)


def daemon_folder(env=None):
    """realpath(AOS_DAEMON) (~ expanded; a relative value counts from AOS_WS, as the tools run there); None when
    unset or when it is relative and AOS_WS is not set."""
    e = environ(env)
    d = expand(e.get("AOS_DAEMON", ""), env)
    if not d:
        return None
    if not os.path.isabs(d):
        if not e.get("AOS_WS"):
            return None
        d = os.path.join(e["AOS_WS"], d)
    return os.path.realpath(d)


def table_rows(env=None):
    """[(stack, def)] for every row of the daemon table, each resolved (relative values count from the daemon
    folder; a "#..." tail is cut); a null def is None. [] when AOS_DAEMON is unset or the table file does not
    exist; a table file that cannot be read = TableError TableBad (read_table).
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


def definition(env=None, stack=None):
    """The agent's definition folder: the "def" of the daemon table row whose stack holds stack (default
    AOS_STACK; a tool or hook cell inside the agent's stack is held by it too), the deepest one, as aos-agent
    ctl who does. None when there is no stack, no daemon, no table, no row or no def."""
    raw = stack if stack is not None else environ(env).get("AOS_STACK", "")
    if not raw:
        return None
    me = os.path.realpath(raw)
    best, depth = None, -1
    for st, d in table_rows(env):
        if st and d and under(me, [st]) and len(st) > depth:
            best, depth = d, len(st)
    return best
