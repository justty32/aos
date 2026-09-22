"""tool cpu：真工具、stdin、退出與逾時、壞請求、收屍和 CLI。"""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import aos_cpu
import aos_inst
import aos_tool_cpu
from aos_agent_info import AgentError

CLI = str(Path(__file__).resolve().parents[2] / "cli" / "aos-tool-cpu")


class TestToolCPU(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        (self.dir / "info.json").write_text(json.dumps({"_metainfo": {"_type": "tool_cpu", "_version": 1}}))
        self.result = self.dir / "result.json"

    def request(self, script="cat", **kw):
        req = {"inst": aos_inst.load_obj({"argv": ["/bin/sh", "-c", script]}, str(self.dir)),
               "stdin": '{"literal":"$env"}', "timeout_ms": 1000, "result": str(self.result)}
        req.update(kw)
        aos_cpu.submit(self.dir, "a.json", req)
        return req

    def read_result(self):
        return json.loads(self.result.read_text())

    def cli(self, *args, cwd=None):
        return subprocess.run([sys.executable, CLI, *map(str, args)], capture_output=True,
                              text=True, cwd=cwd, timeout=10)

    def test_load_and_empty(self):
        self.assertEqual(aos_tool_cpu.load(self.dir)["metainfo"]["_type"], "tool_cpu")
        self.assertEqual(aos_tool_cpu.tick(self.dir), 101)

    def test_wrong_cpu_rejected(self):
        (self.dir / "info.json").write_text('{"_metainfo":{"_type":"llm_cpu","_version":1}}')
        with self.assertRaisesRegex(AgentError, "NotAnAgent"):
            aos_tool_cpu.tick(self.dir)

    def test_stdin_stdout_and_no_result_name(self):
        self.request()
        self.assertEqual(aos_tool_cpu.tick(self.dir), 0)
        self.assertEqual(self.read_result(), {"ok": True, "code": 0, "kind": "child", "timed_out": False,
                                              "stdout": '{"literal":"$env"}'})
        self.assertTrue((self.dir / "done" / "a.json").exists())

    def test_nonzero_exit_is_completed_execution(self):
        self.request("printf failed; exit 7")
        self.assertEqual(aos_tool_cpu.tick(self.dir), 0)
        self.assertEqual(self.read_result(), {"ok": True, "code": 7, "kind": "child",
                                              "timed_out": False, "stdout": "failed"})

    def test_exit_143_is_not_timeout(self):
        self.request("exit 143")
        aos_tool_cpu.tick(self.dir)
        self.assertFalse(self.read_result()["timed_out"])
        self.assertEqual(self.read_result()["code"], 143)

    def test_real_timeout_preserves_output(self):
        self.request("printf before; sleep 5", timeout_ms=80)
        self.assertEqual(aos_tool_cpu.tick(self.dir), 0)
        result = self.read_result()
        self.assertTrue(result["ok"])
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["stdout"], "before")

    def test_exec_preflight_failure_has_aos_kind(self):
        req = self.request()
        req["inst"]["cwd"] = str(self.dir / "missing")
        (self.dir / "requests" / "a.json").write_text(json.dumps(req))
        with contextlib.redirect_stderr(io.StringIO()):
            aos_tool_cpu.tick(self.dir)
        self.assertEqual(self.read_result()["kind"], "aos")
        self.assertTrue(self.read_result()["ok"])
        self.assertEqual(self.read_result()["code"], 1)

    def test_bad_payload_is_error_result_not_stuck_queue(self):
        for kw in ({"inst": {}}, {"stdin": {}}, {"timeout_ms": True}, {"timeout_ms": 0},
                   {"inst": {"$ref": "not-read.json"}}):
            with self.subTest(kw=kw):
                req = self.request(**kw)
                aos_tool_cpu.tick(self.dir)
                self.assertFalse(self.read_result()["ok"])
                self.assertEqual(self.read_result()["code"], "BadPayload")
                self.assertIsInstance(self.read_result()["msg"], str)
                (self.dir / "done" / "a.json").unlink()

    def test_inst_relative_path_rejected_without_executing(self):
        req = self.request()
        req["inst"]["cwd"] = "relative"
        (self.dir / "requests" / "a.json").write_text(json.dumps(req))
        with patch("aos_tool_cpu.aos_exec.run_inst") as run:
            aos_tool_cpu.tick(self.dir)
        run.assert_not_called()
        self.assertFalse(self.read_result()["ok"])

    def test_bad_json_is_quarantined(self):
        self.request()
        queued = self.dir / "requests" / "a.json"
        queued.write_text("{")
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(aos_tool_cpu.tick(self.dir), 1)
        self.assertEqual(len(errors.getvalue().splitlines()), 1)
        self.assertFalse(queued.exists())
        self.assertTrue((self.dir / "bad" / "a.json").exists())
        self.assertFalse(self.result.exists())

    def test_inst_stdin_stdout_not_required_or_validated(self):
        for extra in ({}, {"stdin": 5, "stdout": {"path": "relative"}}):
            with self.subTest(extra=extra):
                inst = aos_inst.load_obj({"argv": ["cat"]}, str(self.dir))
                inst.pop("stdin")
                inst.pop("stdout")
                inst.update(extra)
                self.request(inst=inst)
                self.assertEqual(aos_tool_cpu.tick(self.dir), 0)
                self.assertEqual(self.read_result()["stdout"], '{"literal":"$env"}')
                (self.dir / "done" / "a.json").unlink()

    def test_reaper_uses_tool_timeout_plus_30(self):
        self.request(timeout_ms=1000)
        running = self.dir / "running" / "a.json"
        os.rename(self.dir / "requests" / "a.json", running)
        os.utime(running, (100, 100))
        with patch("aos_cpu.time.time", return_value=131):
            self.assertEqual(aos_tool_cpu.tick(self.dir), 101)
        with patch("aos_cpu.time.time", return_value=132):
            self.assertEqual(aos_tool_cpu.tick(self.dir), 0)
        self.assertFalse(self.read_result()["ok"])

    def test_reaped_result_is_exact_unknown_failure(self):
        self.request()
        os.rename(self.dir / "requests" / "a.json", self.dir / "running" / "a.json")
        os.utime(self.dir / "running" / "a.json", (1, 1))
        self.assertEqual(aos_tool_cpu.tick(self.dir), 0)
        self.assertEqual(self.read_result(), {"ok": False, "code": "Reaped", "msg": "結果不明：工具可能已經跑了，也可能沒有"})

    def test_bad_timeout_interrupted_payload_uses_fallback_reaping(self):
        self.request(timeout_ms=False)
        running = self.dir / "running" / "a.json"
        os.rename(self.dir / "requests" / "a.json", running)
        os.utime(running, (100, 100))
        with patch("aos_cpu.time.time", return_value=190):
            self.assertEqual(aos_tool_cpu.tick(self.dir), 101)
        with patch("aos_cpu.time.time", return_value=191):
            self.assertEqual(aos_tool_cpu.tick(self.dir), 0)
        self.assertFalse(self.read_result()["ok"])

    def test_directives_frozen_but_child_inherits_cpu_environment(self):
        with patch.dict(os.environ, {"CPU_BOUNDARY_PROBE": "agent"}):
            inst = aos_inst.load_obj({"argv": ["/bin/sh", "-c", 'printf "%s/%s" "$1" "$CPU_BOUNDARY_PROBE"',
                                                "sh", {"$env": "CPU_BOUNDARY_PROBE"}]}, str(self.dir))
        self.request(inst=inst)
        with patch.dict(os.environ, {"CPU_BOUNDARY_PROBE": "cpu"}):
            aos_tool_cpu.tick(self.dir)
        self.assertEqual(self.read_result()["stdout"], "agent/cpu")

    def test_cli_success_empty_and_default_dir(self):
        self.assertEqual(self.cli(self.dir).returncode, 101)
        self.assertEqual(self.cli(cwd=self.dir).returncode, 101)
        self.request("printf hello")
        p = self.cli(self.dir)
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))
        self.assertEqual(self.read_result()["stdout"], "hello")

    def test_cli_usage(self):
        self.assertEqual(self.cli("--bad").returncode, 2)
        self.assertEqual(self.cli(self.dir / "missing").returncode, 2)

    def test_cli_info_error(self):
        (self.dir / "info.json").write_text("{}")
        p = self.cli(self.dir)
        self.assertEqual(p.returncode, 1)
        self.assertIn("aos-tool-cpu: NotAnAgent:", p.stderr)
        self.assertEqual(len(p.stderr.splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
