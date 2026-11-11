"""Test the goal in aos-eca-turn (11-11 goal/02) with fake claude / codex CLIs: queue empty + last turn answered + goal active = the reminder is the prompt; done stops it; the limit pauses it; letters come first; a tool call in the CLI's transcript resets the count; with an empty history the goal is the opening prompt (after --prompt's opening)."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
PROTO = HERE.parents[2]
TURN = PROTO / "cmd" / "aos-eca" / "bin" / "aos-eca-turn"
LOCAL_BIN = os.path.expanduser("~/.local/bin")
NOTE = "[aos] goal: "


class EcaGoal(unittest.TestCase):
    kind = "claude"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="eca-goal-")
        self.addCleanup(tmp.cleanup)
        self.t = Path(tmp.name)
        self.bin, self.defn, self.ws, self.stack, self.home = (self.t / n for n in ("bin", "def", "ws", "stack", "home"))
        for d in (self.bin, self.defn, self.ws, self.stack, self.home):
            d.mkdir()
        (self.bin / self.kind).symlink_to(HERE / ("fake_" + self.kind))
        (self.defn / "cli.json").write_text(json.dumps({"kind": self.kind, "timeout_ms": 30000}))
        self.cli_log = self.t / "cli.jsonl"
        subprocess.run(["aos-post", "init", str(self.stack / "queue")], env=self.env(), check=True, capture_output=True)

    def env(self, **more):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("AOS_", "FAKE_CLI_")) and k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME")}
        env.update(PATH="%s:%s:%s" % (self.bin, LOCAL_BIN, env.get("PATH", "")), HOME=str(self.home),
                   AOS_STACK=str(self.stack), AOS_WS=str(self.ws), FAKE_CLI_LOG=str(self.cli_log), PYTHONDONTWRITEBYTECODE="1")
        env.update(more)
        return env

    def say(self, text):
        subprocess.run(["aos-post", "send", "--ordered", str(self.stack / "queue")], check=True, capture_output=True,
                       input=json.dumps({"role": "user", "content": text}), env=self.env(), text=True)

    def turn(self, code=0, empty="idle", **env):
        r = subprocess.run([str(TURN), "--on-empty", empty, str(self.defn)], env=self.env(**env),
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, code, r.stderr)
        return r

    def set_goal(self, text, limit=10, status="active"):
        (self.stack / "goal.json").write_text(json.dumps({"text": text, "status": status, "reason": "", "reminded": 0, "limit": limit,
                                                          "set_by": "outside", "updated_by": "outside",
                                                          "updated_at": "2026-11-11T00:00:00Z"}))

    def rec(self):
        return json.loads((self.stack / "goal.json").read_text())

    def history(self):
        p = self.stack / "history.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []

    def notes(self):
        return [m["content"] for m in self.history() if m.get("role") == "user" and m["content"].startswith(NOTE)]

    def asked(self):
        return [json.loads(l)["stdin"] for l in self.cli_log.read_text().splitlines()] if self.cli_log.exists() else []

    def test_no_goal_is_unchanged(self):
        self.turn(10, empty="stop")
        self.say("hi")
        self.turn()
        self.turn(10, empty="stop")
        self.assertEqual(len(self.asked()), 1)

    def test_remind_then_done(self):
        self.say("hi")
        self.turn()
        self.set_goal("Write the report.")
        self.turn()
        self.assertEqual(len(self.notes()), 1)
        self.assertTrue(self.asked()[-1].endswith("[aos] goal: Write the report. (reminder 1 of 10. Keep working on it; when it is "
                                                  "finished call the goal tool with op done; if you are waiting for someone, op pause.)"))
        self.assertEqual(self.history()[-1]["role"], "assistant")
        self.assertEqual(self.rec()["reminded"], 1)
        self.turn(empty="stop")                                            # also with --on-empty stop: a goal turn instead of exit 10
        self.assertEqual(self.rec()["reminded"], 2)
        r = self.rec()
        r["status"] = "done"
        (self.stack / "goal.json").write_text(json.dumps(r))
        self.turn(10, empty="stop")
        self.assertEqual((len(self.notes()), len(self.asked())), (2, 3))

    def test_empty_history_gets_the_goal_as_opening(self):
        # 11-11 稍後使用者「也丟，當開場題目」：queue 空、還沒有上一輪答案、外面先 set 了 goal＝第一輪的題目就是它（--on-empty stop 也一樣）
        self.set_goal("Write the report.")
        self.turn(empty="stop")
        self.assertEqual(len(self.asked()), 1)
        self.assertTrue(self.asked()[0].startswith("[aos] goal: Write the report. (reminder 1 of 10."), self.asked())
        h = self.history()
        self.assertEqual([m["role"] for m in h], ["user", "assistant"])
        self.assertTrue(h[0]["content"].startswith(NOTE))
        self.assertEqual(self.rec()["reminded"], 1)

    def test_opening_prompt_comes_before_the_goal(self):
        (self.defn / "prompt.txt").write_text("Start here.\n")
        self.set_goal("Write the report.")
        for _ in range(2):
            r = subprocess.run([str(TURN), "--on-empty", "stop", "--prompt", "prompt.txt", str(self.defn)], env=self.env(),
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.asked()[0], "Start here.")
        self.assertIn("(reminder 1 of 10.", self.asked()[1])

    def test_limit_pauses(self):
        self.say("hi")
        self.turn()
        self.set_goal("Keep going.", limit=2)
        for _ in range(3):
            self.turn()
        self.turn(10, empty="stop")
        n = self.notes()
        self.assertEqual(len(n), 3)
        self.assertEqual(n[2], "[aos] goal: reminder limit 2 reached; goal paused (op resume to go on). Goal: Keep going.")
        self.assertEqual((self.rec()["status"], self.rec()["updated_by"]), ("paused", "aos"))
        self.assertEqual(self.history()[-1]["role"], "assistant")

    def test_letters_first_and_paused(self):
        self.say("hi")
        self.turn()
        self.set_goal("Fix it.", status="paused")
        self.turn(10, empty="stop")
        self.set_goal("Fix it.")
        self.say("a letter")
        self.turn()
        self.assertEqual(self.asked()[-1], "a letter")
        self.assertEqual((self.notes(), self.rec()["reminded"]), ([], 0))

    def test_tool_call_resets_the_count(self):
        tool = "mcp__aos__peek_now_time" if self.kind == "claude" else "aos__peek_now_time"
        own = "mcp__aos__goal" if self.kind == "claude" else "aos__goal"
        self.say("hi")
        self.turn()
        self.set_goal("Do work.", limit=3)
        self.turn()
        self.turn()
        self.assertEqual(self.rec()["reminded"], 2)
        self.turn(FAKE_CLI_TOOL=tool)                                      # reminder 3, but the CLI called a tool: back to 0
        self.assertEqual(self.rec()["reminded"], 0)
        self.turn(FAKE_CLI_TOOL=own)                                       # calling goal itself is no progress
        self.assertEqual(self.rec()["reminded"], 1)
        self.assertIn("(reminder 1 of 3.", self.notes()[-1])


class EcaGoalCodex(EcaGoal):
    kind = "codex"


if __name__ == "__main__":
    unittest.main()
