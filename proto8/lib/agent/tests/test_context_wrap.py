"""context_use（各種腦的 context 用量讀法）與 context_wrap（on_clock handler）：讀 live.jsonl 最後答完那輪、子 agent 與壓縮前的不算、讀不到＝None；handler 過門檻寄收尾、答完且 queue 空才寄 /compact、壓完不重複、config 壞了報錯。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROTO / "lib" / "agent"))
import context_use  # noqa: E402

ENTRY = PROTO / "lib" / "agent" / "context_wrap" / "_entry"


def assistant(used, model="m", parent=None):
    return {"type": "assistant", "parent_tool_use_id": parent, "message": {"model": model, "usage": {
        "input_tokens": 1, "cache_creation_input_tokens": 2, "cache_read_input_tokens": used - 3, "output_tokens": 9}}}


def result(window=1000, model="m", n=0):
    return {"type": "result", "n": n, "result": "ok", "modelUsage": {model: {"contextWindow": window}}}


class ContextUse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stack = Path(self.tmp.name)

    def live(self, *events):
        (self.stack / "claude").mkdir(exist_ok=True)
        with open(self.stack / "claude" / "live.jsonl", "a") as f:
            for ev in events:
                f.write((ev if isinstance(ev, str) else json.dumps(ev)) + "\n")

    def test_nothing_to_read(self):
        self.assertIsNone(context_use.read(str(self.stack)))
        self.live({"type": "system"}, assistant(10))                   # a turn still running: no result yet
        self.assertIsNone(context_use.read(str(self.stack)))

    def test_last_finished_turn(self):
        self.live({"type": "system"}, assistant(100), result(n=1), {"type": "system"}, assistant(200), assistant(350),
                  assistant(900, model="sub", parent="toolu_1"), result(n=2), assistant(999))
        u = context_use.read(str(self.stack))
        self.assertEqual((u["used"], u["window"], u["percent"]), (350, 1000, 35.0))   # the sub-agent's and the unfinished one's do not count
        self.assertTrue(u["turn"].startswith("claude:"))
        self.assertEqual(context_use.read(str(self.stack))["turn"], u["turn"])

    def test_window_of_the_model_used(self):
        self.live(assistant(100, model="big"), {"type": "result", "modelUsage": {"small": {"contextWindow": 200}, "big": {"contextWindow": 1000}}})
        self.assertEqual(context_use.read(str(self.stack))["window"], 1000)

    def test_compact_turn_has_no_reading(self):
        self.live(assistant(800), result(n=1), {"type": "system", "subtype": "compact_boundary"}, result(n=2))
        self.assertIsNone(context_use.read(str(self.stack)))
        self.live(assistant(800), {"type": "system", "subtype": "compact_boundary"}, assistant(50), result(n=3))
        self.assertEqual(context_use.read(str(self.stack))["used"], 50)

    def test_bad_lines_and_no_window(self):
        self.live("not json", assistant(100), {"type": "result"})
        self.assertIsNone(context_use.read(str(self.stack)))

    def test_generic_file_comes_first(self):
        self.live(assistant(100), result())
        (self.stack / "context_usage.json").write_text(json.dumps({"used": 30, "window": 100, "turn": "t1"}))
        u = context_use.read(str(self.stack))
        self.assertEqual((u["used"], u["percent"], u["turn"]), (30, 30.0, "t1"))
        (self.stack / "context_usage.json").write_text(json.dumps({"used": "x", "window": 100}))
        self.assertEqual(context_use.read(str(self.stack))["used"], 100)   # a bad file = the next reader

    def test_codex_and_fsm_have_none(self):
        (self.stack / "codex").mkdir()
        (self.stack / "codex" / "live.jsonl").write_text(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 5}}) + "\n")
        self.assertIsNone(context_use.read(str(self.stack)))


@unittest.skipUnless(shutil.which("aos-post"), "aos-post not on PATH")
class ContextWrap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stack = Path(os.path.realpath(self.tmp.name)) / "b"
        self.cell = self.stack / "hooks" / "context_wrap"
        self.cell.mkdir(parents=True)
        self.n = 0

    def turn(self, used):
        self.n += 1
        (self.stack / "claude").mkdir(exist_ok=True)
        with open(self.stack / "claude" / "live.jsonl", "a") as f:
            for ev in (assistant(used), result(n=self.n)):
                f.write(json.dumps(ev) + "\n")

    def fire(self, config=None, ok=True):
        ev = {"event": "on_clock", "hook": "context_wrap", "stack": str(self.stack), "first": False}
        if config is not None:
            ev["config"] = config
        r = subprocess.run([str(ENTRY)], input=json.dumps(ev), text=True, capture_output=True, timeout=30,
                           env=dict(os.environ, AOS_STACK=str(self.cell)))
        if ok:
            self.assertEqual((r.returncode, r.stderr, r.stdout), (0, "", ""))
        return r

    def queued(self):
        box = self.stack / "queue" / "new"
        return sorted(box.iterdir()) if box.is_dir() else []

    def contents(self):
        return [json.loads((d / "letter.json").read_text())["body"]["content"] for d in self.queued()]

    def answer_all(self):
        names = [d.name for d in self.queued()]
        subprocess.run(["aos-post", "take-all", str(self.stack / "queue")], check=True, capture_output=True)
        for name in names:
            subprocess.run(["aos-post", "done", str(self.stack / "queue"), name], check=True, capture_output=True)

    def phase(self):
        return json.loads((self.cell / "state.json").read_text())["phase"]

    def test_round(self):
        self.fire()
        self.assertEqual(self.queued(), [])                            # no reading: nothing, no state
        self.assertFalse((self.cell / "state.json").exists())
        self.turn(340)
        self.fire()
        self.assertEqual(self.queued(), [])                            # 34% < 35%
        self.turn(350)
        self.fire()
        got = self.contents()
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].startswith("[aos] context_wrap: your context is 35% full (350 of 1000 tokens; the limit is 35%)"), got[0])
        self.fire()
        self.assertEqual(len(self.queued()), 1)                        # not answered yet: no /compact, no second wrap-up
        letter = self.queued()[0].name
        (self.stack / "letters.json").write_text(json.dumps({"pending": [letter], "dropped": []}))
        self.answer_all()                                              # handed over, answer not in yet
        self.fire()
        self.assertEqual(self.queued(), [])
        (self.stack / "letters.json").write_text(json.dumps({"pending": [], "dropped": []}))
        self.turn(360)
        self.fire()
        self.assertEqual(self.contents(), ["/compact"])
        self.assertEqual(self.phase(), "compacting")
        self.fire()
        self.assertEqual(len(self.queued()), 1)
        self.answer_all()
        self.fire()
        self.assertEqual(self.phase(), "compacted")
        self.turn(900)
        self.fire()
        self.assertEqual((self.queued(), self.phase()), ([], "compacted"))   # still over: no repeat
        self.turn(100)
        self.fire()
        self.assertEqual(self.phase(), "idle")
        self.turn(400)
        self.fire()
        self.assertEqual(len(self.contents()), 1)

    def test_compact_waits_for_an_empty_queue(self):
        self.turn(500)
        self.fire()
        self.answer_all()
        subprocess.run(["aos-post", "send", "--ordered", str(self.stack / "queue")], input=json.dumps({"role": "user", "content": "x"}),
                       text=True, check=True, capture_output=True)
        self.fire()
        self.assertEqual(self.contents(), ["x"])
        self.answer_all()
        self.fire()
        self.assertEqual(self.contents(), ["/compact"])

    def test_config(self):
        self.turn(200)
        self.fire({"percent": 20})
        self.assertEqual(len(self.queued()), 1)
        for bad in ({"percent": 0}, {"percent": "35"}, {"percent": 101}, [35]):
            r = self.fire(bad, ok=False)
            self.assertEqual(r.returncode, 1)
            self.assertTrue(r.stderr.startswith("context_wrap: error: ArgumentsBad"), r.stderr)

    def test_help(self):
        r = subprocess.run([str(ENTRY), "--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("/compact", r.stdout)


if __name__ == "__main__":
    unittest.main()
