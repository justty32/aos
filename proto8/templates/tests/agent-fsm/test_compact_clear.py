# Verify that /compact clears old tool outputs into placeholders before asking for the summary (compact cut 1).
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock
os.environ.setdefault("AOS_HOME", str(Path(__file__).resolve().parents[3]))   # 路徑規則一（11-17）：範本的格只經 AOS_HOME 找 lib，測試給它這份 proto8

import test_compact as compact_tests
import test_reply_match as reply_tests

CELLS = reply_tests.CELLS
PROTO = reply_tests.PROTO
sys.dont_write_bytecode = True
sys.path[:0] = [str(CELLS), str(PROTO / "py")]
import compact
from aos import ws as aos_ws
from aos.agentlib import tool_clear

BIG = "x" * 1000


def call(n, name="echo"):
    return {"id": "c%d" % n, "type": "function", "function": {"name": name, "arguments": "{\"n\": %d}" % n}}


def turn(n, content=BIG, name="echo"):
    return [{"role": "assistant", "tool_calls": [call(n, name)]},
            {"role": "tool", "tool_call_id": "c%d" % n, "content": content}]


def long_history(count=6):
    rows = [{"role": "user", "content": "do the work"}]
    for n in range(1, count + 1):
        rows += turn(n)
    return rows + [{"role": "assistant", "content": "finished"}]


class ToolClear(unittest.TestCase):
    def test_keeps_last_three_short_and_placeholders(self):
        rows = long_history(6)
        rows[2] = dict(rows[2], content="short")                                    # c1: short, kept
        rows[4] = dict(rows[4], content=tool_clear.PLACEHOLDER % (5000, "echo") + " " * 400)   # c2: already cleared
        new, removed = tool_clear.clear(rows)
        self.assertEqual([r["tool_call_id"] for _, r in removed], ["c3"])           # c4-c6 are the last three
        self.assertEqual(new[6]["content"], tool_clear.PLACEHOLDER % (1000, "echo"))
        self.assertEqual(new[6]["tool_call_id"], "c3")
        self.assertEqual(rows[6]["content"], BIG)                                   # input untouched
        self.assertEqual([r for i, r in enumerate(new) if i != 6], [r for i, r in enumerate(rows) if i != 6])

    def test_last_group_is_kept_even_beyond_keep_last(self):
        rows = [{"role": "user", "content": "go"}] + turn(1) + turn(2)
        rows.append({"role": "assistant", "tool_calls": [call(3), call(4), call(5), call(6)]})
        rows += [{"role": "tool", "tool_call_id": "c%d" % n, "content": BIG} for n in (3, 4, 5, 6)]
        _, removed = tool_clear.clear(rows)
        self.assertEqual([r["tool_call_id"] for _, r in removed], ["c1", "c2"])

    def test_arguments_and_non_string_content_untouched(self):
        rows = long_history(5)
        rows[2] = dict(rows[2], content=[{"type": "text", "text": BIG}])
        new, removed = tool_clear.clear(rows, keep_last=0)
        self.assertEqual([r["tool_call_id"] for _, r in removed], ["c2", "c3", "c4"])   # c5 is the last group
        self.assertEqual([m.get("tool_calls") for m in new], [m.get("tool_calls") for m in rows])
        self.assertEqual(new[2], rows[2])

    def test_tool_name_in_placeholder(self):
        rows = [{"role": "user", "content": "go"}] + turn(1, name="json_get") + turn(2) + turn(3) + turn(4) + turn(5)
        new, _ = tool_clear.clear(rows)
        self.assertEqual(new[2]["content"], tool_clear.PLACEHOLDER % (1000, "json_get"))


class CompactClear(unittest.TestCase):
    setUp = compact_tests.Compact.setUp
    command = reply_tests.ReplyMatch.command
    send = reply_tests.ReplyMatch.send
    letter = reply_tests.ReplyMatch.letter
    history = reply_tests.ReplyMatch.history
    letters = reply_tests.ReplyMatch.letters
    run_cell = compact_tests.Compact.run_cell
    request = compact_tests.Compact.request
    removed = compact_tests.Compact.removed
    fold = compact_tests.Compact.fold

    def test_idle_clears_before_ask_and_fold_keeps_both_records(self):
        rows = long_history(6)
        self.history(rows)
        name = self.letter("/compact")
        self.run_cell("idle")
        h = self.history()
        self.assertEqual(len(h), len(rows) + 1)
        cleared = [m for m in h if m.get("role") == "tool" and tool_clear.is_placeholder(m["content"])]
        self.assertEqual([m["tool_call_id"] for m in cleared], ["c1", "c2", "c3"])
        self.assertEqual([m.get("tool_calls") for m in h[:-1]], [m.get("tool_calls") for m in rows])
        self.assertIn(compact.CLEARED % 3, h[-1]["content"])
        self.assertTrue(compact.is_ask(h[-1]))
        state = compact.state(str(self.stack))
        self.assertEqual((state["cleared"], state["cleared_chars"]), (3, 3000))
        rem = self.removed()
        self.assertEqual([(r["op"], r["line"], r["message"]["tool_call_id"]) for r in rem],
                         [("clear_tools", 3, "c1"), ("clear_tools", 5, "c2"), ("clear_tools", 7, "c3")])
        self.assertEqual(rem[0]["message"]["content"], BIG)
        self.run_cell("brain")
        sent = [m for m in self.request()["messages"] if m.get("role") == "tool"]
        self.assertEqual(sum(tool_clear.is_placeholder(m["content"]) for m in sent), 3)
        self.run_cell("wait", 10)
        self.run_cell("wait", 11, FAKE_MESSAGE=json.dumps({"role": "assistant", "content": "The work summary."}))
        self.assertEqual(len(self.history()), 2)
        self.assertEqual(self.history()[1]["aos"], {"answer_to": [name], "compact": True})
        state = compact.state(str(self.stack))
        self.assertEqual((state["phase"], state["cleared"], state["cleared_chars"]), ("done", 3, 3000))
        self.assertEqual([r["op"] for r in self.removed()].count("compact"), len(rows) + 1)

    def test_nothing_to_clear_keeps_old_request_text(self):
        self.history(compact_tests.OLD)
        self.letter("/compact")
        self.run_cell("idle")
        self.assertEqual(self.history()[:-1], compact_tests.OLD)
        self.assertNotIn("placeholder", self.history()[-1]["content"])
        self.assertEqual(compact.state(str(self.stack))["cleared"], 0)
        self.assertEqual(self.removed(), [])

    def test_mid_turn_keeps_last_group_and_continues(self):
        task = self.letter("Keep working")
        self.history(long_history(5)[:-1])
        self.run_cell("idle")
        rows = self.history() + turn(9)
        self.history(rows)
        self.letter("/compact")
        self.run_cell("brain")
        h = self.history()
        self.assertTrue(compact.state(str(self.stack))["mid_turn"])
        tools = {m["tool_call_id"]: m["content"] for m in h if m.get("role") == "tool"}
        self.assertEqual([k for k, v in tools.items() if tool_clear.is_placeholder(v)], ["c1", "c2", "c3"])
        self.assertEqual(tools["c9"], BIG)
        self.assertTrue(self.fold())
        self.assertEqual(self.history()[-1]["content"], compact.CONTINUE)
        self.assertEqual(self.letters()["pending"], [task])

    def test_history_changing_retries_then_gives_up_clearing(self):
        rows = long_history(6)
        self.history(rows)
        path = str(self.stack / "history.jsonl")
        warnings = []
        real = compact.fingerprint
        with mock.patch.object(compact, "fingerprint", side_effect=lambda p: (os.urandom(4), real(p))):
            self.assertEqual(compact.clear_old_tools(str(self.stack), path, warnings.append), (0, 0))
        self.assertEqual(warnings, ["compact: old tool outputs not cleared: history kept changing"])
        self.assertEqual(self.history(), rows)
        self.assertEqual(self.removed(), [])
        changed = iter([True])
        orig = compact.replace

        def once(*a):
            if next(changed, False):
                with open(path, "a") as f:
                    f.write(json.dumps({"role": "user", "content": "late letter"}) + "\n")
                return False
            return orig(*a)
        with mock.patch.object(compact, "replace", side_effect=once):
            self.assertEqual(compact.clear_old_tools(str(self.stack), path, warnings.append), (3, 3000))
        self.assertEqual(self.history()[-1]["content"], "late letter")
        self.assertEqual(len(self.removed()), 3)

    def test_bad_history_line_skips_clearing(self):
        path = self.stack / "history.jsonl"
        path.write_text("".join(json.dumps(m) + "\n" for m in long_history(6)) + "not json\n")
        warnings = []
        self.assertEqual(compact.clear_old_tools(str(self.stack), str(path), warnings.append), (0, 0))
        self.assertEqual(len(warnings), 1)
        self.assertTrue(path.read_text().endswith("not json\n"))

    def test_second_compact_does_not_clear_again(self):
        rows = long_history(6)
        self.history(rows)
        path = str(self.stack / "history.jsonl")
        self.assertEqual(compact.clear_old_tools(str(self.stack), path, print), (3, 3000))
        self.assertEqual(compact.clear_old_tools(str(self.stack), path, print), (0, 0))
        self.assertEqual(len(self.removed()), 3)
        self.assertEqual(aos_ws.letters_pending(str(self.stack)), [])


if __name__ == "__main__":
    unittest.main()
