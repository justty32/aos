# aos/apps/agent/hook.py - 管 agent 自己那份被勾清單（stack 裡的 hookeds 檔，疊在定義那份上，同名蓋過、null 關掉）：ls、get、add、rm、reset。
# 圖紙：proto8/thinking/2026-11/10/self-family/hook/01-圖紙.md § 4、§ 5。讀清單、驗格一律用 py/aos/agentlib/hooks.py，這裡只管命令列與寫 stack 那份。
# 11-21（線 top-1121-hooknew，使用者「簡化到第四層」）：旗標只剩 --event、-n、--timeout-ms、--replace、--path-json，加 agent 自己留的
#   --condition（「只攔某支工具」，使用者「1.對。」）與 on_clock 的四個鍵；清單在 interfaces.json 最外層的 hookeds；事件名不驗（宣告只是參考）；
#   沒有旗標檔了：before_run／after_run 要 loop.json 接上線才會發，沒接就提醒一行。
import json
import os
from aos import flags as aos_flags
from aos.agentlib import hooks
from . import PROG
from .common import Fail, actions, bad_args, note, parse, target
from .decl import def_of, warn_shared

LOOP_EVENTS = {"before_run": "on_before_run", "after_run": "on_after_run", "after_start": "on_start", "after_stop": "on_stop"}

HELPS = {
    "ls": """aos-agent hook ls - list this agent's hooks

usage: aos-agent [--daemon D] hook [--target NAME] ls [-l | --json]
       aos-agent hook ls --help

flags:
  -l, --long   also CONDITION TIMEOUT_MS FROM, and the names this agent turned off:
               NAME null - - - FILE
  -j, --json   print one JSON array (with "name" and "from")
  -h, --help   show this help

Print NAME TAB EVENT TAB HANDLER per hook in effect: the definition's hookeds with this
agent's own copy on top (same name replaces it, null turns it off).
HANDLER that is a directive object is printed as compact JSON.
exit codes: 0 listed; 1 error (HooksMissing, HooksBad...).
""",
    "get": """aos-agent hook get - print one hook

usage: aos-agent [--daemon D] hook [--target NAME] get NAME
       aos-agent hook get --help

flags:
  -h, --help   show this help

Print the hook as one JSON object (with "name" and "from").
exit codes: 0 printed; 1 error (HookMissing, HooksMissing...).
""",
    "add": """aos-agent hook add - add a hook for this agent only

usage: aos-agent [--daemon D] hook [--target NAME] add --event EVENT [-n N] [--condition M]... [--every-cycles N | --every-ms N] [--clock C] [--config JSON] [--timeout-ms N] [--replace] (XXX | --path-json JSON)
       aos-agent hook add --help

Run XXX (anything aos-exec runs: a tool folder, a JSON file, an executable) when
EVENT happens; the event JSON comes on its stdin. XXX is relative to the current
directory and is stored relative to this agent's hookeds file (absolute stays
absolute). Written to this agent's own copy in its stack; the definition stays as
it is. Flags may go before or after XXX.

events the agent itself fires (exit 10 blocks the ones marked *; exit 0 with a JSON
object on stdout changes the keys in brackets):
        before_queue* [content], after_queue, before_tool* [arguments],
        after_tool [content], brain_failed, tool_added,
        on_clock (a clock moved on: needs --every-cycles or --every-ms)
events fired through aos-hook fire, as the definition wires them:
        after_start, after_stop (loop.json on_start / on_stop),
        before_run, after_run (loop.json on_before_run / on_after_run: before / after each
        run of the loop body; exit 10 of a before_run hook skips that run; only when
        loop.json has that key, else one warning: recompile and restart),
        before_compact, after_compact (eca with claude: compact_hook)
Any other name is taken too (a declaration is only for reading; nothing fires an
event nobody wires). A failing hook (exit code not 0 / 10, too slow, bad stdout)
stops the event on a point marked * and is one warning line on the others; on the
loop points it stops the loop.

flags:
      --event EVENT       the event (required)
  -n, --name N            the hook's name (default: XXX's file or folder name)
      --condition M       run only when the tool name / error code is M (repeatable; for
                          before_tool, after_tool, tool_added, brain_failed)
      --every-cycles N    on_clock: run when the clock moved N cycles since the last run
      --every-ms N        on_clock: the same, N ms counted in cycles (N / $AOS_CLOCK_INTERVAL,
                          default 1000 ms a cycle; not the wall clock)
      --clock C           on_clock: which clock: a proc name on the daemon table (its stack
                          has a clock file), or the path of a clock file or of a folder with
                          one (relative = from the agent's stack); default $AOS_CLOCK
      --config JSON       on_clock: any JSON value kept in the entry as config; the handler
                          gets it as the event's config field (e.g. context_wrap's
                          '{"percent": 50, "wrap": true, "window": 200000}')
      --timeout-ms N      give up waiting after N ms (default 60000; 0 = no limit)
      --replace           replace a hook already listed under that name
      --path-json J       store this JSON value (path string or directive) instead of XXX
  -h, --help              show this help

exit codes: 0 added; 1 error (HookExists, PathMissing, NameBad, HooksMissing...).
""",
    "rm": """aos-agent hook rm - remove a hook from this agent

usage: aos-agent [--daemon D] hook [--target NAME] rm NAME
       aos-agent hook rm --help

flags:
  -h, --help   show this help

A hook from the definition is turned off ("NAME": null in this agent's own copy);
one this agent added is deleted from its copy. The definition stays as it is.
exit codes: 0 removed; 1 error (HookMissing, HooksMissing...).
""",
    "reset": """aos-agent hook reset - delete this agent's own hookeds copy

usage: aos-agent [--daemon D] hook [--target NAME] reset [-y]
       aos-agent hook reset --help

flags:
  -y, --yes    skip confirmation
  -h, --help   show this help

Return to the definition's hooks; asks on a terminal; -y skips.
exit codes: 0 reset or nothing done; 1 error (HooksMissing...); 130 Ctrl-C.
""",
}
HELP = """aos-agent hook - manage this agent's hooks (programs run when an event happens)

usage: aos-agent [--daemon D] hook [--target NAME] [ACTION] [FLAGS...] [ARGS...]
       aos-agent hook ACTION --help

actions:
%s

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT, else ./.stack or ./)
  -h, --help          show this help

No ACTION means ls. The hooks are in the hookeds file named at the top of the definition's
interfaces.json; changes go to this agent's own copy in its stack, on top of the definition's,
and apply from the next event. More: proto8/py/aos/apps/agent/docs/06-hook.md
exit codes: 0 ok; 1 error (TargetMissing, HooksMissing, HooksBad...); 130 Ctrl-C.
""" % actions(HELPS.values(), "aos-agent [--daemon D] hook [--target NAME] ")


def compact(v):
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def shown(name, entry):
    """給人看的一格：name 在前、去掉 base（解路徑用的內部欄）。"""
    out = {"name": name}
    out.update((k, v) for k, v in entry.items() if k != "base")
    return out


def guarded(fn, *args):
    try:
        return fn(*args)
    except hooks.HooksBad as e:
        raise Fail("HooksBad", str(e)) from e


def write_own(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")   # N-05：先寫暫存再改名
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    os.replace(tmp, path)


def read_own(path):
    """stack 那份原樣（已被 hooks.load 驗過）；不在＝{}。"""
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ls(entries, folder, stack, own, long, as_json):
    if as_json:
        print(json.dumps([shown(n, entries[n]) for n in sorted(entries)], ensure_ascii=False))
        return
    for n in sorted(entries):
        e = entries[n]
        if not long:
            print("\t".join((n, e["event"], compact(e["handler"]))))
            continue
        m = e.get("condition")
        m = "-" if m is None else m if isinstance(m, str) else ",".join(m)
        if e["event"] == hooks.CLOCK_EVENT:          # 11-11：on_clock 的條件寫在 CONDITION 欄
            m = ",".join(["%s=%s" % (k, e[k]) for k in hooks.CLOCK_KEYS if k in e]
                         + (["config=" + json.dumps(e["config"], ensure_ascii=False, separators=(",", ":"))]
                            if "config" in e else []))       # 一律 JSON：字串保留引號、\t \n 跳脫，不弄壞 TAB 欄
        print("\t".join((n, e["event"], compact(e["handler"]), m or "-", str(e.get("timeout_ms", 60000)), e["from"])))
    if long:
        for n in guarded(hooks.nulled, folder, stack):
            print("\t".join((n, "null") + ("-",) * 3 + (own,)))


def config_value(help, event, text):
    """--config 的字 → JSON 值；只有 on_clock 的 handler 拿得到 config（hook_clock.clock_tick），別的事件給了＝ArgumentsBad。"""
    if event != hooks.CLOCK_EVENT:
        raise bad_args(help, "--config is only for event %s (only its handler gets the config)" % hooks.CLOCK_EVENT)
    def no_nan(word):
        raise ValueError("%s is not standard JSON" % word)
    try:
        return json.loads(text, parse_constant=no_nan)
    except ValueError as e:
        raise bad_args(help, "--config is not JSON: %s" % e) from e


def build(topts, args, own, help):
    """add 的旗標 → (名字, 格)；只寫有給的選項鍵。"""
    if not topts.get("event"):
        raise bad_args(help, "add needs --event EVENT (%s)" % ", ".join(list(hooks.POINTS) + list(LOOP_EVENTS)))
    if "path_json" in topts:
        try:
            target_v = json.loads(topts["path_json"])
        except ValueError as e:
            raise bad_args(help, "--path-json is not JSON: %s" % e) from e
        if not ((isinstance(target_v, str) and target_v) or (isinstance(target_v, dict) and target_v)):
            raise bad_args(help, "--path-json must be a non-empty JSON string or object")
        if "name" not in topts:
            raise bad_args(help, "--path-json needs --name")
        name = topts["name"]
    else:
        xxx = args[0]
        if not os.path.exists(xxx):
            raise Fail("PathMissing", "%s does not exist (relative to the current directory)" % xxx)
        full = os.path.abspath(xxx)
        target_v = full if os.path.isabs(xxx) else os.path.relpath(full, os.path.dirname(os.path.abspath(own)))
        name = topts.get("name", os.path.basename(full))
    try:
        hooks.hook_lists.check_name(name)
    except hooks.HooksBad as e:
        raise Fail("NameBad", "%s (give one with --name)" % e) from e
    entry = {"event": topts["event"], "handler": target_v}
    if "condition" in topts:
        entry["condition"] = topts["condition"][0] if len(topts["condition"]) == 1 else topts["condition"]
    for key in ("every_cycles", "every_ms"):        # 11-11 on_clock（不是正整數交給 check_entry 說）
        if key in topts:
            entry[key] = int(topts[key]) if topts[key].isdigit() else topts[key]
    if "clock" in topts:
        entry["clock"] = topts["clock"]
    if "timeout_ms" in topts:
        t = topts["timeout_ms"]
        entry["timeout_ms"] = int(t) if t.isdigit() else t     # 不是正整數交給 check_entry 說
    try:
        hooks.check_entry(entry)
    except hooks.HooksBad as e:
        raise bad_args(help, str(e)) from e
    if "config" in topts:                         # 11-16 ok-small：重加 context_wrap 時帶得回門檻（hooks.py 原樣交給 on_clock handler）；
        entry["config"] = config_value(help, topts["event"], topts["config"])   # 事件本身的錯先報
    return name, entry


def loop_wired(folder, event):
    """loop 的點（aos-hook fire 發的）：定義的 loop.json 有沒有接這條線；不是 loop 的點、讀不到 loop.json＝當作有。"""
    key = LOOP_EVENTS.get(event)
    if key is None:
        return True
    try:
        with open(os.path.join(folder, "loop.json"), encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return True
    return not isinstance(doc, dict) or doc.get(key) is not None


def cmd(argv):
    opts, rest = parse(argv, {"--target": "target"}, help=HELP, short=("-t",), sub=True)
    act, args = (rest[0], rest[1:]) if rest else ("ls", [])
    if act not in HELPS:
        raise Fail("CommandUnknown", "hook: unknown subcommand %s (ls, get, add, rm, reset; see aos-agent hook --help)" % act)
    flags = {"add": {"--event": "event", "--name": "name", "--timeout-ms": "timeout_ms",
                     "--path-json": "path_json", "--every-cycles": "every_cycles", "--every-ms": "every_ms",
                     "--clock": "clock", "--config": "config"}}.get(act, {})
    switches = {"ls": {"--json": "json", "--long": "long"}, "add": {"--replace": "replace"},
                "reset": {"--yes": "yes"}}.get(act, {})
    shorts = {"ls": {"-j": "--json", "-l": "--long"}, "add": ("-n",), "reset": ("-y",)}.get(act, ())
    try:
        topts, args = aos_flags.parse(args, flags, switches, {"--condition": "condition"} if act == "add" else None,
                                      help=HELPS[act], short=shorts)
    except aos_flags.Error as e:
        if e.code == "ArgumentsBad":
            raise bad_args(HELPS[act], str(e)) from e
        raise Fail(e.code, "%s (see aos-agent hook %s --help)" % (e, act)) from e
    count = {"ls": 0, "get": 1, "add": 0 if "path_json" in topts else 1, "rm": 1, "reset": 0}[act]
    if len(args) != count:
        raise bad_args(HELPS[act], "add needs one XXX (or --path-json JSON)" if act == "add"
                       else "%s needs %d argument%s" % (act, count, "" if count == 1 else "s"))
    if act == "ls" and topts.get("json") and topts.get("long"):
        raise bad_args(HELPS[act], "use -l or --json, not both")
    a = target(opts)
    folder = def_of(a)
    own = guarded(hooks.own, folder, a.stack)
    if not own:
        raise Fail("HooksMissing", "%s names no hookeds file it can keep a copy of (write \"hookeds\": \"hookeds.json\" at the top "
                   "of the definition's interfaces.json)" % a.name)
    entries = guarded(hooks.load, folder, a.stack)
    if act == "ls":
        return ls(entries, folder, a.stack, own, topts.get("long"), topts.get("json"))
    if act == "get":
        if args[0] not in entries:
            raise Fail("HookMissing", "%s has no hook named %s (see aos-agent hook ls)" % (a.name, args[0]))
        print(json.dumps(shown(args[0], entries[args[0]]), ensure_ascii=False))
        return
    if act == "reset":
        if os.path.isfile(own):
            question = "delete the hookeds copy %s of %s (back to the definition's)?" % (own, a.name)
            if not aos_flags.confirm(PROG, question, yes=topts.get("yes", False)):
                aos_flags.warn(PROG, "nothing done")
                return
            os.unlink(own)
            print("deleted %s; back to the definition's hooks only" % own)
        else:
            print("there was no copy of this agent's own (using the definition's hooks)")
        return
    made, doc = not os.path.isfile(own), read_own(own)
    if act == "add":
        name, entry = build(topts, args, own, HELPS[act])
        if name in entries and not topts.get("replace"):
            raise Fail("HookExists", "%s already has a hook named %s (add --replace to replace it)" % (a.name, name))
        doc[name] = entry
        write_own(own, doc)
        print("added %s (%s#/%s: %s)" % (name, own, name, json.dumps(entry, ensure_ascii=False)))
        if not loop_wired(folder, entry["event"]):
            aos_flags.warn(PROG, "%s/loop.json has no %s, so nothing fires %s for this agent: recompile the definition (or add "
                           "that key, like on_start) and restart the agent" % (folder, LOOP_EVENTS[entry["event"]], entry["event"]))
    else:
        name = args[0]
        if name not in entries:
            raise Fail("HookMissing", "%s has no hook named %s (see aos-agent hook ls)" % (a.name, name))
        in_def = name in guarded(hooks.load, folder, None)     # 只看定義那份
        if in_def:
            doc[name] = None
        else:
            doc.pop(name, None)
        write_own(own, doc)
        print("removed %s (%s#/%s: %s)" % (name, own, name, "set to null" if in_def else "deleted"))
    if made:
        note("created %s (it records only what this agent added or turned off; the definition's hooks still show through; hook reset deletes it)" % own)
    warn_shared(a, folder)
