"""aos-eca-screen - eca 的畫面（介面 aos-agent/screen 的身體；templates/agents/eca-claude/screen/_entry 叫它，thinking 2026-11-04 aos-agent 03/02）。

    aos-eca-screen --eca ECA_DIR open [--detach]   接進畫面（沒開就開、有對話就 --resume）；--detach＝只開不接
    aos-eca-screen --eca ECA_DIR close             收起：關畫面、對話留著（aos-eca-turn 照樣用 --resume 答）；cli.json 無效也能關（一行提醒）
    aos-eca-screen --eca ECA_DIR watch             跟著看非互動那次在做什麼（小格的 live.jsonl），到一次回答結束就走；
                                                   daemon 表上那隻不再 running 或列已移除也走；找不到 daemon／讀不到表照等
    aos-eca-screen --eca ECA_DIR peek /status|/usage  11-16 ok-small：唯讀的 slash 當場回、印 stdout（不經 queue、不寫 history、不拿格的 lock、
                                                   不打字進畫面；agent 正在答題也能回）。字跟 queue 那條一樣（aos.apps.eca.slash 的 slash_status、
                                                   slash_usage：/usage 另起一次 claude -p --no-session-persistence，不碰這隻的對話）。
                                                   使用者 11-16：「全景頁的 /usage、/status 在 agent 忙的時候也直接回，不用排隊」。

命令列（11-05 stdio-unify R6；11-05 隊長代定 D6 把 ECA_DIR 改成子命令前的旗標）：`aos-eca-screen --eca ECA_DIR 子命令 [--detach]`（--eca 必給），
aos_flags.parse（P-44：長旗標與共用短名 -h；子命令前不認得的旗標＝FlagUnknown、子命令不認得＝CommandUnknown、沒給 --eca 或多給位置參數＝ArgumentsBad）。
為什麼是旗標：aos-exec 把呼叫者的參數接在入口 argv 的最後面（`aos-exec 資料夾 參數…`），screen 的入口寫死的部分只能在前面——
`["aos-eca-screen", "--eca", ".."]` ＋ 動作 `open --detach` ＝ `aos-eca-screen --eca .. open --detach`。不用 sh 拼字串（少用 sh）。

人不直接打它：`aos-agent open／close／watch --target 名字` ＝ `aos-exec --ws <ws> --stack <stack> <定義>/screen 動作 [--detach]`
（ECA_DIR 由 screen 的入口寫在前面的 `--eca ..`，見 py/docs/05-commands/05）。
吃 AOS_STACK（那隻的 stack）、AOS_WS（那隻的工作區）；<eca 資料夾>（有 cli.json；相對路徑從 cwd 算）給 kind 與 tools。
身體 11-04 從 aos-eca 的 open／close／watch 原樣搬來（it["cell"]→$AOS_STACK、it["ws"]→$AOS_WS、template→位置參數）。
畫面裡按 Ctrl-]（或 Ctrl-\\）＝跳出、實例不結束。
錯：stderr 一行 `aos-eca-screen: error: 代號 原因`、退 1：ArgumentsBad（沒給 --eca、多給參數、不是 eca 資料夾）、FlagUnknown、CommandUnknown、StackMissing、SessionBad（正在答題時 close）、
加 cli_session 的（CfgBad…）。給人看的狀態句（attaching、watching、watch 不等了）是提醒行 `aos-eca-screen: warning: 句子`（R1、D5）。
`--help`＝英文說明到 stdout、退 0；Ctrl-C＝退 130、不吐 traceback（watch 用 Ctrl-C 離開是正常離開，照舊退 0）。"""
import contextlib, io, json, os, sys, time

from aos import flags as aos_flags  # noqa: E402
from aos.agentlib import cli_base, cli_cell, cli_cfg, cli_screen  # noqa: E402
from aos.apps.eca.slash import slash_status, slash_usage  # noqa: E402  peek 用（11-16 ok-small）
from aos.apps.eca.common import Fail as EcaFail  # noqa: E402
from aos import daemon_ctl as dc  # noqa: E402

PROG = "aos-eca-screen"
dc.PROG = PROG                                   # 坑-64：daemon_ctl 讀窗出錯的提醒行用本程式名（照 aos-agent）
HELP = """aos-eca-screen - open, close or watch an eca's screen

usage: aos-eca-screen --eca ECA_DIR SUBCOMMAND [FLAGS...]
       aos-eca-screen SUBCOMMAND --help

subcommands:
  open    open the screen and attach, or only open with --detach
  close   close the screen while keeping the conversation
  watch   follow the non-interactive run until one answer ends
  peek    answer /status or /usage at once, also while the agent is answering

The screen entry supplies --eca before the action; people normally use aos-agent
open / close / watch / peek. Reads AOS_STACK for the agent's stack and AOS_WS for its workspace.
Screen output goes to the terminal; watch reads live.jsonl from the cell.

flags:
      --eca ECA_DIR   definition folder containing cli.json (required)
  -h, --help          show this help

exit codes: 0 done; 1 error; 130 interrupted (watch leaves with 0 on Ctrl-C).
more: proto8/py/aos/apps/eca/README.md
"""
HELPS = {
    "open": """aos-eca-screen open - open and attach to an eca's screen

usage: aos-eca-screen --eca ECA_DIR open [--detach]

Opens the screen if needed, resuming an existing conversation, then attaches to it.
Reads AOS_STACK and AOS_WS. Ctrl-] (or Ctrl-\\) detaches; the instance keeps running.
With --detach, prints the screen status and socket path without attaching.

flags:
      --eca ECA_DIR   definition folder containing cli.json (before or after open; required)
      --detach        only open the screen; do not attach
  -h, --help          show this help

exit codes: 0 done; 1 error; 130 interrupted.
""",
    "close": """aos-eca-screen close - close the screen and keep the conversation

usage: aos-eca-screen --eca ECA_DIR close

Closes the screen in AOS_STACK; aos-eca-turn can still resume the conversation.
Prints "closed" or "no screen (already closed)". Refuses while the cell is answering.
Works even when cli.json is not valid (one warning line).

flags:
      --eca ECA_DIR   definition folder containing cli.json (before or after close; required)
  -h, --help          show this help

exit codes: 0 closed / already closed; 1 error; 130 interrupted.
""",
    "watch": """aos-eca-screen watch - follow the current non-interactive answer

usage: aos-eca-screen --eca ECA_DIR watch

Prints new live.jsonl events from the cell in AOS_STACK until one answer ends or its
daemon row stops running or is removed. Keeps waiting if the daemon or its table is
unavailable. Ctrl-C leaves normally.

flags:
      --eca ECA_DIR   definition folder containing cli.json (before or after watch; required)
  -h, --help          show this help

exit codes: 0 finished / stopped waiting / Ctrl-C; 1 error.
""",
}
HELPS["peek"] = """aos-eca-screen peek - answer a read-only slash command at once

usage: aos-eca-screen --eca ECA_DIR peek /status|/usage

Prints what the queue would answer for /status or /usage, without the queue: no letter,
nothing in history, no lock on the cell, nothing typed into the screen, so it also works
while the agent is answering. /usage runs a separate claude -p --no-session-persistence
(the agent's conversation is not touched); codex has no usage report outside its screen.
Reads AOS_STACK and AOS_WS.

flags:
      --eca ECA_DIR   definition folder containing cli.json (before or after peek; required)
  -h, --help          show this help

exit codes: 0 printed; 1 error (CliMissing, CliFailed...).
"""
PEEK = ("/status", "/usage")
aos_flags.HELP = HELP


def sub_reason(sub, code, reason):
    """ArgumentsBad 補上子命令的 usage（規則在 aos_flags.with_usage／usage_of）。"""
    return aos_flags.with_usage(HELPS[sub], code, reason)



def die(code, msg):
    aos_flags.die(PROG, code, msg)


def cell_of(eca):
    stack = os.environ.get("AOS_STACK")
    if not stack:
        die("StackMissing", "AOS_STACK is not set (the eca's stack)")
    cfg = cli_cfg.load_cfg(eca)
    return cli_cell.Cell(os.path.join(stack, cfg["kind"])), stack


def cmd_open(eca, opts):
    cell, stack = cell_of(eca)
    ws = os.path.abspath(os.environ.get("AOS_WS") or ".")
    cli_cell.note_cell(cell, eca, ws, stack)          # open_cell 照 tool.txt（定義）、ws.txt、stack.txt（給 aos-mcp）開
    opened = cli_screen.open_cell(cell)                 # 正在答題就等它答完（格的 lock）、等畫面穩
    if opts.get("detach"):
        print("screen %s: %s" % ("opened (resumed with --resume if a conversation exists)" if opened else "already open", cell.sock()))
        return
    env = {k: v for k, v in os.environ.items() if k != "TMUX"}
    aos_flags.warn(PROG, "attaching to %s (Ctrl-] detaches; the instance keeps running)" % ws)
    os.execvpe("tmux", ["tmux", "-S", cell.sock(), "attach", "-t", cli_base.TMUX_SESSION], env)


def kind_for_close(eca):
    # load_cfg 的 die 會先印錯誤再 SystemExit；close 把它改成一行提醒，不擋收畫面。
    error = io.StringIO()
    try:
        with contextlib.redirect_stderr(error):
            kind = cli_cfg.load_cfg(eca)["kind"]
    except SystemExit:
        reason = error.getvalue().strip().split(": error: ", 1)[-1] or "configuration loading failed"
    else:
        sys.stderr.write(error.getvalue())
        return kind
    try:
        with open(os.path.join(eca, "cli.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        kind = cfg.get("kind") if isinstance(cfg, dict) else None
    except (OSError, ValueError):
        kind = None
    aos_flags.warn(PROG, "cli.json of %s is not valid (%s); closing the screen by its kind only" % (eca, reason))
    return kind if isinstance(kind, str) and kind.strip() else None


def cmd_close(eca, opts):
    stack = os.environ.get("AOS_STACK")
    if not stack:
        die("StackMissing", "AOS_STACK is not set (the eca's stack)")
    kind = kind_for_close(eca)
    kinds = (kind,) if kind else cli_cfg.AOS_FLAGS
    closed = False
    for kind in kinds:
        cell = cli_cell.Cell(os.path.join(stack, kind), make=False)
        if not os.path.isdir(cell.path):
            continue
        f, ok = cell.lock()
        with f:
            if not ok:
                die("SessionBad", "busy answering; close it after the answer finishes")
            closed = cli_cell.close(cell) or closed
    print("closed" if closed else "no screen (already closed)")


def describe(ev):
    """live.jsonl 一行 → 給人看的短行（claude stream-json、codex --json）；不認得的＝None。"""
    t = ev.get("type")
    if t == "system" and ev.get("subtype") == "init":
        return "── start (session %s, model %s)" % ((ev.get("session_id") or "")[:8], ev.get("model"))
    if t == "assistant":
        out = []
        for c in (ev.get("message") or {}).get("content") or []:
            if c.get("type") == "text" and c.get("text", "").strip():
                out.append(c["text"].strip())
            elif c.get("type") == "tool_use":
                out.append("  ▶ %s %s" % (c.get("name"), json.dumps(c.get("input"), ensure_ascii=False)[:120]))
        return "\n".join(out) or None
    if t == "user":
        for c in (ev.get("message") or {}).get("content") or []:
            if isinstance(c, dict) and c.get("type") == "tool_result":
                body = c.get("content")
                body = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
                return "  ◀ %s" % body.replace("\n", " ")[:120]
    if t == "result":
        return "── end (%s, $%.4f)" % ("error" if ev.get("is_error") else "done", ev.get("total_cost_usd") or 0)
    if t in ("item.completed", "item.started") and isinstance(ev.get("item"), dict):
        item = ev["item"]
        return "  %s %s" % (item.get("type") or item.get("item_type"), (item.get("text") or item.get("command") or "")[:120])
    if t == "turn.completed":
        return "── end"
    msg = ev.get("message") if t == "message_end" and isinstance(ev.get("message"), dict) else None   # pi（11-18 eca-pi）
    if msg and msg.get("role") == "assistant":
        text = "".join(c.get("text", "") for c in msg.get("content") or [] if isinstance(c, dict) and c.get("type") == "text")
        return text.strip() or ("── error: %s" % msg.get("errorMessage") if msg.get("stopReason") == "error" else None)
    if msg and msg.get("role") == "user":
        text = "".join(c.get("text", "") for c in msg.get("content") or [] if isinstance(c, dict) and c.get("type") == "text")
        return "  ✉ %s" % text.replace("\n", " ")[:120] if text.strip() else None
    if t == "tool_execution_start":
        return "  ▶ %s %s" % (ev.get("toolName"), json.dumps(ev.get("args"), ensure_ascii=False)[:120])
    if t == "agent_settled":
        return "── end"
    return None


def gone(eca, stack, watch=None):
    """走 kernel 每五秒重問表檔；空表或自己不再 running 才退出，缺欄與讀不到都照等。直連路照舊。"""
    if os.environ.get("AOS_KERNEL"):
        watch = watch if watch is not None else {}
        now = time.monotonic()
        if watch.get("last_check") is not None and now - watch["last_check"] < 5:
            return watch.get("result")
        watch["last_check"] = now                   # 查詢或讀表失敗也節流。
        watch["result"] = None
        try:
            path = dc.state_path(timeout_s=1, fresh=True)
            rows = dc.rows_at(path)
        except (dc.Fail, OSError, ValueError):
            return None
        values = [r for r in rows.values() if isinstance(r, dict)]
        if rows and not any("stack" in r for r in values):
            return None
        target = os.path.realpath(stack)
        own = next((r for r in values if isinstance(r.get("stack"), str) and r["stack"]
                    and os.path.realpath(r["stack"]) == target), None)
        if own is not None and ("phase" not in own or own["phase"] == "running"):
            return None
        name = watch.get("name") or os.path.basename(stack.rstrip(os.sep))
        watch["result"] = "watch: %s is no longer running on the table at %s" % (name, path)
        return watch["result"]
    try:
        daemon = dc.find_daemon()
        rows = dc.rows(daemon)
    except dc.Fail:
        return None
    target = os.path.realpath(stack)
    for row in rows.values():
        if not isinstance(row, dict):
            continue
        row_stack = row.get("stack")
        if not isinstance(row_stack, str) or not row_stack:
            continue
        if os.path.realpath(row_stack) == target:
            phase = row.get("phase")
            if phase != "running":
                return "its proc is %s on the daemon table" % phase
            return None
    return "its proc is no longer on the daemon table (slept, stopped or removed?)"


def cmd_watch(eca, opts):
    cell, stack = cell_of(eca)
    path = cell.file("live.jsonl")
    pos = os.path.getsize(path) if os.path.exists(path) else 0
    aos_flags.warn(PROG, "watching %s; Ctrl-C to leave" % path)
    watch = {"name": os.path.basename(stack.rstrip(os.sep))}   # 名字在開始時固定，不從退出當下已刪的列取。
    try:
        while True:
            try:
                with open(path, "rb") as f:
                    f.seek(pos)
                    data = f.read()
            except OSError:
                data = b""
            end = data.rfind(b"\n") + 1
            pos += end
            for line in data[:end].decode("utf-8", "replace").splitlines():
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                s = describe(ev) if isinstance(ev, dict) else None
                if s:
                    print(s, flush=True)
                if isinstance(ev, dict) and ev.get("type") in ("result", "turn.completed", "agent_settled"):
                    return
            why = None if end else gone(eca, stack, watch)   # 這一拍沒有新的整行才看
            if why:
                aos_flags.warn(PROG, "watch stopped waiting, %s; an answer cut off there never finishes" % why)
                return
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass


def cmd_peek(eca, opts, command):
    """唯讀的 slash 當場回（11-16 ok-small）：只讀 cli.json、小格的檔與 history 的則數；/usage 另起一次不存對話的 claude -p。"""
    cell, stack = cell_of(eca)
    cfg = cli_cfg.load_cfg(eca)
    ws = os.path.abspath(os.environ.get("AOS_WS") or ".")
    try:
        text = slash_status(cfg, cell, stack) if command == "/status" else slash_usage(cfg, ws)
    except EcaFail as e:
        die(e.code, str(e))
    sys.stdout.write(text if text.endswith("\n") else text + "\n")


CMDS = {"open": cmd_open, "close": cmd_close, "watch": cmd_watch, "peek": cmd_peek}
SWITCHES = {"open": {"--detach": "detach"}}


def main():
    try:
        top, rest = aos_flags.parse(sys.argv[1:], {"--eca": "eca"}, sub="root")   # --eca 寫在子命令前後都收（11-11 P-44 續）
    except aos_flags.Error as e:
        reason = str(e) if e.code == "FlagUnknown" else "%s (see %s --help)" % (e, PROG)
        die(e.code, reason)
    choices = "%s; see %s --help" % (", ".join(HELPS), PROG)
    if not rest:
        die("ArgumentsBad", "missing subcommand (%s)" % choices)
    sub = rest[0]
    if sub not in CMDS:
        die("CommandUnknown", "unknown subcommand %s (%s)" % (sub, choices))
    try:
        opts, args = aos_flags.parse(rest[1:], {}, SWITCHES.get(sub), help=HELPS[sub])
    except aos_flags.Error as e:
        reason = ("%s (see %s %s --help)" % (e, PROG, sub) if e.code == "FlagUnknown"
                  else sub_reason(sub, e.code, e))
        die(e.code, reason)
    want = 1 if sub == "peek" else 0
    if len(args) > want:
        die("ArgumentsBad", sub_reason(sub, "ArgumentsBad", "unexpected argument %s" % args[want]))
    if sub == "peek" and (not args or args[0].strip() not in PEEK):
        die("ArgumentsBad", sub_reason(sub, "ArgumentsBad", "peek takes one of %s, got %s" % (", ".join(PEEK), args[0] if args else "nothing")))
    if not top.get("eca"):
        die("ArgumentsBad", sub_reason(sub, "ArgumentsBad", "missing --eca ECA_DIR"))
    eca = os.path.realpath(top["eca"])
    if sub != "close" and not os.path.isfile(os.path.join(eca, "cli.json")):
        die("ArgumentsBad", sub_reason(sub, "ArgumentsBad",
                                       "%s is not an eca dir (no cli.json)" % top["eca"]))
    if sub == "peek":
        CMDS[sub](eca, opts, args[0].strip())
    else:
        CMDS[sub](eca, opts)


if __name__ == "__main__":
    aos_flags.run(main)
