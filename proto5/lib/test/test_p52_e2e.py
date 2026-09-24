"""proto5-2 真 daemon＋真 aos-cpu 的端到端（spec：kernel-pools、kernel-tick、handoff、cpu-notify、daemon-reconcile）。

每條都是真的 aos-daemon（第 2 版 info）、真的 aos-cpu、真的 tick 鏈；只有 kernel 的池表由測試直接改 info
（`cpu add` 的 CLI 是另一隊的，這裡用 set_count 代替——kernel-cli：cpu add 就是改 info，不放單）。
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

import aos_client
import aos_daemon
import aos_daemon_ticks
import aos_home
from _kernel_util import CLI, PY, KernelCase, read_json, wait_for

GATED = ("import os, sys, time\n"
         "from pathlib import Path\n"
         "Path(sys.argv[1]).write_text(str(os.getpid()))\n"
         "while not Path(sys.argv[2]).exists(): time.sleep(.005)\n"
         "sys.exit(int(sys.argv[3]))\n")
COUNT = "import sys; open(sys.argv[1], 'a').write('x\\n'); sys.exit(int(sys.argv[2]))"


class RespSpy:
    """背景每 1 ms 列一次 K/requests/，記下看過的 resp- 通知（kernel 最快下一格才刪，看得到）。"""

    def __init__(self, home):
        self.dir = Path(home) / "requests"
        self.seen = {}
        self._halt = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._halt.is_set():
            for name in os.listdir(self.dir):
                if name.startswith("resp-") and name.endswith(".json") and name not in self.seen:
                    body = read_json(self.dir / name)
                    if body is not None:
                        self.seen[name] = body
            time.sleep(.001)

    def close(self):
        self._halt.set()
        self._thread.join(3)

    def for_request(self, req):
        return [(n, b) for n, b in self.seen.items() if (b.get("params") or {}).get("name") == req]


class P52Case(KernelCase):
    def gated(self, name, code=0):
        """一件會卡住的工作：開始時寫 started-<name>（pid），等 release-<name> 才退 code。"""
        started, release = self.root / ("started-" + name), self.root / ("release-" + name)
        target = self.write(self.root / (name + ".json"),
                            {"argv": [PY, "-c", GATED, str(started), str(release), str(code)]})
        return target, started, release

    def counted(self, name, code=0):
        runs = self.root / ("runs-%s.txt" % name)
        return self.write(self.root / (name + ".json"), {"argv": [PY, "-c", COUNT, str(runs), str(code)]})

    def runs(self, name):
        path = self.root / ("runs-%s.txt" % name)
        return len(path.read_text().splitlines()) if path.exists() else 0

    def spy(self):
        spy = RespSpy(self.home)
        self.addCleanup(spy.close)
        return spy

    def events(self, kind=None):
        path = self.home / "kernel.log"
        if not path.exists():
            return []
        text = path.read_text()
        rows = [json.loads(line) for line in text[:text.rfind("\n") + 1].splitlines()]
        return [e for r in rows for e in r["events"] if kind is None or e["event"] == kind]

    def settle(self, ticks=4):
        target = self.state()["last_seq"] + ticks
        wait_for(lambda: self.state().get("last_seq", 0) >= target, timeout=10)

    def busy_on(self, proc):
        return self.state().get("on", {}).get(proc)


class Grow(P52Case):
    def test_zero_pool_then_add_daemon_fills_and_notify_brings_echo(self):
        """init 池 0 顆 → 排隊不算錯 → 改 count（cpu add 的效果）→ daemon 補齊 → 派工、cpu 丟 resp- 通知、kernel 收。"""
        self.setup_running({"default": {"count": 0}})
        self.assertIsNone(self.summary("default"))                   # count 0 的宣告不建池（protocol §1 第 5 步）
        self.assertEqual(self.state()["pools"]["default"]["sent"], {"count": 0, "skip": []})
        name = aos_client.submit(self.home, "add", {"name": "first", "target": self.counted("first"), "once": True})
        self.settle()
        self.assertEqual(self.state()["procs"]["first"]["status"], "queued")
        spy = self.spy()
        self.set_count("default", 2)
        self.wait_running("default", 2)
        response = aos_client.wait_response(self.home, name, timeout_ms=6000, poll_ms=5)
        self.assertEqual(response["result"]["code"], 0, response)
        aos_client.ack(self.home, name)
        entry = self.state()["pools"]["default"]
        self.assertEqual(entry["sent"], {"count": 2, "skip": []})
        for i in (0, 1):
            info = read_json(self.cpu_home("default", i) / "info.json")
            self.assertEqual(info["notify"], str(self.home / "requests"))
            self.assertEqual(info["poll_ms"], 5)
        # 通知：檔名＝SHA-256(home\nname) 前 16；內容是 responded notification
        dispatched = [e for e in self.events("dispatch") if e["proc"] == "first"]
        self.assertEqual(len(dispatched), 1)
        key, req = dispatched[0]["cpu"], dispatched[0]["request"]
        home = str(self.cpu_home(*key.split("/")))
        wait_for(lambda: spy.for_request(req))
        (fname, body), = spy.for_request(req)
        self.assertEqual(fname, "resp-%s.json" % hashlib.sha256(("%s\n%s" % (home, req)).encode()).hexdigest()[:16])
        self.assertEqual(body, {"jsonrpc": "2.0", "method": "responded", "params": {"home": home, "name": req}})
        self.assertFalse(self.events("bad_notify"))
        wait_for(lambda: not list((self.home / "requests").glob("resp-*.json")))   # kernel 收完就刪
        self.assertEqual(self.runs("first"), 1)
        self.kernel_stop()

    def test_notify_through_symlinked_kernel_home(self):
        """K 經過 symlink 給的：cpu 丟的 home 是實際路徑，kernel 照樣認得（D-80），不記 bad_notify。"""
        real = self.root / "real"
        real.mkdir()
        (self.root / "link").symlink_to(real, target_is_directory=True)
        self.home = self.root / "link" / "K"
        self.setup_running({"default": {"count": 1}})
        spy = self.spy()
        for n in range(3):
            response = self.call("add", {"name": "o%d" % n, "target": self.counted("o"), "once": True})
            self.assertEqual(response["result"]["code"], 0, response)
        wait_for(lambda: len(spy.seen) >= 3)
        self.settle()
        self.assertEqual(self.events("bad_notify"), [])
        self.kernel_stop()


class Shrink(P52Case):
    def test_shrink_waits_for_busy_cpu_to_finish(self):
        """縮池時忙的那顆：先不收、做完（回音 code 0，不是被停）才送縮小單、daemon 才收（kernel-pools §3）。"""
        self.setup_running({"default": {"count": 2}})
        self.wait_running("default", 2)
        a, a_started, a_release = self.gated("a")
        b, b_started, b_release = self.gated("b")
        ra = aos_client.submit(self.home, "add", {"name": "a", "target": a, "once": True})
        wait_for(a_started.exists)
        rb = aos_client.submit(self.home, "add", {"name": "b", "target": b, "once": True})
        wait_for(b_started.exists)
        on_one = "a" if self.busy_on("a") == "default/1" else "b"
        self.assertEqual({self.busy_on("a"), self.busy_on("b")}, {"default/0", "default/1"})
        pid_one = self.kid_pid("default", 1)
        self.set_count("default", 1)
        self.settle(6)
        entry = self.state()["pools"]["default"]
        self.assertEqual((entry["want"], entry["sent"], entry["draining"]),
                         ({"count": 1, "skip": []}, {"count": 2, "skip": []}, 1))
        self.assertEqual(self.summary("default")["count"], 2)       # daemon 那邊還沒收
        self.assertEqual(self.kid_pid("default", 1), pid_one)
        # 放掉 1 號那件：做完、收回音，才送縮小單
        (self.root / ("release-" + on_one)).touch()
        first = aos_client.wait_response(self.home, ra if on_one == "a" else rb, timeout_ms=6000, poll_ms=5)
        self.assertEqual(first["result"], {**first["result"], "code": 0, "stopped": False})
        self.wait_running("default", 1)
        wait_for(lambda: self.kid("default", 1) is None)
        with self.assertRaises(ProcessLookupError):
            os.kill(pid_one, 0)
        wait_for(lambda: self.state()["pools"]["default"]["sent"] == {"count": 1, "skip": []})
        other = "b" if on_one == "a" else "a"
        (self.root / ("release-" + other)).touch()
        second = aos_client.wait_response(self.home, rb if on_one == "a" else ra, timeout_ms=6000, poll_ms=5)
        self.assertEqual(second["result"]["code"], 0)
        aos_client.ack(self.home, ra)
        aos_client.ack(self.home, rb)
        self.assertEqual(self.state()["pools"]["default"]["free"], [0])
        self.kernel_stop()


class DaemonRestarts(P52Case):
    def test_kill9_cpu_daemon_backs_off_and_kernel_keeps_going(self):
        """kill -9 一顆閒的 cpu：daemon 退避重拉（gen＋1），kernel 不送單、照派工。"""
        self.setup_running({"default": {"count": 1}})
        self.wait_running("default", 1)
        before = self.kid("default", 0)
        sends = len(self.events("scale_send"))
        os.kill(before["pid"], signal.SIGKILL)
        after = wait_for(lambda: (self.kid("default", 0) or {}).get("gen", 0) > before["gen"]
                         and self.kid("default", 0).get("state") == "running" and self.kid("default", 0))
        self.assertNotEqual(after["pid"], before["pid"])
        self.assertEqual(after["exits"], before.get("exits", 0) + 1)
        self.assertEqual(after["streak"], 1)
        response = self.call("add", {"name": "after", "target": self.counted("after"), "once": True})
        self.assertEqual(response["result"]["code"], 0, response)
        self.assertEqual(len(self.events("scale_send")), sends)     # kernel 不用知道
        self.kernel_stop()

    def test_daemon_halt_then_boot_pulls_pools_back_and_chain_resumes(self):
        """daemon halt → pool.json 留著 → 再開 daemon 照宣告拉回，tick 自己接上，不用 aos-kernel boot。
        （one-boot：沒有 kernel 池；接上靠 daemon 照 D/kernels/ 的登記繼續替 K 開 tick，chain 不變。）"""
        self.setup_running({"default": {"count": 2}})
        self.wait_running("default", 2)
        chain = self.state()["chain"]
        self.good_daemon("halt")
        self.daemon_process.wait(timeout=8)
        self.assertTrue((self.daemon / "pools" / self.dpool("default") / "pool.json").exists())
        self.assertEqual(self.summary("default")["running"], 0)
        seq = self.state()["last_seq"]
        self.start_daemon()
        self.wait_running("default", 2)
        wait_for(lambda: self.state()["last_seq"] >= seq + 3)
        self.assertEqual(self.state()["chain"], chain)
        response = self.call("add", {"name": "after", "target": self.counted("after"), "once": True})
        self.assertEqual(response["result"]["code"], 0, response)
        import aos_kernel_health
        code, text = aos_kernel_health.health(self.home)
        self.assertEqual(code, "ok", text)
        self.kernel_stop()

    def good_daemon(self, command, *args):
        result = subprocess.run([PY, str(CLI / "aos-daemon"), command, "--target", str(self.daemon), *args],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result


TICK = r'''
import json, os, sys, time
sys.path.insert(0, %(lib)r)
import aos_kernel
argv = sys.argv[1:]
rec = {"pid": os.getpid(), "argv": argv[:1]}
start = time.monotonic()
code = 1
try:
    code = aos_kernel.main()
finally:
    end = time.monotonic()
    if argv[:1] == ["tick"]:   # one-boot：daemon 開的一格是 `tick --target K`，沒有 --chain/--seq；chain 事後從帳本讀
        import aos_kernel_store
        try:
            rec["chain"] = aos_kernel_store.meta(argv[argv.index("--target") + 1], "chain").get("chain")
        except Exception:
            rec["chain"] = None
    with open(%(log)r, "a") as f:
        f.write(json.dumps(dict(rec, start=start, end=end, code=code)) + "\n")
sys.exit(code)
'''
BOOT = r'''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import aos_kernel_boot
aos_kernel_boot.CLI = Path(sys.argv[3])
sys.exit(aos_kernel_boot.boot(sys.argv[2], wait_ms=8000))
'''


class Handoff(P52Case):
    def wrapped_boot(self):
        """boot 照產品程式走，只把釘進帳本的 cli 換成會記「每格起訖時間」的包裝。"""
        chain = self.state().get("chain")
        result = subprocess.run([PY, "-c", BOOT, str(CLI.parent / "lib"), str(self.home), str(self.wrapper)],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        wait_for(lambda: self.state().get("chain") != chain and self.state().get("last_seq", 0) >= 1)

    def ticks(self):
        path = self.root / "ticks.jsonl"
        text = path.read_text() if path.exists() else ""
        return [json.loads(line) for line in text[:text.rfind("\n") + 1].splitlines()]

    def test_reboot_new_chain_ticks_never_overlap(self):
        """再 boot：換新 chain、daemon 接著開 tick；任何兩格（拿到 K/.tick.lock 的，退 75 的不算）執行時間都不重疊。
        （one-boot 前是「舊 kernel 池縮 0、等 daemon 收乾淨才開新鏈」；kernel 池拿掉了，不重疊改由 K/.tick.lock 保證。）"""
        self.wrapper = self.root / "aos-kernel-timed"
        self.wrapper.write_text("#!%s\n%s" % (PY, TICK % {"lib": str(CLI.parent / "lib"),
                                                            "log": str(self.root / "ticks.jsonl")}))
        self.wrapper.chmod(0o755)
        self.initialize({"default": {"count": 1}})
        self.start_daemon()
        self.wrapped_boot()
        old = self.state()["chain"]
        wait_for(lambda: self.state()["last_seq"] >= 5)
        self.wrapped_boot()
        new = self.state()["chain"]
        self.assertNotEqual(new, old)
        wait_for(lambda: self.state()["last_seq"] >= 5)
        response = self.call("add", {"name": "after", "target": self.counted("after"), "once": True})
        self.assertEqual(response["result"]["code"], 0, response)
        self.kernel_stop()
        spans = sorted((t["start"], t["end"], t["chain"], t["pid"]) for t in self.ticks()
                       if t["argv"] == ["tick"] and t["code"] != 75)
        self.assertTrue({s[2] for s in spans} >= {old, new})
        for (s1, e1, c1, p1), (s2, e2, c2, p2) in zip(spans, spans[1:]):
            self.assertLessEqual(e1, s2, "兩格同時在跑：%s pid %d 與 %s pid %d" % (c1, p1, c2, p2))

    def test_kernel_halt_shrinks_every_pool_and_daemon_forgets_them(self):
        """kernel halt：每個工作池縮 0、停好那格請 daemon 撤登記；daemon 那邊池全消失、不再開 tick，重開 daemon 也不會拉回來。"""
        self.setup_running({"default": {"count": 2}, "llm": {"count": 1}})
        self.wait_running("default", 2)
        self.wait_running("llm", 1)
        self.assertIsNotNone(aos_daemon_ticks.peek(str(self.daemon), self.home))
        self.kernel_stop()
        for pool in ("default", "llm"):
            self.assertIsNone(self.summary(pool))
            self.assertFalse((self.daemon / "pools" / self.dpool(pool)).exists())
        wait_for(lambda: aos_daemon_ticks.peek(str(self.daemon), self.home) is None)  # one-boot：取代「kernel 池縮 0」
        self.assertTrue(aos_daemon.is_alive(str(self.daemon)))
        self.daemon_stop()
        self.start_daemon()
        time.sleep(.1)
        self.assertEqual(list((self.daemon / "pools").iterdir()), [])
        self.assertEqual(self.state()["phase"], "stopped")


ONCE_THEN_DONE = ("import os, sys, time\n"
                  "from pathlib import Path\n"
                  "runs = Path(sys.argv[1])\n"
                  "with runs.open('a') as f: f.write('x\\n')\n"
                  "if len(runs.read_text().splitlines()) == 1:\n"
                  "    Path(sys.argv[2]).write_text(str(os.getpid()))\n"
                  "    while True: time.sleep(.01)\n"
                  "sys.exit(100)\n")


class CpuDiesMidWork(P52Case):
    """崩潰窗口：工作 cpu 已寫 current、正在跑那件時被 SIGKILL（handoff §2、cpu-notify §3）。"""

    def kill_busy_cpu(self, started, key):
        pool, i = key.split("/")
        cpu = self.cpu_home(pool, i)
        wait_for(lambda: started.exists() and started.read_text())
        worker = int(started.read_text())
        req = self.state()["busy"][key]["req"]
        self.assertEqual(read_json(cpu / "state.json")["current"]["name"], req)   # current 已寫
        before = self.kid(pool, int(i))
        os.kill(before["pid"], signal.SIGKILL)
        os.killpg(worker, signal.SIGKILL)                  # 工作在自己那組，cpu 死了它還活著；測試自己收掉
        wait_for(lambda: (self.kid(pool, int(i)) or {}).get("gen", 0) > before["gen"]
                 and self.kid(pool, int(i))["state"] == "running")
        self.assertEqual(self.kid(pool, int(i))["streak"], 1)
        return req

    def test_repeat_work_interrupted_goes_back_to_queue_and_runs_once_more(self):
        self.setup_running({"default": {"count": 1}})
        spy = self.spy()
        started = self.root / "started-rep"
        target = self.write(self.root / "rep.json",
                            {"argv": [PY, "-c", ONCE_THEN_DONE, str(self.root / "runs-rep.txt"), str(started)]})
        self.add(target, "rep", interval_ms=5)
        wait_for(lambda: self.busy_on("rep"))
        req = self.kill_busy_cpu(started, self.busy_on("rep"))
        wait_for(lambda: self.state()["procs"]["rep"]["status"] == "done")
        proc = self.state()["procs"]["rep"]
        self.assertEqual((proc["runs"], proc["fails"]), (1, 0))
        self.assertEqual(self.runs("rep"), 2)
        self.assertEqual(len([e for e in self.events("dispatch") if e["proc"] == "rep"]), 2)   # 不重派兩次
        responses = [e["response"] for e in self.events("response") if e["proc"] == "rep"]
        self.assertEqual(responses[0]["error"]["data"]["code"], "Interrupted")
        self.assertTrue(spy.for_request(req))              # 新主人開機補丟的通知
        self.settle()
        self.assertEqual(self.state()["busy"], {})
        self.assertEqual(self.state()["pools"]["default"]["free"], [0])
        self.assertFalse(list((self.cpu_home("default", 0) / "responses").iterdir()))
        self.kernel_stop()

    def test_once_work_interrupted_is_replied_not_rerun(self):
        self.setup_running({"default": {"count": 1}})
        started = self.root / "started-one"
        target = self.write(self.root / "one.json",
                            {"argv": [PY, "-c", ONCE_THEN_DONE, str(self.root / "runs-one.txt"), str(started)]})
        name = aos_client.submit(self.home, "add", {"name": "one", "target": target, "once": True})
        wait_for(lambda: self.busy_on("one"))
        self.kill_busy_cpu(started, self.busy_on("one"))
        response = aos_client.wait_response(self.home, name, timeout_ms=6000, poll_ms=5)
        self.assertEqual(response["error"]["data"]["code"], "Interrupted", response)
        aos_client.ack(self.home, name)
        self.settle()
        self.assertNotIn("one", self.state()["procs"])
        self.assertEqual(self.runs("one"), 1)
        self.assertEqual(self.state()["busy"], {})
        again = self.call("add", {"name": "two", "target": self.counted("two"), "once": True})
        self.assertEqual(again["result"]["code"], 0, again)
        self.kernel_stop()
