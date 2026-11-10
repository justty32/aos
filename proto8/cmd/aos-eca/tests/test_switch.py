"""Test aos-eca-turn switching machines (new conversation + reseed record, no lost letter) and its failure cooldown, with fake CLIs."""
import contextlib
import io
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
REPO = HERE.parents[3]
TURN = REPO / "proto8" / "cmd" / "aos-eca" / "bin" / "aos-eca-turn"
sys.path.insert(0, str(REPO / "proto8" / "lib"))
from agent import cooldown  # noqa: E402

LOCAL_BIN = os.path.expanduser("~/.local/bin")


class Base(unittest.TestCase):
    kind = "claude"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="t3-switch-")
        self.addCleanup(self.tmp.cleanup)
        self.t = Path(self.tmp.name)
        self.bin = self.t / "bin"
        self.bin.mkdir()
        (self.bin / "claude").symlink_to(HERE / "fake_claude")
        (self.bin / "codex").symlink_to(HERE / "fake_codex")
        self.defn = self.t / "def"
        self.defn.mkdir()
        self.write_cfg({})
        self.ws = self.t / "ws"
        self.ws.mkdir()
        self.stack = self.t / "stack"
        self.stack.mkdir()
        self.home = self.t / "homeA"
        self.home.mkdir()
        self.log = self.t / "cli_log.jsonl"
        self.extra = {}
        subprocess.run(["aos-post", "init", str(self.stack / "queue")], env=self.env(), check=True,
                       capture_output=True)

    def write_cfg(self, more):
        cfg = {"kind": self.kind, "timeout_ms": 30000}
        cfg.update(more)
        (self.defn / "cli.json").write_text(json.dumps(cfg))

    @property
    def cell(self):
        return self.stack / self.kind

    def env(self, **more):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("AOS_", "FAKE_CLI_")) and k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME")}
        env.update(PATH="%s:%s:%s" % (self.bin, LOCAL_BIN, env.get("PATH", "")), HOME=str(self.home),
                   AOS_STACK=str(self.stack), AOS_WS=str(self.ws), FAKE_CLI_LOG=str(self.log),
                   PYTHONDONTWRITEBYTECODE="1")
        env.update(self.extra)
        env.update(more)
        return env

    def say(self, *texts):
        for text in texts:
            r = subprocess.run(["aos-post", "send", "--ordered", str(self.stack / "queue")],
                               input=json.dumps({"role": "user", "content": text}), env=self.env(),
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def turn(self, *flags, stdin=None, **env):
        return subprocess.run([str(TURN), "--on-empty", "idle", *flags, str(self.defn)] if "--one" not in flags
                              else [str(TURN), *flags, str(self.defn)],
                              input=stdin, env=self.env(**env), capture_output=True, text=True, timeout=60)

    def ok_turn(self, **env):
        r = self.turn(**env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def queue(self):
        return sorted(n for stage in ("new", "cur") for n in os.listdir(self.stack / "queue" / stage)
                      if not n.startswith("."))

    def history(self):
        p = self.stack / "history.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []

    def sid(self):
        p = self.cell / "session.txt"
        return p.read_text().strip() if p.exists() else ""

    def mark(self):
        return json.loads((self.cell / ".session_home").read_text())


class ClaudeSwitch(Base):
    def test_1_same_machine_resumes(self):
        self.say("hello")
        self.ok_turn()
        first = self.sid()
        self.assertTrue(first)
        self.say("again")
        self.ok_turn()
        self.assertEqual(self.sid(), first)
        c1, c2 = self.calls()
        self.assertIn("--session-id", c1["argv"])
        self.assertEqual(c2["argv"][c2["argv"].index("--resume") + 1], first)
        self.assertEqual(c2["stdin"], "again")
        self.assertEqual(self.mark(), {"session": first, "ws": os.path.realpath(self.ws),
                                       "home": os.path.realpath(self.home / ".claude")})
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant", "user", "assistant"])

    def check_new_with_record(self, old):
        new = self.sid()
        self.assertTrue(new and new != old)
        last = self.calls()[-1]
        self.assertIn("--session-id", last["argv"])
        self.assertNotIn("--resume", last["argv"])
        self.assertTrue(last["stdin"].startswith("[aos: this conversation continues in a new session"), last["stdin"])
        self.assertIn("--- record: 2 messages, 2 shown ---\n[user] hello\n[assistant] FAKE: hello\n--- end of record ---\n\nagain",
                      last["stdin"])
        self.assertEqual(self.queue(), [])
        self.assertEqual([m["content"] for m in self.history()][-2:], ["again", "FAKE: again"])
        self.assertEqual(len(self.history()), 4)
        self.assertEqual(self.mark()["session"], new)

    def test_2_marker_gone_and_no_transcript(self):
        self.say("hello")
        self.ok_turn()
        old = self.sid()
        (self.cell / ".session_home").unlink()
        self.home = self.t / "homeB"
        self.home.mkdir()
        self.say("again")
        self.ok_turn()
        self.check_new_with_record(old)

    def test_3_other_home_marker_kept(self):
        self.say("hello")
        self.ok_turn()
        old = self.sid()
        self.home = self.t / "homeB"
        self.home.mkdir()
        self.say("again")
        self.ok_turn()
        self.check_new_with_record(old)

    def test_3b_claude_config_dir_counts_as_home(self):
        self.say("hello")
        self.ok_turn()
        old = self.sid()
        self.extra["CLAUDE_CONFIG_DIR"] = str(self.t / "alt")
        self.say("again")
        self.ok_turn()
        self.check_new_with_record(old)
        self.assertEqual(self.mark()["home"], os.path.realpath(self.t / "alt"))

    def test_4_moved_workspace_new_conversation(self):
        self.say("hello")
        self.ok_turn()
        old = self.sid()
        moved = self.t / "ws2"
        self.ws.rename(moved)
        self.ws = moved
        self.say("again")
        self.ok_turn()
        self.check_new_with_record(old)

    def test_5_no_marker_but_transcript_here(self):
        self.say("hello")
        self.ok_turn()
        old = self.sid()
        (self.cell / ".session_home").unlink()
        self.say("again")
        self.ok_turn()
        self.assertEqual(self.sid(), old)
        last = self.calls()[-1]
        self.assertEqual(last["argv"][last["argv"].index("--resume") + 1], old)
        self.assertEqual(last["stdin"], "again")
        self.assertEqual(self.mark()["session"], old)

    def test_6_resume_fails_transcript_gone(self):
        self.say("hello")
        self.ok_turn()
        old = self.sid()
        for p in (self.home / ".claude" / "projects").glob("*/%s.jsonl" % old):
            p.unlink()
        self.say("lost")
        r = self.turn()
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-eca-turn: error: CliFailed", r.stderr)
        self.assertFalse((self.cell / "session.txt").exists())
        self.assertFalse((self.cell / ".session_home").exists())
        self.assertEqual(self.queue(), [])                       # that letter was taken (decision 5)
        self.assertEqual(self.history()[-1], {"role": "user", "content": "lost"})
        state, rec = cooldown.state(str(self.stack))
        self.assertEqual((state, rec["failures"], rec["dropped"]), ("cooling", 1, 1))
        self.make_due()
        self.say("next")
        self.ok_turn()
        last = self.calls()[-1]
        self.assertIn("--session-id", last["argv"])
        self.assertIn("[user] lost\n", last["stdin"])           # the unanswered one is in the record
        self.assertTrue(last["stdin"].endswith("\n\nnext"))
        self.assertTrue(self.sid() and self.sid() != old)

    def make_due(self):
        rec = json.loads(cooldown.path(str(self.stack)) and Path(cooldown.path(str(self.stack))).read_text())
        rec["until"] = cooldown.iso(time.time() - 5)
        Path(cooldown.path(str(self.stack))).write_text(json.dumps(rec))

    def test_8_cooldown(self):
        self.say("a1", "a2")
        r = self.turn(FAKE_CLI_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-eca-turn: error: CliFailed", r.stderr)
        self.assertIn("usage limit reached", r.stderr)
        rec = cooldown.read(str(self.stack))
        self.assertEqual((rec["failures"], rec["dropped"], rec["code"]), (1, 2, "CliFailed"))
        self.assertEqual(self.queue(), [])
        self.assertEqual(len(self.history()), 2)
        first_sid = self.sid()
        self.assertTrue(first_sid)                               # ⑩ the new conversation's id is written even though it failed
        # cooling: nothing is taken
        self.say("b1", "b2", "b3")
        before = (self.queue(), self.history())
        self.ok_turn()
        self.assertEqual((self.queue(), self.history()), before)
        self.assertEqual(len(self.queue()), 3)
        # due + failing: only the oldest is tried and lost
        self.make_due()
        r = self.turn(FAKE_CLI_FAIL="1")
        self.assertEqual(r.returncode, 1)
        rec = cooldown.read(str(self.stack))
        self.assertEqual((rec["failures"], rec["dropped"]), (2, 3))
        self.assertEqual(len(self.queue()), 2)
        self.assertEqual(self.history()[-1]["content"], "b1")
        # due + working: one letter, cooldown removed
        self.make_due()
        self.ok_turn()
        self.assertFalse(os.path.exists(cooldown.path(str(self.stack))))
        self.assertEqual(len(self.queue()), 1)
        self.assertEqual(self.history()[-2:], [{"role": "user", "content": "b2"},
                                               {"role": "assistant", "content": "FAKE: b2"}])
        # back to batches
        self.say("c1")
        self.ok_turn()
        self.assertEqual(self.queue(), [])
        self.assertEqual([m["content"] for m in self.history()][-3:], ["b3", "c1", "FAKE: c1"])
        self.assertEqual(self.calls()[-1]["stdin"], "b3\n\nc1")

    def test_8b_due_skips_bad_letter(self):
        self.say("w")
        self.ok_turn()                                           # an established conversation, then a failure while resuming
        self.say("x")
        self.turn(FAKE_CLI_FAIL="1")
        self.make_due()
        r = subprocess.run(["aos-post", "send", "--ordered", str(self.stack / "queue")], input='{"role": "user"}',
                           env=self.env(), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.say("good1", "good2")
        self.ok_turn()
        self.assertTrue((self.stack / "mailbox_warning.txt").exists())
        self.assertEqual(self.history()[-2:], [{"role": "user", "content": "good1"},
                                               {"role": "assistant", "content": "FAKE: good1"}])
        self.assertEqual(len(self.queue()), 1)

    def test_9_tool_form_warns(self):
        r = self.turn("--one", stdin='{"prompt": "hi"}')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        old = (self.stack / "session.txt").read_text().strip()
        self.home = self.t / "homeB"
        self.home.mkdir()
        r = self.turn("--one", stdin='{"prompt": "there"}')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "FAKE: there\n")
        self.assertEqual(r.stderr, "def: warning: the earlier conversation is not on this machine; "
                                   "starting a new one without its record\n")
        self.assertNotEqual((self.stack / "session.txt").read_text().strip(), old)
        self.assertEqual(self.calls()[-1]["stdin"], "there")
        self.assertFalse(os.path.exists(cooldown.path(str(self.stack))))

    def test_10_first_turn_fails_session_written(self):
        self.say("x")
        r = self.turn(FAKE_CLI_FAIL="1")
        self.assertEqual(r.returncode, 1)
        sid = self.sid()
        self.assertEqual(self.calls()[-1]["argv"][self.calls()[-1]["argv"].index("--session-id") + 1], sid)
        self.assertEqual(self.mark()["session"], sid)

    def test_cooling_untouched_cur(self):
        """A letter left in cur/ (an earlier yield) stays there while cooling."""
        self.say("x")
        self.turn(FAKE_CLI_FAIL="1")
        self.say("y")
        subprocess.run(["aos-post", "take", str(self.stack / "queue")], env=self.env(), capture_output=True)
        self.ok_turn()
        self.assertEqual(os.listdir(self.stack / "queue" / "cur") and len(os.listdir(self.stack / "queue" / "cur")), 1)

    def test_bad_reseed_bytes(self):
        self.write_cfg({"reseed_bytes": -1})
        self.say("x")
        r = self.turn()
        self.assertEqual(r.returncode, 1)
        self.assertIn("CfgBad", r.stderr)
        self.assertEqual(len(self.queue()), 1)


class CodexSwitch(Base):
    kind = "codex"

    def test_4_codex_moved_ws_still_resumes(self):
        self.say("hello")
        self.ok_turn()
        old = self.sid()
        self.assertTrue(old)
        moved = self.t / "ws2"
        self.ws.rename(moved)
        self.ws = moved
        self.say("again")
        self.ok_turn()
        self.assertEqual(self.sid(), old)
        last = self.calls()[-1]
        self.assertEqual(last["argv"][1:4], ["exec", "resume", old])
        self.assertEqual(last["stdin"], "again")

    def test_codex_other_home_new_with_record(self):
        self.say("hello")
        self.ok_turn()
        old = self.sid()
        self.extra["CODEX_HOME"] = str(self.t / "codexB")
        self.say("again")
        self.ok_turn()
        self.assertNotEqual(self.sid(), old)
        last = self.calls()[-1]
        self.assertNotIn("resume", last["argv"])
        self.assertTrue(last["stdin"].startswith("[aos:"))
        self.assertEqual(self.queue(), [])

    def test_11_thread_written_on_failure(self):
        self.say("x")
        r = self.turn(FAKE_CLI_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("CliFailed", r.stderr)
        self.assertTrue(self.sid())
        self.assertEqual(self.mark()["session"], self.sid())
        self.assertEqual(cooldown.read(str(self.stack))["dropped"], 1)

    def test_codex_resume_fails_thread_gone(self):
        self.say("hello")
        self.ok_turn()
        for p in (self.home / ".codex" / "sessions").rglob("*.jsonl"):
            p.unlink()
        self.say("lost")
        r = self.turn()
        self.assertEqual(r.returncode, 1)
        self.assertFalse((self.cell / "session.txt").exists())
        self.assertFalse((self.cell / ".session_home").exists())


class Reseed(unittest.TestCase):
    """⑦ the record builder itself (aos-eca-turn's reseed)."""

    @classmethod
    def setUpClass(cls):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("aos_eca_turn", str(TURN))
        spec = importlib.util.spec_from_loader("aos_eca_turn", loader)
        mod = importlib.util.module_from_spec(spec)
        argv = sys.argv
        sys.argv = [str(TURN), "--help"]                        # aos_flags.run(main) runs on import: --help exits 0
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                loader.exec_module(mod)
        except SystemExit:
            pass
        finally:
            sys.argv = argv
        cls.m = mod

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="t3-reseed-")
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name) / "ws"
        self.stack = self.ws / ".stack"
        self.stack.mkdir(parents=True)

    def rows(self, msgs):
        (self.stack / "history.jsonl").write_text("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in msgs))

    def reseed(self, limit):
        return self.m.reseed(str(self.stack), str(self.ws), limit)

    def test_empty_history(self):
        self.assertEqual(self.reseed(48000), "")

    def test_all_fit(self):
        self.rows([{"role": "user", "content": "task"}, {"role": "assistant", "content": "done"}])
        out = self.reseed(48000)
        self.assertIn("The complete record is the JSON-lines file .stack/history.jsonl.", out)
        self.assertTrue(out.endswith("--- record: 2 messages, 2 shown ---\n[user] task\n[assistant] done\n"
                                     "--- end of record ---\n\n"))

    def test_limit_first_kept_and_gap(self):
        msgs = [{"role": "user", "content": "FIRST"}] + [
            {"role": "user" if i % 2 else "assistant", "content": "m%03d " % i + "x" * 100} for i in range(1, 60)]
        self.rows(msgs)
        for limit in (1500, 3000, 6000):
            out = self.reseed(limit)
            self.assertLessEqual(len(out.encode()), limit)
            self.assertIn("[user] FIRST\n[... ", out)
            self.assertIn(" earlier messages left out ...]\n", out)
            self.assertIn("m059", out)                          # the newest is there
            shown = int(out.split(" shown ---")[0].rsplit(", ", 1)[1])
            left = int(out.split("[... ")[1].split(" earlier")[0])
            self.assertEqual(shown + left, 60)
            self.assertEqual(out.count("\n[user] ") + out.count("\n[assistant] "), shown)

    def test_long_message_head_and_tail(self):
        body = "H" * 4000 + "M" * 3000 + "T" * 2000
        self.rows([{"role": "user", "content": body}])
        out = self.reseed(48000)
        self.assertIn("[user] " + "H" * 4000 + "\n[... 3000 bytes left out ...]\n" + "T" * 2000 + "\n", out)

    def test_multibyte_not_broken(self):
        body = "字" * 4000                                       # 12000 bytes, 3 bytes per character
        self.rows([{"role": "user", "content": body}])
        out = self.reseed(48000)
        out.encode("utf-8").decode("utf-8")
        head = out.split("[user] ")[1].split("\n[... ")[0]
        tail = out.split(" bytes left out ...]\n")[1].split("\n--- end")[0]
        self.assertEqual(set(head + tail), {"字"})
        n = int(out.split("[... ")[1].split(" bytes")[0])
        self.assertEqual(len(head.encode()) + n + len(tail.encode()), 12000)
        self.assertLessEqual(len(head.encode()), 4000)
        self.assertLessEqual(len(tail.encode()), 2000)

    def test_zero_is_note_only(self):
        self.rows([{"role": "user", "content": "task"}])
        out = self.reseed(0)
        self.assertTrue(out.startswith("[aos:"))
        self.assertNotIn("--- record", out)
        self.assertIn(".stack/history.jsonl", out)
        self.assertTrue(out.endswith("]\n\n"))

    def test_note_bigger_than_limit(self):
        self.rows([{"role": "user", "content": "task"}])
        self.assertNotIn("--- record", self.reseed(100))

    def test_end_to_end_reseed_bytes_zero(self):
        """reseed_bytes 0 in cli.json reaches the CLI as the note only."""
        b = Base("run")
        b.setUp()
        try:
            b.write_cfg({"reseed_bytes": 0})
            b.say("hello")
            b.ok_turn()
            (b.cell / ".session_home").unlink()
            b.home = b.t / "homeB"
            b.home.mkdir()
            b.say("again")
            b.ok_turn()
            stdin = b.calls()[-1]["stdin"]
            self.assertTrue(stdin.startswith("[aos:"))
            self.assertNotIn("--- record", stdin)
            self.assertTrue(stdin.endswith("]\n\nagain"))
        finally:
            b.doCleanups()


class Screen(unittest.TestCase):
    """E: the screen path (start, live, hook) in-process, with tmux replaced by stubs."""

    def setUp(self):
        from unittest import mock
        from agent import cli_session
        self.cs = cli_session
        self.tmp = tempfile.TemporaryDirectory(prefix="t3-screen-")
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.ws, self.home = t / "ws", t / "home"
        self.ws.mkdir()
        self.home.mkdir()
        self.cell = cli_session.Cell(str(t / "cell"))
        for patcher in (mock.patch.dict(os.environ, {"HOME": str(self.home)}),
                        mock.patch.object(cli_session, "die", self.raise_die)):
            patcher.start()
            self.addCleanup(patcher.stop)
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        self.cfg = {"kind": "claude", "flags": [], "timeout_ms": 1000}
        self.mock = mock

    @staticmethod
    def raise_die(code, reason):
        raise RuntimeError(code)

    def test_start_drops_foreign_session(self):
        self.cell.write("session.txt", "old-id\n")
        self.cell.write(".session_home", json.dumps({"session": "old-id", "ws": "/elsewhere", "home": str(self.home)}))
        seen = []

        def tmux(*args, **kw):
            seen.append(args)
            raise FileNotFoundError("tmux")
        with self.mock.patch.object(self.cs.Cell, "alive", return_value=False), \
                self.mock.patch.object(self.cs.Cell, "tmux", side_effect=tmux):
            with self.assertRaises(RuntimeError):                # TmuxMissing after the decision
                self.cs.start(self.cfg, self.cell, str(self.ws), "")
        self.assertFalse(os.path.exists(self.cell.file("session.txt")))
        self.assertFalse(os.path.exists(self.cell.file(".session_home")))
        self.assertNotIn("--resume", seen[-1])

    def test_start_keeps_own_session(self):
        self.cs.mark_session("claude", self.cell, str(self.ws), "mine")
        seen = []

        def tmux(*args, **kw):
            seen.append(args)
            raise FileNotFoundError("tmux")
        with self.mock.patch.object(self.cs.Cell, "alive", return_value=False), \
                self.mock.patch.object(self.cs.Cell, "tmux", side_effect=tmux):
            with self.assertRaises(RuntimeError):
                self.cs.start(self.cfg, self.cell, str(self.ws), "")
        self.assertEqual(seen[-1][seen[-1].index("--resume") + 1], "mine")

    def test_live_new_conversation_gets_capped_reseed(self):
        got, limits = [], []

        def live(cfg, cell, prompt, on_busy, handed):
            got.append(prompt)
            return "ok"
        self.cfg["reseed_bytes"] = 48000
        with self.mock.patch.object(self.cs.Cell, "alive", return_value=True), \
                self.mock.patch.object(self.cs, "live", side_effect=live):
            self.cs.ask(self.cfg, self.cell, str(self.ws), str(self.ws), str(self.ws), "Q",
                        reseed=lambda n: limits.append(n) or "R\n\n")
            self.cell.write("session.txt", "s1\n")               # the hook wrote it after the first turn
            self.cs.ask(self.cfg, self.cell, str(self.ws), str(self.ws), str(self.ws), "Q2",
                        reseed=lambda n: limits.append(n) or "R\n\n")
        self.assertEqual(got, ["R\n\nQ", "Q2"])
        self.assertEqual(limits, [8000])

    def test_hook_writes_marker(self):
        self.cell.write("ws.txt", os.path.relpath(self.ws, self.cell.path) + "\n")
        payload = json.dumps({"hook_event_name": "Stop", "session_id": "hook-id", "last_assistant_message": "hi"})
        r = subprocess.run([sys.executable, str(REPO / "proto8" / "lib" / "agent" / "cli_session.py"), "hook", "claude",
                            self.cell.path], input=payload, capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cell.read("session.txt"), "hook-id")
        self.assertEqual(json.loads(self.cell.read(".session_home")),
                         {"session": "hook-id", "ws": os.path.realpath(self.ws), "home": os.path.realpath(self.home / ".claude")})


if __name__ == "__main__":
    unittest.main()
