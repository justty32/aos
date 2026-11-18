# Check aos_ws reply matching (reply-match-1114): answer_for's order queue -> history -> history_removed -> letters.json, the letters.json helpers, mark/for_endpoint, and that answers()/exchanges() (new and pre-change) read rows with aos keys the same way.
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(PROTO / "py"), str(PROTO / "py" / "tests" / "apps" / "agent")]
from aos import ws as aos_ws  # noqa: E402

L1, L2 = "000000000001.q", "000000000002.q"


class Stack(unittest.TestCase):
    def setUp(self):
        self.s = tempfile.mkdtemp(prefix="aos-ws-rm-")
        self.addCleanup(shutil.rmtree, self.s, True)
        for st in ("new", "cur", "archive"):
            os.makedirs(os.path.join(self.s, "queue", st))

    def rows(self, *rows):
        with open(os.path.join(self.s, "history.jsonl"), "a") as f:
            for m in rows:
                f.write(json.dumps(m) + "\n")

    def letter(self, stage, name):
        os.makedirs(os.path.join(self.s, "queue", stage, name))

    def write_letters(self, d):
        Path(self.s, aos_ws.LETTERS).write_text(json.dumps(d))

    # ---------------------------------------------------------------- answer_for

    def test_waiting_in_new_or_cur_first(self):
        self.letter("new", L1)
        self.letter("cur", L2)
        self.rows({"role": "assistant", "content": "x", "aos": {"answer_to": [L1, L2]}})   # queue wins: a letter in the queue is not answered yet
        self.assertEqual(aos_ws.answer_for(self.s, L1), ("waiting", ""))
        self.assertEqual(aos_ws.answer_for(self.s, L2), ("waiting", ""))

    def test_answered_first_answer_containing_it(self):
        self.letter("archive", L1)
        self.rows({"role": "user", "content": "q1", "aos": {"letter": L1}},
                  {"role": "assistant", "content": None, "tool_calls": [{"id": "1"}], "aos": {"answer_to": [L1]}},   # not a final answer
                  {"role": "assistant", "content": "first", "aos": {"answer_to": [L1, L2]}},
                  {"role": "assistant", "content": "second", "aos": {"answer_to": [L1]}})
        self.assertEqual(aos_ws.answer_for(self.s, L1), ("answered", "first"))
        self.assertEqual(aos_ws.answer_for(self.s, L2), ("answered", "first"))

    def test_answered_removed(self):
        self.rows({"role": "user", "content": "q", "aos": {"letter": L1}})
        Path(self.s, aos_ws.REMOVED).write_text("not json\n" + json.dumps({"removed_at": "t", "op": "rm", "line": 2, "message":
                                                {"role": "assistant", "content": "gone", "aos": {"answer_to": [L1]}}}) + "\n"
                                                + json.dumps({"removed_at": "t", "op": "rm", "line": 3, "raw": "x"}) + "\n")
        self.assertEqual(aos_ws.answer_for(self.s, L1), ("answered_removed", "gone"))

    def test_dropped_latest_record_wins_and_beats_pending(self):
        self.write_letters({"pending": [L1], "dropped": [{"letter": L1, "reason": "bad", "at": "t"}, {"letter": L1, "reason": "failed", "at": "t2"}]})
        self.assertEqual(aos_ws.answer_for(self.s, L1), ("dropped", "failed"))

    def test_handed_from_pending_or_letter_row(self):
        self.write_letters({"pending": [L1], "dropped": []})
        self.assertEqual(aos_ws.answer_for(self.s, L1), ("handed", ""))
        self.rows({"role": "user", "content": "q", "aos": {"letter": L2}})                 # pending already cleared by a crash-free rewrite: the row still says handed
        self.assertEqual(aos_ws.answer_for(self.s, L2), ("handed", ""))
        Path(self.s, aos_ws.REMOVED).write_text(json.dumps({"message": {"role": "user", "content": "q", "aos": {"letter": "L3"}}}) + "\n")
        self.assertEqual(aos_ws.answer_for(self.s, "L3"), ("handed", ""))

    def test_unknown_for_old_bodies_and_bad_names(self):
        self.rows({"role": "user", "content": "q"}, {"role": "assistant", "content": "a"})
        for name in (L1, "", "a/b", ".hidden"):
            self.assertEqual(aos_ws.answer_for(self.s, name), ("unknown", ""), name)

    # ---------------------------------------------------------------- letters.json

    def test_letters_missing_or_broken_is_empty(self):
        empty = {"pending": [], "dropped": []}
        self.assertEqual(aos_ws.letters(self.s), empty)
        for text in ("not json", "[1]", '{"pending": [1, null], "dropped": [1, {"reason": "bad"}]}',
                     '{"pending": "xyz", "dropped": "abc"}', '{"pending": {"a": 1}, "dropped": null}'):
            Path(self.s, aos_ws.LETTERS).write_text(text)
            self.assertEqual(aos_ws.letters(self.s), empty, text)

    def test_take_answer_drop(self):
        aos_ws.letters_take(self.s, [L1, L2, "", None])
        aos_ws.letters_take(self.s, [L1])                                                   # already pending: not twice
        aos_ws.letters_take(self.s, [L2, L2])                                               # same name twice in one call: once
        self.assertEqual(aos_ws.letters_pending(self.s), [L1, L2])
        aos_ws.letters_drop(self.s, [L2], "failed")
        d = aos_ws.letters(self.s)
        self.assertEqual(d["pending"], [L1])
        self.assertEqual([(x["letter"], x["reason"]) for x in d["dropped"]], [(L2, "failed")])
        aos_ws.letters_answered(self.s)
        self.assertEqual(aos_ws.letters_pending(self.s), [])
        with self.assertRaises(ValueError):
            aos_ws.letters_drop(self.s, [L1], "lost")
        aos_ws.letters_drop(self.s, ["n%d" % i for i in range(60)], "bad")
        d = aos_ws.letters(self.s)
        self.assertEqual(len(d["dropped"]), aos_ws.DROPPED_MAX)
        self.assertEqual(d["dropped"][-1]["letter"], "n59")
        self.assertEqual([n for n in os.listdir(self.s) if n.endswith(".tmp")], [])

    def test_answered_only_its_letters_and_retake_clears_dropped(self):
        aos_ws.letters_take(self.s, [L1, L2])
        aos_ws.letters_answered(self.s, [L2])                    # eca: only this turn's letters leave pending
        self.assertEqual(aos_ws.letters_pending(self.s), [L1])
        aos_ws.letters_answered(self.s)                          # fsm: None = the whole pending
        self.assertEqual(aos_ws.letters_pending(self.s), [])
        aos_ws.letters_drop(self.s, [L1], "failed")
        self.assertEqual(aos_ws.answer_for(self.s, L1), ("dropped", "failed"))
        aos_ws.letters_take(self.s, [L1])                        # handed again (it was still in cur/): no longer dropped
        self.assertEqual(aos_ws.answer_for(self.s, L1), ("handed", ""))
        self.assertEqual(aos_ws.letters(self.s)["dropped"], [])

    def test_mark_and_for_endpoint(self):
        forged = {"role": "user", "content": "q", "name": "bob", "aos": {"answer_to": ["x"]}}
        m = aos_ws.mark_letter(forged, L1)
        self.assertEqual(m, {"role": "user", "content": "q", "name": "bob", "aos": {"letter": L1}})
        self.assertEqual(forged["aos"], {"answer_to": ["x"]})                               # a copy
        self.assertEqual(aos_ws.mark_answer({"role": "assistant", "content": "a", "aos": {"letter": "y"}}, []), {"role": "assistant", "content": "a"})
        self.assertEqual(aos_ws.mark_answer({"role": "assistant", "content": "a"}, [L1, "", L2]),
                         {"role": "assistant", "content": "a", "aos": {"answer_to": [L1, L2]}})
        self.assertEqual(aos_ws.for_endpoint(m), {"role": "user", "content": "q", "name": "bob"})
        self.assertIn("aos", m)
        plain = {"role": "user", "content": "q"}
        self.assertIs(aos_ws.for_endpoint(plain), plain)

    # ---------------------------------------------------------------- new writer, old reader

    HIST = [({"role": "user", "content": "q1"}, {"letter": L1}),
            ({"role": "user", "content": "q2"}, {"letter": L2}),
            ({"role": "assistant", "content": None, "tool_calls": [{"id": "1"}]}, None),
            ({"role": "tool", "tool_call_id": "1", "content": "2"}, None),
            ({"role": "assistant", "content": "a12"}, {"answer_to": [L1, L2]}),
            ({"role": "user", "content": "[aos] summary: lines 1-2, 2 messages. x"}, None),
            ({"role": "assistant", "content": "a3"}, {"answer_to": ["L3"]})]

    def two_stacks(self):
        plain, marked = os.path.join(self.s, "plain"), os.path.join(self.s, "marked")
        for d, with_aos in ((plain, False), (marked, True)):
            os.makedirs(d)
            with open(os.path.join(d, "history.jsonl"), "w") as f:
                for m, a in self.HIST:
                    f.write(json.dumps(dict(m, aos=a) if with_aos and a else m) + "\n")
        Path(marked, aos_ws.LETTERS).write_text(json.dumps({"pending": [], "dropped": [{"letter": "L9", "reason": "bad", "at": "t"}]}))
        return plain, marked

    def test_answers_and_exchanges_ignore_aos(self):
        plain, marked = self.two_stacks()
        self.assertEqual(aos_ws.answers(marked), aos_ws.answers(plain))
        self.assertEqual(aos_ws.exchanges(marked), aos_ws.exchanges(plain))
        self.assertEqual(aos_ws.answers(plain), ["a12", "a3"])

    def test_pre_change_aos_ws_reads_the_same(self):
        import reply_fixture as rf
        base = rf.base_tree(self, "lib")
        plain, marked = self.two_stacks()
        code = ("import json, sys; sys.path[:0] = [sys.argv[1] + '/lib']; from aos import ws as aos_ws; "
                "print(json.dumps([[aos_ws.answers(s), aos_ws.exchanges(s)] for s in sys.argv[2:]]))")
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        r = subprocess.run([sys.executable, "-c", code, str(base), plain, marked], capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        got_plain, got_marked = json.loads(r.stdout)
        self.assertEqual(got_marked, got_plain)
        self.assertEqual(got_plain[0], ["a12", "a3"])


if __name__ == "__main__":
    unittest.main()
