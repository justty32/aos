#!/usr/bin/env python3

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "proto4-7"
USER = P / "aos-user"
AGENT = P / "aos-agent"


class UserCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.A = self.base / "bob"
        self.K = self.base / "K"
        self.K.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def user(self, *args, stdin=None):
        return subprocess.run([str(USER), str(self.A), *args], input=stdin, text=True,
                              capture_output=True, check=False)

    def new(self):
        result = self.user("new", "--name", "bob", "--system", "be useful", "--K", str(self.K))
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_new_builds_complete_agent_and_tools_work_alone(self):
        result = self.new()
        self.assertIn("aos-kernel add", result.stdout)
        inst = json.loads((self.A / "inst.json").read_text())
        self.assertTrue(Path(inst["argv"][0]).is_absolute())
        self.assertEqual(inst["cwd"], str(self.A.resolve()))
        echo = subprocess.run([str(self.A / "tools/echo/run")], input='{"x":1}', text=True,
                              capture_output=True, check=True)
        self.assertEqual(echo.stdout, '{"x":1}')
        shell = subprocess.run([str(self.A / "tools/sh/run")], input='{"cmd":"pwd"}', text=True,
                               capture_output=True, check=True, cwd=self.base)
        self.assertEqual(shell.stdout.strip(), str(self.A.resolve()))

    def test_say_argument_and_stdin_use_microsecond_files(self):
        self.new()
        self.assertEqual(self.user("say", "one").returncode, 0)
        self.assertEqual(self.user("say", stdin="two").returncode, 0)
        files = sorted((self.A / "inbox/user").glob("*.json"))
        self.assertEqual(len(files), 2)
        self.assertTrue(all(len(path.stem) == 22 for path in files))
        self.assertEqual([json.loads(x.read_text())["content"] for x in files], ["one", "two"])

    def test_listen_once_and_new(self):
        self.new()
        (self.A / "outbox/0001.json").write_text('{"content":"hello"}', encoding="utf-8")
        result = self.user("listen", "--once")
        self.assertIn("--- 0001 ---\nhello", result.stdout)
        process = subprocess.Popen(
            [str(USER), str(self.A), "listen", "--new", "--once"], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        time.sleep(0.25)
        (self.A / "outbox/0002.json").write_text('{"content":"new"}', encoding="utf-8")
        stdout, _ = process.communicate(timeout=3)
        self.assertIn("--- 0002 ---\nnew", stdout)

    def test_status_and_agent_status_are_one_line(self):
        self.new()
        self.user("say", "waiting")
        result = self.user("status")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.count("\n"), 1)
        self.assertIn("unread=1", result.stdout)
        result = subprocess.run([str(AGENT), str(self.A), "--status"], text=True,
                                capture_output=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.count("\n"), 1)

    def test_talk_sends_until_eof(self):
        self.new()
        result = self.user("talk", stdin="hello from talk\n")
        self.assertEqual(result.returncode, 0)
        files = list((self.A / "inbox/user").glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text())["content"], "hello from talk")

    def test_reset_only_removes_state(self):
        self.new()
        (self.A / "state.json").write_text("{}", encoding="utf-8")
        (self.A / "messages.json").write_text('[{"role":"user"}]', encoding="utf-8")
        (self.A / "outbox/0001.json").write_text("{}", encoding="utf-8")
        result = subprocess.run([str(AGENT), str(self.A), "--reset"], capture_output=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.A / "state.json").exists())
        self.assertTrue((self.A / "messages.json").exists())
        self.assertTrue((self.A / "outbox/0001.json").exists())


if __name__ == "__main__":
    unittest.main()
