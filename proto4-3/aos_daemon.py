#!/usr/bin/env python3
"""aos-daemon：一個常駐進程，裡面就是一個 dict——key＝資料夾，value＝正在跑的 aos-run。

[proto4 筆記第 13 節](../proto4/notes/2026-09-08-ideas.md)的原型。value 是**一個
`aos-run` 子進程**（不是在 daemon 自己進程裡跑 `run_loop`），所以暫停／繼續＝SIGSTOP／
SIGCONT、刪＝SIGTERM，進程的事交給 Linux 管。這裡只有本體（dict、七個動作、主迴圈），
命令列入口是 `aos-daemon`（前台程式，不背景化）、下指令的是 `aos_daemon_ctl.py`；
七個動作都是 `Daemon` 的方法、都回 `(ok, result)`，所以測試可以不開 daemon 進程直接叫。
"""
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time

from aos_home import Home, write_json      # noqa: F401  （Home 讓外面 import 這裡就夠）

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, "aos-run")
TICK = 0.2              # 主迴圈：多久掃一次 requests/
SAVE = 0.5              # 多久寫一次 state.json
TERM_WAIT = 5.0         # remove：等 aos-run 跑完手上那次的上限
FORCE_GAP = 0.2         # 兩次 SIGTERM 之間要隔一下，不然會被併成一次
LINE = re.compile(r"^aos-run: #(\d+) exit=(-?\d+)")     # aos-run 每跑完一次印的那行


def base_dir(target):
    """key＝目標**基準資料夾**的 realpath：資料夾→它自己；`.json`／普通檔案→它所在的
    資料夾。symlink、`..`、尾巴的 `/` 算同一個。不拿 inst.json 的 `cwd` 當 key（§13.1）。
    """
    p = os.path.abspath(target)
    if not os.path.isdir(p):
        p = os.path.dirname(p)
    return os.path.realpath(p)


class Run:
    """表上的一筆：一個 aos-run 子進程 ＋ 從它 stderr 解出來的近況。"""

    def __init__(self, key, proc, target, args):
        self.key = key
        self.proc = proc
        self.target = target
        self.args = list(args)
        self.started_at = time.time()
        self.paused = False
        self.runs = 0                   # 最後一個 `#n`
        self.last_exit = None           # 最後一個 `exit=c`
        self.last_line = None           # 最後一行原文（停下來時是 `aos-run: stop …`）
        self.thread = None

    def entry(self):
        return {"pid": self.proc.pid, "target": self.target, "args": self.args,
                "started_at": self.started_at, "paused": self.paused,
                "runs": self.runs, "last_exit": self.last_exit,
                "last_line": self.last_line, "alive": self.proc.poll() is None}


class Daemon:
    def __init__(self, home):
        self.home = home
        self.home.ensure()
        self.table = {}                 # 資料夾 realpath -> Run
        self.stopping = False
        self._lock = threading.Lock()   # daemon.log 是好幾條執行緒一起寫的

    # ── 七個動作，一律回 (ok, result) ─────────────────────
    def add(self, target, args=()):
        """開一個 `aos-run <target> <旗標…>` 子進程，記進表。同 key 第二次＝拒絕。"""
        key = base_dir(target)
        if key in self.table:
            return False, "已經有一個在跑：%s" % key
        target = os.path.abspath(target)
        if not os.path.exists(target):
            return False, "找不到 %s" % target
        args = [str(a) for a in args]
        p = subprocess.Popen([sys.executable, RUN, target] + args,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE, start_new_session=True)
        r = Run(key, p, target, args)
        self.table[key] = r
        r.thread = threading.Thread(target=self._read, args=(r,), daemon=True)
        r.thread.start()
        self.say("add %s pid=%d target=%s args=%s" % (key, p.pid, target, args))
        return True, r.entry()

    def remove(self, d, force=False):
        """SIGTERM（aos-run 跑完手上那次自己退）→ 等它退 → 從表拿掉。`force`＝再送第二次
        （腰斬，退出碼 143），還不退就 SIGKILL 整個 group。暫停中的先 SIGCONT，不然收不到。
        """
        key = os.path.realpath(d)
        r = self.table.get(key)
        if r is None:
            return False, "沒有在跑：%s" % key
        if r.paused:
            self._sig(r, signal.SIGCONT)
            r.paused = False
        self._sig(r, signal.SIGTERM)
        if force:
            time.sleep(FORCE_GAP)
            self._sig(r, signal.SIGTERM)
        if not self._wait(r, TERM_WAIT):
            self._killpg(r)
            self._wait(r, 2.0)
        self.table.pop(key, None)
        code = r.proc.poll()
        code = code if code is None or code >= 0 else 128 - code    # 被訊號 N 砍＝128+N
        r.thread.join(1.0)
        self.say("remove %s pid=%d exit=%s last=%s" % (key, r.proc.pid, code, r.last_line))
        return True, {"dir": key, "pid": r.proc.pid, "exit": code, "last_line": r.last_line}

    def restart(self, target, args=()):
        """換旗標＝`remove`（不 force）再 `add`——aos-run 開跑後旗標改不了。"""
        key = base_dir(target)
        if key not in self.table:
            return False, "沒有在跑：%s" % key
        ok, res = self.remove(key)
        if not ok:
            return ok, res
        return self.add(target, args)

    def get(self, d):
        key = os.path.realpath(d)
        r = self.table.get(key)
        if r is None:
            return False, "沒有在跑：%s" % key
        return True, r.entry()

    def ls(self):
        return True, {k: r.entry() for k, r in self.table.items()}

    def pause(self, d):
        """SIGSTOP。正在跑的那次會自己跑完（它在別的 session），只是不會開下一次。"""
        return self._flip(d, True)

    def resume(self, d):
        return self._flip(d, False)

    def _flip(self, d, paused):
        key = os.path.realpath(d)
        r = self.table.get(key)
        if r is None:
            return False, "沒有在跑：%s" % key
        self._sig(r, signal.SIGSTOP if paused else signal.SIGCONT)
        r.paused = paused
        self.say("%s %s pid=%d" % ("pause" if paused else "resume", key, r.proc.pid))
        return True, r.entry()

    # ── 請求 ─────────────────────────────────────────
    def dispatch(self, req):
        """一個請求 → `(ok, result)`。不認得的 op／缺欄位一律 `ok:false`。"""
        if not isinstance(req, dict):
            return False, "請求不是一個 JSON 物件"
        op = req.get("op")
        try:
            if op == "add":
                return self.add(req["target"], req.get("args") or [])
            if op == "remove":
                return self.remove(req["dir"], bool(req.get("force")))
            if op == "restart":
                return self.restart(req["target"], req.get("args") or [])
            if op == "get":
                return self.get(req["dir"])
            if op == "ls":
                return self.ls()
            if op == "pause":
                return self.pause(req["dir"])
            if op == "resume":
                return self.resume(req["dir"])
            if op == "stop":
                self.stopping = True
                return True, "收工中"
        except KeyError as e:
            return False, "缺欄位 %s" % e
        return False, "不認得的 op：%r" % (op,)

    def handle_requests(self):
        """掃 requests/*.json（`.tmp` 忽略）、處理、搬到 done/ 同名＋ok／result。"""
        try:
            names = sorted(n for n in os.listdir(self.home.requests) if n.endswith(".json"))
        except OSError:
            return
        for n in names:
            src = os.path.join(self.home.requests, n)
            if not os.path.isfile(src):
                continue
            req = None
            try:
                with open(src, encoding="utf-8") as f:
                    req = json.load(f)
                ok, res = self.dispatch(req)
            except Exception as e:                          # 壞掉的請求檔也要有回音
                ok, res = False, "%s: %s" % (type(e).__name__, e)
            if not ok:
                self.say("請求 %s 被拒：%s" % (n, res))
            try:
                os.remove(src)
            except OSError:
                pass
            if ok: self.save()                  # 先落地再回音，CLI 收到 done 時 ls 已是新的
            out = dict(req) if isinstance(req, dict) else {"req": n}
            out["ok"], out["result"] = ok, res
            write_json(os.path.join(self.home.done, n), out)

    # ── 收屍、落地、主迴圈 ────────────────────────────────
    def reap(self):
        """aos-run 自己退了就從表拿掉、log 記一行。不自動重開；那個資料夾之後可以再 `add`。"""
        for key, r in list(self.table.items()):
            if r.proc.poll() is None:
                continue
            self.table.pop(key, None)
            r.thread.join(1.0)              # 等 stderr 那條把最後一行（stop …）讀完
            self.say("自己退了 %s pid=%d exit=%s last=%s"
                     % (key, r.proc.pid, r.proc.returncode, r.last_line))
            self.save()

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
                self.handle_requests()
                self.reap()
                if time.monotonic() - last >= SAVE:
                    self.save()
                    last = time.monotonic()
                t0 = time.monotonic()
                while time.monotonic() - t0 < TICK and not self.stopping:
                    time.sleep(0.02)
        finally:
            self.shutdown()

    def shutdown(self):
        """收工：所有 aos-run 送 SIGTERM、等它們跑完手上那次退，再刪掉 pid／state。"""
        self.say("收工中：%d 個 aos-run 送 SIGTERM" % len(self.table))
        for key in list(self.table):
            self.remove(key)
        for f in (self.home.statef, self.home.pidf):
            try:
                os.remove(f)
            except OSError:
                pass
        self.say("收工了 pid=%d" % os.getpid())

    # ── 小工具 ───────────────────────────────────────
    def _read(self, r):
        """一條執行緒逐行讀 aos-run 的 stderr：原樣進 daemon.log，順手解析近況。"""
        for raw in r.proc.stderr:                       # 一行一行來，不等它退
            line = raw.decode("utf-8", "replace").rstrip("\n")
            m = LINE.match(line)
            if m:
                r.runs, r.last_exit = int(m.group(1)), int(m.group(2))
            r.last_line = line
            self.say("%s %s" % (r.key, line))
        try:
            r.proc.stderr.close()
        except OSError:
            pass

    def say(self, s):
        with self._lock:
            try:
                with open(self.home.logf, "a", encoding="utf-8") as f:
                    f.write("%s %s\n" % (time.strftime("%H:%M:%S"), s))
            except OSError:
                pass

    def _sig(self, r, sig):
        try:
            os.kill(r.proc.pid, sig)
        except OSError:                     # 已經死了＝ESRCH，無害
            pass

    def _killpg(self, r):
        try:
            os.killpg(os.getpgid(r.proc.pid), signal.SIGKILL)
        except OSError:
            pass

    @staticmethod
    def _wait(r, secs):
        t0 = time.monotonic()
        while time.monotonic() - t0 < secs:
            if r.proc.poll() is not None:
                return True
            time.sleep(0.02)
        return r.proc.poll() is not None
