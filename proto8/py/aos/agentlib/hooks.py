"""hooks - the agent family's own hook rules (agent-fsm cells, aos-eca-turn, aos-mcp): which of its points can be blocked, which keys a hook may change, what condition compares; its hookeds lists (the definition's with the stack's copy on top); tool_added's list.

The user 11-21 chose the fourth layer (proto8/thinking/2026-11/21/aos-hook-簡化-1121/07): the engine (aos.hook_run) only runs
handlers and gives back exit codes and stdout; "發事件的程式自己決定" what they mean, and the agent family keeps its rules here,
in code, not in a declaration (declarations are "只是參考"). Kept as before: exit 10 blocks before_queue / before_tool;
a JSON object on stdout changes content / arguments; condition = only for these tool names / error codes (the user's
"1.對。": the agent keeps this filter, written in the hookeds entry); on_clock's own keys (every_cycles, every_ms, clock,
config; hook_clock.py). Gone with the fourth layer: intercept, async, on_error (an entry that has them: the keys are
ignored). A hook that fails (exit code not 0 / 10, timed out, cannot start, bad stdout): on a point that can be blocked the
event stops (HookFailed: the firing program says its error line), on the other points it is one warning line and the next
hook runs (line top-1121-hooknew's choice, see its notes).
Firing programs go through agent_hooks.open (the remote); aos-agent hook and the compile use load / check_entry here.
Standard library plus aos.hook_run / hook_lists / hook_point; prints nothing, never exits.

API:
    POINTS[event] = {"field": the event field condition compares, or None; "block": exit 10 blocks;
                     "change": {key: check(value) -> bool, plus a sentence}} for the points the agent family fires itself
                     (the loop points are fired through aos-hook fire, which has no rules; before_compact / after_compact
                     keep their rules where they are fired: agent-fsm's compact.py, eca-claude's compact_hook)
    CLOCK_EVENT, CLOCK_KEYS   on_clock and its own entry keys
    HooksBad, HookFailed
    check_entry(entry)        the engine's checks plus the agent's own keys (condition; on_clock's keys only on on_clock)
    check_clock(entry)        only on_clock's keys
    layers(def_folder, stack) -> the hookeds lists in order (aos.hook_point.layers); own(def_folder, stack) -> the stack copy
    load(def_folder, stack)   -> {name: entry} in effect (definition's lists, then the stack's copies; null = off)
    nulled(def_folder, stack) -> names the stack's copy turns off (sorted)
    matches(entry, data)      -> whether the entry's condition takes this data
    fire(event, data, entries, stack, warn=None, only=None) -> {"data": data after the hooks (a new dict), "changed": [keys],
                     "blocked": bool, "hook": the blocking hook or None, "text": its stdout or ""}; hooks run in name order,
                     each sees what the earlier ones changed; only = exactly these names (no condition compared)
    tools_added(stack, tools, has_hook) -> [(name, path)] new since the last look ($AOS_STACK/hook_tools_seen.json)
"""
import copy
import json
import os

from aos import hook_lists, hook_point, hook_run


def _text(v):
    return isinstance(v, str)


POINTS = {
    "before_queue": {"field": None, "block": True, "change": {"content": (lambda v: isinstance(v, str) and bool(v.strip()),
                                                                          "a non-empty string")}},
    "after_queue": {"field": None, "block": False, "change": {}},
    "before_tool": {"field": "name", "block": True, "change": {"arguments": (lambda v: True, "any JSON value")}},
    "after_tool": {"field": "name", "block": False, "change": {"content": (_text, "a string")}},
    "brain_failed": {"field": "name", "block": False, "change": {}},
    "tool_added": {"field": "name", "block": False, "change": {}},
    "on_clock": {"field": None, "block": False, "change": {}},
}
CLOCK_EVENT = "on_clock"
CLOCK_KEYS = ("clock", "every_cycles", "every_ms")   # only on_clock takes them
BLOCK = hook_run.BLOCK
CELLS = hook_run.CELLS                           # $AOS_STACK/hookeds/NAME/
SEEN = "hook_tools_seen.json"                    # tool_added: the names seen last time
HooksBad = hook_lists.HooksBad


class HookFailed(RuntimeError):
    """A hook on a point that can be blocked failed: the event does not go on."""


def check_clock(entry):
    """on_clock's own keys: exactly one of every_cycles / every_ms, a positive whole number; clock a non-empty string."""
    if entry["event"] != CLOCK_EVENT:
        for key in CLOCK_KEYS:
            if key in entry:
                raise HooksBad("%s is only for event %s" % (key, CLOCK_EVENT))
        return
    given = [k for k in ("every_cycles", "every_ms") if k in entry]
    if len(given) != 1:
        raise HooksBad("event %s needs exactly one of every_cycles, every_ms" % CLOCK_EVENT)
    n = entry[given[0]]
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise HooksBad("%s must be a positive integer" % given[0])
    if "clock" in entry and not (isinstance(entry["clock"], str) and entry["clock"]):
        raise HooksBad("clock must be a non-empty string (a proc name, or the path of a clock file or of a folder with one)")


def check_entry(entry):
    hook_lists.check_entry(entry)
    if "condition" in entry:
        m = entry["condition"]
        if not ((isinstance(m, str) and m) or (isinstance(m, list) and all(isinstance(x, str) and x for x in m))):
            raise HooksBad("condition must be a non-empty string or an array of them")
    check_clock(entry)


def _bad(e):
    raise HooksBad(str(e)) from None


def layers(def_folder, stack):
    try:
        return hook_point.layers(def_folder, stack)
    except hook_point.InterfaceBad as e:
        _bad(e)


def own(def_folder, stack):
    try:
        return hook_point.own(def_folder, stack)
    except hook_point.InterfaceBad as e:
        _bad(e)


def load(def_folder, stack):
    return hook_lists.load(layers(def_folder, stack), check_entry)


def nulled(def_folder, stack):
    path = own(def_folder, stack)
    return sorted(n for n, e in hook_lists.read(path).items() if e is None) if path else []


def matches(entry, data):
    field = POINTS.get(entry["event"], {}).get("field")
    if field is None or "condition" not in entry:
        return True
    m = entry["condition"]
    return data.get(field) in ([m] if isinstance(m, str) else m)


def _changes(point, out):
    """stdout of a hook that went on -> {key: value} of the keys this point lets a hook change; bad = ValueError."""
    if not point["change"] or not out.strip():
        return {}
    try:
        reply = json.loads(out)
    except ValueError as e:
        raise ValueError("stdout is not JSON: %s" % e) from None
    if not isinstance(reply, dict):
        raise ValueError("stdout is not a JSON object")
    got = {}
    for key, (ok, what) in point["change"].items():
        if key in reply:
            if not ok(reply[key]):
                raise ValueError("%s in stdout must be %s" % (key, what))
            got[key] = reply[key]
    return got


def fire(event, data, entries, stack, warn=None, only=None):
    point = POINTS.get(event, {"field": None, "block": False, "change": {}})
    result = {"data": copy.deepcopy(data), "changed": [], "blocked": False, "hook": None, "text": ""}
    for name in hook_run.names(entries, event):
        entry = entries[name]
        if (only is not None and name not in only) or (only is None and not matches(entry, data)):
            continue
        r = hook_run.run(name, entry, event, result["data"], stack)
        try:
            if r["error"]:
                raise ValueError(r["error"])
            if r["code"] == BLOCK and point["block"]:
                result.update(blocked=True, hook=name, text=r["stdout"])
                return result
            if r["code"] not in (0, BLOCK):
                raise ValueError("exited %d" % r["code"])
            got = _changes(point, r["stdout"])
        except ValueError as e:
            why = "hook %s (event %s) failed: %s" % (name, event, e)
            if point["block"]:
                raise HookFailed(why) from None
            if warn:
                warn(why + "; going on without it")
            continue
        for key, v in got.items():
            result["data"][key] = v
            if key not in result["changed"]:
                result["changed"].append(key)
    return result


def tools_added(stack, tools, has_hook):
    """tool_added's "who is new": with a hook in effect write this time's names to $AOS_STACK/hook_tools_seen.json and return
    the [(name, path)] new since last time; the first time (no file or a bad one) only records; no hook = delete the file, [].
    Cannot write = OSError."""
    path = os.path.join(stack, SEEN)
    if not has_hook:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return []
    try:
        with open(path, encoding="utf-8") as f:
            seen = json.load(f)
        if not (isinstance(seen, list) and all(isinstance(x, str) for x in seen)):
            seen = None
    except (OSError, ValueError):
        seen = None
    names = sorted({n for n, _ in tools})
    if seen != names:
        tmp = os.path.join(stack, ".%s.%d.tmp" % (SEEN, os.getpid()))
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(names, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    if seen is None:
        return []
    return [(n, p) for n, p in tools if n not in set(seen)]
