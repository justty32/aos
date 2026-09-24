"""daemon-home §2～§4 的池：宣告（pool.json）、一顆一檔（kids/<i>.json）、摘要（summary.json），
以及孩子怎麼拉（daemon-reconcile §5：只留 fd 0 一條 pipe，fd 1 接 /dev/null）。

這支只放資料形狀與檔案動作；誰在什麼時候改狀態由 aos_daemon_loop 決定。
"""
import collections
import contextlib
import io
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys

import aos_exec
import aos_home

POOL_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")
NAME_RE = re.compile(r"0|[1-9][0-9]*")
MAX_COUNT = 1000000                       # kernel-info §5 的 count 上限
COUNTERS = ("running", "restarting", "pending", "dead", "failed", "killing", "draining")
SUMMARY_KEYS = ("pool", "owner", "count", "ver")


def valid_pool_name(name):
    """kernel-info §5：1～64 bytes、只用 A-Z a-z 0-9 _ . -、不是 . 或 ..。"""
    return isinstance(name, str) and bool(POOL_RE.fullmatch(name)) and name not in (".", "..")


def members(count, skip):
    """成員＝不在 skip 裡的最小 count 個非負整數（kernel-info §3），由小到大。"""
    skip, found, i = set(skip), [], 0
    while len(found) < count:
        if i not in skip:
            found.append(i)
        i += 1
    return found


def pools_dir(home):
    return Path(home) / "pools"


def pool_dir(home, name):
    return pools_dir(home) / name


def kid_path(home, name, i):
    return pool_dir(home, name) / "kids" / ("%d.json" % i)


def log(code, msg):
    sys.stderr.write("aos-daemon: %s: %s\n" % (code, str(msg).replace("\n", " ")))


def signal_pid(pid, sig, group=False):
    try:
        (os.killpg if group else os.kill)(pid, sig)
    except ProcessLookupError:
        pass


def pid_exists(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class Kid:
    """一個號碼。沒檔、沒行程的新號也有一個（狀態 pending），只在記憶體。"""

    __slots__ = ("i", "pid", "gen", "state", "since", "exits", "streak", "last_exit", "next_at",
                 "member", "has_file", "handle", "started", "restarting", "queued", "due", "stage")

    def __init__(self, i, member=True):
        self.i, self.member = i, member
        self.pid = self.since = self.last_exit = self.next_at = None
        self.gen = self.exits = self.streak = 0
        self.state = "pending"
        self.has_file = False
        self.handle = None                 # aos_exec.Spawned；只有 running／killing 有
        self.started = None                # 這一代拉起來的 monotonic
        self.restarting = False            # 死過、重拉後還沒活滿 stable_ms
        self.queued = False                # 在池的「可以拉」佇列裡
        self.due = None                    # dead／failed 什麼時候（monotonic）可以再拉
        self.stage = None                  # 階梯走到哪：stop／term／kill

    def record(self):
        return {"pid": self.pid, "gen": self.gen, "state": self.state, "since": self.since,
                "exits": self.exits, "streak": self.streak, "last_exit": self.last_exit,
                "next_at": self.next_at}

    def load(self, record):
        """重開時沿用舊檔的 gen、exits、last_exit（handoff §2），其他歸成 pending。"""
        if isinstance(record, dict):
            for key in ("gen", "exits"):
                if type(record.get(key)) is int and record[key] >= 0:
                    setattr(self, key, record[key])
            if type(record.get("last_exit")) is int:
                self.last_exit = record["last_exit"]


def cats(kid):
    """這顆算進摘要的哪幾格；restarting 包含在 running 裡（daemon-home §4）。"""
    if kid.state == "killing":
        return ("killing",) if kid.member else ("draining",)
    if kid.state == "running":
        return ("running", "restarting") if kid.restarting else ("running",)
    return (kid.state,)


class Pool:
    """一池：宣告、成員集合、每號一個 Kid、各狀態計數（跟著轉移加減，不重數）。

    todo＝(要重算的池, 要發布的池) 兩個有序字典（當有序集合用），由 daemon 持有；
    dirty／changed 一設 True 就把自己登記進去，daemon 每圈只看登記過的池（review P9）。"""

    def __init__(self, home, decl, todo=None):
        self.home, self.name, self.decl = Path(home), decl["pool"], decl
        self.todo = todo
        self.members = set()
        self.kids = {}
        self.counts = dict.fromkeys(COUNTERS, 0)
        self.ready = collections.deque()   # 可以拉的號（先進先出）
        self._dirty = self._changed = False
        self.dirty = True                  # 成員要重算
        self.changed = True                # summary 要重寫
        self.in_rotation = False
        self.failing = False               # summary 正在寫失敗（一段連續失敗只印第一次）

    @property
    def dirty(self):
        return self._dirty

    @dirty.setter
    def dirty(self, value):
        self._dirty = bool(value)
        if value and self.todo is not None:
            self.todo[0][self] = None

    @property
    def changed(self):
        return self._changed

    @changed.setter
    def changed(self, value):
        self._changed = bool(value)
        if value and self.todo is not None:
            self.todo[1][self] = None

    @property
    def count(self):
        return self.decl["count"]

    def target(self, i):
        return self.decl["target"].replace("{name}", str(i), 1)

    def home_of(self, i):
        home = self.decl.get("home")
        return None if home is None else home.replace("{name}", str(i), 1)

    def add(self, kid):
        self.kids[kid.i] = kid
        for c in cats(kid):
            self.counts[c] += 1
        self.changed = True

    def drop(self, kid):
        for c in cats(kid):
            self.counts[c] -= 1
        del self.kids[kid.i]
        self.changed = True

    def update(self, kid, **changes):
        for c in cats(kid):
            self.counts[c] -= 1
        for key, value in changes.items():
            setattr(kid, key, value)
        for c in cats(kid):
            self.counts[c] += 1
        self.changed = True

    def summary(self, now):
        out = {key: self.decl.get(key) for key in SUMMARY_KEYS}
        out.update(self.counts)
        out["updated"] = now
        return out

    # ---- 檔案（影子：寫壞了只記一行，真正的狀態在記憶體＋pool.json，daemon-home §6） ----

    def write_kid(self, kid):
        try:
            aos_home.write_json(kid_path(self.home, self.name, kid.i), kid.record())
            kid.has_file = True
            return True
        except aos_home.HomeError as exc:
            log(exc.code, exc.msg)
            return False

    def delete_kid(self, kid):
        if kid.has_file:
            try:
                os.unlink(kid_path(self.home, self.name, kid.i))
            except FileNotFoundError:
                pass
            except OSError as exc:
                log("WriteFailed", "刪不掉 kids 檔：%s" % exc)
            kid.has_file = False

    def write_summary(self, now):
        """寫成功才清 changed（review P5）；失敗留著、回 False，由呼叫端下一圈再試。
        一段連續失敗只印第一次（訊息裡有隨機暫存檔名，不能拿訊息比），成功後再失敗才會再印。"""
        try:
            aos_home.write_json(pool_dir(self.home, self.name) / "summary.json", self.summary(now))
        except aos_home.HomeError as exc:
            if not self.failing:
                log(exc.code, exc.msg + "（之後每圈重試，成功前不再印）")
            self.failing = True
            return False
        self.failing = False
        self._changed = False
        return True


def write_pool_json(home, decl):
    path = pool_dir(home, decl["pool"])
    try:
        (path / "kids").mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise aos_home.HomeError("WriteFailed", "建不起池的資料夾 %s：%s" % (path, exc)) from exc
    aos_home.write_json(path / "pool.json", decl)


def remove_pool(home, name, quiet=False):
    """count 0 收完：先刪 summary.json（kernel 看它不在＝池已拿掉），再刪 pool.json，最後整個資料夾。
    照順序、前一步沒成功就不做下一步；回 True＝整個拿掉了，False＝沒拿掉（呼叫端記成待刪、下一圈再試，
    review P5）。quiet＝已經印過（待刪重試中），不再印。"""
    path = pool_dir(home, name)
    try:
        for leaf in ("summary.json", "pool.json"):
            try:
                os.unlink(path / leaf)
            except (FileNotFoundError, NotADirectoryError):
                pass
        try:
            shutil.rmtree(path)
        except (FileNotFoundError, NotADirectoryError):
            pass
        if os.path.lexists(path):
            raise OSError("資料夾還在")
    except OSError as exc:
        if not quiet:
            log("WriteFailed", "拿不掉池 %s：%s（之後每圈重試，成功前不再印）" % (path, exc))
        return False
    return True


def read_pool_json(path):
    """開機讀宣告；形狀不對就丟 ReadFailed（寧可不開也不要猜，D-55）。"""
    decl = aos_home.read_json(path)
    ok = (isinstance(decl, dict) and valid_pool_name(decl.get("pool")) and
          decl["pool"] == path.parent.name and isinstance(decl.get("owner"), str) and
          type(decl.get("count")) is int and 0 <= decl["count"] <= MAX_COUNT and
          isinstance(decl.get("skip"), list) and
          all(type(x) is int and x >= 0 for x in decl["skip"]) and
          type(decl.get("ver")) is int and
          (decl["count"] == 0 or isinstance(decl.get("target"), str)))
    if not ok:
        raise aos_home.HomeError("ReadFailed", "pool.json 形狀不對：%s" % path)
    decl.setdefault("dir_target", aos_exec.DEFAULT_DIR_TARGET)
    return decl


# ---- 拉孩子 ----

def _launch(argv, cwd, env, fin, fout, ferr, timeout_ms, exit_path, on_spawn=None,
            exit_append=False, *unused):
    """fd 0 一條控制 pipe（daemon 寫）；fd 1 接 /dev/null（daemon-reconcile §5）。"""
    try:
        p = subprocess.Popen(argv, cwd=cwd, env=env, process_group=0, close_fds=True,
                             stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=ferr,
                             bufsize=0)
    except (OSError, ValueError) as e:
        raise aos_exec.SpawnError("SpawnFailed", "無法啟動子程式：%s" % e)
    os.set_blocking(p.stdin.fileno(), False)
    return aos_exec.Spawned(p, exit_path, exit_append)


def spawn_child(target, dir_target=aos_exec.DEFAULT_DIR_TARGET):
    """同 aos_exec.spawn_target（每次重讀目標、同樣的讀驗與 SpawnFailed），只差 fd 1 的接法。"""
    p = os.path.abspath(target)
    if os.path.isdir(p):
        inst_path, base = os.path.join(p, dir_target), p
        if not os.path.isfile(inst_path):
            raise aos_exec.SpawnError("SpawnFailed", "資料夾 %s 裡沒有 %s" % (p, dir_target))
    elif p.endswith(".json"):
        inst_path, base = p, os.path.dirname(p)
    else:
        if not os.path.exists(p):
            raise aos_exec.SpawnError("SpawnFailed", "找不到 %s" % target)
        return _launch([p], os.path.dirname(p), dict(os.environ), None, None, None, 0, "")
    inst = aos_exec._load_control_inst(inst_path, base)
    diagnostic = io.StringIO()
    try:
        with contextlib.redirect_stderr(diagnostic):
            result = aos_exec._execute_inst(inst, 0, launcher=_launch)
    except ValueError as e:
        raise aos_exec.SpawnError("SpawnFailed", "FieldTypeMismatch: 無法執行 inst：%s" % e)
    if not isinstance(result, aos_exec.Spawned):
        raise aos_exec.SpawnError("SpawnFailed", diagnostic.getvalue().strip())
    return result


def exit_code(status):
    code = os.waitstatus_to_exitcode(status)
    return code if code >= 0 else 128 - code


def finish(kid, code):
    """收屍後：exit 檔照 inst 寫、關 fd 0。Popen 的 returncode 補上，免得它之後自己 waitpid。"""
    handle, kid.handle = kid.handle, None
    handle.process.returncode = code
    diagnostic = io.StringIO()
    with contextlib.redirect_stderr(diagnostic):
        _, kind = handle.finish(code)
    if kind == "aos":
        log("WriteFailed", "孩子 %d 的 exit 檔收尾失敗（退出碼 %d）：%s" %
            (kid.i, code, diagnostic.getvalue().strip()))
    try:
        handle.process.stdin.close()
    except OSError:
        pass


TERM, KILL = signal.SIGTERM, signal.SIGKILL
