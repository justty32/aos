"""llm-cpu 測試共用：真開 CLI、假 HTTP server、/tmp 家。"""
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
CLI = ROOT / "llm-cpu"
EXEC = ROOT.parent / "proto4-3" / "aos-exec"
PY = sys.executable


class CpuCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="llm-cpu-test-")
        self.home = Path(self.temp.name) / "home"
        result = self.cli("init", self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.server = subprocess.Popen(
            [PY, str(HERE / "_fake_openai.py")], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        self.port = int(self.server.stdout.readline().strip())
        self.server.stdout.close()
        self.set_local()

    def tearDown(self):
        for path in (self.home / "requests" / "running").glob("*.json"):
            try:
                pid = json.loads(path.read_text())["_aos"]["pid"]
                os.kill(pid, signal.SIGKILL)
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

    def cli(self, *args, input_data=None, cwd=None):
        return subprocess.run([PY, str(CLI), *map(str, args)], input=input_data,
                              text=True, capture_output=True, cwd=cwd)

    def set_local(self, max_concurrent=4, timeout_ms=2000, extra=None):
        endpoint = {
            "name": "local", "kind": "openai",
            "base_url": "http://127.0.0.1:%d/v1" % self.port,
            "model": "fake-model", "max_concurrent": max_concurrent,
            "timeout_ms": timeout_ms,
        }
        endpoint.update(extra or {})
        self.write_json("endpoints.json", {"default": "local", "endpoints": [endpoint]})

    def write_json(self, relative, value):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def request(self, request_id, content="echo:ok", **extra):
        req = {"messages": [{"role": "user", "content": content}], **extra}
        return self.write_json("requests/%s.json" % request_id, req)

    def tick(self):
        result = self.cli("tick", self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def result(self, request_id, timeout=4):
        path = self.home / "results" / (request_id + ".json")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if path.exists():
                return json.loads(path.read_text())
            time.sleep(0.02)
        self.fail("等不到結果：%s" % request_id)

    def pid(self, request_id):
        path = self.home / "requests" / "running" / (request_id + ".json")
        return json.loads(path.read_text())["_aos"]["pid"]
