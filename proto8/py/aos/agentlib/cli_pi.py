# cli_pi.py - cli_session 的 pi 身（pi coding agent，11-18 eca-pi 甲案）：pi --mode json 一問一答、對話檔進小格、aos-mcp 經生成的外掛、/compact 走一次 pi --mode rpc
import json, os, shutil, subprocess, threading, uuid

from aos.agentlib import cli_base
from aos.agentlib.cli_cell import PI_SESSIONS, drop_session, mark_session, transcripts
from aos.agentlib.cli_cfg import system_argv
from aos.agentlib.cli_mcp import _aos_server_args, mcp_env

# 11-18 實測 pi 1.5.2（使用者自己裝的那份，假 OpenAI 相容端點）：
# - 題目只給 stdin、不給參數＝stdin 就是題目（文件說「接在第一則題目前面」，沒有題目時就是它自己）。
# - --session-dir <小格>/pi-sessions --session-id <id>：第一次建 <時間>_<id>.jsonl（stderr 印一行 "No project session found …; creating"），
#   第二次同一個 id＝接著那段（送給模型的訊息變多），不是開新的。
# - 答完：最後一則 role assistant 的 message_end 是回答；之後還有 agent_end、agent_settled（以 agent_settled 為準，行程隨後結束）。
# - 模型那邊出錯（端點連不上等）pi 照樣退 0：最後一則 assistant 的 stopReason 是 "error"、errorMessage 寫原因；模型名不認得＝退 1、stderr 一行。
# - json 模式不認 /compact（當成一般題目交給模型）；壓縮要 --mode rpc 送 {"type": "compact"}，而且 stdin 要等到 response 才關
#   （先關 stdin＝pi 收工、壓縮被取消，回 "Compaction cancelled"）。
# - 沒有「這次起動用這份 MCP 設定」的旗標；-e <外掛檔> 的外掛呼叫 pi.registerMcpServer 可以（--no-approve 下照載，明寫的 -e 不受信任管）。
# - 用量：message_end 的 message.usage {input, output, cacheRead, cacheWrite, totalTokens}；事件裡沒有 context 視窗大小。

EXTENSION = "pi-aos-mcp.mjs"                           # 小格裡 aos 每次起 pi 前重寫的外掛（只做一件事：登記 aos 那台 MCP）


def extension_argv(cfg, cell, ws, stack):
    """有登記檔＝寫小格的外掛檔、回 ["-e", 它]；沒有＝[]。外掛只呼叫 pi.registerMcpServer("aos", …)：指令＝aos-mcp 的絕對路徑、
    參數同 claude／codex、env＝MCP_ENV 加 AOS_WS／AOS_STACK（同 codex）、exposure direct（工具直接給模型看，跟 claude／codex 一樣）。"""
    if not cfg.get("registry"):
        return []
    args = _aos_server_args(cfg, ws, stack)
    server = {"command": shutil.which("aos-mcp"), "args": args, "env": mcp_env(ws, stack), "exposure": "direct",
              "description": "aos tools of this agent"}
    text = ("// written by aos (cli_pi.py) before each pi run; do not edit\n"
            "export default function (pi) { pi.registerMcpServer(\"aos\", %s); }\n" % json.dumps(server, ensure_ascii=False))
    try:
        cell.write(EXTENSION, text)
    except OSError as e:
        cli_base.die("WriteFailed", "cannot write %s: %s" % (cell.file(EXTENSION), e))
    return ["-e", cell.file(EXTENSION)]


def pi_argv(cfg, cell, ws, stack, mode, sid):
    """起 pi 的整串：pi --mode <mode> --no-approve --session-dir <小格>/pi-sessions --session-id <id> [flags] [print_flags] [-e 外掛] [system]。"""
    os.makedirs(cell.file(PI_SESSIONS), exist_ok=True)
    return (["pi", "--mode", mode, "--no-approve", "--session-dir", cell.file(PI_SESSIONS), "--session-id", sid]
            + cfg.get("flags", []) + cfg.get("print_flags", []) + extension_argv(cfg, cell, ws, stack) + system_argv(cfg))


def last_assistant(lines):
    """事件流裡最後一則 role assistant 的 message_end 的 message；沒有＝None。"""
    out = None
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "message_end":
            msg = ev.get("message")
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                out = msg
    return out


def message_text(msg):
    parts = msg.get("content")
    if isinstance(parts, str):
        return parts
    return "".join(p.get("text", "") for p in parts or [] if isinstance(p, dict) and p.get("type") == "text"
                   and isinstance(p.get("text"), str))


def _missing_hint(code):
    return " (exit 127: pi, or the node it runs on, is not on PATH)" if code == 127 else ""


def print_pi(cfg, cell, ws, stack, prompt, handed=None, sid=None):
    """sid＝要接的對話（ask 已認過是這台的）；空＝開新對話：我們產 id、--session-id 給，交出去那一刻先寫 session.txt 與記號檔（同 claude）。
    沒給 sid（None）＝照舊讀 session.txt。題目從 stdin 進；事件一行一行接進 live.jsonl。回最後一則 assistant 的文字。"""
    from aos.agentlib.cli_print import run_claude_stream          # 通用的「起、stdin 給題目、邊讀邊寫 live.jsonl」
    sid = cell.read("session.txt") if sid is None else sid
    new = "" if sid else str(uuid.uuid4())
    argv = pi_argv(cfg, cell, ws, stack, "json", sid or new)

    def given():
        if new:
            mark_session("pi", cell, ws, new)
        if handed:
            handed()
    code, lines = run_claude_stream(argv, prompt, ws, cli_base.turn_timeout_ms(cfg), cell.file("live.jsonl"), given)
    msg = last_assistant(lines)
    bad = code != 0 or msg is None or msg.get("stopReason") in ("error", "aborted")
    if bad:
        if not transcripts("pi", sid or new, cell.path):           # 以為有、或第一輪就失敗而 pi 沒建檔：清掉，下一輪開新的（05、TS 9）
            drop_session(cell)
    if code != 0 or msg is None:
        cli_base.die("CliFailed", "pi exited %d with no answer in its output%s (its reason is on stderr)" % (code, _missing_hint(code)))
    if bad:
        why = msg.get("errorMessage") if isinstance(msg.get("errorMessage"), str) else msg.get("stopReason")
        cli_base.die("CliFailed", "pi's answer ended with %s: %s" % (msg.get("stopReason"), str(why)[-300:]))
    return message_text(msg)


def compact(cfg, cell, ws, stack, instructions=None):
    """非互動的 /compact：起一次 pi --mode rpc 接同一段對話，送 {"type": "compact"}（帶指示＝customInstructions），讀到 response 才關 stdin。
    回 (True, 摘要) 或 (False, 原因)。事件也接進 live.jsonl。沒有對話＝(False, …)。"""
    sid = cell.read("session.txt")
    if not sid:
        return False, "no conversation yet, nothing to compact"
    argv = pi_argv(cfg, cell, ws, stack, "rpc", sid)
    cmd = {"type": "compact", "id": "aos-compact"}
    if instructions:
        cmd["customInstructions"] = instructions
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=ws)
    except FileNotFoundError:
        cli_base.die("CliMissing", "pi is not on PATH")
    seconds = cli_base.turn_timeout_ms(cfg) / 1000 or None
    timer = threading.Timer(seconds, p.kill) if seconds else None
    if timer:
        timer.start()
    reply = None
    try:
        p.stdin.write(json.dumps(cmd) + "\n")
        p.stdin.flush()
        with open(cell.file("live.jsonl"), "a", encoding="utf-8") as live:
            for line in p.stdout:
                live.write(line)
                live.flush()
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if isinstance(ev, dict) and ev.get("type") == "response" and ev.get("id") == cmd["id"]:
                    reply = ev
                    break
        p.stdin.close()
        p.wait()
    finally:
        if timer:
            timer.cancel()
    if reply is None:
        return False, "pi exited %d without answering the compact command%s" % (p.returncode, _missing_hint(p.returncode))
    if not reply.get("success"):
        return False, "pi did not compact: %s" % reply.get("error")
    data = reply.get("data") if isinstance(reply.get("data"), dict) else {}
    summary = data.get("summary")
    return True, summary if isinstance(summary, str) else ""
