"""Test aos-agent history on a fake daemon table (11-10 self-family): ls, rm, summarize, set, the kept originals (default, --keep, --no-keep), ranges and errors."""
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

MSGS = [{"role": "user", "content": "what time is it?"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
                                                              "function": {"name": "peek_now_time", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "10:00"},
        {"role": "assistant", "content": "It is 10:00.\nBye."},
        {"role": "user", "content": "thanks"}]


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return env


class History(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-history-"))
        self.d = self.tmp / "d"
        self.defn = self.tmp / "defs" / "bob"
        self.defn.mkdir(parents=True)
        self.decl({"aos-agent": {"history": "history.jsonl"}})
        (self.tmp / "ws").mkdir()
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps({"procs": {"bob": {
            "phase": "paused", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn)}}}))
        self.hist = self.stack / "history.jsonl"
        self.hist.write_text("".join(json.dumps(m) + "\n" for m in MSGS))
        self.removed = self.stack / "history_removed.jsonl"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def decl(self, d):
        (self.defn / "interfaces.json").write_text(json.dumps(d))

    def agent(self, *args, ok=True, stdin=None):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "history", "--target", "bob", *[str(a) for a in args]],
                           env=clean_env(), capture_output=True, text=True, timeout=60, cwd=self.tmp,
                           input=stdin if stdin is not None else "")
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def lines(self):
        return [json.loads(l) for l in self.hist.read_text().splitlines()]

    def kept(self, path=None):
        return [json.loads(l) for l in (path or self.removed).read_text().splitlines()]

    def test_ls_text_and_json(self):
        out = self.agent().stdout.splitlines()
        self.assertEqual(len(out), 5)
        self.assertEqual(out[1], "2\tassistant\t-> peek_now_time({})")
        self.assertEqual(out[2], "3\ttool\t(c1) 10:00")
        self.assertEqual(out[3], "4\tassistant\tIt is 10:00.\\nBye.")
        self.assertEqual(self.agent("ls", "4-").stdout.splitlines(), out[3:])
        rows = json.loads(self.agent("ls", "--json", "2").stdout)
        self.assertEqual(rows, [{"line": 2, "message": MSGS[1]}])

    def test_rm_keeps_originals_next_to_it(self):
        r = self.agent("rm", "2-3")
        self.assertIn("removed 2 messages from line 2", r.stdout)
        self.assertEqual(self.lines(), [MSGS[0], MSGS[3], MSGS[4]])
        kept = self.kept()
        self.assertEqual([(k["op"], k["line"], k["message"]) for k in kept], [("rm", 2, MSGS[1]), ("rm", 3, MSGS[2])])
        self.assertTrue(kept[0]["removed_at"].endswith("Z"))

    def test_summarize_open_range_from_stdin(self):
        r = self.agent("summarize", "--role", "assistant", "2-", "-", stdin="It was 10:00; the user said thanks.")
        self.assertIn("replaced 4 messages with one assistant message at line 2", r.stdout)
        self.assertEqual(self.lines(), [MSGS[0], {"role": "assistant", "content": "[aos] summary: lines 2-5, 4 messages. It was 10:00; the user said thanks."}])
        self.assertEqual(len(self.kept()), 4)

    def test_summarize_one_line_default_user(self):
        r = self.agent("summarize", "3", "asked the time")
        self.assertIn("replaced 1 message with one user message at line 3", r.stdout)
        self.assertEqual(self.lines()[2], {"role": "user", "content": "[aos] summary: line 3, 1 message. asked the time"})

    def test_set_any_line_and_keep_elsewhere(self):
        other = self.tmp / "elsewhere" / "old.jsonl"
        self.agent("set", "--keep", "elsewhere/old.jsonl", "5", '{"role": "user", "content": "thank you", "x": 1}')
        self.assertEqual(self.lines()[4], {"role": "user", "content": "thank you", "x": 1})
        self.assertEqual(self.kept(other)[0]["message"], MSGS[4])
        self.assertFalse(self.removed.exists())

    def test_no_keep_and_broken_line(self):
        with open(self.hist, "a") as f:
            f.write("not json\n")
        self.assertEqual(self.agent("ls", "6").stdout, "6\t?\tnot json\n")
        self.agent("rm", "--no-keep", "-y", "6")      # 讀不懂的行照樣能刪
        self.assertEqual(self.lines(), MSGS)
        self.assertFalse(self.removed.exists())

    def test_errors(self):
        before = self.hist.read_bytes()
        for args, code in ((("rm", "9"), "RangeBad"), (("rm", "3-2"), "RangeBad"), (("rm", "x"), "RangeBad"),
                           (("set", "2-3", "{}"), "RangeBad"), (("set", "2", "[1]"), "MessageBad"),
                           (("set", "2", "nope"), "MessageBad"), (("summarize", "2", " "), "ArgumentsBad"),
                           (("rm", "--keep", "a", "--no-keep", "1"), "ArgumentsBad"), (("rm", "-y", "1"), "ArgumentsBad"),
                           (("rm",), "ArgumentsBad"), (("bogus",), "CommandUnknown")):
            r = self.agent(*args, ok=False)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn("aos-agent: error: %s " % code, r.stderr, args)
        self.assertEqual(self.hist.read_bytes(), before)
        self.decl({"aos-agent": {}})
        self.assertIn("HistoryMissing", self.agent(ok=False).stderr)

    def test_empty_history(self):
        self.hist.unlink()
        self.assertEqual(self.agent().stdout, "")
        self.assertIn("the history is empty", self.agent("rm", "1", ok=False).stderr)


if __name__ == "__main__":
    unittest.main()
