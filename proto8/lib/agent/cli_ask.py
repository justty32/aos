# cli_ask.py - cli_session 問一輪：畫面開著從 tmux 送字（live、type_line）、ask 挑兩條路、aos-eca-turn --one 的 call_main
import fcntl, json, os, re, shlex, signal, sys, time

if __package__:
    from . import cli_base
    from .cli_base import RESEED_BYTES, SCREEN_RESEED_BYTES, TMUX_SESSION
    from .cli_cell import Cell, link_transcript, note_cell, session_here
    from .cli_cfg import load_cfg
    from .cli_print import print_claude, print_codex
else:
    import cli_base
    from cli_base import RESEED_BYTES, SCREEN_RESEED_BYTES, TMUX_SESSION
    from cli_cell import Cell, link_transcript, note_cell, session_here
    from cli_cfg import load_cfg
    from cli_print import print_claude, print_codex


# ---------------------------------------------------------------- 從畫面送字（畫面開著）

# claude 在沒信任過的資料夾開畫面，會先停在「信不信任這個資料夾」的選單，預設選項是 No, exit：這時貼題目＋Enter＝選了離開、畫面關掉
# （11-10 深夜使用者選「aos 偵測後報錯」；實拍 2026-11 claude 的選單：「Quick safety check: Is this a project you created or one you trust?」
#   底下「❯ No, exit」「Yes, I trust this folder」「Enter to confirm · Esc to cancel」）。認法要耐得住小改字：畫面最後 TRUST_TAIL 行裡
#   有 trust 這個字，而且有一行像選項（前面可有 ❯／›／> 與「1.」）寫著 no, exit 或 yes … trust；認不出＝照舊貼。codex 實拍沒這種選單，不做。
TRUST_TAIL = 30
_TRUST_OPTION = re.compile(r"^\s*(?:[❯›>»]\s*)?(?:\d+[.)]\s*)?(?:no\b[^\n]{0,12}\bexit\b|yes\b[^\n]{0,40}\btrust)", re.I | re.M)


def trust_prompt(screen):
    """畫面（capture-pane 的字）是不是停在 claude 的信任資料夾選單。"""
    tail = "\n".join([l for l in (screen or "").splitlines() if l.strip()][-TRUST_TAIL:])
    return "trust" in tail.lower() and bool(_TRUST_OPTION.search(tail))


def live(cfg, cell, prompt, on_busy="yield", handed=None):
    """on_busy＝yield（預設）：有人接在畫面上、或 busy.txt 在＝SessionBad；answer（10-31 eca --on-busy）：有人接著照樣貼，
    busy.txt 在就等它消失再貼——等它跟等回答共用 timeout_ms 的期限，逾時 ReplyMissing。貼上、按 Enter 之後叫 handed（交出去了，11-03）。"""
    deadline = time.time() + cfg.get("timeout_ms", 600000) / 1000
    if on_busy == "yield":
        who = cell.clients()
        if who:
            cli_base.die("SessionBad", "someone is attached to the screen (%s); call again after they detach" % ", ".join(who))
        if os.path.exists(cell.file("busy.txt")):
            cli_base.die("SessionBad", "a turn is running on the screen (sent, not finished yet); call again after it finishes")
    while os.path.exists(cell.file("busy.txt")) and time.time() < deadline:
        if not cell.alive():
            cli_base.die("CliFailed", "the screen closed before the turn finished")
        time.sleep(0.2)
    if os.path.exists(cell.file("busy.txt")):                # 等到期限還在跑：不貼，免得逾時了還打進畫面
        cli_base.die("ReplyMissing", "the turn on the screen did not finish within %d s; not sent (attach to look)" % (cfg.get("timeout_ms", 600000) // 1000))
    if cfg.get("kind") == "claude" and trust_prompt(cell.tmux("capture-pane", "-p", "-t", TMUX_SESSION).stdout):
        ws = os.path.normpath(os.path.join(cell.path, cell.read("ws.txt") or "."))
        cli_base.die("TrustMissing", "claude on the screen is waiting at its trust-this-folder prompt for %s; nothing was typed. "
            "Choose yourself: attach to the screen (aos-agent open), or run claude there once and pick trust: cd %s && claude"
            % (ws, shlex.quote(ws)))
    seen = len(cell.turns())
    r = cell.tmux("load-buffer", "-b", "aos", "-", input=prompt)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)                         # tmux 自己的話原樣透出（R10）
        cli_base.die("CliFailed", "tmux load-buffer exited %d" % r.returncode)
    cell.tmux("paste-buffer", "-p", "-d", "-b", "aos", "-t", TMUX_SESSION)   # -p：程式要的話包成 bracketed paste，多行不會半路送出
    time.sleep(0.3)
    cell.tmux("send-keys", "-t", TMUX_SESSION, "Enter")
    if handed:
        handed()
    while time.time() < deadline:
        turns = cell.turns()
        if len(turns) > seen:
            return turns[-1].get("text") or ""
        if not cell.alive():
            cli_base.die("CliFailed", "the screen closed before the turn finished")
        time.sleep(0.2)
    cli_base.die("ReplyMissing", "no answer %d s after sending (may be stuck on a permission or trust prompt; attach to look)"
        % (cfg.get("timeout_ms", 600000) // 1000))


def type_line(cell, text):
    """在開著的畫面上打一行字再按 Enter（跟人打的一樣，11-12 eca-slash Q2「幫我貼進去」：say 送的 /clear、/compact）；不等回答。"""
    cell.tmux("send-keys", "-t", TMUX_SESSION, "-l", text)
    time.sleep(0.5)                                          # 11-12 實測：slash 選單要一下才跟上，太快按 Enter 會被吃掉
    cell.tmux("send-keys", "-t", TMUX_SESSION, "Enter")


def ask(cfg, cell, tool_dir, ws, stack, prompt, on_busy="yield", handed=None, reseed=None):
    """問 CLI 一句 → 回答文字：記下這格（note_cell）→ 拿格的 lock（拿不到：on_busy＝yield（預設）＝SessionBad、
    answer＝等到拿到，同 open_cell）→ 畫面開著走 live（on_busy 照傳）、沒開走非互動
    → 建 transcripts symlink。lib/agent/agent_tool.py 的 ask_cli 與 aos-eca-turn（含 --one 的 call_main）共用這一段。
    tool_dir＝cli.json 所在的資料夾（工具資料夾或 eca 定義）；ws＝CLI 的 cwd（絕對路徑）；stack＝給 aos-mcp 的 --stack
    （平級形＝那隻 eca 的 $AOS_STACK、工具形＝這格本身；11-03 eca-tools）。handed＝選填、不帶參數的函式：題目交給 CLI 的那一刻叫一次
    （非互動＝CLI 起來、題目寫進去；畫面＝貼上按 Enter），在等回答之前（11-03 aos-eca-turn 在這一刻收信；工具形不給）。錯一律走 die
    （工具形印一行退 1；aos-eca-turn 把 die 換成丟例外）。
    reseed＝選填、reseed(上限 bytes) -> 開場白（整理過的舊紀錄，結尾一個空行；沒紀錄回 ""）：這次是新對話（session.txt 沒有，
    或 session_here 認不出是這台的）就接在題目前面（11-10 two-machines 05；aos-eca-turn 給）。沒給而且是「有舊 id 但不在這台」
    ＝stderr 一行 warning、照樣開新的（工具形）。"""
    note_cell(cell, tool_dir, ws, stack)
    f, ok = cell.lock()
    if not ok:
        if on_busy == "yield":
            cli_base.die("SessionBad", "this conversation is in use (another call, or attach is opening the screen)")
        fcntl.flock(f, fcntl.LOCK_EX)
    with f:
        limit = cfg.get("reseed_bytes", RESEED_BYTES)
        sid = cell.read("session.txt")
        if cell.alive():                                 # 畫面開著＝這台的；session.txt 還沒有＝新對話（hook 第一輪才寫）
            if not sid and reseed:
                prompt = reseed(min(limit, SCREEN_RESEED_BYTES)) + prompt
            text = live(cfg, cell, prompt, on_busy, handed)
        else:
            if sid and not session_here(cfg, cell, ws, sid):
                if not reseed:
                    cli_base.warn("the earlier conversation is not on this machine; starting a new one without its record")
                sid = ""
            if not sid and reseed:
                prompt = reseed(limit) + prompt
            if cfg["kind"] == "claude":
                text = print_claude(cfg, cell, ws, stack, prompt, handed, sid)
            else:
                text = print_codex(cfg, cell, ws, stack, prompt, handed, sid)
        link_transcript(cell, cfg["kind"])               # 工具形也留（方向題 3）
    return text


CALL_HELP = """\
usage: %(name)s < ARGUMENTS.json   (a tool: run it with aos-exec; $AOS_STACK is its cell)
Hand the prompt to the %(name)s CLI and print its answer; the conversation goes on in this
tool's cell (session.txt), and a person can attach to its screen (aos-agent attach).
How the CLI is called (flags, timeout_ms, tools) is in cli.json next to _entry.
If the earlier conversation was started on another machine, in another workspace (claude) or with another
account folder (.session_home in the cell says so), a warning is printed and a new conversation is started.
AOS_WS is required and must be a directory.
Arguments: one JSON object on stdin:
  prompt  string, required
Result on stdout. On error: one line "%(name)s: error: CODE reason" on stderr and stdout, exit 1
(the CLI's own stderr is passed through to stderr).
"""


def call_main(tool_dir, on_busy="yield"):
    """aos-eca-turn --one 入口：stdin {"prompt": "..."} → stdout 回答。tool_dir＝定義資料夾（cli.json 在裡面；名字＝資料夾名）。
    on_busy 照 --on-busy 傳給 ask；lib 的 claude／codex 改由 agent_tool.py 的 ask_cli 呼叫 ask。"""
    cli_base.PROG, cli_base.ECHO = os.path.basename(tool_dir), True   # die 在 cli_base 讀這兩個
    if "--help" in sys.argv[1:]:                         # --help：英文說明印 stdout、退 0（stdio-unify R3）
        sys.stdout.write(CALL_HELP % {"name": cli_base.PROG})
        sys.exit(0)
    signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))   # Ctrl-C：不吐 traceback、退 130（R12）
    cfg = load_cfg(tool_dir)
    stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS")
    if not stack:
        cli_base.die("StackMissing", "AOS_STACK is not set")
    if not ws or not os.path.isdir(ws):
        cli_base.die("WsMissing", "AOS_WS is not set or not a directory")
    ws = os.path.realpath(ws)
    try:
        args = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        cli_base.die("ArgumentsBad", "stdin is not JSON")
    if not isinstance(args, dict) or not isinstance(args.get("prompt"), str) or not args["prompt"].strip():
        cli_base.die("ArgumentsBad", "missing prompt (a non-empty string)")
    cell = Cell(stack)                                   # 工具形：對話在這格本身，aos-mcp 的 stack 也是它（它叫的工具再疊 tools/<名>/）
    text = ask(cfg, cell, os.path.abspath(tool_dir), ws, cell.path, args["prompt"], on_busy)
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
