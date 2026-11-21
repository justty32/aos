"""Test the pi kind of aos-eca-turn (11-18 eca-pi, plan B: one pi --mode rpc per batch, letters that come meanwhile steered in) with a fake pi CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
TURN = REPO / "proto8" / "bin" / "aos-eca-turn"                       # the entry install.py writes
sys.path.insert(0, str(REPO / "proto8" / "py"))
from aos.agentlib import cli_cell, cli_pi, context_use  # noqa: E402


class PiBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="t-pi-")
        self.addCleanup(self.tmp.cleanup)
        self.t = Path(self.tmp.name)
        self.bin = self.t / "bin"
        self.bin.mkdir()
        pi = self.bin / "pi"                                           # a wrapper: the fake needs no exec bit of its own
        pi.write_text('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, HERE / "fake_pi"))
        pi.chmod(0o755)
        self.defn = self.t / "def"
        self.defn.mkdir()
        self.write_cfg({})
        self.ws = self.t / "ws"
        self.ws.mkdir()
        self.stack = self.t / "stack"
        self.stack.mkdir()
        self.home = self.t / "home"
        self.home.mkdir()
        self.log = self.t / "cli_log.jsonl"
        subprocess.run(["aos-post", "init", str(self.stack / "queue")], env=self.env(), check=True, capture_output=True)

    def write_cfg(self, more):
        cfg = {"kind": "pi", "timeout_ms": 30000}
        cfg.update(more)
        (self.defn / "cli.json").write_text(json.dumps(cfg))

    @property
    def cell(self):
        return self.stack / "pi"

    def env(self, **more):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("AOS_", "FAKE_CLI_", "PI_"))}
        env.update(PATH="%s:%s" % (self.bin, env.get("PATH", "")), HOME=str(self.home),
                   AOS_STACK=str(self.stack), AOS_WS=str(self.ws), FAKE_CLI_LOG=str(self.log), PYTHONDONTWRITEBYTECODE="1")
        env.update(more)
        return env

    def say(self, *texts):
        for text in texts:
            r = subprocess.run(["aos-post", "send", "--ordered", str(self.stack / "queue")],
                               input=json.dumps({"role": "user", "content": text}), env=self.env(), capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def turn(self, **env):
        return subprocess.run([str(TURN), "--on-empty", "idle", str(self.defn)], env=self.env(**env),
                              capture_output=True, text=True, timeout=60)

    def ok_turn(self, **env):
        r = self.turn(**env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def history(self):
        p = self.stack / "history.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []

    def sid(self):
        p = self.cell / "session.txt"
        return p.read_text().strip() if p.exists() else ""

    def flag(self, call, name):
        a = call["argv"]
        return a[a.index(name) + 1]


class PiTurn(PiBase):
    def test_1_new_then_resume_same_id(self):
        self.say("hello")
        self.ok_turn()
        first = self.sid()
        self.assertTrue(first)
        self.say("again")
        self.ok_turn()
        self.assertEqual(self.sid(), first)
        c1, c2 = self.calls()
        for c in (c1, c2):
            self.assertEqual(self.flag(c, "--mode"), "rpc")
            self.assertIn("--no-approve", c["argv"])
            self.assertEqual(self.flag(c, "--session-dir"), str(self.cell / "pi-sessions"))
            self.assertEqual(self.flag(c, "--session-id"), first)
        self.assertEqual(json.loads(c2["stdin"][0]), {"type": "prompt", "message": "again", "id": "aos-1"})
        self.assertEqual([m["content"] for m in self.history()], ["hello", "FAKE PI: hello", "again", "FAKE PI: again"])
        mark = json.loads((self.cell / ".session_home").read_text())
        self.assertEqual(mark["home"], os.path.realpath(self.home / ".pi" / "agent"))
        self.assertEqual(mark["ws"], os.path.realpath(self.ws))
        self.assertEqual(len(cli_cell.transcripts("pi", first, str(self.cell))), 1)
        self.assertTrue((self.cell / "transcripts" / ("pi-%s.jsonl" % first)).is_symlink())
        self.assertIn('"agent_settled"', (self.cell / "live.jsonl").read_text())

    def test_2_error_answer_fails_and_drops_new_session(self):
        self.say("hello")
        r = self.turn(FAKE_CLI_FAIL="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("CliFailed", r.stderr)
        self.assertIn("connect timeout", r.stderr)
        self.assertEqual(self.sid(), "")                               # pi made no session file: the next message starts over

    def test_3_exit_127_names_node(self):
        self.say("hello")
        r = self.turn(FAKE_CLI_EXIT="127")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("node it runs on", r.stderr)

    def test_4_tools_go_in_through_the_extension(self):
        (self.defn / "tools.json").write_text(json.dumps({"tools": []}))
        self.say("hello")
        self.ok_turn()
        call = self.calls()[0]
        ext = self.flag(call, "-e")
        self.assertEqual(ext, str(self.cell / "pi-aos-mcp.mjs"))
        text = Path(ext).read_text()
        self.assertIn('pi.registerMcpServer("aos", ', text)
        server = json.loads(text.split('pi.registerMcpServer("aos", ', 1)[1].rsplit("); }", 1)[0])
        self.assertTrue(server["command"].endswith("/aos-mcp"))
        self.assertEqual(server["args"][:4], ["--ws", os.path.realpath(self.ws), "--stack", str(self.stack)])
        self.assertEqual(server["exposure"], "direct")
        self.assertEqual(server["env"]["AOS_STACK"], str(self.stack))

    def test_5_system_and_model(self):
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"system": "system.txt", "llm": "llm.json"}}))
        (self.defn / "system.txt").write_text("be short\n")
        (self.defn / "llm.json").write_text(json.dumps({"model": "openai-codex/gpt-5.5"}))
        self.say("hello")
        self.ok_turn()
        call = self.calls()[0]
        self.assertEqual(self.flag(call, "--append-system-prompt"), str(self.defn / "system.txt"))
        self.assertEqual(self.flag(call, "--model"), "openai-codex/gpt-5.5")

    def test_5b_reasoning_effort_is_thinking(self):
        """11-21 top-1121-ecaeffort: llm.json reasoning_effort = pi's --thinking; a level pi does not take is CfgBad before any letter is claimed."""
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"llm": "llm.json", "llm_keys": ["model", "reasoning_effort"]}}))
        (self.defn / "llm.json").write_text(json.dumps({"reasoning_effort": "minimal"}))
        self.say("hello")
        self.ok_turn()
        self.assertEqual(self.flag(self.calls()[0], "--thinking"), "minimal")
        (self.stack / "llm.json").write_text(json.dumps({"reasoning_effort": "none"}))
        self.say("again")
        r = self.turn()
        self.assertEqual(r.returncode, 1)
        self.assertIn("CfgBad", r.stderr)
        self.assertIn("--thinking takes: off, minimal", r.stderr)
        self.assertEqual(len(self.calls()), 1)

    def test_6_compact_replaces_history(self):
        self.say("hello")
        self.ok_turn()
        sid = self.sid()
        self.say("/compact keep the names")
        self.ok_turn()
        rpc = self.calls()[-1]
        self.assertEqual(self.flag(rpc, "--mode"), "rpc")
        self.assertEqual(json.loads(rpc["stdin"][0]), {"type": "compact", "id": "aos-compact", "customInstructions": "keep the names"})
        self.assertEqual(self.sid(), sid)
        rows = self.history()
        self.assertIn("FAKE SUMMARY", rows[0]["content"])
        self.assertIn("pi compacted conversation", rows[-1]["content"])

    def test_7_compact_refused_keeps_history(self):
        self.say("hello")
        self.ok_turn()
        self.say("/compact")
        self.ok_turn(FAKE_CLI_COMPACT_FAIL="1")
        rows = self.history()
        self.assertEqual(rows[0]["content"], "hello")
        self.assertIn("too small", rows[-1]["content"])

    def test_8_clear_starts_new_session(self):
        self.say("hello")
        self.ok_turn()
        first = self.sid()
        self.say("/clear")
        self.ok_turn()
        self.say("again")
        self.ok_turn()
        self.assertTrue(self.sid() and self.sid() != first)

    def test_9_letter_during_the_answer_is_steered_in(self):
        self.say("hello")
        p = subprocess.Popen([str(TURN), "--on-empty", "idle", str(self.defn)], env=self.env(FAKE_PI_DELAY="2"),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(0.8)
        self.say("second")
        out, err = p.communicate(timeout=60)
        self.assertEqual(p.returncode, 0, err)
        self.assertEqual([m["content"] for m in self.history()], ["hello", "second", "FAKE PI: hello\n\nFAKE PI: second"])
        (call,) = self.calls()
        sent = [json.loads(l) for l in call["stdin"]]
        self.assertEqual([c["type"] for c in sent], ["prompt", "steer"])
        self.assertEqual(sent[1]["message"], "second")
        self.assertEqual(list((self.stack / "queue" / "new").iterdir()), [])

    def test_10_live_mail_false_waits_for_the_next_turn(self):
        self.write_cfg({"live_mail": False})
        self.say("hello")
        p = subprocess.Popen([str(TURN), "--on-empty", "idle", str(self.defn)], env=self.env(FAKE_PI_DELAY="1.5"),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(0.6)
        self.say("second")
        p.communicate(timeout=60)
        self.assertEqual([m["content"] for m in self.history()], ["hello", "FAKE PI: hello"])
        self.ok_turn()
        self.assertEqual([m["content"] for m in self.history()][2:], ["second", "FAKE PI: second"])


class PiAnswer(unittest.TestCase):
    def test_segments(self):
        a = lambda text, stop="stop": {"role": "assistant", "stopReason": stop, "text": text}
        u = {"role": "user", "text": "q"}
        self.assertEqual(cli_pi.answer_of([u, a("", "toolUse"), a("one"), u, a("let me look", "toolUse"), a("two")]), "one\n\ntwo")
        self.assertEqual(cli_pi.answer_of([u, a("x", "toolUse"), u, a("both")]), "both")       # steered in before it said anything
        self.assertEqual(cli_pi.answer_of([u, a("half", "error")]), "")
        full = {"role": "assistant", "stopReason": "stop", "content": [{"type": "thinking"}, {"type": "text", "text": "hi"}]}
        self.assertEqual(cli_pi.answer_of([u, full]), "hi")


class PiCfg(PiBase):
    def bad(self, more, words):
        self.write_cfg(more)
        self.say("hello")
        r = self.turn()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("CfgBad", r.stderr)
        self.assertIn(words, r.stderr)
        self.assertEqual(self.calls(), [])

    def test_reserved_flags(self):
        self.bad({"flags": ["--session-id", "x"]}, "--session-id")
        self.bad({"flags": ["--approve"]}, "--approve")

    def test_external_mcp_not_yet(self):
        self.bad({"mcp_servers": []}, "mcp_servers is not supported for kind pi")


class PiUsage(unittest.TestCase):
    def test_reading_needs_window_and_resets_on_compaction(self):
        with tempfile.TemporaryDirectory() as d:
            live = Path(d) / "pi" / "live.jsonl"
            live.parent.mkdir()
            ok = {"type": "message_end", "message": {"role": "assistant", "stopReason": "stop",
                                                     "usage": {"input": 900, "cacheRead": 100, "cacheWrite": 0, "output": 5}}}
            err = {"type": "message_end", "message": {"role": "assistant", "stopReason": "error", "usage": {"input": 0}}}
            live.write_text(json.dumps(ok) + "\n" + json.dumps(err) + "\n")
            self.assertIsNone(context_use.read(d))
            self.assertIn("config.window", context_use.explain(d))
            got = context_use.read(d, window=4000)
            self.assertEqual((got["used"], got["window"]), (1000, 4000))
            with live.open("a") as f:
                f.write(json.dumps({"type": "compaction_end", "result": {"summary": "s"}}) + "\n")
            self.assertIsNone(context_use.read(d, window=4000))


if __name__ == "__main__":
    unittest.main()
