# cli_cell.py - cli_session 的小格：Cell（檔、鎖、畫面 tmux）、畫面 socket 位置、session.txt 與記號檔、認是不是這台的對話、transcripts symlink
import fcntl, glob, hashlib, json, os, re, socket, stat, subprocess

if __package__:
    from . import cli_base
    from .cli_base import TMUX_SESSION, tool_io
else:
    import cli_base
    from cli_base import TMUX_SESSION, tool_io


def machine_id():
    """這台機器的識別（記號檔的 machine，11-10 TS 8）：/etc/machine-id 的內容；讀不到或空的＝socket.gethostname()。"""
    try:
        with open("/etc/machine-id", encoding="utf-8") as f:
            mid = f.read().strip()
        if mid:
            return mid
    except (OSError, ValueError):
        pass
    return socket.gethostname()


TTY_HASH = 16                                            # 小格 realpath 的 sha256 取前幾個 hex（路徑短，遠低於 AF_UNIX 的 108 bytes）


def tty_base():
    """放畫面 socket 的資料夾：${XDG_RUNTIME_DIR}/aos-tty-<uid>；XDG_RUNTIME_DIR 沒設、不是資料夾、不可寫、或太長＝/tmp/aos-tty-<uid>。"""
    sub = "aos-tty-%d" % os.getuid()
    xdg = os.environ.get("XDG_RUNTIME_DIR") or ""
    if (os.path.isabs(xdg) and os.path.isdir(xdg) and os.access(xdg, os.W_OK | os.X_OK)
            and len(os.path.join(xdg, sub).encode()) <= 80):
        return os.path.join(xdg, sub)
    return os.path.join("/tmp", sub)


def tty_dir_ok(folder, make=False):
    """socket 的資料夾是這個使用者自己的（不是 symlink、owner 是自己）＝True；權限多給了就收回 0700。
    不在：make＝建（mode 0700）、否則 False。別人的或修不了＝False（不連別人的 tmux server）。"""
    try:
        st = os.lstat(folder)
    except FileNotFoundError:
        if not make:
            return False
        try:
            os.makedirs(folder, mode=0o700)
        except FileExistsError:
            pass
        except OSError:
            return False
        try:
            st = os.lstat(folder)
        except OSError:
            return False
    except OSError:
        return False
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
        return False
    if st.st_mode & 0o077:
        try:
            os.chmod(folder, 0o700)
        except OSError:
            return False
    return True


def tty_socket(cell_path, make=False):
    """小格的畫面（tmux）socket 在哪：唯一入口（11-10 TS 10）。一律回 <tty_base()>/<小格 realpath 的短雜湊>.sock，例外只有
    「那裡沒有、但另一個候選有」：XDG_RUNTIME_DIR 有無不同的行程（daemon、人的 shell）各算出 /run/user/… 或 /tmp/…，
    兩處都看；11-10 以前開的畫面在小格的 tty.sock（過渡，只認、不建）。make＝要開新畫面：只回首選、資料夾不在就建、
    不是自己的＝CellBad。資料夾不是自己的候選一律跳過。"""
    h = hashlib.sha256(os.path.realpath(cell_path).encode()).hexdigest()[:TTY_HASH] + ".sock"
    first = os.path.join(tty_base(), h)
    if make:
        if not tty_dir_ok(os.path.dirname(first), make=True):
            cli_base.die("CellBad", "%s is not a private folder of this user (cannot put the screen socket there)" % os.path.dirname(first))
        return first
    for cand in (first, os.path.join("/tmp", "aos-tty-%d" % os.getuid(), h), os.path.join(cell_path, "tty.sock")):
        try:
            is_sock = stat.S_ISSOCK(os.stat(cand).st_mode)
        except OSError:
            continue
        if is_sock and (cand.startswith(cell_path + os.sep) or tty_dir_ok(os.path.dirname(cand))):
            return cand
    return first


class Cell:
    def __init__(self, path, make=True):
        self.path = os.path.abspath(path)
        if make:                                     # make=False：只看不寫（attach 列表），小格不在就不建（11-11 tool-cells-lazy）
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

    def sock(self, make=False):
        """畫面的 tmux socket（tty_socket，11-10 TS 10；不在小格裡）。"""
        return tty_socket(self.path, make)

    def tmux(self, *args, new=False, **kw):
        """new＝開新畫面（start 的 new-session）：socket 放首選位置、資料夾不在就建。"""
        kw.setdefault("capture_output", True)
        kw.setdefault("text", True)
        return subprocess.run(["tmux", "-S", self.sock(new)] + list(args), **kw)

    def alive(self):
        if not os.path.exists(self.sock()):
            return False
        try:
            return self.tmux("has-session", "-t", TMUX_SESSION).returncode == 0
        except FileNotFoundError:            # 沒有 tmux：畫面不可能開著
            return False

    def clients(self):
        r = self.tmux("list-clients", "-t", TMUX_SESSION, "-F", "#{client_tty}")
        return [l for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []


def note_cell(cell, tool_dir, ws, stack):
    """工具、工作區、stack 都存相對小格的路徑，整樹搬遷後 open_cell 照新位置叫回。寫不成不擋正事。"""
    try:
        for name, value in (("tool.txt", tool_dir), ("ws.txt", ws), ("stack.txt", stack)):
            value = os.path.relpath(value, cell.path)
            if cell.read(name) != value:
                cell.write(name, value + "\n")
    except OSError:
        pass


def close(cell):
    """關掉畫面（tmux 和裡面的 CLI；對話是 CLI 邊講邊存的，id 留在 session.txt）。回 True＝本來開著。"""
    if not cell.alive():
        return False
    sock = cell.sock()
    cell.tmux("kill-server")
    if not sock.startswith(cell.path + os.sep):          # tmux 3.4 kill-server 後 socket 檔還留著：收掉（在小格的舊 socket 照舊不動）
        try:
            os.remove(sock)
        except OSError:
            pass
    return True


def account_dir(kind):
    """CLI 的帳號資料夾（對話存在它底下）：claude＝CLAUDE_CONFIG_DIR 或 ~/.claude；codex＝CODEX_HOME 或 ~/.codex。"""
    if kind == "claude":
        return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    return os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")


def transcripts(kind, sid):
    """CLI 自己存的這段對話（含中間訊息、工具呼叫等副產物）放在哪：claude ~/.claude/projects/*/<id>.jsonl、
    codex ~/.codex/sessions/年/月/日/rollout-*-<id>.jsonl。小格的 transcripts/ symlink 指到這裡（10-30；10-28 是 stop 時才拷）。"""
    if not sid:
        return []
    base = account_dir(kind)
    if kind == "claude":
        return sorted(glob.glob(os.path.join(base, "projects", "*", sid + ".jsonl")))
    return sorted(glob.glob(os.path.join(base, "sessions", "**", "*%s.jsonl" % sid), recursive=True))


def codex_parent(sid):
    """codex 這段 thread 是 multi-agent 的子 agent 就回它的父 thread id，不是（或讀不到）＝None。看 rollout 第一行 session_meta 的 payload：
    parent_thread_id，或 source.subagent.thread_spawn.parent_thread_id（codex 0.167.2 兩處都寫）。子 thread 的 notify 不是換對話，
    子 thread 也不能自己 resume（codex：cannot resume an unloaded multi-agent v2 sub-agent through its parent）。"""
    for path in transcripts("codex", sid)[:1]:
        try:
            with open(path, encoding="utf-8") as f:
                meta = json.loads(f.readline())
        except (OSError, ValueError):
            return None
        p = meta.get("payload") if isinstance(meta, dict) else None
        if not isinstance(p, dict):
            return None
        spawn = p.get("source")
        for key in ("subagent", "thread_spawn"):
            spawn = spawn.get(key) if isinstance(spawn, dict) else None
        parent = p.get("parent_thread_id") or (spawn.get("parent_thread_id") if isinstance(spawn, dict) else None)
        return parent if isinstance(parent, str) and parent and parent != sid else None
    return None


def codex_main_thread(sid):
    """sid 往上找到不是子 agent 的那段 thread（子 agent 還能再開子 agent）；sid 本來就是主對話＝回它自己。"""
    seen = set()
    while sid not in seen:
        seen.add(sid)
        sid = codex_parent(sid) or sid
    return sid


def mark_session(kind, cell, ws, sid):
    """寫 session.txt 與記號檔 .session_home（11-10 two-machines 05）。寫不成＝提醒一行、回 False（不擋正事：
    下一輪認不出是這台的，頂多開新對話）。"""
    try:
        cell.write("session.txt", sid + "\n")
        cell.write(".session_home", json.dumps({"session": sid, "ws": os.path.realpath(ws),
                                                "home": os.path.realpath(account_dir(kind)),
                                                "machine": machine_id()}, ensure_ascii=False) + "\n")
        return True
    except OSError as e:
        cli_base.warn("cannot write %s or .session_home: %s" % (cell.file("session.txt"), e))
        return False


def drop_session(cell):
    """刪 session.txt 與 .session_home（下一次開新對話）；本來不在不算錯，刪不掉不擋（下一次 session_here 照樣認不出）。"""
    for name in ("session.txt", ".session_home"):
        try:
            os.remove(cell.file(name))
        except FileNotFoundError:
            pass
        except OSError as e:
            cli_base.warn("cannot remove %s: %s" % (tool_io.place(cell.file(name)), tool_io.os_reason(e)))


def session_here(cfg, cell, ws, sid):
    """sid 這段對話是不是在這台（這個帳號資料夾、claude 再加這個工作區）開的（11-10 two-machines 05）：看記號檔，
    session 與 home 一樣、claude 的 ws 也一樣＝True；記號檔有 machine＝再比 machine_id()（11-10 TS 8；舊記號檔沒有＝不比，
    免得已在跑的全部開新對話）。記號檔不在或讀不懂、但 transcripts() 找得到＝功能上線前就在跑的，
    當這台的、補寫記號檔（過渡補丁）。不讀 CLI 的任何檔內容、不靠它的錯誤訊息。"""
    kind = cfg["kind"]
    try:
        with open(cell.file(".session_home"), encoding="utf-8") as f:
            mark = json.load(f)
    except (OSError, ValueError):
        mark = None
    if isinstance(mark, dict) and isinstance(mark.get("session"), str) and isinstance(mark.get("home"), str):
        return (mark["session"] == sid and mark["home"] == os.path.realpath(account_dir(kind))
                and (kind != "claude" or mark.get("ws") == os.path.realpath(ws))
                and ("machine" not in mark or mark["machine"] == machine_id())
                and stored_here(cfg, ws, sid))
    if stored_here(cfg, ws, sid):
        mark_session(kind, cell, ws, sid)
        return True
    return False


def stored_here(cfg, ws, sid):
    """CLI 自己存的這段對話在這台、這個工作區找得到嗎（11-10 TA 實跑：shutdown 打斷第一輪、claude 還沒建檔就被殺，
    記號檔相符卻 resume 不到＝下一封白掉；同帳號資料夾、專案換了路徑時過渡補丁會認錯）。只看檔在不在、不讀內容：
    claude＝<帳號資料夾>/projects/<工作區真實路徑把非英數字元換成 -（照 CLI 的命名，未經真機驗證）>/<id>.jsonl；
    codex＝transcripts() 找得到。flags 帶 --no-session-persistence＝CLI 不存檔，不看（當作在）。"""
    flags = list(cfg.get("flags", [])) + list(cfg.get("print_flags", []))
    if "--no-session-persistence" in flags:
        return True
    found = transcripts(cfg["kind"], sid)
    if cfg["kind"] != "claude":
        return bool(found)
    want = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(ws))
    return any(os.path.basename(os.path.dirname(f)) == want for f in found)


def transcript_link(cell_path, kind, sid):
    """小格裡指到 CLI 自己那份對話的 symlink 放哪：transcripts/<kind>-<id>.jsonl（10-30）。"""
    return os.path.join(cell_path, "transcripts", "%s-%s.jsonl" % (kind, sid))


def link_transcript(cell, kind):
    """拿到 session id 就在小格建 symlink 指到 CLI 自己的對話檔（10-30 C-16、C-17）。已有就不動；
    找不到（CLI 還沒寫、--no-session-persistence）就不建；任何問題都不擋正事。"""
    sid = cell.read("session.txt")
    if not sid:
        return
    link = transcript_link(cell.path, kind, sid)
    try:
        if os.path.lexists(link):
            return
        found = transcripts(kind, sid)
        if not found:
            return
        os.makedirs(os.path.dirname(link), exist_ok=True)
        tmp = os.path.join(os.path.dirname(link), "." + os.path.basename(link) + ".tmp")   # N-05：先建暫存再改名
        if os.path.lexists(tmp):
            os.remove(tmp)
        os.symlink(os.path.abspath(found[0]), tmp)
        os.replace(tmp, link)
    except OSError:
        pass
