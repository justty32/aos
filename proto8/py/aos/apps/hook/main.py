"""aos-hook - fire a hook event from any program (C++, shell, ...), list the points of hook_points.json declarations, check declarations and hooks lists.

Design: proto8/thinking/2026-11/20/aos-hook-plan-1120/05 (the command) with 12 (what holds after the review); the user
11-20: "任何子程式，含非 Python", then "先開第 4 刀". Cut 4 added it; the
templates' loop.json fire their four loop points through it (on_start / on_stop since line top-1121-hookfire).
The hooks run in aos.hook_run (the engine the agents and the kernel use) through an aos.hook_point handle: order, exit
10, on_error, timeout_ms and which keys a hook may change are the engine's rules; the handle reads the lists and checks
the changed values' declared types. The source: --points / --list, or --agent DEF_DIR (aos.agentlib.agent_hooks.source:
the agent's hook_points, its two hooks layers and on_clock rules; after_start first clears the on_clock state).
Exit codes: 0 ok (also when no hook listens), 10 blocked (fire only), 1 error (one line "aos-hook: error: CODE reason").
Flags of the loop points (aos.hook_flags; hook cut 5, second half, line top-1121-hook5): fire after_start and check with a
stack make STACK/hook_before_run.flag and hook_after_run.flag match the lists, for any source whose points include them.
"""
import json
import os
import re
import sys

from aos import flags as aos_flags
from aos import hook_flags, hook_point, hook_run

PROG = "aos-hook"
HELP = """aos-hook - fire a hook event from any program, and list or check hook point declarations

usage: aos-hook SUBCOMMAND [--points FILE]... [--list FILE]... [--stack DIR] [FLAGS...] [ARGS...]
       aos-hook SUBCOMMAND --help

subcommands:
  fire EVENT   run the hooks of EVENT; event data from stdin (JSON) and flags; one JSON line out
  points       list the points the declarations offer
  check        check the declarations and the hooks lists; runs no handler

where the points and the hooks are (these flags go before or after the subcommand):
  --points FILE   a hook_points.json declaration (repeat for several; the same point in two files must agree)
  --list FILE     a JSON file with a "hooks" table (an agent's hooks.json, a kernel.json...); repeat for
                  several: a later file overrides an earlier one by name, null turns a hook off; a file
                  that does not exist has no hooks
  --stack DIR     where the hooks' own folders go (DIR/hooks/NAME/); default $AOS_STACK
  --agent DEF_DIR an agent's own set instead of --points / --list: the points = the hook_points of
                  DEF_DIR/interfaces.json, the hooks = the definition's hooks file with the stack's copy
                  on top (no stack: the definition's only; fire needs one); on_clock entries get the
                  agent's checks; fire after_start first clears the on_clock state of the stack
  -h, --help      show this help

flag files: when the points include before_run / after_run, fire after_start and check (with a
stack) create STACK/hook_before_run.flag / hook_after_run.flag while a hook listens to that point
and remove them otherwise; a loop.json wired to aos-hook fires those points only while they exist.

exit codes: 0 ok; 10 blocked by a hook (fire only); 1 error ("aos-hook: error: CODE reason" on stderr).
more: proto8/py/aos/apps/hook/README.md"""
HELPS = {
    "fire": """aos-hook fire - run the hooks of one event, as the program that offers the point

usage: aos-hook fire [--points FILE]... [--list FILE]... [--stack DIR] [-q]
                     [--field NAME=VALUE]... [--field-file NAME=PATH]... [--field-default NAME=VALUE]... EVENT

EVENT must be a point of the --points files (also one marked not_fired_yet).
Event data, later ones override earlier ones:
  stdin                   a JSON object (empty, or a terminal = {}); keys are passed on as given
  environment             a field declared with "env": that variable, when set and not empty after
                          trimming spaces (type int = a whole number, else ArgumentsBad); not set = what
                          stdin gave, or null
  --field NAME=VALUE      a string (an int field gets a whole number)
  --field-file NAME=PATH  the file's text without leading/trailing white space; no such file = null
  --field-default NAME=VALUE   only when nothing above gave NAME a value (missing or null)
  The same NAME in --field and --field-file is ArgumentsBad; the same flag twice = the last one counts.
  -q, --quiet             print nothing on stdout (only the exit code tells)
after_start also sets the flag files of before_run / after_run in the stack (see aos-hook --help).

stdout: one JSON line {"data": {...}, "changed": [...], "blocked": false, "hook": null, "text": ""}:
the data after the hooks, the keys they changed, and when blocked the hook's name and its stdout.
Hooks run in name order; a hook may change only the point's change keys, with the declared type.
exit codes: 0 ok (also when no hook listens); 10 blocked (only points with block true);
1 error: HookFailed (a hook with on_error stop failed), HooksBad, PointsBad, EventUnknown,
ArgumentsBad, StackMissing. A failing hook with on_error continue is one warning line, exit 0.
The hooks' stderr goes straight through.""",
    "points": """aos-hook points - list the points of hook_points.json declarations

usage: aos-hook points [--points FILE]... [-j]

One block per point: NAME PHASE, its condition field, the keys a hook may change and whether it can
block; then what each provider says (when, if blocked, if failed, not fired yet) and the fields.
  -j, --json   one JSON object {NAME: point} instead; "said" has one item per file that declares it""",
    "check": """aos-hook check - check declarations and hooks lists without running a handler

usage: aos-hook check [--points FILE]... [--list FILE]... [--stack DIR]

Reads the declarations (PointsBad) and every hooks list against them (HooksBad: an event no
declaration has, a bad key, an entry_keys key on another point). A hook on a point marked
not_fired_yet is one warning line. Prints one "ok: ..." line, exit 0.
With a stack (--stack, or $AOS_STACK) and points that include before_run / after_run, it also
sets their flag files in the stack (one more line "flags: ..."; WriteFailed when it cannot)."""}
ROOT = {}                                      # the shared flags (--points, --list, --stack, --agent)
FLAGS = {"--stack": "stack", "--agent": "agent"}
MULTI = {"--points": "points", "--list": "list"}
INT = re.compile(r"-?[0-9]+\Z")
NOW = {"help": HELP}                           # the help the ArgumentsBad usage comes from


class Fail(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def warn(line):
    aos_flags.warn(PROG, line)


def parse(argv, sub, switches=None, multi=None, short=None):
    NOW["help"] = HELPS[sub]
    try:
        return aos_flags.parse(argv, {}, switches or {}, multi or {}, help=HELPS[sub], short=short or {})
    except aos_flags.Error as e:
        raise Fail(e.code, "%s (see %s %s --help)" % (e, PROG, sub))


def failed(code, sentence):
    """The fail() of the hook_point handle: this command's own error line."""
    raise Fail(code, sentence)


def stack_dir():
    return ROOT.get("stack") or os.environ.get("AOS_STACK", "")


def declared(stack=""):
    """Where the points and the lists come from: --points / --list, or --agent (aos.agentlib is imported only then)."""
    agent = ROOT.get("agent")
    if agent is None:
        paths = ROOT.get("points", [])
        if not paths:
            raise Fail("ArgumentsBad", "give at least one --points FILE, or --agent DEF_DIR")
        try:
            points = hook_point.read(paths)
        except hook_point.PointsBad as e:
            raise Fail("PointsBad", str(e))
        return {"points": points, "lists": ROOT.get("list", []), "files": len(paths), "entry_check": None,
                "label": ", ".join(paths), "agent": None}
    if ROOT.get("points") or ROOT.get("list"):
        raise Fail("ArgumentsBad", "give either --agent DEF_DIR or --points / --list, not both")
    if not (agent and os.path.isdir(agent)):
        raise Fail("ArgumentsBad", "--agent needs an agent definition folder, got %r" % agent)
    from aos.agentlib import agent_hooks
    return agent_hooks.source(os.path.abspath(agent), stack, failed)


def handle(src, stack):
    """The hook_point handle over the source's points and lists."""
    return hook_point.open(src["points"], lists=src["lists"], stack=stack or ".", fail=failed, warn=warn,
                           entry_check=src["entry_check"])


def value(point, event, name, text, source):
    """A string from the environment or a flag; an int field gets a whole number."""
    about = point["fields"].get(name)
    if not (isinstance(about, dict) and about.get("type") == "int"):
        return text
    if not INT.match(text.strip()):
        raise Fail("ArgumentsBad", "field %s of point %s is a whole number; %s gave %r" % (name, event, source, text))
    return int(text.strip())


def pair(flag, item):
    name, eq, text = item.partition("=")
    if not eq or not name:
        raise Fail("ArgumentsBad", "%s wants NAME=VALUE (got %r)" % (flag, item))
    return name, text


def stdin_data():
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    text = sys.stdin.read()
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except ValueError as e:
        raise Fail("ArgumentsBad", "stdin is not JSON: %s" % e)
    if not isinstance(data, dict):
        raise Fail("ArgumentsBad", "stdin must be a JSON object")
    return data


def event_data(points, event, opts):
    """stdin -> environment -> --field / --field-file -> --field-default (05, A14)."""
    point = points[event]
    data = stdin_data()
    for name, about in point["fields"].items():
        if isinstance(about, dict):
            text = os.environ.get(about["env"], "").strip()
            if text:
                data[name] = value(point, event, name, text, "$" + about["env"])
            else:
                data.setdefault(name, None)
    given = {}
    for flag, key in (("--field", "field"), ("--field-file", "field_file")):
        for item in opts.get(key, []):
            name, text = pair(flag, item)
            if given.setdefault(name, flag) != flag:
                raise Fail("ArgumentsBad", "field %s is given by both --field and --field-file; give it once" % name)
            if flag == "--field-file":
                try:
                    with open(text, encoding="utf-8") as f:
                        text = f.read().strip()
                except FileNotFoundError:
                    data[name] = None
                    continue
                except OSError as e:
                    raise Fail("ArgumentsBad", "--field-file %s: cannot read %s: %s" % (name, text, aos_flags.os_reason(e)))
                except UnicodeError as e:
                    raise Fail("ArgumentsBad", "--field-file %s: %s is not UTF-8 text: %s" % (name, text, e))
            data[name] = value(point, event, name, text, flag)
    defaults = dict(pair("--field-default", item) for item in opts.get("field_default", []))
    for name, text in defaults.items():
        if data.get(name) is None:
            data[name] = value(point, event, name, text, "--field-default")
    return data


def fire(argv):
    opts, rest = parse(argv, "fire", {"--quiet": "quiet"},
                       {"--field": "field", "--field-file": "field_file", "--field-default": "field_default"},
                       {"-q": "--quiet"})
    if len(rest) != 1:
        raise Fail("ArgumentsBad", "give one EVENT" if not rest else "give one EVENT (got %s)" % " ".join(rest))
    event = rest[0]
    stack = stack_dir()
    src = declared(stack)
    points = src["points"]
    if event not in points:
        raise Fail("EventUnknown", "no point %s in %s (points: %s)"
                   % (event, src["label"], ", ".join(points) or "none"))
    if not stack:
        raise Fail("StackMissing", "give --stack DIR or set AOS_STACK (the hooks' folders go to DIR/hooks/NAME/)")
    hooks = handle(src, stack)
    entries = hooks.load()
    data = event_data(points, event, opts)
    if src["agent"] and event == "after_start":   # the first clock check after a start runs at once
        try:
            from aos.agentlib import hook_clock
            hook_clock.clock_restart(stack)
        except OSError as e:
            warn("cannot reset the on_clock state in %s: %s" % (stack, e))
    if event == "after_start":   # 06/12 B1: a loop's start is one of the moments the flags are set from the lists
        keep_flags(stack, points, entries)
    result = hooks.fire(event, data, entries=entries)
    if not opts.get("quiet"):
        print(json.dumps(result, ensure_ascii=False), flush=True)
    sys.exit(hook_run.BLOCK if result["blocked"] else 0)


def keep_flags(stack, points, entries):
    """The flag files of before_run / after_run in the stack, from the hooks in effect (aos.hook_flags); {point: on}."""
    try:
        return hook_flags.sync(stack, points, entries)
    except OSError as e:
        raise Fail("WriteFailed", "cannot set the hook flag files in %s: %s" % (stack, aos_flags.os_reason(e)))


def head(name, point):
    """The first line of a point in `points`: NAME PHASE, condition, change, block."""
    parts = [name, point["phase"]]
    if point.get("condition"):
        parts.append("condition " + point["condition"])
    change = point.get("change", {})
    if change:
        parts.append("change " + ", ".join("%s (%s)" % kv for kv in change.items()))
    if point.get("block"):
        parts.append("can block")
    return "  ".join(parts)


def show(points):
    out = []
    for name, point in points.items():
        out.append(head(name, point))
        for said in point["said"]:
            out.append("  %s: %s" % (said["provider"], said["when"]))
            for key, label in (("if_blocked", "if blocked"), ("if_failed", "if failed"), ("not_fired_yet", "not fired yet")):
                if key in said:
                    out.append("  %s, %s: %s" % (said["provider"], label, said[key]))
        for field, about in point["fields"].items():
            if isinstance(about, dict):
                about = "%s ($%s, %s)" % (about["about"], about["env"], about.get("type", "string"))
            out.append("  field %s: %s" % (field, about))
    return out


def points_cmd(argv):
    opts, rest = parse(argv, "points", {"--json": "json"}, short={"-j": "--json"})
    if rest:
        raise Fail("ArgumentsBad", "points takes no arguments (got %s)" % " ".join(rest))
    points = declared()["points"]
    if opts.get("json"):
        print(json.dumps(points, ensure_ascii=False))
    else:
        for line in show(points):
            print(line)


def check(argv):
    _, rest = parse(argv, "check")
    if rest:
        raise Fail("ArgumentsBad", "check takes no arguments (got %s)" % " ".join(rest))
    stack = stack_dir()
    src = declared(stack)
    points = src["points"]
    entries = handle(src, stack).load()
    for name, entry in sorted(entries.items()):
        later = [s for s in points[entry["event"]]["said"] if "not_fired_yet" in s]
        if later:
            warn("hook %s (in %s) is on point %s, which nothing fires yet: %s"
                 % (name, entry["from"], entry["event"], later[0]["not_fired_yet"]))
    print("ok: %d points from %d declarations, %d hooks from %d lists"
          % (len(points), src["files"], len(entries), len(src["lists"])))
    flags = keep_flags(stack, points, entries) if stack else {}
    if flags:
        print("flags: " + ", ".join("%s %s" % (os.path.join(stack, hook_flags.FLAGS[p]), "on" if on else "off")
                                    for p, on in flags.items()))


SUBS = {"fire": fire, "points": points_cmd, "check": check}


def main():
    global ROOT
    aos_flags.HELP = HELP
    try:
        ROOT, rest = aos_flags.parse(sys.argv[1:], FLAGS, multi=MULTI, help=HELP, sub="root")   # flags given after
        # the subcommand are written back into this same dict by the subcommand's parse (aos.flags scopes)
        if not rest:
            raise Fail("ArgumentsBad", "missing subcommand (%s; see %s --help)" % (", ".join(SUBS), PROG))
        if rest[0] not in SUBS:
            raise Fail("CommandUnknown", "unknown subcommand %s (%s; see %s --help)" % (rest[0], ", ".join(SUBS), PROG))
        SUBS[rest[0]](rest[1:])
    except (aos_flags.Error, Fail) as e:
        aos_flags.die(PROG, e.code, aos_flags.with_usage(NOW["help"], e.code, e))
    sys.exit(0)


aos_flags.run(main)
