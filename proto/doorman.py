#!/usr/bin/env python3
"""門房第一級（spec 13）——獨立腳本，只看不擋。

    python3 proto/doorman.py <根目錄> [--home <AOS_HOME>]

盯著根目錄底下的地（有 `.aos/layout.json` 的資料夾）出生與死亡：

- 出生 → 本子記一筆 `born`，登記表補一筆 `state:"stopped"`、`clock`／`pid`／`parent` 都 null
  （S-13-22／S-08-27：不起時鐘，起時鐘是父或使用者的事）。
- 死亡 → 本子記一筆 `gone`，那筆標 `stopped`、`pid` 清 null、`ext.died_at` 記時間；
  路徑不在而 pid 還活著＝孤魂，先補刀再改登記表（S-13-17）。

「只記不做」：事件一律先落到 `$AOS_HOME/.aos/doorman.jsonl`，再動登記表（S-13-08）。
登記表寫入走 `$AOS_HOME/.aos/registry.lock`，tmp → fsync → rename → fsync 目錄
（S-08-21／S-08-22／S-13-37）。鎖的協定跟 `proto/aosp/fsutil.py` 的 `Lock` 一模一樣，
沒有發明第二種鎖；這支不 import aosp 只是為了在另一隊改 aosp 時互不干擾。

純標準庫。inotify 用 ctypes 綁 libc；綁不上或監看數量爆掉就退回輪詢（S-13-32／S-13-33）。
"""
import argparse
import ctypes
import ctypes.util
import errno
import json
import os
import select
import signal
import struct
import sys
import tempfile
import time

# ---------------------------------------------------------------- 常數

AOS_DIR = ".aos"
LAYOUT = "layout.json"
LOG_NAME = "doorman.jsonl"          # 使用者指定的檔名（spec 13 寫的是 doorman.log，見 DOORMAN.md）
REGISTRY = "registry.json"
REGISTRY_LOCK = "registry.lock"

# 本子的六個短代碼（S-13-13）
BORN = "born"
BORN_INVALID = "born_invalid"
GONE = "gone"
WRITE = "write"
INBOX = "inbox"
FALLBACK = "fallback"

STOPPED = "stopped"
RUNNING = "running"
PENDING = "pending"

DEFAULT_DEPTH = 2
DEFAULT_POLL_MS = 1000
LOCK_WAIT_MS = 5000


# ---------------------------------------------------------------- 小工具

def now_iso():
    """ISO 8601 UTC 含毫秒。跟 aosp/fsutil.now_iso 同一個格式。"""
    t = time.time()
    ms = int((t - int(t)) * 1000)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%03dZ" % ms


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def _fsync_dir(dirpath):
    fd = os.open(dirpath, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_bytes(path, data):
    """tmp → fsync → rename → fsync 目錄。照 aosp/fsutil.atomic_write_bytes。"""
    path = os.path.abspath(path)
    d = os.path.dirname(path)
    ensure_dir(d)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.rename(tmp, path)
    _fsync_dir(d)


def write_json(path, obj):
    atomic_write_bytes(path, (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, NotADirectoryError):
        return default
    except (ValueError, OSError):
        return default


def append_line(path, text):
    """本子：一行一筆，O_APPEND 單次 write。照 aosp/fsutil.append_line。"""
    ensure_dir(os.path.dirname(path))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, (text.rstrip("\n") + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


class LockBusy(Exception):
    """鎖被別人佔住。"""


class Lock:
    """跟 aosp/fsutil.Lock 同一把鎖、同一個協定：O_EXCL 建檔、寫 {"pid","at"}、
    持鎖者死了就收回。門房與 daemon 共用 `$AOS_HOME/.aos/registry.lock`。"""

    def __init__(self, path, wait_ms=LOCK_WAIT_MS):
        self.path = path
        self.wait_ms = wait_ms
        self.fd = None

    def acquire(self):
        deadline = time.time() + self.wait_ms / 1000.0
        while True:
            try:
                ensure_dir(os.path.dirname(self.path))
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                os.write(self.fd, json.dumps({"pid": os.getpid(), "at": now_iso()}).encode())
                os.fsync(self.fd)
                return self
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
                if self._steal_if_dead():
                    continue
                if time.time() >= deadline:
                    raise LockBusy("鎖被佔住：%s" % self.path)
                time.sleep(0.02)

    def _steal_if_dead(self):
        info = read_json(self.path) or {}
        pid = info.get("pid")
        if not isinstance(pid, int):
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            try:
                os.unlink(self.path)
            except FileNotFoundError:
                pass
            return True
        except PermissionError:
            return False
        return False

    def release(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
        return False


def _proc_stat(pid):
    """/proc/<pid>/stat 切成 comm 之後的欄位。拿不到就 None。"""
    try:
        with open("/proc/%d/stat" % int(pid), "rb") as f:
            data = f.read()
    except (OSError, ValueError, TypeError):
        return None
    try:
        return data[data.rindex(b")") + 2:].split()
    except ValueError:
        return None


def proc_start(pid):
    """/proc/<pid>/stat 第 22 欄。拿不到就 None。照 aosp/registry.proc_start。"""
    rest = _proc_stat(pid)
    if rest is None:
        return None
    try:
        return int(rest[19])
    except (ValueError, IndexError):
        return None


def is_zombie(pid):
    """殭屍禁止算成活著（S-08-90）：pid 還在、行程已經死了只是沒被收屍。"""
    rest = _proc_stat(pid)
    if not rest:
        return False
    return rest[0] == b"Z"


def alive(pid, pid_start=None):
    """判活：pid 與 pid_start 都吻合才算（S-08-68，免得補刀打到無辜的人）。"""
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if is_zombie(pid):
        return False
    if pid_start is not None:
        cur = proc_start(pid)
        # 登記表可能存字串（spec）或整數（proto），兩邊都拿來比
        if cur is not None and str(cur) != str(pid_start):
            return False
    return True


# ---------------------------------------------------------------- inotify（ctypes 綁 libc）

IN_ACCESS = 0x00000001
IN_MODIFY = 0x00000002
IN_ATTRIB = 0x00000004
IN_CLOSE_WRITE = 0x00000008
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_DELETE_SELF = 0x00000400
IN_MOVE_SELF = 0x00000800
IN_IGNORED = 0x00008000
IN_ONLYDIR = 0x01000000
IN_EXCL_UNLINK = 0x04000000
IN_ISDIR = 0x40000000
IN_Q_OVERFLOW = 0x00004000

IN_NONBLOCK = 0o4000
IN_CLOEXEC = 0o2000000

WATCH_MASK = (IN_CREATE | IN_MOVED_TO | IN_DELETE | IN_MOVED_FROM |
              IN_DELETE_SELF | IN_MOVE_SELF | IN_CLOSE_WRITE | IN_EXCL_UNLINK)

_EVENT_HDR = struct.Struct("iIII")   # wd, mask, cookie, len


class WatchLimit(Exception):
    """inotify 監看數量碰到系統上限（ENOSPC）。"""


class Inotify:
    """libc 的 inotify_init1／inotify_add_watch／read，用 ctypes 綁。"""

    def __init__(self):
        name = ctypes.util.find_library("c") or "libc.so.6"
        self.libc = ctypes.CDLL(name, use_errno=True)
        self.libc.inotify_init1.argtypes = [ctypes.c_int]
        self.libc.inotify_init1.restype = ctypes.c_int
        self.libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        self.libc.inotify_add_watch.restype = ctypes.c_int
        self.libc.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
        self.libc.inotify_rm_watch.restype = ctypes.c_int
        fd = self.libc.inotify_init1(IN_NONBLOCK | IN_CLOEXEC)
        if fd < 0:
            raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()), "inotify_init1")
        self.fd = fd
        self.wd_path = {}      # wd -> 路徑
        self.path_wd = {}      # 路徑 -> wd

    def add(self, path, mask=WATCH_MASK):
        if path in self.path_wd:
            return self.path_wd[path]
        wd = self.libc.inotify_add_watch(self.fd, os.fsencode(path), mask)
        if wd < 0:
            e = ctypes.get_errno()
            if e == errno.ENOSPC:
                raise WatchLimit(path)
            if e in (errno.ENOENT, errno.EACCES, errno.ENOTDIR):
                return None
            raise OSError(e, os.strerror(e), path)
        self.wd_path[wd] = path
        self.path_wd[path] = wd
        return wd

    def drop(self, path):
        wd = self.path_wd.pop(path, None)
        if wd is not None:
            self.wd_path.pop(wd, None)
            self.libc.inotify_rm_watch(self.fd, wd)

    def read(self, timeout_s):
        """等最多 timeout_s 秒，回傳 [(路徑, mask, 名字)]；沒事就空的。"""
        try:
            r, _, _ = select.select([self.fd], [], [], timeout_s)
        except (OSError, ValueError):
            return []
        if not r:
            return []
        out = []
        while True:
            try:
                buf = os.read(self.fd, 1 << 16)
            except BlockingIOError:
                break
            except OSError:
                break
            if not buf:
                break
            i = 0
            while i + _EVENT_HDR.size <= len(buf):
                wd, mask, _cookie, ln = _EVENT_HDR.unpack_from(buf, i)
                raw = buf[i + _EVENT_HDR.size:i + _EVENT_HDR.size + ln]
                name = os.fsdecode(raw.split(b"\0", 1)[0]) if ln else ""
                out.append((self.wd_path.get(wd), mask, name))
                if mask & IN_IGNORED:
                    p = self.wd_path.pop(wd, None)
                    if p is not None:
                        self.path_wd.pop(p, None)
                i += _EVENT_HDR.size + ln
            # 還有沒有下一批
            try:
                r, _, _ = select.select([self.fd], [], [], 0)
            except (OSError, ValueError):
                break
            if not r:
                break
        return out

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass


# ---------------------------------------------------------------- 版面檔檢查

def check_layout(land):
    """讀 `<地>/.aos/layout.json`。回傳 (ok, land_id, 壞在哪)。

    照 schemas/layout.schema.json 檢查，但 `land_id` 只警告不否決：
    今天 proto 的 `aos init` 根本不寫 land_id，嚴格照 S-13-49 的話一塊地都登記不了。
    要嚴格就下 `--strict-layout`。
    """
    p = os.path.join(land, AOS_DIR, LAYOUT)
    try:
        with open(p, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except FileNotFoundError:
        return False, None, "沒有 %s" % p
    except ValueError as e:
        return False, None, "不是合法 json：%s" % e
    except OSError as e:
        return False, None, "讀不到：%s" % e
    if not isinstance(obj, dict):
        return False, None, "最外層不是物件"
    for k in ("format_version", "layout_version"):
        v = obj.get(k)
        if not isinstance(v, int) or isinstance(v, bool) or v < 1:
            return False, None, "%s 缺了或不是 >=1 的整數" % k
    land_id = obj.get("land_id")
    if land_id is None:
        return True, None, "沒有 land_id（schema 要求，proto 的 aos init 不寫）"
    if not isinstance(land_id, str) or len(land_id) != 32 or \
            any(c not in "0123456789abcdef" for c in land_id):
        return True, None, "land_id 不是 32 個小寫 hex"
    return True, land_id, None


# ---------------------------------------------------------------- 門房本體

class Doorman:
    def __init__(self, root, home, depth=DEFAULT_DEPTH, poll_ms=DEFAULT_POLL_MS,
                 force_poll=False, strict_birth=False, strict_layout=False,
                 say=None):
        self.root = os.path.realpath(root)
        self.home = os.path.realpath(home)
        self.depth = depth
        self.poll_ms = poll_ms
        self.strict_birth = strict_birth
        self.strict_layout = strict_layout
        self.say = say or (lambda s: None)

        self.home_aos = os.path.join(self.home, AOS_DIR)
        self.registry = os.path.join(self.home_aos, REGISTRY)
        self.lock_path = os.path.join(self.home_aos, REGISTRY_LOCK)
        self.log_path = os.path.join(self.home_aos, LOG_NAME)

        self.seen = set()          # 現在認定活著的地
        self.invalid = {}          # 記過 born_invalid 的地 -> 壞在哪（同樣的壞法不重記）
        self.ino = None
        self.mode = "poll" if force_poll else "inotify"
        self.fallback_reason = None
        self.counts = {BORN: 0, BORN_INVALID: 0, GONE: 0, FALLBACK: 0}

    # ---------- 本子 ----------
    def log(self, kind, path, ext=None):
        """一行一事件。`kind` 是使用者要的欄名，`event` 是 schema 要的欄名，
        兩個同值一起寫（DOORMAN.md 第一條）。"""
        line = {"at": now_iso(), "kind": kind, "event": kind, "path": path}
        if ext:
            line["ext"] = ext
        append_line(self.log_path, json.dumps(line, ensure_ascii=False, sort_keys=False))
        self.counts[kind] = self.counts.get(kind, 0) + 1
        return line

    # ---------- 登記表 ----------
    def _load_reg(self):
        reg = read_json(self.registry, None)
        if not isinstance(reg, dict) or not isinstance(reg.get("entries"), list):
            reg = {"format_version": 1, "daemon_pid": None, "entries": []}
        return reg

    @staticmethod
    def _find(reg, path):
        for e in reg["entries"]:
            if e.get("path") == path:
                return e
        return None

    def _save_reg(self, reg):
        write_json(self.registry, reg)

    def register_birth(self, land, land_id):
        """出生 → 補一筆 stopped（S-13-22／S-08-27）。同 path 只准一筆（S-08-11）。"""
        ensure_dir(self.home_aos)
        with Lock(self.lock_path):
            reg = self._load_reg()
            e = self._find(reg, land)
            now = now_iso()
            if e is None:
                e = {
                    "path": land,
                    "pid": None,
                    "pid_start": None,
                    "land_id": land_id,
                    "state": STOPPED,
                    "clock": None,
                    "budget": None,
                    "parent": None,
                    "registered_at": now,
                    "updated_at": now,
                    "ext": {"by": "doorman"},
                }
                reg["entries"].append(e)
                fresh = True
            else:
                # 同一塊地又生一次：不新增第二筆，也不覆寫別人（run／daemon）寫的鐘。
                ext = e.get("ext")
                if not isinstance(ext, dict):
                    ext = {}
                ext.pop("died_at", None)
                ext.pop("died_by", None)
                ext["reborn_at"] = now
                e["ext"] = ext
                if land_id is not None:
                    e["land_id"] = land_id
                e["updated_at"] = now
                fresh = False
            self._save_reg(reg)
            return fresh

    def register_death(self, land):
        """死亡 → 有活 pid 先補刀，再標 stopped 並記 ext.died_at。

        回傳 (有沒有那筆, 補刀掉的 pid 或 None)。
        """
        ensure_dir(self.home_aos)
        killed = None
        with Lock(self.lock_path):
            reg = self._load_reg()
            e = self._find(reg, land)
            if e is None:
                return False, None
            pid, pid_start = e.get("pid"), e.get("pid_start")
            if alive(pid, pid_start):
                killed = self._reap(pid)
            now = now_iso()
            e["state"] = STOPPED
            e["pid"] = None
            e["pid_start"] = None
            e["updated_at"] = now
            ext = e.get("ext")
            if not isinstance(ext, dict):
                ext = {}
            ext["died_at"] = now
            ext["died_by"] = "doorman"
            if killed is not None:
                ext["killed_pid"] = killed
            ext.pop("reborn_at", None)
            e["ext"] = ext
            self._save_reg(reg)
        return True, killed

    @staticmethod
    def _reap(pid):
        """孤魂補刀（S-13-17）：地都沒了，控制收件匣也跟著沒了，只能直接送訊號。
        對整個行程群組送（S-08-77），同步子孫才不會變孤兒繼續改檔案。
        除了「停掉這支行程」以外什麼都不做。"""
        try:
            pgid = os.getpgid(pid)
        except OSError:
            pgid = None
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                if pgid is not None and pgid != os.getpgid(0):
                    os.killpg(pgid, sig)
                else:
                    os.kill(pid, sig)
            except (ProcessLookupError, PermissionError, OSError):
                break
            deadline = time.time() + (0.5 if sig == signal.SIGTERM else 0.5)
            while time.time() < deadline:
                if not alive(pid):
                    return pid
                time.sleep(0.02)
        return None if alive(pid) else pid

    # ---------- 掃描 ----------
    def _dirs(self):
        """root 底下 depth 層以內的目錄（含 root），不進 `.aos/`、不跟 symlink。
        S-13-31 說不准遞迴監看整棵樹，所以這裡有明確的層數上限。"""
        out = [self.root]
        frontier = [(self.root, 0)]
        while frontier:
            d, lv = frontier.pop()
            if lv >= self.depth:
                continue
            try:
                with os.scandir(d) as it:
                    for ent in it:
                        if ent.name == AOS_DIR:
                            continue
                        try:
                            if not ent.is_dir(follow_symlinks=False):
                                continue
                        except OSError:
                            continue
                        p = os.path.join(d, ent.name)
                        out.append(p)
                        frontier.append((p, lv + 1))
            except (FileNotFoundError, NotADirectoryError, PermissionError):
                continue
        return out

    def _scan_lands(self):
        return {d for d in self._dirs() if os.path.isfile(os.path.join(d, AOS_DIR, LAYOUT))}

    def _under_root(self, p):
        return p == self.root or p.startswith(self.root + os.sep)

    def _registry_paths(self):
        out = {}
        for e in self._load_reg()["entries"]:
            p = e.get("path")
            if isinstance(p, str) and self._under_root(p):
                out[p] = e
        return out

    # ---------- 一次巡邏 ----------
    def sweep(self, triggers=None, birth_filter=None):
        """掃一遍：新出現的記 born、不見了的記 gone。triggers 只是拿來寫進 ext。
        birth_filter 是一組准出生的路徑（--strict-birth 用），None＝不擋。"""
        triggers = triggers or {}
        found = self._scan_lands()
        regs = self._registry_paths()
        for gone_bad in set(self.invalid) - found:
            self.invalid.pop(gone_bad, None)

        # 出生
        for land in sorted(found - self.seen):
            if birth_filter is not None and land not in birth_filter:
                continue
            self._birth(land, triggers.get(land, "sweep"))

        # 死亡：看過的 + 登記表上在 root 底下的，都算候選
        candidates = set(self.seen) | set(regs)
        for land in sorted(candidates - found):
            e = regs.get(land)
            if land not in self.seen:
                # 門房沒看過它出生（重啟後接手）。已經標過死的就別再記一次。
                ext = e.get("ext") if isinstance(e, dict) else None
                if isinstance(ext, dict) and ext.get("died_at"):
                    continue
                if e is None:
                    continue
            self._death(land, triggers.get(land, "sweep"))
        return found

    def _birth(self, land, trigger):
        ok, land_id, why = check_layout(land)
        if not ok or (self.strict_layout and land_id is None):
            # S-13-49：讀不到或不合 schema 就不登記，只記一筆 born_invalid。
            # 同一塊壞地每輪掃描都記一次會把本子洗版，所以壞法沒變就不重記。
            why = why or "沒有 land_id"
            if self.invalid.get(land) == why:
                return
            self.invalid[land] = why
            self.log(BORN_INVALID, land, {"trigger": trigger, "why": why})
            self.say("born_invalid %s（%s）" % (land, why))
            return
        self.invalid.pop(land, None)
        ext = {"trigger": trigger}
        if land_id is not None:
            ext["land_id"] = land_id
        elif why:
            ext["warn"] = why
        # 先落本子，再改登記表（S-13-08：只記不做，記在前）
        self.log(BORN, land, ext)
        self.seen.add(land)
        fresh = self.register_birth(land, land_id)
        self.say("born %s%s" % (land, "" if fresh else "（同一筆，重生）"))

    def _death(self, land, trigger):
        reg = self._load_reg()
        e = self._find(reg, land)
        pid = e.get("pid") if e else None
        ext = {"trigger": trigger}
        if e is None:
            ext["registered"] = False
        elif alive(pid, e.get("pid_start")):
            ext["orphan_pid"] = pid
        self.log(GONE, land, ext)
        self.seen.discard(land)
        self.invalid.pop(land, None)
        found, killed = self.register_death(land)
        if killed is not None:
            self.log(GONE, land, {"trigger": "reap", "killed_pid": killed})
            self.say("gone %s（孤魂 pid %d 已補刀）" % (land, killed))
        else:
            self.say("gone %s%s" % (land, "" if found else "（登記表沒有這筆）"))

    # ---------- 監看 ----------
    def _watch_targets(self):
        t = set(self._dirs())
        # 每個候選目錄底下的 .aos/ 也要盯：layout.json 是在那裡面改名就位的，
        # 不盯的話 S-13-47 那個 IN_MOVED_TO 根本收不到。
        for d in list(t):
            a = os.path.join(d, AOS_DIR)
            if os.path.isdir(a):
                t.add(a)
        for land in self.seen:
            t.add(land)
            t.add(os.path.join(land, AOS_DIR))
        return t

    def _refresh_watches(self):
        if self.ino is None:
            return
        want = self._watch_targets()
        for p in sorted(want):
            if p in self.ino.path_wd:
                continue
            try:
                self.ino.add(p)
            except WatchLimit:
                self.log(FALLBACK, self.root,
                         {"why": "inotify 監看數量碰到系統上限（ENOSPC）",
                          "watches": len(self.ino.path_wd)})
                self.say("監看爆掉，退回輪詢（S-13-32）")
                self.ino.close()
                self.ino = None
                self.mode = "poll"
                self.fallback_reason = "watch_limit"
                return
        for p in list(self.ino.path_wd):
            if p not in want:
                self.ino.drop(p)

    def _start_inotify(self):
        try:
            self.ino = Inotify()
        except (OSError, AttributeError) as e:
            self.log(FALLBACK, self.root, {"why": "綁不上 libc 的 inotify：%s" % e})
            self.say("綁不上 inotify，退回輪詢：%s" % e)
            self.mode = "poll"
            self.fallback_reason = "no_inotify"
            return
        self._refresh_watches()

    def _triggers_from(self, events):
        """把 inotify 事件翻成「哪塊地被什麼動作碰到」。"""
        out = {}
        for path, mask, name in events:
            if path is None:
                continue
            child = os.path.join(path, name) if name else path
            base = os.path.basename(path)
            if base == AOS_DIR and name == LAYOUT:
                land = os.path.dirname(path)
            elif name == AOS_DIR:
                land = path
            elif mask & (IN_DELETE_SELF | IN_MOVE_SELF):
                land = os.path.dirname(path) if base == AOS_DIR else path
            elif mask & IN_ISDIR:
                land = child
            else:
                land = path
            kinds = []
            if mask & IN_MOVED_TO:
                kinds.append("inotify:moved_to")
            if mask & IN_CREATE:
                kinds.append("inotify:create")
            if mask & IN_CLOSE_WRITE:
                kinds.append("inotify:close_write")
            if mask & (IN_DELETE | IN_MOVED_FROM):
                kinds.append("inotify:delete")
            if mask & (IN_DELETE_SELF | IN_MOVE_SELF):
                kinds.append("inotify:delete_self")
            if mask & IN_Q_OVERFLOW:
                kinds.append("inotify:overflow")
            if kinds:
                out.setdefault(land, kinds[0])
        return out

    # ---------- 主迴圈 ----------
    def run(self, duration_ms=None, once=False):
        ensure_dir(self.home_aos)
        if self.mode == "inotify":
            self._start_inotify()
        self.say("門房起來了：根目錄 %s，家 %s，方式 %s" % (self.root, self.home, self.mode))

        # 開場先掃一遍（門房不是永遠都在，重啟時要把積欠的生死補上）
        self.sweep()
        self._refresh_watches()
        if once:
            return 0

        stop = {"hit": None}

        def _on(signum, _frame):
            stop["hit"] = signum

        for s in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(s, _on)
            except (ValueError, OSError):
                pass

        deadline = None if duration_ms is None else time.time() + duration_ms / 1000.0
        wait_s = self.poll_ms / 1000.0
        while not stop["hit"]:
            if deadline is not None and time.time() >= deadline:
                break
            triggers = {}
            if self.ino is not None:
                slice_s = wait_s if deadline is None else max(0.0, min(wait_s, deadline - time.time()))
                events = self.ino.read(slice_s)
                if events:
                    # 一批事件先攢起來一起處理（S-13-28：不准一個通知推一次動作）
                    time.sleep(0.02)
                    events += self.ino.read(0)
                    triggers = self._triggers_from(events)
            else:
                slice_s = wait_s if deadline is None else max(0.0, min(wait_s, deadline - time.time()))
                if slice_s > 0:
                    time.sleep(slice_s)
            if self.strict_birth:
                # S-13-47：只有這一批事件裡真的看到 layout.json 原子改名的才准出生。
                # 死亡不受影響。
                allow = {p for p, k in triggers.items() if k == "inotify:moved_to"}
                self.sweep(triggers, birth_filter=allow)
            else:
                self.sweep(triggers)
            self._refresh_watches()
        if self.ino is not None:
            self.ino.close()
        return 0


# ---------------------------------------------------------------- tmpfs 實測

def tmpfs_probe():
    """真的在 tmpfs 上跑一次 inotify：建 watch → 原子改名放進 layout.json →
    看 IN_MOVED_TO 有沒有回來。回傳 (結論字串, 細節 dict)。"""
    def probe(base):
        try:
            d = tempfile.mkdtemp(prefix="doorman-probe.", dir=base)
        except OSError as e:
            return None, "建不了暫存目錄：%s" % e
        try:
            ino = Inotify()
        except OSError as e:
            return None, "綁不上 inotify：%s" % e
        try:
            if ino.add(d) is None:
                return None, "加不了 watch"
            tmp = os.path.join(d, LAYOUT + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write('{"format_version":1,"layout_version":1}')
            os.rename(tmp, os.path.join(d, LAYOUT))
            got = ino.read(1.0)
            hit = any(name == LAYOUT and (mask & IN_MOVED_TO) for _p, mask, name in got)
            return hit, "收到 %d 個事件" % len(got)
        finally:
            ino.close()
            for f in os.listdir(d):
                try:
                    os.unlink(os.path.join(d, f))
                except OSError:
                    pass
            try:
                os.rmdir(d)
            except OSError:
                pass

    detail = {}
    tmpfs_dirs = [p for p in ("/dev/shm", "/run/user/%d" % os.getuid(), "/tmp")
                  if os.path.isdir(p) and _fstype(p) == "tmpfs"]
    disk_dir = None
    for p in (os.path.expanduser("~"), "/var/tmp"):
        if os.path.isdir(p) and _fstype(p) not in (None, "tmpfs"):
            disk_dir = p
            break

    if not tmpfs_dirs:
        return ".aos/ 在 tmpfs 時 inotify 一樣有效／無效：測不出來——這台機器上找不到掛著的 tmpfs。", detail
    t_dir = tmpfs_dirs[0]
    t_hit, t_note = probe(t_dir)
    detail["tmpfs"] = {"dir": t_dir, "fstype": "tmpfs", "moved_to": t_hit, "note": t_note}
    if disk_dir:
        d_hit, d_note = probe(disk_dir)
        detail["disk"] = {"dir": disk_dir, "fstype": _fstype(disk_dir),
                          "moved_to": d_hit, "note": d_note}
    verdict = "有效" if t_hit else "無效"
    line = (".aos/ 在 tmpfs 時 inotify 一樣%s：在 %s（tmpfs）原子改名放進 layout.json，"
            "IN_MOVED_TO %s收到%s" %
            (verdict, t_dir, "" if t_hit else "沒", ""))
    if disk_dir:
        line += "；同一份測試在 %s（%s，磁碟）%s收到，兩邊行為一樣" % (
            disk_dir, detail["disk"]["fstype"], "" if detail["disk"]["moved_to"] else "沒")
    line += "。"
    return line, detail


def _fstype(path):
    """從 /proc/self/mountinfo 找 path 落在哪個掛載點、是什麼檔案系統。"""
    try:
        with open("/proc/self/mountinfo", "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    real = os.path.realpath(path)
    best, best_len = None, -1
    for ln in lines:
        try:
            left, right = ln.split(" - ", 1)
            mp = left.split()[4]
            fstype = right.split()[0]
        except (ValueError, IndexError):
            continue
        if real == mp or real.startswith(mp.rstrip("/") + "/"):
            if len(mp) > best_len:
                best, best_len = fstype, len(mp)
    return best


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="doorman.py",
        description="門房第一級：盯著根目錄底下的地出生與死亡，只記不做（spec 13）。")
    ap.add_argument("root", nargs="?", help="根目錄：底下有 .aos/layout.json 的資料夾就是一塊地")
    ap.add_argument("--home", default=None, help="AOS_HOME（預設吃 $AOS_HOME，再預設 ~）")
    ap.add_argument("--depth", type=int, default=DEFAULT_DEPTH,
                    help="往根目錄底下找幾層地（預設 %d；S-13-31 不准遞迴整棵樹）" % DEFAULT_DEPTH)
    ap.add_argument("--poll", action="store_true", help="不用 inotify，直接輪詢")
    ap.add_argument("--poll-ms", type=int, default=DEFAULT_POLL_MS,
                    help="輪詢間隔／inotify 的保底巡邏間隔（毫秒，預設 %d）" % DEFAULT_POLL_MS)
    ap.add_argument("--once", action="store_true", help="掃一遍就退出（給測試與保底對帳用）")
    ap.add_argument("--for-ms", type=int, default=None, help="跑這麼多毫秒就自己退出")
    ap.add_argument("--strict-birth", action="store_true",
                    help="照 S-13-47：出生只認 layout.json 的原子改名（IN_MOVED_TO）")
    ap.add_argument("--strict-layout", action="store_true",
                    help="照 layout.schema.json 嚴格檢查：沒有 land_id 就 born_invalid")
    ap.add_argument("--tmpfs-note", action="store_true",
                    help="只印一句 tmpfs 上 inotify 有效與否的實測結果，不搬任何東西")
    ap.add_argument("--quiet", action="store_true", help="不印過程")
    a = ap.parse_args(argv)

    if a.tmpfs_note:
        line, detail = tmpfs_probe()
        sys.stdout.write(line + "\n")
        if not a.quiet and detail:
            sys.stdout.write("  細節：%s\n" % json.dumps(detail, ensure_ascii=False))
        return 0

    if not a.root:
        sys.stderr.write("錯誤：沒給根目錄\n下一步：python3 proto/doorman.py <根目錄> [--home <AOS_HOME>]\n")
        return 2
    if not os.path.isdir(a.root):
        sys.stderr.write("錯誤：根目錄不在或不是資料夾：%s\n下一步：先 mkdir -p %s，或改指一個已經在的資料夾\n"
                         % (a.root, a.root))
        return 2

    home = a.home or os.environ.get("AOS_HOME") or os.path.expanduser("~")
    def say(msg):
        if not a.quiet:
            sys.stdout.write(msg + "\n")
            sys.stdout.flush()

    d = Doorman(a.root, home, depth=a.depth, poll_ms=a.poll_ms, force_poll=a.poll,
                strict_birth=a.strict_birth, strict_layout=a.strict_layout, say=say)
    try:
        return d.run(duration_ms=a.for_ms, once=a.once)
    except LockBusy as e:
        sys.stderr.write("錯誤：拿不到登記表的鎖：%s\n下一步：看 %s 裡的 pid 還在不在，"
                         "在就等它做完，不在就刪掉那個檔\n" % (e, d.lock_path))
        return 75
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
