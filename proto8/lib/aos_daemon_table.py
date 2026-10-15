"""daemon 的表：每個子項是一支長壽的子程序 `aos_loop.py -`，daemon 只靠寫它的 ctl 窗、讀它的 state 窗控制它。純標準庫。

子項六態（`phase`，09 §19）：starting／running／exited／backoff／stopping／removed。表落在 `table` 窗（N-14 一種，只有 daemon 寫）：
`{"kind": "aos-daemon-table", "children": [列, ...]}`，每列 {id, target, work_dir, ctl, state, pid, started, phase,
exits, last_code}；先寫表、再 Popen。table 窗就是存檔（暫定 d）：`load: true` 起來時讀它接回。

daemon 只管自己這一層（C-52，10-15 深夜使用者「不留」）：收子項時只看它需要的——是物件、沒 inst 有 argv 就包成跑一次、
ctl／state 沒寫就放 work_dir/N/——裡面的 loop 設定、inst 都不驗、不填預設，原樣從 stdin 灌給子 loop；寫錯了子 loop 自己
退 1、錯落在 work_dir/N/err.json，daemon 只看到它結束（走策略格）。子項的 times 也不記：add_times 讀它的 ctl／state 窗。

`Table` 一個方法對一條指令（add／set／pause／resume／add_times／remove／state／get／list），加上每圈的 `tick()`
（收屍、套策略格、退避到點重起、寫表）、`load()`、`shutdown()`。要等 loop 讀到才回的，回一個 ready()：還沒好回 None。
`DaemonError` 也在這裡。規矩的白話說明在 aos_daemon 的檔頭。
"""
import itertools
import json
import os
import shutil
import signal
import subprocess
import sys
import time

import aos_cli
import aos_inst
from aos_cli import CliError, is_int, split_target, target_id
from aos_ctl_state import parse_ctl, proc_started, read_state, write_json
from aos_proc import _killpg, reap

__all__ = ["DaemonError", "Table"]

AOS_LOOP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aos_loop.py")
AOS_INST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aos_inst.py")
MAX_EXITS = 5       # 崩潰迴圈的上限：exits ≥ 5 強制 leave，不問策略格


class DaemonError(CliError):
    """config 或指令被拒。`code`＝錯誤代號，`msg`＝白話，`str(e)`＝「代號: 白話」。"""


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.loads(f.read())
    except (OSError, ValueError):
        return None


# ---- 表上一個子項 ----

class _Entry:
    """表上一個 loop：子程序（或接回的孤兒：只有 pid＋啟動時間）＋它的 ctl、state 窗在哪。"""

    def __init__(self, ident, target, workdir, ctl, state):
        self.id, self.target, self.workdir, self.ctl, self.state = ident, target, workdir, ctl, state
        self.cfg = None             # 灌給 aos_loop 的設定；接回的孤兒沒有（要重起時再讀 target）
        self.proc = self.pid = self.started = self.code = self.retry_at = None
        self.phase, self.exits, self.removing = "starting", 0, False

    def row(self):
        return {"id": self.id, "target": self.target, "work_dir": self.workdir, "ctl": self.ctl,
                "state": self.state, "pid": self.pid, "started": self.started, "phase": self.phase,
                "exits": self.exits, "last_code": self.code}

    def exited(self):
        return self.phase not in ("starting", "running", "stopping")

    def gone(self):
        """行程結束了沒（結束了就收屍、記碼）。接回的孤兒看 pid＋啟動時間。"""
        if self.proc is not None:
            if os.waitid(os.P_PID, self.proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
                return False
            self.code = reap(self.proc)
            return True
        return self.pid is None or proc_started(self.pid) != self.started

    def status(self):
        st = read_state(self.state)
        if st is None or st.get("pid") != self.pid:
            st = {"id": self.id, "state": "stopped" if self.exited() else "starting"}
        st = dict(st, id=self.id, phase=self.phase)
        if self.exited() and st["state"] not in ("done", "stopped"):
            st["state"] = "stopped"
        return st

    def ctl_doc(self):
        doc = _read(self.ctl)
        return doc if isinstance(doc, dict) else {}

    def update_ctl(self, **fields):
        """讀現在的 ctl、改幾格、流水號 seq 加一、整份寫回（暫存再改名），回這次的 seq（N-14 回音以序號為準）。"""
        doc = self.ctl_doc()
        seq = (doc.get("seq") if is_int(doc.get("seq"), 0) else 0) + 1
        try:
            write_json(self.ctl, dict(doc, seq=seq, **fields))
        except OSError as e:
            raise DaemonError("WriteFailed", "寫不了 %s：%s" % (self.ctl, e))
        return seq

    def acked(self, seq, settled=lambda st: True):
        """回 ready()：loop 讀到 seq 那份 ctl（state 的 ctl_seq 趕上，而且 settled）就回狀態物件；行程結束了直接回。"""
        def ready():
            st = self.status()
            if self.exited():
                return st
            s = st.get("ctl_seq")
            return st if is_int(s, 0) and s >= seq and settled(st) else None
        return ready


# ---- 表 ----

class Table:
    def __init__(self, cfg, daemon_id):
        self.cfg, self.daemon_id = cfg, daemon_id
        self.entries = {}
        self.closing = False
        self.written = None
        self.warning = None         # 最近一件意外（「代號: 白話」）：daemon 放進 state 窗的 last_warning，不寫 stderr

    def _say(self, code, msg):
        self.warning = "%s: %s" % (code, msg)

    # ---- 起子項 ----

    def _config(self, target, i=None):
        """TARGET（絕對路徑，可接 `#/位置`；或內嵌物件）→ (id, 那份 loop 設定原樣)。inst.json（沒 inst、有 argv）包成
        只跑一次的 loop。只看到「是個物件」為止，裡面不驗（子 loop 自己驗、自己報，C-52）。"""
        if isinstance(target, dict):
            doc, ident = target, target.get("id") or "%s#/children/%d" % (self.daemon_id, i)
        else:
            file = _split(target)[0]
            if not os.path.isabs(file):
                raise DaemonError("FieldType", "id 要是 loop.json 的絕對路徑，不是 %r" % (target,))
            if not os.path.isfile(file):
                raise DaemonError("NotFound", "%s 不存在" % file)
            try:
                doc, ident = aos_cli.load_target(target)
            except CliError as e:
                raise DaemonError(e.code, e.msg)
        if not isinstance(doc, dict):
            raise DaemonError("FieldType", "%s 要是 loop 設定（物件），不是 %r" % (ident, doc))
        if "inst" not in doc and "argv" in doc:
            doc = {"inst": doc, "times": 1}
        return ident, doc

    def _windows(self, doc, d):
        """子項的 ctl／state 窗：它自己寫了就用它的（相對路徑從 daemon 的 cwd 算，子 loop 也從這裡起），沒寫＝work_dir/N/。"""
        out = {}
        for k in ("ctl", "state"):
            v = doc.get(k)
            if v is None:
                v = os.path.join(d, k + ".json")
            elif not (isinstance(v, str) and v):
                raise DaemonError("FieldType", "%s 要是路徑字串，不是 %r" % (k, v))
            out[k] = os.path.abspath(v)
        return out

    def add(self, target, i=None):
        ident, doc = self._config(target, i)
        if ident in self.entries:
            raise DaemonError("Exists", "loop %s 已經在了" % ident)
        os.makedirs(self.cfg["work_dir"], exist_ok=True)
        for n in itertools.count(1):
            d = os.path.join(self.cfg["work_dir"], str(n))
            try:
                os.mkdir(d)
                break
            except FileExistsError:
                continue
        try:
            win = self._windows(doc, d)
        except DaemonError:
            shutil.rmtree(d, ignore_errors=True)
            raise
        e = _Entry(ident, target, d, win["ctl"], win["state"])
        e.cfg = dict(doc, id=ident, **win)
        if not os.path.exists(e.ctl):
            write_json(e.ctl, {})
        self.entries[ident] = e
        self._spawn(e)
        return ident

    def _spawn(self, e):
        """先寫表（starting）、再 Popen；子 loop 的 stdout 丟 /dev/null（結果一律從 state 窗讀），
        stderr append 到 work_dir/N/err.json（只在出錯時長）。"""
        if e.cfg is None:                   # 接回的孤兒要重起：重讀 target
            e.cfg = dict(self._config(e.target)[1], id=e.id, ctl=e.ctl, state=e.state)
        e.phase, e.proc, e.pid, e.started = "starting", None, None, None
        self.write()
        with open(os.path.join(e.workdir, "err.json"), "ab") as err:
            e.proc = subprocess.Popen([sys.executable, AOS_LOOP, "-"], start_new_session=True,
                                      stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=err)
        try:
            e.proc.stdin.write(json.dumps(e.cfg).encode("utf-8"))
            e.proc.stdin.close()
        except OSError:
            pass
        e.pid, e.started, e.phase = e.proc.pid, proc_started(e.proc.pid), "running"
        self.write()

    # ---- 每圈 ----

    def tick(self):
        """收屍、套策略格、退避到點的重起、寫表。"""
        now = time.monotonic()
        for e in list(self.entries.values()):
            if not e.exited() and e.gone():
                e.exits += 1
                e.phase = "removed" if e.removing else "exited"
                if not e.removing and not self.closing:
                    self._exit_policy(e, now)
            elif e.phase == "backoff" and not self.closing and now >= e.retry_at:
                try:
                    self._spawn(e)
                except (DaemonError, OSError) as err:
                    e.phase = "exited"
                    self._say("RestartFailed", "%s 重起不了：%s" % (e.id, err))
        self.write()

    def _exit_policy(self, e, now):
        """子項結束：問 `policies.child_exit`（inst TARGET；stdin {id, code, exits, last_state} → stdout
        {action, after_ms}）。沒設、exits ≥ MAX_EXITS、格出錯＝leave。"""
        target = self.cfg["policies"].get("child_exit")
        if target is None or e.exits >= MAX_EXITS:
            return
        act = {"action": "leave"}
        try:
            doc = target if isinstance(target, dict) else aos_cli.load_target(target, aos_inst._file)[0]
            fin, fout = os.path.join(e.workdir, "policy.in.json"), os.path.join(e.workdir, "policy.out.json")
            write_json(fin, {"id": e.id, "code": e.code, "exits": e.exits, "last_state": read_state(e.state)})
            subprocess.run([sys.executable, AOS_INST, "-"], input=json.dumps(dict(doc, stdin=fin, stdout=fout)),
                           text=True, stdout=subprocess.DEVNULL)
            with open(fout, encoding="utf-8") as f:
                outs = [o for o in aos_cli.read_stream(f.read()) if isinstance(o, dict)]
            act = outs[-1]
            if act.get("action") not in ("restart", "leave", "remove") or not is_int(act.get("after_ms", 0), 0):
                raise ValueError("策略格回的不對：%r" % (act,))
        except (CliError, OSError, ValueError, IndexError) as err:
            self._say("PolicyFailed", "%s 的 child_exit 策略格出錯（%s），當成 leave" % (e.id, err))
            act = {"action": "leave"}
        if act["action"] == "restart":
            e.phase, e.retry_at = "backoff", now + act.get("after_ms", 0) / 1000
        elif act["action"] == "remove":
            self.drop(e)

    def write(self):
        """表有變才寫 table 窗（沒設 table＝不寫）。"""
        doc = {"kind": "aos-daemon-table", "children": [e.row() for e in self.entries.values()]}
        if self.cfg["table"] is None or doc == self.written:
            return
        try:
            write_json(self.cfg["table"], doc)
            self.written = doc
        except OSError as err:
            self._say("TableWriteFailed", "寫不了 table 窗 %s：%s" % (self.cfg["table"], err))

    def load(self):
        """讀 table 窗接回：pid＋啟動時間對得上＝認領（不重起）；對不上下一圈當 exited 走策略格；backoff 的馬上重起。"""
        doc = _read(self.cfg["table"])
        if doc is None:
            return
        rows = doc.get("children") if isinstance(doc, dict) else None
        if not isinstance(rows, list):
            raise DaemonError("FieldType", "table 窗 %s 的 children 要是陣列" % self.cfg["table"])
        for r in rows:
            try:
                e = _Entry(r["id"], r["target"], r["work_dir"], r["ctl"], r["state"])
                e.pid, e.started, e.exits, e.code = r["pid"], r["started"], r["exits"], r["last_code"]
                e.phase = {"exited": "exited", "backoff": "backoff"}.get(r["phase"], "running")
            except (KeyError, TypeError) as err:
                raise DaemonError("FieldType", "table 窗 %s 有一列不對：%r（%s）" % (self.cfg["table"], r, err))
            e.retry_at = time.monotonic()
            os.makedirs(e.workdir, exist_ok=True)
            self.entries[e.id] = e

    # ---- 指令 ----

    def _get(self, target):
        file, pos = _split(target)
        e = self.entries.get(target_id(os.path.realpath(file), pos)) or self.entries.get(target)
        if e is None or e.removing:
            raise DaemonError("NotFound", "沒有 loop %s" % target)
        return e

    def set(self, path, how):
        e = self._get(path)
        if not isinstance(how, dict) or not set(how) <= {"times", "interval_ms"}:
            raise DaemonError("FieldType", "how 只能有 times／interval_ms，不是 %r" % (how,))
        try:
            parse_ctl(how)
        except ValueError as err:
            raise DaemonError("FieldType", str(err))
        return e.acked(e.update_ctl(**how))

    def pause(self, path):
        e = self._get(path)
        return e.acked(e.update_ctl(paused=True), lambda st: st.get("state") == "paused")

    def resume(self, path):
        e = self._get(path)
        return e.acked(e.update_ctl(paused=False))

    def add_times(self, path, delta):
        if not is_int(delta, -2 ** 63):
            raise DaemonError("FieldType", "delta 要是整數，不是 %r" % (delta,))
        e = self._get(path)
        doc = e.ctl_doc()
        times = doc["times"] if "times" in doc else e.status().get("times")     # 只靠它的兩扇窗（N-28）
        if times is None:
            raise DaemonError("Conflict", "%s 是不限次數，不能加減" % e.id)
        if not is_int(times, 0):
            raise DaemonError("Conflict", "%s 的 ctl 裡 times 不對：%r" % (e.id, times))
        return e.acked(e.update_ctl(times=max(0, times + delta)))

    def remove(self, path, wait=True):
        e = self._get(path)
        _bool(wait)
        if not e.exited():
            e.update_ctl(stop=True)
            if not wait and e.pid:                      # 當場收掉＝對子 loop 送訊號（ctl 只收布林）
                _killpg(e.pid, signal.SIGTERM)
            e.phase = "stopping"
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
        self.write()

    def state(self, path):
        return self._get(path).status()["state"]

    def get(self, path):
        return self._get(path).status()

    def list(self):
        return [e.status() for e in self.entries.values() if not e.removing]

    def shutdown(self, now, grace_ms, got):
        """收掉全部（表留著，給下次 load 接回）。now＝整群 SIGTERM、等 grace_ms、整群 SIGKILL；
        否則替每個寫 stop、等它們自己結束（中途收到訊號改成 now）。"""
        self.closing = True
        live = [e for e in self.entries.values() if not e.exited()]
        if not now:
            for e in live:
                try:
                    e.update_ctl(stop=True)
                except DaemonError as err:
                    self._say(err.code, err.msg)
            while not got and any(not e.exited() for e in live):
                self.tick()
                time.sleep(0.02)
        for e in live:
            if not e.exited() and e.pid:
                _killpg(e.pid, signal.SIGTERM)
        end = time.monotonic() + grace_ms / 1000
        while time.monotonic() < end and any(not e.exited() for e in live):
            self.tick()
            time.sleep(0.02)
        for e in live:
            if not e.exited() and e.pid:
                _killpg(e.pid, signal.SIGKILL)
                if e.proc:
                    e.code = reap(e.proc)
                e.phase = "exited"
        self.write()


def _split(target):
    if not isinstance(target, str):
        raise DaemonError("FieldType", "id 要是 loop.json 的絕對路徑，不是 %r" % (target,))
    try:
        return split_target(target)
    except CliError as e:
        raise DaemonError(e.code, e.msg)


def _bool(v):
    if not isinstance(v, bool):
        raise DaemonError("FieldType", "wait 要是 true／false，不是 %r" % (v,))
