"""核心（tick、tock、任務、ctl、inst、掃描）的測試；daemon 的在 test_core_daemon.py。共用小工具 CoreCase 也在這裡。"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
LIB = os.path.join(TOP, "lib")
BIN = os.path.join(TOP, "bin")
sys.path.insert(0, LIB)

import aos7_daemon  # noqa: E402
import aos7_task  # noqa: E402
from aos7_fs import read_json, write_json  # noqa: E402

# 收到 n 次 tock 就自己結束的任務（S-11 的例子）；每收到一次記一行
WAITER = """import os, sys
sys.path.insert(0, %r)
from aos7_fs import wait_tock, append_jsonl
n, last = int(sys.argv[1]), 0
for _ in range(n):
    last = wait_tock(os.environ["AOS7_TASK"], last)
    append_jsonl(os.path.join(os.environ["AOS7_TASK"], "seen.jsonl"), {"round": last})
""" % LIB


def text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


SLEEPER = ["python3", "-c", "import time; time.sleep(60)"]


class CoreCase(unittest.TestCase):
    """建暫存空間根、node；結束時把 daemon 與所有任務程序收乾淨。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="aos7-core-")
        self.root = os.path.realpath(self._tmp.name)
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()
            if p.stderr:
                p.stderr.close()
        self.sweep(self.root)
        # daemon 被殺時它起的 tick 可能還在寫（會在刪掉後重建 a/.aos/round.json）：殺整個程序群組，再多刪幾次
        for p in self.procs:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
        for _ in range(5):
            shutil.rmtree(self.root, ignore_errors=True)
            if not os.path.exists(self.root):
                break
            time.sleep(0.1)
        self._tmp.cleanup()

    @staticmethod
    def sweep(root):
        """把 root 底下所有 pid.json 記的程序群組與 aos7-run 都 SIGKILL。"""
        for d, _, files in os.walk(root):
            if "pid.json" in files:
                pid = read_json(os.path.join(d, "pid.json"), {})
                for f, x in ((os.killpg, pid.get("pgid")), (os.kill, pid.get("runner_pid"))):
                    try:
                        f(x, signal.SIGKILL)
                    except (OSError, TypeError):
                        pass

    def mknode(self, nid, tasks=(), interval_ms=100, root=None):
        node = os.path.join(root or self.root, nid) if nid != "." else (root or self.root)
        write_json(os.path.join(node, ".aos", "timeline.json"), {"interval_ms": interval_ms})
        write_json(os.path.join(node, ".aos", "tasks.json"), {"tasks": list(tasks)})
        with open(os.path.join(node, "waiter.py"), "w") as f:
            f.write(WAITER)
        return node

    def prog(self, name, *args):
        p = subprocess.run([sys.executable, os.path.join(BIN, name), *args],
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else None

    def tick(self, nid="a"):
        return self.prog("aos7-tick", self.root, nid)

    def tock(self, nid="a"):
        return self.prog("aos7-tock", self.root, nid)

    def wait_for(self, pred, timeout=10, msg="timeout"):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            v = pred()
            if v:
                return v
            time.sleep(0.02)
        self.fail(msg)

    def tdir(self, node, tid):
        return aos7_task.task_dir(node, tid)

    def state(self, node, tid):
        return aos7_task.task_state(self.tdir(node, tid))


class TestTickTock(CoreCase):
    def test_tick_starts_and_does_not_wait(self):
        node = self.mknode("a", [{"name": "s", "argv": SLEEPER}])
        t0 = time.monotonic()
        r = self.tick()
        self.assertLess(time.monotonic() - t0, 5)      # 任務睡 60 秒，tick 早就回來
        self.assertEqual(r, {"round": 1, "started": ["s-r1"]})
        birth = read_json(os.path.join(self.tdir(node, "s-r1"), "birth.json"))
        self.assertEqual(birth["mounts"], {})
        self.wait_for(lambda: os.path.exists(os.path.join(self.tdir(node, "s-r1"), "pid.json")))
        self.assertEqual(self.state(node, "s-r1"), "live")
        self.assertTrue(read_json(os.path.join(node, ".aos", "round.json"))["open"])

    def test_task_spans_rounds_and_gets_tock(self):
        node = self.mknode("a", [{"name": "w", "mode": "keep", "argv": ["python3", "waiter.py", "2"]}])
        self.tick()
        self.wait_for(lambda: self.state(node, "w-r1") == "live")
        s1 = self.tock()
        self.assertEqual(s1["alive"], ["w-r1"])
        self.assertEqual(read_json(os.path.join(self.tdir(node, "w-r1"), "tock.json"))["round"], 1)
        self.assertEqual(self.tick()["started"], [])      # keep：活著就不再起
        self.tock()
        self.wait_for(lambda: self.state(node, "w-r1") == "ended")
        s3 = (self.tick(), self.tock())[1]
        self.assertEqual(s3["ended"], [{"tid": "w-r1", "code": 0}])
        seen = [json.loads(x)["round"] for x in text(os.path.join(self.tdir(node, "w-r1"), "seen.jsonl")).splitlines()]
        self.assertEqual(seen, [1, 2])
        self.assertEqual(read_json(os.path.join(self.tdir(node, "w-r1"), "ended.json")), {"round": 3})
        self.assertFalse(read_json(os.path.join(node, ".aos", "round.json"))["open"])

    def test_from_round_and_each(self):
        node = self.mknode("a", [{"name": "j", "argv": ["true"], "from_round": 2}])
        self.assertEqual(self.tick()["started"], [])
        self.tock()
        self.assertEqual(self.tick()["started"], ["j-r2"])
        self.wait_for(lambda: self.state(node, "j-r2") == "ended")

    def test_ctl_kill_and_restart(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEPER}])
        self.tick()
        self.wait_for(lambda: self.state(node, "s-r1") == "live")
        self.prog("aos7-ctl", "task", self.tdir(node, "s-r1"), "kill", "測試")
        s = self.tock()
        self.assertEqual(s["ctl"], [{"tid": "s-r1", "op": "kill", "ok": True}])
        done = read_json(os.path.join(self.tdir(node, "s-r1"), "ctl-done.json"))
        self.assertTrue(done["result"]["ok"])
        self.wait_for(lambda: self.state(node, "s-r1") == "ended")
        self.assertEqual(read_json(os.path.join(self.tdir(node, "s-r1"), "exit.json"))["code"], -signal.SIGTERM)
        # keep 任務被 kill，下個 tick 又會被 tasks.json 起回來（problems-core.md P-09）
        self.assertEqual(self.tick()["started"], ["s-r2"])
        self.wait_for(lambda: self.state(node, "s-r2") == "live")
        self.tock()
        # restart：tick 時刻執行，同一個 tick 就從 spawn 起新的
        self.prog("aos7-ctl", "task", self.tdir(node, "s-r2"), "restart")
        r = self.tick()
        self.assertEqual(r["started"], ["s-r3"])
        self.assertEqual(read_json(os.path.join(self.tdir(node, "s-r3"), "birth.json"))["restart_of"], "s-r2")
        self.wait_for(lambda: self.state(node, "s-r2") == "ended")
        self.assertFalse(os.listdir(os.path.join(node, ".aos", "spawn")))

    def test_ctl_not_object_gets_failed_receipt(self):
        """ctl.json 是合法 JSON 但不是物件（`[]`）：寫失敗回條、搬走，tick 照常印結果（astra 試玩二-1）。"""
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEPER}])
        self.tick()
        self.wait_for(lambda: self.state(node, "s-r1") == "live")
        write_json(os.path.join(self.tdir(node, "s-r1"), "ctl.json"), [])
        r = self.tock()
        self.assertEqual(r["ctl"], [{"tid": "s-r1", "op": None, "ok": False}])
        done = read_json(os.path.join(self.tdir(node, "s-r1"), "ctl-done.json"))
        self.assertEqual((done["raw"], done["result"]["msg"]), ([], "not a JSON object"))
        self.assertFalse(os.path.exists(os.path.join(self.tdir(node, "s-r1"), "ctl.json")))
        self.assertEqual(self.state(node, "s-r1"), "live")
        with open(os.path.join(self.tdir(node, "s-r1"), "ctl.json"), "w") as f:
            f.write("{oops")
        self.assertEqual(self.tick()["round"], 2)
        done = read_json(os.path.join(self.tdir(node, "s-r1"), "ctl-done.json"))
        self.assertEqual(done["result"]["msg"], "unreadable JSON")

    def test_lost_task(self):
        node = self.mknode("a", [{"name": "s", "argv": SLEEPER}])
        self.tick()
        self.wait_for(lambda: self.state(node, "s-r1") == "live")
        pid = read_json(os.path.join(self.tdir(node, "s-r1"), "pid.json"))
        os.kill(pid["runner_pid"], signal.SIGKILL)       # 包裝程式先死，exit.json 不會有人寫
        os.killpg(pid["pgid"], signal.SIGKILL)
        self.wait_for(lambda: self.state(node, "s-r1") == "lost")
        s = self.tock()
        self.assertEqual(s["ended"], [{"tid": "s-r1", "code": None, "lost": True}])
        self.assertTrue(read_json(os.path.join(self.tdir(node, "s-r1"), "exit.json"))["lost"])

    def test_inst_task(self):
        node = self.mknode("a", [{"name": "i", "inst": "job.inst.json"}])
        write_json(os.path.join(node, "job.inst.json"),
                   {"argv": ["sh", "-c", "echo $AOS7_TID > inst-out.txt; echo hi"],
                    "stdout": {"$opt": "inherit"}})
        self.tick()
        self.wait_for(lambda: self.state(node, "i-r1") == "ended")
        td = self.tdir(node, "i-r1")
        self.assertEqual(read_json(os.path.join(td, "exit.json"))["code"], 0)
        self.assertEqual(text(os.path.join(node, "inst-out.txt")).strip(), "i-r1")
        self.assertEqual(text(os.path.join(td, "out.log")).strip(), "hi")

    def test_inst_task_kill_reaches_grandchild(self):
        """aos-exec 把子程式開在另一個 session；kill 要連它一起收（P-05）。"""
        node = self.mknode("a", [{"name": "i", "inst": "s.inst.json"}])
        write_json(os.path.join(node, "s.inst.json"), {"argv": SLEEPER})
        self.tick()
        td = self.tdir(node, "i-r1")
        self.wait_for(lambda: len(aos7_task._groups_with_descendants(
            read_json(os.path.join(td, "pid.json"), {}).get("pgid", -1))) >= 2)
        groups = aos7_task._groups_with_descendants(read_json(os.path.join(td, "pid.json"))["pgid"])
        ok, _ = aos7_task.kill_task(td)
        self.assertTrue(ok)
        self.assertFalse(any(aos7_task.group_alive(g) for g in groups))


class TestScan(CoreCase):
    def test_nested_daemon_root_is_skipped(self):
        self.mknode(".")
        self.mknode("team")
        self.mknode("team/agents/amy")
        self.mknode("sub")
        self.mknode("sub/inner")
        os.makedirs(os.path.join(self.root, "sub", ".aosd"))
        self.mknode(".hidden")
        self.assertEqual(aos7_daemon.scan_nodes(self.root), [".", "team", "team/agents/amy"])


if __name__ == "__main__":
    unittest.main()
