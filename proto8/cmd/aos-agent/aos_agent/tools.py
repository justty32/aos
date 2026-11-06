# aos_agent/tools.py - 透過 aos-tools 管理 agent 的工具覆蓋層。
import os
import subprocess
import sys
from .common import Fail, TOOLS, note, parse, target
from .decl import agent_decl, pass_err, warn_shared


def tools_env(a):
    return dict(os.environ, AOS_STACK=a.stack, AOS_WS=a.ws)


def aos_tools(a, reg, over, args):
    """aos-tools --file <定義的登記檔> --overlay <stack>/tools.json …（疊法、寫法都歸 aos-tools；覆蓋層不在＝就是定義那份）。"""
    r = subprocess.run([sys.executable, TOOLS, "--file", reg, "--overlay", over] + list(args), stderr=subprocess.PIPE, text=True, env=tools_env(a))
    pass_err(r.returncode, r.stderr)


def cmd(argv):
    """tools（11-05 portable-flow 步 4，使用者「tools只存差異」）：<stack>/tools.json 是這隻的覆蓋層 {"add": {…}, "rm": […]}，
    不是定義的副本；身體每格讀「定義疊覆蓋層」。說明在 cmd/aos-agent/README.md「tools 覆蓋層」。"""
    opts, rest = parse(argv, {"--target": "target"})
    a = target(opts)
    folder, decl = agent_decl(a)
    rel = decl.get("tools")
    if not isinstance(rel, str) or not rel:
        raise Fail("ToolsMissing", "%s does not declare the tools sub-interface (write {\"aos-agent\": {\"tools\": \"tools.json\"}} in the definition's interfaces.json)" % a.name)
    orig, over = os.path.join(folder, rel), os.path.join(a.stack, "tools.json")
    act, args = (rest[0], rest[1:]) if rest else ("ls", [])
    if act in ("ls", "get"):
        if os.path.isfile(over):
            note("definition %s with this agent's overlay %s on top" % (orig, over))
        else:
            note("using the definition's %s (this agent has no overlay)" % orig)
        return aos_tools(a, orig, over, [act] + args)
    if act == "reset":
        if args:
            raise Fail("ArgumentsBad", "tools reset takes no arguments")
        if os.path.isfile(over):
            os.unlink(over)
            print("deleted overlay %s; back to the definition's %s only" % (over, orig))
        else:
            print("there was no overlay (using the definition's %s)" % orig)
        return
    if act == "add":                                  # 11-05 edge-agent：撞名時 aos-tools 說「加 --override」，原本這裡收不了
        topts, args = parse(args, {}, {"--override": "override", "--no-cache": "no_cache"})
        if len(args) != 2:
            raise Fail("ArgumentsBad", "usage: tools add [--override] [--no-cache] NAME PATH")
        targs = ["add"] + (["--override"] if topts.get("override") else []) + (["--no-cache"] if topts.get("no_cache") else []) \
            + ["--name", args[0], os.path.abspath(args[1])]
    elif act == "rm":
        if len(args) != 1:
            raise Fail("ArgumentsBad", "usage: tools rm NAME")
        targs = ["rm", args[0]]
    else:
        raise Fail("CommandUnknown", "tools: unknown action %s (ls, get, add [--override] [--no-cache], rm, reset)" % act)
    made = not os.path.isfile(over)
    aos_tools(a, orig, over, targs)                   # 失敗＝aos-tools 不寫（覆蓋層照舊）
    if made:
        note("created overlay %s (it records only what this agent added or removed; later changes to the definition still show through; tools reset deletes it)" % over)
    warn_shared(a, folder)
