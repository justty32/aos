# aos_agent/tools.py - 分層解析工具命令並管理 agent 自己那份工具登記檔（$override 定義那份）與重設確認。
import json
import os
import subprocess
import sys
import aos_flags
import directive_value
from . import declared_files
from . import PROG
from .common import Fail, TOOLS, actions, bad_args, note, parse, target
from .decl import agent_decl, pass_err, warn_shared



HELPS = {
    "ls": """aos-agent tools ls - list this agent's tools

usage: aos-agent [--daemon D] tools [--target NAME] ls [-l | --json]
       aos-agent tools ls --help

flags:
  -l, --long   NAME KIND PATH FROM STORED ENV (as aos-tools ls -l), and the names
               this agent turned off: NAME null PATH-IT-HIDES FILE#/tools/NAME null -
  -j, --json   print one JSON array
  -h, --help   show this help

Print NAME TAB the first sentence of its description per tool (see one in full with
get NAME): this agent's own registry when it has one (it overrides the
definition's), else the definition's. Tools turned off with rm are not listed;
ls -l shows them.
exit codes: 0 listed; 1 error (ToolsMissing, RegistryBad, ToolDefBad...).
""",
    "get": """aos-agent tools get - print a tool definition matching a name or path

usage: aos-agent [--daemon D] tools [--target NAME] get NAME_OR_PATH
       aos-agent tools get --help

flags:
  -h, --help   show this help

Print one JSON object per matching tool, including its tooldef and optional metainfo.
exit codes: 0 printed; 1 error (ToolMissing, ToolsMissing...).
""",
    "add": """aos-agent tools add - add a tool for this agent only

usage: aos-agent [--daemon D] tools [--target NAME] add [-n N] [--replace] [--envs K=V]... [--env-file FILE] [--no-cache] (XXX | --path-json JSON)
       aos-agent tools add --help

Same as aos-tools add (flags and meaning), written to this agent's own registry in
its stack, which overrides the definition's ("$override"); the definition stays as it
is. The first add or rm creates that file. XXX is a tool folder, JSON file or
executable, relative to the current directory; flags may go before or after it.

flags:
  -n, --name N        list it under this name (default: folder or file name)
      --replace       replace a tool already listed under that name
      --path-json J   store this JSON path value (string or directive) instead of XXX
      --envs K=V      set K to V for every call of this tool (repeatable)
      --env-file FILE remember where FILE is; it is read on every call
      --no-cache      inspect executable tool definitions each time
  -h, --help          show this help

exit codes: 0 added; 1 error (ToolExists, PathMissing, ToolsMissing...).
""",
    "rm": """aos-agent tools rm - remove a tool from this agent's toolbox

usage: aos-agent [--daemon D] tools [--target NAME] rm XXX
       aos-agent tools rm --help

flags:
  -h, --help   show this help

XXX = a tool name, else a path (relative to the current directory), as aos-tools rm.
Write "NAME": null in this agent's own registry (an entry whose value is null is not
a tool); the definition stays as it is.
exit codes: 0 removed; 1 error (ToolMissing, ToolsMissing...).
""",
    "reset": """aos-agent tools reset - delete this agent's own tools registry

usage: aos-agent [--daemon D] tools [--target NAME] reset [-y]
       aos-agent tools reset --help

flags:
  -y, --yes    skip confirmation
  -h, --help   show this help

Return to the definition's toolbox; asks on a terminal; -y skips.
exit codes: 0 reset or nothing done; 1 error (ToolsMissing...); 130 Ctrl-C.
""",
}
HELP = """aos-agent tools - manage this agent's toolbox

usage: aos-agent [--daemon D] tools [--target NAME] [ACTION] [FLAGS...] [ARGS...]
       aos-agent tools ACTION --help

actions:
%s

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -h, --help          show this help

No ACTION means ls. Changes go to this agent's own registry, which overrides the definition's.
exit codes: 0 ok; 1 error (TargetMissing, ToolsMissing...); 130 Ctrl-C.
""" % actions(HELPS.values(), "aos-agent [--daemon D] tools [--target NAME] ")
SUBS = {name: name for name in HELPS}

def tools_env(a):
    return dict(os.environ, AOS_STACK=a.stack, AOS_WS=a.ws)


OVERRIDE_KEY = "$override"   # 跟 aos-tools 同一個 key（使用者 11-10 K1「現在就寫 $override」）


def aos_tools(a, f, args):
    """aos-tools --file F …（11-10 aos-tools-cli 步 4：只傳一份；疊法、寫法都歸 aos-tools，stack 那份用 $override 指回定義那份）。"""
    r = subprocess.run([sys.executable, TOOLS, "--file", f] + list(args), stderr=subprocess.PIPE, text=True, env=tools_env(a))
    pass_err(r.returncode, r.stderr)


def pointer_for(a, orig, over, rel):
    """第一次建 stack 那份時寫的 $override（使用者 11-10 N2「跟你加 agent 時的寫法走」）：ctl add 給定義時是 $env 指示詞
    （daemon 表的 as_written.def，只讀）＝原樣接上宣告的相對路徑；其餘（絕對字串在表上分不出原寫法）＝相對 stack 那份的資料夾。"""
    aw = (a.row.get("as_written") or {}).get("def") if isinstance(a.row.get("as_written"), dict) else None
    if isinstance(aw, dict) and "$env" in aw and "$ref" not in aw and "$prefix" not in aw:
        p = dict(aw)
        p["$path"] = (aw.get("$path") or "").rstrip("/") + "/" + rel.lstrip("/")
        return p
    return os.path.relpath(orig, os.path.dirname(os.path.abspath(over)))


def check_pointer(over, orig):
    """stack 那份的 $override 解出來不是這隻定義的那份＝一行 warning（04 N2 後果：stack 被 cp 去配另一個定義時，指標不會跟著變）。
    只讀、解不開就不說（讀它的 aos-tools 自己會報）。"""
    try:
        with open(over, encoding="utf-8") as f:
            v = json.load(f).get(OVERRIDE_KEY)
    except (OSError, ValueError, AttributeError):
        return
    if v is None:
        return
    items, folder, found = (v if isinstance(v, list) else [v]), os.path.dirname(os.path.abspath(over)), []
    for i, item in enumerate(items):
        if isinstance(item, dict):
            at = directive_value.pointer(OVERRIDE_KEY, *([i] if isinstance(v, list) else []))
            try:
                item = directive_value.resolve(item, folder, over, stderr=subprocess.DEVNULL, at=at)   # #/… ＝ over 自己；#./、#../ 從這格所在的物件算
            except directive_value.Error:
                item = None
        if isinstance(item, str) and item:
            found.append(os.path.realpath(os.path.join(folder, item)))
    if found and os.path.realpath(orig) not in found:
        note("this agent's %s overrides %s, not its definition's %s (was the stack copied from another agent?)"
             % (over, ", ".join(found), orig))


def cmd(argv):
    """tools（11-05 portable-flow 步 4，使用者「tools只存差異」；11-10 aos-tools-cli 步 4 改形狀）：<stack>/<宣告相對路徑> 是這隻自己那份，
    {"$override": 定義那份, "tools": {加的…, "不要的": null}}（null 那格不算工具）；在就用它，不在就用定義那份。說明在 cmd/aos-agent/README.md「tools 覆蓋層」。"""
    opts, rest = parse(argv, {"--target": "target"}, help=HELP, short=("-t",), sub=True)
    act, args = (rest[0], rest[1:]) if rest else ("ls", [])
    if act not in SUBS:
        raise Fail("CommandUnknown", "tools: unknown subcommand %s (ls, get, add, rm, reset; see aos-agent tools --help)" % act)
    switches = {"ls": {"--json": "json", "--long": "long"},
                "add": {"--replace": "replace", "--no-cache": "no_cache"},
                "reset": {"--yes": "yes"}}.get(act, {})
    shorts = {"ls": {"-j": "--json", "-l": "--long"}, "reset": ("-y",)}.get(act, ())
    if act == "add":                                  # 11-10 Q8：旗標與 aos-tools add 一樣（C-86），原樣轉交
        try:
            topts, args = aos_flags.parse(args, {"--name": "name", "--env-file": "env_file", "--path-json": "path_json"},
                                          switches, {"--envs": "envs"}, help=HELPS[act], short=("-n",))
        except aos_flags.Error as e:
            if e.code == "ArgumentsBad":
                raise bad_args(HELPS[act], str(e)) from e
            raise Fail(e.code, "%s (see aos-agent tools add --help)" % e) from e
    else:
        topts, args = parse(args, {}, switches, help=HELPS[act], short=shorts)
    a = target(opts)
    folder, decl = agent_decl(a)
    rel = decl.get("tools")
    if not isinstance(rel, str) or not rel:
        raise Fail("ToolsMissing", "%s does not declare the tools sub-interface (write {\"aos-agent\": {\"tools\": \"tools.json\"}} in the definition's interfaces.json)" % a.name)
    try:
        rel = declared_files(folder)["tools"]
    except ValueError as e:
        raise Fail("ToolsBad", str(e)) from e
    orig, over = os.path.join(folder, rel), os.path.join(a.stack, rel)
    count = {"ls": 0, "get": 1, "add": 0 if "path_json" in topts else 1, "rm": 1, "reset": 0}[act]
    if len(args) != count:
        raise bad_args(HELPS[act], "add needs one XXX (or --path-json JSON)" if act == "add"
                       else "%s needs %d arguments" % (act, count))
    if act in ("ls", "get"):
        if os.path.isfile(over):
            note("using this agent's %s (it overrides the definition's %s)" % (over, orig))
            check_pointer(over, orig)
        else:
            note("using the definition's %s (this agent has no file of its own)" % orig)
        f = over if os.path.isfile(over) else orig
        return aos_tools(a, f, [act] + (["--json"] if topts.get("json") else []) + (["--long"] if topts.get("long") else []) + args)
    if act == "reset":
        if os.path.isfile(over):
            question = "delete the tools file %s of %s (back to the definition's %s)?" % (over, a.name, orig)
            if not aos_flags.confirm(PROG, question, yes=topts.get("yes", False)):
                aos_flags.warn(PROG, "nothing done")
                return 0
            os.unlink(over)
            print("deleted %s; back to the definition's %s only" % (over, orig))
        else:
            print("there was no file of this agent's own (using the definition's %s)" % orig)
        return
    if act == "add":                                  # 11-05 edge-agent：撞名時 aos-tools 說「加 --replace」，這裡收得了
        targs = ["add"] + (["--replace"] if topts.get("replace") else []) + (["--no-cache"] if topts.get("no_cache") else []) \
            + (["--name", topts["name"]] if "name" in topts else []) \
            + (["--env-file", topts["env_file"]] if "env_file" in topts else []) \
            + [x for kv in topts.get("envs", []) for x in ("--envs", kv)] \
            + (["--path-json", topts["path_json"]] if "path_json" in topts else []) + args
        # 照使用者的寫法轉（同一個 cwd）：絕對存絕對、相對存相對 stack 那份（11-10 TC）
    elif act == "rm":
        targs = ["rm", args[0]]
    else:
        raise Fail("CommandUnknown", "tools: unknown action %s (ls, get, add, rm, reset)" % act)
    made = not os.path.isfile(over)
    if made and os.path.isfile(orig):                 # 第一次：先建 {"$override": 定義那份}；定義那份不在＝add 直接新建一般登記檔
        r = subprocess.run([sys.executable, TOOLS, "--file", over, "override", "--path-json",
                            json.dumps(pointer_for(a, orig, over, rel))],
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, env=tools_env(a))
        pass_err(r.returncode, r.stderr)
    elif not made:
        check_pointer(over, orig)
    try:
        aos_tools(a, over, targs)
    except SystemExit:
        if made and os.path.isfile(over) and os.path.isfile(orig):
            os.unlink(over)                           # 剛建的只有指標；add／rm 沒成＝收回，不留一份空的
        raise
    if made:
        note("created %s (it records only what this agent added or removed; later changes to the definition still show through; tools reset deletes it)" % over)
    warn_shared(a, folder)
