import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
KERNEL = ROOT.parent / "proto4-3"
MODULE = ROOT / "llm_cpu_module.py"
PY = sys.executable


class ModuleManageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="llm-module-manage-")
        self.base = Path(self.temp.name)
        self.k = self.base / "K"
        self.env = dict(os.environ, AOS_DAEMON_HOME=str(self.base / "dead-daemon"))
        self.init = self.command(KERNEL / "aos-kernel-init", self.k, "--ncpu", 1,
                                 "--module", MODULE)
        self.assertEqual(self.init.returncode, 0, self.init.stderr)
        self.tick()

    def tearDown(self):
        for path in (self.k / "llm/requests/running").glob("*.json"):
            try:
                os.killpg(json.loads(path.read_text())["_aos"]["pid"], signal.SIGKILL)
            except (OSError, KeyError, TypeError, json.JSONDecodeError):
                pass
        self.temp.cleanup()

    def command(self, program, *args, cwd=None, timeout=10):
        return subprocess.run([PY, str(program), *map(str, args)], env=self.env, cwd=cwd,
                              capture_output=True, text=True, timeout=timeout)

    def kernel(self, *args):
        return self.command(KERNEL / "aos-kernel", "llm", *args)

    def tick(self):
        result = self.command(KERNEL / "aos-kernel-tick", cwd=self.k)
        self.assertEqual(result.returncode, 0, result.stderr)

    def write(self, relative, value):
        path = self.k / "llm" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_init_prints_hint_and_generated_endpoints_are_indented(self):
        self.assertIn("第一回合會生", self.init.stdout)
        self.assertIn("local 的 model 換成 aos-llm models", self.init.stdout)
        raw = (self.k / "llm/endpoints.json").read_text()
        self.assertIn('\n  "default": "local"', raw)

    def test_kernel_status_warns_about_placeholder_model(self):
        result = self.command(KERNEL / "aos-kernel", "ls", self.k)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("llm:", result.stdout)
        self.assertIn("⚠ local 的 model 還沒換", result.stdout)

    def test_ls_prints_queued_running_and_done_details(self):
        submitted = "2026-09-13T01:02:03.000+00:00"
        self.write("requests/q.json", {"endpoint": "local", "_aos": {"submitted": submitted}})
        self.write("requests/running/r.json", {"_aos": {"endpoint": "local", "submitted": submitted}})
        self.write("requests/running/just-finished.json",
                   {"_aos": {"endpoint": "local", "submitted": submitted}})
        self.write("results/just-finished.json", {"ok": True})
        self.write("requests/done/ok.json", {"_aos": {"endpoint": "local", "submitted": submitted}})
        self.write("results/ok.json", {"ok": True})
        self.write("requests/done/bad.json", {"_aos": {"endpoint": "local", "submitted": submitted}})
        self.write("results/bad.json", {"ok": False, "error": {"kind": "timeout"}})
        result = self.kernel("ls", self.k)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("queued:\n  q  endpoint=local  submitted=" + submitted, result.stdout)
        self.assertIn("running:\n  r  endpoint=local  submitted=" + submitted, result.stdout)
        self.assertNotIn("running:\n  just-finished", result.stdout)
        self.assertIn("just-finished  endpoint=local", result.stdout)
        self.assertIn("result=%s  ok=true" % (self.k / "llm/results/ok.json"), result.stdout)
        self.assertIn("error.kind=timeout", result.stdout)

    def test_rm_removes_all_files_and_missing_name_returns_one(self):
        for relative in ("requests/q.json", "requests/done/q.json", "results/q.json"):
            self.write(relative, {})
        removed = self.kernel("rm", self.k, "q")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertEqual(removed.stdout.strip(), "刪掉了：q")
        self.assertFalse(any((self.k / "llm" / p).exists() for p in
                             ("requests/q.json", "requests/done/q.json", "results/q.json")))
        missing = self.kernel("rm", self.k, "q")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("沒有這個名字", missing.stderr)

    def test_rm_running_kills_worker_before_removing_files(self):
        worker = subprocess.Popen(["sleep", "30"], start_new_session=True)
        try:
            self.write("requests/running/live.json", {"_aos": {"pid": worker.pid,
                       "endpoint": "local", "submitted": "now"}})
            self.write("results/live.json", {})
            removed = self.kernel("rm", self.k, "live")
            self.assertEqual(removed.returncode, 0, removed.stderr)
            worker.wait(timeout=3)
            self.assertFalse((self.k / "llm/requests/running/live.json").exists())
            self.assertFalse((self.k / "llm/results/live.json").exists())
        finally:
            if worker.poll() is None:
                os.killpg(worker.pid, signal.SIGKILL)
                worker.wait(timeout=2)

    def test_rm_running_reports_worker_without_a_killable_pid(self):
        path = self.write("requests/running/stuck.json", {"_aos": {"pid": None}})
        removed = self.kernel("rm", self.k, "stuck")
        self.assertEqual(removed.returncode, 1)
        self.assertIn("沒有可砍的 worker pid", removed.stderr)
        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
