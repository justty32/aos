# aos_agent/tools.py - 分層解析工具命令並管理 agent 的工具覆蓋層與重設確認。
import os
import subprocess
import sys
import aos_flags
from . import declared_files
from . import PROG
from .common import Fail, TOOLS, actions, bad_args, note, parse, target
from .decl import agent_decl, pass_err, warn_shared



HELPS = {
    "ls": """aos-agent tools ls - list this agent's tools

usage: aos-agent [--daemon D] tools [--target NAME] ls [--json]
       aos-agent tools ls --help

flags:
  -j, --json   print one JSON array
  -h, --help   show this help

Print NAME TAB KIND TAB PATH per tool; the definition is merged with this agent's overlay.
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
    "add": """aos-agent tools add - add a tool to this agent's overlay

usage: aos-agent [--daemon D] tools [--target NAME] add [--override] [--no-cache] NAME PATH
       aos-agent tools add --help

flags:
  --override   replace an existing name
  --no-cache   inspect executable tool definitions each time
  -h, --help   show this help

Only this agent's overlay changes; PATH is resolved from the current directory.
exit codes: 0 added; 1 error (ToolExists, PathMissing, ToolsMissing...).
""",
    "rm": """aos-agent tools rm - remove a tool from this agent's toolbox

usage: aos-agent [--daemon D] tools [--target NAME] rm NAME
       aos-agent tools rm --help

flags:
  -h, --help   show this help

Record the removal in this agent's overlay; the definition stays as it is.
exit codes: 0 removed; 1 error (ToolMissing, ToolsMissing...).
""",
    "reset": """aos-agent tools reset - delete this agent's tools overlay

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

No ACTION means ls. Changes belong to this agent's overlay of the definition's toolbox.
exit codes: 0 ok; 1 error (TargetMissing, ToolsMissing...); 130 Ctrl-C.
""" % actions(HELPS.values(), "aos-agent [--daemon D] tools [--target NAME] ")
SUBS = {name: name for name in HELPS}

def tools_env(a):
    return dict(os.environ, AOS_STACK=a.stack, AOS_WS=a.ws)


def aos_tools(a, reg, over, args):
    """aos-tools --file <定義的宣告檔> --overlay <stack>/<宣告相對路徑> …（疊法、寫法都歸 aos-tools；覆蓋層不在＝就是定義那份）。"""
    r = subprocess.run([sys.executable, TOOLS, "--file", reg, "--overlay", over] + list(args), stderr=subprocess.PIPE, text=True, env=tools_env(a))
    pass_err(r.returncode, r.stderr)


def cmd(argv):
    """tools（11-05 portable-flow 步 4，使用者「tools只存差異」）：<stack>/<宣告相對路徑> 是這隻的覆蓋層 {"add": {…}, "rm": […]}，
    不是定義的副本；身體每格讀「定義疊覆蓋層」。說明在 cmd/aos-agent/README.md「tools 覆蓋層」。"""
    opts, rest = parse(argv, {"--target": "target"}, help=HELP, short=("-t",))
    act, args = (rest[0], rest[1:]) if rest else ("ls", [])
    if act not in SUBS:
        raise Fail("CommandUnknown", "tools: unknown subcommand %s (ls, get, add, rm, reset; see aos-agent tools --help)" % act)
    switches = {"ls": {"--json": "json"},
                "add": {"--override": "override", "--no-cache": "no_cache"},
                "reset": {"--yes": "yes"}}.get(act, {})
    shorts = {"ls": ("-j",), "reset": ("-y",)}.get(act, ())
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
    count = {"ls": 0, "get": 1, "add": 2, "rm": 1, "reset": 0}[act]
    if len(args) != count:
        raise bad_args(HELPS[act], "%s needs %d arguments" % (act, count))
    if act in ("ls", "get"):
        if os.path.isfile(over):
            note("definition %s with this agent's overlay %s on top" % (orig, over))
        else:
            note("using the definition's %s (this agent has no overlay)" % orig)
        return aos_tools(a, orig, over, [act] + (["--json"] if topts.get("json") else []) + args)
    if act == "reset":
        if os.path.isfile(over):
            question = "delete the tools overlay %s of %s (back to the definition's %s)?" % (over, a.name, orig)
            if not aos_flags.confirm(PROG, question, yes=topts.get("yes", False)):
                aos_flags.warn(PROG, "nothing done")
                return 0
            os.unlink(over)
            print("deleted overlay %s; back to the definition's %s only" % (over, orig))
        else:
            print("there was no overlay (using the definition's %s)" % orig)
        return
    if act == "add":                                  # 11-05 edge-agent：撞名時 aos-tools 說「加 --override」，原本這裡收不了
        targs = ["add"] + (["--override"] if topts.get("override") else []) + (["--no-cache"] if topts.get("no_cache") else []) \
            + ["--name", args[0], args[1]]           # 照使用者的寫法轉（同一個 cwd）：絕對存絕對、相對存相對覆蓋層（11-10 TC）
    elif act == "rm":
        targs = ["rm", args[0]]
    else:
        raise Fail("CommandUnknown", "tools: unknown action %s (ls, get, add [--override] [--no-cache], rm, reset)" % act)
    made = not os.path.isfile(over)
    aos_tools(a, orig, over, targs)                   # 失敗＝aos-tools 不寫（覆蓋層照舊）
    if made:
        note("created overlay %s (it records only what this agent added or removed; later changes to the definition still show through; tools reset deletes it)" % over)
    warn_shared(a, folder)
