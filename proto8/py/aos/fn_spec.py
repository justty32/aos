"""fn_spec - compile @fn.tool / @fn.hook functions of an agent.py (or a kernel.py) into programs fn/<name>.py of the definition folder ("pulled out").

Cut 3 of the compile library (line aos-pylib-k3-1120; design thinking/2026-11/20/aos-pylib-plan-1120/03, 04, 07c). The user (11-20):
"抽出來" (pull them out), "兩種都收，明寫的贏", "一起，同一套寫法" (tools and hooks the same way). Used only while compiling.
  tool_item(func)    a function in tools=[...] -> a tool item (like defs.tool) whose entry carries KEY, a reference to the function
  hook_entry(func)   a function in hooks=[...] -> (hook name, entry {"event", "handler": "fn/<name>.py", other keys, KEY})
  programs(...)      after tools.json / hooks.json are worked out: each entry with KEY -> {"path" / "handler": "fn/<name>.py"},
                     plus {"fn/<name>.py": Program(text)}; the file is named after the last name (tools.json key, hook name)
What a function may use (04; user 11-20 question 5 "先不定" = everything else is an error for now, so it can be opened later):
builtins, its own parameters and locals, fn, and names imported at the top of agent.py (one line per name, only those used).
A constant, function or class of agent.py, the compile library (defs, std), a module next to agent.py, a name agent.py does not
define: SpecBad. Outside names come from symtable (the compiler's own table); fn.block from the syntax tree.
The program: setup lines that find aos under $AOS_HOME/lib only (and take fn/ itself off the module path), the imports, the
function as written (decorator included), then fn.main(name). Relative paths in it start at fn/, like any tool (user 11-20
question 7 "照今天工具的規矩"); the workspace is $AOS_WS. Internal (aos.*).
"""
import ast, builtins, os, re, symtable, types

from aos import fn_mark
from aos.spec_base import SpecBad, Program

KEY = "$fn"                     # in an entry: which function it came from (taken out before anything is written)
FOLDER = "fn"
TOOL_RE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")      # = agent_spec_parts.TOOL_RE (aos-tools' NAME_RE)
LIBRARY = ("aos.py.agent.defs", "aos.agent_spec", "aos.py.kernel.defs", "aos.kernel_spec", "aos.spec_unit", "aos.spec_base")
ALLOWED = ("fn", "__file__", "__name__")
_FUNCS = {}                     # KEY value -> the function (alive while agent.py compiles; defs.load runs the base in this process)
_SEEN = {}                      # KEY value -> what its source told (a function is read once)


def _ref(func, what):
    if not isinstance(func, types.FunctionType):
        raise SpecBad("%s: %r is not a function: put @fn.%s on a plain def" % (what, func, what))
    code = func.__code__
    ref = "%s:%d:%s" % (os.path.realpath(code.co_filename), code.co_firstlineno, func.__qualname__)
    _FUNCS[ref] = func
    return ref


def _mark(func, want):
    where = "tools" if want == "tool" else "hooks"
    m = getattr(func, fn_mark.MARK, None)
    label = getattr(func, "__name__", repr(func))
    if not isinstance(m, dict):
        raise SpecBad("%s: %s is a function without a mark: put @fn.%s on it" % (where, label, want))
    if m["kind"] != want:
        raise SpecBad("%s: %s is marked @fn.%s; it goes in %s=[...]" % (where, label, m["kind"], "tools" if m["kind"] == "tool" else "hooks"))
    return m


def tool_item(func):
    """A function in tools=[...] -> {"kind": "tool", "name", "entry": {"path", KEY}} (a wrong one: {"kind": "bad"})."""
    try:
        m = _mark(func, "tool")
        name = m["name"] if m["name"] is not None else func.__name__
        if not isinstance(name, str) or not TOOL_RE.match(name):
            raise SpecBad("tool name %r must be 1-64 letters, digits, _ or -" % (name,))
        return {"kind": "tool", "name": name, "entry": {"path": "%s/%s.py" % (FOLDER, name), KEY: _ref(func, "tool")}}
    except SpecBad as e:
        return {"kind": "bad", "bad": str(e)}


def hook_entry(func):
    """A function in hooks=[...] -> (hook name, entry); the other keys of @fn.hook(...) go into the entry as written. Wrong = SpecBad."""
    m = _mark(func, "hook")
    name = m["name"] if m["name"] is not None else func.__name__
    if not isinstance(name, str) or not name:
        raise SpecBad("hooks: hook %s: name= must be a non-empty string" % func.__name__)
    if not isinstance(m["event"], str) or not m["event"]:
        raise SpecBad("hooks: hook %s needs the event name, like @fn.hook(\"before_tool\")" % name)
    for k in ("event", "handler"):
        if k in m["entry"]:
            raise SpecBad("hooks: hook %s: @fn.hook sets %s itself; leave %s= out" % (name, k, k))
    entry = {"event": m["event"], "handler": "%s/%s.py" % (FOLDER, name)}
    entry.update(m["entry"])
    entry[KEY] = _ref(func, "hook")
    return name, entry


def programs(tools_out, tools_file, hooks_out, hooks_file, events):
    """Replace each entry with KEY in tools_out["tools"] / hooks_out["hooks"] (new dicts; the old entries are not touched) and give
    {"fn/<name>.py": Program}. Paths are relative to the folder of tools.json / hooks.json. events = the hook event table."""
    out, who = {}, {}
    for doc, key, list_file, kind in ((tools_out, "tools", tools_file, "tool"), (hooks_out, "hooks", hooks_file, "hook")):
        table = (doc or {}).get(key) or {}
        for name, entry in list(table.items()):
            if not isinstance(entry, dict) or KEY not in entry:
                continue
            if entry[KEY] not in _FUNCS:
                raise SpecBad("%s %s: %s is a key aos uses for functions; leave it out" % (kind, name, KEY))
            file, what = "%s/%s.py" % (FOLDER, name), "%s %s" % (kind, name)
            if file in out:
                raise SpecBad("%s and %s both compile to %s: give one of them another name (name=)" % (who[file], what, file))
            out[file], who[file] = Program(_program(_FUNCS[entry[KEY]], name, kind, entry.get("event"), events)), what
            new = {k: v for k, v in entry.items() if k != KEY}
            new["path" if kind == "tool" else "handler"] = os.path.relpath(file, os.path.dirname(list_file or "") or ".")
            table[name] = new
    return out


def _program(func, name, kind, event, events):
    what = "%s %s" % (kind, name)
    seen = _read(func, what, kind)
    if kind == "tool":
        if seen["blocks"]:
            raise SpecBad("%s uses fn.block: only a hook can block; a tool reports its own error with fn.fail(\"Code\", \"why\")" % what)
        fn_mark.tool_spec_of(func)                         # the same checks as fn.main does before every run (description, types)
        m = getattr(func, fn_mark.MARK)
        doc = m["description"] if m["description"] is not None else fn_mark.split_doc(func.__doc__)[0]
    else:
        names, _ = fn_mark.signature(func, what)
        if len(names) != 1:
            raise SpecBad("%s takes one parameter, the event: def %s(event)" % (what, func.__name__))
        if seen["blocks"] and not (events or {}).get(event, {}).get("block"):
            raise SpecBad("%s: %s cannot be blocked; fn.block has no effect there" % (what, event))
        doc = fn_mark.cleandoc(func.__doc__) or "a hook handler for %s events" % event
    first = "%s - %s" % (name, doc.strip().split("\n", 1)[0].strip())
    head = '"""%s"""' % first if '"""' not in first and "\\" not in first and not first.endswith('"') else repr(first)
    lines = ["#!/usr/bin/env python3", head] + seen["future"] + _setup(name) + seen["imports"]
    return "\n".join(lines) + "\n\n\n" + seen["source"] + "\n\n\nfn.main(%s)\n" % func.__name__


def _setup(name):
    home = repr("%s: error: HomeMissing AOS_HOME is not set (the aos package is found under $AOS_HOME/lib)\n" % name)
    gone = repr("%s: error: ModuleMissing %%s not found under $AOS_HOME/lib\n" % name)
    return [
        "# ---- setup: find the aos package under $AOS_HOME/lib (keep these lines as they are) ----",
        "import os as _os, sys as _sys",
        "_sys.dont_write_bytecode = True",
        "if _sys.path and _os.path.realpath(_sys.path[0] or _os.curdir) == _os.path.dirname(_os.path.realpath(__file__)):",
        "    del _sys.path[0]          # this fn/ folder: a program called json.py here must not hide the json module",
        "if not _os.environ.get(\"AOS_HOME\"):",
        "    _sys.stderr.write(%s)" % home,
        "    _sys.stdout.write(%s)" % home,
        "    _sys.exit(1)",
        "_sys.path.insert(0, _os.path.join(_os.environ[\"AOS_HOME\"], \"lib\"))",
        "try:",
        "    from aos.py import fn",
        "except ModuleNotFoundError as _e:",
        "    if _e.name != \"aos\" and not (_e.name or \"\").startswith(\"aos.\"):",
        "        raise",
        "    _sys.stderr.write(%s %% _e.name)" % gone,
        "    _sys.stdout.write(%s %% _e.name)" % gone,
        "    _sys.exit(1)",
        "# ---- the function ----"]


def _read(func, what, kind):
    """Find the function in its file and check what it uses -> {"source", "imports", "future", "blocks"} (cached per function)."""
    ref = _ref(func, kind)
    if ref in _SEEN:
        return _SEEN[ref]
    file = os.path.realpath(func.__code__.co_filename)
    try:
        with open(file, encoding="utf-8") as f:
            text = f.read()
        tree = ast.parse(text, file)
    except (OSError, SyntaxError, ValueError):
        raise SpecBad("%s: cannot read its source %s; write the function in agent.py itself" % (what, file)) from None
    line = func.__code__.co_firstlineno
    node = next((n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func.__name__
                 and (n.decorator_list[0].lineno if n.decorator_list else n.lineno) == line), None)
    if node is None or isinstance(node, ast.AsyncFunctionDef) or func.__qualname__ != func.__name__ \
            or len(node.decorator_list) != 1 or not _is_fn_mark(node.decorator_list[0]):
        raise SpecBad("%s must be a plain def at the top of agent.py with only @fn.%s on it (not a lambda, a method, a function "
                      "inside a function, async, or one with another decorator)" % (what, kind))
    bound, imports = _top_bindings(tree), []
    for n in sorted(_outside(node, text, file)):
        imports += _allowed(n, bound, what, os.path.dirname(file))
    order = _import_lines(tree)
    future = sorted({"from __future__ import %s" % a.name for s in tree.body
                     if isinstance(s, ast.ImportFrom) and s.module == "__future__" for a in s.names})
    blocks = any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "block"
                 and isinstance(c.func.value, ast.Name) and c.func.value.id == "fn" for c in ast.walk(node))
    rows = text.split("\n")[node.decorator_list[0].lineno - 1:node.end_lineno]
    _SEEN[ref] = {"source": "\n".join(rows), "imports": sorted(set(imports), key=order.index), "future": future, "blocks": blocks}
    return _SEEN[ref]


def _is_fn_mark(d):
    d = d.func if isinstance(d, ast.Call) else d
    return isinstance(d, ast.Attribute) and d.attr in ("tool", "hook") and isinstance(d.value, ast.Name) and d.value.id == "fn"


def _outside(node, text, file):
    """Names the function takes from outside: what its symbol table calls global (nested scopes too), plus the names in the
    decorator, the defaults and the annotations (those are worked out at the top of the file, so asked one by one)."""
    names = set()

    def walk(t):
        for s in t.get_symbols():
            if s.is_global() and (s.is_referenced() or s.is_assigned()):
                names.add(s.get_name())
        for c in t.get_children():
            walk(c)
    top = symtable.symtable(text, file, "exec")
    for t in top.get_children():
        if t.get_type() == "function" and t.get_name() == node.name and t.get_lineno() in (node.lineno, node.decorator_list[0].lineno):
            walk(t)
            break
    a = node.args
    exprs = list(node.decorator_list) + list(a.defaults) + [d for d in a.kw_defaults if d is not None] + [node.returns] + \
        [x.annotation for x in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg] if x is not None]
    for e in exprs:
        if e is not None:
            t = symtable.symtable(ast.unparse(e), file, "eval")
            names |= {s.get_name() for s in t.get_symbols() if s.is_referenced() and not s.is_assigned()}
            for c in t.get_children():
                walk(c)
    return names


def _import_line(module, level, a):
    level = level or 0
    head = "from %s%s import " % ("." * level, module or "") if module is not None or level else "import "
    return head + a.name + (" as %s" % a.asname if a.asname else "")


def _top_bindings(tree):
    """{name: [(how, line or import text, module, level)]} for names bound at the top of agent.py (also inside if / for / while /
    with / try blocks there, not inside def or class); how = "import", "own", or "library" (bound from defs, std...)."""
    bound, library = {}, set()

    def own(name, line):
        bound.setdefault(name, []).append(("own", line, None, 0))

    def body(stmts):
        for s in stmts:
            if isinstance(s, (ast.Import, ast.ImportFrom)):
                module = s.module if isinstance(s, ast.ImportFrom) else None
                level = getattr(s, "level", 0) or 0
                if module == "__future__":
                    continue
                for a in s.names:
                    full = (module + "." + a.name) if module else a.name
                    n = a.asname or (a.name if isinstance(s, ast.ImportFrom) else a.name.split(".")[0])
                    bound.setdefault(n, []).append(("import", _import_line(module, level, a), module or a.name, level))
                    if full.startswith(LIBRARY) or (module or "").startswith(LIBRARY):
                        library.add(n)
            elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                own(s.name, s.lineno)
            elif isinstance(s, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.With, ast.AsyncWith, ast.Try)):
                heads = [s.target] if isinstance(s, (ast.For, ast.AsyncFor)) else \
                    [i.optional_vars for i in s.items if i.optional_vars] if isinstance(s, (ast.With, ast.AsyncWith)) else []
                for t in heads:
                    for x in ast.walk(t):
                        if isinstance(x, ast.Name):
                            own(x.id, s.lineno)
                for h in getattr(s, "handlers", []):
                    if h.name:
                        own(h.name, h.lineno)
                    body(h.body)
                for part in ("body", "orelse", "finalbody"):
                    body(getattr(s, part, []))
            else:
                uses = {x.id for x in ast.walk(s) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)}
                for x in ast.walk(s):
                    if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                        own(x.id, s.lineno)
                        if uses & library:
                            library.add(x.id)
    body(tree.body)
    return {n: [("library",) + b[1:] for b in ways] if n in library else ways for n, ways in bound.items()}


def _import_lines(tree):
    return [_import_line(s.module if isinstance(s, ast.ImportFrom) else None, getattr(s, "level", 0), a)
            for s in ast.walk(tree) if isinstance(s, (ast.Import, ast.ImportFrom)) for a in s.names]


def _allowed(n, bound, what, here):
    """One outside name -> the import lines it needs ([] = nothing to add); not allowed = SpecBad."""
    ways = bound.get(n)
    if n in ALLOWED:
        return []
    if not ways:
        if hasattr(builtins, n):
            return []
        raise SpecBad("%s uses %s, which agent.py neither defines nor imports at the top" % (what, n))
    if any(b[0] == "library" for b in ways):
        raise SpecBad("%s uses %s, the compile library; at run time use fn.fail / fn.block" % (what, n))
    own = [b for b in ways if b[0] == "own"]
    if own:
        raise SpecBad("%s uses %s, defined at the top of agent.py (line %d); a compiled function cannot see it: "
                      "move it into the function" % (what, n, own[0][1]))
    lines = []
    for _, line, module, level in ways:
        top = module.split(".")[0]
        nearby = os.path.isfile(os.path.join(here, top + ".py")) or os.path.isdir(os.path.join(here, top))
        if level or (nearby and top != "aos"):        # aos itself is found under $AOS_HOME/lib at run time
            raise SpecBad("%s imports %s, a module next to agent.py; a compiled function cannot find it at run time" % (what, module or n))
        lines.append(line)
    return lines
