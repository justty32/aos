"""fn_mark - the marks behind @fn.tool / @fn.hook / fn.param, and the tool description they compile to (name, _tooldef, _metainfo).

Cut 1 of the compile library (line aos-pylib-k1-1120, design thinking/2026-11/20/aos-pylib-plan-1120/03 and 07b).
A decorator only puts a mark on the function and returns the same function; nothing is checked until tool_spec_of() runs
(at --compile, --dry-run, --tooldef, --metainfo, and before every run). The rule for description and parameters is
"both are taken, the written one wins", one parameter at a time:
  description   the docstring up to the "Args:" line, or description= (replaces it whole)
  a parameter   type from the annotation (str int float bool list dict, list[str]...), description from "name: ..." under
                Args:, or fn.param("name", type, description, enum=, items=) for that parameter (replaces it whole)
  required      no default in the signature; a default is written into the description (never written by hand)
  errors        errors=[...] plus what the caller scanned (fn.fail codes in the source)
  meta          the N-68 defaults, keys of meta= win
Assembly goes to tool_spec.tooldef / tool_spec.metainfo. No inspect (the signature comes from the code object).
Internal (aos.*): people import it as aos.py.fn.
"""
import re

from aos import tool_spec
from aos.spec_base import SpecBad

MARK = "_aos_fn"
TYPES = {"str": "string", "int": "integer", "float": "number", "bool": "boolean", "list": "array", "dict": "object"}
PLAIN = "str, int, float, bool, list, dict"
_ITEM_RE = re.compile(r"(list|dict)\[\s*(\w+)\s*(?:,[^\]]*)?\]\Z")
_ARG_RE = re.compile(r"([A-Za-z_]\w*)\s*:\s*(.*)\Z")
_SECTION_RE = re.compile(r"\w+:\Z")


def tool(func=None, *, name=None, description=None, params=None, errors=None, meta=None):
    """@fn.tool or @fn.tool(name=, description=, params=[fn.param(...)], errors=[...], meta={...}): mark a function as a tool."""
    keys = {"kind": "tool", "name": name, "description": description, "params": params, "errors": errors, "meta": meta}
    if callable(func):
        setattr(func, MARK, keys)
        return func
    if func is not None:
        raise TypeError("fn.tool takes the function, or only keyword arguments: @fn.tool(description=...)")

    def mark(f):
        setattr(f, MARK, dict(keys))
        return f
    return mark


def hook(event=None, *, name=None, **entry):
    """@fn.hook("before_tool", condition=..., timeout_ms=..., name=...): mark a function as a hook handler; its other keywords go into the entry as written."""
    if callable(event):                         # bare @fn.hook: remembered, reported by fn.main
        setattr(event, MARK, {"kind": "hook", "event": None, "name": name, "entry": entry})
        return event
    cell = dict(entry)

    def mark(f):
        setattr(f, MARK, {"kind": "hook", "event": event, "name": name, "entry": dict(cell)})
        return f
    return mark


def param(name, type, description, enum=None, items=None):
    """fn.param("b", "integer", "the second number", enum=[1, 2]): one parameter written out; required and default come from the signature."""
    return {"name": name, "type": type, "description": description, "enum": enum, "items": items, "fn_param": True}


def mark_of(func):
    m = getattr(func, MARK, None) if callable(func) else None
    if not isinstance(m, dict):
        what = getattr(func, "__name__", repr(func))
        raise SpecBad("%s is not marked: put @fn.tool (or @fn.hook(\"event\")) on the function, then fn.main(it)" % what)
    return m


def cleandoc(doc):
    """Like inspect.cleandoc: drop the common indent of the lines after the first, and blank lines at both ends."""
    lines = (doc or "").expandtabs().split("\n")
    rest = [len(x) - len(x.lstrip()) for x in lines[1:] if x.strip()]
    cut = min(rest) if rest else 0
    lines = [lines[0].strip()] + [x[cut:].rstrip() for x in lines[1:]]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def split_doc(doc):
    """docstring -> (description, {parameter: description}). Args: lines are "name: text"; a deeper line goes on; a line like
    "Returns:" (one word and a colon), or one less indented than the entries, ends the Args part."""
    lines = cleandoc(doc).split("\n")
    at = next((i for i, x in enumerate(lines) if x.strip() == "Args:"), None)
    if at is None:
        return "\n".join(lines).strip(), {}
    found, indent, last = {}, None, None
    for raw in lines[at + 1:]:
        if not raw.strip():
            continue
        depth, text = len(raw) - len(raw.lstrip()), raw.strip()
        if indent is None:
            indent = depth
        if depth > indent and last is not None:
            found[last] = (found[last] + " " + text).strip()
            continue
        m = _ARG_RE.match(text)
        if depth < indent or _SECTION_RE.match(text) or not m:
            break
        last = m.group(1)
        found[last] = m.group(2).strip()
    return "\n".join(lines[:at]).strip(), found


def json_type(note):
    """An annotation (a type, list[str], or the same written as a string) -> (JSON type, items type or None); unknown -> (None, None)."""
    if isinstance(note, str):
        text = note.strip().replace("builtins.", "")
        if text in TYPES:
            return TYPES[text], None
        m = _ITEM_RE.match(text)
        if m and m.group(1) == "dict":
            return "object", None
        if m and m.group(2) in TYPES:
            return "array", TYPES[m.group(2)]
        return None, None
    origin, args = getattr(note, "__origin__", None), getattr(note, "__args__", ())
    if origin is dict:
        return "object", None
    if origin is list:
        inner = json_type(args[0]) if len(args) == 1 else (None, None)
        return ("array", inner[0]) if inner[0] and inner[1] is None else (None, None)
    if origin is None and isinstance(note, type) and note.__name__ in TYPES and note.__module__ == "builtins":
        return TYPES[note.__name__], None
    return None, None


def signature(func, what):
    """(names in order, {name: default}) from the code object; *args, **kwargs, positional-only and keyword-only = SpecBad."""
    code = func.__code__
    if code.co_flags & 0x0C or code.co_posonlyargcount or code.co_kwonlyargcount:
        raise SpecBad("%s: plain named parameters only (no *args, **kwargs, / or *)" % what)
    names = list(code.co_varnames[:code.co_argcount])
    defaults = func.__defaults__ or ()
    return names, dict(zip(names[len(names) - len(defaults):], defaults))


def _annotations(func):
    try:
        return dict(getattr(func, "__annotations__", None) or {})
    except Exception:                           # noqa: BLE001  an annotation that cannot be evaluated counts as none
        return {}


def _names_in(code):
    """Global and attribute names a function's code uses, nested functions and comprehensions included."""
    out = set(code.co_names)
    for c in code.co_consts:
        if hasattr(c, "co_names"):
            out |= _names_in(c)
    return out


def tool_spec_of(func, scanned=()):
    """A marked tool function -> (tool name, _tooldef, _metainfo); scanned = error codes found in the source. Wrong = SpecBad."""
    m = mark_of(func)
    if m["kind"] != "tool":
        raise SpecBad("%s is a hook, not a tool" % func.__name__)
    name = m["name"] if m["name"] is not None else func.__name__
    if not isinstance(name, str) or not name:
        raise SpecBad("tool %s: name= must be a non-empty string" % func.__name__)
    what = "tool %s" % name
    if {"fn", "block"} <= _names_in(func.__code__):
        raise SpecBad("%s uses fn.block: only a hook can block; a tool reports its own error with fn.fail(\"Code\", \"why\")" % what)
    doc_desc, doc_args = split_doc(func.__doc__)
    desc = m["description"] if m["description"] is not None else doc_desc
    if not isinstance(desc, str) or not desc.strip():
        raise SpecBad("%s has no description: write a docstring, or description=" % what)
    names, defaults = signature(func, what)
    for n in doc_args:
        if n not in names:
            raise SpecBad("%s: Args: in the docstring names %s, but the function has no parameter %s" % (what, n, n))
    written = {}
    for p in m["params"] or ():
        if not isinstance(p, dict) or not p.get("fn_param"):
            raise SpecBad("%s: each item of params= must come from fn.param(...), got %r" % (what, p))
        if p["name"] in written:
            raise SpecBad("%s: fn.param(%r, ...) is written twice" % (what, p["name"]))
        if p["name"] not in names:
            raise SpecBad("%s: fn.param(%r, ...), but the function has no parameter %s" % (what, p["name"], p["name"]))
        written[p["name"]] = p
    notes, params = _annotations(func), []
    for n in names:
        default = defaults.get(n, tool_spec._NO)
        if n in written:
            p = written[n]
            params.append(tool_spec.param(n, p["type"], p["description"], default=default, enum=p["enum"], items=p["items"]))
            continue
        t, items = json_type(notes[n]) if n in notes else (None, None)
        if t is None:
            raise SpecBad("parameter %s needs a type (%s), or fn.param(\"%s\", ...)" % (n, PLAIN, n))
        if not doc_args.get(n):
            raise SpecBad("parameter %s has no description: add \"%s: ...\" under Args: in the docstring, or fn.param(\"%s\", ...)" % (n, n, n))
        params.append(tool_spec.param(n, t, doc_args[n], default=default, items=items))
    errors = m["errors"] or []
    if not isinstance(errors, (list, tuple)):
        raise SpecBad("%s: errors= must be a list of codes like [\"CityMissing\"]" % what)
    td = tool_spec.tooldef(desc, params, list(errors) + list(scanned))
    return name, td, tool_spec.metainfo(desc, m["meta"])
