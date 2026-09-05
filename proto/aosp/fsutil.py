"""原子寫、鎖、json 讀寫。純標準庫。"""
import errno
import json
import os
import time

FORMAT_VERSION = 1


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
    """tmp -> fsync -> rename -> fsync 目錄。WRITER-BRIEF 4.4。"""
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


def atomic_write_text(path, text):
    atomic_write_bytes(path, text.encode("utf-8"))


def write_json(path, obj):
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n")


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def append_line(path, text):
    """帳簿用：一行一筆，O_APPEND 單次 write。"""
    ensure_dir(os.path.dirname(path))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, (text.rstrip("\n") + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def now_iso():
    """ISO 8601 UTC 含毫秒。WRITER-BRIEF 3."""
    t = time.time()
    ms = int((t - int(t)) * 1000)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%03dZ" % ms


def new_id():
    """機器產的 id：32 個小寫 hex。"""
    return os.urandom(16).hex()


class LockBusy(Exception):
    """鎖被別人佔住。對應退出碼 75。"""


class Lock:
    """一塊地同時只准一支 exec／run。O_EXCL 建檔。"""

    def __init__(self, path, wait_ms=0):
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
        """持鎖者死了就把鎖收回來（FINDINGS: spec 沒講孤兒鎖）。"""
        info = read_json(self.path) or {}
        pid = info.get("pid")
        if not isinstance(pid, int):
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            try:
                os.unlink(self.path)
                return True
            except FileNotFoundError:
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
