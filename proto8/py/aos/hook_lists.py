"""hook_lists - read hooks lists (JSON files with a "hooks" table) against a hook point table, and check the values hooks change against the declared types; the part aos.hook_point.open puts between the declarations and the engine.

Design: proto8/thinking/2026-11/20/aos-hook-plan-1120 (04 the small library, 01 entry_keys, 12 what holds after review).
Moved here from py/aos/apps/hook/lists.py (cut 4) in cut 2, so aos-hook and every program that opens a hook_point
handle read lists the same way. Standard library plus the engine aos.hook_run; prints nothing, never exits.

API:
    owners(points)        -> {key: [points that take it]} from the points' entry_keys
    load(paths, table, owners=None, entry_check=None) -> {name: entry} for aos.hook_run.fire: the hooks tables of
                             the files in order, a later file overrides an earlier one by name, null = turned off;
                             a missing file = no hooks. Each entry: the engine's common checks against table, a key of
                             owners only on its points, then entry_check(entry) (the provider's own rules; raises
                             HooksBad). Bad = hook_run.HooksBad naming the hook and the file
    type_check(points)    -> check(event, key, value) for hook_run.fire: a changed value must have the declared
                             change type (string, nonempty_string, object, any); bad = ValueError, one English sentence
"""
import json
import os

from aos import hook_run


def owners(points):
    """{key: [points that take it]} from the points' entry_keys."""
    out = {}
    for name, point in points.items():
        for key in point.get("entry_keys", []):
            out.setdefault(key, []).append(name)
    return out


def _check_entry(entry, table, owned, entry_check):
    """The engine's checks of the common keys, then: a key of some point's entry_keys only on that point (01, B5)."""
    hook_run.validate_entry(entry, table)
    for key, events in sorted(owned.items()):
        if key in entry and entry["event"] not in events:
            raise hook_run.HooksBad("%s is only for event %s" % (key, " or ".join(sorted(events))))
    if entry_check is not None:
        entry_check(entry)


def _read(path, table, owned, entry_check):
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
                _check_entry(entry, table, owned, entry_check)
            except hook_run.HooksBad as e:
                raise hook_run.HooksBad("hook %s in %s: %s" % (name, path, e)) from None
    return hooks


def load(paths, table, owners=None, entry_check=None):
    """The list files in order -> {name: entry} completed with the engine's defaults, "from" and "base"."""
    owned = owners or {}
    out = {}
    for path in paths:
        path = os.path.abspath(path)
        for name, entry in _read(path, table, owned, entry_check).items():
            if entry is None:
                out.pop(name, None)
            else:
                out[name] = hook_run.complete(entry, path)
    return out


def type_check(points):
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
