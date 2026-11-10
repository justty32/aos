"""Test aos-agent ctl ls health fields (--json keys auto_restart/queue/cooldown/busy, -l columns) on a fake daemon table."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
BIN = REPO / "proto8" / "cmd" / "aos-agent" / "bin" / "aos-agent"
COOL = {"failures": 4, "until": "2099-11-10T02:41:07Z", "at": "2026-11-10T02:33:07Z",
        "code": "CliFailed", "reason": "claude exited 1: usage limit reached", "dropped": 3}
DUE = dict(COOL, failures=2, until="2000-01-01T00:00:00Z", code="BrainFailed",
           reason="x" * 200, dropped=0)


def clean_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env.update(PYTHONDONTWRITEBYTECODE="1", TZ="UTC")
    return env


class LsHealth(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ls-health-"))
        self.d = self.tmp / "d"
        (self.tmp / "ws").mkdir()
        rows = {
            # ann：冷卻中、new/ 兩封（. 開頭的不算）＋cur/ 一封、auto_restart
            "ann": {"phase": "running", "stack": "procs/ann", "ws": "../ws", "auto_restart": True},
            # bob：表上 stopped＋reason、fsm 等腦回信（think/pending.txt）、沒 queue/
            "bob": {"phase": "stopped", "stack": "procs/bob", "ws": "../ws", "reason": "exited 1\nsecond line"},
            # cat：冷卻到了（due）、stage.txt 是 act
            "cat": {"phase": "running", "stack": "procs/cat", "ws": "../ws"},
            # dan：eca 小格的 busy.txt＝cli
            "dan": {"phase": "running", "stack": "procs/dan", "ws": "../ws"},
        }
        for n in rows:
            (self.d / "procs" / n).mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps({"procs": rows}))
        ann = self.d / "procs" / "ann"
        for box in ("new", "cur", "tmp"):
            (ann / "queue" / box).mkdir(parents=True)
        for f in ("new/a", "new/b", "new/.c.tmp", "cur/z"):
            (ann / "queue" / f).write_text("{}")
        (ann / "cooldown.json").write_text(json.dumps(COOL))
        bob = self.d / "procs" / "bob"
        (bob / "think").mkdir()
        (bob / "think" / "pending.txt").write_text("letter-1\n")
        cat = self.d / "procs" / "cat"
        (cat / "stage.txt").write_text("act\n")
        (cat / "cooldown.json").write_text(json.dumps(DUE))
        (self.d / "procs" / "dan" / "busy.txt").write_text("2026-11-10T00:00:00Z\n")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def ls(self, *args):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "ctl", "ls", *args], env=clean_env(),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stderr, "")
        return p.stdout

    def base(self):
        ws = str(self.tmp / "ws")
        return [["ann", "running", ws, "3", "-"],
                ["bob", "stopped", ws, "-", "exited 1 second line"],
                ["cat", "running", ws, "-", "-"],
                ["dan", "running", ws, "-", "-"]]

    def test_plain_unchanged(self):
        # 不帶 -l：跟改前同一個樣子（五欄 TAB）
        want = "".join("\t".join(r) + "\n" for r in self.base())
        self.assertEqual(self.ls(), want)

    def test_long(self):
        extra = [["2", "4", "until 02:41 (4)", "CliFailed claude exited 1: usage limit reached"],
                 ["-", "0", "-", "exited 1 second line"],
                 ["-", "2", "due (2)", "BrainFailed " + "x" * 45 + "..."],
                 ["-", "0", "-", "-"]]
        want = "".join("\t".join(b + e) + "\n" for b, e in zip(self.base(), extra))
        self.assertEqual(self.ls("-l"), want)
        self.assertEqual(self.ls("--long"), want)
        self.assertEqual(len(extra[2][3]), 60)

    def test_json(self):
        rows = {r["name"]: r for r in json.loads(self.ls("-j"))}
        old = {"name", "state", "phase", "ws", "stack", "queued", "reason"}
        for r in rows.values():
            self.assertTrue(old <= set(r))
        self.assertEqual(rows["ann"]["queued"], 3)
        self.assertEqual(rows["ann"]["queue"], 2)
        self.assertIs(rows["ann"]["auto_restart"], True)
        self.assertEqual(rows["ann"]["cooldown"], {k: COOL[k] for k in ("failures", "until", "code", "reason", "dropped")}
                         | {"state": "cooling"})
        self.assertIsNone(rows["ann"]["busy"])
        self.assertIs(rows["bob"]["auto_restart"], False)
        self.assertIsNone(rows["bob"]["queue"])
        self.assertIsNone(rows["bob"]["cooldown"])
        self.assertEqual(rows["bob"]["busy"], "think")
        self.assertEqual(rows["cat"]["cooldown"]["state"], "due")
        self.assertEqual(rows["cat"]["busy"], "act")
        self.assertEqual(rows["dan"]["busy"], "cli")
        self.assertEqual(json.loads(self.ls("-j", "-l")), json.loads(self.ls("-j")))

    def test_bad_cooldown_is_none(self):
        (self.d / "procs" / "ann" / "cooldown.json").write_text("not json")
        rows = {r["name"]: r for r in json.loads(self.ls("--json"))}
        self.assertIsNone(rows["ann"]["cooldown"])
        self.assertEqual(self.ls("-l").splitlines()[0].split("\t")[5:], ["2", "0", "-", "-"])

    def test_help(self):
        out = self.ls("--help")
        self.assertIn("-l, --long", out)
        self.assertIn("usage: aos-agent [--daemon D] ctl ls [-j] [-l]", out)


if __name__ == "__main__":
    unittest.main()
