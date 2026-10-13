"""daemon 的表：表上每個 loop 是一支子程序 `aos_loop.py`，daemon 只靠寫它的 ctl.json、讀它的 state.json 控制它。純標準庫。

`Table` 一個方法對一條指令（add／set／pause／resume／add_times／remove／state／get／list），加上 save／load 用的
`snapshot()`／`restore()`、收工用的 `shutdown()`。要等 loop 讀到才回的，回一個 ready()：還沒好回 None。
`DaemonError` 也在這裡（表、指令、config 共用）。規矩的白話說明在 aos_daemon 的檔頭。
"""
import itertools
import json
import os
import shutil
import signal
import subprocess
import sys
import time

import aos_inst
import aos_loop
from aos_directives import DirectiveError, locate, split_target, target_id
from aos_loop import load_config as _load_cfg, parse_ctl, read_state, reap, write_json

__all__ = ["DaemonError", "Table"]

AOS_LOOP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aos_loop.py")


class DaemonError(Exception):
    """config 或指令被拒。`code`＝錯誤代號，`msg`＝白話，`str(e)`＝「代號: 白話」。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.loads(f.read())
    except (OSError, ValueError):
        return None


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


# ---- 表 ----

class _Entry:
    """表上一個 loop：子程序＋它的 ctl.json、state.json 在哪。"""

    def __init__(self, ident, lcfg, ctl, state, workdir):
        self.id, self.lcfg, self.ctl, self.state, self.workdir = ident, lcfg, ctl, state, workdir
        self.proc = None
        self.removing = False

    def exited(self):
        return self.proc.returncode is not None

    def status(self):
        st = read_state(self.state)
        if st is None or st.get("pid") != self.proc.pid:
            st = {"id": self.id, "state": "stopped" if self.exited() else "starting"}
        st = dict(st, id=self.id)
        if self.exited() and st["state"] not in ("done", "stopped"):
            st["state"] = "stopped"
        return st

    def ctl_doc(self):
        doc = _read(self.ctl)
        return doc if isinstance(doc, dict) else {}

    def update_ctl(self, **fields):
        """讀現在的 ctl.json、改幾格、整份寫回（暫存再改名），回寫完的 mtime。"""
        doc = dict(self.ctl_doc(), **fields)
        try:
            write_json(self.ctl, doc)
            return os.stat(self.ctl).st_mtime
        except OSError as e:
            raise DaemonError("WriteFailed", "寫不了 %s：%s" % (self.ctl, e))

    def acked(self, mtime, settled=lambda st: True):
        """回 ready()：loop 讀到 mtime 那份 ctl（而且 settled）就回狀態物件，還沒回 None；行程結束了直接回。"""
        def ready():
            st = self.status()
            if self.exited():
                return st
            m = st.get("ctl_mtime")
            return st if isinstance(m, (int, float)) and m >= mtime and settled(st) else None
        return ready


class Table:
    def __init__(self, cfg):
        self.cfg = cfg
        self.entries = {}

    def _id(self, path):
        """指令的 id → (id, 檔的 realpath, 位置 tuple)。"""
        if not isinstance(path, str):
            raise DaemonError("FieldType", "id 要是 loop.json 的絕對路徑，不是 %r" % (path,))
        try:
            file, pos = split_target(path)
        except DirectiveError as e:
            raise DaemonError(e.code, e.msg)
        if not os.path.isabs(file):
            raise DaemonError("FieldType", "id 要是 loop.json 的絕對路徑，不是 %r" % (path,))
        real = os.path.realpath(file)
        return target_id(real, pos), real, pos

    def _get(self, path):
        ident = self._id(path)[0]
        e = self.entries.get(ident)
        if e is None or e.removing:
            raise DaemonError("NotFound", "沒有 loop %s" % ident)
        return e

    def _prepare(self, path):
        """驗一個 loop.json（或 inst.json）、決定 ctl／state 放哪，回 (_Entry, 包裝檔的內容或 None)。不動檔案。
        頂層沒有 "inst"、有 "argv" 的當 inst.json：包成只跑一次的 loop {"inst": {"$ref": 它}, "times": 1}。"""
        ident, real, pos = self._id(path)
        if not os.path.isfile(real):
            raise DaemonError("NotFound", "%s 不存在" % real)
        if ident in self.entries:
            raise DaemonError("Exists", "loop %s 已經在了" % ident)
        try:
            raw = locate(_read(real), pos, real)
        except DirectiveError:
            raw = None      # 讀不了、走不到：交給下面的 _load_cfg 報錯
        if isinstance(raw, dict) and "inst" not in raw and "argv" in raw:
            try:
                aos_inst.load(ident)
            except aos_inst.InstError as err:
                raise DaemonError(err.code, err.msg)
            lcfg = dict(aos_loop.DEFAULTS, times=1)
            return _Entry(ident, lcfg, None, None, None), {"inst": {"$ref": ident}, "times": 1}
        _, lcfg = _load_cfg(ident, err=DaemonError)
        wrap = None
        if lcfg["ctl"] is None or lcfg["state"] is None:
            wrap = {k: {"$ref": target_id(real, pos + (k,))} for k in raw}
        return _Entry(ident, lcfg, lcfg["ctl"], lcfg["state"], None), wrap

    def _start(self, e, wrap, ctl=None):
        start = e.id
        if wrap is not None:
            os.makedirs(self.cfg["work_dir"], exist_ok=True)
            for n in itertools.count(1):
                d = os.path.join(self.cfg["work_dir"], str(n))
                try:
                    os.mkdir(d)
                    break
                except FileExistsError:
                    continue
            e.workdir = d
            e.ctl = e.ctl or os.path.join(d, "ctl.json")
            e.state = e.state or os.path.join(d, "state.json")
            start = os.path.join(d, "loop.json")
            write_json(start, dict(wrap, ctl=e.ctl, state=e.state))
            if ctl is None and not os.path.exists(e.ctl):
                ctl = {}
        if ctl is not None:
            write_json(e.ctl, ctl)
        e.proc = subprocess.Popen([sys.executable, AOS_LOOP, start], start_new_session=True)
        self.entries[e.id] = e

    def add(self, path, ctl=None):
        e, wrap = self._prepare(path)
        try:
            self._start(e, wrap, ctl)
        except OSError as err:
            raise DaemonError("WriteFailed", "起不了 %s：%s" % (e.id, err))
        return e.id

    def set(self, path, how):
        e = self._get(path)
        if not isinstance(how, dict) or not set(how) <= {"times", "interval_ms", "interval_mode"}:
            raise DaemonError("FieldType", "how 只能有 times／interval_ms／interval_mode，不是 %r" % (how,))
        try:
            parse_ctl(how)
        except ValueError as err:
            raise DaemonError("FieldType", str(err))
        return e.acked(e.update_ctl(**how))

    def pause(self, path, wait=True):
        e = self._get(path)
        _bool(wait)
        return e.acked(e.update_ctl(paused={"val": True, "now": not wait}), lambda st: st.get("state") == "paused")

    def resume(self, path):
        e = self._get(path)
        return e.acked(e.update_ctl(paused=False))

    def add_times(self, path, delta):
        if not aos_loop._int(delta, -2 ** 63):
            raise DaemonError("FieldType", "delta 要是整數，不是 %r" % (delta,))
        e = self._get(path)
        doc = e.ctl_doc()
        times = doc["times"] if "times" in doc else e.lcfg["times"]
        if times is None:
            raise DaemonError("Conflict", "%s 是不限次數，不能加減" % e.id)
        if not aos_loop._int(times):
            raise DaemonError("Conflict", "%s 的 ctl.json 裡 times 不對：%r" % (e.id, times))
        return e.acked(e.update_ctl(times=max(0, times + delta)))

    def remove(self, path, wait=True):
        e = self._get(path)
        _bool(wait)
        e.update_ctl(stop={"val": True, "now": not wait})
        e.removing = True

        def ready():
            if not e.exited():
                return None
            st = e.status()
            self.drop(e)
            return st
        return ready

    def drop(self, e):
        self.entries.pop(e.id, None)
        if e.workdir:
            shutil.rmtree(e.workdir, ignore_errors=True)

    def state(self, path):
        return self._get(path).status()["state"]

    def get(self, path):
        return self._get(path).status()

    def list(self):
        return [e.status() for e in self.entries.values() if not e.removing]

    def reap(self):
        """行程結束了的：整群補 SIGKILL、收屍。"""
        for e in self.entries.values():
            if not e.exited() and os.waitid(os.P_PID, e.proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT):
                reap(e.proc)

    def snapshot(self):
        return [{"loop": e.id, "ctl": e.ctl_doc()} for e in self.entries.values() if not e.removing]

    def restore(self, items):
        """全有全無：先全部驗過，有一筆不對就丟錯、一個都不起。"""
        if not isinstance(items, list):
            raise DaemonError("FieldType", "表要是陣列")
        todo = []
        for it in items:
            if not (isinstance(it, dict) and set(it) == {"loop", "ctl"} and isinstance(it["ctl"], dict)):
                raise DaemonError("FieldType", "表裡每筆要是 {loop, ctl}：%r" % (it,))
            todo.append((self._prepare(it["loop"]), it["ctl"]))
        if len({e.id for (e, _), _ in todo}) != len(todo):
            raise DaemonError("Exists", "表裡有重複的 loop")
        for (e, _), _ in todo:
            st = read_state(e.state) if e.state else None
            if st is not None and isinstance(st.get("pid"), int) and _alive(st["pid"]):
                raise DaemonError("Exists", "%s 的 state.json 說 pid %d 還在跑" % (e.id, st["pid"]))
        for (e, wrap), ctl in todo:
            try:
                self._start(e, wrap, ctl)
            except OSError as err:
                raise DaemonError("WriteFailed", "起不了 %s：%s" % (e.id, err))
        return [e.id for (e, _), _ in todo]

    def shutdown(self, now, grace_ms, got):
        """收掉全部。now＝整群 SIGTERM、等 grace_ms、整群 SIGKILL；否則替每個寫 stop、等它們自己結束（中途收到訊號改成 now）。"""
        live = [e for e in self.entries.values() if not e.exited()]
        if not now:
            for e in live:
                try:
                    e.update_ctl(stop=True)
                except DaemonError as err:
                    print(err, file=sys.stderr)
            while not got and any(not e.exited() for e in live):
                self.reap()
                time.sleep(0.02)
        for e in live:
            if not e.exited():
                aos_loop._killpg(e.proc.pid, signal.SIGTERM)
        end = time.monotonic() + grace_ms / 1000
        while time.monotonic() < end and any(not e.exited() for e in live):
            self.reap()
            time.sleep(0.02)
        for e in live:
            if not e.exited():
                reap(e.proc)


def _bool(v):
    if not isinstance(v, bool):
        raise DaemonError("FieldType", "wait 要是 true／false，不是 %r" % (v,))
