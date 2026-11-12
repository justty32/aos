# aos_eca/__init__.py - aos-eca-turn 的英文說明、旗標檢查與主入口（main）。
import os
import sys

import aos_flags

from .common import NAME, NOT_FOUND, Fail
from .common import cli_session
from .turn import one_turn

USAGE = "aos-eca-turn [--one] [--on-empty stop|idle] [--on-busy yield|answer] [--prompt FILE] DEF_DIR"
aos_flags.HELP = """aos-eca-turn - one turn of an external coding agent (claude / codex, an "eca"): hand every letter in the stack's queue,
in order, to the CLI as one prompt (handing it over = the letters are done), wait for the answer, append it to history.

    aos-eca-turn [--one] [--on-empty stop|idle] [--on-busy yield|answer] [--prompt FILE] DEF_DIR

DEF_DIR: the eca definition folder (absolute; cli.json at its top, optional tools.json). It is never written; everything goes to $AOS_STACK.
Loop form (no --one): the batch = all of queue/cur/ plus all of queue/new/; bad letters are dropped and noted in
  $AOS_STACK/mailbox_warning.txt; good contents are joined with a blank line and asked once (a pasted screen if one is open,
  otherwise claude -p --resume / codex exec resume). The user messages go into history.jsonl when the prompt is handed over, the
  answer goes in as one assistant message.
  --on-empty stop (default): empty queue = exit 10 | idle: exit 0.
  --on-busy yield (default): the session is busy (lock taken, someone attached, busy.txt) = leave the batch in cur/, exit 0 |
    answer: wait and answer anyway.
  --prompt FILE: opening message (relative to DEF_DIR) queued when history and queue are both empty.
  New conversation: when there is no session.txt, or the earlier conversation is not on this machine (its .session_home names
    another session, account folder, machine or - for claude - workspace), a new one is started before the letters are handed over, and
    a record built from history.jsonl goes in front of the prompt: a short note, the first user message, then the newest messages
    that fit. Its size limit is cli.json's optional reseed_bytes (default 48000; at most 8000 when pasting into a screen; 0 = the
    note only). Delete session.txt by hand to restart the conversation on purpose.
  History changed: when history.jsonl differs from how the last turn left it (aos-agent history, self_history, a hand edit),
    the next turn starts a new conversation the same way, carrying the changed record (not while the screen is open).
  Cooldown: a failure after the prompt was handed over (CliFailed, ReplyMissing) is recorded in $AOS_STACK/cooldown.json; while
    cooling, no letter is taken (exit 0); when the cooldown is over, only the oldest letter is tried; a success removes the file.
  Hooks (hooks.json declared in DEF_DIR's interfaces.json, the stack copy on top): before_queue before a good letter is handed over
    (may change content or drop it; a dropped letter is done and noted in mailbox_warning.txt), tool_added before handing over,
    after_queue after the letters went into history, brain_failed on CliFailed / ReplyMissing after handing over. before_tool /
    after_tool run in aos-mcp. on_clock is checked first thing every turn (it runs only when its clock condition is met).
    A failing hook = HookFailed (letters not yet handed over stay in cur/).
  Goal: with no letter, when the CLI answered the last turn (or history is still empty) and $AOS_STACK/goal.json is active, the prompt of this turn is one
    message "[aos] goal: TEXT (reminder N of LIMIT...)" (it goes into history like a letter). A turn in which the CLI called tools
    (seen in its own transcript) sets the count back to 0; LIMIT reminders in a row without progress pause the goal.
  Slash commands: a batch of one letter that is exactly /clear, /compact, /status, /usage or /exit (spaces around allowed) is
    done by aos and answered with one "[aos] slash: ..." message (or claude's own words): /status = aos's own report;
    /usage = a separate claude -p /usage (codex: not available); /compact = handed to claude on the same conversation
    (codex: the next message starts a new thread carrying aos's record); /clear = history.jsonl moves to history_removed.jsonl
    and the next message starts a new conversation; /exit = closes the screen. After claude's /compact, history.jsonl is
    replaced by claude's summary (one "[aos] summary: ..." message; the old ones move to history_removed.jsonl). With the
    screen open, /clear and /compact are typed into it (not while it is answering) and the screen hooks keep aos in step.
    A letter starting with /goal ("/goal TEXT", "/goal clear", "/goal") is the CLI's own goal: typed into an open screen,
    otherwise handed to claude as it is (codex exec has no /goal: aos says so). /status also shows the last goal the CLI recorded.
    When codex's screen asks "Replace goal?" (a goal is already set), aos picks "1. Replace current goal"; any other question is left alone.
--one (tool form): stdin {"prompt"} -> stdout the answer; the conversation lives in $AOS_STACK itself. --on-empty / --prompt not allowed.
  If the earlier conversation is not on this machine, a warning is printed and a new one is started without a record. No cooldown.
Needs aos-post on PATH (loop form) and AOS_STACK.
Errors: one stderr line `aos-eca-turn: error: CODE reason`, exit 1 (tool form: the line also goes to stdout). aos-post's own stderr
  is passed through as it is. Codes: ArgumentsBad, FlagUnknown, AgentBad, StackMissing, PromptMissing, HistoryBad, PostFailed,
  WriteFailed, HookFailed, HooksBad, ToolsBad, CfgMissing, CfgBad, ToolsMissing, CliMissing, CliFailed, ReplyMissing,
  TrustMissing (claude on the screen waits at its trust-this-folder prompt; nothing typed: a person attaches and chooses)."""

def die(code, reason):
    aos_flags.die(NAME, code, reason)


def _cli_die(code, reason):                    # cli_session 出錯時本來 exit；平級形改成丟例外，這支自己說一行
    raise Fail(code, reason)


def main():
    try:
        opts, args = aos_flags.parse(sys.argv[1:], {"--on-empty": "on_empty", "--on-busy": "on_busy", "--prompt": "prompt"},
                                     {"--one": "one"}, anywhere=True)
    except aos_flags.Error as e:
        die(e.code, "%s (usage: %s)" % (e, USAGE))
    if len(args) != 1:
        die("ArgumentsBad", "%s (usage: %s)" % ("missing DEF_DIR" if not args else "only one DEF_DIR allowed, extra: %s" % args[1], USAGE))
    empty, busy = opts.get("on_empty", "stop"), opts.get("on_busy", "yield")
    if empty not in ("stop", "idle"):
        die("ArgumentsBad", "--on-empty must be stop or idle, got %r" % empty)
    if busy not in ("yield", "answer"):
        die("ArgumentsBad", "--on-busy must be yield or answer, got %r" % busy)
    if opts.get("one") and "on_empty" in opts:
        die("ArgumentsBad", "--one (tool form) has no queue; --on-empty not allowed")
    if opts.get("one") and "prompt" in opts:
        die("ArgumentsBad", "--one (tool form) has no queue; --prompt not allowed")
    if opts.get("prompt") == "":
        die("ArgumentsBad", "--prompt needs the path of a prompt file")
    template = args[0]
    if not os.path.isabs(template) or not os.path.isdir(template):
        die("AgentBad", "definition dir must be an existing absolute path, got %r" % template)
    template = os.path.normpath(template)
    prompt = None
    if "prompt" in opts:                                           # 相對路徑從定義資料夾算（11-04）
        prompt = os.path.normpath(os.path.join(template, opts["prompt"]))
        if not os.path.isfile(prompt):
            die("PromptMissing", "--prompt file not found: %s" % prompt)
    if opts.get("one"):
        cli_session.call_main(template, busy)                      # --one 專用入口；lib 的 ask_cli 與它共用 cli_session.ask
        return
    stack = os.environ.get("AOS_STACK")
    if not stack:
        die("StackMissing", "AOS_STACK is not set")
    stack = os.path.abspath(stack)
    ws = os.path.abspath(os.environ.get("AOS_WS") or ".")
    cli_session.die = _cli_die
    try:
        code = one_turn(template, stack, ws, NOT_FOUND if empty == "stop" else 0, busy, prompt)
    except Fail as e:
        die(e.code, e)
    sys.exit(code)
