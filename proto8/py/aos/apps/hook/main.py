"""aos-hook - fire a hook event from any program (C++, shell, ...): run the handlers hooked on it and print each one's exit code and stdout.

Design: proto8/thinking/2026-11/20/aos-hook-plan-1120/05 (the user 11-20: "任何子程式，含非Python"); since 11-21 the user's
fourth layer (proto8/thinking/2026-11/21/aos-hook-簡化-1121/07: "簡化到第四層"; timeout "留著"; exit code "用旗標選"):
it does one thing, through the engine aos.hook_run. Blocking, changing fields, conditions and failure rules are the
firing program's ("發事件的程式自己決定", 11-21 8th); declarations are never read ("宣告這東西只是參考"). Line top-1121-hooknew.
The templates' loop.json fire the loop points with it, --stop-on-nonzero, so aos-loop reads the handler's own exit code.
"""
import json
import os
import sys

from aos import flags as aos_flags
from aos import hook_lists, hook_point, hook_run

PROG = "aos-hook"
HELP = """aos-hook - fire a hook event from any program: run the handlers hooked on it

usage: aos-hook fire (--list FILE... | --def DIR) [--stack DIR] [--stop-on-nonzero] [-q] EVENT
       aos-hook fire --help

subcommands:
  fire EVENT   run the handlers of EVENT in name order, each with the event JSON on stdin;
               print one JSON line with each one's exit code and stdout

The handlers hooked on EVENT come from hookeds lists ({hook name: {"event", "handler",
"timeout_ms"?, ...} or null}); nothing else is read. What an exit code or a stdout means
(block, change, fail) is for the program that fires the event to decide.
exit codes: 0 fired (also when no hook listens, and when a handler failed: see the JSON);
with --stop-on-nonzero the first handler's code that is not 0; 1 error ("aos-hook: error: CODE reason").
more: proto8/py/aos/apps/hook/README.md"""
FIRE = """aos-hook fire - run the handlers hooked on one event

usage: aos-hook fire (--list FILE... | --def DIR) [--stack DIR] [--stop-on-nonzero] [-q] EVENT

where the hooks are (one of):
  --list FILE        a hookeds list; repeat for several: a later file overrides an earlier one by
                     name, null turns a hook off; a file that does not exist has no hooks
  --def DIR          the hookeds of DIR/interfaces.json (a file name, a directive, or an array of
                     them), each relative one with the stack's same-named copy on top
flags:
  --stack DIR        where the handlers' own folders go (DIR/hookeds/NAME/); default $AOS_STACK
  --stop-on-nonzero  stop after the first handler whose exit code is not 0 and exit with that code
                     (a handler that timed out or could not start: exit 1, HookFailed)
  -q, --quiet        print nothing on stdout
  -h, --help         show this help

The event data is the JSON object on stdin (empty, or a terminal = {}); each handler gets it with
"event", "hook" and "stack" added, as STACK/hookeds/NAME/event.json on its stdin, in a process group
of its own; its stderr goes straight through. A handler's "timeout_ms" (default 60000, 0 = no limit):
at the limit its whole group is stopped.
stdout: one JSON line {"event": EVENT, "hooks": [{"hook": NAME, "code": N, "stdout": "...",
"error": null}, ...]}; code null and error the reason when it timed out or could not start
(also one warning line on stderr).
exit codes: 0 fired, whatever the handlers did; with --stop-on-nonzero the first non-zero code (an
error line HookFailed unless it is 10, N-43's "no"); 1 error: ArgumentsBad, HooksBad, InterfaceBad,
StackMissing, HookFailed."""
NOW = {"help": HELP}


class Fail(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


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


def lists(opts, stack):
    if opts.get("def") is not None:
        if opts.get("list"):
            raise Fail("ArgumentsBad", "give either --def DIR or --list FILE, not both")
        if not os.path.isdir(opts["def"]):
            raise Fail("ArgumentsBad", "--def needs a definition folder, got %r" % opts["def"])
        try:
            return hook_point.layers(os.path.abspath(opts["def"]), stack)
        except hook_point.InterfaceBad as e:
            raise Fail("InterfaceBad", str(e))
    if not opts.get("list"):
        raise Fail("ArgumentsBad", "give at least one --list FILE, or --def DIR")
    return opts["list"]


def fire(argv):
    NOW["help"] = FIRE
    try:
        opts, rest = aos_flags.parse(argv, {"--stack": "stack", "--def": "def"},
                                     {"--quiet": "quiet", "--stop-on-nonzero": "stop"}, {"--list": "list"},
                                     help=FIRE, short={"-q": "--quiet"}, anywhere=True)
    except aos_flags.Error as e:
        raise Fail(e.code, "%s (see %s fire --help)" % (e, PROG))
    if len(rest) != 1 or not rest[0]:
        raise Fail("ArgumentsBad", "give one EVENT" if not rest else "give one EVENT (got %s)" % " ".join(rest))
    event = rest[0]
    stack = opts.get("stack") or os.environ.get("AOS_STACK", "")
    if not stack:
        raise Fail("StackMissing", "give --stack DIR or set AOS_STACK (the handlers' folders go to DIR/hookeds/NAME/)")
    try:
        entries = hook_lists.load(lists(opts, stack))
    except hook_lists.HooksBad as e:
        raise Fail("HooksBad", str(e))
    results = hook_run.fire(event, stdin_data(), entries, stack, stop_on_nonzero=opts.get("stop", False))
    for r in results:
        if r["error"]:
            aos_flags.warn(PROG, "hook %s (event %s): %s" % (r["hook"], event, r["error"]))
    if not opts.get("quiet"):
        print(json.dumps({"event": event, "hooks": results}, ensure_ascii=False), flush=True)
    last = results[-1] if results else None
    if opts.get("stop") and last and last["code"] != 0:
        if last["code"] == hook_run.BLOCK:
            sys.exit(hook_run.BLOCK)
        why = last["error"] or "exited %d" % last["code"]
        print(aos_flags.error_line(PROG, "HookFailed", "hook %s (event %s) %s" % (last["hook"], event, why)),
              file=sys.stderr, flush=True)
        sys.exit(last["code"] or 1)
    sys.exit(0)


SUBS = {"fire": fire}


def main():
    aos_flags.HELP = HELP
    try:
        args = sys.argv[1:]
        if args and args[0] in ("-h", "--help"):
            print(HELP)
            sys.exit(0)
        if not args:
            raise Fail("ArgumentsBad", "missing subcommand (fire; see %s --help)" % PROG)
        if args[0] not in SUBS:
            raise Fail("CommandUnknown", "unknown subcommand %s (fire; see %s --help)" % (args[0], PROG))
        SUBS[args[0]](args[1:])
    except (aos_flags.Error, Fail) as e:
        aos_flags.die(PROG, e.code, aos_flags.with_usage(NOW["help"], e.code, e))
    sys.exit(0)


aos_flags.run(main)
