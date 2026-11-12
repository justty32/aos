# cli_print.py - cli_session 的非互動那條路（畫面沒開）：claude -p／codex exec 起 CLI、等回答、記 session
import json, os, signal, subprocess, sys, threading, time, uuid

if __package__:
    from .cli_base import die
    from .cli_cell import drop_session, mark_session, transcripts
    from .cli_cfg import system_argv
    from .cli_mcp import external_claude, external_codex, guard_hooks, mcp_argv
else:
    from cli_base import die
    from cli_cell import drop_session, mark_session, transcripts
    from cli_cfg import system_argv
    from cli_mcp import external_claude, external_codex, guard_hooks, mcp_argv


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


def run_cli(argv, prompt, ws, timeout_ms, handed=None, env=None):
    """起 CLI、題目從 stdin 給、等它做完；起來了就叫 handed（交出去了，11-03 aos-eca-turn 在這一刻收信）。
    env＝只加給這個 CLI 行程的環境（11-12 external-mcp：外部 server 的 bearer、憑證路徑；不動自己的 os.environ）。
    CLI 的 stderr 不攔、原樣透出（R10）。"""
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             text=True, cwd=ws, preexec_fn=parent_death_term(),
                             env=dict(os.environ, **env) if env else None)
    except FileNotFoundError:
        die("CliMissing", "%s is not on PATH" % argv[0])
    if handed:
        handed()
    try:
        out, err = p.communicate(prompt, timeout=timeout_ms / 1000)
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        die("CliFailed", "%s did not finish within %d s" % (argv[0], timeout_ms // 1000))
    return subprocess.CompletedProcess(argv, p.returncode, out, None)


def tail(text, n=300):
    return (text or "").strip()[-n:]


def run_claude_stream(argv, prompt, ws, timeout_ms, live_path, handed=None, env=None):
    """claude -p --output-format stream-json：每行一邊寫進 live.jsonl（人可以 tail 著看），一邊收起來；回 (結束碼, 全部行)。
    題目寫進 stdin、關掉之後叫 handed（交出去了，11-03）。claude 的 stderr 不攔、原樣透出（R10）。"""
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             text=True, cwd=ws, preexec_fn=parent_death_term(),
                             env=dict(os.environ, **env) if env else None)
    except FileNotFoundError:
        die("CliMissing", "%s is not on PATH" % argv[0])
    p.stdin.write(prompt)
    p.stdin.close()
    if handed:
        handed()
    deadline, lines = time.time() + timeout_ms / 1000, []
    timer = threading.Timer(timeout_ms / 1000, p.kill)
    timer.start()
    try:
        with open(live_path, "a", encoding="utf-8") as live:      # 10-28：只接不重寫（副產物留著）
            for line in p.stdout:
                lines.append(line)
                live.write(line)
                live.flush()
        p.wait()
    finally:
        timer.cancel()
    if time.time() > deadline:
        die("CliFailed", "%s did not finish within %d s" % (argv[0], timeout_ms // 1000))
    return p.returncode, lines


def print_claude(cfg, cell, ws, stack, prompt, handed=None, sid=None):
    """sid＝要接的對話（ask 已認過是這台的）；空＝開新對話：我們產 id、--session-id 給，交出去那一刻先寫 session.txt 與
    記號檔再叫呼叫者的 handed（第一輪就失敗也不留孤兒，05）。沒給 sid（None）＝照舊讀 session.txt。"""
    sid = cell.read("session.txt") if sid is None else sid
    new = "" if sid else str(uuid.uuid4())
    # 10-27：改 stream-json（--verbose 是它要的），一行一事件寫進小格的 live.jsonl，人用 aos-agent watch 看得到它正在做什麼；
    # 回答取最後一個帶 result 的那行（type: result）
    argv = ["claude", "-p", "--output-format", "stream-json", "--verbose"] + cfg.get("flags", []) + cfg.get("print_flags", [])
    ext, env, _ = external_claude(cfg)
    argv += mcp_argv(cfg, cell, ws, stack, ext) + system_argv(cfg)
    guard = guard_hooks(cfg)
    argv += ["--settings", json.dumps({"hooks": guard})] if guard else []
    argv += ["--resume", sid] if sid else ["--session-id", new]

    def given():
        if new:
            mark_session("claude", cell, ws, new)
        if handed:
            handed()
    code, lines = run_claude_stream(argv, prompt, ws, cfg.get("timeout_ms", 600000), cell.file("live.jsonl"), given, env)
    out = None
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and "result" in ev:
            out = ev
    stdout = "".join(lines)
    if out is None or code != 0 or out.get("is_error"):
        if sid and not transcripts("claude", sid):          # 以為是這台的、這台卻找不到：清掉，下一封開新的（05）
            drop_session(cell)
        elif new and not transcripts("claude", new):        # 新對話第一輪就失敗、CLI 沒建出來：清掉，下一輪直接開新的（TS 9）
            drop_session(cell)
    if out is None:
        die("CliFailed", "claude exited %d with no result in its output: %s" % (code, tail(stdout)))
    if code != 0 or out.get("is_error"):   # result 行自己帶原因（例 模型不存在）就印它；stdout 尾巴會切在 JSON 中間
        why = out.get("result") if isinstance(out.get("result"), str) and out.get("result") else tail(stdout)
        die("CliFailed", "claude exited %d: %s" % (code, tail(why)))
    got = out.get("session_id")
    if new and isinstance(got, str) and got and (got != new or cell.read("session.txt") != new):
        mark_session("claude", cell, ws, got)              # result 帶了不同的 id（或交出去時沒寫成）：以它為準
    return out.get("result") or ""


def print_codex(cfg, cell, ws, stack, prompt, handed=None, sid=None):
    """sid＝要接的對話（ask 已認過是這台的）；空＝開新對話。thread id 是 codex 自己產的：不管成敗，讀到 thread.started 就寫
    session.txt 與記號檔（05）。沒給 sid（None）＝照舊讀 session.txt。"""
    sid = cell.read("session.txt") if sid is None else sid
    last = cell.file("last.txt")
    argv = ["codex", "exec"] + (["resume", sid] if sid else []) + cfg.get("flags", []) + cfg.get("print_flags", [])
    ext, env, _ = external_codex(cfg)
    argv += mcp_argv(cfg, cell, ws, stack) + ext + system_argv(cfg)
    argv += ["--skip-git-repo-check", "--json", "-o", last, "-"]     # 題目從 stdin 進（"-"）
    if os.path.exists(last):
        os.remove(last)
    r = run_cli(argv, prompt, ws, cfg.get("timeout_ms", 600000), handed, env)
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
        die("CliFailed", "codex exited %d (its reason is on stderr)" % r.returncode)
    with open(last, encoding="utf-8") as f:
        return f.read()
