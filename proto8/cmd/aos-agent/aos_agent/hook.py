# aos_agent/hook.py - 管 agent 自己那份 hooks 清單（疊在定義那份上，同名蓋過、null 關掉）：ls、get、add、rm、reset。
# 圖紙：proto8/thinking/2026-11/10/self-family/hook/01-圖紙.md § 4、§ 5。讀清單、驗格一律用 lib/agent/hooks.py，這裡只管命令列與寫 stack 那份。
import json
import os
import aos_flags
from agent import hooks
from . import PROG
from .common import Fail, actions, bad_args, note, parse, target
from .decl import agent_decl, warn_shared


HELPS = {
    "ls": """aos-agent hook ls - list this agent's hooks

usage: aos-agent [--daemon D] hook [--target NAME] ls [-l | --json]
       aos-agent hook ls --help

flags:
  -l, --long   also MATCH WAIT ON_FAIL CHANGE TIMEOUT_MS FROM, and the names this
               agent turned off: NAME null - - - - - - FILE
  -j, --json   print one JSON array (defaults filled in, with "name" and "from")
  -h, --help   show this help

Print NAME TAB EVENT TAB EXEC per hook in effect: the definition's list with this
agent's own list on top (same name replaces it, null turns it off).
EXEC that is a directive object is printed as compact JSON.
exit codes: 0 listed; 1 error (HooksMissing, HooksBad...).
""",
    "get": """aos-agent hook get - print one hook

usage: aos-agent [--daemon D] hook [--target NAME] get NAME
       aos-agent hook get --help

flags:
  -h, --help   show this help

Print the hook as one JSON object (defaults filled in, with "name" and "from").
exit codes: 0 printed; 1 error (HookMissing, HooksMissing...).
""",
    "add": """aos-agent hook add - add a hook for this agent only

usage: aos-agent [--daemon D] hook [--target NAME] add --on EVENT [-n N] [--match M]... [--change] [--no-wait] [--on-fail stop|continue] [--timeout-ms N] [--replace] (XXX | --path-json JSON)
       aos-agent hook add --help

Run XXX (anything aos-exec runs: a tool folder, a JSON file, an executable) when
EVENT happens; the event JSON comes on its stdin. XXX is relative to the current
directory and is stored relative to this agent's hooks file (absolute stays
absolute). Written to this agent's own list in its stack; the definition stays as
it is. Flags go before XXX.

events: queue_before, queue_after, tool_before, tool_after, brain_failed, tool_added

flags:
      --on EVENT          the event (required)
  -n, --name N            the hook's name (default: XXX's file or folder name)
      --match M           run only when the tool name / error code is M (repeatable;
                          not for queue_before / queue_after)
      --change            read its reply: exit 0 + JSON on stdout changes the event,
                          exit 10 blocks it (queue_before, tool_before, tool_after)
      --no-wait           start it and do not wait (cannot be used with --change)
      --on-fail W         stop (default: the agent stops) or continue (a warning)
      --timeout-ms N      give up waiting after N ms (default 60000)
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

A hook from the definition is turned off ("NAME": null in this agent's own list);
one this agent added is deleted from its list. The definition stays as it is.
exit codes: 0 removed; 1 error (HookMissing, HooksMissing...).
""",
    "reset": """aos-agent hook reset - delete this agent's own hooks list

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
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -h, --help          show this help

No ACTION means ls. Changes go to this agent's own list, which sits on top of the definition's.
Changes apply from the next event. More: proto8/cmd/aos-agent/docs/06-hook.md
exit codes: 0 ok; 1 error (TargetMissing, HooksMissing, HooksBad...); 130 Ctrl-C.
""" % actions(HELPS.values(), "aos-agent [--daemon D] hook [--target NAME] ")
COLS = ("on", "exec", "match", "wait", "on_fail", "change", "timeout_ms", "from")


def compact(v):
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def shown(name, entry):
    """給人看的一格：name 在前、去掉 base（解路徑用的內部欄）。"""
    out = {"name": name}
    out.update((k, v) for k, v in entry.items() if k != "base")
    return out


def loaded(folder, stack):
    try:
        return hooks.load(folder, stack)
    except hooks.HooksBad as e:
        raise Fail("HooksBad", str(e)) from e


def write_own(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")   # N-05：先寫暫存再改名
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    os.replace(tmp, path)


def read_own(path):
    """stack 那份原樣（已被 hooks.load 驗過）；不在＝{"hooks": {}}。"""
    if not os.path.isfile(path):
        return {"hooks": {}}
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    doc.setdefault("hooks", {})
    return doc


def ls(entries, folder, stack, own, long, as_json):
    if as_json:
        print(json.dumps([shown(n, entries[n]) for n in sorted(entries)], ensure_ascii=False))
        return
    for n in sorted(entries):
        e = entries[n]
        if not long:
            print("\t".join((n, e["on"], compact(e["exec"]))))
            continue
        m = e.get("match")
        m = "-" if m is None else m if isinstance(m, str) else ",".join(m)
        print("\t".join((n, e["on"], compact(e["exec"]), m, json.dumps(e["wait"]), e["on_fail"],
                         json.dumps(e["change"]), str(e["timeout_ms"]), e["from"])))
    if long:
        for n in loaded_nulled(folder, stack):
            print("\t".join((n, "null") + ("-",) * 6 + (own,)))


def loaded_nulled(folder, stack):
    try:
        return hooks.nulled(folder, stack)
    except hooks.HooksBad as e:
        raise Fail("HooksBad", str(e)) from e


def build(topts, args, own, help):
    """add 的旗標 → (名字, 格)；只寫有給的選項鍵。"""
    if "on" not in topts:
        raise bad_args(help, "add needs --on EVENT (%s)" % ", ".join(hooks.EVENTS))
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
            raise Fail("PathMissing", "%s does not exist (relative to the current directory %s)" % (xxx, os.getcwd()))
        full = os.path.abspath(xxx)
        target_v = full if os.path.isabs(xxx) else os.path.relpath(full, os.path.dirname(os.path.abspath(own)))
        name = topts.get("name", os.path.basename(full))
    if not name or "/" in name or name.startswith("."):
        raise Fail("NameBad", "hook name %r must be non-empty, without / and not start with . (give one with --name)" % name)
    entry = {"on": topts["on"], "exec": target_v}
    if "match" in topts:
        entry["match"] = topts["match"][0] if len(topts["match"]) == 1 else topts["match"]
    if topts.get("change"):
        entry["change"] = True
    if topts.get("no_wait"):
        entry["wait"] = False
    if "on_fail" in topts:
        entry["on_fail"] = topts["on_fail"]
    if "timeout_ms" in topts:
        t = topts["timeout_ms"]
        entry["timeout_ms"] = int(t) if t.isdigit() else t     # 不是正整數交給 validate_entry 說
    try:
        hooks.validate_entry(entry)
    except hooks.HooksBad as e:
        raise bad_args(help, str(e)) from e
    return name, entry


def cmd(argv):
    opts, rest = parse(argv, {"--target": "target"}, help=HELP, short=("-t",))
    act, args = (rest[0], rest[1:]) if rest else ("ls", [])
    if act not in HELPS:
        raise Fail("CommandUnknown", "hook: unknown subcommand %s (ls, get, add, rm, reset; see aos-agent hook --help)" % act)
    flags = {"add": {"--on": "on", "--name": "name", "--on-fail": "on_fail", "--timeout-ms": "timeout_ms",
                     "--path-json": "path_json"}}.get(act, {})
    switches = {"ls": {"--json": "json", "--long": "long"},
                "add": {"--change": "change", "--no-wait": "no_wait", "--replace": "replace"},
                "reset": {"--yes": "yes"}}.get(act, {})
    shorts = {"ls": {"-j": "--json", "-l": "--long"}, "add": ("-n",), "reset": ("-y",)}.get(act, ())
    try:
        topts, args = aos_flags.parse(args, flags, switches, {"--match": "match"} if act == "add" else None,
                                      help=HELPS[act], short=shorts)
    except aos_flags.Error as e:
        if e.code == "ArgumentsBad":
            raise bad_args(HELPS[act], str(e)) from e
        raise Fail(e.code, "%s (see aos-agent hook %s --help)" % (e, act)) from e
    count = {"ls": 0, "get": 1, "add": 0 if "path_json" in topts else 1, "rm": 1, "reset": 0}[act]
    if act == "add" and len(args) > count and args[count].startswith("-"):
        raise bad_args(HELPS[act], "flags go before XXX: %s" % args[count])
    if len(args) != count:
        raise bad_args(HELPS[act], "add needs one XXX (or --path-json JSON)" if act == "add"
                       else "%s needs %d argument%s" % (act, count, "" if count == 1 else "s"))
    if act == "ls" and topts.get("json") and topts.get("long"):
        raise bad_args(HELPS[act], "use -l or --json, not both")
    a = target(opts)
    folder, _ = agent_decl(a)
    try:
        rel = hooks.declared(folder)
    except hooks.HooksBad as e:
        raise Fail("HooksBad", str(e)) from e
    if not rel:
        raise Fail("HooksMissing", "%s does not declare hooks (write {\"aos-agent\": {\"hooks\": \"hooks.json\"}} in the definition's interfaces.json)" % a.name)
    mine, own = os.path.join(folder, rel), os.path.join(a.stack, rel)
    entries = loaded(folder, a.stack)
    if act == "ls":
        return ls(entries, folder, a.stack, own, topts.get("long"), topts.get("json"))
    if act == "get":
        if args[0] not in entries:
            raise Fail("HookMissing", "%s has no hook named %s (see aos-agent hook ls)" % (a.name, args[0]))
        print(json.dumps(shown(args[0], entries[args[0]]), ensure_ascii=False))
        return
    if act == "reset":
        if os.path.isfile(own):
            question = "delete the hooks file %s of %s (back to the definition's %s)?" % (own, a.name, mine)
            if not aos_flags.confirm(PROG, question, yes=topts.get("yes", False)):
                aos_flags.warn(PROG, "nothing done")
                return
            os.unlink(own)
            print("deleted %s; back to the definition's %s only" % (own, mine))
        else:
            print("there was no file of this agent's own (using the definition's %s)" % mine)
        return
    made, doc = not os.path.isfile(own), read_own(own)
    if act == "add":
        name, entry = build(topts, args, own, HELPS[act])
        if name in entries and not topts.get("replace"):
            raise Fail("HookExists", "%s already has a hook named %s (add --replace to replace it)" % (a.name, name))
        doc["hooks"][name] = entry
        write_own(own, doc)
        print("added %s (%s#/hooks/%s: %s)" % (name, own, name, json.dumps(entry, ensure_ascii=False)))
    else:
        name = args[0]
        if name not in entries:
            raise Fail("HookMissing", "%s has no hook named %s (see aos-agent hook ls)" % (a.name, name))
        in_def = name in loaded(folder, folder)          # stack 傳定義自己＝只看定義那份
        if in_def:
            doc["hooks"][name] = None
        else:
            del doc["hooks"][name]
        write_own(own, doc)
        print("removed %s (%s#/hooks/%s: %s)" % (name, own, name, "set to null" if in_def else "deleted"))
    if made:
        note("created %s (it records only what this agent added or turned off; the definition's %s still shows through; hook reset deletes it)" % (own, mine))
    warn_shared(a, folder)
