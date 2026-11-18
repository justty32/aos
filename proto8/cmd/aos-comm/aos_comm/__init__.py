# aos_comm/__init__.py - aos-comm 本體：comm/1 協議的命令列（board-1114 批 1：board 五個動作與 check）；讀寫與算法全在 py/aos/comm（aos.comm），這裡只派發與印。
# 圖紙：proto8/thinking/2026-11/14/board-1114/（02 稿＋03 計劃＋05 採納表；衝突時 05 優先）。信件分級、頻道是之後的批，這版沒有。
import json
import os
import sys

from aos import flags as aos_flags
from aos.comm import Fail, check

from . import board_cmd, common
from .common import CTX

PROG = "aos-comm"

HELP = """aos-comm - the comm/1 protocol: boards (what a proc is doing, whether to disturb it, who it waits for)

usage: aos-comm [-s STACK] [-d DAEMON] SUBCOMMAND [FLAGS...] [ARGS...]
       aos-comm SUBCOMMAND --help

subcommands:
  board   set, clear, wait, show, ls: my board and the boards of others (see aos-comm board --help)
  check   check a file or a letter against the comm/1 schemas

flags:
  -s, --stack STACK    whose board is mine (default: $AOS_STACK; a tool's own folder <root>/tools/<name>
                       counts as <root> when <root>/mailbox exists)
  -d, --daemon DAEMON  the daemon table to ask for names (passed to aos-agent --daemon; default: what
                       aos-agent finds: AOS_KERNEL, AOS_DAEMON, ./.stack)
  -h, --help           show this help
Flags may go anywhere after the name they belong to.

Output is one line per item; -j / --json gives JSON for programs.
exit codes: 0 ok; 10 nothing found (board wait --done with no such line); 1 error
("aos-comm: error: CODE reason" on stderr).
more: proto8/cmd/aos-comm/README.md"""

CHECK_HELP = """aos-comm check - check a file or a letter against the comm/1 schemas

usage: aos-comm check FILE|LETTER_DIR [--schema board|letter-comm|channel|channel-members] [--builtin] [-j]

Which schema: --schema, else a letter (a folder with letter.json, or a letter.json) = its body.comm
against letter-comm (no comm = a normal letter, ok), else the file's "format" (board/1, channel/1,
channel-members/1). Uses Python jsonschema when installed, else (or with --builtin) a small checker
that knows only the keywords these four schemas use. date-time values must be ISO 8601 with a zone.
Prints "ok ..." (exit 0), or one line per problem "POINTER: reason" and then the error line
CheckFailed (exit 1). -j = one JSON object {file, schema, engine, ok, problems}."""


def _letter(path, v):
    return os.path.basename(path) == "letter.json" or (isinstance(v, dict) and isinstance(v.get("body"), dict)
                                                       and "sent_at" in v and "sender" in v)


def cmd_check(argv):
    opts, rest = common.parse(argv, "check", CHECK_HELP, {"--schema": "schema"}, {"--builtin": "builtin", "--json": "json"})
    if len(rest) != 1:
        raise Fail("ArgumentsBad", "check takes one FILE or LETTER_DIR (usage: aos-comm check FILE|LETTER_DIR [--schema NAME])")
    path = rest[0]
    if os.path.isdir(path):
        path = os.path.join(path, "letter.json")
    try:
        with open(path, encoding="utf-8") as fh:
            v = json.load(fh)
    except OSError as e:
        raise Fail("FileMissing" if isinstance(e, FileNotFoundError) else "ReadFailed",
                   "cannot read %s: %s" % (path, e.strerror or e))
    except (ValueError, UnicodeError):
        raise Fail("JsonBad", "%s is not valid JSON" % path)
    name = opts.get("schema")
    what = v
    if name is None and _letter(path, v):
        name, what = "letter-comm", (v.get("body") or {}).get("comm") if isinstance(v, dict) else None
        if what is None:
            _report(opts, path, name, None, [], "no comm: a normal letter")
            return 0
    if name is None:
        name = check.BY_FORMAT.get(v.get("format")) if isinstance(v, dict) else None
        if name is None:
            raise Fail("ArgumentsBad", "cannot tell which schema %s is for (no letter, no known format); give --schema" % path)
    engine = "builtin" if opts.get("builtin") else check.engine()
    found = check.problems(what, check.load_schema(name), engine)
    _report(opts, path, name, engine, found)
    if found:
        raise Fail("CheckFailed", "%d problem%s in %s against comm/1/%s" % (len(found), "" if len(found) == 1 else "s", path, name))
    return 0


def _report(opts, path, name, engine, found, note=None):
    if opts.get("json"):
        print(json.dumps({"file": path, "schema": "comm/1/" + name, "engine": engine, "ok": not found,
                          "problems": [{"at": a, "reason": r} for a, r in found]}, ensure_ascii=False))
    elif found:
        for a, r in found:
            print("%s: %s" % (a, r))
    else:
        print("ok %s (comm/1/%s%s)" % (path, name, "; " + note if note else ", checked with " + engine))
    sys.stdout.flush()


def cmd_board(argv):
    try:
        opts, rest = aos_flags.parse(argv, {}, help=board_cmd.HELP, sub=True)
    except aos_flags.Error as e:
        raise Fail(e.code, "%s (see aos-comm board --help)" % e)
    if not rest:
        raise Fail("ArgumentsBad", "missing action (%s; see aos-comm board --help)" % ", ".join(board_cmd.ACTIONS))
    if rest[0] not in board_cmd.ACTIONS:
        raise Fail("CommandUnknown", "unknown action %s (%s; see aos-comm board --help)" % (rest[0], ", ".join(board_cmd.ACTIONS)))
    return board_cmd.ACTIONS[rest[0]](rest[1:])


SUBS = {"board": cmd_board, "check": cmd_check}


def main():
    aos_flags.HELP = HELP
    try:
        opts, rest = aos_flags.parse(sys.argv[1:], {"--stack": "stack", "--daemon": "daemon"}, help=HELP,
                                     short=("-s", "-d"), sub="root")
        common.ROOT_OPTS = opts                     # 子命令後的 -s／-d 由 aos_flags 寫回這份
        CTX.update(stack=opts.get("stack"), daemon=opts.get("daemon"))
        if not rest:
            raise Fail("ArgumentsBad", "missing subcommand (%s; see aos-comm --help)" % ", ".join(SUBS))
        if rest[0] not in SUBS:
            raise Fail("CommandUnknown", "unknown subcommand %s (%s; see aos-comm --help)" % (rest[0], ", ".join(SUBS)))
        code = SUBS[rest[0]](rest[1:])
    except aos_flags.Error as e:
        aos_flags.die(PROG, e.code, e)
    except Fail as e:
        aos_flags.die(PROG, e.code, e)
    sys.exit(code or 0)
