# aos_agent/system.py - 管 agent 自己那份 system 文字（stack 那份在就整份蓋過定義那份）：get、set、reset。
# 使用者 11-11：「然後我們現在的工具沒辦法讓agent修改自身的system prompt……」，選項框裁「單獨一支工具」（人用 aos-agent system＋給腦的 self_system）、
#   「fsm 取代、eca 附加」、「只給 reset、不擋」（thinking 2026-11/11/self-system）。
# 宣告：定義 interfaces.json 的 aos-agent.system＝定義裡的相對檔名（例 system.txt）；這隻自己的＝$AOS_STACK 同一個相對路徑那份（整份、不是差異）。
#   定義那份不在＝空文字（同 llm 定義那份不在＝{}）。怎麼用這份文字是身體的事：agent-fsm 的 brain.py 當整則 system 訊息（取代）、
#   eca（cli_session）交給 claude --append-system-prompt-file／codex developer_instructions（附加）；空＝fsm 不送 system、eca 不附加。
import json
import os
import sys
import aos_flags
from . import PROG
from .common import Fail, actions, bad_args, in_stack, note, parse, target
from .decl import agent_decl, warn_shared


HELPS = {
    "get": """aos-agent system get - print this agent's system text in effect

usage: aos-agent [--daemon D] system [--target NAME] get [-l | --json]
       aos-agent system get --help

flags:
  -l, --long   first a line FROM TAB FILE (FROM: agent = its own copy in its stack,
               definition = the definition's file, none = neither file exists), then the text
  -j, --json   print one JSON object {"text", "from", "file", "bytes"}
  -h, --help   show this help

Print the text as it is: this agent's own copy when it has one, else the definition's.
exit codes: 0 printed; 1 error (SystemMissing, SystemBad...).
""",
    "set": """aos-agent system set - replace this agent's system text (its own copy only)

usage: aos-agent [--daemon D] system [--target NAME] set [FILE | -]
       aos-agent system set --help

flags:
  -h, --help   show this help

The new text is FILE's content, or stdin when FILE is - or not given (stdin must not be a
terminal then). It is written whole to this agent's stack; the definition stays as it is.
An empty text is kept too (an agent-fsm brain then gets no system message; an eca adds nothing).
How the body uses it: agent-fsm sends it as the system message (replacing the definition's);
eca appends it to the CLI's own system prompt. It applies from the next brain call (eca: the
next turn; an open screen keeps the old text until it is opened again; codex: its next new
conversation).
exit codes: 0 set; 1 error (ArgumentsBad, PathMissing, SystemMissing, SystemBad, WriteFailed...).
""",
    "reset": """aos-agent system reset - delete this agent's own system text

usage: aos-agent [--daemon D] system [--target NAME] reset [-y]
       aos-agent system reset --help

flags:
  -y, --yes    skip confirmation
  -h, --help   show this help

Back to the definition's system text; asks on a terminal; -y skips.
exit codes: 0 reset or nothing done; 1 error (SystemMissing, SystemBad...); 130 Ctrl-C.
""",
}
HELP = """aos-agent system - see and change this agent's system text (its own copy sits on top of the definition's)

usage: aos-agent [--daemon D] system [--target NAME] [ACTION] [FLAGS...] [ARGS...]
       aos-agent system ACTION --help

actions:
%s

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -h, --help          show this help

No ACTION means get. This agent's own copy replaces the definition's whole (not merged).
Changing it makes the brain's prompt cache miss once. More: proto8/cmd/aos-agent/docs/07-system.md
exit codes: 0 ok; 1 error (TargetMissing, SystemMissing, SystemBad...); 130 Ctrl-C.
""" % actions(HELPS.values(), "aos-agent [--daemon D] system [--target NAME] ")


def system_paths(a):
    """回 (定義, 定義那份, stack 那份)。沒宣告＝SystemMissing；宣告的不是定義內相對檔名＝SystemBad。"""
    folder, decl = agent_decl(a)
    rel = decl.get("system")
    if rel is None:
        raise Fail("SystemMissing", "%s does not declare system (write {\"aos-agent\": {\"system\": \"system.txt\"}} in the definition's interfaces.json)" % a.name)
    if (not isinstance(rel, str) or not rel or os.path.isabs(rel) or ".." in rel.split("/")
            or os.path.isdir(os.path.join(folder, rel))):
        raise Fail("SystemBad", "the system declared by %s must be a relative path to a text file in the definition (e.g. \"system.txt\"), not %s" % (folder, json.dumps(rel)))
    return folder, os.path.join(folder, rel), os.path.join(a.stack, rel)


def read_text(path, a=None):
    """檔不在＝None。錯誤行裡 stack 裡的檔寫相對 a 的 stack（11-12 線 errpath）。"""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as e:
        raise Fail("SystemBad", "cannot read %s: %s" % (in_stack(path, a), aos_flags.os_reason(e)))


def effective(orig, copy, a=None):
    """(文字, 來源, 檔)：stack 那份在＝它；否則定義那份；都不在＝("", none, 定義那份)。"""
    mine = read_text(copy, a)
    if mine is not None:
        return mine, "agent", copy
    base = read_text(orig, a)
    if base is not None:
        return base, "definition", orig
    return "", "none", orig


def eca_kind(folder):
    """定義有 cli.json＝eca：回 claude／codex；不是 eca 或讀不懂＝None（只用來決定提醒，不擋）。"""
    try:
        with open(os.path.join(folder, "cli.json"), encoding="utf-8") as f:
            kind = json.load(f).get("kind")
    except (OSError, ValueError, AttributeError):
        return None
    return kind if kind in ("claude", "codex") else None


def screen_open(folder, stack):
    """eca 的畫面開著＝True。開著的 CLI 帶的是開畫面那時的 system，改了要重開才生效（11-11 代定：只提醒）。"""
    kind = eca_kind(folder)
    if kind is None:
        return False
    try:
        from agent import cli_base, cli_cell
        cell = os.path.join(stack, kind)
        sock = cli_cell.tty_socket(cell)
        if not os.path.exists(sock):
            return False
        import subprocess
        return subprocess.run(["tmux", "-S", sock, "has-session", "-t", cli_base.TMUX_SESSION],
                              capture_output=True).returncode == 0
    except Exception:                           # 看不出來＝不提醒（只是提醒，不擋）
        return False


def notes_after(a, folder):
    """set／reset 之後的提醒：畫面開著要重開；codex 的對話只在開頭讀一次（11-11 實測：exec resume 帶新的 developer_instructions 不生效）。"""
    if screen_open(folder, a.stack):
        note("the screen of %s is open: it keeps the old text until it is opened again (aos-agent close, then open)" % a.name)
    if eca_kind(folder) == "codex":
        note("codex keeps the system text a conversation started with: the change applies when %s starts a new conversation "
             "(its session.txt removed, or its history changed)" % a.name)


def write_text(path, text, a=None):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")   # N-05
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError as e:
        raise Fail("WriteFailed", "cannot write %s: %s" % (in_stack(path, a), aos_flags.os_reason(e)))


def cmd(argv):
    opts, rest = parse(argv, {"--target": "target"}, help=HELP, short=("-t",), sub=True)
    act, args = (rest[0], rest[1:]) if rest else ("get", [])
    if act not in HELPS:
        raise Fail("CommandUnknown", "system: unknown subcommand %s (get, set, reset; see aos-agent system --help)" % act)
    switches = {"get": {"--json": "json", "--long": "long"}, "reset": {"--yes": "yes"}}.get(act, {})
    shorts = {"get": {"-j": "--json", "-l": "--long"}, "reset": ("-y",)}.get(act, ())
    aopts, args = parse(args, {}, switches, help=HELPS[act], short=shorts)
    if act in ("get", "reset") and args:
        raise bad_args(HELPS[act], "%s takes no arguments" % act)
    if act == "set" and len(args) > 1:
        raise bad_args(HELPS[act], "set takes one FILE (or - / nothing for stdin)")
    if act == "get" and aopts.get("json") and aopts.get("long"):
        raise bad_args(HELPS[act], "give -l or --json, not both")
    a = target(opts)
    folder, orig, copy = system_paths(a)
    if act == "get":
        text, src, path = effective(orig, copy, a)
        if aopts.get("json"):
            print(json.dumps({"text": text, "from": src, "file": path, "bytes": len(text.encode("utf-8"))}, ensure_ascii=False))
            return
        if aopts.get("long"):
            print("%s\t%s" % (src, path))
        if not text:
            note("no system text (%s)" % ("this agent's own copy %s is empty" % copy if src == "agent" else
                                           "the definition's %s is empty" % orig if src == "definition" else
                                           "neither %s nor %s exists" % (copy, orig)))
        sys.stdout.write(text)
        if text and not text.endswith("\n"):
            sys.stdout.write("\n")
        return
    if act == "reset":
        if os.path.isfile(copy):
            question = "delete the system text %s of %s (back to the definition's %s)?" % (copy, a.name, orig)
            if not aos_flags.confirm(PROG, question, yes=aopts.get("yes", False)):
                aos_flags.warn(PROG, "nothing done")
                return
            os.unlink(copy)
            print("deleted %s; back to the definition's %s" % (copy, orig))
            notes_after(a, folder)
        else:
            print("there was no own system text (using the definition's %s)" % orig)
        return
    src = args[0] if args else "-"
    if src == "-":
        if sys.stdin is None or sys.stdin.isatty():
            raise bad_args(HELPS[act], "give FILE, or pipe the text on stdin")
        text = sys.stdin.read()
    else:
        if not os.path.isfile(src):
            raise Fail("PathMissing", "%s is not a file (relative to the current directory)" % src)
        try:
            with open(src, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeError) as e:
            raise Fail("SystemBad", "cannot read %s: %s" % (src, aos_flags.os_reason(e)))
    made = not os.path.isfile(copy)
    write_text(copy, text, a)
    print("set the system text of %s: %s (%d bytes); takes effect from its next brain call" % (a.name, copy, len(text.encode("utf-8"))))
    if made:
        note("created %s (its own copy replaces the definition's %s whole; system reset deletes it)" % (copy, orig))
    if not text:
        note("the text is empty: an agent-fsm brain gets no system message, an eca adds nothing to the CLI's own")
    notes_after(a, folder)
    warn_shared(a, folder)
