"""探針共用小工具：開暫存空間根、建 node、起 daemon、等條件、讀狀態、收乾淨（不留程序與暫存）。

每個探針 `probes/<名字>/probe.py` 的寫法：

    import probelib as pl
    def main():
        r = pl.Result("名字")
        with pl.Space("名字") as sp:
            sp.node("a", [{"name": "q", "argv": ["true"]}], interval_ms=100)
            sp.start()
            sp.wait_for(lambda: sp.round_of("a") >= 3)
            r.check("跑到第 3 回合", sp.round_of("a") >= 3)
            r.measure("某個數字", 12)
            r.finding("基礎設施缺什麼的一句話")
        return r.done()          # 印結果，回退出碼（全部 check 過＝0）

跑：`python3 proto7-1/probes/<名字>/probe.py`；全部跑：`python3 proto7-1/probes/run_all.py`。
"""
import glob
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
P71 = os.path.dirname(HERE)
LIB = os.path.join(P71, "lib")
BIN = os.path.join(P71, "bin")
sys.path.insert(0, LIB)

import aos7_fs as fs  # noqa: E402
import aos7_task  # noqa: E402

PREFIX = "aos7probe-"
PY = sys.executable


class ProbeTimeout(Exception):
    pass


def our_procs(prefix):
    """還活著、環境變數 AOS7_ROOT 以 prefix 開頭的程序（孤兒檢查）。"""
    found = []
    for env_path in glob.glob("/proc/[0-9]*/environ"):
        try:
            with open(env_path, "rb") as f:
                env = f.read().split(b"\0")
        except OSError:
            continue
        for kv in env:
            if kv.startswith(b"AOS7_ROOT=") and kv[10:].decode(errors="replace").startswith(prefix):
                found.append(int(env_path.split("/")[2]))
                break
    return [p for p in found if p != os.getpid()]


def daemon_procs(prefix):
    """還活著、命令列是 aos7-daemon <prefix...> 的程序。"""
    found = []
    for cmd_path in glob.glob("/proc/[0-9]*/cmdline"):
        try:
            with open(cmd_path, "rb") as f:
                argv = f.read().split(b"\0")
        except OSError:
            continue
        if any(a.endswith(b"aos7-daemon") for a in argv) and any(a.decode(errors="replace").startswith(prefix) for a in argv):
            found.append(int(cmd_path.split("/")[2]))
    return [p for p in found if p != os.getpid()]


def write(path, obj):
    """寫檔：dict／list 寫 JSON（原子），字串原樣。"""
    if isinstance(obj, (dict, list)):
        fs.write_json(path, obj)
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(obj)


class Space:
    """一個暫存空間根（可再開幾個，給跨 daemon 用）。離開 with 時停掉所有 daemon、殺掉殘留任務、刪資料夾。"""

    def __init__(self, name):
        self.name = name
        self.base = os.path.realpath(tempfile.mkdtemp(prefix=PREFIX + name + "-"))
        self.root = os.path.join(self.base, "root")
        os.makedirs(self.root)
        self.procs = []           # [(root, Popen)]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cleanup()
        return False

    # ---------- 建東西 ----------

    def new_root(self, name):
        """在同一個暫存底下多開一個空間根（路二：跨 daemon）。"""
        r = os.path.join(self.base, name)
        os.makedirs(r, exist_ok=True)
        return r

    def path(self, nid, *rest, root=None):
        return os.path.join(fs.node_path(root or self.root, nid), *rest)

    def node(self, nid, tasks=None, interval_ms=100, files=None, root=None, **tasks_extra):
        """建 node：`.aos/timeline.json`、`.aos/tasks.json`（tasks＋頂層其他鍵，如 mount_allow），files＝{相對 node 的路徑: 內容}。"""
        n = fs.node_path(root or self.root, nid)
        fs.write_json(os.path.join(n, ".aos", "timeline.json"), {"interval_ms": interval_ms})
        t = dict(tasks_extra)
        t["tasks"] = tasks or []
        fs.write_json(os.path.join(n, ".aos", "tasks.json"), t)
        for rel, obj in (files or {}).items():
            write(os.path.join(n, rel), obj)
        return n

    # ---------- daemon ----------

    def start(self, root=None, env=None):
        root = root or self.root
        e = fs.env_with_bin()
        e.update(env or {})
        out = open(os.path.join(self.base, "daemon-%d.out" % len(self.procs)), "w")
        p = subprocess.Popen([PY, os.path.join(BIN, "aos7-daemon"), root], stdout=out,
                             stderr=subprocess.STDOUT, env=e, start_new_session=True)
        out.close()
        self.procs.append((root, p))
        return p

    def ctl(self, op, node=None, kill=False, root=None, by="probe"):
        obj = {"op": op, "by": by}
        if node is not None:
            obj["node"] = node
        if kill:
            obj["kill"] = True
        name = "probe-%d-%d.json" % (time.time_ns(), os.getpid())
        fs.write_json(os.path.join(root or self.root, ".aosd", "ctl", name), obj)
        return name

    # ---------- 讀 ----------

    def status(self, root=None):
        return fs.read_json(os.path.join(root or self.root, ".aosd", "status.json"), {}) or {}

    def log(self, root=None):
        return fs.read_jsonl(os.path.join(root or self.root, ".aosd", "log.jsonl"))

    def round_of(self, nid, root=None):
        r = fs.read_json(self.path(nid, ".aos", "round.json", root=root), {}) or {}
        return r.get("round", 0)

    def rounds(self, nid, root=None):
        return fs.read_jsonl(self.path(nid, ".aos", "rounds.jsonl", root=root))

    def tasks(self, nid, root=None):
        return aos7_task.list_tasks(fs.node_path(root or self.root, nid))

    def live(self, nid, root=None):
        return aos7_task.live_tasks(fs.node_path(root or self.root, nid))

    def task_file(self, nid, tid, name, root=None):
        return fs.read_json(os.path.join(aos7_task.task_dir(fs.node_path(root or self.root, nid), tid), name))

    def wait_for(self, cond, timeout=10.0, poll=0.05, msg="條件沒成立"):
        end = time.monotonic() + timeout
        while True:
            v = cond()
            if v:
                return v
            if time.monotonic() >= end:
                raise ProbeTimeout("%s（%.1f 秒）" % (msg, timeout))
            time.sleep(poll)

    # ---------- 收 ----------

    def stop_all(self, timeout=10.0):
        """對每個還活著的 daemon 寫 stop+kill，等它退出；回 {root: 退出碼或 None（逾時）}。"""
        res = {}
        for root, p in self.procs:
            if p.poll() is None:
                try:
                    self.ctl("stop", kill=True, root=root)
                except OSError:
                    pass
        for root, p in self.procs:
            try:
                res[root] = p.wait(timeout)
            except subprocess.TimeoutExpired:
                res[root] = None
        return res

    def cleanup(self):
        self.stop_all()
        for _, p in self.procs:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
            if p.poll() is None:
                p.kill()
            p.wait()
        for d, _, files in os.walk(self.base):
            if "pid.json" in files:
                pid = fs.read_json(os.path.join(d, "pid.json"), {}) or {}
                for f, x in ((os.killpg, pid.get("pgid")), (os.kill, pid.get("runner_pid"))):
                    try:
                        f(x, signal.SIGKILL)
                    except (OSError, TypeError):
                        pass
        for pid in our_procs(self.base) + daemon_procs(self.base):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        for _ in range(10):
            shutil.rmtree(self.base, ignore_errors=True)
            if not os.path.exists(self.base):
                break
            time.sleep(0.1)


class Result:
    """探針結果：check（該發生的有沒有發生）、measure（量到的數字）、finding（基礎設施缺什麼）。"""

    def __init__(self, name):
        self.name = name
        self.checks, self.measures, self.findings = [], {}, []
        self.t0 = time.monotonic()

    def check(self, what, ok, detail=None):
        self.checks.append({"what": what, "ok": bool(ok), "detail": detail})
        return bool(ok)

    def measure(self, key, value):
        self.measures[key] = value

    def finding(self, text):
        self.findings.append(text)

    def done(self):
        ok = all(c["ok"] for c in self.checks)
        print("== 探針 %s（%.1f 秒）" % (self.name, time.monotonic() - self.t0))
        for c in self.checks:
            print("  [%s] %s%s" % ("OK" if c["ok"] else "NG", c["what"],
                                   "" if c["detail"] is None else "  — %s" % (c["detail"],)))
        for k, v in self.measures.items():
            print("  量：%s = %s" % (k, json.dumps(v, ensure_ascii=False)))
        for f in self.findings:
            print("  發現：%s" % f)
        print(json.dumps({"probe": self.name, "ok": ok, "checks": len(self.checks),
                          "failed": [c["what"] for c in self.checks if not c["ok"]]}, ensure_ascii=False))
        return 0 if ok else 1


def run_main(main):
    """探針入口：例外也要收乾淨（Space 的 with 已處理），退出碼照 main 回的。"""
    try:
        sys.exit(main())
    except ProbeTimeout as e:
        print("逾時：%s" % e)
        sys.exit(2)
