"""Test user_send wraps aos-user send for the calling agent: from = its name, reply-to = its mailbox, envelope sender = its stack, the body passes through; aos-user errors become user_send errors; aos-user is looked up in $AOS_USER_TOOL, $AOS_WS/tools, PATH (fake aos-agent and fake aos-user)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
TOOL = Path(__file__).resolve().parents[1]
FAKE_AGENT = r'''#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:] == ["ctl", "who", "--json"]:
    print(json.dumps({"name": os.environ["FAKE_NAME"], "stack": os.environ["FAKE_STACK"]}))
else:
    sys.stderr.write("aos-agent: error: ArgumentsBad unexpected\n"); sys.exit(1)
'''
FAKE_USER = r'''#!/usr/bin/env python3
import json, os, sys
body = json.loads(sys.stdin.read())
if body.get("what") == "bad":
    sys.stderr.write("aos-user: error: SchemaBad at most 7 questions in one letter (got 8) (see the door: aos-user door)\n"); sys.exit(1)
with open(os.environ["FAKE_LOG"], "w") as f:
    json.dump({"argv": sys.argv[1:], "body": body, "stack": os.environ.get("AOS_STACK"), "me": sys.argv[0]}, f)
print("01700000000000000000.1.1")
'''


class UserSend(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="user-send-"))
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        for name, text in (("aos-agent", FAKE_AGENT), ("aos-user", FAKE_USER)):
            (bin_ / name).write_text(text)
            (bin_ / name).chmod(0o755)
        (self.tmp / "ws").mkdir()
        (self.tmp / "alice").mkdir()
        self.log = self.tmp / "log.json"
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env = dict(env, PATH="%s:%s" % (bin_, env["PATH"]), AOS_WS=str(self.tmp / "ws"),
                        AOS_STACK=str(self.tmp / "alice" / "tools" / "user_send"), FAKE_NAME="alice",
                        FAKE_STACK=str(self.tmp / "alice"), FAKE_LOG=str(self.log), PYTHONDONTWRITEBYTECODE="1")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, args, **env):
        return subprocess.run([sys.executable, str(TOOL / "_entry")], input=json.dumps(args), capture_output=True,
                              text=True, env=dict(self.env, **env), timeout=30)

    def test_sends_as_caller(self):
        q = [{"id": "q1", "question": "Tick?", "eli5": "How often. Faster costs more.",
              "options": [{"key": "a", "label": "1s"}, {"key": "b", "label": "1m"}], "recommend": "b"}]
        r = self.run_tool({"kind": "decide", "title": "Which tick?", "questions": q, "urgent": True, "deadline": "2026-11-15"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("sent letter 01700000000000000000.1.1 to the user zone", r.stdout)
        got = json.loads(self.log.read_text())
        self.assertEqual(got["argv"], ["send", "--kind", "decide", "--title", "Which tick?", "--from", "alice",
                                       "--reply-to", str(self.tmp / "alice" / "mailbox"), "-"])
        self.assertEqual(got["body"], {"questions": q, "urgent": True, "deadline": "2026-11-15"})
        self.assertEqual(got["stack"], str(self.tmp / "alice"))       # 不是工具自己的小格

    def test_schema_error_passes_through(self):
        r = self.run_tool({"kind": "decide", "title": "x", "what": "bad"})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.strip(), "user_send: error: SchemaBad at most 7 questions in one letter (got 8) (see the door: aos-user door)")

    def test_unknown_key_and_missing_kind(self):
        r = self.run_tool({"kind": "decide", "title": "x", "color": "red"})
        self.assertIn("user_send: error: ArgumentsBad unknown key color", r.stdout)
        r = self.run_tool({"title": "x"})
        self.assertIn("user_send: error: ArgumentsBad missing kind", r.stdout)
        r = self.run_tool({"kind": "decide", "title": "x", "questions": [{"id": "q1", "oops": 1}]})
        self.assertIn("ArgumentsBad", r.stdout)

    def test_finds_tool_in_ws_tools_first(self):
        d = self.tmp / "ws" / "tools" / "aos-user"
        d.mkdir(parents=True)
        shutil.copy(self.tmp / "bin" / "aos-user", d / "aos-user")
        r = self.run_tool({"kind": "fyi", "title": "done", "what": "the build is green"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("no answer comes for fyi", r.stdout)
        self.assertEqual(json.loads(self.log.read_text())["me"], str(d / "aos-user"))
        r = self.run_tool({"kind": "fyi", "title": "done", "what": "x"}, AOS_USER_TOOL=str(self.tmp / "bin" / "aos-user"))
        self.assertEqual(json.loads(self.log.read_text())["me"], str(self.tmp / "bin" / "aos-user"))

    def test_tool_missing(self):
        os.remove(self.tmp / "bin" / "aos-user")
        r = self.run_tool({"kind": "fyi", "title": "done", "what": "x"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("user_send: error: ToolMissing aos-user not found", r.stdout)


if __name__ == "__main__":
    unittest.main()
