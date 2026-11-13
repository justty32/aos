# cli_cfg.py - cli_session 的設定：讀與驗工具資料夾的 cli.json、llm.json 疊 model、system 附加旗標、tools／tools_sub 登記檔
import json, os, sys

if __package__:
    from .agent_files import declared_files
    from . import cli_base
    from .cli_base import RESEED_BYTES, _lib, tool_io
    from .cli_mcp import external_servers
else:
    from agent_files import declared_files
    import cli_base
    from cli_base import RESEED_BYTES, _lib, tool_io
    from cli_mcp import external_servers


# aos 每次起 CLI 自己會加、cli.json 的 flags／print_flags 不准再寫的旗標（寫了＝CfgBad：在認領信之前就停，信留在 queue、不進冷卻）。
# codex exec 的這幾個不准重複（寫第二次 codex 退 2：cannot be used multiple times）；claude 的是輸出格式與接哪段對話，重寫會解不開輸出或接錯對話。
# 有宣告才加的（--mcp-config、--allowedTools、--append-system-prompt-file、--agents、codex 的 -c …）可重複，不擋。
# claude 的 --settings 不能重複（11-13 實測：命令列上兩個 --settings 只有最後一個算數，前一個整個不見、沒有提醒；aos 自己那個接在後面），
# 所以也擋；要帶 CLI 自己的設定（hooks、permissions…）寫 cli.json 的 settings 鍵，aos 併進它那一個（cli_settings、cli_mcp.settings_argv）。
AOS_FLAGS = {"codex": ("--skip-git-repo-check", "--json", "-o", "--output-last-message"),
             "claude": ("-p", "--print", "--output-format", "--session-id", "--resume", "-r", "--continue", "-c", "--settings")}


def reserved_flags(kind, flags):
    """flags 裡 aos 自己會加的那幾個（含 --旗標=值 的寫法），排序去重；沒有＝[]。"""
    mine = AOS_FLAGS[kind]
    return sorted({a.split("=", 1)[0] if a.startswith("--") else a for a in flags} & set(mine))


def load_cfg(tool_dir):
    path = os.path.join(tool_dir, "cli.json")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cli_base.die("CfgMissing", path)
    except (OSError, ValueError) as e:
        cli_base.die("CfgBad", "%s: %s" % (tool_io.place(path), tool_io.os_reason(e)))
    if not isinstance(cfg, dict) or cfg.get("kind") not in ("claude", "codex"):
        cli_base.die("CfgBad", "%s: kind must be claude or codex" % path)
    for k in ("flags", "print_flags", "tools_flags"):
        if not isinstance(cfg.get(k, []), list) or not all(isinstance(a, str) for a in cfg.get(k, [])):
            cli_base.die("CfgBad", "%s: %s must be an array of strings" % (path, k))
    for k in ("flags", "print_flags"):
        mine = reserved_flags(cfg["kind"], cfg.get(k, []))
        if mine:
            hint = " (for --settings: put the settings in the settings key of cli.json; aos merges them into its own)" if "--settings" in mine else ""
            cli_base.die("CfgBad", "%s: %s has %s, which aos adds itself; remove it%s" % (path, k, ", ".join(mine), hint))
    rb = cfg.get("reseed_bytes", RESEED_BYTES)                     # 11-10 two-machines 05：開新對話時接在題目前的紀錄上限
    if not isinstance(rb, int) or isinstance(rb, bool) or rb < 0:
        cli_base.die("CfgBad", "%s: reseed_bytes must be a non-negative integer" % path)
    try:
        files = declared_files(tool_dir)
    except ValueError as e:
        cli_base.die("CfgBad", str(e))
    cfg["registry"] = registry(cfg, tool_dir, path, files)
    cfg["sub_registry"] = sub_registry(cfg, tool_dir, path)        # 11-12 eca-task-subagent：cli.json 的 tools_sub
    cfg["hooks_def"] = os.path.abspath(tool_dir) if files.get("hooks") else None   # 11-10 hook：宣告了 hooks＝aos-mcp 帶 --hooks
    cfg["external"] = external_servers(cfg, tool_dir, path)        # 11-12 external-mcp 步 1：cli.json 的 mcp_servers
    cfg["cli_settings"] = cli_settings(cfg, tool_dir, path)        # 11-13 第 1 題乙：cli.json 的 settings（定義自帶的 CLI 設定）
    cfg["cli_def"] = os.path.abspath(tool_dir)
    stack_copies(cfg, tool_dir, files)
    return cfg


def cli_settings(cfg, tool_dir, path):
    """cli.json 選填 settings（使用者 11-13「都按照建議」＝ops-agent-six-suggestions 第 1 題乙）：這份定義自帶的 Claude Code 設定
    （hooks、permissions…，CLI 的 settings.json 那種物件），規矩跟著定義走、不必放工作區。物件＝就是它；字串＝一個 JSON 檔的路徑
    （相對從 cli.json 的資料夾算），每次 load_cfg（每題）重讀。沒寫＝None。只有 claude 身認（codex 身寫了＝CfgBad）。
    形狀不對（不是物件、檔讀不了、hooks 不是「事件名: 陣列」）＝CfgBad。內容不驗（CLI 自己的格式），照樣交給 CLI。"""
    if "settings" not in cfg:
        return None
    if cfg["kind"] != "claude":
        cli_base.die("CfgBad", "%s: settings is only for kind claude" % path)
    s = cfg["settings"]
    if isinstance(s, str) and s:
        file = os.path.normpath(os.path.join(os.path.abspath(tool_dir), s))
        try:
            with open(file, encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, ValueError) as e:
            cli_base.die("CfgBad", "%s: settings names %s, which cannot be read as JSON: %s" % (path, tool_io.place(file), tool_io.os_reason(e)))
    if not isinstance(s, dict):
        cli_base.die("CfgBad", "%s: settings must be an object (Claude Code settings) or the path of a JSON file holding one" % path)
    hooks = s.get("hooks", {})
    if not isinstance(hooks, dict) or not all(isinstance(v, list) for v in hooks.values()):
        cli_base.die("CfgBad", "%s: hooks in settings must be an object of EVENT: [entries]" % path)
    return s


def read_llm(path):
    """llm.json：一層物件；不在＝{}。"""
    try:
        with open(path, encoding="utf-8") as f:
            llm = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        cli_base.die("CfgBad", "%s: %s" % (tool_io.place(path), tool_io.os_reason(e)))
    if not isinstance(llm, dict):
        cli_base.die("CfgBad", "%s: must be a flat object" % path)
    return llm


def stack_copies(cfg, tool_dir, files):
    """子介面 tools／llm 依 interfaces.json 宣告的相對檔名讀 stack 覆蓋；沒有宣告就不讀 stack。
    cli.json 明寫 tools 時照它、不看 stack 那份；未宣告時定義的預設登記檔仍是同層 tools.json。
    腦設定：定義宣告的 llm（沒宣告時仍可用同層 llm.json）疊 stack 宣告那份；
    有 model＝flags 的 --model 換成它（沒有就加在尾）。每次 load_cfg（每題）重讀＝下一題生效。"""
    stack = os.environ.get("AOS_STACK")
    llm = read_llm(os.path.join(tool_dir, files.get("llm", "llm.json")))
    if stack:
        rel = files.get("tools")
        copy = os.path.join(stack, rel) if rel else None
        if "tools" not in cfg and copy and cfg.get("registry"):
            cfg["own_registry"], cfg["def_registry"] = copy, cfg["registry"]   # 11-10 深夜 tools-def（「3.同一輪就生效」）：aos-mcp --own 每次重看，第一次 self_tools add 才建也看得到
        if "tools" not in cfg and copy and os.path.isfile(copy):
            cfg["registry"] = copy                   # 11-10 aos-tools-cli 步 4：這隻自己那份（"$override" 指回定義那份）在就用它
        if "llm" in files:
            llm.update(read_llm(os.path.join(stack, files["llm"])))
    model = llm.get("model")
    if "model" in llm and (not isinstance(model, str) or not model):
        cli_base.die("CfgBad", "model in llm.json must be a non-empty string (same as agent-fsm's brain.py), not %s" % json.dumps(model))
    if model:
        flags = list(cfg.get("flags", []))
        if "--model" in flags[:-1]:
            flags[flags.index("--model") + 1] = model
        else:
            flags += ["--model", model]
        cfg["flags"] = flags
    cfg["system"] = system_file(tool_dir, files, stack)


def system_file(tool_dir, files, stack):
    """宣告了 system（11-11 self-system，使用者裁「fsm 取代、eca 附加」）＝{"file": 生效那份的絕對路徑或 None（都不在或空）}：
    stack 那份在就整份用它（aos-agent system set 寫的），否則定義那份；沒宣告＝None（不碰 CLI 的 system）。每題重讀＝下一輪生效。"""
    rel = files.get("system")
    if not rel:
        return None
    own = os.path.join(stack, rel) if stack else None
    path = own if own and os.path.isfile(own) else os.path.join(tool_dir, rel)
    try:
        empty = os.path.getsize(path) == 0
    except OSError:
        return {"file": None}
    return {"file": None if empty else os.path.abspath(path)}


def system_argv(cfg):
    """把生效的 system 文字附加給 CLI（不用整份取代的 --system-prompt）：
    claude＝--append-system-prompt-file 檔；宣告了就一律加 --system-prompt-snapshot off（claude 預設把第一輪的 system 記下來、--resume 時照舊送，
    off 才會每輪重讀，改了、reset 了下一輪都跟著變；代價是 claude 自己的動態段落〔日期等〕變了也會讓快取失效）。
    codex＝-c developer_instructions=文字（附加成 developer 訊息；值照 TOML 寫，JSON 字串是合法的 TOML 字串）。沒宣告＝[]。"""
    sysd = cfg.get("system")
    if sysd is None:
        return []
    path = sysd.get("file")
    if cfg["kind"] == "claude":
        return ["--system-prompt-snapshot", "off"] + (["--append-system-prompt-file", path] if path else [])
    if not path:
        return []
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeError) as e:
        cli_base.die("CfgBad", "cannot read the system text %s: %s" % (tool_io.place(path), tool_io.os_reason(e)))
    return ["-c", "developer_instructions=" + json.dumps(text, ensure_ascii=False)]


def _named_registry(cfg, key, base, path):
    """cli.json 的 key（tools／tools_sub）指的登記檔（絕對路徑）：字串＝相對從 cli.json 的資料夾算；物件＝指示詞，每次讀才解、不寫回
    （例 {"$env": "X", "$path": "tools.json"}，11-10 two-machines TC），解完照字串的規則。不是檔＝ToolsMissing。"""
    tools = cfg[key]
    if isinstance(tools, dict):
        sys.path.insert(0, _lib)      # directive_value 跟 tool_io 同在 lib/（直接執行此檔時 lib 不在 sys.path）
        try:
            from directive_value import resolve_path
        finally:
            sys.path.pop(0)
        try:
            tools = resolve_path(tools, path, key)
        except tool_io.Error as e:
            cli_base.die(e.code, str(e))
    if not isinstance(tools, str) or not tools:
        cli_base.die("CfgBad", "%s: %s must be the path of a registry file (a non-empty string)" % (path, key))
    reg = os.path.normpath(os.path.join(base, tools))
    if not os.path.isfile(reg):
        cli_base.die("ToolsMissing", "%s: registry file named by %s not found: %s" % (path, key, reg))
    return reg


def sub_registry(cfg, tool_dir, path):
    """子 agent 那台的登記檔（絕對路徑）；cli.json 沒寫 tools_sub＝None（11-12 eca-task-subagent）。只有 claude 身認：
    codex 身寫了、或 flags 裡自己又寫了 --agents＝CfgBad（寫什麼就做什麼，不靜靜吞掉）。"""
    if "tools_sub" not in cfg:
        return None
    if cfg["kind"] != "claude":
        cli_base.die("CfgBad", "%s: tools_sub is only for kind claude" % path)
    if "--agents" in cfg.get("flags", []) + cfg.get("print_flags", []):
        cli_base.die("CfgBad", "%s: tools_sub and --agents in flags cannot be used together (tools_sub adds its own --agents)" % path)
    return _named_registry(cfg, "tools_sub", os.path.abspath(tool_dir), path)


def registry(cfg, tool_dir, path, files):
    """這份定義的 aos-tools 登記檔（絕對路徑）；沒有＝None（11-03 eca-tools）。
    tools 有寫＝它（相對路徑從 cli.json 的資料夾算），不是檔＝ToolsMissing；沒寫＝interfaces.json 宣告的 tools，未宣告才取同層 tools.json。
    給了 tools_flags 卻沒有登記檔＝CfgBad（寫什麼就做什麼，不靜靜吞掉）。"""
    base = os.path.abspath(tool_dir)
    if "tools" in cfg:
        return _named_registry(cfg, "tools", base, path)
    reg = os.path.join(base, files.get("tools", "tools.json"))
    if os.path.isfile(reg):
        return reg
    if "tools_flags" in cfg:
        cli_base.die("CfgBad", "%s: tools_flags given but no registry file (no tools, and no default registry alongside)" % path)
    return None
