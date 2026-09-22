"""共用 CPU：不依賴 LLM 的交件、鎖、收屍與遲到發布。"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import aos_cpu
from aos_agent_info import AgentError


class TestCPU(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.result = self.dir / "result.json"
        self.req = {"result": str(self.result), "payload": {"$env": "LITERAL"}}

    def submit(self, name="a.json"):
        return aos_cpu.submit(self.dir, name, self.req)

    def read_result(self):
        return json.loads(self.result.read_text())

    def test_submit_atomic_and_preserves_literal_payload(self):
        target = self.submit()
        self.assertEqual(json.loads(Path(target).read_text()), self.req)
        self.assertEqual(list((self.dir / "requests").iterdir()), [Path(target)])

    def test_same_name_in_each_location_rejected(self):
        for part in ("requests", "running", "done"):
            with self.subTest(part=part):
                with aos_cpu.queue_lock(self.dir):
                    occupied = self.dir / part / (part + ".json")
                    occupied.write_text("original")
                with self.assertRaisesRegex(AgentError, "ReadFailed"):
                    self.submit(part + ".json")
                self.assertEqual(occupied.read_text(), "original")

    def test_bad_name_rejected(self):
        for name in ("../x.json", "/x.json", "x", "x.json\0", 1):
            with self.subTest(name=name), self.assertRaisesRegex(AgentError, "FieldTypeMismatch"):
                self.submit(name)
        self.assertFalse((self.dir / "requests").exists())

    def test_bad_envelope_rejected_before_write(self):
        for req in ([], {}, {"result": "relative"}, {"result": "/x\0"}):
            with self.subTest(req=req), self.assertRaises(AgentError):
                aos_cpu.submit(self.dir, "a.json", req)
        self.assertFalse((self.dir / "requests").exists())

    def test_submit_replace_failure_cleans_tmp(self):
        with patch("aos_cpu.os.replace", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(AgentError, "ReadFailed"):
                self.submit()
        self.assertEqual(list((self.dir / "requests").iterdir()), [])

    def test_empty_never_executes(self):
        execute = Mock()
        self.assertEqual(aos_cpu.tick(self.dir, execute), 101)
        execute.assert_not_called()

    def test_execute_receives_request_and_result_is_not_decorated(self):
        self.submit()
        execute = Mock(return_value={"ok": True, "custom": 7})
        self.assertEqual(aos_cpu.tick(self.dir, execute), 0)
        execute.assert_called_once_with(self.req)
        self.assertEqual(self.read_result(), {"ok": True, "custom": 7})
        self.assertTrue((self.dir / "done" / "a.json").exists())

    def test_optional_validator_runs_before_claim(self):
        self.submit()
        def reject(req, path):
            raise AgentError("FieldTypeMismatch", "bad payload")
        with self.assertRaises(AgentError):
            aos_cpu.tick(self.dir, Mock(), validate=reject)
        self.assertTrue((self.dir / "requests" / "a.json").exists())

    def test_exception_leaves_running_for_reaper(self):
        self.submit()
        with self.assertRaises(RuntimeError):
            aos_cpu.tick(self.dir, Mock(side_effect=RuntimeError("interrupted")))
        self.assertTrue((self.dir / "running" / "a.json").exists())
        self.assertFalse(self.result.exists())

    def test_reap_strict_timeout_plus_grace_boundary(self):
        self.submit()
        running = self.dir / "running" / "a.json"
        os.rename(self.dir / "requests" / "a.json", running)
        os.utime(running, (100, 100))
        with patch("aos_cpu.time.time", return_value=131):
            self.assertEqual(aos_cpu.tick(self.dir, Mock(), timeout_ms=lambda req: 1000), 101)
        with patch("aos_cpu.time.time", return_value=131.001):
            self.assertEqual(aos_cpu.tick(self.dir, Mock(), timeout_ms=lambda req: 1000), 0)
        self.assertFalse(self.read_result()["ok"])

    def test_reaper_preserves_newer_occupied_result(self):
        self.submit("old.json")
        os.rename(self.dir / "requests" / "old.json", self.dir / "running" / "old.json")
        os.utime(self.dir / "running" / "old.json", (1, 1))
        self.result.write_text('{"ok":true,"newer":"different request"}')
        self.assertEqual(aos_cpu.tick(self.dir, Mock()), 0)
        self.assertEqual(self.read_result(), {"ok": True, "newer": "different request"})

    def test_late_return_does_not_publish_after_reap(self):
        self.submit()
        def execute(req):
            os.utime(self.dir / "running" / "a.json", (1, 1))
            self.assertEqual(aos_cpu.tick(self.dir, Mock()), 0)
            return {"ok": True}
        self.assertEqual(aos_cpu.tick(self.dir, execute), 0)
        self.assertFalse(self.read_result()["ok"])

    def test_replaced_running_identity_does_not_publish(self):
        self.submit()
        def execute(req):
            running = self.dir / "running" / "a.json"
            os.rename(running, self.dir / "original.json")
            running.write_text(json.dumps(req))
            return {"ok": True}
        self.assertEqual(aos_cpu.tick(self.dir, execute), 0)
        self.assertFalse(self.result.exists())
        self.assertTrue((self.dir / "running" / "a.json").exists())

    def test_result_write_failure_retains_running(self):
        self.submit()
        with patch("aos_cpu.os.replace", side_effect=OSError("no space")):
            with self.assertRaises(AgentError):
                aos_cpu.tick(self.dir, lambda req: {"ok": True})
        self.assertTrue((self.dir / "running" / "a.json").exists())
        self.assertFalse(list(self.dir.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
