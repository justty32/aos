"""hook_lists - read hookeds lists (what is hooked: a JSON object {hook name: entry or null}) in order, a later file overriding an earlier one by name.

Design: the user 11-21 (proto8/thinking/2026-11/21/hook-points-格式-使用者審-1121.md, 6th and 7th: "hooks.json, hookeds.json,
hooks表示有哪些鉤子，hookeds表示有哪些被勾着"; aos-hook-簡化-1121/07: "簡化到第四層", "庫也極簡"); line top-1121-hooknew.
The one reader of hookeds lists: aos-hook fire, the agent family (aos.agentlib.hooks) and the kernel all read theirs here.
It checks only what the engine itself needs (a name it can make a folder of, an event, a handler, timeout_ms); every
other key of an entry belongs to whoever fires the event (the agent's condition and on_clock keys...) and is kept as it is.
Standard library only; prints nothing, never exits: a bad list is HooksBad.

A hookeds list (hookeds.json, kernel_hookeds.json, the stack's copy...):
    {"description": "a sentence (optional; not a hook)", "NAME": {"event": "before_tool", "handler": PATH or directive,
     "timeout_ms": 60000, ...the firing program's own keys}, "OTHER": null}
    null turns off a hook of an earlier file of the same name. A file that does not exist has no hooks.

API:
    HooksBad                  a list (or a name, or an entry) is bad; ValueError subclass
    check_name(name)          a hook name: non-empty, no /, not starting with ., not "description"
    check_entry(entry)        an entry: object; event a non-empty string; handler a non-empty string or directive
                              object; timeout_ms (when given) a whole number >= 0
    read(path)                -> {name: entry or None} of one file, checked; missing file = {}
    load(paths)               -> {name: entry} over the files in order (later wins by name, null = off); each entry
                              gets "from" (its file) and "base" (the folder relative handler paths start from)
"""
import json
import os

RESERVED = "description"                         # a sentence about the file, not a hook


class HooksBad(ValueError):
    """A hookeds list, a hook name or an entry is bad."""


def check_name(name):
    """A hook name is also the name of its folder in the stack (STACK/hookeds/NAME/)."""
    if not isinstance(name, str) or not name or "/" in name or name.startswith(".") or name == RESERVED:
        raise HooksBad("hook name %r must be non-empty, without / and not start with . (and not be %r)" % (name, RESERVED))


def check_entry(entry):
    """The keys the engine reads; unknown keys are kept for the firing program (C-48). Bad = HooksBad (no name in it)."""
    if not isinstance(entry, dict):
        raise HooksBad("must be a JSON object or null")
    if not (isinstance(entry.get("event"), str) and entry["event"]):
        raise HooksBad("event must be a non-empty string")
    target = entry.get("handler")
    if not ((isinstance(target, str) and target) or (isinstance(target, dict) and target)):
        raise HooksBad("handler must be a non-empty string or a directive object")
    if "timeout_ms" in entry:
        t = entry["timeout_ms"]
        if not isinstance(t, int) or isinstance(t, bool) or t < 0:
            raise HooksBad("timeout_ms must be a whole number of milliseconds >= 0 (0 = no limit)")


def read(path):
    """One list file -> {name: entry or None}; missing = {}; bad = HooksBad naming the file and the hook."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise HooksBad("cannot read %s: %s" % (path, e)) from None
    if not isinstance(doc, dict):
        raise HooksBad("%s must be a JSON object {hook name: entry or null}" % path)
    out = {}
    for name, entry in doc.items():
        if name == RESERVED:
            continue
        try:
            check_name(name)
        except HooksBad as e:
            raise HooksBad("%s: %s" % (path, e)) from None
        if entry is not None:
            try:
                check_entry(entry)
            except HooksBad as e:
                raise HooksBad("hook %s in %s: %s" % (name, path, e)) from None
        out[name] = entry
    return out


def load(paths, check=None):
    """The list files in order -> {name: entry + "from" + "base"}; check(entry) = the caller's own rules (raise HooksBad)."""
    out = {}
    for path in paths:
        path = os.path.abspath(path)
        for name, entry in read(path).items():
            if entry is None:
                out.pop(name, None)
                continue
            if check is not None:
                try:
                    check(entry)
                except HooksBad as e:
                    raise HooksBad("hook %s in %s: %s" % (name, path, e)) from None
            out[name] = dict(entry, **{"from": path, "base": os.path.dirname(path)})
    return out
