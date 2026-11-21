# Verify the before_compact / after_compact hooks of agent-fsm's /compact (compact cut 4): block, instructions, a hook's summary, changing the summary, restore, broken hooks.
import json
import os
from pathlib import Path
import sys
import unittest
os.environ.setdefault("AOS_HOME", str(Path(__file__).resolve().parents[3]))   # 路徑規則一（11-17）：範本的格只經 AOS_HOME 找 lib，測試給它這份 proto8

import test_compact as compact_tests
import test_compact_clear as clear_tests
import test_reply_match as reply_tests

CELLS = reply_tests.CELLS
PROTO = reply_tests.PROTO
sys.dont_write_bytecode = True
sys.path[:0] = [str(CELLS), str(PROTO / "py")]
import compact
from aos import ws as aos_ws

OLD = compact_tests.OLD
CALL = reply_tests.CALL
PRELUDE = """import json, os, sys
ev = json.load(sys.stdin)
with open(%r, "a") as f:
    f.write(json.dumps(ev) + "\\n")
"""


class CompactHooks(unittest.TestCase):
    # the helpers of test_compact.Compact, borrowed (not inherited, so its tests do not run twice)
    command = compact_tests.Compact.command
    send = compact_tests.Compact.send
    letter = compact_tests.Compact.letter
    history = compact_tests.Compact.history
    letters = compact_tests.Compact.letters
    run_cell = compact_tests.Compact.run_cell
    request = compact_tests.Compact.request
    fold = compact_tests.Compact.fold
    removed = compact_tests.Compact.removed
    start_idle = compact_tests.Compact.start_idle
    start_mid = compact_tests.Compact.start_mid

    def setUp(self):
        compact_tests.Compact.setUp(self)
        self.log = self.root / "hooklog.jsonl"
        face = json.loads((self.defn / "interfaces.json").read_text())
        face["hookeds"] = "hookeds.json"
        (self.defn / "interfaces.json").write_text(json.dumps(face))

    def hook(self, name, event, body="", **entry):
        path = self.defn / (name + ".py")
        path.write_text("#!" + sys.executable + "\n" + PRELUDE % str(self.log) + body)
        path.chmod(0o755)
        table = json.loads((self.defn / "hookeds.json").read_text()) if (self.defn / "hookeds.json").exists() else {}
        table[name] = dict({"event": event, "handler": path.name, "timeout_ms": 10000}, **entry)
        (self.defn / "hookeds.json").write_text(json.dumps(table))

    def events(self, event=None):
        rows = [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []
        return [r for r in rows if event is None or r["event"] == event]

    # ---- before_compact
    def test_block_answers_and_folds_nothing(self):
        self.hook("gate", "before_compact", 'print("not now"); sys.exit(10)')
        self.hook("late", "before_compact")
        self.history(OLD)
        c = self.letter("/compact keep the files")
        self.run_cell("idle", 10)
        h = self.history()
        self.assertEqual(h[:6], OLD)
        self.assertEqual(len(h), 7)
        self.assertEqual(h[6]["content"], compact.BLOCKED % ("gate", ": not now"))
        self.assertEqual(h[6]["aos"], {"answer_to": [c], "compact": True, "skipped": True, "blocked": "gate"})
        self.assertEqual(aos_ws.answer_for(str(self.stack), c)[0], "answered")
        self.assertEqual(self.letters()["pending"], [])
        self.assertEqual(list((self.stack / "queue/cur").iterdir()), [])
        self.assertEqual(compact.state(str(self.stack))["phase"], "blocked")
        self.assertEqual(compact.state(str(self.stack))["hook"], "gate")
        ev, = self.events()                      # the hook after the blocking one does not run
        self.assertEqual({k: ev[k] for k in ("letters", "asked", "instructions", "mid_turn", "foldable", "clear", "summary", "restore")},
                         {"letters": [c], "asked": "keep the files", "instructions": "keep the files", "mid_turn": False,
                          "foldable": 6, "clear": True, "summary": None, "restore": None})
        self.assertEqual(self.removed(), [])
        self.run_cell("brain", 10)
        self.assertFalse((self.stack / "think/request.json").exists())

    def test_instructions_and_clear_false_change_the_request(self):
        self.hook("a_words", "before_compact", 'print(json.dumps({"instructions": ev["instructions"] + " / list every path"}))')
        self.hook("b_keep", "before_compact", 'print(json.dumps({"clear": False}))')
        rows = clear_tests.long_history(6)
        self.history(rows)
        self.letter("/compact be short")
        self.run_cell("idle")
        ask = self.history()[-1]["content"]
        self.assertTrue(ask.endswith(" Extra instructions: be short / list every path"), ask)
        self.assertNotIn("old tool outputs were replaced", ask)
        self.assertEqual(self.history()[:-1], rows)                        # clear false: nothing cleared
        self.assertEqual(self.removed(), [])
        first, second = self.events()
        self.assertEqual(second["instructions"], "be short / list every path")   # each sees what the earlier changed
        self.assertEqual(compact.state(str(self.stack))["by"], "brain")

    def test_hook_summary_folds_at_once_without_brain(self):
        self.hook("mine", "before_compact", 'print(json.dumps({"summary": "  my own summary  "}))')
        self.hook("tell", "after_compact")
        rows = clear_tests.long_history(6)
        self.history(rows)
        c = self.letter("/compact")
        self.run_cell("idle")
        h = self.history()
        self.assertEqual(len(h), 2)
        self.assertTrue(h[0]["content"].startswith("[aos] summary: lines 1-15, 15 messages. my own summary (Compacted"))
        self.assertEqual(h[1]["aos"], {"answer_to": [c], "compact": True})
        self.assertFalse((self.stack / "think/request.json").exists())
        self.assertEqual([r["op"] for r in self.removed()], ["compact"] * 15)   # not cleared first (no request to make smaller)
        self.assertEqual(self.removed()[-1]["message"]["content"].split(" Extra")[0], compact.ASK)
        st = compact.state(str(self.stack))
        self.assertEqual((st["phase"], st["by"], st["cleared"]), ("done", "mine", 0))
        ev, = self.events("after_compact")
        self.assertEqual({k: ev[k] for k in ("letters", "summary", "by", "mid_turn", "cleared", "restore")},
                         {"letters": [c], "summary": "my own summary", "by": "mine", "mid_turn": False, "cleared": 0, "restore": None})
        self.assertEqual(aos_ws.answer_for(str(self.stack), c)[0], "answered")
        self.assertIn("my own summary", (self.stack / "handoff.md").read_text())
        self.run_cell("brain", 10)

    # ---- after_compact
    def test_after_changes_summary_and_restore_goes_after_it(self):
        self.hook("a_before", "before_compact", 'print(json.dumps({"restore": "from before"}))')
        self.hook("b_after", "after_compact",
                  'print(json.dumps({"summary": ev["summary"].upper(), "restore": ev["restore"] + " + todo: ship it"}))')
        c = self.start_idle()
        self.run_cell("brain")
        self.run_cell("wait", 10)
        self.run_cell("wait", 11, FAKE_MESSAGE=json.dumps({"role": "assistant", "content": "the work summary"}))
        h = self.history()
        self.assertEqual(len(h), 3)
        self.assertIn("THE WORK SUMMARY", h[0]["content"])
        self.assertEqual(h[1], {"role": "user", "content": compact.RESTORED + "from before + todo: ship it"})
        self.assertEqual(h[2]["aos"], {"answer_to": [c], "compact": True})
        ev, = self.events("after_compact")
        self.assertEqual((ev["summary"], ev["by"], ev["restore"]), ("the work summary", "brain", "from before"))
        self.assertIn("THE WORK SUMMARY", (self.stack / "handoff.md").read_text())
        self.assertEqual(compact.state(str(self.stack))["restored_chars"], len("from before + todo: ship it"))
        self.run_cell("brain", 10)               # no extra brain call: the history ends with compact done
        b = self.letter("next question")         # task mode still finds the summary (and the restore row with it)
        self.run_cell("idle")
        self.run_cell("brain", 0, "--history", "task")
        sent = [m["content"] for m in self.request()["messages"]]
        self.assertEqual(sent, [h[0]["content"], h[1]["content"], h[2]["content"], "next question"])
        self.assertTrue(b)

    def test_restore_mid_turn_and_continue(self):
        self.hook("back", "after_compact", 'print(json.dumps({"restore": "goal: finish"}))')
        task, requested = self.start_mid()
        self.run_cell("wait", 10)
        self.run_cell("wait", 11, FAKE_MESSAGE=json.dumps({"role": "assistant", "content": "The work summary."}))
        h = self.history()
        self.assertEqual(h[1]["content"], compact.RESTORED + "goal: finish")
        self.assertEqual(h[-1]["content"], compact.CONTINUE)
        self.assertTrue(self.events("after_compact")[0]["mid_turn"])

    def test_mid_turn_hook_summary_folds_and_goes_on(self):
        self.hook("mine", "before_compact", 'print(json.dumps({"summary": "mid summary"}))')
        task, requested = self.start_mid()
        h = self.history()
        self.assertIn("mid summary", h[0]["content"])
        self.assertEqual(h[-1]["content"], compact.CONTINUE)
        self.assertIn("tools", self.request())                            # the same brain cell went on with the turn
        self.assertEqual(self.request()["messages"][-1]["content"], compact.CONTINUE)
        self.assertEqual(aos_ws.answer_for(str(self.stack), requested)[0], "answered")
        self.assertEqual(self.letters()["pending"], [task])

    def test_mid_turn_block_leaves_letters_for_idle(self):
        self.hook("gate", "before_compact", 'sys.exit(10 if ev["mid_turn"] else 0)')
        task, requested = self.start_mid()
        self.assertIn("tools", self.request())                            # the turn went on
        self.assertFalse(any(compact.is_ask(m) for m in self.history()))
        self.assertTrue((self.stack / "queue/cur" / requested).exists())
        self.assertEqual(compact.state(str(self.stack))["phase"], "blocked")
        self.run_cell("wait", 10)
        self.run_cell("wait", FAKE_MESSAGE=json.dumps({"role": "assistant", "content": "task done"}))
        self.run_cell("brain", 10)
        self.run_cell("idle")                                             # end of turn: idle asks before_compact again
        self.assertEqual([e["mid_turn"] for e in self.events()], [True, False])
        self.assertTrue(compact.is_ask(self.history()[-1]))
        self.assertEqual(compact.state(str(self.stack))["phase"], "asked")

    # ---- broken hooks and no hooks
    def test_broken_hooks_are_warnings_and_compact_goes_on(self):
        self.hook("a_crash", "before_compact", "sys.exit(3)")
        self.hook("b_badjson", "before_compact", 'print("not json")')
        self.hook("c_badtype", "before_compact", 'print(json.dumps({"summary": "   "}))')
        self.hook("d_slow", "before_compact", "import time; time.sleep(5)", timeout_ms=300)
        self.hook("e_after", "after_compact", 'print(json.dumps({"restore": 5}))')
        c = self.start_idle()
        h = self.history()
        self.assertTrue(compact.is_ask(h[-1]))
        self.assertTrue(h[-1]["content"].endswith(compact.ASK.split(". ")[-1]))   # no extra instructions
        r = self.run_cell("brain")
        self.run_cell("wait", 10)
        r2 = self.run_cell("wait", 11, FAKE_MESSAGE=json.dumps({"role": "assistant", "content": "The work summary."}))
        self.assertEqual(len(self.history()), 2)
        self.assertEqual(aos_ws.answer_for(str(self.stack), c)[0], "answered")
        self.assertIn("hook e_after (event after_compact) failed: restore in stdout must be a string or null", r2.stderr)
        self.assertEqual(len(self.events("before_compact")), 4)
        self.assertTrue(r)

    def test_broken_hook_warnings_reach_stderr(self):
        self.hook("a_crash", "before_compact", "sys.exit(3)")
        self.history(OLD)
        self.letter("/compact")
        r = self.run_cell("idle")
        self.assertIn("agent-fsm: warning: hook a_crash (event before_compact) failed: exited 3; going on without it", r.stderr)
        self.assertTrue(compact.is_ask(self.history()[-1]))

    def test_short_compact_fires_nothing_and_no_hooks_records_brain(self):
        self.hook("gate", "before_compact", "sys.exit(10)")
        self.history(OLD[:2])
        self.letter("/compact")
        self.run_cell("idle", 10)
        self.assertEqual(self.events(), [])
        self.assertEqual(self.history()[-1]["aos"]["skipped"], True)
        self.assertNotIn("blocked", self.history()[-1]["aos"])

    def test_off_in_stack_copy(self):
        self.hook("gate", "before_compact", "sys.exit(10)")
        (self.stack / "hookeds.json").write_text(json.dumps({"gate": None}))
        self.start_idle()
        self.assertEqual(self.events(), [])
        self.assertTrue(compact.is_ask(self.history()[-1]))


if __name__ == "__main__":
    unittest.main()
