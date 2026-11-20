"""lists - aos-hook's part between the declarations and the engine: read the --list files (hooks tables), check their entries against the points, check the values hooks change.

Design: proto8/thinking/2026-11/20/aos-hook-plan-1120 (05 the command, 01 entry_keys, 04 the change types; 12 is what holds).
Cut 4 of that plan: only aos-hook uses this. Running the hooks is aos.hook_run (the same engine the agents and the
kernel use); this file only decides which entries there are and which changed values are allowed.
Cut 2 (aos.hook_point.open) needs the same three things and may move them there.

API:
    load(paths, points) -> {name: entry} for aos.hook_run.fire: the hooks tables of the files, a later file overrides
                           an earlier one by name, null = turned off; a missing file = no hooks. Bad = hook_run.HooksBad
    check(points)       -> check(event, key, value) for hook_run.fire: the value must have the declared change type
                           (string, nonempty_string, object, any); bad = ValueError with one English sentence
"""
import json
import os

from aos import hook_point, hook_run


def _entry_keys(points):
    """{key: [points that take it]} from the points' entry_keys."""
    out = {}
    for name, point in points.items():
        for key in point.get("entry_keys", []):
            out.setdefault(key, []).append(name)
    return out


def _check_entry(entry, table, owners):
    """The engine's checks of the common keys, then: a key of some point's entry_keys only on that point (01, B5)."""
    hook_run.validate_entry(entry, table)
    for key, events in sorted(owners.items()):
        if key in entry and entry["event"] not in events:
            raise hook_run.HooksBad("%s is only for event %s" % (key, " or ".join(sorted(events))))


def _read(path, table, owners):
    """One list file -> {name: entry or None}; missing = {}."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise hook_run.HooksBad("cannot read %s: %s" % (path, e)) from None
    if not isinstance(doc, dict):
        raise hook_run.HooksBad("%s must be a JSON object" % path)
    hooks = doc.get("hooks", {})
    if not isinstance(hooks, dict):
        raise hook_run.HooksBad("hooks in %s must be a JSON object" % path)
    for name, entry in hooks.items():
        try:
            hook_run.validate_name(name)
        except hook_run.HooksBad as e:
            raise hook_run.HooksBad("hook name %r in %s %s" % (name, path, e)) from None
        if entry is not None:
            try:
                _check_entry(entry, table, owners)
            except hook_run.HooksBad as e:
                raise hook_run.HooksBad("hook %s in %s: %s" % (name, path, e)) from None
    return hooks


def load(paths, points):
    """The --list files in order -> {name: entry} completed with the engine's defaults, "from" and "base"."""
    table, owners = hook_point.engine_table(points), _entry_keys(points)
    out = {}
    for path in paths:
        path = os.path.abspath(path)
        for name, entry in _read(path, table, owners).items():
            if entry is None:
                out.pop(name, None)
            else:
                out[name] = hook_run.complete(entry, path)
    return out


def check(points):
    """The engine's check hook: a changed value must have the type the point declares for that key."""
    def one(event, key, value):
        want = points[event].get("change", {}).get(key, "any")
        if want == "string" and not isinstance(value, str):
            raise ValueError("%s in stdout must be a string" % key)
        if want == "nonempty_string" and not (isinstance(value, str) and value.strip()):
            raise ValueError("%s in stdout must be a non-empty string" % key)
        if want == "object" and not isinstance(value, dict):
            raise ValueError("%s in stdout must be a JSON object" % key)
    return one
