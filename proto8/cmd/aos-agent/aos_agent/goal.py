# aos_agent/goal.py - 管 agent 的 goal（<stack>/goal.json）：get、set、done、pause、resume、clear；腦自己停下來時由身體（agent-fsm idle、aos-eca-turn）丟提醒。
# 使用者 11-11：「然後自動給agent看的，可能要做goal工具。預期是當agent自己停下來時(在沒有新user prompt的情況下，自己不再呼叫工具)，自動丟goal給他，」
#   裁定「agent 自己和外面都行」：agent 用工具 goal（lib/agent/goal，包這支、目標＝自己）；人和父 agent 用這支（照 aos-agent system 的寫法）。
#   讀寫一律走 lib/agent/goal_state.py（格式、提醒文字、上限都在那裡）。thinking 2026-11/11/goal/02。
# 誰改的（set_by／updated_by）：叫這支的 $AOS_STACK 在目標的 stack 裡面＝agent（它自己的工具）；否則 outside（人、父 agent）。
# **對應關係**：工具 goal 的 op 與這裡的動作一對一（clear 除外：工具不給，agent 用 done）；這裡加了動作或旗標，工具要跟著加。
import json
import os
import sys
import aos_flags
import daemon_ctl as dc
from . import PROG
from .common import Fail, actions, bad_args, parse, target, under

try:
    from agent import goal_state
except ImportError:                              # bin 旁邊跟著帶的（同 agent_files）
    import goal_state


HELPS = {
    "get": """aos-agent goal get - print this agent's goal and where it stands

usage: aos-agent [--daemon D] goal [--target NAME] get [-j | --json]
       aos-agent goal get --help

flags:
  -j, --json   print the goal.json object (null when there is no goal)
  -h, --help   show this help

One KEY TAB VALUE line each: status, text, reminded (N of LIMIT), reason, set_by, updated.
No goal = the line "no goal".
exit codes: 0 printed; 1 error (GoalBad...).
""",
    "set": """aos-agent goal set - give this agent a goal (replaces the one it had)

usage: aos-agent [--daemon D] goal [--target NAME] set [--limit N] TEXT... | -
       aos-agent goal set --help

flags:
  -n, --limit N   stop reminding after N reminders in a row without progress (default 10)
  -h, --help      show this help

TEXT is one short sentence (words are joined with spaces; - = read it from stdin).
The goal is active at once: when the agent stops by itself (its last answer calls no tool)
and its queue is empty, it gets one message "[aos] goal: TEXT (reminder N of LIMIT...)".
Calling a tool after a reminder counts as progress and starts the count again.
exit codes: 0 set; 1 error (ArgumentsBad, WriteFailed...).
""",
    "done": """aos-agent goal done - mark the goal finished (or given up); no more reminders

usage: aos-agent [--daemon D] goal [--target NAME] done [--abandoned] [REASON...]
       aos-agent goal done --help

flags:
  -a, --abandoned   given up instead of finished
  -h, --help        show this help

exit codes: 0 done; 1 error (GoalMissing, GoalBad, WriteFailed...).
""",
    "pause": """aos-agent goal pause - stop reminding for now (for example while waiting for someone)

usage: aos-agent [--daemon D] goal [--target NAME] pause [REASON...]
       aos-agent goal pause --help

flags:
  -h, --help   show this help

A paused goal stays paused when letters come; resume starts it again.
exit codes: 0 paused (or it already was); 1 error (GoalMissing, GoalEnded, GoalBad, WriteFailed...).
""",
    "resume": """aos-agent goal resume - start reminding again, counting from 0

usage: aos-agent [--daemon D] goal [--target NAME] resume
       aos-agent goal resume --help

flags:
  -h, --help   show this help

Also after the reminder limit paused it. A done or abandoned goal cannot be resumed (set it again).
exit codes: 0 resumed (or it already was active); 1 error (GoalMissing, GoalEnded, GoalBad, WriteFailed...).
""",
    "clear": """aos-agent goal clear - delete this agent's goal

usage: aos-agent [--daemon D] goal [--target NAME] clear [-y]
       aos-agent goal clear --help

flags:
  -y, --yes    skip confirmation
  -h, --help   show this help

Asks on a terminal; -y skips.
exit codes: 0 deleted or nothing done; 1 error; 130 Ctrl-C.
""",
}
HELP = """aos-agent goal - see and change this agent's goal (reminded when it stops by itself)

usage: aos-agent [--daemon D] goal [--target NAME] [ACTION] [FLAGS...] [ARGS...]
       aos-agent goal ACTION --help

actions:
%s

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -h, --help          show this help

No ACTION means get. The goal lives in the agent's stack (goal.json). The agent itself uses its
tool goal (op get, set, done, pause, resume). Letters come first: a reminder is only given when
the queue is empty and the last answer called no tool.
exit codes: 0 ok; 1 error (TargetMissing, GoalMissing, GoalBad...); 130 Ctrl-C.
""" % actions(HELPS.values(), "aos-agent [--daemon D] goal [--target NAME] ")


def who(a):
    """叫這支的是這隻自己（$AOS_STACK 在它的 stack 裡：它的 goal 工具）＝agent；否則 outside。"""
    mine = os.environ.get("AOS_STACK")
    return "agent" if mine and under(mine, a.stack) else "outside"


def load(a, need=True):
    try:
        rec = goal_state.read(a.stack)
    except goal_state.GoalBad as e:
        raise Fail("GoalBad", "%s (aos-agent goal set or clear rewrites it)" % e)
    if rec is None and need:
        raise Fail("GoalMissing", "%s has no goal (set one with aos-agent goal set TEXT)" % a.name)
    return rec


def save(a, rec):
    try:
        goal_state.write(a.stack, rec)
    except OSError as e:
        raise Fail("WriteFailed", "cannot write %s: %s" % (goal_state.path(a.stack), e))


def words(args):
    return " ".join(args).strip()


def show(rec):
    if rec is None:
        print("no goal")
        return
    print("status\t%s" % rec["status"])
    print("text\t%s" % rec["text"])
    print("reminded\t%d of %d" % (rec["reminded"], rec["limit"]))
    if rec.get("reason"):
        print("reason\t%s" % rec["reason"])
    print("set_by\t%s" % rec.get("set_by", ""))
    print("updated\t%s by %s" % (rec.get("updated_at", ""), rec.get("updated_by", "")))


def limit_of(aopts, help):
    raw = aopts.get("limit", goal_state.DEFAULT_LIMIT)
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = 0
    if str(raw).strip() != str(n) or not 1 <= n <= goal_state.MAX_LIMIT:
        raise bad_args(help, "--limit must be a whole number from 1 to %d, not %s" % (goal_state.MAX_LIMIT, raw))
    return n


def cmd(argv):
    opts, rest = parse(argv, {"--target": "target"}, help=HELP, short=("-t",), sub=True)
    act, args = (rest[0], rest[1:]) if rest else ("get", [])
    if act not in HELPS:
        raise Fail("CommandUnknown", "goal: unknown subcommand %s (%s; see aos-agent goal --help)" % (act, ", ".join(HELPS)))
    flags = {"set": {"--limit": "limit"}}.get(act, {})
    switches = {"get": {"--json": "json"}, "done": {"--abandoned": "abandoned"}, "clear": {"--yes": "yes"}}.get(act, {})
    shorts = {"get": {"-j": "--json"}, "set": {"-n": "--limit"}, "done": {"-a": "--abandoned"}, "clear": ("-y",)}.get(act, ())
    aopts, args = parse(args, flags, switches, help=HELPS[act], short=shorts)
    if act in ("get", "resume", "clear") and args:
        raise bad_args(HELPS[act], "%s takes no arguments" % act)
    a = target(opts)
    by = who(a)
    if act == "get":
        rec = load(a, need=False)
        if aopts.get("json"):
            print(json.dumps(rec, ensure_ascii=False))
        else:
            show(rec)
        return
    if act == "set":
        if args == ["-"]:
            if sys.stdin is None or sys.stdin.isatty():
                raise bad_args(HELPS[act], "give TEXT, or pipe it on stdin with -")
            text = sys.stdin.read().strip()
        else:
            text = words(args)
        if not text:
            raise bad_args(HELPS[act], "set needs the goal TEXT")
        if len(text) > goal_state.MAX_TEXT:
            raise bad_args(HELPS[act], "the goal is %d characters; keep it under %d (one short sentence)" % (len(text), goal_state.MAX_TEXT))
        limit = limit_of(aopts, HELPS[act])
        old = os.path.exists(goal_state.path(a.stack))     # 舊的壞了也照蓋（set 就是重寫）
        save(a, goal_state.new(text, limit, by))
        print("set the goal of %s%s: %s (reminders: at most %d in a row without progress)"
              % (a.name, " (replaced the old one)" if old else "", text, limit))
        return
    if act == "clear":
        if not os.path.exists(goal_state.path(a.stack)):
            print("%s had no goal" % a.name)
            return
        if not aos_flags.confirm(PROG, "delete the goal of %s (%s)?" % (a.name, goal_state.path(a.stack)), yes=aopts.get("yes", False)):
            aos_flags.warn(PROG, "nothing done")
            return
        goal_state.clear(a.stack)
        print("deleted the goal of %s" % a.name)
        return
    rec = load(a)
    reason = words(args)
    if act == "done":
        status = "abandoned" if aopts.get("abandoned") else "done"
        save(a, goal_state.changed(rec, by, status=status, reason=reason))
        print("goal of %s marked %s%s; no more reminders" % (a.name, status, ": " + reason if reason else ""))
        return
    if rec["status"] in ("done", "abandoned"):
        raise Fail("GoalEnded", "the goal of %s is %s; give a new one with aos-agent goal set TEXT" % (a.name, rec["status"]))
    if act == "pause":
        if rec["status"] == "paused" and not reason:
            raise dc.Already("the goal of %s is already paused" % a.name)
        save(a, goal_state.changed(rec, by, status="paused", reason=reason))
        print("goal of %s paused%s; no reminders until resume" % (a.name, ": " + reason if reason else ""))
        return
    if rec["status"] == "active":
        raise dc.Already("the goal of %s is already active" % a.name)
    save(a, goal_state.changed(rec, by, status="active", reason="", reminded=0))
    print("goal of %s resumed (count back to 0 of %d)" % (a.name, rec["limit"]))
