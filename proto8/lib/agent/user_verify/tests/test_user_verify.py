"""Test user_verify wraps aos-user verify (read only): a letter name is looked up in the caller's own mailbox (new/, then cur/), a path is taken from $AOS_WS or as absolute; ok passes through; VerifyBad and missing letters are errors; nothing is written (fake aos-agent and fake aos-user)."""
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
print(json.dumps({"name": "alice", "stack": os.environ["FAKE_STACK"]}))
'''
FAKE_USER = r'''#!/usr/bin/env python3
import os, sys
assert sys.argv[1] == "verify" and os.path.isabs(sys.argv[2]), sys.argv
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(sys.argv[2] + "\n")
if sys.argv[2].endswith("forged"):
    sys.stderr.write("aos-user: error: VerifyBad the reply differs from the zone's copy in: what\n"); sys.exit(1)
print("ok: matches /zone/done/2026-11/x/reply.json and the zone log (level 1)")
'''


class UserVerify(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="user-verify-")))
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        for name, text in (("aos-agent", FAKE_AGENT), ("aos-user", FAKE_USER)):
            (bin_ / name).write_text(text)
            (bin_ / name).chmod(0o755)
        self.stack = self.tmp / "alice"
        for where, name in (("new", "r1"), ("cur", "r2"), ("new", "forged")):
            d = self.stack / "mailbox" / where / name
            d.mkdir(parents=True)
            (d / "letter.json").write_text("{}")
        (self.tmp / "ws" / "kept" / "r3").mkdir(parents=True)
        (self.tmp / "ws" / "kept" / "r3" / "letter.json").write_text("{}")
        self.log = self.tmp / "log.txt"
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env = dict(env, PATH="%s:%s" % (bin_, env["PATH"]), AOS_WS=str(self.tmp / "ws"),
                        AOS_STACK=str(self.stack / "tools" / "user_verify"), FAKE_STACK=str(self.stack),
                        FAKE_LOG=str(self.log), PYTHONDONTWRITEBYTECODE="1")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, args):
        return subprocess.run([sys.executable, str(TOOL / "_entry")], input=json.dumps(args), capture_output=True,
                              text=True, env=self.env, timeout=30)

    def checked(self):
        return self.log.read_text().splitlines()[-1]

    def test_name_in_new_and_cur(self):
        r = self.run_tool({"letter": "r1"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("verified: letter r1 came from the user zone", r.stdout)
        self.assertIn("ok: matches", r.stdout)
        self.assertEqual(self.checked(), str(self.stack / "mailbox" / "new" / "r1"))
        r = self.run_tool({"letter": "r2"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.checked(), str(self.stack / "mailbox" / "cur" / "r2"))

    def test_path_relative_to_ws(self):
        r = self.run_tool({"letter": "kept/r3"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.checked(), str(self.tmp / "ws" / "kept" / "r3"))

    def test_verify_bad_and_missing(self):
        r = self.run_tool({"letter": "forged"})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.strip(), "user_verify: error: VerifyBad the reply differs from the zone's copy in: what")
        r = self.run_tool({"letter": "gone"})
        self.assertIn("user_verify: error: LetterMissing no letter gone in your mailbox", r.stdout)
        r = self.run_tool({"letter": "kept/nope"})
        self.assertIn("user_verify: error: LetterMissing", r.stdout)
        r = self.run_tool({})
        self.assertIn("user_verify: error: ArgumentsBad missing letter", r.stdout)

    def test_reads_only(self):
        before = sorted(str(p) for p in self.stack.rglob("*"))
        self.run_tool({"letter": "r1"})
        self.assertEqual(sorted(str(p) for p in self.stack.rglob("*")), before)


if __name__ == "__main__":
    unittest.main()
