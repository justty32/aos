#!/usr/bin/env python3
"""aos-daemon：提供基礎——管所有 cpu（每顆 cpu 就是一個 aos_cpu.py 進程）。

    python3 aos_daemon.py start|run|stop [--home H]

家目錄走 --home 或環境變數 AOS_HOME。裡面：

    H/requests/            使用者面的請求（CLI 寫這裡，只有 kernel 讀）
    H/kernel/              第一顆 cpu 跑的 proc（daemon 起來時自動生 .aos/inst.json）
    H/daemon/daemon.pid    daemon 的 pid
    H/daemon/state.json    每輪寫一次：daemon pid ＋ 每顆 cpu 的 pid／alive／tick／rss_kb
    H/daemon/cpus.json     登記表（每輪落地；重開不接回，最簡版）
    H/daemon/daemon.log    daemon 與各 cpu 的 stdout／stderr
    H/daemon/requests/     daemon 請求（只有 kernel 該寫），處理完搬到 requests/done/

一個 proc 的本體＝它的 cwd（資料夾），也是它的唯一標示：一個資料夾最多一顆 cpu。
所以「表」的 key 一律是那個資料夾的絕對路徑（先 os.path.realpath() 正規化過，
symlink／`..`／尾巴 `/` 都算同一個），沒有另外取名字這回事。

daemon 請求只有三個 op：
    {"op":"spawn","dir":…,"interval":…}   開一顆 cpu 去跑那個資料夾（那個資料夾已經有一顆在跑＝拒絕）
    {"op":"kill","dir":…}                  SIGTERM 那顆 cpu（那個資料夾沒在跑＝拒絕）
    {"op":"ls"}                            回登記表

start 的第一件事就是開第一顆 cpu 跑 kernel（跟真的作業系統一樣），所以 daemon 與
kernel 是綁在一起的；kernel 那顆 cpu 的 key 就是它的路徑 H/kernel。
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time

from aos_cpu import write_json

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL_INTERVAL = 1.0
TURN = 0.5              # 主 loop 一輪


class DaemonError(Exception):
    """使用者／kernel 端可預期的拒絕（已經在跑、沒在跑…），不是程式炸了。"""


class Home:
    def __init__(self, d):
        self.dir = os.path.abspath(d)
        self.requests = os.path.join(self.dir, "requests")           # 使用者面
        self.done = os.path.join(self.requests, "done")
        self.kernel = os.path.join(self.dir, "kernel")
        self.daemon = os.path.join(self.dir, "daemon")
        self.dreq = os.path.join(self.daemon, "requests")            # daemon 面
        self.ddone = os.path.join(self.dreq, "done")
        self.pidf = os.path.join(self.daemon, "daemon.pid")
        self.statef = os.path.join(self.daemon, "state.json")
        self.cpusf = os.path.join(self.daemon, "cpus.json")
        self.logf = os.path.join(self.daemon, "daemon.log")

    def ensure(self):
        for p in (self.dir, self.requests, self.done, self.kernel,
                  self.daemon, self.dreq, self.ddone):
            os.makedirs(p, exist_ok=True)

    def pid(self):
        try:
            with open(self.pidf) as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return None

    def alive(self):
        return alive(self.pid())

    def state(self):
        try:
            with open(self.statef) as f:
                return json.load(f)
        except (OSError, ValueError):
            return None


def alive(pid):
    """活著＝/proc 有它、而且不是殭屍。"""
    if not pid:
        return False
    try:
        with open("/proc/%d/stat" % pid) as f:
            st = f.read()
    except OSError:
        return False
    return st[st.rindex(")") + 2] != "Z"


def rss_kb(pid):
    """佔用資源：/proc/<pid>/status 的 VmRSS。"""
    try:
        with open("/proc/%d/status" % pid) as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def cpu_tick(d):
    try:
        with open(os.path.join(d, ".aos", "cpu.json")) as f:
            return json.load(f)["tick"]
    except (OSError, ValueError, KeyError):
        return 0


# ── daemon 本體 ──────────────────────────────────────────

class Daemon:
    def __init__(self, home):
        self.home = home
        self.cpus = {}          # 資料夾絕對路徑(realpath) -> {"proc": Popen, "pid", "dir", "interval"}
        self.reaping = []       # 已經 SIGTERM、還在等它斷氣的（不收就變殭屍）
        self.stopping = False
        self.log = None

    # ── cpu ────────────────────────────────
    def spawn(self, d, interval):
        d = os.path.realpath(d)
        if d in self.cpus:                  # 一個資料夾最多一顆 cpu：第二次＝拒絕，舊的不動
            raise DaemonError("already running: %s" % d)
        p = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "aos_cpu.py"), d, "--interval", str(interval)],
            cwd=d, stdin=subprocess.DEVNULL, stdout=self.log, stderr=self.log)
        self.cpus[d] = {"proc": p, "pid": p.pid, "dir": d, "interval": interval}
        self.say("spawn pid=%d dir=%s 每 %s 秒" % (p.pid, d, interval))
        return {"dir": d, "pid": p.pid, "interval": interval}

    def kill(self, d):
        d = os.path.realpath(d)
        c = self.cpus.pop(d, None)
        if not c:
            raise DaemonError("not running: %s" % d)
        try:
            c["proc"].terminate()
        except OSError:
            pass
        self.reaping.append(c["proc"])
        self.say("kill dir=%s pid=%d" % (d, c["pid"]))
        return {"dir": d, "pid": c["pid"]}

    def ls(self):
        return self.table()

    def table(self):
        """每顆 cpu 現在長怎樣：pid 活不活、跑到第幾格、佔多少記憶體。key＝資料夾路徑。"""
        t = {}
        for dpath, c in self.cpus.items():
            c["proc"].poll()                     # 順手收殭屍
            a = c["proc"].returncode is None
            t[dpath] = {"pid": c["pid"], "dir": c["dir"], "interval": c["interval"],
                        "alive": a, "tick": cpu_tick(c["dir"]),
                        "rss_kb": rss_kb(c["pid"]) if a else None}
        return t

    # ── 請求 ────────────────────────────────
    def handle_requests(self):
        names = sorted(n for n in os.listdir(self.home.dreq)
                       if n.endswith(".json") and os.path.isfile(os.path.join(self.home.dreq, n)))
        for n in names:
            src = os.path.join(self.home.dreq, n)
            try:
                with open(src) as f:
                    req = json.load(f)
                op = req["op"]
                if op == "spawn":
                    r = self.spawn(req["dir"], req.get("interval", 1))
                elif op == "kill":
                    r = self.kill(req["dir"])
                elif op == "ls":
                    r = self.ls()
                else:
                    raise KeyError(op)
                out = {"req": req, "ok": True, "result": r}
            except DaemonError as e:
                out = {"req": req, "ok": False, "result": str(e)}
                self.say("請求 %s 被拒：%s" % (n, out["result"]))
            except Exception as e:
                out = {"req": n, "ok": False, "result": "%s: %s" % (type(e).__name__, e)}
                self.say("請求 %s 失敗：%s" % (n, out["result"]))
            os.remove(src)
            write_json(os.path.join(self.home.ddone, n), out)

    # ── 生命週期 ─────────────────────────────
    def say(self, s):
        print("[daemon] " + s, flush=True)

    def ensure_kernel_inst(self):
        """kernel 也是一個普通的 proc：沒有 inst.json 就替它生一份。"""
        f = os.path.join(self.home.kernel, ".aos", "inst.json")
        if not os.path.exists(f):
            write_json(f, {"argv": [sys.executable, os.path.join(HERE, "aos_kernel.py")],
                           "env": {"AOS_HOME": self.home.dir}})

    def save(self):
        t = self.table()
        write_json(self.home.cpusf, {dpath: {k: c[k] for k in ("pid", "dir", "interval")}
                                     for dpath, c in self.cpus.items()})
        write_json(self.home.statef, {"pid": os.getpid(), "cpus": t})

    def serve(self):
        self.home.ensure()
        self.log = open(self.home.logf, "ab", buffering=0)
        os.dup2(self.log.fileno(), 1)
        os.dup2(self.log.fileno(), 2)
        with open(self.home.pidf, "w") as f:
            f.write(str(os.getpid()))
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stopping", True))
        self.say("起來了 pid=%d home=%s" % (os.getpid(), self.home.dir))
        self.ensure_kernel_inst()
        self.spawn(self.home.kernel, KERNEL_INTERVAL)   # 最初的那顆 cpu，key＝它的路徑 H/kernel
        try:
            while not self.stopping:
                self.handle_requests()
                self.reaping = [p for p in self.reaping if p.poll() is None]   # 收殭屍
                self.save()
                t0 = time.time()
                while time.time() - t0 < TURN and not self.stopping:
                    time.sleep(0.05)
        finally:
            self.shutdown()

    def shutdown(self):
        self.say("收工中：SIGTERM 所有 cpu")
        procs = [c["proc"] for c in self.cpus.values()] + self.reaping
        for dpath in list(self.cpus):
            self.kill(dpath)
        t0 = time.time()                            # 等它們跑完手上那次
        while time.time() - t0 < 5.0 and any(p.poll() is None for p in procs):
            time.sleep(0.05)
        for p in procs:
            if p.poll() is None:
                p.kill()
            p.wait()
        for f in (self.home.statef, self.home.pidf):
            try:
                os.remove(f)
            except OSError:
                pass
        self.say("收工了 pid=%d" % os.getpid())


# ── 客戶端 ───────────────────────────────────────────────

_spawned = []       # 留著 Popen 的參考，免得 GC 掉時噴 ResourceWarning


def start(home, timeout=10.0):
    """開背景 daemon。等到 state.json 冒出來、pid 對得上才回「起來了」。"""
    if home.alive():
        print("已經在跑（pid %d）" % home.pid())
        return False
    home.ensure()
    with open(home.logf, "ab") as log:
        _spawned.append(subprocess.Popen(
            [sys.executable, os.path.join(HERE, "aos_daemon.py"), "run", "--home", home.dir],
            stdout=log, stderr=log, stdin=subprocess.DEVNULL,
            start_new_session=True, cwd=home.dir))
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = home.state()
        if home.alive() and st and st.get("pid") == home.pid():
            print("起來了（pid %d，家在 %s）" % (home.pid(), home.dir))
            return True
        time.sleep(0.05)
    print("開了但等不到 state.json，看 " + home.logf, file=sys.stderr)
    return False


def stop(home, timeout=10.0):
    """SIGTERM daemon；它自己會收掉所有 cpu、刪 state.json。"""
    pid = home.pid()
    if not home.alive():
        print("本來就沒在跑")
        return True
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not alive(pid):
            print("收工了（pid %d）" % pid)
            return True
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    print("收不掉，只好 KILL（pid %d）" % pid, file=sys.stderr)
    return False


def main():
    ap = argparse.ArgumentParser(prog="aos-daemon")
    ap.add_argument("cmd", choices=["start", "run", "stop"])
    ap.add_argument("--home", default=os.environ.get("AOS_HOME"))
    a = ap.parse_args()
    if not a.home:
        print("沒有家：給 --home 或設 AOS_HOME", file=sys.stderr)
        return 2
    home = Home(a.home)
    if a.cmd == "run":
        Daemon(home).serve()
        return 0
    if a.cmd == "start":
        return 0 if start(home) else 1
    return 0 if stop(home) else 1


if __name__ == "__main__":
    sys.exit(main())
