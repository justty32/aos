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
PROTO = AGENT.parents[2]
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
        self.assertNotIn("user-zone replies are kept", r.stdout)
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

    def test_keep_file_in_workspace(self):
        bob_box = str(self.tmp / "bob" / "mailbox")
        subprocess.run(["aos-post", "init", bob_box], check=True)
        (self.tmp / "ws" / "mail").mkdir()
        log = self.tmp / "ws" / "mail" / "letters.jsonl"
        r = self.tool("mailbox_send", {"box": bob_box, "status": "REQUEST", "title": "Count files", "what": "Count them.",
                                       "keep": "mail/letters.jsonl"})                  # 相對路徑從工作區算
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("(one line added to mail/letters.jsonl)", r.stdout)
        r = self.tool("mailbox_read", {"all": True, "keep": "mail/letters.jsonl"}, me="bob")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("what: Count them.\n", r.stdout)
        self.assertIn("reply_to: ", r.stdout)                                          # 印給腦看的照舊
        self.assertIn("(one line per letter added to mail/letters.jsonl; removed from the mailbox)", r.stdout)
        self.assertFalse((self.tmp / "bob" / "mailbox" / "archive").exists())          # 檔名＝只進檔，不進 archive/
        lines = [json.loads(l) for l in log.read_text().splitlines()]
        self.assertEqual([(l["kept"], l["from"], l["title"]) for l in lines],
                         [("sent", "alice", "Count files"), ("received", "alice", "Count files")])
        self.assertEqual(lines[0]["letter"], lines[1]["letter"])
        self.assertNotIn(str(self.tmp), log.read_text())
        self.assertEqual(self.tool("mailbox_read", {}, me="bob").stdout, "no letters waiting\n")
        r = self.tool("mailbox_send", {"box": bob_box, "status": "DONE", "title": "t", "what": "w", "keep": "nodir/x.jsonl"})
        self.assertTrue(r.stdout.startswith("mailbox_send: error: WriteFailed "), r.stdout)
        r = self.tool("mailbox_read", {"keep": "nodir/x.jsonl"}, me="bob")             # 沒信箱可拿前就先開檔
        self.assertEqual(self.tool("mailbox_peek", {}, me="bob").stdout, "no letters waiting\n")

    def test_user_zone_summary_contract(self):
        fake_mailbox = self.tmp / "bin" / "aos-mailbox"
        fake_mailbox.write_text('''#!/usr/bin/env python3
import json, os
path = os.path.join(os.environ["FAKE_STACK"], "mailbox", "archive", "reply")
print("letter: reply")
print('(unverified user-zone reply: kept in %s; verify it with user_verify %s or aos-user verify %s)'
      % (path, json.dumps({"letter": "reply"}), path))
''')
        fake_mailbox.chmod(0o755)
        archive = self.tmp / "bob" / "mailbox" / "archive"
        note = " (user-zone replies are kept in %s/, see above)" % archive
        for keep in (None, False, "zone.jsonl", True):
            with self.subTest(keep=keep):
                r = self.tool("mailbox_read", {} if keep is None else {"keep": keep}, me="bob")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("(unverified user-zone reply: kept in ", r.stdout)
                if keep is True:
                    self.assertIn("(kept in %s/)\n" % archive, r.stdout)
                    self.assertNotIn(note, r.stdout)
                else:
                    summary = ("one line per letter added to zone.jsonl; removed from the mailbox"
                               if keep else "removed from the mailbox")
                    self.assertIn("(%s%s)\n" % (summary, note), r.stdout)

    def test_user_zone_replies_are_kept_and_reported(self):
        bob_box = self.tmp / "bob" / "mailbox"
        subprocess.run(["aos-post", "init", str(bob_box)], check=True)
        log = self.tmp / "ws" / "zone.jsonl"
        for number, keep in enumerate((None, "zone.jsonl", True)):
            for status in ("DONE", "FAILED"):
                name = "zone-%d-%s" % (number, status.lower())
                folder = bob_box / "new" / name
                folder.mkdir()
                body = {"zone": "user-zone/1", "from": "user", "status": status,
                        "title": "Re: Test", "what": "Test reply"}
                if status == "FAILED":
                    body["returned"] = True
                (folder / "letter.json").write_text(json.dumps({"sender": "user", "sent_at": "2026-11-14T00:00:00Z",
                                                               "body": body, "in_reply_to": "original"}))
                args = {} if keep is None else {"keep": keep}
                r = self.tool("mailbox_read", args, me="bob")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                archived = bob_box / "archive" / name
                notice = ('(unverified user-zone reply: kept in %s; verify it with user_verify '
                          '{"letter": "%s"} or aos-user verify %s)' % (archived, name, archived))
                self.assertIn(notice + "\n", r.stdout)
                self.assertTrue((archived / "letter.json").is_file())
                self.assertFalse(folder.exists())
                note = " (user-zone replies are kept in %s/archive/, see above)" % bob_box
                if keep is True:
                    self.assertIn("(kept in %s/archive/)\n" % bob_box, r.stdout)
                    self.assertNotIn(note, r.stdout)
                else:
                    summary = ("one line per letter added to zone.jsonl; removed from the mailbox"
                               if keep else "removed from the mailbox")
                    self.assertIn("(%s%s)\n" % (summary, note), r.stdout)
        self.assertEqual(len(log.read_text().splitlines()), 2)

    def test_refusals(self):
        box = str(self.tmp / "bob")                       # 不是信箱（沒有 tmp/ new/ cur/）
        for name, args, code in (("mailbox_send", {"box": box, "status": "DONE", "title": "t", "what": "w"}, "MailboxBad"),
                                 ("mailbox_send", {"box": box, "status": "OK", "title": "t", "what": "w"}, "StatusBad"),
                                 ("mailbox_send", {"status": "DONE", "title": "t", "what": "w"}, "ArgumentsBad"),
                                 ("mailbox_send", {"box": box, "status": "DONE", "title": "t"}, "ArgumentsBad"),
                                 ("mailbox_send", {"box": box, "status": "DONE", "title": "t", "what": "w", "keep": True}, "ArgumentsBad"),
                                 ("mailbox_read", {"keep": 3}, "ArgumentsBad"),
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
