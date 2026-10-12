#!/usr/bin/env python3
"""daemon：管很多個 loop 的表；自己也是一個 loop（每一圈＝掃一次控制資料夾）。純標準庫。

    python3 aos_daemon.py DAEMON.json

`run(path)` 跟命令列一模一樣。

daemon.json（先用指示詞 lib 解，基準＝daemon 啟動時的 cwd）：

    control_dir    控制資料夾（必填），沒有就建
    load           起來後先 load 這個檔（選填；跟丟一條 load 指令一樣，但失敗＝起不來）
    save           收工時先 save 到這個檔（選填；SIGTERM、ctl 的 stop、times 跑完才存，SIGINT 不存）
    work_dir       替 loop 生包裝檔的地方（選填；沒寫＝control_dir 旁邊的 loops/）
    grace_ms       收工時等底下的 loop 多久，過了整群 SIGKILL（非負整數；沒寫＝10000；要比 loop 的 grace_ms 長）
    times          掃幾圈就收工（非負整數；null＝不限，預設）
    interval_ms    每圈隔多久（非負整數；沒寫＝200）
    ctl            daemon 自己的 ctl.json（選填；不能放在 control_dir 裡）：paused＝不掃資料夾（指令堆著、loop 照跑）、
                   stop＝收工（now＝底下的 loop 當場收掉；沒 now＝等它們這次跑完）、times、interval_ms
    ctl_poll_ms    多久看一次 ctl.json（正整數；沒寫＝1000）
    state          daemon 自己的 state.json（選填）：id、state、pid、times、interval_ms、runs（掃了幾圈）、ctl_mtime、loops（表上幾個）

表上每個 loop 是一支子程序 `aos_loop.py LOOP.json`（自成一個 session），daemon 跟它之間只靠兩個檔：寫它的 ctl.json、
讀它的 state.json。loop.json 有寫 ctl／state 就用它寫的；沒寫的，daemon 在 `work_dir/<編號>/` 生一份包裝檔
`loop.json`（每個 key 用 `$ref` 指回原檔，補上 ctl、state 指到同一個資料夾）、起的是包裝檔；移除或收工時刪掉那個資料夾。

指令：往控制資料夾放一個 `名字.json`。daemon 每圈把裡面的 `*.json` 照檔名順序讀進來處理，處理完改成 `名字.json.done`，
內容換成一問一答：

    {"request": 原指令, "ok": true,  "result": 結果}
    {"request": 原指令, "ok": false, "error": {"code": "NotFound", "msg": "白話"}}

讀到不合法的 JSON 也一樣當場變成 `.done`（`request` 是讀到的原文字串，error.code＝BadCommand）。
寫到一半被讀到＝BadCommand，寫的人自己負責（先寫 `.` 開頭的檔再改名）；`.` 開頭的檔不讀。`.done` 由丟指令的人清。不 fsync。

指令一律 {"op", "id", ...參數}。`id` 要是 loop.json 的絕對路徑（相對＝FieldType），daemon 轉成 realpath：

    {"op": "add",       "id": ID}                 起一個 loop                                  → result＝realpath
    {"op": "set",       "id": ID, "how": {...}}   改 times／interval_ms／interval_mode（寫進它的 ctl.json）
    {"op": "pause",     "id": ID, "wait": B}      暫停；wait＝true 等這次跑完，false 當場收掉（預設 true）
    {"op": "resume",    "id": ID}                 繼續
    {"op": "add_times", "id": ID, "delta": N}     總次數加減 N（最少到 0；不限次數＝Conflict）
    {"op": "remove",    "id": ID, "wait": B}      停掉它（ctl 的 stop）、等行程結束、從表上拿掉 → result＝最後的狀態物件
    {"op": "state",     "id": ID}                 → result＝狀態字串（loop 還沒寫 state.json＝"starting"）
    {"op": "get",       "id": ID}                 → result＝狀態物件（就是它的 state.json；行程已結束＝state "stopped"）
    {"op": "list"}                                → result＝[狀態物件, ...]
    {"op": "save",      "path": P}                表存成一份 JSON（整份重寫）                → result＝存了幾個
    {"op": "load",      "path": P}                從 save 存的檔一次起回來                    → result＝[id, ...]

set／pause／resume／add_times 回改完的狀態物件，**等 loop 讀到了才回**（它的 state.json 的 ctl_mtime 趕上 daemon 寫的那份）；
pause 還要等這次真的停了；remove 等行程結束。等的期間指令檔留在原地。loop 行程已經結束的，馬上回當下的狀態。
error.code（只供參考，看 ok 就好）：BadCommand、UnknownOp、FieldType、NotFound、Exists、Conflict、ReadFailed、JsonSyntax、
WriteFailed、Internal。

save 存每個 loop 的 {"loop": loop.json 的 realpath, "ctl": 當下 ctl.json 的內容}；runs 在 loop 行程裡、不存，
load 回來從 0 數。先寫 `.名字.tmp` 再改名。load 全有全無：某個 loop.json 不在（NotFound）、已經在表上或檔裡重複、
它自己的 state.json 裡的 pid 還活著（Exists）、格式不對（FieldType）——任何一點不對就回 error，一個都不起。
load 會把存下來的 ctl 內容寫回各 loop 的 ctl.json 再起它。

收工：SIGTERM＝先 save（config 有 save）、對每個 loop 的 session 送 SIGTERM、等 grace_ms、沒走的整群 SIGKILL。
SIGINT 同樣收、不存。ctl 的 stop／times 跑完：先 save；now＝同 SIGTERM，沒 now＝替每個 loop 的 ctl.json 寫 stop、等它們自己結束。
跑起來之後出意外不結束，只往 stderr 印一行（同一件事印一次）：控制資料夾看不了（ScanFailed）、回覆寫不了
（ReplyFailed：改把指令改名成 .done；改名也不行就放著不管）、指令處理出了沒料到的錯（回 Internal）。
命令列退出碼：0＝正常結束；1＝起不來，或收工時 save 失敗（stderr 印一行「代號: 白話」）。
"""
import itertools
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time

import aos_loop
from aos_loop import CtlFile, kill, load_config as _load_cfg, parse_ctl, reap, want, write_json

__all__ = ["DaemonError", "load_config", "run"]

AOS_LOOP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aos_loop.py")
DEFAULTS = {"control_dir": None, "load": None, "save": None, "work_dir": None, "grace_ms": 10000,
            "times": None, "interval_ms": 200, "ctl": None, "ctl_poll_ms": 1000, "state": None}
_CAUGHT = (signal.SIGINT, signal.SIGTERM)


class DaemonError(Exception):
    """config 或指令被拒。`code`＝錯誤代號，`msg`＝白話，`str(e)`＝「代號: 白話」。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg


def load_config(path):
    """讀 daemon.json，回 (realpath, 填好預設值的 dict)。"""
    ident, cfg = _load_cfg(path, DEFAULTS, need_inst=False, err=DaemonError)
    if cfg["work_dir"] is None:
        cfg["work_dir"] = os.path.join(os.path.dirname(cfg["control_dir"]), "loops")
    if cfg["ctl"] and os.path.commonpath([cfg["ctl"], cfg["control_dir"]]) == cfg["control_dir"]:
        raise DaemonError("Conflict", "ctl %s 不能放在 control_dir 裡（會被當成指令讀）" % cfg["ctl"])
    return ident, cfg


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
        st = _read(self.state)
        if not isinstance(st, dict) or st.get("pid") != self.proc.pid:
            st = {"id": self.id, "state": "stopped" if self.exited() else "starting"}
        st = dict(st, id=self.id)
        if self.exited():
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


def _esc(k):
    return k.replace("~", "~0").replace("/", "~1")


class Table:
    def __init__(self, cfg):
        self.cfg = cfg
        self.entries = {}

    def _id(self, path):
        if not isinstance(path, str) or not os.path.isabs(path):
            raise DaemonError("FieldType", "id 要是 loop.json 的絕對路徑，不是 %r" % (path,))
        return os.path.realpath(path)

    def _get(self, path):
        ident = self._id(path)
        e = self.entries.get(ident)
        if e is None or e.removing:
            raise DaemonError("NotFound", "沒有 loop %s" % ident)
        return e

    def _prepare(self, path):
        """驗一個 loop.json、決定 ctl／state 放哪，回 (_Entry, 起的時候用的 loop.json 內容或 None)。不動檔案。"""
        ident = self._id(path)
        if not os.path.isfile(ident):
            raise DaemonError("NotFound", "%s 不存在" % ident)
        if ident in self.entries:
            raise DaemonError("Exists", "loop %s 已經在了" % ident)
        _, lcfg = _load_cfg(ident, err=DaemonError)
        raw = _read(ident)
        wrap = None
        if lcfg["ctl"] is None or lcfg["state"] is None:
            wrap = {k: {"$ref": "%s#/%s" % (ident, _esc(k))} for k in raw}
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
            st = _read(e.state) if e.state else None
            if isinstance(st, dict) and isinstance(st.get("pid"), int) and _alive(st["pid"]):
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


# ---- 指令 ----

def _error(code, msg):
    return {"ok": False, "error": {"code": code, "msg": msg}}


def handle(table, cmd):
    """一條指令 → 回 {"ok", "result"} 或 {"ok", "error"}；要等的回一個函式 ready()：還沒好回 None。"""
    try:
        r = _dispatch(table, cmd)
    except DaemonError as e:
        return _error(e.code, e.msg)
    except Exception as e:
        return _error("Internal", "%s: %s" % (type(e).__name__, e))
    if callable(r):
        def ready():
            try:
                v = r()
            except Exception as e:
                return _error("Internal", "%s: %s" % (type(e).__name__, e))
            return None if v is None else {"ok": True, "result": v}
        return ready
    return {"ok": True, "result": r}


def _dispatch(table, cmd):
    if not isinstance(cmd, dict):
        raise DaemonError("BadCommand", "指令要是物件")
    op, ident = cmd.get("op"), cmd.get("id")
    ops = {"add": lambda: table.add(ident), "set": lambda: table.set(ident, cmd.get("how", {})),
           "pause": lambda: table.pause(ident, cmd.get("wait", True)), "resume": lambda: table.resume(ident),
           "add_times": lambda: table.add_times(ident, cmd.get("delta")),
           "remove": lambda: table.remove(ident, cmd.get("wait", True)),
           "state": lambda: table.state(ident), "get": lambda: table.get(ident), "list": table.list,
           "save": lambda: _save(table, _path(cmd.get("path"))), "load": lambda: _load(table, _path(cmd.get("path")))}
    if op not in ops:
        raise DaemonError("UnknownOp", "不認得的 op %r" % (op,))
    return ops[op]()


def _path(p, key="path"):
    if not isinstance(p, str) or not p:
        raise DaemonError("FieldType", "%s 要是字串路徑，不是 %r" % (key, p))
    return os.path.abspath(p)


def _save(table, path):
    snap = table.snapshot()
    try:
        write_json(path, snap)
    except OSError as e:
        raise DaemonError("WriteFailed", "寫不了 %s：%s" % (path, e))
    return len(snap)


def _load(table, path):
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise DaemonError("ReadFailed", "讀不到 %s：%s" % (path, e))
    try:
        items = json.loads(raw)
    except ValueError as e:
        raise DaemonError("JsonSyntax", "%s 不是合法 JSON：%s" % (path, e))
    return table.restore(items)


# ---- 控制資料夾 ----

class _Folder:
    def __init__(self, d):
        self.d = d
        self.said, self.given_up, self.pending = {}, set(), {}

    def say(self, key, msg):
        """同一件事只往 stderr 印一次；key 的訊息變了才再印。"""
        if self.said.get(key) != msg:
            self.said[key] = msg
            print(msg, file=sys.stderr)

    def flush(self):
        for name, (path, cmd, ready) in list(self.pending.items()):
            r = ready()
            if r is not None:
                del self.pending[name]
                self.reply(path, {"request": cmd, **r})

    def scan(self, table):
        """處理一圈。出意外不往上丟：印到 stderr，下一圈照常。"""
        try:
            names = sorted(os.listdir(self.d))
        except OSError as e:
            self.say("list", "ScanFailed: 看不了控制資料夾 %s：%s" % (self.d, e))
            self.flush()
            return
        self.said.pop("list", None)
        for name in names:
            if name.startswith(".") or not name.endswith(".json") or name in self.given_up or name in self.pending:
                continue
            path = os.path.join(self.d, name)
            raw = None
            try:
                with open(path, encoding="utf-8") as f:
                    raw = f.read()
                cmd = json.loads(raw)
            except (OSError, ValueError) as e:
                reply = {"request": raw, **_error("BadCommand", "讀不了 %s：%s" % (name, e))}
            else:
                r = handle(table, cmd)
                if callable(r):
                    self.pending[name] = (path, cmd, r)
                    continue
                reply = {"request": cmd, **r}
            self.reply(path, reply)
        self.flush()

    def reply(self, path, reply):
        """回覆寫成 名字.json.done、刪掉指令。寫不了就把指令本身改名成 .done；改名也不行就放著不管（之後也不再讀它）。"""
        name = os.path.basename(path)
        try:
            write_json(path + ".done", reply)
        except OSError as e:
            try:
                os.replace(path, path + ".done")
                self.say(name, "ReplyFailed: 寫不了 %s 的回覆（%s），把指令改名成 .done" % (name, e))
            except OSError as e2:
                self.given_up.add(name)
                self.say(name, "ReplyFailed: 寫不了 %s 的回覆（%s），改名也不行（%s），放著不管" % (name, e, e2))
            return
        try:
            os.remove(path)
        except OSError:
            pass


# ---- 主迴圈：daemon 自己也是一個 loop ----

def serve(ident, cfg, got):
    """跑到收工。got＝收到的訊號（list，訊號處理函式往裡面放）。save 失敗丟 DaemonError（loop 們照樣收掉）。"""
    try:
        os.makedirs(cfg["control_dir"], exist_ok=True)
    except OSError as e:
        raise DaemonError("MkdirFailed", "建不了控制資料夾：%s" % e)
    table = Table(cfg)
    folder = _Folder(cfg["control_dir"])
    if cfg["load"]:
        _load(table, cfg["load"])
    ctl = CtlFile(cfg["ctl"], "daemon") if cfg["ctl"] else None
    initial = {"paused": (False, False), "stop": (False, False), "times": cfg["times"], "interval_ms": cfg["interval_ms"]}
    runs, next_poll, next_scan, written = 0, 0, 0, None
    w = want(initial, {})
    save, now_ = False, True
    try:
        while True:
            t = time.monotonic()
            if ctl and t >= next_poll:
                ctl.poll()
                next_poll = t + cfg["ctl_poll_ms"] / 1000
            w = want(initial, ctl.good if ctl else {})
            table.reap()
            if got:
                save = signal.SIGTERM in got
                break
            if w["stop"][0]:
                save, now_ = True, w["stop"][1]
                break
            if w["times"] is not None and runs >= w["times"]:
                save, now_ = True, False
                break
            if not w["paused"][0] and t >= next_scan:
                folder.scan(table)
                runs += 1
                next_scan = time.monotonic() + w["interval_ms"] / 1000
            written = _write_state(cfg, ident, w, runs, ctl, len(table.entries), written)
            time.sleep(0.02)
    finally:
        try:
            if save and cfg["save"]:
                _save(table, cfg["save"])
        finally:
            _write_state(cfg, ident, w, runs, ctl, len(table.entries), written, "stopping")
            table.shutdown(now_, cfg["grace_ms"], got)
            folder.flush()
            for e in list(table.entries.values()):
                table.drop(e)
            _write_state(cfg, ident, w, runs, ctl, 0, None, "stopped")


def _write_state(cfg, ident, w, runs, ctl, n, written, final=None):
    if cfg["state"] is None:
        return written
    st = {"id": ident, "state": final or ("paused" if w["paused"][0] else "waiting"), "pid": os.getpid(),
          "times": w["times"], "interval_ms": w["interval_ms"], "runs": runs,
          "ctl_mtime": ctl.mtime if ctl else None, "loops": n}
    if st != written:
        try:
            write_json(cfg["state"], st)
        except OSError:
            pass
    return st


def run(path):
    """跟命令列 `aos_daemon.py DAEMON.json` 一模一樣。正常收工回 None；起不來或 save 失敗丟 DaemonError。"""
    main = threading.current_thread() is threading.main_thread()
    got = []
    old = {s: signal.signal(s, lambda signum, frame: got.append(signum)) for s in _CAUGHT} if main else {}
    try:
        serve(*load_config(path), got)
    finally:
        for s, h in old.items():
            signal.signal(s, h)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("用法：aos_daemon.py DAEMON.json", file=sys.stderr)
        return 1
    try:
        run(args[0])
        return 0
    except DaemonError as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
