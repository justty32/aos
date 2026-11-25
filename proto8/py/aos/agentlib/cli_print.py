# cli_print.py - cli_session 的非互動那條路（畫面沒開）：claude -p／codex exec 起 CLI、等回答、記 session
import json, os, selectors, signal, subprocess, sys, threading, time, uuid

from aos.agentlib import cli_base, cli_fault
from aos.agentlib.cli_cell import codex_main_thread, drop_session, mark_session, transcripts
from aos.agentlib.cli_cfg import system_argv
from aos.agentlib.cli_mcp import external_claude, external_codex, guard_hooks, mcp_argv, settings_argv, settings_env
from aos.agentlib.cli_stream import CAP, LIVE_HINT, MID_FLAGS, answer_text, run_claude_stream_mid


# ---------------------------------------------------------------- 非互動（畫面沒開）

def parent_death_term():
    """給 Popen 的 preexec_fn：子程式那側設 PR_SET_PDEATHSIG＝SIGTERM（11-10 坑-52），起它的執行緒一結束（這支被 kill -9、OOM）CLI 就收 TERM。
    設完 getppid 跟 fork 前記的不同＝父在設之前就死了，直接退。非 Linux、載不到 libc＝回 None（不設、不報錯）。
    PDEATHSIG 看的是 fork 的那條執行緒：這檔的 Popen 都在呼叫者的主執行緒起（Timer 執行緒只負責 kill）。"""
    if not sys.platform.startswith("linux"):
        return None
    try:
        import ctypes
        prctl = ctypes.CDLL(None, use_errno=True).prctl          # fork 前先找好，子程式那側只呼叫
    except (ImportError, OSError, AttributeError):
        return None
    parent = os.getpid()
    args = (ctypes.c_int(1), ctypes.c_ulong(signal.SIGTERM),       # 1＝PR_SET_PDEATHSIG
            ctypes.c_ulong(0), ctypes.c_ulong(0), ctypes.c_ulong(0))

    def preexec():
        prctl(*args)
        if os.getppid() != parent:
            os._exit(128 + signal.SIGTERM)
    return preexec


def timeout_seconds(timeout_ms):
    # 0 表示不限時；缺省值仍由讀設定的呼叫者提供。
    return None if timeout_ms == 0 else timeout_ms / 1000


def run_cli(argv, prompt, ws, timeout_ms, handed=None, env=None):
    """起 CLI、題目從 stdin 給、等它做完；起來了就叫 handed（交出去了，11-03 aos-eca-turn 在這一刻收信）。
    env＝只加給這個 CLI 行程的環境（11-12 external-mcp：外部 server 的 bearer、憑證路徑；不動自己的 os.environ）。
    CLI 的 stderr 不攔、原樣透出（R10）。"""
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             text=True, cwd=ws, preexec_fn=parent_death_term(),
                             env=dict(os.environ, **env) if env else None)
    except FileNotFoundError:
        cli_base.die("CliMissing", "%s is not on PATH" % argv[0])
    if handed:
        handed()
    try:
        out, err = p.communicate(prompt, timeout=timeout_seconds(timeout_ms))
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        cli_base.die("CliFailed", "%s did not finish within %d s" % (argv[0], timeout_ms // 1000))
    return subprocess.CompletedProcess(argv, p.returncode, out, None)


def tail(text, n=300):
    return (text or "").strip()[-n:]


RESULT_GRACE_S = 3          # 第一個 result 之後等 CLI 自己退出的秒數；還沒退＝它在等背景任務（11-24 bgmail 報告第 7 節），整群收掉
STOP_GRACE_S = 2            # 收的時候 SIGTERM 之後等多久才 SIGKILL


def _descendants(pid):
    """pid 底下所有子孫（讀 /proc/*/stat 的 ppid）；背景任務可能自己開了新的行程群組，所以除了群組也逐支收。"""
    kids = {}
    for name in os.listdir("/proc") if os.path.isdir("/proc") else []:
        if not name.isdigit():
            continue
        try:
            with open("/proc/%s/stat" % name, encoding="utf-8", errors="replace") as f:
                text = f.read()
            ppid = int(text[text.rindex(")") + 2:].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        kids.setdefault(ppid, []).append(int(name))
    out, todo = [], [pid]
    while todo:
        for c in kids.get(todo.pop(), []):
            if c not in out:
                out.append(c)
                todo.append(c)
    return out


def stop_group(p):
    """收掉 claude 與它開的一切（背景 Bash 等）：它的行程群組（start_new_session 開的）加上逐支的子孫，先 SIGTERM，
    STOP_GRACE_S 秒後還在的 SIGKILL，最後 wait 收屍（不留殭屍）。本來就退了＝只收屍。"""
    if p.poll() is not None:
        return
    targets = _descendants(p.pid)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(p.pid, sig)
        except OSError:
            pass
        for pid in targets:
            try:
                os.kill(pid, sig)
            except OSError:
                pass
        try:
            p.wait(timeout=STOP_GRACE_S)
            if sig == signal.SIGTERM and not any(os.path.exists("/proc/%d" % t) for t in targets):
                return
        except subprocess.TimeoutExpired:
            pass
    p.wait()


def run_claude_stream(argv, prompt, ws, timeout_ms, live_path, handed=None, env=None):
    """claude -p --output-format stream-json：每行一邊寫進 live.jsonl（人可以 tail 著看），一邊收起來；回 (結束碼, 全部行)。
    題目寫進 stdin、關掉之後叫 handed（交出去了，11-03）。claude 的 stderr 不攔、原樣透出（R10）。
    11-25（使用者 11-24 批 bgmail 報告 ⑦⑧）：讀到第一個 type=result 就算這輪答完，不等 EOF——claude -p 開了背景任務會等它做完
    才退、還自己多開一輪寫同一段對話（實測）。result 之後 RESULT_GRACE_S 秒內自己退了＝照常；還沒退＝stop_group 整群收掉
    （背景任務跟著收），結束碼當 0（答完了才收的）。逾時也整群收。行程在自己的行程群組裡起（start_new_session）。"""
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             cwd=ws, preexec_fn=parent_death_term(), start_new_session=True,
                             env=dict(os.environ, **env) if env else None)
    except FileNotFoundError:
        cli_base.die("CliMissing", "%s is not on PATH" % argv[0])
    p.stdin.write(prompt.encode("utf-8"))
    p.stdin.close()
    if handed:
        handed()
    seconds = timeout_seconds(timeout_ms)
    deadline, lines = None if seconds is None else time.time() + seconds, []
    stopped, result_at, buf, fd = False, None, b"", p.stdout.fileno()
    sel = selectors.DefaultSelector()
    sel.register(fd, selectors.EVENT_READ)
    try:
        with open(live_path, "a", encoding="utf-8") as live:      # 10-28：只接不重寫（副產物留著）
            def got(raw):
                nonlocal result_at
                line = raw.decode("utf-8", errors="replace")
                lines.append(line)
                live.write(line)
                live.flush()
                if result_at is None and '"result"' in line:
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        ev = None
                    if isinstance(ev, dict) and ev.get("type") == "result":
                        result_at = time.time()
            while True:
                now = time.time()
                if deadline is not None and now > deadline:
                    break
                if result_at is not None and now - result_at > RESULT_GRACE_S:
                    stopped = True                        # 答完了、它還在（等背景任務）：不再讀，整群收掉
                    break
                if not sel.select(0.5):
                    continue
                chunk = os.read(fd, 65536)
                if not chunk:
                    if buf and result_at is None:
                        got(buf)                          # 最後一段沒換行也算一行
                    break
                if result_at is not None:
                    continue                              # 第一個 result 之後的輸出不收（不是這封信的回答），只等它退出
                buf += chunk
                while b"\n" in buf and result_at is None:
                    raw, buf = buf.split(b"\n", 1)
                    got(raw + b"\n")
    finally:
        sel.close()
        late = deadline is not None and time.time() > deadline
        if stopped or late or p.poll() is None:
            stop_group(p)
        else:
            p.wait()
        p.stdout.close()
    if late and result_at is None:
        cli_base.die("CliFailed", "%s did not finish within %d s" % (argv[0], timeout_ms // 1000))
    return (0 if result_at is not None and (stopped or p.returncode < 0) else p.returncode), lines


def warn_unconnected(init, external):
    """claude 開場的 init 事件列了每台 MCP server 的連線狀態：cli.json 列的外部 server 不是 connected＝提醒一行
    （CLI 自己不說，那台的工具只是不見）。只看 aos 交給它的外部 server；codex 的 --json 沒有這種事件。"""
    names = {s["name"] for s in external}
    servers = init.get("mcp_servers")
    for s in servers if isinstance(servers, list) else []:
        if isinstance(s, dict) and s.get("name") in names and s.get("status") != "connected":
            cli_base.warn("external MCP server %s was not connected when claude started (status %s)" % (s["name"], s.get("status")))


def live_cap(cfg):
    """cli.json 的 live_mail_cap（選填）：{"letters": 非負整數, "seconds": 非負整數}，缺的鍵用 CAP；格式不對＝CfgBad。"""
    cap = cfg.get("live_mail_cap", {})
    ok = isinstance(cap, dict) and set(cap) <= set(CAP) and all(
        isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in cap.values())
    if not ok:
        cli_base.die("CfgBad", 'cli.json: live_mail_cap must be {"letters": N, "seconds": N} (non-negative integers)')
    return dict(CAP, **cap)


def _fail(code, reason, info):
    try:
        cli_base.die(code, reason)
    except Exception as e:
        try:
            e.info = info
        except Exception:
            pass
        raise


def print_claude(cfg, cell, ws, stack, prompt, handed=None, sid=None, more=None):
    """sid＝要接的對話（ask 已認過是這台的）；空＝開新對話：我們產 id、--session-id 給，交出去那一刻先寫 session.txt 與
    記號檔再叫呼叫者的 handed（第一輪就失敗也不留孤兒，05）。沒給 sid（None）＝照舊讀 session.txt。
    more＝選填（midturn.More）：cli.json 寫 "live_mail": true 又給了 more＝stdin 用 stream-json、先不關，等回答時又來的信
    一封一行寫進去（cli_stream，wake-1114 主案 S）；回答＝cli_stream.answer_text（每個 result，加上取走中途信後先回的話）。其他情況照舊。"""
    live = more is not None and cfg.get("live_mail") is True
    cap = live_cap(cfg) if live else None
    sid = cell.read("session.txt") if sid is None else sid
    new = "" if sid else str(uuid.uuid4())
    # 10-27：改 stream-json（--verbose 是它要的），一行一事件寫進小格的 live.jsonl，人用 aos-agent watch 看得到它正在做什麼；
    # 回答取第一個帶 result 的那行（type: result；11-25 起，之前取最後一個）
    argv = ["claude", "-p", "--output-format", "stream-json", "--verbose"] + cfg.get("flags", []) + cfg.get("print_flags", [])
    argv += MID_FLAGS if live else []
    ext, env, _ = external_claude(cfg)
    argv += mcp_argv(cfg, cell, ws, stack, ext) + system_argv(cfg)
    if live:                                    # 長指令丟背景的提示（wake-1114 C4）；snapshot 沒關的話 --resume 時新加的 system 送不進去（2.1.325 實測）
        argv += ([] if "--system-prompt-snapshot" in argv else ["--system-prompt-snapshot", "off"]) + ["--append-system-prompt", LIVE_HINT]
    guard = guard_hooks(cfg)
    argv += settings_argv(cfg, {"hooks": guard} if guard else {})   # 定義帶了 settings＝併進這一個（11-13 第 1 題乙）
    env = dict(env or {}, **settings_env(cfg)) or None
    argv += ["--resume", sid] if sid else ["--session-id", new]

    def given():
        if new:
            mark_session("claude", cell, ws, new)
        if handed:
            handed()
    if live:
        code, lines = run_claude_stream_mid(argv, prompt, ws, timeout_seconds(cli_base.turn_timeout_ms(cfg)),
                                            cell.file("live.jsonl"), given, env, more, cap, parent_death_term())
    else:
        code, lines = run_claude_stream(argv, prompt, ws, cli_base.turn_timeout_ms(cfg), cell.file("live.jsonl"), given, env)
    out = None
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and "result" in ev and out is None:
            out = ev                              # 第一個 result（11-25 ⑧：之後的是 CLI 自己為背景任務多開的那輪）
        elif isinstance(ev, dict) and ev.get("type") == "system" and ev.get("subtype") == "init":
            warn_unconnected(ev, ext)
    stdout = "".join(lines)
    if out is None or code != 0 or out.get("is_error"):
        if sid and not transcripts("claude", sid):          # 以為是這台的、這台卻找不到：清掉，下一封開新的（05）
            drop_session(cell)
        elif new and not transcripts("claude", new):        # 新對話第一輪就失敗、CLI 沒建出來：清掉，下一輪直接開新的（TS 9）
            drop_session(cell)
    if out is None:
        _fail("CliFailed", "claude exited %d with no result in its output: %s" % (code, tail(stdout)),
              cli_fault.classify_claude(out, code, False, lines))
    if code != 0 or out.get("is_error"):   # result 行自己帶原因（例 模型不存在）就印它；stdout 尾巴會切在 JSON 中間
        why = out.get("result") if isinstance(out.get("result"), str) and out.get("result") else tail(stdout)
        _fail("CliFailed", "claude exited %d: %s" % (code, tail(why)),
              cli_fault.classify_claude(out, code, False, lines))
    res = out.get("result")
    if res is not None and not isinstance(res, str):
        _fail("CliFailed", "claude's result is not text (%s)" % type(res).__name__, None)
    got = out.get("session_id")
    if new and isinstance(got, str) and got and (got != new or cell.read("session.txt") != new):
        mark_session("claude", cell, ws, got)              # result 帶了不同的 id（或交出去時沒寫成）：以它為準
    if live:
        return answer_text(lines)
    return out.get("result") or ""


def print_codex(cfg, cell, ws, stack, prompt, handed=None, sid=None):
    """sid＝要接的對話（ask 已認過是這台的）；空＝開新對話。thread id 是 codex 自己產的：不管成敗，讀到 thread.started 就寫
    session.txt 與記號檔（05）。沒給 sid（None）＝照舊讀 session.txt。"""
    sid = cell.read("session.txt") if sid is None else sid
    main = codex_main_thread(sid) if sid else sid
    if main != sid:                              # session.txt 記到子 agent 的 thread（codex 不給 resume）：改記、改接它的主對話
        cli_base.warn("session.txt names a codex sub-agent thread %s; resuming its parent thread %s instead" % (sid, main))
        mark_session("codex", cell, ws, main)
        sid = main
    last = cell.file("last.txt")
    argv = ["codex", "exec"] + (["resume", sid] if sid else []) + cfg.get("flags", []) + cfg.get("print_flags", [])
    ext, env, _ = external_codex(cfg)
    argv += mcp_argv(cfg, cell, ws, stack) + ext + system_argv(cfg)
    argv += ["--skip-git-repo-check", "--json", "-o", last, "-"]     # 題目從 stdin 進（"-"）
    if os.path.exists(last):
        os.remove(last)
    r = run_cli(argv, prompt, ws, cli_base.turn_timeout_ms(cfg), handed, env)
    try:                                         # 10-28：--json 的事件（中間訊息、跑過的指令）也接進 live.jsonl 留著
        with open(cell.file("live.jsonl"), "a", encoding="utf-8") as live:
            live.write(r.stdout if not r.stdout or r.stdout.endswith("\n") else r.stdout + "\n")
    except OSError:
        pass
    thread = ""
    for line in r.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "thread.started":
            thread = ev.get("thread_id") or thread
    if not sid and thread:                       # 成敗之前就寫：第一輪就失敗也不留孤兒（05）
        mark_session("codex", cell, ws, thread)
    if r.returncode != 0 or not os.path.exists(last):
        if sid and not transcripts("codex", sid):           # 以為是這台的、這台卻找不到：清掉，下一封開新的（05）
            drop_session(cell)
        elif not sid and thread and not transcripts("codex", thread):   # 新 thread 第一輪就失敗、CLI 沒存檔：清掉（TS 9）
            drop_session(cell)
        cli_base.die("CliFailed", "codex exited %d (its reason is on stderr)" % r.returncode)
    with open(last, encoding="utf-8") as f:
        return f.read()
