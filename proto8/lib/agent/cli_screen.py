# cli_screen.py - cli_session 開畫面：tmux 裡起互動的 claude／codex（start）、attach 與叫回畫面（open_cell）
import fcntl, json, os, shlex, sys, time

if __package__:
    from . import cli_a2a, cli_base
    from .cli_base import SELF, TMUX_SESSION
    from .cli_cell import Cell, drop_session, link_transcript, note_cell, session_here
    from .cli_cfg import load_cfg, system_argv
    from .cli_hook import codex_note_compacts
    from .cli_mcp import exec_wrap, external_claude, external_codex, guard_hooks, mcp_argv
else:
    import cli_a2a, cli_base
    from cli_base import SELF, TMUX_SESSION
    from cli_cell import Cell, drop_session, link_transcript, note_cell, session_here
    from cli_cfg import load_cfg, system_argv
    from cli_hook import codex_note_compacts
    from cli_mcp import exec_wrap, external_claude, external_codex, guard_hooks, mcp_argv


# ---------------------------------------------------------------- 開畫面（attach 用）

TMUX_CONF = """# tmux.conf - tmux settings for the screen attach opens (cli_session.py rewrites it each time)
set -g prefix None
unbind-key C-b
bind-key -n 'C-\\' detach-client
bind-key -n 'C-]' detach-client
set -g escape-time 0
set -g focus-events on
set -g status-left ''
set -g status-right ' Ctrl-] detach (the screen stays) | /exit or /quit inside to end '
set -g status-right-length 80
"""


def hook_cmd(kind, cell):
    return [sys.executable, SELF, "hook", kind, cell.path]


def start(cfg, cell, ws, stack):
    """畫面沒開就開一個（在 tmux 裡、背景）；有對話而且是這台的就接著那段，沒有或不是這台的就開新的。有登記檔＝跟非互動同一段接上 aos-mcp（11-03 eca-tools）。"""
    if cell.alive():
        return False
    sid = cell.read("session.txt")
    if sid and not session_here(cfg, cell, ws, sid):     # 不是這台的（換台、搬位置、換帳號資料夾）：清掉、開新的（05）
        drop_session(cell)
        sid = ""
    link_transcript(cell, cfg["kind"])                   # 叫回舊對話：id 早就知道
    if cfg["kind"] == "claude":
        # 11-13：hook 指令最後帶 HOOK_MARK＝這個畫面的 hook 會記收件 socket 與回執；--settings 併進「跨 session 訊息直接收」（cli_a2a）
        cmd = " ".join(shlex.quote(a) for a in hook_cmd("claude", cell) + [cli_a2a.HOOK_MARK])
        hooks = {"hooks": {e: [{"hooks": [{"type": "command", "command": cmd}]}]
                           for e in ("SessionStart", "UserPromptSubmit", "Stop")}}
        hooks.update(cli_a2a.SETTINGS)
        hooks["hooks"].update(guard_hooks(cfg))            # 11-12 eca-task-subagent：子 agent 叫主 agent 那台 aos 的工具＝擋
        ext, _, spec = external_claude(cfg)
        argv = ["claude"] + cfg.get("flags", []) + mcp_argv(cfg, cell, ws, stack, ext) + system_argv(cfg) + ["--settings", json.dumps(hooks)]
        argv += ["--resume", sid] if sid else []
        argv = exec_wrap(argv, spec)
    else:
        if sid:
            codex_note_compacts(cell, sid)                   # Q5：畫面開起來那刻壓過幾次＝基準，之後多出來的才跟上
        ext, _, spec = external_codex(cfg)
        argv = ["codex"] + (["resume", sid] if sid else []) + cfg.get("flags", []) + mcp_argv(cfg, cell, ws, stack) + ext + system_argv(cfg)
        argv += ["-c", "notify=" + json.dumps(hook_cmd("codex", cell))]
        argv = exec_wrap(argv, spec)
    with open(cell.file("tmux.conf"), "w", encoding="utf-8") as f:
        f.write(TMUX_CONF)
    for name in ("busy.txt",):
        if os.path.exists(cell.file(name)):
            os.remove(cell.file(name))
    cli_a2a.forget(cell)                                 # 上一個畫面的收件 socket 與回執不算數；新畫面的 SessionStart hook 會重抄
    try:
        r = cell.tmux("-f", cell.file("tmux.conf"), "new-session", "-d", "-s", TMUX_SESSION,
                      "-x", "160", "-y", "45", "-c", ws, "--", *argv, new=True)
    except FileNotFoundError:
        cli_base.die("TmuxMissing", "tmux is not on PATH")
    if r.returncode != 0:
        sys.stderr.write(r.stderr)                         # tmux 自己的話原樣透出（R10）
        cli_base.die("CliFailed", "tmux new-session exited %d" % r.returncode)
    # 等畫面穩下來（CLI 開機要幾秒；太早貼字會被吃掉）：畫面有字、連續 3 秒沒變、不是停在「Resuming session…」
    # （10-24 實跑：codex 的「Resuming session…」會停 2 秒以上不動，1.5 秒的門檻會太早放行）
    last, stable_since, deadline = None, time.time(), time.time() + 30
    while time.time() < deadline and cell.alive():
        screen = cell.tmux("capture-pane", "-p", "-t", TMUX_SESSION).stdout
        if screen != last:
            last, stable_since = screen, time.time()
        elif screen.strip() and "Resuming session" not in screen and time.time() - stable_since > 3:
            break
        time.sleep(0.25)
    if not cell.alive():
        cli_base.die("CliFailed", "%s exited right after starting (wrong session id?)" % argv[0])
    return True


ATTACH_USAGE = """usage: attach [--ws WS] [-d] [TOOL]
  Attach to TOOL's interactive screen, opening it first if needed.
  -d     open only, do not attach
  no TOOL: list each tool's screen state"""


def attach_main(argv, agent_dir):
    """attach [--ws WS] [-d] [工具名]：接進那個工具的互動畫面；沒開就先開。-d＝只開、不接。沒給工具名＝列出各工具的狀態。"""
    ws, detached, names = os.environ.get("AOS_WS") or ".", False, []
    it = iter(argv)
    for a in it:
        if a == "--ws":
            ws = next(it, None) or cli_base.die("ArgumentsBad", "--ws needs a path")
        elif a.startswith("--ws="):
            ws = a[5:]
        elif a == "-d":
            detached = True
        elif a in ("-h", "--help"):
            print(ATTACH_USAGE)
            return
        elif a.startswith("-"):
            cli_base.die("FlagUnknown", a)
        else:
            names.append(a)
    ws = os.path.abspath(ws)
    if not os.path.isdir(ws):
        cli_base.die("WsMissing", ws)
    stack = os.environ.get("AOS_STACK") or os.path.join(ws, ".stack")
    tools_dir = os.path.join(agent_dir, "tools")
    known = sorted(t for t in os.listdir(tools_dir) if os.path.isfile(os.path.join(tools_dir, t, "cli.json")))
    if not names:
        for t in known:
            cell = Cell(os.path.join(stack, "tools", t), make=False)
            state = "screen open" if cell.alive() else "screen closed"
            if cell.alive() and cell.clients():
                state += ", attached"
            print("%-8s %s | session %s | %s" % (t, state, cell.read("session.txt") or "(none yet)", cell.path))
        return
    if len(names) > 1:
        cli_base.die("ArgumentsBad", "attach one tool at a time")
    if names[0] not in known:
        cli_base.die("ToolUnknown", "%s (known: %s)" % (names[0], ", ".join(known)))
    cell = Cell(os.path.join(stack, "tools", names[0]))
    note_cell(cell, os.path.realpath(os.path.join(tools_dir, names[0])), ws, cell.path)   # 工具形：stack＝這格（同 call_main）
    opened = open_cell(cell)
    if detached:
        print("%s screen %s: %s" % (names[0], "opened" if opened else "already open", cell.sock()))
        return
    cli_base.warn("attaching to %s (Ctrl-\\ detaches, the screen stays; /exit inside to end)" % names[0])
    os.execvp("tmux", ["tmux", "-S", cell.sock(), "attach", "-t", TMUX_SESSION])


def open_cell(cell):
    """畫面沒開就開（有 session.txt 就 --resume 接回那段＝叫回）；tool.txt、ws.txt、stack.txt 都從小格解相對路徑。回 True＝這次才開的。
    stack.txt 只在接了工具時要（沒有＝CellBad；11-03 eca-tools）。"""
    tool_dir, ws, stack = cell.read("tool.txt"), cell.read("ws.txt"), cell.read("stack.txt")
    if not tool_dir or not ws:
        cli_base.die("CellBad", "%s has no tool.txt/ws.txt (not a cell cli_session has used)" % cell.path)
    tool_dir = os.path.normpath(os.path.join(cell.path, tool_dir))
    ws = os.path.normpath(os.path.join(cell.path, ws))
    stack = os.path.normpath(os.path.join(cell.path, stack)) if stack else ""
    cfg = load_cfg(tool_dir)
    if (cfg.get("registry") or cfg.get("sub_registry")) and not stack:
        cli_base.die("CellBad", "%s has no stack.txt (tools are attached; need the stack for aos-mcp)" % cell.path)
    f, ok = cell.lock()
    if not ok:
        cli_base.warn("the agent is using this conversation; waiting for its turn to finish...")
        fcntl.flock(f, fcntl.LOCK_EX)
    with f:
        return start(cfg, cell, ws, stack)
