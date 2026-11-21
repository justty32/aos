# 驗 on_clock 只靠 kernel 查 proc 鐘、記路徑、鐘讀不到才重查一次，且不直接讀 daemon 表。
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(LIB), str(LIB / "tools/agent/subagent/tests")]
from aos.agentlib import hook_clock, hooks
from kernel_fixture import KernelFixture


class ClockKernel(unittest.TestCase):
    def test_kernel_only_clock_is_cached_and_refreshed(self):
        fixture = KernelFixture()
        self.addCleanup(fixture.close)
        self.assertNotIn("AOS_DAEMON", fixture.env)
        clock = fixture.mom / "clock"
        clock.write_text("10\n")
        definition, stack = fixture.definition, fixture.mom
        KernelFixture.save(definition / "interfaces.json", {"aos-agent": {}, "hookeds": "hookeds.json"})
        KernelFixture.save(definition / "hookeds.json", {"tick": {
            "event": "on_clock", "handler": "unused", "clock": "mom", "every_cycles": 5}})
        warnings = []
        tick = lambda: hook_clock.clock_tick(str(definition), str(stack), warn=warnings.append)
        state = stack / "hookeds/tick/on_clock.json"
        with patch.dict(os.environ, fixture.env, clear=True), patch.object(hooks, "fire") as fire:
            with patch.object(hook_clock.subprocess, "run", wraps=subprocess.run) as query:
                self.assertEqual(tick(), ["tick"])
                query.assert_called_once_with(["aos-agent", "ctl", "ls", "--json"], stdin=subprocess.DEVNULL,
                                              capture_output=True, text=True, timeout=5)
                self.assertEqual(json.loads(state.read_text())["clock"], str(clock))
                clock.write_text("14\n")
                self.assertEqual(tick(), [])
                clock.write_text("15\n")
                self.assertEqual(tick(), ["tick"])
                self.assertEqual(query.call_count, 1)
            # 記住的路徑不在：表上仍同一 proc，但它的 stack 換了，重查後記新鐘。
            new_stack = fixture.root / "moved-mom"
            new_stack.mkdir()
            (new_stack / "clock").write_text("20\n")
            clock.rename(clock.with_name("clock.old"))
            rows = [{"name": "mom", "stack": str(new_stack)}]
            with patch.object(hook_clock.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(rows), "")) as query:
                self.assertEqual(tick(), ["tick"])
                self.assertEqual(query.call_count, 1)
            self.assertEqual(json.loads(state.read_text())["clock"], str(new_stack / "clock"))
            self.assertTrue(fire.call_args.args[1]["first"])
            # 壞掉的快取鐘也只重查一次；查回的鐘仍壞，不起 handler。
            (new_stack / "clock").write_text("not a cycle")
            with patch.object(hook_clock.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(rows), "")) as query:
                self.assertEqual(tick(), [])
                self.assertEqual(query.call_count, 1)
            self.assertEqual(fire.call_count, 3)
            # 改成另一個名字、但指同一鐘檔且尚未到期，也要記下新的名字，下一拍不再問表。
            (new_stack / "clock").write_text("21\n")
            KernelFixture.save(definition / "hookeds.json", {"tick": {
                "event": "on_clock", "handler": "unused", "clock": "renamed", "every_cycles": 5}})
            rows[0]["name"] = "renamed"
            with patch.object(hook_clock.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(rows), "")) as query:
                self.assertEqual(tick(), [])
                self.assertEqual(tick(), [])
                self.assertEqual(query.call_count, 1)
            self.assertEqual(json.loads(state.read_text())["clock_source"], "renamed")
        self.assertIn("does not hold a cycle number", warnings[-1])

    def test_failed_query_warns_without_falling_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            definition, stack = root / "def", root / "stack"
            definition.mkdir()
            stack.mkdir()
            KernelFixture.save(definition / "interfaces.json", {"aos-agent": {}, "hookeds": "hookeds.json"})
            KernelFixture.save(definition / "hookeds.json", {"tick": {
                "event": "on_clock", "handler": "unused", "clock": "mom", "every_cycles": 1}})
            warnings = []
            with patch.dict(os.environ, {"AOS_KERNEL": str(root / "requests")}, clear=True), patch.object(hooks, "fire") as fire:
                result = subprocess.CompletedProcess([], 1, "", "aos-agent: error: KernelFailed no reply")
                with patch.object(hook_clock.subprocess, "run", return_value=result) as query:
                    for _ in range(2):
                        self.assertEqual(hook_clock.clock_tick(str(definition), str(stack), warn=warnings.append), [])
                    self.assertEqual(query.call_count, 2)
                fire.assert_not_called()
            self.assertEqual(len(warnings), 1)
            self.assertIn("KernelFailed", warnings[0])


if __name__ == "__main__":
    unittest.main()
