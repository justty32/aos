# cli_session.py - 把 claude／codex 的一段對話接成工具：平常 agent 用非互動模式續同一個對話；人用 attach 接進互動畫面（tmux），跳出後畫面留著，agent 改從畫面送字
#
# 一個工具的小格（$AOS_STACK，act 給的是 $AOS_STACK/<工具名>/）裡放：
#   session.txt   這段對話的 id（claude 的 session id／codex 的 thread id）；第一次講完話才有
#   tty.sock      tmux 的 socket：互動畫面活著時，CLI 的終端就接在這裡（attach＝tmux -S tty.sock attach）
#   tmux.conf     attach 開畫面時寫的 tmux 設定（Ctrl-\ 跳出、不用 prefix）
#   turns.jsonl   互動畫面每講完一輪，hook 接一行 {"at", "text"}（agent 從這裡拿回答，不去解析畫面）
#   busy.txt      claude 的畫面正在跑一輪（有人送出、還沒講完）
#   lock          同一時間只有一個人用這段對話（agent 的一次呼叫、attach 開畫面）
#
# 兩條路（每次呼叫自己挑）：
#   畫面沒開 → 非互動：claude -p --resume <id>（第一次 --session-id <新 id>）、codex exec resume <id> -（第一次 codex exec -）
#   畫面開著 → 從 pty 送字：tmux paste-buffer 貼上＋Enter，等 hook 在 turns.jsonl 接一行（有人接著看、或 claude 正在跑一輪＝SessionBad）
# 錯：stderr 一行「cli_session: 代號 原因」、退 1。
import datetime, fcntl, json, os, shlex, subprocess, sys, time, uuid

HERE = os.path.dirname(os.path.abspath(__file__))     # agent 資料夾
TMUX_SESSION = "cli"


def die(code, reason):
    print("cli_session: %s %s" % (code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def load_cfg(tool_dir):
    path = os.path.join(tool_dir, "cli.json")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        die("CfgMissing", path)
    except (OSError, ValueError) as e:
        die("CfgBad", "%s：%s" % (path, e))
    if not isinstance(cfg, dict) or cfg.get("kind") not in ("claude", "codex"):
        die("CfgBad", "%s：kind 要是 claude 或 codex" % path)
    for k in ("flags", "print_flags"):
        if not isinstance(cfg.get(k, []), list) or not all(isinstance(a, str) for a in cfg.get(k, [])):
            die("CfgBad", "%s：%s 要是字串陣列" % (path, k))
    return cfg


class Cell:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        os.makedirs(self.path, exist_ok=True)

    def file(self, name):
        return os.path.join(self.path, name)

    def read(self, name):
        try:
            with open(self.file(name), encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""

    def write(self, name, text):                     # N-05：先寫 . 開頭的暫存檔再改名
        tmp = self.file("." + name)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, self.file(name))

    def turns(self):
        try:
            with open(self.file("turns.jsonl"), encoding="utf-8") as f:
                return [json.loads(l) for l in f if l.strip()]
        except FileNotFoundError:
            return []

    def lock(self):
        f = open(self.file("lock"), "w")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return f, False
        return f, True

    def tmux(self, *args, **kw):
        kw.setdefault("capture_output", True)
        kw.setdefault("text", True)
        return subprocess.run(["tmux", "-S", self.file("tty.sock")] + list(args), **kw)

    def alive(self):
        if not os.path.exists(self.file("tty.sock")):
            return False
        try:
            return self.tmux("has-session", "-t", TMUX_SESSION).returncode == 0
        except FileNotFoundError:            # 沒有 tmux：畫面不可能開著
            return False

    def clients(self):
        r = self.tmux("list-clients", "-t", TMUX_SESSION, "-F", "#{client_tty}")
        return [l for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []


# ---------------------------------------------------------------- 非互動（畫面沒開）

def run_cli(argv, prompt, ws, timeout_ms):
    try:
        return subprocess.run(argv, input=prompt, capture_output=True, text=True, cwd=ws,
                              timeout=timeout_ms / 1000, start_new_session=False)
    except FileNotFoundError:
        die("CliMissing", "%s 不在 PATH 上" % argv[0])
    except subprocess.TimeoutExpired:
        die("CliFailed", "%s 超過 %d 秒沒做完" % (argv[0], timeout_ms // 1000))


def tail(text, n=300):
    return (text or "").strip()[-n:]


def print_claude(cfg, cell, ws, prompt):
    sid = cell.read("session.txt")
    new = "" if sid else str(uuid.uuid4())
    argv = ["claude", "-p", "--output-format", "json"] + cfg.get("flags", []) + cfg.get("print_flags", [])
    argv += ["--resume", sid] if sid else ["--session-id", new]
    r = run_cli(argv, prompt, ws, cfg.get("timeout_ms", 600000))
    try:
        out = json.loads(r.stdout)
    except ValueError:
        die("CliFailed", "claude 結束碼 %d、輸出不是 JSON：%s %s" % (r.returncode, tail(r.stdout), tail(r.stderr)))
    if r.returncode != 0 or not isinstance(out, dict) or out.get("is_error"):
        die("CliFailed", "claude 結束碼 %d：%s %s" % (r.returncode, tail(r.stdout), tail(r.stderr)))
    if not sid:
        cell.write("session.txt", (out.get("session_id") or new) + "\n")
    return out.get("result") or ""


def print_codex(cfg, cell, ws, prompt):
    sid = cell.read("session.txt")
    last = cell.file("last.txt")
    argv = ["codex", "exec"] + (["resume", sid] if sid else []) + cfg.get("flags", []) + cfg.get("print_flags", [])
    argv += ["--skip-git-repo-check", "--json", "-o", last, "-"]     # 題目從 stdin 進（"-"）
    if os.path.exists(last):
        os.remove(last)
    r = run_cli(argv, prompt, ws, cfg.get("timeout_ms", 600000))
    thread = ""
    for line in r.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "thread.started":
            thread = ev.get("thread_id") or thread
    if r.returncode != 0 or not os.path.exists(last):
        die("CliFailed", "codex 結束碼 %d：%s" % (r.returncode, tail(r.stderr) or tail(r.stdout)))
    if not sid and thread:
        cell.write("session.txt", thread + "\n")
    with open(last, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- 從畫面送字（畫面開著）

def live(cfg, cell, prompt):
    who = cell.clients()
    if who:
        die("SessionBad", "有人接在畫面上（%s），等他跳出再叫" % ", ".join(who))
    if os.path.exists(cell.file("busy.txt")):
        die("SessionBad", "畫面上正在跑一輪（有人送出、還沒講完），等它講完再叫")
    seen = len(cell.turns())
    r = cell.tmux("load-buffer", "-b", "aos", "-", input=prompt)
    if r.returncode != 0:
        die("CliFailed", "tmux load-buffer：%s" % tail(r.stderr))
    cell.tmux("paste-buffer", "-p", "-d", "-b", "aos", "-t", TMUX_SESSION)   # -p：程式要的話包成 bracketed paste，多行不會半路送出
    time.sleep(0.3)
    cell.tmux("send-keys", "-t", TMUX_SESSION, "Enter")
    deadline = time.time() + cfg.get("timeout_ms", 600000) / 1000
    while time.time() < deadline:
        turns = cell.turns()
        if len(turns) > seen:
            return turns[-1].get("text") or ""
        if not cell.alive():
            die("CliFailed", "畫面在講完之前關掉了")
        time.sleep(0.2)
    die("ReplyMissing", "送出後 %d 秒還沒講完（可能卡在權限或信任的提問；attach 進去看）"
        % (cfg.get("timeout_ms", 600000) // 1000))


def call_main(tool_name):
    """工具入口：stdin {"prompt": "..."} → stdout 回答。"""
    tool_dir = os.path.join(HERE, "tools", tool_name)
    cfg = load_cfg(tool_dir)
    stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
    if not stack:
        die("StackMissing", "沒設定 AOS_STACK")
    try:
        args = json.loads(sys.stdin.read())
    except ValueError as e:
        die("PromptBad", "stdin 不是 JSON：%s" % e)
    if not isinstance(args, dict) or not isinstance(args.get("prompt"), str) or not args["prompt"].strip():
        die("PromptBad", "缺 prompt（要一個非空字串）")
    cell = Cell(stack)
    f, ok = cell.lock()
    if not ok:
        die("SessionBad", "這段對話有人在用（另一次呼叫、或 attach 正在開畫面）")
    with f:
        if cell.alive():
            text = live(cfg, cell, args["prompt"])
        elif cfg["kind"] == "claude":
            text = print_claude(cfg, cell, os.path.abspath(ws), args["prompt"])
        else:
            text = print_codex(cfg, cell, os.path.abspath(ws), args["prompt"])
    sys.stdout.write(text if text.endswith("\n") else text + "\n")


# ---------------------------------------------------------------- hook（互動畫面講完一輪時 CLI 叫的）

def last_text_from_transcript(path):
    """claude 的 transcript（jsonl）裡最後一則 assistant 的文字。"""
    text = ""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                if m.get("type") != "assistant":
                    continue
                content = (m.get("message") or {}).get("content")
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                    if parts:
                        text = "".join(parts)
    except OSError:
        pass
    return text


def hook_main(kind, cell_path, payload_arg=None):
    """claude：stdin 一份 hook JSON（UserPromptSubmit／Stop）；codex：notify 把 JSON 放在最後一個參數。
    hook 不准讓 CLI 出錯：任何問題都吞掉、退 0。"""
    try:
        cell = Cell(cell_path)
        raw = payload_arg if kind == "codex" else sys.stdin.read()
        p = json.loads(raw)
        if kind == "claude":
            if p.get("hook_event_name") == "UserPromptSubmit":
                cell.write("busy.txt", now() + "\n")
                return
            if p.get("hook_event_name") != "Stop":
                return
            text = p.get("last_assistant_message")
            if not isinstance(text, str):
                text = last_text_from_transcript(p.get("transcript_path") or "")
            sid = p.get("session_id")
        else:
            if p.get("type") != "agent-turn-complete":
                return
            text = p.get("last-assistant-message") or ""
            sid = p.get("thread-id") or p.get("thread_id")
        if sid and not cell.read("session.txt"):
            cell.write("session.txt", sid + "\n")
        with open(cell.file("turns.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": now(), "text": text}, ensure_ascii=False) + "\n")
        if os.path.exists(cell.file("busy.txt")):
            os.remove(cell.file("busy.txt"))
    except Exception:            # noqa: BLE001 —— hook 壞了也不能卡住 CLI
        pass


# ---------------------------------------------------------------- 開畫面（attach 用）

TMUX_CONF = """# tmux.conf - attach 開的畫面用的 tmux 設定（cli_session.py 每次開畫面時重寫）
set -g prefix None
unbind-key C-b
bind-key -n 'C-\\' detach-client
set -g escape-time 0
set -g focus-events on
set -g status-left ''
set -g status-right ' Ctrl-\\ 跳出（畫面留著）｜在裡面 /exit 或 /quit 結束 '
set -g status-right-length 80
"""


def hook_cmd(kind, cell):
    return [sys.executable, os.path.join(HERE, "cli_session.py"), "hook", kind, cell.path]


def start(cfg, cell, ws):
    """畫面沒開就開一個（在 tmux 裡、背景）；有對話就接著那段，沒有就開新的。"""
    if cell.alive():
        return False
    sid = cell.read("session.txt")
    if cfg["kind"] == "claude":
        cmd = " ".join(shlex.quote(a) for a in hook_cmd("claude", cell))
        hooks = {"hooks": {e: [{"hooks": [{"type": "command", "command": cmd}]}]
                           for e in ("UserPromptSubmit", "Stop")}}
        argv = ["claude"] + cfg.get("flags", []) + ["--settings", json.dumps(hooks)]
        argv += ["--resume", sid] if sid else []
    else:
        argv = ["codex"] + (["resume", sid] if sid else []) + cfg.get("flags", [])
        argv += ["-c", "notify=" + json.dumps(hook_cmd("codex", cell))]
    with open(cell.file("tmux.conf"), "w", encoding="utf-8") as f:
        f.write(TMUX_CONF)
    for name in ("busy.txt",):
        if os.path.exists(cell.file(name)):
            os.remove(cell.file(name))
    try:
        r = cell.tmux("-f", cell.file("tmux.conf"), "new-session", "-d", "-s", TMUX_SESSION,
                      "-x", "160", "-y", "45", "-c", ws, "--", *argv)
    except FileNotFoundError:
        die("TmuxMissing", "tmux 不在 PATH 上")
    if r.returncode != 0:
        die("CliFailed", "tmux new-session：%s" % tail(r.stderr))
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
        die("CliFailed", "%s 開起來就結束了（session id 不對？）" % argv[0])
    return True


def attach_main(argv):
    """attach [--ws WS] [-d] [工具名]：接進那個工具的互動畫面；沒開就先開。-d＝只開、不接。沒給工具名＝列出各工具的狀態。"""
    ws, detached, names = os.environ.get("AOS_WS") or ".", False, []
    it = iter(argv)
    for a in it:
        if a == "--ws":
            ws = next(it, None) or die("ArgumentsBad", "--ws 要一個路徑")
        elif a.startswith("--ws="):
            ws = a[5:]
        elif a == "-d":
            detached = True
        elif a in ("-h", "--help"):
            print(attach_main.__doc__)
            return
        elif a.startswith("-"):
            die("FlagUnknown", a)
        else:
            names.append(a)
    ws = os.path.abspath(ws)
    if not os.path.isdir(ws):
        die("WsMissing", ws)
    stack = os.environ.get("AOS_STACK") or os.path.join(ws, ".stack")
    tools_dir = os.path.join(HERE, "tools")
    known = sorted(t for t in os.listdir(tools_dir) if os.path.isfile(os.path.join(tools_dir, t, "cli.json")))
    if not names:
        for t in known:
            cell = Cell(os.path.join(stack, t))
            state = "畫面開著" if cell.alive() else "畫面沒開"
            if cell.alive() and cell.clients():
                state += "、有人接著"
            print("%-8s %s｜對話 %s｜%s" % (t, state, cell.read("session.txt") or "（還沒有）", cell.path))
        return
    if len(names) > 1:
        die("ArgumentsBad", "一次只接一個工具")
    if names[0] not in known:
        die("ToolUnknown", "%s（有：%s）" % (names[0], ", ".join(known)))
    cfg = load_cfg(os.path.join(tools_dir, names[0]))
    cell = Cell(os.path.join(stack, names[0]))
    f, ok = cell.lock()
    if not ok:
        print("agent 正在用這段對話，等它這次講完…", file=sys.stderr)
        fcntl.flock(f, fcntl.LOCK_EX)
    with f:
        opened = start(cfg, cell, ws)
    if detached:
        print("%s 的畫面%s：%s" % (names[0], "開好了" if opened else "本來就開著", cell.file("tty.sock")))
        return
    print("接進 %s（Ctrl-\\ 跳出、畫面留著；在裡面 /exit 結束）" % names[0], file=sys.stderr)
    os.execvp("tmux", ["tmux", "-S", cell.file("tty.sock"), "attach", "-t", TMUX_SESSION])


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "hook":
        hook_main(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    else:
        die("ArgumentsBad", "用法：cli_session.py hook <claude|codex> <小格> [payload]（工具入口與 attach 用 import 叫）")
