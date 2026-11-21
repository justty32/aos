"""hook_point - where a definition's hook files are (the "hooks" and "hookeds" keys at the top of its interfaces.json, directives allowed) and how to read hook point declarations.

Design: the user 11-21 (proto8/thinking/2026-11/21/hook-points-格式-使用者審-1121.md, 6th to 8th): one declaration file is
an object whose keys are hook ids, each with a required input schema, other keys free ("硬性規定要有id，要有input
schema，剩下其他key就是想放啥放啥"); interfaces.json says "hooks" (what can be hooked) and "hookeds" (what is hooked), a file
name or an array of them, "interfaces.json必須支援指示詞"; kernel 11-21 1st/2nd: both keys at the top of interfaces.json.
"宣告這東西只是參考" (kernel 11-21 4th): no program refuses to run or to hook because of a declaration; aos-hook fire
and the engine never read one. Readers: tests and people (and whoever wants the declared input schemas). Line
top-1121-hooknew.
Standard library plus aos.directive_value (directives are resolved only for items that are directive objects, so a
plain file name costs no process); prints nothing, never exits: errors are InterfaceBad / PointsBad.

interfaces.json (top level):
    "hooks":   "hooks.json" | ["hooks.json", {"$env": "AOS_HOME", "$path": "/lib/aos/apps/hook/loop_hooks.json"}, ...]
    "hookeds": "hookeds.json" | [...]
    A string is a file name (relative = from the definition folder); an object is a directive that resolves to one.
A declaration file (hooks.json):
    {"description": "a sentence (optional; not a point)", "ID": {"input": {JSON Schema of what a handler gets}, ...free}}

API:
    InterfaceBad              interfaces.json cannot be read, or its hooks / hookeds value is not one of the above
    PointsBad                 a declaration file is bad
    items(def_dir, key)       -> [(written item, absolute path)] of def_dir/interfaces.json[key]; no file or no key = []
    files(def_dir, key)       -> [absolute path] (the paths of items())
    layers(def_dir, stack)    -> the hookeds lists to read for a definition running in stack, in order: the files of
                                 "hookeds", then STACK/ITEM for each item that is a relative file name (the stack's own
                                 copy, which overrides the definition's by name); stack None = only the definition's
    own(def_dir, stack)       -> STACK/ITEM of the first relative item of "hookeds" (the copy aos-agent hook writes), or None
    read(paths)               -> {id: point} over several declaration files; an id in two files: the first one counts
    declared(def_dir)         -> read(files(def_dir, "hooks"))
"""
import json
import os
import re

from aos import directive_value

NAME = "interfaces.json"
KEYS = ("hooks", "hookeds")
ID = re.compile(r"[a-z0-9_]+\Z")


class InterfaceBad(ValueError):
    """interfaces.json cannot be read, or its hooks / hookeds is not a file name, a directive or an array of them."""


class PointsBad(ValueError):
    """A hook point declaration file is bad."""


def _doc(def_dir):
    path = os.path.join(def_dir, NAME)
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return path, {}
    except (OSError, ValueError) as e:
        raise InterfaceBad("cannot read %s: %s" % (path, e)) from None
    if not isinstance(doc, dict):
        raise InterfaceBad("%s must be a JSON object" % path)
    return path, doc


def items(def_dir, key):
    """[(item as written, absolute path)] for interfaces.json[key] (key = hooks or hookeds)."""
    path, doc = _doc(def_dir)
    if key not in doc:
        return []
    value = doc[key]
    many = isinstance(value, list)
    out = []
    for i, item in enumerate(value if many else [value]):
        where = "%s: %s%s" % (path, key, "[%d]" % i if many else "")
        if isinstance(item, dict) and item:
            try:
                got = directive_value.resolve(item, def_dir, path, at=directive_value.pointer(key, *([i] if many else [])))
            except directive_value.Error as e:
                raise InterfaceBad("%s cannot be resolved: %s" % (where, e)) from None
        else:
            got = item
        if not (isinstance(got, str) and got):
            raise InterfaceBad("%s must be a file name or a directive giving one (or an array of those), got %s"
                               % (where, json.dumps(item, ensure_ascii=False)))
        out.append((item, got if os.path.isabs(got) else os.path.join(os.path.abspath(def_dir), got)))
    return out


def files(def_dir, key):
    return [p for _, p in items(def_dir, key)]


def _relative(item):
    return isinstance(item, str) and not os.path.isabs(item) and ".." not in item.split("/")


def layers(def_dir, stack=None):
    got = items(def_dir, "hookeds")
    out = [p for _, p in got]
    if stack:
        out += [os.path.join(os.path.abspath(stack), item) for item, _ in got if _relative(item)]
    return out


def own(def_dir, stack):
    for item, _ in items(def_dir, "hookeds"):
        if _relative(item):
            return os.path.join(os.path.abspath(stack), item)
    return None


def read(paths):
    out = {}
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError) as e:
            raise PointsBad("cannot read hook points %s: %s" % (path, e)) from None
        if not isinstance(doc, dict):
            raise PointsBad("%s must be a JSON object {hook id: point}" % path)
        for name, point in doc.items():
            if name == "description":
                continue
            if not ID.match(name):
                raise PointsBad("%s: hook id %r may only have a-z, 0-9 and _" % (path, name))
            if not (isinstance(point, dict) and isinstance(point.get("input"), dict)):
                raise PointsBad("%s: point %s must be an object with input, a JSON Schema object" % (path, name))
            out.setdefault(name, point)
    return out


def declared(def_dir):
    return read(files(def_dir, "hooks"))
