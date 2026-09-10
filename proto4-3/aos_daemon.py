#!/usr/bin/env python3
"""aos-daemon：一個常駐進程，裡面就是一個 dict——key＝一份 inst.json 的路徑，value＝
正在跑的 aos-run。

[proto4 筆記第 13 節](../proto4/notes/2026-09-08-ideas.md)的原型（key 那條看 §15）。
**key＝那個 `.json` 檔的 realpath**：`add`／`restart` 只收副檔名 `.json` 的路徑，資料夾與
普通檔案一律拒絕；檔案還不存在照收（aos-run 每次跑回 125，出現了就跑起來）。同一個資料夾
可以掛好幾份不同的 inst.json，各自一支 aos-run。value 是**一個
`aos-run` 子進程**（不是在 daemon 自己進程裡跑 `run_loop`），所以暫停／繼續＝SIGSTOP／
SIGCONT、刪＝SIGTERM，進程的事交給 Linux 管。

**主迴圈不等任何人**：七個動作都是「送個訊號、標個狀態、立刻回 `(ok, result)`」，真正
的「等它退」「等它睡著」交給每圈跑一次的 `advance()`／`reap()`。所以 rm 一個手上那次
要跑一小時的 aos-run，daemon 照樣每 0.2 秒收下一個請求。唯一可以卡的地方是收工
（`shutdown()`）——那時候本來就該等大家走乾淨。

近況（`ready`／`running`／`runs`／`last_exit`／`last_kind`）從 aos-run 的 `--status-fd`
讀，**不再解 stderr**；stderr 照舊接管子、原樣（前面加 key）進 `daemon.log`。

三個檔分工：這裡是本體（那個 dict、七個動作、主迴圈、收屍、收工）、一筆長什麼樣與狀態機
在 `aos_daemon_entry.py`、請求檔那一層在 `aos_daemon_req.py`；命令列入口是 `aos-daemon`
（前台程式，不背景化），下指令的是 `aos_daemon_ctl.py`。七個動作都是 `Daemon` 的方法、
都回 `(ok, result)`，所以測試可以不開 daemon 進程直接叫。
"""
import os
import signal
import subprocess
import sys
import threading
import time

import aos_daemon_req
from aos_daemon_entry import (PAUSED, PAUSE_PENDING, RESTARTING, RUNNING, STOPPING,
                              TERM_WAIT, Entry, json_only, key_of, read_status,
                              read_stderr)
from aos_home import Home, write_json      # noqa: F401  （Home 讓外面 import 這裡就夠）

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, "aos-run")
TICK = 0.2              # 主迴圈：多久跑一圈（掃 requests/、推狀態機、收屍）
SAVE = 0.5              # 多久寫一次 state.json


class Daemon:
    def __init__(self, home):
        self.home = home
        self.home.ensure()
        self.table = {}                 # inst.json 的 realpath -> Entry
        self.stopping = False
        self._lock = threading.Lock()   # daemon.log 是好幾條執行緒一起寫的

    # ── 七個動作，一律回 (ok, result)，而且都不等 ──────────────
    def add(self, target, args=()):
        """開一個 `aos-run <target> <旗標…> --status-fd N` 子進程，記進表。

        target 只收 `.json`（資料夾／普通檔案拒絕），不存在照收。status 管子的寫端用
        `pass_fds` 交給它，daemon 這邊立刻關掉自己那份（不然讀端永遠等不到 EOF），讀端交給
        一條執行緒逐行讀。同 key 第二次＝拒絕，舊的不動。
        """
        bad = json_only(target)
        if bad:
            return False, bad
        key = key_of(target)
        if key in self.table:
            return False, "已經有一個在跑：%s" % key
        target = os.path.abspath(target)
        args = [str(a) for a in args]
        rfd, wfd = os.pipe()
        try:
            p = subprocess.Popen(
                [sys.executable, RUN, target] + args + ["--status-fd", str(wfd)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, start_new_session=True, pass_fds=(wfd,))
        except OSError as e:
            os.close(rfd)
            os.close(wfd)
            return False, "開不起來 %s：%s" % (target, e)
        os.close(wfd)
        r = Entry(key, p, target, args, rfd)
        self.table[key] = r
        r.thread = _thread(read_stderr, r, self.say)
        r.sthread = _thread(read_status, r)
        self.say("add %s pid=%d target=%s args=%s" % (key, p.pid, target, args))
        return True, r.entry()

    def remove(self, f, force=False):
        """送 SIGTERM 就**立刻回** `stopping`：等它退是主迴圈（`advance`／`reap`）的事。

        `force`＝0.2 秒後再補一發 SIGTERM（腰斬正在跑的那次，退出碼 143）；5 秒還不退
        ＝SIGKILL 整個 group。已經在收的再 rm＝冪等（restart 收到一半的會改成單純 rm，
        不再重開）。`f` 是那份 inst.json 的路徑，存不存在都照 realpath 查表。
        """
        key = key_of(f)
        r = self.table.get(key)
        if r is None:
            return False, "沒有在跑：%s" % key
        if r.state in (STOPPING, RESTARTING):
            if force and r.force_at is None:
                r.force_at = time.monotonic()
            r.state = STOPPING
            return True, "stopping"
        self.say(r.begin_stop(STOPPING, force))
        return True, "stopping"

    def restart(self, target, args=()):
        """換旗標＝請舊的退（SIGTERM），**收屍時**用新旗標同 key 再開一顆。立刻回。

        跟舊版的「remove 再 add」比，中間那段空窗這一筆還在表上（狀態 `restarting`），
        別人趁隙 `add` 會被擋掉。target 跟 `add` 一樣只收 `.json`。
        """
        bad = json_only(target)
        if bad:
            return False, bad
        key = key_of(target)
        r = self.table.get(key)
        if r is None:
            return False, "沒有在跑：%s" % key
        r.new_args = [str(a) for a in args]
        r.target = os.path.abspath(target)
        if r.state in (STOPPING, RESTARTING):
            r.state = RESTARTING        # 已經送過 SIGTERM 了，改成收屍後重開
        else:
            self.say(r.begin_stop(RESTARTING))
        return True, "restarting"

    def get(self, f):
        key = key_of(f)
        r = self.table.get(key)
        if r is None:
            return False, "沒有在跑：%s" % key
        return True, r.entry()

    def ls(self):
        return True, {k: r.entry() for k, r in self.table.items()}

    def pause(self, f):
        """標 `pause_pending` 就回：真的 SIGSTOP 要等它睡著，主迴圈盯著。

        不打斷正在跑的那次——等 status 說它 `done` 了（`running == False`）才停。已經
        `paused`／`pause_pending` 的再 pause＝冪等。

        **不保證零次**：interval 很短時 SIGSTOP 可能剛好落在下一次開跑之後，那一次會整個
        跑完才真的停下來。
        """
        key = key_of(f)
        r = self.table.get(key)
        if r is None:
            return False, "沒有在跑：%s" % key
        if r.state in (STOPPING, RESTARTING):
            return False, "正在收掉，不能 pause：%s" % key
        if r.state != PAUSED:
            r.state = PAUSE_PENDING
            self.say("pause %s pid=%d（等它睡著）" % (key, r.proc.pid))
        return True, r.state

    def resume(self, f):
        """`paused`→SIGCONT；`pause_pending`→取消那個等待。本來就在跑＝冪等。"""
        key = key_of(f)
        r = self.table.get(key)
        if r is None:
            return False, "沒有在跑：%s" % key
        if r.state in (STOPPING, RESTARTING):
            return False, "正在收掉，不能 resume：%s" % key
        if r.state == PAUSED:
            r.sig(signal.SIGCONT)
        r.state = RUNNING
        self.say("resume %s pid=%d" % (key, r.proc.pid))
        return True, RUNNING

    # ── 請求（真東西在 aos_daemon_req.py）──────────────────
    def dispatch(self, req):
        return aos_daemon_req.dispatch(self, req)

    def handle_requests(self):
        return aos_daemon_req.handle_requests(self)

    # ── 狀態機、收屍、落地、主迴圈 ─────────────────────────
    def advance(self):
        """每一筆的狀態機推一格：該睡的睡、該補刀的補刀。不等、不睡，一圈很快。"""
        now = time.monotonic()
        for r in list(self.table.values()):
            msg = r.advance(now)
            if msg:
                self.say(msg)
                self.save()

    def reap(self):
        """退掉的（自己退的、被 rm 的、被 restart 的）從表拿掉、log 一行。

        `restarting` 的例外：拿掉之後馬上用新旗標同 key 再 `add` 一顆。其餘都不自動重開，
        那份 inst.json 之後可以再 `add`。
        """
        for key, r in list(self.table.items()):
            if r.alive():
                continue
            self.table.pop(key, None)
            r.join()                    # 等兩條執行緒把最後幾行讀完
            what = {STOPPING: "rm 掉了", RESTARTING: "restart 舊的退了"}.get(
                r.state, "自己退了")
            self.say("%s %s pid=%d exit=%s last=%s"
                     % (what, key, r.proc.pid, r.code(), r.last_line))
            if r.state == RESTARTING:
                self.add(r.target, r.new_args or [])
            self.save()

    def tick(self):
        """主迴圈的一圈：收請求、推狀態機、收屍。這一圈裡沒有任何等待。"""
        self.handle_requests()
        self.advance()
        self.reap()

    def save(self):
        write_json(self.home.statef, {"pid": os.getpid(), "home": self.home.dir,
                                      "runs": {k: r.entry() for k, r in self.table.items()}})

    def serve(self):
        """前台跑到收工為止（背景化是 CLI 的事）。SIGTERM＝跟 `{"op":"stop"}` 一樣。"""
        with open(self.home.pidf, "w") as f:
            f.write(str(os.getpid()))
        for s in (signal.SIGTERM, signal.SIGINT):
            signal.signal(s, lambda *_: setattr(self, "stopping", True))
        self.say("起來了 pid=%d home=%s" % (os.getpid(), self.home.dir))
        self.save()
        last = 0.0
        try:
            while not self.stopping:
                self.tick()
                if time.monotonic() - last >= SAVE:
                    self.save()
                    last = time.monotonic()
                t0 = time.monotonic()
                while time.monotonic() - t0 < TICK and not self.stopping:
                    time.sleep(0.02)
        finally:
            self.shutdown()

    def shutdown(self):
        """收工：全部 SIGCONT＋SIGTERM，同步等（上限 5 秒），還活著就 SIGKILL 整個 group。

        **這裡可以卡**——收工就是要等大家走乾淨，跟「主迴圈不等人」是兩件事。
        """
        self.say("收工中：%d 個 aos-run 送 SIGTERM" % len(self.table))
        for r in self.table.values():
            r.sig(signal.SIGCONT)                       # 暫停中的要先叫醒才收得到
            r.sig(signal.SIGTERM)
        t0 = time.monotonic()
        while time.monotonic() - t0 < TERM_WAIT:
            if all(not r.alive() for r in self.table.values()):
                break
            time.sleep(0.02)
        for key, r in list(self.table.items()):
            if r.alive():
                r.killpg()
                try:
                    r.proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    pass
            r.join()
            self.say("收工帶走 %s pid=%d exit=%s last=%s"
                     % (key, r.proc.pid, r.code(), r.last_line))
        self.table.clear()
        for f in (self.home.statef, self.home.pidf):
            try:
                os.remove(f)
            except OSError:
                pass
        self.say("收工了 pid=%d" % os.getpid())

    def say(self, s):
        with self._lock:
            try:
                with open(self.home.logf, "a", encoding="utf-8") as f:
                    f.write("%s %s\n" % (time.strftime("%H:%M:%S"), s))
            except OSError:
                pass


def _thread(fn, *args):
    t = threading.Thread(target=fn, args=args, daemon=True)
    t.start()
    return t
