"""context_use（各種腦的 context 用量讀法）與 context_wrap（on_clock handler）：讀 live.jsonl 最後答完那輪、子 agent 與壓縮前的不算、讀不到＝None；handler 過門檻寄收尾、答完且 queue 空才寄 /compact、壓完不重複、config 壞了報錯。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

PROTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROTO / "py"))
from aos.agentlib import context_use  # noqa: E402

ENTRY = PROTO / "py" / "tools" / "agent" / "context_wrap" / "_entry"


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


SID = "7d13c9a4-19e5-47bf-bde9-c20e0b6defb6"


def said(used, stop="end_turn", model="m", side=False, mid=None):
    """One assistant row of claude's own transcript (shape seen in claude 2.1.325)."""
    return {"type": "assistant", "isSidechain": side, "uuid": "u-%d" % used, "message": {
        "id": mid or "msg_%d" % used, "model": model, "stop_reason": stop, "usage": {
            "input_tokens": 1, "cache_creation_input_tokens": 2, "cache_read_input_tokens": used - 3, "output_tokens": 9}}}


BOUNDARY = {"type": "system", "subtype": "compact_boundary", "isSidechain": False}


class ClaudeTranscript(unittest.TestCase):   # 11-16 ok-small：畫面開著（互動 claude）不寫 live.jsonl，讀 claude 自己的 transcript
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stack = Path(self.tmp.name) / "st"
        self.cell = self.stack / "claude"
        self.cell.mkdir(parents=True)
        self.home = Path(self.tmp.name) / "claude-home"
        self.env = mock_env(CLAUDE_CONFIG_DIR=str(self.home))
        self.env.start()
        self.addCleanup(self.env.stop)

    def session(self, sid=SID):
        (self.cell / "session.txt").write_text(sid + "\n")

    def transcript(self, *events, linked=False):
        if linked:
            path = self.cell / "transcripts" / ("claude-%s.jsonl" % SID)
        else:
            path = self.home / "projects" / "-x-ws" / (SID + ".jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            for ev in events:
                f.write((ev if isinstance(ev, str) else json.dumps(ev)) + "\n")
        return path

    def live(self, *events):
        with open(self.cell / "live.jsonl", "a") as f:
            for ev in events:
                f.write(json.dumps(ev) + "\n")

    def read(self, window=None):
        return context_use.read(str(self.stack), window=window)

    def test_last_finished_turn_from_the_transcript(self):
        self.session()
        path = self.transcript({"type": "user"}, said(300), said(400, stop="tool_use"), said(900, side=True), said(500),
                               said(700, stop="tool_use"), said(800, stop=None), linked=True)
        u = self.read(window=1000)
        self.assertEqual((u["used"], u["percent"], u["turn"], u["source"]), (500, 50.0, "claude-transcript:msg_500", str(path)))
        self.assertEqual(self.read(window=1000)["turn"], u["turn"])          # same turn read twice = same id

    def test_window_from_old_live_results_and_the_account_folder(self):
        self.session()
        self.transcript(said(400, model="big"))                               # found under CLAUDE_CONFIG_DIR/projects/*/
        self.assertIsNone(self.read())                                        # no window known yet
        self.assertIn("set config.window", context_use.explain(str(self.stack)))
        self.live({"type": "result", "modelUsage": {"small": {"contextWindow": 500}, "big": {"contextWindow": 2000}}})
        self.assertEqual(self.read()["window"], 2000)
        self.assertEqual(self.read(window=800)["percent"], 50.0)              # config.window wins

    def test_compacted_means_none_and_no_fallback_to_live(self):
        self.session()
        self.live(assistant(900), result(n=1))                                # the old -p turn: 90%
        self.transcript(said(900), BOUNDARY, {"type": "user", "isCompactSummary": True})
        self.assertIsNone(self.read(window=1000))                             # not the 90% from before the compaction
        self.assertIn("no finished turn with usage since the last compaction", context_use.explain(str(self.stack), window=1000))
        self.transcript(said(120))
        self.assertEqual(self.read(window=1000)["used"], 120)

    def test_no_transcript_falls_back_to_live(self):
        self.live(assistant(350), result(n=1))
        self.assertTrue(self.read()["turn"].startswith("claude:"))           # no session.txt
        self.session()
        self.assertEqual(self.read()["used"], 350)                            # session.txt but no transcript file
        self.session("../../*")
        self.transcript(said(100))
        self.assertEqual(self.read()["used"], 350)                            # an id that is not a uuid is not globbed

    def test_bad_rows_are_skipped(self):
        self.session()
        bad = said(600)
        bad["message"]["usage"]["input_tokens"] = "x"
        empty = said(650)
        empty["message"]["usage"] = {"output_tokens": 5}
        self.transcript("not json", said(200), {"type": "assistant", "message": "x"}, bad, empty)
        self.assertEqual(self.read(window=1000)["used"], 200)                 # broken / empty usage rows skipped, the older one counts
        self.transcript(said(300))
        self.assertEqual(self.read(window=1000)["used"], 300)
        self.transcript(BOUNDARY, bad)
        self.assertIsNone(self.read(window=1000))                             # a bad row after a compaction is still nothing

    def test_sidechain_compaction_does_not_reset(self):
        self.session()
        self.transcript(said(400), dict(BOUNDARY, isSidechain=True))
        self.assertEqual(self.read(window=1000)["used"], 400)

    def test_reads_back_past_big_rows_and_block_edges(self):
        self.session()
        blob = json.dumps({"type": "api-request-blob", "body": "b" * 5000})
        self.transcript(said(100), BOUNDARY, said(420), *([blob] * 40))       # ~200 KB of rows after the finished turn
        with mock.patch.object(context_use, "TRANSCRIPT_BLOCK", 4096):        # rows cut by block edges
            self.assertEqual(self.read(window=1000)["used"], 420)
            with mock.patch.object(context_use, "TRANSCRIPT_SCAN", 8192):     # read-back cap reached = nothing
                self.assertIsNone(self.read(window=1000))
                self.assertIn("read back at most", context_use.explain(str(self.stack), window=1000))

    def test_unknown_model_takes_the_smallest_window_and_newest_file(self):
        self.session()
        self.transcript(said(400, model="other"))
        self.live({"type": "result", "modelUsage": {"small": {"contextWindow": 500}, "big": {"contextWindow": 2000}}})
        self.assertEqual(self.read()["window"], 500)                          # earlier rather than too late
        newer = self.home / "projects" / "-y-ws" / (SID + ".jsonl")
        newer.parent.mkdir(parents=True)
        newer.write_text(json.dumps(said(250, model="big")) + "\n")
        old = self.home / "projects" / "-x-ws" / (SID + ".jsonl")
        os.utime(old, (1, 1))
        self.assertEqual((self.read()["used"], self.read()["source"]), (250, str(newer)))


def mock_env(**values):
    from unittest import mock
    return mock.patch.dict(os.environ, values)


class FsmContextUse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stack = Path(self.tmp.name) / "stack"
        self.stack.mkdir()
        self.kernel = Path(self.tmp.name) / "kernel"
        self.kernel.mkdir()
        (self.stack / "think").mkdir()
        (self.stack / "think" / "brain_wait.json").write_text(json.dumps({"kernel": str(self.kernel)}))
        self.packs({"sol-high": {"context": 1000}})

    def packs(self, doc):
        (self.kernel / "endpoints.json").write_text(json.dumps(doc))

    def observed(self, usage, letter="turn-1", kind="think", endpoint="sol-high"):
        with open(self.stack / "observed.jsonl", "a") as f:
            f.write(json.dumps({"kind": kind, "letter": letter, "endpoint": endpoint, "usage": usage}) + "\n")

    def test_last_think_reading(self):
        self.observed({"prompt_tokens": 350, "completion_tokens": 999})
        got = context_use.read(str(self.stack))
        self.assertEqual(got, {"used": 350, "window": 1000, "percent": 35.0, "turn": "fsm:turn-1",
                               "source": str(self.stack / "observed.jsonl")})
        self.assertEqual(context_use.PROVIDERS[-1], context_use.from_fsm_observed)
        self.assertIn("35.0% (350 of 1000 tokens), turn fsm:turn-1", context_use.explain(str(self.stack)))

    def test_failed_and_compact_rows_do_not_change_reading(self):
        self.observed({"prompt_tokens": 350})
        self.observed(None, letter="failed")
        self.observed({"prompt_tokens": 1}, letter="summary", kind="compact")
        self.assertEqual(context_use.read(str(self.stack))["turn"], "fsm:turn-1")

    def test_anthropic_input_sum_and_prompt_priority(self):
        self.observed({"input_tokens": 100, "cache_read_input_tokens": 200, "cache_creation_input_tokens": 50})
        self.assertEqual(context_use.read(str(self.stack))["used"], 350)
        self.observed({"cache_read_input_tokens": 12})
        self.assertEqual(context_use.read(str(self.stack))["used"], 12)
        self.observed({"prompt_tokens": 5, "input_tokens": 1000})
        self.assertEqual(context_use.read(str(self.stack))["used"], 5)
        self.observed({"prompt_tokens": 0})
        self.assertEqual(context_use.read(str(self.stack))["used"], 0)

    def test_invalid_usage_and_letter_are_skipped(self):
        self.observed({"prompt_tokens": 350})
        for usage in ({}, {"completion_tokens": 1}, {"prompt_tokens": True}, {"prompt_tokens": -1},
                      {"prompt_tokens": "350"}, {"prompt_tokens": 1.5}, {"input_tokens": False},
                      {"input_tokens": -1}, {"prompt_tokens": None, "input_tokens": 999}):
            with self.subTest(usage=usage):
                self.observed(usage, letter="bad")
                self.assertEqual(context_use.read(str(self.stack))["turn"], "fsm:turn-1")
        for letter in (None, "", 3):
            self.observed({"prompt_tokens": 999}, letter=letter)
            self.assertEqual(context_use.read(str(self.stack))["turn"], "fsm:turn-1")

    def test_window_override_and_missing_pack_context(self):
        self.observed({"prompt_tokens": 350})
        self.assertEqual(context_use.read(str(self.stack), window=2000)["window"], 2000)
        for doc in ({"sol-high": {}}, {}, {"sol-high": {"context": True}},
                    {"sol-high": {"context": 0}}, {"sol-high": {"context": "1000"}}):
            with self.subTest(doc=doc):
                self.packs(doc)
                self.assertIsNone(context_use.read(str(self.stack)))
                why = context_use.explain(str(self.stack))
                self.assertIn("no reading: fsm: pack", why)
                self.assertIn("config.window", why)
                self.assertEqual(context_use.read(str(self.stack), window=2000)["window"], 2000)
        for window in (True, 0, -1, "1000", 1.5):
            self.assertIsNone(context_use.read(str(self.stack), window=window))

    def test_missing_wait_and_bad_rows_explain(self):
        self.assertEqual(context_use.explain(str(self.stack)), "no reading: no provider knows this stack")
        self.observed({"prompt_tokens": 5}, kind="compact")
        with open(self.stack / "observed.jsonl", "a") as f:
            f.write("broken json\n[]\n")
        self.assertIsNone(context_use.read(str(self.stack)))
        self.assertIn("no valid think row", context_use.explain(str(self.stack)))
        self.observed({"prompt_tokens": 350})
        (self.stack / "think" / "brain_wait.json").write_text("broken json")
        self.assertIsNone(context_use.read(str(self.stack)))
        self.assertIn("brain_wait.json", context_use.explain(str(self.stack)))
        self.assertEqual(context_use.read(str(self.stack), window=2000)["window"], 2000)

    def test_fsm_generic_and_claude_readers_still_win(self):
        self.observed({"prompt_tokens": 350})
        (self.stack / "claude").mkdir()
        (self.stack / "claude" / "live.jsonl").write_text(
            json.dumps(assistant(100)) + "\n" + json.dumps(result()) + "\n")
        self.assertTrue(context_use.read(str(self.stack), window=2000)["turn"].startswith("claude:"))
        (self.stack / "context_usage.json").write_text(json.dumps({"used": 30, "window": 100, "turn": "generic"}))
        got = context_use.read(str(self.stack), window=2000)
        self.assertEqual((got["used"], got["window"], got["turn"]), (30, 100, "generic"))

    def test_tail_skips_partial_first_line_but_keeps_small_first_line(self):
        self.observed({"prompt_tokens": 350})
        with open(self.stack / "observed.jsonl", "a") as f:
            f.write("x" * (context_use.OBSERVED_TAIL + 10) + "\n")
        self.assertIsNone(context_use.read(str(self.stack)))
        self.observed({"prompt_tokens": 450}, letter="tail")
        with open(self.stack / "observed.jsonl", "a") as f:
            f.write("bad final line\n")
        got = context_use.read(str(self.stack))
        self.assertEqual((got["used"], got["turn"]), (450, "fsm:tail"))


class ContextReading(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stack = Path(self.tmp.name)

    def reading(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        return subprocess.run([str(ENTRY), *args], env=env, text=True, capture_output=True, timeout=30)

    def test_reading_without_stack_env_or_state(self):
        (self.stack / "context_usage.json").write_text(json.dumps({"used": 350, "window": 1000, "turn": "t"}))
        before = sorted(str(p) for p in self.stack.rglob("*"))
        r = self.reading("--reading", str(self.stack))
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(len(r.stdout.splitlines()), 1)
        self.assertIn("35.0% (350 of 1000 tokens), turn t", r.stdout)
        self.assertEqual(before, sorted(str(p) for p in self.stack.rglob("*")))
        r = self.reading("--reading", str(self.stack / "absent"))
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout, "no reading: no provider knows this stack\n")

    def test_reading_fsm_window_override(self):
        (self.stack / "observed.jsonl").write_text(json.dumps(
            {"kind": "think", "letter": "t", "usage": {"prompt_tokens": 350}}) + "\n")
        r = self.reading("--reading", str(self.stack), "--window", "2000")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertIn("17.5% (350 of 2000 tokens), turn fsm:t", r.stdout)
        self.assertFalse((self.stack / "state.json").exists())

    def test_reading_arguments_bad(self):
        for args in (("--reading",), ("--reading", "--window"), ("--reading", str(self.stack), "extra"),
                     ("--reading", str(self.stack), "--other", "10"),
                     ("--reading", str(self.stack), "--window", "0"),
                     ("--reading", str(self.stack), "--window", "true"),
                     ("--reading", str(self.stack), "--window", "1.5"),
                     ("--reading", str(self.stack), "--window", "-1"),
                     ("--reading", str(self.stack), "--window", "10", "extra")):
            with self.subTest(args=args):
                r = self.reading(*args)
                self.assertEqual((r.returncode, r.stdout), (1, ""))
                self.assertTrue(r.stderr.startswith("context_wrap: error: ArgumentsBad"), r.stderr)


@unittest.skipUnless(shutil.which("aos-post"), "aos-post not on PATH")
class ContextWrap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stack = Path(os.path.realpath(self.tmp.name)) / "b"
        self.cell = self.stack / "hookeds" / "context_wrap"
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

    def test_round_from_the_transcript_with_config_window(self):   # 11-16 ok-small：畫面開著＝只有 transcript；視窗從 config.window
        (self.stack / "claude").mkdir(exist_ok=True)
        (self.stack / "claude" / "session.txt").write_text(SID + "\n")
        path = self.stack / "claude" / "transcripts" / ("claude-%s.jsonl" % SID)
        path.parent.mkdir()

        def said_turn(*events):
            with open(path, "a") as f:
                for ev in events:
                    f.write(json.dumps(ev) + "\n")
        cfg = {"percent": 50, "window": 1000}
        said_turn(said(400))
        self.fire(cfg)
        self.assertEqual(self.queued(), [])
        said_turn(said(600, stop="tool_use"))
        self.fire(cfg)
        self.assertEqual(self.queued(), [])                            # mid-turn rows do not count
        said_turn(said(650))
        self.fire(cfg)
        self.assertEqual(len(self.contents()), 1)
        self.answer_all()
        self.fire(cfg)
        self.assertEqual(self.contents(), ["/compact"])
        self.answer_all()
        said_turn(BOUNDARY)                                            # the screen compacted: no finished turn since
        self.fire(cfg)
        self.assertEqual(self.phase(), "compacted")
        self.fire(cfg)
        self.assertEqual((self.queued(), self.phase()), ([], "compacted"))
        said_turn(said(200))
        self.fire(cfg)
        self.assertEqual(self.phase(), "idle")

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

    def test_no_wrap_sends_only_compact_with_busy_queue(self):
        self.turn(500)
        subprocess.run(["aos-post", "init", str(self.stack / "queue")], check=True, capture_output=True)
        subprocess.run(["aos-post", "send", "--ordered", str(self.stack / "queue")],
                       input=json.dumps({"role": "user", "content": "busy"}),
                       text=True, check=True, capture_output=True)
        self.fire({"wrap": False})
        self.assertEqual(self.contents(), ["busy", "/compact"])
        self.assertEqual(self.phase(), "compacting")
        self.fire({"wrap": False})
        self.assertEqual(self.contents(), ["busy", "/compact"])
        self.answer_all()
        self.fire({"wrap": False})
        self.assertEqual(self.phase(), "compacted")
        self.turn(100)
        self.fire({"wrap": False})
        self.assertEqual(self.phase(), "idle")
        self.turn(400)
        self.fire({"wrap": False})
        self.assertEqual(self.contents(), ["/compact"])

    def test_fsm_handler_window_override(self):
        (self.stack / "observed.jsonl").write_text(json.dumps(
            {"kind": "think", "letter": "t1", "usage": {"prompt_tokens": 350}}) + "\n")
        self.fire({"wrap": False})
        self.assertEqual(self.contents(), [])
        self.fire({"wrap": False, "window": 1000})
        self.assertEqual(self.contents(), ["/compact"])
        self.assertEqual(self.phase(), "compacting")

    def test_invalid_wrap_and_window(self):
        for bad in ({"wrap": "no"}, {"wrap": 0}, {"wrap": None}, {"window": 0}, {"window": True},
                    {"window": -1}, {"window": "1000"}, {"window": 1.5}, {"window": None}):
            with self.subTest(config=bad):
                r = self.fire(bad, ok=False)
                self.assertEqual((r.returncode, r.stdout), (1, ""))
                self.assertTrue(r.stderr.startswith("context_wrap: error: ArgumentsBad"), r.stderr)
                self.assertFalse((self.cell / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
