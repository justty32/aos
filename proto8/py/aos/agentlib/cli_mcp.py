# cli_mcp.py - cli_session 接 MCP：aos-mcp 那台的旗標（claude 的 mcp.json／codex 的 -c；pi 用同一份參數，見 cli_pi）、外部 MCP server、tools_sub 子 agent 那台與 guard hook
import json, os, shlex, shutil, sys

from aos.agentlib import cli_base
from aos.agentlib.cli_base import SELF, tool_io


def _server_mod():
    from aos import mcp_server_file
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
                from aos.directive_value import resolve_path
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


CLAUDE_SCOPES = ("user", "project", "local")      # cli.json 的 claude_mcp 認的範圍（照 claude mcp add --scope 的名字）


def claude_config_file():
    """這次起的 claude 讀的那份 .claude.json：$CLAUDE_CONFIG_DIR/.claude.json，沒設＝~/.claude.json（Claude Code 自己的規則）。"""
    d = os.environ.get("CLAUDE_CONFIG_DIR", "")
    return os.path.join(os.path.expanduser(d) if d else os.path.expanduser("~"), ".claude.json")


def _project_entry(projects, ws):
    """projects 裡這個 cwd 那格：claude 照完全相同的 cwd 認（子資料夾不算），先比真實路徑再比原字。"""
    if not isinstance(projects, dict):
        return {}
    for key in (os.path.realpath(ws), os.path.abspath(ws)):
        if isinstance(projects.get(key), dict):
            return projects[key]
    return {}


def claude_own(cfg, ws, taken=()):
    """cli.json 選填 claude_mcp（11-24，使用者：aos 起的 Claude Code 要用得到使用者自己設的 MCP；「總之把事情解決」）：
    範本帶 --strict-mcp-config（不讓工作區的 .mcp.json 不問就連），所以 claude 自己設定裡的 server 要由 aos 抄進小格的 mcp.json 才接得到。
    範圍照 claude mcp add --scope：user＝那份 .claude.json 最外層的 mcpServers；local＝projects[cwd].mcpServers（cwd＝ws，要完全相同）；
    project＝ws 的 .mcp.json 裡、那份 projects[cwd] 的 enabledMcpjsonServers 列過的（人在 claude 裡核准過的；
    enableAllProjectMcpServers 是 true＝全部；disabledMcpjsonServers 列的不要）。後面的範圍蓋前面的同名（claude 的順序：local＞project＞user）。
    名字是 aos、aos_sub 或 taken 裡已有的（cli.json 的 mcp_servers）＝warning 跳過。檔不在＝沒有；讀不懂＝warning、沒有。
    回 {名: claude 那格的設定（原樣）}。"""
    scopes = cfg.get("claude_mcp") or []
    if not scopes:
        return {}
    path = claude_config_file()
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        cli_base.warn("claude_mcp: cannot read %s, no MCP servers taken from it: %s" % (path, tool_io.os_reason(e)))
        return {}
    if not isinstance(doc, dict):
        cli_base.warn("claude_mcp: %s is not a JSON object, no MCP servers taken from it" % path)
        return {}
    project = _project_entry(doc.get("projects"), ws)
    found = {}
    for scope in CLAUDE_SCOPES:
        if scope not in scopes:
            continue
        if scope == "user":
            got = doc.get("mcpServers")
        elif scope == "local":
            got = project.get("mcpServers")
        else:
            got = {}
            try:
                with open(os.path.join(ws, ".mcp.json"), encoding="utf-8") as f:
                    listed = json.load(f).get("mcpServers")
            except FileNotFoundError:
                listed = None
            except (OSError, ValueError, AttributeError) as e:
                cli_base.warn("claude_mcp: cannot read %s: %s" % (os.path.join(ws, ".mcp.json"), e))
                listed = None
            if isinstance(listed, dict):
                ok = project.get("enabledMcpjsonServers") if isinstance(project.get("enabledMcpjsonServers"), list) else []
                off = project.get("disabledMcpjsonServers") if isinstance(project.get("disabledMcpjsonServers"), list) else []
                every = project.get("enableAllProjectMcpServers") is True
                got = {n: v for n, v in listed.items() if (every or n in ok) and n not in off}
        if not isinstance(got, dict):
            continue
        for name, entry in got.items():
            if not isinstance(entry, dict) or not name:
                cli_base.warn("claude_mcp: %s server %r in %s is not an object, skipped" % (scope, name, path))
                continue
            found[name] = entry
    out = {}
    for name, entry in found.items():
        if name in ("aos", SUB_SERVER) or name in taken:
            cli_base.warn("claude_mcp: MCP server %s skipped: the name is already used by aos or a server file in mcp_servers" % name)
            continue
        out[name] = entry
    return out


def stdio_ready(servers):
    """起 CLI 前先看每台 stdio server 起不起得來：CLI 自己接的 server 起不來，CLI 只是少了那台的工具、不說原因，aos 看不到。
    照 aos-mcp-launch 的讀法解出指令與環境（mcp_server_file.stdio_launch：指示詞、env、env_file）；解不開、指令找不到或不能執行
    ＝warning 跳過那台、其他照接（X8）。只看起不起得來；起來之後才壞的（握手失敗、中途死掉）只有 CLI 知道。回留下的 servers。"""
    msf, kept = _server_mod(), []
    for s in servers:
        if s["transport"] == "stdio":
            try:
                argv, env, _ = msf.stdio_launch(s["file"])
            except tool_io.Error as err:
                cli_base.warn("external MCP server %s skipped: %s %s" % (s["name"], err.code, err))
                continue
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
        cli_base.die("CliMissing", "aos-mcp-launch is not on PATH (an stdio MCP server is listed in mcp_servers; add proto8/bin to PATH)")
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
    return [sys.executable, os.path.realpath(_server_mod().__file__), "--exec", json.dumps(spec), "--"] + argv


# codex 起 MCP server 不帶父程序的環境變數（11-11 實測：aos-mcp 少了 AOS_HOME 解不開範本登記檔的指示詞、起不來，腦看不到任何 aos 工具），
# 所以明寫帶進 mcp_servers.aos.env。帶哪些＝aos-mcp、aos-tools 與 lib 工具實際讀的（_tooldef 的 env、程式裡讀的）；
# AOS_CD／AOS_ENTRY／AOS_AGENT 是每支程序自己的，不帶。使用者 11-11 選項框裁「修」。
MCP_ENV = ("AOS_HOME", "AOS_DAEMON", "AOS_CLOCK", "AOS_CLOCK_INTERVAL", "AOS_LLM_KERNEL", "AOS_KERNEL",
           "AOS_LINUX_USER_STACK")                # 11-11 舊 do_task 的 AOS_DO_TASK_DEPTH／AOS_DO_TASK_FROM 隨它拿掉


# 人開的畫面（aos-agent open）是從開畫面那個人的殼起的：殼裡的 MCP_ENV（AOS_CLOCK、AOS_KERNEL、AOS_LLM_KERNEL…）可能沒有或不一樣，
# 畫面裡的 CLI 與它帶起來的 aos-mcp 就跟 loop 那邊（daemon 底下）看到的世界不同（11-13 ops-agent-six-suggestions 第 6 點的 bug）。
# 收法：loop 那邊每次把自己手上的 MCP_ENV 記進小格的 env.json（note_env；aos-eca-turn 每一圈、ask 每一題），
# 開畫面時照它蓋（screen_env；cli_screen.start）。還沒記過（畫面比 loop 先開）＝照舊用開畫面的殼、提醒一行。
ENV_FILE = "env.json"


def note_env(cell):
    """把這個行程手上的 MCP_ENV（有設、非空的）記進小格的 env.json；跟上次一樣就不寫。寫不成不擋正事。"""
    text = json.dumps({k: os.environ[k] for k in MCP_ENV if os.environ.get(k)}, ensure_ascii=False, sort_keys=True)
    try:
        if cell.read(ENV_FILE) != text:
            cell.write(ENV_FILE, text + "\n")
    except (OSError, UnicodeError):
        pass


def noted_env(cell):
    """小格記的那份 {變數名: 值}；沒記過或讀不懂＝None。只認 MCP_ENV 裡的名字、字串值。"""
    try:
        env = json.loads(cell.read(ENV_FILE) or "null")
    except (OSError, ValueError):
        return None
    if not isinstance(env, dict):
        return None
    return {k: v for k, v in env.items() if k in MCP_ENV and isinstance(v, str) and v}


def screen_env(cfg, cell):
    """開畫面時要用的整份環境（給 cli_screen.start 暫時換上）：自己的 os.environ，MCP_ENV 那幾個照小格記的那份——有記的設成那個值、
    沒記的拿掉（跟 loop 那邊一致）；沒記過＝不動、提醒一行。定義帶了 settings＝再加 AOS_CLI_DEF（定義資料夾，給它的 hook 指令找自己的檔）。"""
    env = dict(os.environ)
    noted = noted_env(cell)
    if noted is None:
        cli_base.warn("no %s in the cell yet (the agent's loop has not run a turn); the screen takes %s from this shell"
                      % (ENV_FILE, "AOS_CLOCK, AOS_KERNEL, AOS_LLM_KERNEL"))
    else:
        for k in MCP_ENV:
            env.pop(k, None)
        env.update(noted)
    env.update(settings_env(cfg))
    return env


def settings_env(cfg):
    """定義帶了 settings＝{"AOS_CLI_DEF": 定義資料夾的絕對路徑}（只給 CLI 行程；hook 指令寫 "$AOS_CLI_DEF/…" 找定義裡的檔）；沒帶＝{}。"""
    return {"AOS_CLI_DEF": cfg["cli_def"]} if cfg.get("cli_settings") is not None else {}


def settings_argv(cfg, mine):
    """這次要給 claude 的 --settings（命令列上只會有這一個：CLI 只認最後一個，flags 裡自己寫＝CfgBad）。mine＝aos 自己要加的那份
    （畫面：三個 hook＋收件口設定＋guard；非互動：guard，沒有＝{}）。定義沒帶 settings＝照舊（mine 空＝[]，否則就是 mine）。
    定義帶了（cfg["cli_settings"]，11-13 第 1 題乙）＝以它為底併上 mine：hooks 每個事件的表接在一起（定義的在前、aos 的在後，兩邊都會跑）；
    其他頂層鍵定義有寫的照定義（寫什麼就做什麼）、沒寫的用 aos 的。"""
    own = cfg.get("cli_settings")
    if own is None:
        return ["--settings", json.dumps(mine)] if mine else []
    out = dict(own)
    hooks = {event: list(entries) for event, entries in (own.get("hooks") or {}).items()}
    for event, entries in (mine.get("hooks") or {}).items():
        hooks[event] = hooks.get(event, []) + list(entries)
    for k, v in mine.items():
        if k != "hooks":
            out.setdefault(k, v)
    if hooks:
        out["hooks"] = hooks
    return ["--settings", json.dumps(out, ensure_ascii=False)]


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
    own = claude_own(cfg, ws, {s["name"] for s in external}) if cfg["kind"] == "claude" else {}
    if not reg and not external and not sub and not own:
        return []
    servers = {}
    if reg:
        servers = _aos_server(cfg, ws, stack, reg)
        if cfg["kind"] == "codex":
            return servers
    msf = _server_mod() if external else None
    entries, allowed, denied = msf.claude_entries(external, _launcher(external)) if external else ({}, [], [])
    servers.update(entries)
    servers.update(own)                            # claude 自己設定裡的（claude_mcp）：可能帶金鑰，檔只給自己讀
    try:
        cell.write("mcp.json", json.dumps({"mcpServers": servers}, ensure_ascii=False) + "\n")
        if own:
            os.chmod(cell.file("mcp.json"), 0o600)
    except OSError as e:
        cli_base.die("WriteFailed", "cannot write %s: %s" % (tool_io.place(cell.file("mcp.json")), tool_io.os_reason(e)))
    allow = (["mcp__aos"] if reg else []) + (["mcp__" + SUB_SERVER] if sub else []) + allowed + ["mcp__" + n for n in own]
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
        cli_base.die("CliMissing", "aos-mcp is not on PATH (tools_sub is set; add proto8/bin to PATH)")
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


def _aos_server_args(cfg, ws, stack, reg=None):
    """aos-mcp 那台的參數（三身共用；pi 身的外掛也用，cli_pi.extension_argv）。登記檔不在、aos-mcp 不在 PATH＝die。"""
    reg = reg or cfg["registry"]
    if cfg.get("own_registry"):                       # aos-mcp 自己挑：--own 那份在就用它，不在（reset 刪了）＝回定義那份
        reg = cfg["def_registry"]
    if not os.path.isfile(reg):                       # load_cfg 之後才被刪掉
        cli_base.die("ToolsMissing", "registry file not found: %s" % reg)
    if shutil.which("aos-mcp") is None:
        cli_base.die("CliMissing", "aos-mcp is not on PATH (tools are attached; add proto8/bin to PATH)")
    return ["--ws", ws, "--stack", stack] + (["--hooks", cfg["hooks_def"]] if cfg.get("hooks_def") else []) \
        + (["--own", os.path.abspath(cfg["own_registry"])] if cfg.get("own_registry") else []) \
        + cfg.get("tools_flags", []) + [reg]


def _aos_server(cfg, ws, stack, reg):
    """aos 自己那台：codex＝-c 旗標的串列；claude＝mcp.json 裡 aos 那格（{"aos": …}）。"""
    args = _aos_server_args(cfg, ws, stack, reg)
    if cfg["kind"] == "codex":                           # JSON 字串與字串陣列同時是合法的 TOML（-c 的值照 TOML 解）
        return ["-c", "mcp_servers.aos.command=" + json.dumps("aos-mcp"), "-c", "mcp_servers.aos.args=" + json.dumps(args),
                "-c", "mcp_servers.aos.env=" + _server_mod().toml_table(mcp_env(ws, stack)),
                "-c", "mcp_servers.aos.default_tools_approval_mode=" + json.dumps("approve")]
    return {"aos": {"command": "aos-mcp", "args": args}}
