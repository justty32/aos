"""共用 CPU：不依賴 LLM 的交件、鎖、收屍與遲到發布。"""
import json
import contextlib
import io
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

    def test_bad_files_in_both_queues_do_not_block_good_request(self):
        self.submit("z.json")
        for part in ("requests", "running"):
            (self.dir / part / (part + ".json")).write_text("{\nbroken")
        errors = io.StringIO()
        execute = Mock(return_value={"ok": True})
        with contextlib.redirect_stderr(errors):
            self.assertEqual(aos_cpu.tick(self.dir, execute), 1)
        execute.assert_called_once_with(self.req)
        self.assertEqual(len(errors.getvalue().splitlines()), 2)
        self.assertEqual(sorted(p.name for p in (self.dir / "bad").iterdir()),
                         ["requests.json", "running.json"])
        self.assertTrue((self.dir / "done" / "z.json").exists())
        self.assertEqual(aos_cpu.tick(self.dir, Mock()), 101)

    def test_missing_result_parent_rejected_at_submit(self):
        self.req["result"] = str(self.dir / "missing" / "result.json")
        with self.assertRaisesRegex(AgentError, "ReadFailed"):
            self.submit()
        self.assertFalse((self.dir / "requests").exists())

    def test_unencodable_result_is_quarantined_and_next_request_runs(self):
        self.submit("b.json")
        bad_request = dict(self.req, result=str(self.dir / "\ud800.json"))
        (self.dir / "requests" / "a.json").write_text(json.dumps(bad_request))
        execute = Mock(return_value={"ok": True})
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(aos_cpu.tick(self.dir, execute), 1)
        self.assertEqual(len(errors.getvalue().splitlines()), 1)
        self.assertIn("FieldTypeMismatch", errors.getvalue())
        execute.assert_called_once_with(self.req)
        self.assertTrue((self.dir / "bad" / "a.json").exists())
        self.assertTrue((self.dir / "done" / "b.json").exists())
        self.assertEqual(aos_cpu.tick(self.dir, Mock()), 101)

    def test_bad_envelope_is_quarantined(self):
        for payload in ([], {}, {"result": "relative"}, {"result": "/x\0"}):
            with self.subTest(payload=payload):
                with aos_cpu.queue_lock(self.dir):
                    queued = self.dir / "requests" / "a.json"
                    queued.write_text(json.dumps(payload))
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(aos_cpu.tick(self.dir, Mock()), 1)
                self.assertFalse(queued.exists())
                self.assertEqual(json.loads((self.dir / "bad" / "a.json").read_text()), payload)

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
        self.assertEqual(self.read_result()["code"], "Reaped")
        self.assertEqual(set(self.read_result()), {"ok", "code", "msg"})

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

    def test_result_write_failure_moves_done(self):
        self.submit()
        with patch("aos_cpu.os.replace", side_effect=OSError("no space")):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(aos_cpu.tick(self.dir, lambda req: {"ok": True}), 1)
        self.assertEqual(len(errors.getvalue().splitlines()), 1)
        self.assertFalse((self.dir / "running" / "a.json").exists())
        self.assertTrue((self.dir / "done" / "a.json").exists())
        self.assertFalse(list(self.dir.glob("*.tmp")))

    def test_missing_result_parent_during_reap_still_moves_done_and_claims(self):
        parent = self.dir / "removed"
        parent.mkdir()
        self.req["result"] = str(parent / "result.json")
        self.submit()
        os.rename(self.dir / "requests" / "a.json", self.dir / "running" / "a.json")
        os.utime(self.dir / "running" / "a.json", (1, 1))
        parent.rmdir()
        self.req["result"] = str(self.result)
        self.submit("b.json")
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(aos_cpu.tick(self.dir, lambda req: {"ok": True}), 1)
        self.assertEqual(len(errors.getvalue().splitlines()), 1)
        self.assertEqual(sorted(p.name for p in (self.dir / "done").iterdir()), ["a.json", "b.json"])
        self.assertEqual(list((self.dir / "running").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
