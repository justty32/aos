# cli_mcp.py - cli_session 接 MCP：aos-mcp 那台的旗標（claude 的 mcp.json／codex 的 -c）、外部 MCP server、tools_sub 子 agent 那台與 guard hook
import json, os, shlex, shutil, sys

if __package__:
    from . import cli_base
    from .cli_base import SELF, _lib, tool_io
else:
    import cli_base
    from cli_base import SELF, _lib, tool_io


def _server_mod():
    sys.path.insert(0, _lib)   # mcp_server_file 跟 tool_io 同在 lib/（直接執行此檔時 lib 不在 sys.path）
    try:
        import mcp_server_file
    finally:
        sys.path.pop(0)
    return mcp_server_file


def external_servers(cfg, tool_dir, path):
    """cli.json 選填 mcp_servers（11-12 external-mcp，使用者裁「都按照推薦。」）：server 檔路徑的陣列，相對從 cli.json 的資料夾算、
    也可寫指示詞（同 tools）。陣列本身形狀不對＝CfgBad；某一份壞（檔不在、形狀不對、重名、名字 aos、指示詞解不開）＝warning 跳過那台、其他照接（X8）。
    http 與 stdio 兩身都接（stdio 經 aos-mcp-launch，03 步 4）。回讀好的 server 列表（mcp_server_file.load 的形狀）。"""
    if "mcp_servers" not in cfg:
        return []
    entries = cfg["mcp_servers"]
    if not isinstance(entries, list) or not all(isinstance(e, (str, dict)) and e for e in entries):
        cli_base.die("CfgBad", "%s: mcp_servers must be an array of server file paths (strings or directives)" % path)
    msf, base, out, seen = _server_mod(), os.path.abspath(tool_dir), [], set()
    for e in entries:
        try:
            if isinstance(e, dict):
                sys.path.insert(0, _lib)
                try:
                    from directive_value import resolve_path
                finally:
                    sys.path.pop(0)
                e = resolve_path(e, path, "mcp_servers")
            s = msf.load(os.path.normpath(os.path.join(base, e)))
        except tool_io.Error as err:
            cli_base.warn("external MCP server skipped: %s %s" % (err.code, err))
            continue
        if s["name"] in seen:
            cli_base.warn("external MCP server %s skipped: the name is already used by an earlier server file (%s)" % (s["name"], s["file"]))
            continue
        seen.add(s["name"])
        out.append(s)
    return out


def stdio_ready(servers):
    """起 CLI 前先看每台 stdio server 起不起得來：CLI 自己接的 server 起不來，CLI 只是少了那台的工具、不說原因，aos 看不到。
    照 aos-mcp-launch 的讀法解出指令與環境（mcp_server_file.stdio_launch：指示詞、env、env_file）；解不開、指令找不到或不能執行
    ＝warning 跳過那台、其他照接（X8）。只看起不起得來；起來之後才壞的（握手失敗、中途死掉）只有 CLI 知道。回留下的 servers。"""
    msf, kept = _server_mod(), []
    for s in servers:
        if s["transport"] == "stdio":
            sys.path.insert(0, _lib)                  # stdio_launch 用到才 import directive_value（同在 lib/）
            try:
                argv, env, _ = msf.stdio_launch(s["file"])
            except tool_io.Error as err:
                cli_base.warn("external MCP server %s skipped: %s %s" % (s["name"], err.code, err))
                continue
            finally:
                sys.path.pop(0)
            cmd = argv[0]
            tries = [cmd] if "/" in cmd else [os.path.join(d or ".", cmd) for d in env.get("PATH", os.defpath).split(os.pathsep)]
            if not any(os.path.isfile(t) and os.access(t, os.X_OK) for t in tries):
                cli_base.warn("external MCP server %s skipped: CommandMissing its command is not found or cannot be run: %s"
                              % (s["name"], cmd))
                continue
        kept.append(s)
    return kept


def external_codex(cfg):
    """codex 這一次要加的 (-c 旗標, 只給 codex 行程的環境, 畫面啟動器的 spec)：每次起 codex 前叫，env 檔在這一刻才讀。"""
    if not cfg.get("external"):
        return [], {}, None
    msf = _server_mod()
    kept, env, spec = msf.http_plan(stdio_ready(cfg["external"]), cli_base.warn)
    launcher = _launcher(kept)
    stdio_env = {k: os.environ[k] for k in MCP_ENV if os.environ.get(k)}
    return msf.codex_argv(kept, launcher, stdio_env), env, (spec if spec["set"] or spec["from"] else None)


def _launcher(servers):
    """有 stdio server＝aos-mcp-launch 的絕對路徑（從 PATH 找，N-50）；不在 PATH＝CliMissing。沒有 stdio＝None。"""
    if not any(s["transport"] == "stdio" for s in servers):
        return None
    path = shutil.which("aos-mcp-launch")
    if path is None:
        cli_base.die("CliMissing", "aos-mcp-launch is not on PATH (an stdio MCP server is listed in mcp_servers; add proto8/cmd/aos-mcp-launch/bin to PATH)")
    return os.path.abspath(path)


def external_claude(cfg):
    """claude 這一次的 (留下的 http server, 只給 claude 行程的環境, 畫面啟動器的 spec)：token 走 headersHelper、不進環境；ca_file＝NODE_EXTRA_CA_CERTS。"""
    if not cfg.get("external"):
        return [], {}, None
    return _server_mod().claude_plan(stdio_ready(cfg["external"]), cli_base.warn)


def exec_wrap(argv, spec):
    """畫面那條路：有金鑰或憑證要給＝前面接 mcp_server_file 的啟動器（命令列只有路徑與變數名），值只進 CLI 行程（tmux 的環境沒有）。"""
    if not spec:
        return argv
    return [sys.executable, os.path.join(_lib, "mcp_server_file.py"), "--exec", json.dumps(spec), "--"] + argv


# codex 起 MCP server 不帶父程序的環境變數（11-11 實測：aos-mcp 少了 AOS_HOME 解不開範本登記檔的指示詞、起不來，腦看不到任何 aos 工具），
# 所以明寫帶進 mcp_servers.aos.env。帶哪些＝aos-mcp、aos-tools 與 lib 工具實際讀的（_tooldef 的 env、程式裡讀的）；
# AOS_CD／AOS_ENTRY／AOS_AGENT 是每支程序自己的，不帶。使用者 11-11 選項框裁「修」。
MCP_ENV = ("AOS_HOME", "AOS_DAEMON", "AOS_CLOCK", "AOS_CLOCK_INTERVAL", "AOS_LLM_KERNEL", "AOS_KERNEL",
           "AOS_LINUX_USER_STACK")                # 11-11 舊 do_task 的 AOS_DO_TASK_DEPTH／AOS_DO_TASK_FROM 隨它拿掉


def mcp_env(ws, stack):
    """給 codex 的 aos MCP server 的環境：MCP_ENV 裡有設（非空）的，加上這次的 AOS_WS、AOS_STACK（跟 --ws／--stack 同值）。"""
    env = {k: os.environ[k] for k in MCP_ENV if os.environ.get(k)}
    env.update(AOS_WS=ws, AOS_STACK=stack)
    return env


def mcp_argv(cfg, cell, ws, stack, external=()):
    """有登記檔＝接上 aos-mcp 要加給 CLI 的旗標；沒有＝[]（11-03 eca-tools）。每次起 CLI 前叫（claude 的 mcp.json 每次重寫）。
    ws＝CLI 的 cwd、stack＝給 aos-mcp 的 --stack（工具叫的小格在 <stack>/tools/<名>/）。
    external＝claude 身要並排接的外部 http server（external_claude 留下的；11-12 external-mcp 步 3）；codex 的外部 server 走 external_codex。"""
    reg, sub = cfg.get("registry"), cfg.get("sub_registry")
    if not reg and not external and not sub:
        return []
    servers = {}
    if reg:
        servers = _aos_server(cfg, ws, stack, reg)
        if cfg["kind"] == "codex":
            return servers
    msf = _server_mod() if external else None
    entries, allowed, denied = msf.claude_entries(external, _launcher(external)) if external else ({}, [], [])
    servers.update(entries)
    try:
        cell.write("mcp.json", json.dumps({"mcpServers": servers}, ensure_ascii=False) + "\n")
    except OSError as e:
        cli_base.die("WriteFailed", "cannot write %s: %s" % (tool_io.place(cell.file("mcp.json")), tool_io.os_reason(e)))
    allow = (["mcp__aos"] if reg else []) + (["mcp__" + SUB_SERVER] if sub else []) + allowed
    return ["--mcp-config", cell.file("mcp.json"), "--allowedTools", ",".join(allow)] \
        + (["--disallowedTools", ",".join(denied)] if denied else []) \
        + (["--agents", json.dumps(sub_agents(cfg, ws, stack), ensure_ascii=False)] if sub else [])


# 子 agent 那台（11-12 eca-task-subagent）。蓋掉的是 claude 內建的 general-purpose（Agent 工具沒指定類型時用的那個）。
SUB_SERVER, SUB_AGENT = "aos_sub", "general-purpose"
SUB_DESCRIPTION = ("General-purpose agent for researching complex questions, searching for code, and executing multi-step tasks. "
                   "It has the built-in tools and the reduced aos tool set (mcp__aos_sub__*), not the main agent's aos tools (mcp__aos__*).")
SUB_PROMPT = ("You are a general-purpose subagent working for the main agent. Do the task you were given with the tools you have. "
              "Your aos tools are the reduced set named mcp__aos_sub__*; the main agent's own aos tools are not available to you. "
              "When you are done, reply with a concise report of what you did and what you found: that report is all the main agent sees.")
GUARD_REASON = ("aos tools on the server aos belong to the main agent and are not available to subagents. "
                "Subagents of type general-purpose have the reduced set mcp__aos_sub__*; ask the main agent to make this call itself.")


def sub_agents(cfg, ws, stack):
    """--agents 的 JSON：蓋掉 general-purpose——拿掉主 agent 那台（mcp__aos）、內嵌只有它連得到的 aos_sub（aos-mcp 接 tools_sub 那份登記檔；
    同一個工作區與 stack、有宣告 hooks 照帶 --hooks、tools_flags 照插；不帶 --own：這隻自己加減的工具不進子 agent 那台）。"""
    if shutil.which("aos-mcp") is None:
        cli_base.die("CliMissing", "aos-mcp is not on PATH (tools_sub is set; add proto8/cmd/aos-mcp/bin to PATH)")
    args = ["--ws", ws, "--stack", stack] + (["--hooks", cfg["hooks_def"]] if cfg.get("hooks_def") else []) \
        + cfg.get("tools_flags", []) + [cfg["sub_registry"]]
    return {SUB_AGENT: {"description": SUB_DESCRIPTION, "prompt": SUB_PROMPT, "disallowedTools": ["mcp__aos"],
                        "mcpServers": [{SUB_SERVER: {"command": "aos-mcp", "args": args}}]}}


def guard_hooks(cfg):
    """有 tools_sub 又有主 agent 那台＝claude 的 PreToolUse hook 表（給 --settings 的 hooks 併進去）；否則 {}。
    general-purpose 以外的子 agent 類型還看得到 mcp__aos__*，叫的時候由 guard_main 擋。"""
    if not (cfg.get("sub_registry") and cfg.get("registry")):
        return {}
    cmd = " ".join(shlex.quote(a) for a in (sys.executable, SELF, "guard"))
    return {"PreToolUse": [{"matcher": "mcp__aos__.*", "hooks": [{"type": "command", "command": cmd}]}]}


def guard_main():
    """claude 的 PreToolUse hook：stdin 一份 hook JSON。有 agent_id＝子 agent 叫的＝印 deny；主對話叫的＝什麼都不印（照原本的權限走）。
    讀不懂輸入＝也 deny（擋錯只少一次工具呼叫，放錯就是子 agent 用到主 agent 那台）。一律退 0。"""
    try:
        sub = bool(json.loads(sys.stdin.read()).get("agent_id"))
    except (ValueError, AttributeError, OSError):
        sub = True
    if sub:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": GUARD_REASON}}))


def _aos_server(cfg, ws, stack, reg):
    """aos 自己那台：codex＝-c 旗標的串列；claude＝mcp.json 裡 aos 那格（{"aos": …}）。"""
    if cfg.get("own_registry"):                       # aos-mcp 自己挑：--own 那份在就用它，不在（reset 刪了）＝回定義那份
        reg = cfg["def_registry"]
    if not os.path.isfile(reg):                       # load_cfg 之後才被刪掉
        cli_base.die("ToolsMissing", "registry file not found: %s" % reg)
    if shutil.which("aos-mcp") is None:
        cli_base.die("CliMissing", "aos-mcp is not on PATH (tools are attached; add proto8/cmd/aos-mcp/bin to PATH)")
    args = ["--ws", ws, "--stack", stack] + (["--hooks", cfg["hooks_def"]] if cfg.get("hooks_def") else []) \
        + (["--own", os.path.abspath(cfg["own_registry"])] if cfg.get("own_registry") else []) \
        + cfg.get("tools_flags", []) + [reg]
    if cfg["kind"] == "codex":                           # JSON 字串與字串陣列同時是合法的 TOML（-c 的值照 TOML 解）
        return ["-c", "mcp_servers.aos.command=" + json.dumps("aos-mcp"), "-c", "mcp_servers.aos.args=" + json.dumps(args),
                "-c", "mcp_servers.aos.env=" + _server_mod().toml_table(mcp_env(ws, stack)),
                "-c", "mcp_servers.aos.default_tools_approval_mode=" + json.dumps("approve")]
    return {"aos": {"command": "aos-mcp", "args": args}}
