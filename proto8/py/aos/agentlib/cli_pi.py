# cli_pi.py - cli_session 的 pi 身（pi coding agent，11-18 eca-pi）：起 pi 的整串、小格的兩支外掛、從事件讀回答；非互動一輪與 /compact 都走 pi --mode rpc（cli_pi_rpc）
import json, os, shutil, sys, uuid

from aos.agentlib import cli_base
from aos.agentlib.cli_cell import PI_SESSIONS, drop_session, mark_session, transcripts
from aos.agentlib.cli_cfg import system_argv
from aos.agentlib.cli_mcp import _aos_server_args, mcp_env

# 11-18 實測 pi 1.5.2（使用者自己裝的那份）：
# - --session-dir <小格>/pi-sessions --session-id <id>：第一次建 <時間>_<id>.jsonl（stderr 印一行 "No project session found …; creating"），
#   第二次同一個 id＝接著那段；互動畫面同一招也是接著那段（session_start reason startup）。
# - rpc（乙案，取代甲案的 --mode json）：{"type": "prompt"} 回 response disposition started；答完以 agent_settled 為準（agent_end 不是終點）。
#   答題途中送 {"type": "steer"}＝回 response disposition queued、下一次叫模型之前以一則 user 送進去（工具做完那一步、或這段字講完之後再開一段），
#   全部都在 agent_settled 之前送到；答題中再送 prompt＝success false "Agent is already processing"。rpc 不印 session 那行。
# - 答案：一則 user（題目或中途的信）到下一則 user 之間，最後一則講完的 assistant（stopReason stop）的文字；中途的信各自一段，用空行接起來。
# - 模型那邊出錯 pi 照樣退 0：最後一則 assistant 的 stopReason 是 "error"、errorMessage 寫原因；模型名不認得＝退 1、stderr 一行。
# - compact：rpc 送 {"type": "compact"}，stdin 要等到 response 才關（先關＝pi 收工、壓縮被取消，回 "Compaction cancelled"）。
# - 沒有「這次起動用這份 MCP 設定」的旗標；-e <外掛檔> 的外掛呼叫 pi.registerMcpServer 可以（--no-approve 下照載，明寫的 -e 不受信任管）。
# - 互動畫面：外掛拿得到 session_start（reason startup／new／resume／fork）、agent_start、agent_end（messages）、agent_settled、
#   session_compact（compactionEntry.summary）；node:child_process 的 spawnSync 叫得動 aos 的 hook；pi.sendUserMessage(字, {deliverAs: "steer"})
#   在答題中、不帶參數在閒著時，都把字送進對話（同 claude 畫面的收件口，cli_a2a 的 pi 分岔）。
# - 用量：message_end 的 message.usage {input, output, cacheRead, cacheWrite, totalTokens}；事件裡沒有 context 視窗大小。

EXTENSION = "pi-aos-mcp.mjs"                           # 小格裡 aos 每次起 pi 前重寫的外掛（只做一件事：登記 aos 那台 MCP）
SCREEN_EXTENSION = "pi-aos-screen.mjs"                 # 開畫面時重寫的一行外掛：叫同層的 pi_aos_screen.mjs、帶這格的設定
SCREEN_MODULE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pi_aos_screen.mjs")
INBOX = "pi_inbox"                                     # 畫面開著時 aos 投信的資料夾（一封一個 .json；畫面外掛讀了就刪）


def _write(cell, name, text):
    try:
        cell.write(name, text)
    except OSError as e:
        cli_base.die("WriteFailed", "cannot write %s: %s" % (cell.file(name), e))
    return ["-e", cell.file(name)]


def extension_argv(cfg, cell, ws, stack):
    """有登記檔＝寫小格的外掛檔、回 ["-e", 它]；沒有＝[]。外掛只呼叫 pi.registerMcpServer("aos", …)：指令＝aos-mcp 的絕對路徑、
    參數同 claude／codex、env＝MCP_ENV 加 AOS_WS／AOS_STACK（同 codex）、exposure direct（工具直接給模型看，跟 claude／codex 一樣）。"""
    if not cfg.get("registry"):
        return []
    args = _aos_server_args(cfg, ws, stack)
    server = {"command": shutil.which("aos-mcp"), "args": args, "env": mcp_env(ws, stack), "exposure": "direct",
              "description": "aos tools of this agent"}
    return _write(cell, EXTENSION, "// written by aos (cli_pi.py) before each pi run; do not edit\n"
                  "export default function (pi) { pi.registerMcpServer(\"aos\", %s); }\n" % json.dumps(server, ensure_ascii=False))


def screen_extension_argv(cell, hook_script):
    """開畫面用：小格寫一行外掛，import 同層的 pi_aos_screen.mjs、帶 {python, hook, cell, inbox}，回 ["-e", 它]。"""
    conf = {"python": sys.executable, "hook": hook_script, "cell": cell.path, "inbox": cell.file(INBOX)}
    return _write(cell, SCREEN_EXTENSION, "// written by aos (cli_pi.py) when it opens the screen; do not edit\n"
                  "import run from %s;\nexport default function (pi) { run(pi, %s); }\n"
                  % (json.dumps(SCREEN_MODULE), json.dumps(conf, ensure_ascii=False)))


def pi_argv(cfg, cell, ws, stack, sid, mode="rpc"):
    """起 pi 的整串。mode＝rpc：pi --mode rpc --no-approve --session-dir … --session-id <id> [flags] [print_flags] [-e 外掛] [system]；
    mode＝None（畫面）：不帶 --mode 與 print_flags，sid 空＝不帶 --session-id（pi 自己開新的，畫面外掛回報 id）。"""
    os.makedirs(cell.file(PI_SESSIONS), exist_ok=True)
    head = ["pi"] + (["--mode", mode] if mode else []) + ["--no-approve", "--session-dir", cell.file(PI_SESSIONS)]
    head += ["--session-id", sid] if sid else []
    return head + cfg.get("flags", []) + (cfg.get("print_flags", []) if mode else []) + extension_argv(cfg, cell, ws, stack) + system_argv(cfg)


def message_text(msg):
    parts = msg.get("content")
    if isinstance(parts, str):
        return parts
    return "".join(p.get("text", "") for p in parts or [] if isinstance(p, dict) and p.get("type") == "text"
                   and isinstance(p.get("text"), str))


def messages_of(lines):
    """事件流 → 依序每則 message_end 的 message（user、assistant；其他 role 略過）。"""
    out = []
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        msg = ev.get("message") if isinstance(ev, dict) and ev.get("type") == "message_end" else None
        if isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
            out.append(msg)
    return out


def answer_of(messages):
    """回答：每則 user 之後到下一則 user 之前，最後一則講完（stopReason 不是 toolUse／error／aborted）又有字的 assistant；各段用空行接起來。
    messages 也收畫面外掛給的瘦身版 {"role", "stopReason", "text"}。"""
    parts, seg = [], None
    for m in messages:
        if m.get("role") == "user":
            if seg:
                parts.append(seg)
            seg = None
        elif m.get("role") == "assistant" and m.get("stopReason") not in ("toolUse", "error", "aborted"):
            text = m["text"] if isinstance(m.get("text"), str) else message_text(m)
            seg = text if text.strip() else seg
    return "\n\n".join(parts + ([seg] if seg else []))


def _missing_hint(code):
    return " (exit 127: pi, or the node it runs on, is not on PATH)" if code == 127 else ""


def print_pi(cfg, cell, ws, stack, prompt, handed=None, sid=None, more=None):
    """sid＝要接的對話（ask 已認過是這台的）；空＝開新對話：我們產 id、--session-id 給，交出去那一刻先寫 session.txt 與記號檔（同 claude）。
    沒給 sid（None）＝照舊讀 session.txt。起一次 pi --mode rpc 送題目；more＝等回答時又來的信（midturn.More），cli.json 沒寫 "live_mail": false
    就一封一封 steer 進去（乙案）。事件一行一行接進 live.jsonl。回 answer_of 的文字。"""
    from aos.agentlib.cli_pi_rpc import run_pi_rpc
    from aos.agentlib.cli_print import live_cap, parent_death_term, timeout_seconds
    live = more is not None and cfg.get("live_mail", True) is not False
    cap = live_cap(cfg) if live else None
    sid = cell.read("session.txt") if sid is None else sid
    new = "" if sid else str(uuid.uuid4())
    argv = pi_argv(cfg, cell, ws, stack, sid or new)

    def given():
        if new:
            mark_session("pi", cell, ws, new)
        if handed:
            handed()
    code, lines, refused = run_pi_rpc(argv, prompt, ws, timeout_seconds(cli_base.turn_timeout_ms(cfg)), cell.file("live.jsonl"),
                                      given, more if live else None, cap, parent_death_term())
    msgs = messages_of(lines)
    last = next((m for m in reversed(msgs) if m.get("role") == "assistant"), None)
    bad = refused or last is None or last.get("stopReason") in ("error", "aborted")
    if bad and not transcripts("pi", sid or new, cell.path):       # 以為有、或第一輪就失敗而 pi 沒建檔：清掉，下一輪開新的（05、TS 9）
        drop_session(cell)
    if refused:
        cli_base.die("CliFailed", "pi refused the prompt: %s" % refused)
    if last is None:
        cli_base.die("CliFailed", "pi exited %d with no answer in its output%s (its reason is on stderr)" % (code, _missing_hint(code)))
    if bad:
        why = last.get("errorMessage") if isinstance(last.get("errorMessage"), str) else last.get("stopReason")
        cli_base.die("CliFailed", "pi's answer ended with %s: %s" % (last.get("stopReason"), str(why)[-300:]))
    return answer_of(msgs)


def compact(cfg, cell, ws, stack, instructions=None):
    """非互動的 /compact：起一次 pi --mode rpc 接同一段對話，送 {"type": "compact"}（帶指示＝customInstructions），讀到 response 才關 stdin。
    回 (True, 摘要) 或 (False, 原因)。事件也接進 live.jsonl。沒有對話＝(False, …)。"""
    from aos.agentlib.cli_pi_rpc import rpc_once
    from aos.agentlib.cli_print import timeout_seconds
    sid = cell.read("session.txt")
    if not sid:
        return False, "no conversation yet, nothing to compact"
    cmd = {"type": "compact", "id": "aos-compact"}
    if instructions:
        cmd["customInstructions"] = instructions
    code, reply = rpc_once(pi_argv(cfg, cell, ws, stack, sid), cmd, ws, timeout_seconds(cli_base.turn_timeout_ms(cfg)), cell.file("live.jsonl"))
    if reply is None:
        return False, "pi exited %d without answering the compact command%s" % (code, _missing_hint(code))
    if not reply.get("success"):
        return False, "pi did not compact: %s" % reply.get("error")
    data = reply.get("data") if isinstance(reply.get("data"), dict) else {}
    summary = data.get("summary")
    return True, summary if isinstance(summary, str) else ""
