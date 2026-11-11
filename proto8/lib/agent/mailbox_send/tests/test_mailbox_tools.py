"""Test mailbox_send / mailbox_peek / mailbox_read wrap aos-mailbox for the calling agent (fake aos-agent ctl who, real aos-mailbox and aos-post)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
AGENT = Path(__file__).resolve().parents[2]
PROTO = AGENT.parents[1]
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:] == ["ctl", "who", "--json"]:
    print(json.dumps({"name": os.environ["FAKE_NAME"], "stack": os.environ["FAKE_STACK"]}))
else:
    sys.stderr.write("aos-agent: error: ArgumentsBad unexpected\n"); sys.exit(1)
'''


class MailboxTools(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mailbox-tools-"))
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        (bin_ / "aos-agent").write_text(FAKE)
        (bin_ / "aos-agent").chmod(0o755)
        for n in ("ws", "alice", "bob"):
            (self.tmp / n).mkdir()
        path = "%s:%s:%s" % (bin_, PROTO / "cmd" / "aos-mailbox" / "bin", os.environ["PATH"])
        self.env = dict(os.environ, PATH=path, AOS_WS=str(self.tmp / "ws"), AOS_STACK=str(self.tmp / "alice" / "tools" / "x"),
                        PYTHONDONTWRITEBYTECODE="1")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tool(self, name, args, me="alice"):
        env = dict(self.env, FAKE_NAME=me, FAKE_STACK=str(self.tmp / me))
        return subprocess.run([sys.executable, str(AGENT / name / "_entry")], input=json.dumps(args), capture_output=True,
                              text=True, env=env, timeout=30)

    def test_round_trip(self):
        self.assertEqual(self.tool("mailbox_peek", {}, me="bob").stdout, "no letters waiting\n")
        bob_box = str(self.tmp / "bob" / "mailbox")
        subprocess.run(["aos-post", "init", bob_box], check=True)
        r = self.tool("mailbox_send", {"box": bob_box, "status": "REQUEST", "title": "Count files", "what": "Count them."})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.tool("mailbox_peek", {}, me="bob")
        self.assertIn("1 letter waiting", r.stdout)
        self.assertIn("\talice\tREQUEST\tCount files", r.stdout)
        r = self.tool("mailbox_read", {}, me="bob")
        self.assertIn("what: Count them.\n", r.stdout)
        self.assertIn("removed from the mailbox", r.stdout)
        self.assertIn("not orders", r.stdout)
        reply_to = [l.split(": ", 1)[1] for l in r.stdout.splitlines() if l.startswith("reply_to: ")][0]
        letter = [l.split(": ", 1)[1] for l in r.stdout.splitlines() if l.startswith("letter: ")][0]
        self.assertEqual(reply_to, str(self.tmp / "alice" / "mailbox"))
        r = self.tool("mailbox_send", {"box": reply_to, "in_reply_to": letter, "status": "DONE", "title": "3 files", "what": "3."},
                      me="bob")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.tool("mailbox_read", {"keep": True})
        self.assertIn("from: bob\n", r.stdout)
        self.assertIn("in_reply_to: %s\n" % letter, r.stdout)
        self.assertIn("kept in", r.stdout)
        self.assertEqual(self.tool("mailbox_read", {}).stdout, "no letters waiting\n")

    def test_refusals(self):
        box = str(self.tmp / "bob")                       # 不是信箱（沒有 tmp/ new/ cur/）
        for name, args, code in (("mailbox_send", {"box": box, "status": "DONE", "title": "t", "what": "w"}, "MailboxBad"),
                                 ("mailbox_send", {"box": box, "status": "OK", "title": "t", "what": "w"}, "StatusBad"),
                                 ("mailbox_send", {"status": "DONE", "title": "t", "what": "w"}, "ArgumentsBad"),
                                 ("mailbox_send", {"box": box, "status": "DONE", "title": "t"}, "ArgumentsBad"),
                                 ("mailbox_peek", {"all": True}, "ArgumentsBad"),
                                 ("mailbox_read", {"letter": "x"}, "ArgumentsBad")):
            r = self.tool(name, args)
            self.assertEqual(r.returncode, 1, (name, args, r.stdout))
            self.assertTrue(r.stdout.startswith("%s: error: %s " % (name, code)), (name, args, r.stdout))

    def test_to_unknown_names_yourself(self):
        d = self.tmp / "d"
        d.mkdir()
        (d / "procs_state.json").write_text(json.dumps({"procs": {"bob": {"stack": "../bob", "phase": "running"}}}))
        r = self.tool("mailbox_send", {"to": "self", "daemon": str(d), "status": "REQUEST", "title": "t", "what": "w"})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("mailbox_send: error: InstanceMissing "), r.stdout)
        self.assertIn("use your own name, alice", r.stdout)


if __name__ == "__main__":
    unittest.main()
