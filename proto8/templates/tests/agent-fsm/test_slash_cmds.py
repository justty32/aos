# Verify agent-fsm's /status, /usage and /exit letters (line eca-aos-templates-1125b, user 11-25 "18.要認"): answered in idle without a brain call, a batch of their own, with fake commands.
import json
import sys
import unittest

import test_compact as compact_tests
import test_reply_match as reply_tests

sys.dont_write_bytecode = True
from aos import ws as aos_ws  # noqa: E402

OLD = compact_tests.OLD
PREFIX = "[aos] slash: "
FAKE_AGENT = """import json, os, sys
with open(os.environ['FAKE_AGENT_LOG'], 'a') as f:
    f.write(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd()}) + '\\n')
if sys.argv[1:3] == ['ctl', 'who']:
    print('ann'); sys.exit(0)
if os.environ.get('FAKE_AGENT_FAIL'):
    print('aos-agent: error: DaemonMissing AOS_DAEMON is not set', file=sys.stderr); sys.exit(1)
print('stop sent for ann')
"""


class SlashCommands(unittest.TestCase):
    setUp = compact_tests.Compact.setUp
    command = reply_tests.ReplyMatch.command
    send = reply_tests.ReplyMatch.send
    letter = reply_tests.ReplyMatch.letter
    history = reply_tests.ReplyMatch.history
    letters = reply_tests.ReplyMatch.letters
    think = reply_tests.ReplyMatch.think
    run_cell = compact_tests.Compact.run_cell

    def cur(self):
        return sorted(p.name for p in (self.stack / "queue/cur").iterdir() if not p.name.startswith("."))

    def answered(self, name, command):
        """The last two messages are this letter and its slash answer; the brain was not asked. Returns the answer text."""
        h = self.history()
        self.assertEqual(h[-2]["aos"], {"letter": name})
        self.assertEqual(h[-1]["role"], "assistant")
        self.assertEqual(h[-1]["aos"], {"answer_to": [name], "slash": command})
        text = h[-1]["content"]
        self.assertTrue(text.startswith(PREFIX + command + ": "), text)
        self.assertEqual(aos_ws.answer_for(str(self.stack), name), ("answered", text))
        self.assertEqual(self.letters()["pending"], [])
        self.assertFalse((self.root / "sent.json").exists())             # no brain call
        return text[len(PREFIX):]

    def test_status_reports_from_the_stack(self):
        self.history(OLD)
        (self.stack / "llm.json").write_text('{"reasoning_effort": "high"}')   # the stack's own settings lie over the definition's
        (self.stack / "goal.json").write_text(json.dumps({"text": "finish the report", "status": "paused", "reason": "",
                                                          "reminded": 0, "limit": 5, "set_by": "user", "updated_by": "user",
                                                          "updated_at": "2026-11-25T00:00:00Z"}))
        name = self.letter(" /status ")
        self.run_cell("idle", 10)                                       # nothing for the brain: back to idle
        text = self.answered(name, "/status")
        self.assertIn("agent-fsm, model local, reasoning_effort high", text)
        self.assertIn("history %d messages" % len(OLD), text)            # counted before this exchange went in
        self.assertIn("goal paused: finish the report", text)
        self.assertIn("compact none; cooldown none; 0 more letters waiting", text)
        self.run_cell("brain", 10)                                      # the answer is the last message

    def test_status_shows_cooldown(self):
        reply_tests.cooldown.fail(str(self.stack), "BrainFailed", "upstream said no")
        name = self.letter("/status")
        self.run_cell("idle", 10)
        self.assertIn("cooldown cooling until ", self.answered(name, "/status"))

    def test_usage_sums_observed_rows(self):
        rows = [{"kind": "think", "endpoint": "sol", "usage": {"prompt_tokens": 100, "completion_tokens": 7, "details": {"x": 1}}},
                {"kind": "think", "endpoint": "sol", "usage": None},
                {"kind": "tool", "usage": {"prompt_tokens": 999}},
                {"kind": "think", "endpoint": "sol", "letter": "L2", "usage": {"prompt_tokens": 150, "completion_tokens": 3}}]
        (self.stack / "observed.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows) + "not json\n")
        name = self.letter("/usage")
        self.run_cell("idle", 10)
        text = self.answered(name, "/usage")
        self.assertIn("2 brain calls with usage in observed.jsonl: total completion_tokens 10, prompt_tokens 250", text)
        self.assertIn("last call (sol): completion_tokens 3, prompt_tokens 150", text)
        self.assertIn("no quota or rate limit to report", text)

    def test_usage_with_nothing_yet(self):
        name = self.letter("/usage")
        self.run_cell("idle", 10)
        text = self.answered(name, "/usage")
        self.assertIn("no brain call with usage in observed.jsonl yet", text)
        self.assertIn("context: no reading", text)

    def test_exit_stops_itself(self):
        log = self.root / "agent.jsonl"
        self.command("aos-agent", FAKE_AGENT)
        self.history(OLD)
        name = self.letter("/exit")
        self.run_cell("idle", 10, FAKE_AGENT_LOG=str(log), AOS_WS=str(self.root))
        calls = [json.loads(l) for l in log.read_text().splitlines()]
        self.assertEqual([c["argv"] for c in calls], [["ctl", "who"], ["ctl", "stop", "--target", "ann", "--no-wait"]])
        self.assertEqual({c["cwd"] for c in calls}, {str(self.root)})
        text = self.answered(name, "/exit")
        self.assertIn("ann stops at the end of this step", text)
        self.assertIn("aos-agent ctl start ann brings it back", text)

    def test_exit_that_cannot_stop_says_so(self):
        self.command("aos-agent", FAKE_AGENT)
        name = self.letter("/exit")
        self.run_cell("idle", 10, FAKE_AGENT_LOG=str(self.root / "agent.jsonl"), FAKE_AGENT_FAIL="1")
        self.assertEqual(self.answered(name, "/exit"),
                         "/exit: could not stop (aos-agent: error: DaemonMissing AOS_DAEMON is not set); still running")

    def test_with_more_words_is_a_plain_letter(self):
        for text in ("/status please", "/usage of memory", "/exit now"):
            with self.subTest(text=text):
                name = self.letter(text)
                self.run_cell("idle")
                self.assertEqual(self.history()[-1], {"role": "user", "content": text, "aos": {"letter": name}})

    def test_a_batch_of_its_own(self):
        a = self.letter("letter A")
        s = self.letter("/status")
        b = self.letter("letter B")
        self.run_cell("idle")                                           # A goes to the brain; /status and B wait in cur/
        self.assertEqual(self.history()[-1]["aos"], {"letter": a})
        self.assertEqual(self.cur(), sorted([s, b]))
        self.think({"role": "assistant", "content": "answer A"})
        (self.root / "sent.json").unlink()
        self.run_cell("idle", 10)                                       # /status alone; B still waits
        self.assertIn("1 more letter waiting", self.answered(s, "/status"))
        self.assertEqual(self.cur(), [b])
        self.run_cell("idle")
        self.assertEqual(self.history()[-1]["aos"], {"letter": b})


if __name__ == "__main__":
    unittest.main()
