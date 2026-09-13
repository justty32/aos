import json
import os
import subprocess
import sys
import tempfile
import unittest

import _util  # noqa: F401
from aos_kernel import KHome

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
INIT = os.path.join(ROOT, "aos-kernel-init")
KERNEL = os.path.join(ROOT, "aos-kernel")
TICK = os.path.join(ROOT, "aos-kernel-tick")
ECHO = os.path.join(HERE, "fx", "echo_module.py")


class ModuleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aos-module-test-")
        self.k = os.path.join(self.temp.name, "k")

    def tearDown(self):
        self.temp.cleanup()

    def command(self, program, *args, cwd=None):
        return subprocess.run([PY, program, *map(str, args)], cwd=cwd,
                              capture_output=True, text=True, timeout=15)

    def init(self, module=ECHO):
        args = [self.k, "--ncpu", "1"]
        if module is not None:
            args += ["--module", module]
        result = self.command(INIT, *args)
        self.assertEqual(result.returncode, 0, result.stderr)

    def tick(self):
        result = self.command(TICK, cwd=self.k)
        self.assertEqual(result.returncode, 0, result.stderr)

    def syscall(self, name, body):
        with open(os.path.join(self.k, "syscalls", name), "w", encoding="utf-8") as stream:
            json.dump(body, stream)

    def reply(self, name):
        with open(os.path.join(self.k, "syscalls", "done", name), encoding="utf-8") as stream:
            return json.load(stream)

    def test_init_and_config_keep_absolute_module_paths(self):
        relative = os.path.relpath(ECHO)
        self.init(relative)
        with open(os.path.join(self.k, "config.json"), encoding="utf-8") as stream:
            raw = json.load(stream)
        self.assertEqual(raw["modules"], [os.path.abspath(relative)])
        self.assertEqual(KHome(self.k).config()["modules"], [os.path.abspath(relative)])

    def test_tick_logs_module_note(self):
        self.init()
        self.tick()
        with open(os.path.join(self.k, "kernel.log"), encoding="utf-8") as stream:
            log = stream.read()
        self.assertIn("echo tick", log)

    def test_module_handles_syscall_and_writes_reply(self):
        self.init()
        self.syscall("1-echo.json", {"op": "echo", "text": "hi"})
        self.tick()
        with open(os.path.join(self.k, "echo.txt"), encoding="utf-8") as stream:
            self.assertEqual(stream.read(), "hi")
        self.assertEqual(self.reply("1-echo.json"), {"ok": True, "msg": "echoed"})

    def test_unknown_syscall_stays_unknown(self):
        self.init()
        self.syscall("1-wat.json", {"op": "wat"})
        self.tick()
        reply = self.reply("1-wat.json")
        self.assertFalse(reply["ok"])
        self.assertIn("看不懂", reply["msg"])

    def test_ls_includes_module_status(self):
        self.init()
        result = self.command(KERNEL, "ls", self.k)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("echo: ok", result.stdout)

    def test_unknown_subcommand_dispatches_to_module_cli(self):
        self.init()
        result = self.command(KERNEL, "echo", self.k, "a", "b")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("a b", result.stdout)

    def test_missing_module_only_leaves_a_note(self):
        self.init(os.path.join(self.temp.name, "missing.py"))
        self.tick()
        with open(os.path.join(self.k, "kernel.log"), encoding="utf-8") as stream:
            log = stream.read()
        self.assertIn("module missing.py 載入失敗", log)


if __name__ == "__main__":
    unittest.main()
