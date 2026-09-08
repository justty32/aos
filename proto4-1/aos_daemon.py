#!/usr/bin/env python3
"""aos-daemon（Python 版）：一個常駐進程裡跑一個 kernel。外面的人靠丟 JSON 請求檔跟它講話。

    python3 aos_daemon.py start|run|stop|ls [--home DIR] [--interval SEC]
    python3 aos_daemon.py register DIR [NAME] [INTERVAL] [--home DIR] [--no-wait]
    python3 aos_daemon.py unregister|pause|resume NAME [--home DIR] [--no-wait]
    python3 aos_daemon.py req '{"op": "...", ...}' [--home DIR]     # 直接丟任意請求

home：--home > 環境變數 AOS_DAEMON_DIR > 退 2。第一次 start 自己建。裡面：
    kernel.pid       daemon 的 pid
    state.json       每格寫一次：pid／steps／interval／updated／procs（ls 讀這個，daemon 沒跑也讀得到）
    procs.json       登記表，每次變動就寫；重開時接回來（proto2 教訓 28：登記要持久化）
    kernel.log       daemon 的 stdout／stderr
    requests/        請求檔 <毫秒>-<pid>-<流水>.json；處理完搬到 requests/done/ 同名，多 ok／result
請求 JSON：{"op": "register", "dir": "...", "name": "...", "interval": N}
          {"op": "unregister"|"pause"|"resume", "name": "..."}
          {"op": "ls"} {"op": "steps"} {"op": "stop"} {"op": "set-interval", "sec": N}

跟 proto2 差在哪：只有一個進程一個 kernel，不再一個世界一個 aos-loop；暫停是 kernel 裡的旗子不是 SIGSTOP；
start 等到第一格跑完才回（教訓 26）；stop 不掉登記（procs.json）；inst 卡住走 config.json 的 timeout（教訓 06）。
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time

from aos_kernel import Kernel, parse_spec

HERE = os.path.dirname(os.path.abspath(__file__))


class Home:
    def __init__(self, d):
        self.dir = os.path.abspath(d)
        self.pidf = os.path.join(self.dir, "kernel.pid")
        self.statef = os.path.join(self.dir, "state.json")
        self.procsf = os.path.join(self.dir, "procs.json")
        self.logf = os.path.join(self.dir, "kernel.log")
        self.requests = os.path.join(self.dir, "requests")
        self.done = os.path.join(self.requests, "done")

    def ensure(self):
        for p in (self.dir, self.requests, self.done):
            os.makedirs(p, exist_ok=True)

    def pid(self):
        try:
            return int(open(self.pidf).read().strip())
        except (OSError, ValueError):
            return None

    def alive(self):
        pid = self.pid()
        if not pid:
            return False
        try:
            st = open("/proc/%d/stat" % pid).read()
        except OSError:
            return False
        return st[st.rindex(")") + 2] != "Z"     # 殭屍不算活著

    def state(self):
        try:
            return json.load(open(self.statef))
        except (OSError, ValueError):
            return None


def write_json(path, obj):
    """先寫 .tmp 再 rename，別人不會讀到半個。"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ── daemon 本體 ──────────────────────────────────────────

class Daemon:
    def __init__(self, home, interval=1.0):
        self.home = home
        self.k = Kernel()
        self.interval = interval
        self.stopping = False
        self.ops = {
            "register": lambda r: self.k.register(r["dir"], r.get("name"), r.get("interval")),
            "unregister": lambda r: self.k.unregister(r["name"]),
            "pause": lambda r: self.k.pause(r["name"]),
            "resume": lambda r: self.k.resume(r["name"]),
            "ls": lambda r: self.k.ls(),
            "steps": lambda r: self.k.steps,
            "stop": lambda r: self._stop(),
            "set-interval": lambda r: self._set_interval(float(r["sec"])),
        }

    def _stop(self):
        self.stopping = True
        return "跑完這格就收工"

    def _set_interval(self, sec):
        self.interval = sec
        return sec

    def load_procs(self):
        try:
            for p in json.load(open(self.home.procsf)):
                self.k.register(p["dir"], p["name"], p["interval"])
                if p.get("paused"):
                    self.k.pause(p["name"])
        except (OSError, ValueError):
            pass

    def save_procs(self):
        write_json(self.home.procsf, [{k: p[k] for k in ("dir", "name", "interval", "paused")} for p in self.k.ls()])

    def save_state(self):
        write_json(self.home.statef, {
            "pid": os.getpid(), "steps": self.k.steps, "interval": self.interval,
            "updated": time.time(), "procs": self.k.ls()})

    def handle_requests(self):
        names = sorted(n for n in os.listdir(self.home.requests)
                       if n.endswith(".json") and os.path.isfile(os.path.join(self.home.requests, n)))
        for n in names:
            src = os.path.join(self.home.requests, n)
            try:
                req = json.load(open(src))
                op = self.ops[req["op"]]
                out = {"req": req, "ok": True, "result": op(req)}
            except Exception as e:
                out = {"req": open(src).read(), "ok": False, "result": "%s: %s" % (type(e).__name__, e)}
            print("請求 %s → %s %s" % (n, "ok" if out["ok"] else "FAIL", out["result"]), flush=True)
            os.remove(src)
            write_json(os.path.join(self.home.done, n), out)
        if names:
            self.save_procs()

    def serve(self):
        self.home.ensure()
        open(self.home.pidf, "w").write(str(os.getpid()))
        self.load_procs()
        signal.signal(signal.SIGTERM, lambda *_: self._stop())   # 跑完這格乾淨收工
        try:
            while not self.stopping:
                self.handle_requests()
                if self.stopping:
                    self.save_state()
                    break
                self.k.step()
                self.save_procs()      # inst 用退出碼要求 pause／unregister 也會改登記表，每格落一次最省事
                self.save_state()
                if self.interval > 0:
                    time.sleep(self.interval)
        finally:
            self.save_procs()
            try:
                os.remove(self.home.pidf)
            except OSError:
                pass
            print("收工（pid %d，走了 %d 格）" % (os.getpid(), self.k.steps), flush=True)


# ── 客戶端 ───────────────────────────────────────────────

_seq = 0


def request(home, req, wait=True, timeout=5.0):
    """丟一個請求。wait 就等 done/ 冒出同名檔並回讀；daemon 沒活著就不等。"""
    global _seq
    home.ensure()
    _seq += 1
    name = "%013d-%d-%04d.json" % (time.time() * 1000, os.getpid(), _seq)
    write_json(os.path.join(home.requests, name), req)
    if not wait:
        return {"sent": name}
    if not home.alive():
        print("daemon 沒在跑，請求先放著：" + name)
        return {"sent": name, "pending": True}
    donef = os.path.join(home.done, name)
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.isfile(donef):
            return json.load(open(donef))
        time.sleep(0.05)
    return {"sent": name, "timeout": True}


def start(home, interval=1.0, timeout=5.0):
    """開背景 daemon。等到 pid 活著、第一格跑完才回 True（proto2 教訓 26：要有就緒語意）。"""
    if home.alive():
        print("已經在跑（pid %d）" % home.pid())
        return False
    home.ensure()
    log = open(home.logf, "ab")
    subprocess.Popen([sys.executable, os.path.join(HERE, "aos_daemon.py"), "run",
                      "--home", home.dir, "--interval", str(interval)],
                     stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                     start_new_session=True, cwd=home.dir)
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = home.state()
        if home.alive() and st and st.get("pid") == home.pid():
            print("起來了（pid %d，每 %s 秒一格）" % (home.pid(), interval))
            return True
        time.sleep(0.05)
    print("開了但等不到第一格，看 " + home.logf, file=sys.stderr)
    return False


def stop(home):
    """先請它自己收（stop 請求），不理就 TERM，再不理才 KILL。"""
    pid = home.pid()
    if not home.alive():
        print("本來就沒在跑")
        return True
    request(home, {"op": "stop"}, wait=False)
    for sig, wait_s in ((None, 3.0), (signal.SIGTERM, 2.0), (signal.SIGKILL, 1.0)):
        if sig:
            try:
                os.kill(pid, sig)
            except OSError:
                pass
        t0 = time.time()
        while time.time() - t0 < wait_s:
            if not home.alive():
                if os.path.exists(home.pidf):
                    os.remove(home.pidf)
                print("收工了（pid %d）" % pid)
                return True
            time.sleep(0.05)
    print("收不掉（pid %d）" % pid, file=sys.stderr)
    return False


def ls(home):
    st = home.state()
    alive = home.alive()
    if not st:
        print("kernel  %s  home=%s（還沒有 state.json）" % ("alive" if alive else "stopped", home.dir))
        return
    print("kernel  %s  pid=%s  steps=%d  interval=%s  home=%s" % (
        "alive" if alive else "stopped", st.get("pid"), st.get("steps", 0), st.get("interval"), home.dir))
    for p in st.get("procs", []):
        last = p.get("last") or {}
        print("  %-12s %s  每 %d 格  runs=%d%s%s" % (
            p["name"], p["dir"], p["interval"], p["runs"],
            "  paused" if p["paused"] else "",
            ("  error=" + p["error"]) if p.get("error") else ("  last=%s" % last.get("code") if last else "")))


def main():
    ap = argparse.ArgumentParser(prog="aos-daemon")
    ap.add_argument("cmd", choices=["start", "run", "stop", "ls", "register", "unregister", "pause", "resume", "req"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--home", default=os.environ.get("AOS_DAEMON_DIR"))
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--no-wait", action="store_true")
    a = ap.parse_args()
    if not a.home:
        print("沒有 home：給 --home 或設 AOS_DAEMON_DIR", file=sys.stderr)
        sys.exit(2)
    home = Home(a.home)
    c = a.cmd
    if c == "run":
        Daemon(home, a.interval).serve()
    elif c == "start":
        sys.exit(0 if start(home, a.interval) else 1)
    elif c == "stop":
        sys.exit(0 if stop(home) else 1)
    elif c == "ls":
        ls(home)
    else:
        if c == "register":
            d, name, iv = parse_spec(a.args[0])
            req = {"op": "register", "dir": os.path.realpath(d)}
            if len(a.args) > 1: req["name"] = a.args[1]
            elif name: req["name"] = name
            if len(a.args) > 2: req["interval"] = int(a.args[2])
            elif iv: req["interval"] = iv
        elif c == "req":
            req = json.loads(a.args[0])
        else:
            req = {"op": c, "name": a.args[0]}
        print(json.dumps(request(home, req, wait=not a.no_wait), ensure_ascii=False))


if __name__ == "__main__":
    main()
