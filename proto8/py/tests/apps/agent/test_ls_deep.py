"""Test aos-agent ctl ls --deep: walks rows whose stack is a daemon, adds PID state, STAGE and LAST-ACTIVE (fake tables)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import env_helper  # noqa: E402  同夾的共用零件


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[5]
BIN = REPO / "proto8" / "bin" / "aos-agent"


class LsDeep(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ls-deep-"))
        self.d = self.tmp / "d"
        (self.tmp / "ws").mkdir()
        self.table(self.d, {
            # ann：活著的 pid（這個測試自己）、stage.txt 是 think、queue 一封
            "ann": {"phase": "running", "stack": "procs/ann", "ws": "../ws", "pid": os.getpid()},
            # kid：自己是一台 daemon（有 procs_state.json），pid 已經不在
            "kid": {"phase": "running", "stack": "procs/kid", "ws": "../ws", "pid": 2147483647},
            # back：stack 指回頂層那台＝不再走（防繞圈）
            "back": {"phase": "stopped", "stack": ".", "ws": "../ws"},
            # bad：自己是 daemon 但表壞了＝stderr 一行 warning，照走別的
            "bad": {"phase": "stopped", "stack": "procs/bad", "ws": "../ws", "reason": "exited 1"},
        })
        ann = self.d / "procs" / "ann"
        (ann / "stage.txt").write_text("think\nsecond\n")
        for box in ("new", "cur", "tmp"):
            (ann / "queue" / box).mkdir(parents=True)
        (ann / "queue" / "new" / "a").write_text("{}")
        os.utime(ann / "stage.txt", (1000000000, 1000000000))
        os.utime(ann / "queue", (1000000000, 1000000000))
        os.utime(ann, (1000000000, 1000000000))
        kid = self.d / "procs" / "kid"
        self.table(kid, {"grand": {"phase": "running", "stack": "procs/grand", "ws": "../../../ws"}})
        (kid / "procs" / "grand" / "busy.txt").write_text("x\n")
        (self.d / "procs" / "bad" / "procs_state.json").write_text("{broken")

    def table(self, d, rows):
        for n, r in rows.items():
            if r["stack"] != ".":
                (d / r["stack"]).mkdir(parents=True, exist_ok=True)
        (d / "procs_state.json").write_text(json.dumps({"procs": rows}))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def ls(self, *args):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "ctl", "ls", "--deep", *args],
                           env=env_helper.clean_env(TZ="UTC"), capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def test_text(self):
        p = self.ls()
        lines = [line.split("\t") for line in p.stdout.splitlines()]
        self.assertEqual([c[0] for c in lines], ["ann", "kid", "back", "bad", "kid/grand"])
        self.assertEqual(lines[0], ["ann", "running", "%d alive" % os.getpid(), "think", "1", "09-09 01:46", "-"])
        self.assertEqual(lines[1][:5], ["kid", "running", "2147483647 dead", "-", "-"])
        self.assertEqual(lines[3][:3] + lines[3][6:], ["bad", "stopped", "-", "exited 1"])
        self.assertEqual(lines[4][:4], ["kid/grand", "running", "-", "cli"])
        today = time.strftime("%m-%d", time.gmtime())
        self.assertTrue(lines[4][5].startswith(today), lines[4])
        self.assertEqual(len(lines[0]), 7)
        self.assertIn("aos-agent: warning: could not list the table %s" % (self.d / "procs" / "bad"), p.stderr)
        self.assertEqual(len(self.ls("-l").stdout.splitlines()[0].split("\t")), 11)

    def test_json(self):
        rows = {r["path"]: r for r in json.loads(self.ls("-j").stdout)}
        self.assertEqual(set(rows), {"ann", "kid", "back", "bad", "kid/grand"})
        ann, grand = rows["ann"], rows["kid/grand"]
        self.assertEqual((ann["pid"], ann["pid_state"], ann["stage"], ann["depth"]), (os.getpid(), "alive", "think", 1))
        self.assertEqual(ann["last_active"], "2001-09-09T01:46:40+00:00")
        self.assertEqual(ann["table"], str(self.d))
        self.assertEqual((grand["name"], grand["depth"], grand["table"]), ("grand", 2, str(self.d / "procs" / "kid")))
        self.assertEqual(grand["stack"], str(self.d / "procs" / "kid" / "procs" / "grand"))
        self.assertEqual(grand["ws"], str(self.tmp / "ws"))
        self.assertEqual((grand["pid"], grand["pid_state"], grand["busy"]), (None, None, "cli"))
        self.assertEqual(rows["kid"]["pid_state"], "dead")

    def test_plain_ls_unchanged(self):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "ctl", "ls"], env=env_helper.clean_env(TZ="UTC"),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual([line.split("\t")[0] for line in p.stdout.splitlines()], ["ann", "kid", "back", "bad"])

    def test_help(self):
        p = subprocess.run([str(BIN), "ctl", "ls", "--help"], env=env_helper.clean_env(), capture_output=True,
                           text=True, timeout=30)
        self.assertIn("--deep", p.stdout)
        self.assertTrue(p.stdout.isascii())


if __name__ == "__main__":
    unittest.main()
