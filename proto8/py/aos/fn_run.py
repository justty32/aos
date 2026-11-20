"""fn_run - fn.main(function): the compile flags and running a marked function as a tool or as a hook handler; fn.fail and fn.block.

Cut 1 of the compile library (line aos-pylib-k1-1120, design thinking/2026-11/20/aos-pylib-plan-1120/03 and 07b); main() and the
result printing came here from tool_spec (which keeps tooldef / metainfo / write for tools_def), outputs unchanged.
A tool (@fn.tool):
  --compile [LOCATION]  write _tooldef and _metainfo (a folder: two files; FILE.json#/POINTER: two keys); default = the script's folder
  --dry-run             print both as one JSON object, write nothing
  --tooldef, --metainfo print one of them (aos-tools asks a program --tooldef)
  anything else         run it through tool_io: check the arguments (types, required, enum, unknown keys), fill defaults, call the
                        function with them as keyword arguments, print the result (a string as is, None nothing, else one JSON line)
  fn.fail codes in the source are scanned only for those four flags and --help; a plain run does not read the source.
A hook (@fn.hook("event")): stdin = the event JSON, given to the function as its one parameter. It returns None (go on, exit 0),
  a dict (keys to change, printed as one JSON line, exit 0) or fn.block("why") (the reason is printed, exit 10 = blocked);
  anything else = ReplyBad, an exception = RunFailed with the line; both exit 1.
The name at the start of error lines: name= if given, else from the file (tool.py = its folder, other.py = other).
"""
import json, os, signal, sys, traceback

from aos import fn_mark, spec_base, tool_io, tool_spec
from aos.spec_base import SpecBad

SCAN = ("--tooldef", "--metainfo", "--compile", "--dry-run")
BLOCK = 10                                       # same as hook_run.BLOCK (N-43: 10 = "no", not an error)


class Fail(Exception):
    """Raised by fn.fail: this tool's own error line (code and reason)."""
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code = code


def fail(code, reason):
    """In a tool or hook function: fn.fail("NotFound", "no such city") -> "name: error: NotFound no such city", exit 1."""
    raise Fail(code, reason)


class Block:
    """What fn.block returns; only a hook may return it."""
    def __init__(self, reason):
        self.reason = reason

    def __repr__(self):
        return "fn.block(%r)" % self.reason


def block(reason):
    """In a hook function: return fn.block("why") stops the event; the reason is what the engine reports."""
    return Block(str(reason))


def _print_result(result):
    if result is None:
        return
    if isinstance(result, str):
        text = result
    else:
        try:
            text = json.dumps(result, ensure_ascii=False)
        except (TypeError, ValueError):
            text = str(result)
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    sys.stdout.flush()


def _where(e, script):
    frames = [f for f in traceback.extract_tb(e.__traceback__) if os.path.realpath(f.filename) == script]
    return " (%s line %d)" % (os.path.basename(script), frames[-1].lineno) if frames else ""


def main(func):
    """The last line of a tool or hook file: fn.main(the marked function)."""
    script = os.path.realpath(getattr(getattr(func, "__code__", None), "co_filename", None) or sys.argv[0])
    m = getattr(func, fn_mark.MARK, None) if callable(func) else None
    named = m.get("name") if isinstance(m, dict) else None
    tool_io.NAME = named if isinstance(named, str) and named else spec_base.prog_name(script, "tool.py")
    try:
        m = fn_mark.mark_of(func)
    except SpecBad as e:
        tool_io.die("SpecBad", "%s (fix %s)" % (e, os.path.basename(script)))
    (_hook if m["kind"] == "hook" else _tool)(func, m, script)


def _tool(func, m, script):
    argv = sys.argv[1:]
    scanned = tool_spec.errors_in(script) if argv[:1] in [[f] for f in SCAN] or "--help" in argv else []
    try:
        _, td, mi = fn_mark.tool_spec_of(func, scanned)
    except SpecBad as e:
        tool_io.die("SpecBad", "%s (fix the declaration in %s)" % (e, os.path.basename(script)))
    if argv[:1] in (["--tooldef"], ["--metainfo"]):
        print(json.dumps(td if argv[0] == "--tooldef" else mi, ensure_ascii=False, indent=2))
        sys.exit(0)
    if argv[:1] in (["--compile"], ["--dry-run"]):
        location = spec_base.location(argv[0], argv[1:], argv, script, "usage: python3 %s --compile [LOCATION] | --dry-run"
                                      % os.path.basename(script), tool_io.die)
    if argv[:1] == ["--dry-run"]:
        print(json.dumps({"_tooldef.json": td, "_metainfo.json": mi}, ensure_ascii=False, indent=2))
        sys.exit(0)
    if argv[:1] == ["--compile"]:
        try:
            for target in tool_spec.write(location, td, mi):
                print("wrote %s" % target)
        except (OSError, SpecBad) as e:
            tool_io.die("WriteFailed", str(e), echo=False)
        sys.exit(0)
    tool_io.start(tool_io.NAME, None, tooldef=td)
    args = tool_io.arguments()
    for key, node in td["parameters"]["properties"].items():
        if key not in args and "default" in node:
            args[key] = node["default"]
        elif key in args and "enum" in node and args[key] not in node["enum"]:
            tool_io.die("ArgumentsBad", "%s must be one of: %s (got %s)" % (key, ", ".join(map(str, node["enum"])), json.dumps(args[key])))
    try:
        result = func(**args)
    except (Fail, tool_io.Error) as e:
        tool_io.die(e.code, str(e))
    except Exception as e:      # noqa: BLE001  for the brain: which line, which exception
        tool_io.die("RunFailed", "%s() raised %s: %s%s" % (func.__name__, type(e).__name__, e, _where(e, script)))
    _print_result(result)


def _hook(func, m, script):
    name, base = tool_io.NAME, os.path.basename(script)
    if not isinstance(m["event"], str) or not m["event"]:
        tool_io.die("SpecBad", "hook %s needs the event name, like @fn.hook(\"before_tool\") (fix the declaration in %s)" % (func.__name__, base))
    try:
        names, _ = fn_mark.signature(func, "hook %s" % func.__name__)
    except SpecBad as e:
        tool_io.die("SpecBad", "%s (fix the declaration in %s)" % (e, base))
    if len(names) != 1:
        tool_io.die("SpecBad", "hook %s takes one parameter, the event: def %s(event) (fix the declaration in %s)"
                    % (func.__name__, func.__name__, base))
    argv = sys.argv[1:]
    if argv == ["--help"]:
        print("%s - a hook handler for %s events (%s)\nusage: %s < EVENT.json   (the hook engine runs it with aos-exec)\n"
              "Prints nothing (go on), one JSON object (keys to change), or the reason and exit 10 (blocked).\n"
              "On error: one line \"%s: error: CODE reason\" on stderr and stdout, exit 1. Error codes: ArgumentsBad, ReplyBad, RunFailed"
              % (name, m["event"], fn_mark.cleandoc(func.__doc__).split("\n", 1)[0] or "no docstring", name, name))
        sys.exit(0)
    if argv:
        tool_io.die("ArgumentsBad", "a hook takes no arguments: %s (usage: %s < EVENT.json)" % (" ".join(argv), name))
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(130))
    try:
        event = json.loads(sys.stdin.read() or "null")
    except ValueError as e:
        tool_io.die("ArgumentsBad", "stdin is not JSON: %s" % e)
    if not isinstance(event, dict):
        tool_io.die("ArgumentsBad", "stdin must be the event JSON object")
    try:
        reply = func(event)
    except (Fail, tool_io.Error) as e:
        tool_io.die(e.code, str(e))
    except Exception as e:      # noqa: BLE001
        tool_io.die("RunFailed", "%s: %s%s" % (type(e).__name__, e, _where(e, script)))
    if reply is None:
        sys.exit(0)
    if isinstance(reply, Block):
        if reply.reason:
            sys.stdout.write(reply.reason if reply.reason.endswith("\n") else reply.reason + "\n")
        sys.stdout.flush()
        sys.exit(BLOCK)
    try:
        text = json.dumps(reply, ensure_ascii=False) if isinstance(reply, dict) else None
    except (TypeError, ValueError) as e:
        tool_io.die("ReplyBad", "hook %s returned a dict that is not JSON: %s" % (func.__name__, e))
    if text is None:
        tool_io.die("ReplyBad", "hook %s returned %s; return None, a dict of the keys to change, or fn.block(\"why\")"
                    % (func.__name__, type(reply).__name__))
    print(text)
