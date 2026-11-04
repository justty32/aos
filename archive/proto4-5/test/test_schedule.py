import json
import os
import signal
import time
import unittest

from _util import CpuCase


class ScheduleTest(CpuCase):
    def test_priority_larger_goes_first(self):
        self.set_local(max_concurrent=1, timeout_ms=20000)
        self.request("p2", "slow:10", priority=2)
        self.request("p0", "slow:10", priority=0)
        self.request("p5", "slow:10", priority=5)
        self.tick()
        self.assertTrue((self.home / "requests/running/p5.json").exists())
        self.assertTrue((self.home / "requests/p2.json").exists())

    def test_same_priority_earlier_mtime_goes_first(self):
        self.set_local(max_concurrent=1, timeout_ms=20000)
        early = self.request("z-early", "slow:10", priority=1)
        late = self.request("a-late", "slow:10", priority=1)
        now = time.time_ns()
        os.utime(early, ns=(now - 2_000_000_000, now - 2_000_000_000))
        os.utime(late, ns=(now, now))
        self.tick()
        self.assertTrue((self.home / "requests/running/z-early.json").exists())

    def test_full_endpoint_leaves_second_until_later_tick(self):
        self.set_local(max_concurrent=1)
        first = self.request("first", "slow:0.2")
        second = self.request("second", "echo:second")
        now = time.time_ns()
        os.utime(first, ns=(now - 2_000_000_000, now - 2_000_000_000))
        os.utime(second, ns=(now, now))
        self.tick()
        self.assertTrue((self.home / "requests/second.json").exists())
        self.result("first")
        self.tick()
        self.assertTrue((self.home / "requests/running/second.json").exists())
        self.assertEqual(self.result("second")["text"], "second")

    def test_full_one_endpoint_does_not_block_another(self):
        doc = json.loads((self.home / "endpoints.json").read_text())
        second = dict(doc["endpoints"][0], name="other", max_concurrent=1)
        doc["endpoints"].append(second)
        doc["endpoints"][0]["max_concurrent"] = 1
        self.write_json("endpoints.json", doc)
        self.request("local1", "slow:10", endpoint="local", priority=3)
        self.request("local2", "slow:10", endpoint="local", priority=2)
        self.request("other", "slow:10", endpoint="other", priority=1)
        self.tick()
        self.assertTrue((self.home / "requests/running/local1.json").exists())
        self.assertTrue((self.home / "requests/local2.json").exists())
        self.assertTrue((self.home / "requests/running/other.json").exists())

    def test_killed_worker_becomes_worker_died(self):
        self.request("dead", "slow:10", timeout_ms=20000)
        self.tick()
        pid = self.pid("dead")
        os.kill(pid, signal.SIGKILL)
        deadline = time.time() + 2
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.02)
        self.tick()
        self.assertEqual(self.result("dead")["error"]["kind"], "worker_died")

    def test_slow_request_ends_as_timeout(self):
        self.request("slow", "slow:3", timeout_ms=500)
        self.tick()
        result = self.result("slow", timeout=3)
        self.assertEqual(result["error"]["kind"], "timeout")
        self.tick()
        self.assertTrue((self.home / "requests/done/slow.json").exists())

    def test_tick_kills_worker_past_hard_timeout(self):
        self.request("hard", "slow:10", timeout_ms=20000)
        self.tick()
        running = self.home / "requests/running/hard.json"
        req = json.loads(running.read_text())
        req["timeout_ms"] = 1
        req["_aos"]["started"] = time.time() - 6
        running.write_text(json.dumps(req))
        self.tick()
        self.assertEqual(self.result("hard")["error"]["kind"], "timeout")
        self.assertTrue((self.home / "requests/done/hard.json").exists())


if __name__ == "__main__":
    unittest.main()
