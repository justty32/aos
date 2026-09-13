import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
KERNEL_ROOT = ROOT.parent / "proto4-3"
PY = sys.executable
MODULE = ROOT / "llm_cpu_module.py"


class LlmModuleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="llm-module-test-")
        self.base = Path(self.temp.name)
        self.k = self.base / "k"
        self.env = dict(os.environ, AOS_DAEMON_HOME=str(self.base / "dead-daemon"))
        result = self.command(KERNEL_ROOT / "aos-kernel-init", self.k, "--ncpu", 1,
                              "--interval-ms", 100, "--module", MODULE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.server = subprocess.Popen(
            [PY, str(HERE / "_fake_openai.py")], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        self.port = int(self.server.stdout.readline().strip())
        self.server.stdout.close()

    def tearDown(self):
        for path in (self.k / "llm" / "requests" / "running").glob("*.json"):
            try:
                os.kill(json.loads(path.read_text())["_aos"]["pid"], signal.SIGKILL)
            except (OSError, KeyError, TypeError, json.JSONDecodeError):
                pass
        try:
            os.killpg(self.server.pid, signal.SIGTERM)
            self.server.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(self.server.pid, signal.SIGKILL)
            except OSError:
                pass
        self.temp.cleanup()

    def command(self, program, *args, cwd=None, timeout=15):
        return subprocess.run([PY, str(program), *map(str, args)], env=self.env,
                              cwd=cwd, capture_output=True, text=True, timeout=timeout)

    def tick(self):
        result = self.command(KERNEL_ROOT / "aos-kernel-tick", cwd=self.k)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def prepare(self):
        self.tick()
        endpoint = {
            "name": "local", "kind": "openai",
            "base_url": "http://127.0.0.1:%d/v1" % self.port,
            "model": "fake-model", "max_concurrent": 1, "timeout_ms": 2000,
        }
        (self.k / "llm" / "endpoints.json").write_text(json.dumps({
            "default": "local", "endpoints": [endpoint]}), encoding="utf-8")

    def request_file(self, name="request.json", **extra):
        request = {"messages": [{"role": "user", "content": "echo:hello"}], **extra}
        path = self.base / name
        path.write_text(json.dumps(request), encoding="utf-8")
        return path

    def cli_while_ticking(self, *args, tick_until_exit=False):
        proc = subprocess.Popen([PY, str(KERNEL_ROOT / "aos-kernel"), "llm", self.k,
                                 *map(str, args)], env=self.env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.time() + 8
        while (proc.poll() is None and time.time() < deadline
               and not list((self.k / "syscalls").glob("*.json"))):
            time.sleep(0.01)
        while proc.poll() is None and time.time() < deadline:
            self.tick()
            if not tick_until_exit:
                break
            time.sleep(0.1)
        out, err = proc.communicate(timeout=8)
        return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)

    def test_first_tick_creates_module_home_without_inst(self):
        self.tick()
        self.assertTrue((self.k / "llm" / "endpoints.json").is_file())
        self.assertFalse((self.k / "llm" / "inst.json").exists())
        self.assertIn("llm module：建了", (self.k / "kernel.log").read_text())

    def test_cli_syscall_gets_positive_reply(self):
        self.prepare()
        result = self.cli_while_ticking(self.request_file(), "--name", "t1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("id=t1", result.stdout)

    def test_two_ticks_produce_successful_result(self):
        self.prepare()
        result = self.cli_while_ticking(self.request_file(), "--name", "t1")
        self.assertEqual(result.returncode, 0, result.stderr)
        deadline = time.time() + 3
        while not (self.k / "llm/results/t1.json").exists() and time.time() < deadline:
            time.sleep(0.02)
        self.tick()
        data = json.loads((self.k / "llm/results/t1.json").read_text())
        self.assertIs(data["ok"], True)
        self.assertEqual(data["text"], "hello")

    def test_ls_has_llm_status(self):
        self.prepare()
        result = self.command(KERNEL_ROOT / "aos-kernel", "ls", self.k)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("llm: queued 0  running 0", result.stdout)
        self.assertIn("local 0/1", result.stdout)

    def test_bad_request_gets_negative_reply(self):
        self.prepare()
        result = self.cli_while_ticking(self.request_file(model="forbidden"),
                                        "--name", "bad")
        self.assertEqual(result.returncode, 1)
        self.assertIn("不准指定 model", result.stdout)
        self.assertFalse((self.k / "llm/requests/bad.json").exists())

    def test_wait_ticks_in_background_and_prints_result(self):
        self.prepare()
        stop = threading.Event()
        errors = []

        def ticking():
            while not stop.wait(0.3):
                try:
                    self.tick()
                except BaseException as exc:
                    errors.append(exc)
                    return

        thread = threading.Thread(target=ticking)
        thread.start()
        try:
            result = self.command(KERNEL_ROOT / "aos-kernel", "llm", self.k,
                                  self.request_file(), "--name", "waited", "--wait", 5,
                                  timeout=10)
        finally:
            stop.set()
            thread.join()
        self.assertFalse(errors, errors)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"ok": true', result.stdout)
        self.assertIn('"text": "hello"', result.stdout)


if __name__ == "__main__":
    unittest.main()
