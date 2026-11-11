"""Test aos-agent goal on a fake daemon table (11-11 goal): get with none, set (words, stdin, --limit), done / abandoned, pause, resume (count back to 0), clear, who is recorded (agent vs outside), flags written after the words, and errors."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[4]
BIN = REPO / "proto8" / "cmd" / "aos-agent" / "bin" / "aos-agent"


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return env


class Goal(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-goal-"))
        self.d = self.tmp / "d"
        self.defn = self.tmp / "defs" / "bob"
        self.defn.mkdir(parents=True)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {}}))
        (self.tmp / "ws").mkdir()
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps(
            {"procs": {"bob": {"phase": "running", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn)}}}))
        self.file = self.stack / "goal.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def agent(self, *args, ok=True, stdin=None, env=None):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "goal", "--target", "bob", *args],
                           env=env or clean_env(), capture_output=True, text=True, timeout=60, cwd=self.tmp,
                           input=stdin, stdin=None if stdin is not None else subprocess.DEVNULL)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        else:
            self.assertEqual(p.returncode, 1, p.stdout)
        return p

    def rec(self):
        return json.loads(self.file.read_text())

    def test_none_then_set_and_get(self):
        self.assertEqual(self.agent().stdout, "no goal\n")
        self.assertEqual(self.agent("get", "--json").stdout, "null\n")
        out = self.agent("set", "Write", "the", "report.").stdout
        self.assertIn("set the goal of bob: Write the report.", out)
        r = self.rec()
        self.assertEqual((r["text"], r["status"], r["reminded"], r["limit"], r["set_by"]), ("Write the report.", "active", 0, 10, "outside"))
        got = self.agent("get").stdout
        self.assertIn("status\tactive\n", got)
        self.assertIn("reminded\t0 of 10\n", got)
        self.assertEqual(json.loads(self.agent("get", "-j").stdout)["text"], "Write the report.")
        self.agent("set", "--limit", "2", "-", stdin="From stdin.\n")
        self.assertEqual((self.rec()["text"], self.rec()["limit"]), ("From stdin.", 2))
        self.assertIn("replaced the old one", self.agent("set", "-n", "3", "x").stdout)

    def test_done_pause_resume_clear(self):
        self.agent("set", "Fix it.")
        r = self.rec()
        r["reminded"] = 4
        self.file.write_text(json.dumps(r))
        self.agent("pause", "waiting", "for", "amy")
        self.assertEqual((self.rec()["status"], self.rec()["reason"]), ("paused", "waiting for amy"))
        self.assertIn("already paused", self.agent("pause").stdout)
        self.agent("resume")
        self.assertEqual((self.rec()["status"], self.rec()["reminded"], self.rec()["reason"]), ("active", 0, ""))
        self.assertIn("already active", self.agent("resume").stdout)
        self.agent("done", "--abandoned", "cannot", "be", "done")
        self.assertEqual((self.rec()["status"], self.rec()["reason"]), ("abandoned", "cannot be done"))
        self.assertIn("GoalEnded", self.agent("resume", ok=False).stderr)
        self.assertIn("GoalEnded", self.agent("pause", ok=False).stderr)
        self.agent("done", "ok")
        self.assertEqual(self.rec()["status"], "done")
        self.agent("clear", "-y")
        self.assertFalse(self.file.exists())
        self.assertIn("had no goal", self.agent("clear", "-y").stdout)

    def test_errors(self):
        for act in ("done", "pause", "resume"):
            self.assertIn("GoalMissing", self.agent(act, ok=False).stderr)
        self.assertIn("ArgumentsBad", self.agent("set", ok=False).stderr)
        self.assertIn("ArgumentsBad", self.agent("set", "--limit", "0", "x", ok=False).stderr)
        self.assertIn("ArgumentsBad", self.agent("set", "--limit", "two", "x", ok=False).stderr)
        self.assertIn("ArgumentsBad", self.agent("set", "x" * 1001, ok=False).stderr)
        self.assertIn("ArgumentsBad", self.agent("get", "extra", ok=False).stderr)
        self.assertIn("CommandUnknown", self.agent("show", ok=False).stderr)
        self.file.write_text("[1]")
        self.assertIn("GoalBad", self.agent("get", ok=False).stderr)
        self.agent("set", "over the bad one")                              # set rewrites a broken file
        self.assertEqual(self.rec()["text"], "over the bad one")

    def test_agent_itself_is_recorded(self):
        env = clean_env(AOS_STACK=str(self.stack / "tools" / "goal"))   # what the goal tool runs with
        self.agent("set", "Mine.", env=env)
        self.assertEqual((self.rec()["set_by"], self.rec()["updated_by"]), ("agent", "agent"))
        self.agent("pause", "wait")
        self.assertEqual((self.rec()["set_by"], self.rec()["updated_by"]), ("agent", "outside"))

    def test_flags_after_words(self):
        # 11-11 P-44 續（使用者「全部改」）：旗標寫在位置參數前後都收，外層的 --target、--daemon 也一樣
        p = subprocess.run([str(BIN), "goal", "set", "Write", "it.", "--limit", "3", "--target", "bob", "--daemon", str(self.d)],
                           env=clean_env(), capture_output=True, text=True, timeout=60, cwd=self.tmp, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((self.rec()["text"], self.rec()["limit"]), ("Write it.", 3))
        self.agent("done", "gave", "up", "-a")
        self.assertEqual((self.rec()["status"], self.rec()["reason"]), ("abandoned", "gave up"))
        self.assertEqual(json.loads(self.agent("get", "-j").stdout)["status"], "abandoned")
        self.assertIn("FlagUnknown", self.agent("set", "x", "--nope", ok=False).stderr)

    def test_help_lists_goal(self):
        p = subprocess.run([str(BIN), "--help"], env=clean_env(), capture_output=True, text=True, timeout=30)
        self.assertIn("goal     its goal", p.stdout)


if __name__ == "__main__":
    unittest.main()
