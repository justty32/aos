"""hook_point - read the hook_points.json declarations (the hook points a program offers), check them, turn them into the table the hook engine wants, and open a handle a program fires its points with.

Design: proto8/thinking/2026-11/20/aos-hook-plan-1120 (01 format, 04 this library, 12 what changed after review).
Cut 1 added the reading; cut 2a (library half) added open() and the handle. aos-hook uses the handle; the agent
bodies and the kernel still fire through their own tables (aos.agentlib.hooks.EVENTS, the kernel's hooks.EVENTS)
until cut 2b / 3 switch them; py/tests/test_hook_points_match.py checks that the declarations say the same.
Standard library plus the engine (aos.hook_run, aos.hook_lists); prints nothing, never exits: errors are PointsBad,
or go to the handle's fail().

One declaration file = one provider (the program that fires the events) and all its points:
    {"description": "...", "provider": "agent-fsm", "points": {"before_tool": {point}, ...}}
Keys of a point (unknown keys are ignored, C-48):
    when        required, one English sentence: which program fires it, at what moment
    phase       required: before, after or on
    fields      required (may be {}): {field: "one sentence"} or {field: {"about": "...", "env": "ENV_NAME", "type": "int"|"string"}}
                (the object form = the firing command takes the value from that environment variable; type defaults to string)
    condition   optional: the field a hook's condition is compared with (no key = the point takes no condition)
    subject     optional: what the condition names (tool, code, stage...)
    change      optional: {key: type} a hook may change; type = string, nonempty_string, object or any
    block       optional, default false: exit 10 of a hook blocks the event
    if_blocked  required when block is true: what the provider does when blocked
    key         optional: the field that tells one firing from another (tool call id, letter name)
    entry_keys  optional: extra keys an entry of the hooks list may have for this point (on_clock's every_ms ...)
    fired_in    optional: source files in the provider's folder that fire it (tests look for the name there)
    if_failed   optional: what happens when a hook of this point fails (on_error stop)
    not_fired_yet  optional: the point is declared ahead of the code; nothing fires it yet (the sentence says why)

API:
    PointsBad                 a declaration (or the hook_points list of interfaces.json) is bad; ValueError subclass
    PROVIDERS                 {provider name: declaration path} for the providers aos itself ships
    provider_path(name)       -> path of a shipped provider's declaration; unknown name = PointsBad
    read_file(path)           -> (provider, {name: point}) of one file, checked
    read(paths)               -> {name: point} merged over several files (rule 5 below). Each point is the first
                                 declaration's keys, fields = the union (the first file's sentence wins), plus
                                 "said": [{"provider", "path", "when", and if_blocked / if_failed / not_fired_yet
                                 when given}] with one item per file that declares it
    engine_table(points)      -> {name: {"condition": field or None, "intercept": (keys...), "block": bool}}
                                 (the shape of aos.agentlib.hooks.EVENTS that aos.hook_run takes)
    for_definition(def_dir)   -> read() of the "hook_points" list in def_dir/interfaces.json ("aos-agent" key);
                                 no file, no "aos-agent" or no "hook_points" = {}. Items: a string = a path
                                 (relative = from def_dir), or {"provider": name}
    open(points=None, *, table=None, lists=None, entries=None, stack, fail, warn=None, check=None, entry_check=None)
                              -> Handle. Where the points come from, exactly one of:
                                 points  a list of declaration paths (read() is called) or read()'s {name: point}
                                 table   a ready engine table (the shape engine_table() gives); no declared types
                              Who listens, at most one of (neither = nobody):
                                 lists   paths of hooks lists, read again on every fire (aos.hook_lists.load:
                                         later overrides earlier, null = off, missing = none, entry_keys only on
                                         their points, then entry_check(entry) for the provider's own rules)
                                 entries {name: entry} already read and completed (hook_run.complete), or a
                                         function returning that, called on every fire (the kernel resolves its
                                         list itself; the agent reads its two layers itself)
                              stack = where the hooks' folders go (stack/hooks/NAME/).
                              fail(code, sentence) = report an error the program's own way; it should not return.
                              It gets PointsBad (at open), EventUnknown, HooksBad and HookFailed. When fail raises,
                              that exception goes out as it is; when fail returns, FailReturned is raised.
                              warn(line) = one English line when an on_error continue hook fails; None = silent.
                              check(event, key, value) = the caller's own check of a changed value (raise
                              ValueError); it runs after the declared type check, inside the engine, right after
                              each hook, so a bad value follows that hook's on_error and never reaches the next hook.
    Handle.points             the declared points ({name: point}; {} when opened with table)
    Handle.table              the engine table
    Handle.load()             -> {name: entry} of who listens now (HooksBad goes to fail)
    Handle.has(event)         -> whether some hook is on event (no condition compared)
    Handle.names(event, data) -> the names that would run for data, sorted (condition compared)
    Handle.fire(event, data, only=None, entries=None) -> the engine's result {"data", "changed", "blocked", "hook",
                                 "text"}. only = run exactly these names that are on event, with no condition compared
                                 again (take them from names(); the kernel's after_verdict fires one by one);
                                 entries = what load() gave (not read again)
    FailReturned              raised when fail() returned; .code and the sentence
    call_fail(fail, code, sentence) -> never returns: calls fail, raises FailReturned if it returned

Checks (PointsBad, one English sentence naming the file and the point):
    1 the file is a JSON object; provider a non-empty string; points an object; point names only a-z, 0-9, _;
      every key above has its type
    2 phase is one of three; block true is not allowed with phase on; block true needs if_blocked
    3 condition, key and every change key are fields of the point
    4 change types are one of four
    5 the same point name in several files: phase, condition, subject, change, block, key and entry_keys must match
"""
import io                                         # io.open: this module's own open() is the handle
import json
import os
import re

from aos import hook_handle

HERE = os.path.dirname(os.path.realpath(__file__))           # py/aos, or lib/aos once installed
ROOT = os.path.dirname(os.path.dirname(HERE))                 # the aos tree (proto8 / AOS_HOME)
PROVIDERS = {
    "aos-loop": os.path.join(HERE, "apps", "hook", "loop_points.json"),
    "agent-fsm": os.path.join(ROOT, "templates", "agent-fsm", "hook_points.json"),
    "eca": os.path.join(HERE, "apps", "eca", "hook_points.json"),
    "mcp": os.path.join(HERE, "apps", "mcp", "hook_points.json"),
}
PHASES = ("before", "after", "on")
CHANGE_TYPES = ("string", "nonempty_string", "object", "any")
FIELD_TYPES = ("int", "string")
CONTRACT = ("phase", "condition", "subject", "change", "block", "key", "entry_keys")   # must match across files
SAID = ("if_blocked", "if_failed", "not_fired_yet")             # kept per file in "said"
NAME = re.compile(r"[a-z0-9_]+\Z")


class PointsBad(ValueError):
    """A hook point declaration, or the hook_points list of an interfaces.json, is bad."""


FailReturned = hook_handle.FailReturned
call_fail = hook_handle.call_fail
Handle = hook_handle.Handle


def provider_path(name):
    """Path of the declaration of a provider aos ships; unknown name = PointsBad."""
    if name not in PROVIDERS:
        raise PointsBad("unknown hook point provider %r (known: %s)" % (name, ", ".join(sorted(PROVIDERS))))
    return PROVIDERS[name]


def _text(v):
    return isinstance(v, str) and bool(v.strip())


def _strings(v):
    return isinstance(v, list) and all(_text(x) for x in v)


def _check_field(where, name, about):
    if isinstance(about, str):
        return
    if not isinstance(about, dict):
        raise PointsBad("%s: field %s must be a sentence or an object" % (where, name))
    if not _text(about.get("about")):
        raise PointsBad("%s: field %s needs about, a non-empty string" % (where, name))
    if not _text(about.get("env")):
        raise PointsBad("%s: field %s needs env, a non-empty string" % (where, name))
    if "type" in about and about["type"] not in FIELD_TYPES:
        raise PointsBad("%s: field %s type must be %s" % (where, name, " or ".join(FIELD_TYPES)))


def _check_point(where, point):
    """Rules 1 to 4 for one point; where = 'FILE: point NAME'."""
    if not isinstance(point, dict):
        raise PointsBad("%s must be a JSON object" % where)
    if not _text(point.get("when")):
        raise PointsBad("%s: when must be a non-empty string" % where)
    if point.get("phase") not in PHASES:
        raise PointsBad("%s: phase must be %s" % (where, ", ".join(PHASES)))
    fields = point.get("fields")
    if not isinstance(fields, dict):
        raise PointsBad("%s: fields must be a JSON object" % where)
    for name, about in fields.items():
        _check_field(where, name, about)
    for k in ("condition", "subject", "key", "if_blocked", "if_failed", "not_fired_yet"):
        if k in point and not _text(point[k]):
            raise PointsBad("%s: %s must be a non-empty string" % (where, k))
    for k in ("entry_keys", "fired_in"):
        if k in point and not _strings(point[k]):
            raise PointsBad("%s: %s must be an array of non-empty strings" % (where, k))
    if "block" in point and not isinstance(point["block"], bool):
        raise PointsBad("%s: block must be true or false" % where)
    change = point.get("change", {})
    if not isinstance(change, dict):
        raise PointsBad("%s: change must be a JSON object" % where)
    for k, t in change.items():
        if t not in CHANGE_TYPES:
            raise PointsBad("%s: change %s must be %s" % (where, k, ", ".join(CHANGE_TYPES)))
        if k not in fields:
            raise PointsBad("%s: change %s is not one of its fields" % (where, k))
    for k in ("condition", "key"):
        if k in point and point[k] not in fields:
            raise PointsBad("%s: %s %s is not one of its fields" % (where, k, point[k]))
    if point.get("block"):
        if point["phase"] == "on":
            raise PointsBad("%s: block true does not go with phase on" % where)
        if "if_blocked" not in point:
            raise PointsBad("%s: block true needs if_blocked" % where)


def read_file(path):
    """One declaration file -> (provider, {name: point}); bad = PointsBad."""
    try:
        with io.open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        raise PointsBad("cannot read hook points %s: %s" % (path, e)) from None
    if not isinstance(doc, dict):
        raise PointsBad("%s must be a JSON object" % path)
    if not _text(doc.get("provider")):
        raise PointsBad("%s: provider must be a non-empty string" % path)
    points = doc.get("points")
    if not isinstance(points, dict):
        raise PointsBad("%s: points must be a JSON object" % path)
    for name, point in points.items():
        if not NAME.match(name):
            raise PointsBad("%s: point name %r may only have a-z, 0-9 and _" % (path, name))
        _check_point("%s: point %s" % (path, name), point)
    return doc["provider"], points


def _contract(point):
    """The keys that must match across files, with their defaults filled in."""
    return {"phase": point["phase"], "condition": point.get("condition"), "subject": point.get("subject"),
            "change": point.get("change", {}), "block": point.get("block", False), "key": point.get("key"),
            "entry_keys": point.get("entry_keys", [])}


def read(paths):
    """Several declaration files -> {name: point} (see the module doc for the merged shape); bad = PointsBad."""
    out = {}
    for path in paths:
        provider, points = read_file(path)
        for name, point in points.items():
            said = dict({"provider": provider, "path": path, "when": point["when"]},
                        **{k: point[k] for k in SAID if k in point})
            if name not in out:
                out[name] = dict(point, fields=dict(point["fields"]), said=[said])
                continue
            have = out[name]
            mine, theirs = _contract(point), _contract(have)
            for k in CONTRACT:
                if mine[k] != theirs[k]:
                    raise PointsBad("%s: point %s: %s differs from %s (%s)"
                                    % (path, name, k, have["said"][0]["path"], have["said"][0]["provider"]))
            for field, about in point["fields"].items():
                have["fields"].setdefault(field, about)
            have["said"].append(said)
    return out


def engine_table(points):
    """{name: point} -> the engine's table {name: {"condition", "intercept", "block"}}."""
    return {name: {"condition": p.get("condition"), "intercept": tuple(p.get("change", {})),
                   "block": p.get("block", False)}
            for name, p in points.items()}


def for_definition(def_dir):
    """read() of the hook_points list in def_dir/interfaces.json; nothing declared = {}; bad = PointsBad."""
    path = os.path.join(def_dir, "interfaces.json")
    try:
        with io.open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise PointsBad("cannot read %s: %s" % (path, e)) from None
    if not isinstance(doc, dict):
        raise PointsBad("%s must be a JSON object" % path)
    decl = doc.get("aos-agent", {})
    if not isinstance(decl, dict):
        raise PointsBad("%s: aos-agent must be a JSON object" % path)
    if "hook_points" not in decl:
        return {}
    items = decl["hook_points"]
    if not isinstance(items, list):
        raise PointsBad("%s: hook_points must be an array" % path)
    paths = []
    for item in items:
        if _text(item):
            paths.append(item if os.path.isabs(item) else os.path.join(def_dir, item))
        elif isinstance(item, dict) and set(item) == {"provider"} and _text(item["provider"]):
            paths.append(provider_path(item["provider"]))
        else:
            raise PointsBad("%s: each item of hook_points must be a path or {\"provider\": NAME}" % path)
    return read(paths)


def open(points=None, *, table=None, lists=None, entries=None, stack=None, fail=None, warn=None, check=None,
         entry_check=None):
    """A Handle to fire a program's points (see the module doc). Wrong arguments = TypeError (a caller's bug)."""
    if (points is None) == (table is None):
        raise TypeError("hook_point.open wants exactly one of points, table")
    if lists is not None and entries is not None:
        raise TypeError("hook_point.open wants at most one of lists, entries")
    if not (isinstance(stack, str) and stack) or not callable(fail):
        raise TypeError("hook_point.open wants stack (a non-empty path) and fail (a function)")
    if table is not None:
        return Handle({}, table, lists, entries, stack, fail, warn, check, entry_check)
    if isinstance(points, (list, tuple)):
        try:
            points = read(points)
        except PointsBad as e:
            call_fail(fail, "PointsBad", str(e))
    return Handle(points, engine_table(points), lists, entries, stack, fail, warn, check, entry_check)
