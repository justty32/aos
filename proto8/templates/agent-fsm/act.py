# act.py [--tools FILE] - act 格：依序 aos-tools call，照 metainfo 限時，失敗附 stderr 尾給腦（比照 aos-mcp 的 C-52 例外），結果接進 history，另記工具成本觀測。
# 結束碼（fsm.json 照碼分岔，N-36）：全部跑完退 0（→ think：帶工具結果再問腦）；最後一則 assistant 沒有 tool_calls＝腦給了最後答案、沒事做，退 10（→ idle）。
#   「要不要叫工具」11-04 晚從 think 搬到這裡判（think 只組請求，thinking 2026-11-04 think-as-function 03 § 1）。
# 工具的介面（P-41）：arguments（JSON 字串）原樣從 stdin 進、stdout 整段是結果；工具的小格由 aos-tools call 算成 $AOS_STACK/tools/<名>/（P-17）、工作區＝$AOS_WS。
# 中途失敗重跑時，已經有 tool 訊息的 id 不再跑（只補沒回的）。
# 叫工具出的問題回給腦、不停（P-41）：工具退非 0（stdout 照收、尾巴加結束碼）、逾時、叫了沒登記的工具、arguments 不是 JSON。
# 比照 aos-mcp 的 C-52／C-53 例外：工具退非 0 或逾時，接住 stderr、原樣轉印，最後 2 KB 另附給腦；成功時不附（J4 授權，條文 J7 再補）。
# 逾時取 _metainfo.time_ms.max（毫秒），沒寫＝不設；自成一群，逾時或本格中斷時 TERM 整群，2 秒後 KILL。
# 工具退非 0 時 stderr 多一行提醒「agent-fsm: warning: tool <名> exit code N (passed back to the brain)」（stdio-unify R1：不是這格的錯，照樣退 0）。
# 只有自己這層的錯才停：stderr 一行「agent-fsm: error: 代號 原因」、退 1、history 不接（P-20）——沒 stack、history 壞、
#   history 裡沒有 assistant、aos-tools 起不來。
# --tools FILE：aos-tools 登記檔（預設 interfaces.json 宣告的 tools；沒有那份＝沒有工具）。相對路徑從範本資料夾（AOS_CD）算。
#   沒給 --tools 時，$AOS_STACK/<宣告相對路徑> 在＝疊上這隻的覆蓋層（aos-tools --overlay；aos-agent tools add／rm 寫的，只存差異，11-05）。
# 照舊的 agent-eve 的 act.py 改（拿掉 out/、done/、current.txt；agent-eve 11-04 隨 proto8/tests 刪了）。
import json, os, signal, subprocess, sys, time
from pathlib import Path

_import_paths = [str(Path(__file__).resolve().parent)]
for _parent in Path(__file__).resolve().parents:
    for _layer, _module in (("py", "aos_flags.py"), ("lib", "agent/agent_files.py")):
        _root = _parent / _layer
        if (_root / _module).is_file() and str(_root) not in _import_paths:
            _import_paths.append(str(_root))
sys.path[:0] = _import_paths
try:
    import aos_flags  # noqa: E402
    if (Path(__file__).resolve().parent / "agent_files.py").is_file():
        from agent_files import declared_files  # noqa: E402
    else:
        from agent.agent_files import declared_files  # noqa: E402
except ModuleNotFoundError as _error:
    if _error.name not in ("aos_flags", "tool_io", "agent_files", "agent", "agent.agent_files"):
        raise
    print("agent-fsm: error: ModuleMissing required Python module %s is unavailable" % _error.name,
          file=sys.stderr)
    sys.exit(1)
finally:
    for _path in _import_paths:
        sys.path.remove(_path)

from observed import append_observed

HELP = """\
usage: act.py [--tools FILE]   (a cell of templates/agent-fsm; run by its fsm.json under aos-fsm, needs $AOS_STACK)
The act cell: run the tool_calls of the last assistant message in $AOS_STACK/history.jsonl
(aos-tools call NAME), one tool message each. Exit 0 = done (go think); 10 = no tool_calls.
--tools FILE: the aos-tools registry (default: tools declared in interfaces.json).
Timeout: tool metainfo time_ms.max (ms), otherwise no limit; TERM the group, KILL 2 s later.
On tool failure or timeout, append the last 2048 bytes of stderr to the tool message;
the full stderr is also passed through. Tool failures are returned to the brain; exit 0.
Append tool name, code, elapsed_ms, in_bytes and out_bytes to observed.jsonl (best effort).
On error: one line "agent-fsm: error: CODE reason" on stderr, exit 1.
"""
signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))   # Ctrl-C：不吐 traceback、退 130（R12）
signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(143))  # 工具另成一群：自己收 TERM 也得把它收掉


def die(code, reason):
    aos_flags.die("agent-fsm", code, reason)


try:
    values, rest = aos_flags.parse(sys.argv[1:], {}, multi={'--tools': '--tools'}, help=HELP)
except aos_flags.Error as e:
    die(e.code, e)
if rest:
    die("ArgumentsBad", "unexpected argument %s (usage: act.py [--tools FILE])" % rest[0])
# 收齊重複值再取最後一個：任一次空值都照舊報錯，不讓後面的值蓋掉錯誤。
for flag, items in values.items():
    if any(not value for value in items):
        die("ArgumentsBad", "%s needs a non-empty value (usage: act.py [--tools FILE])" % flag)
opts = {flag: items[-1] for flag, items in values.items()}
stack = os.environ.get("AOS_STACK")
if not stack:
    die("StackMissing", "AOS_STACK is not set")
try:
    files = declared_files(os.environ.get("AOS_CD") or ".")
except ValueError as e:
    die("InterfaceBad", str(e))
tools_rel = opts.get("--tools", files.get("tools"))
tools_file = os.path.join(os.environ.get("AOS_CD") or ".", tools_rel) if tools_rel else None
if "--tools" in opts and not os.path.isfile(tools_file):
    die("ToolsMissing", "tool registry not found: %s" % tools_file)
overlay = os.path.join(stack, tools_rel) if tools_rel and "--tools" not in opts else None
overlay = overlay if overlay and os.path.isfile(overlay) else None
TOOLS = ["aos-tools"] + (["--file", tools_file] if tools_file else []) + (["--overlay", overlay] if overlay else [])
history_path = os.path.join(stack, "history.jsonl")
history = []
try:
    with open(history_path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.strip():
                try:
                    m = json.loads(line)
                except ValueError:
                    m = None
                if not isinstance(m, dict):
                    die("HistoryBad", "history.jsonl line %d is not a JSON object" % n)
                history.append(m)
except FileNotFoundError:
    pass
except OSError as e:
    die("HistoryBad", "cannot read history.jsonl: %s" % e)
last = max((i for i, m in enumerate(history) if m.get("role") == "assistant"), default=None)
if last is None:
    die("HistoryBad", "no assistant message in history.jsonl")
calls = history[last].get("tool_calls")
if not calls:
    sys.exit(10)                                 # 最後答案：沒有工具要叫，回 idle 等信
if not isinstance(calls, list):
    die("HistoryBad", "tool_calls of the last assistant message is not an array")


def append(message):
    try:
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")
    except OSError as e:
        die("WriteFailed", "cannot append to history.jsonl: %s" % e)


def stop_group(p):
    """TERM 整群、寬限 2 秒後 KILL；群長先退也不能漏掉忽略 TERM 的孫行程。"""
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    time.sleep(2)
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


registered = {}
if (tools_file and os.path.isfile(tools_file)) or overlay:        # 能叫的＝登記檔（疊覆蓋層）裡的（aos-tools ls --json）；失敗＝自己這層的錯
    try:
        r = subprocess.run(TOOLS + ["ls", "--json"], stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, text=True)
    except OSError as e:
        die("ToolFailed", "aos-tools cannot start: %s" % e)
    if r.returncode != 0:
        die("ToolsBad", "aos-tools ls exited %d" % r.returncode)
    for t in json.loads(r.stdout):
        meta = t.get("metainfo") or {}
        tm = meta.get("time_ms")
        limit = None
        if isinstance(tm, dict) and isinstance(tm.get("max"), (int, float)) and tm["max"] > 0:
            limit = tm["max"] / 1000.0
        registered[t["name"]] = limit
answered = {m.get("tool_call_id") for m in history[last + 1:] if m.get("role") == "tool"}
for call in calls:
    try:
        cid, name, arguments = call["id"], call["function"]["name"], call["function"].get("arguments")
    except (KeyError, TypeError):
        die("HistoryBad", "a tool_calls entry has no id or function.name: %s" % json.dumps(call, ensure_ascii=False))
    if cid in answered:
        continue
    if name not in registered:                   # 名字只認登記過的（也擋掉 ../ 之類）
        append({"role": "tool", "tool_call_id": cid,
                "content": aos_flags.error_line("act", "ToolUnknown", "%s (available: %s)" % (name, ", ".join(registered))) + "\n"})
        continue
    try:
        if not isinstance(arguments, str):
            raise ValueError("arguments is not a string")
        json.loads(arguments)
    except ValueError as e:
        append({"role": "tool", "tool_call_id": cid, "content": aos_flags.error_line("act", "ArgumentsBad", "%s: %s" % (name, e)) + "\n"})
        continue
    started_ns = time.monotonic_ns()
    try:
        p = subprocess.Popen(TOOLS + ["call", name], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=True)   # 繼承自己的 stack；aos-tools call 算小格。自成一群，逾時整群收掉
    except OSError as e:
        die("ToolFailed", "aos-tools cannot start: %s" % e)
    limit, timed_out = registered[name], False
    try:
        try:
            out, err = p.communicate(arguments.encode("utf-8"), timeout=limit)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop_group(p)
            try:
                out, err = p.communicate(timeout=2)
            except subprocess.TimeoutExpired as e:   # 逃出群組的行程仍拿著管子：保留已收的輸出，不無限等
                out, err = e.output or b"", e.stderr or b""
                p.stdout.close()
                p.stderr.close()
                p.wait()
    except BaseException:                       # Ctrl-C／TERM／其他中斷：工具不再跟自己的群，離開前主動收掉
        stop_group(p)
        p.wait()
        raise
    append_observed(stack, {"kind": "tool", "name": name, "code": p.returncode,
                            "elapsed_ms": (time.monotonic_ns() - started_ns) / 1_000_000,
                            "in_bytes": len(arguments.encode("utf-8")), "out_bytes": len(out)})
    if err:                                     # C-52 例外：原樣轉印，成功時不附給腦
        sys.stderr.buffer.write(err)
        sys.stderr.buffer.flush()
    content = out.decode("utf-8", "replace")
    if timed_out:
        aos_flags.warn("agent-fsm", "tool %s timed out (passed back to the brain)" % name)
        content += "%s(tool %s timed out (%g s); its process group was killed)\n" % ("" if content.endswith("\n") or not content else "\n", name, limit)
    elif p.returncode != 0:                      # 回給腦、不停；人在 stderr 看得到
        aos_flags.warn("agent-fsm", "tool %s exit code %d (passed back to the brain)" % (name, p.returncode))
        content += "%s(tool %s exit code %d)\n" % ("" if content.endswith("\n") or not content else "\n", name, p.returncode)
    if (timed_out or p.returncode != 0) and err:
        content += "stderr (last 2048 bytes at most):\n%s\n" % err[-2048:].decode("utf-8", "replace").strip()
    append({"role": "tool", "tool_call_id": cid, "content": content})
sys.exit(0)
