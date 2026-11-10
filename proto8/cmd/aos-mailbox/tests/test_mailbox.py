"""Test aos-mailbox where / peek / read / send against real aos-post boxes and a hand-written daemon table."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
BIN = Path(__file__).resolve().parents[1] / "bin" / "aos-mailbox"


class Mailbox(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-mailbox-"))
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.daemon = self.tmp / "d"
        self.daemon.mkdir()
        (self.tmp / "bob").mkdir()
        (self.daemon / "procs_state.json").write_text(json.dumps({"procs": {"bob": {"stack": "../bob", "phase": "running"}}}))
        self.env = dict(os.environ, HOME=str(self.home), USER="alice", PYTHONDONTWRITEBYTECODE="1")
        for k in ("AOS_MY_STACK", "AOS_DAEMON", "AOS_WS", "AOS_STACK"):
            self.env.pop(k, None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_mb(self, *args, stdin=""):
        return subprocess.run([sys.executable, str(BIN)] + list(args), input=stdin, capture_output=True, text=True,
                              env=self.env, cwd=str(self.tmp), timeout=30)

    def ok(self, *args, **kw):
        r = self.run_mb(*args, **kw)
        self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
        return r.stdout

    def test_default_stack_is_home_dot_stack(self):
        self.assertEqual(self.ok("where").strip(), str(self.home / ".stack" / "mailbox"))
        self.env["AOS_MY_STACK"] = str(self.tmp / "me")
        self.assertEqual(self.ok("where").strip(), str(self.tmp / "me" / "mailbox"))
        self.assertEqual(self.ok("-s", "other", "where").strip(), str(self.tmp / "other" / "mailbox"))

    def test_send_by_name_peek_read_reply(self):
        name = self.ok("send", "--to", "bob", "-d", "d", "--status", "REQUEST", "--title", "Please count files", "count", "them").strip()
        peek = self.ok("-s", "bob", "peek")
        self.assertEqual(peek, "%s\talice\tREQUEST\tPlease count files\n" % name)
        r = json.loads(self.ok("-s", "bob", "read", "-j"))
        self.assertEqual((r["letter"], r["what"], r["outputs"], r["to"]), (name, "count them", "none", "bob"))
        self.assertEqual(r["reply_to"], str(self.home / ".stack" / "mailbox"))
        self.assertEqual(self.ok("-s", "bob", "peek"), "")
        self.assertEqual(self.run_mb("-s", "bob", "read").returncode, 10)              # 讀完就沒了
        self.ok("-s", "bob", "send", "--box", r["reply_to"], "--in-reply-to", name, "--from", "bob", "--status", "DONE",
                "--title", "3 files", "-", stdin="I counted 3.\n")
        out = self.ok("read", "--keep")
        self.assertIn("from: bob\n", out)
        self.assertIn("in_reply_to: %s\n" % name, out)
        self.assertIn("what: I counted 3.\n", out)
        self.assertEqual(len(os.listdir(self.home / ".stack" / "mailbox" / "archive")), 1)   # --keep 留著

    def test_read_all_and_order(self):
        for t in ("first", "second"):
            self.ok("send", "--box", str(self.ok("-s", "bob", "where").strip()), "--status", "PROGRESS", "--title", t, "x")
        out = [json.loads(l)["title"] for l in self.ok("-s", "bob", "read", "--all", "-j").splitlines()]
        self.assertEqual(out, ["first", "second"])

    def test_refusals(self):
        box = self.ok("-s", "bob", "where").strip()
        for args, code in ((["--box", box, "--status", "DONEZ", "--title", "t", "x"], "StatusBad"),
                           (["--box", str(self.tmp), "--status", "DONE", "--title", "t", "x"], "MailboxBad"),
                           (["--box", str(self.tmp / "nope"), "--status", "DONE", "--title", "t", "x"], "MailboxMissing"),
                           (["--to", "carol", "-d", "d", "--status", "DONE", "--title", "t", "x"], "InstanceMissing"),
                           (["--to", "bob", "--box", box, "--status", "DONE", "--title", "t", "x"], "ArgumentsBad"),
                           (["--box", box, "--status", "DONE", "--title", "t"], "ArgumentsBad")):
            r = self.run_mb("send", *args)
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stderr.startswith("aos-mailbox: error: %s " % code), (args, r.stderr))
        self.assertEqual(os.listdir(Path(box) / "new"), [])
        r = self.run_mb("fly")
        self.assertIn("error: CommandUnknown", r.stderr)

    def test_peek_without_mailbox_is_empty(self):
        self.assertEqual(self.ok("-s", "nobody", "peek"), "")
        self.assertFalse((self.tmp / "nobody").exists())
        self.assertEqual(self.run_mb("-s", "nobody", "read").returncode, 10)


if __name__ == "__main__":
    unittest.main()
