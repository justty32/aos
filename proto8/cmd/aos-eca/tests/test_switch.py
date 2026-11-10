"""Test aos-eca-turn switching machines (new conversation + reseed record, no lost letter) and its failure cooldown, with fake CLIs."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
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
from agent import cli_session, cooldown  # noqa: E402

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

    def make_due(self):
        rec = json.loads(cooldown.path(str(self.stack)) and Path(cooldown.path(str(self.stack))).read_text())
        rec["until"] = cooldown.iso(time.time() - 5)
        Path(cooldown.path(str(self.stack))).write_text(json.dumps(rec))


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
                                       "home": os.path.realpath(self.home / ".claude"),
                                       "machine": cli_session.machine_id()})
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant", "user", "assistant"])

    def check_new_with_record(self, old):
        new = self.sid()
        self.assertTrue(new and new != old)
        last = self.calls()[-1]
        self.assertIn("--session-id", last["argv"])
        self.assertNotIn("--resume", last["argv"])
        self.assertTrue(last["stdin"].startswith("[aos] session: this conversation continues in a new session"), last["stdin"])
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

    def test_6_transcript_gone_opens_new(self):
        # 11-10 stored_here: the CLI's own record of the conversation is gone (claude cleaned it up, or a first turn
        # was cut before claude saved it) = seen before handing over, so the next letter opens a new conversation
        # with the record instead of resuming into a failure (no letter lost).
        self.say("hello")
        self.ok_turn()
        old = self.sid()
        for p in (self.home / ".claude" / "projects").glob("*/%s.jsonl" % old):
            p.unlink()
        self.say("next")
        self.ok_turn()
        last = self.calls()[-1]
        self.assertIn("--session-id", last["argv"])
        self.assertNotIn("--resume", last["argv"])
        self.assertIn("[user] hello\n", last["stdin"])
        self.assertTrue(last["stdin"].endswith("\n\nnext"))
        self.assertTrue(self.sid() and self.sid() != old)
        self.assertEqual(self.queue(), [])
        self.assertEqual(cooldown.state(str(self.stack))[0], "none")

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
        self.assertFalse(self.sid())                             # TS 9: the CLI saved nothing, so the new id is dropped
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
        r = self.turn(FAKE_CLI_FAIL="1", FAKE_CLI_FAIL_SAVED="1")       # the CLI saved the conversation before failing
        self.assertEqual(r.returncode, 1)
        sid = self.sid()
        self.assertEqual(self.calls()[-1]["argv"][self.calls()[-1]["argv"].index("--session-id") + 1], sid)
        self.assertEqual(self.mark()["session"], sid)

    def test_ts9_first_turn_fails_nothing_saved(self):
        """TS 9: a new conversation fails on its first turn and the CLI saved nothing: both files go, the next turn starts new."""
        self.say("x")
        r = self.turn(FAKE_CLI_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-eca-turn: error: CliFailed", r.stderr)
        failed = self.calls()[-1]["argv"]
        self.assertIn("--session-id", failed)
        self.assertFalse((self.cell / "session.txt").exists())
        self.assertFalse((self.cell / ".session_home").exists())
        self.make_due()
        self.say("y")
        self.ok_turn()
        self.assertEqual(len(self.calls()), 2)                   # no wasted --resume of a conversation that never existed
        last = self.calls()[-1]["argv"]
        self.assertNotIn("--resume", last)
        self.assertNotEqual(last[last.index("--session-id") + 1], failed[failed.index("--session-id") + 1])
        self.assertEqual(self.history()[-1], {"role": "assistant", "content": "FAKE: y"})
        self.assertFalse(os.path.exists(cooldown.path(str(self.stack))))

    def test_ts8_other_machine_new_with_record(self):
        """TS 8: the marker names another machine (cp -a carried it over): new conversation with the record."""
        self.say("hello")
        self.ok_turn()
        old = self.sid()
        mark = self.mark()
        mark["machine"] = "some-other-machine"
        (self.cell / ".session_home").write_text(json.dumps(mark))
        self.say("again")
        self.ok_turn()
        self.check_new_with_record(old)
        self.assertEqual(self.mark()["machine"], cli_session.machine_id())

    def test_ts8_marker_without_machine_still_resumes(self):
        """TS 8: an older marker without the machine key is not compared on machine (gentle on running ecas)."""
        self.say("hello")
        self.ok_turn()
        old = self.sid()
        mark = self.mark()
        del mark["machine"]
        (self.cell / ".session_home").write_text(json.dumps(mark))
        self.say("again")
        self.ok_turn()
        self.assertEqual(self.sid(), old)
        last = self.calls()[-1]
        self.assertEqual(last["argv"][last["argv"].index("--resume") + 1], old)
        self.assertEqual(last["stdin"], "again")

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
        self.assertTrue(last["stdin"].startswith("[aos] session: "))
        self.assertEqual(self.queue(), [])

    def test_11_thread_written_on_failure(self):
        self.say("x")
        r = self.turn(FAKE_CLI_FAIL="1", FAKE_CLI_FAIL_SAVED="1")       # codex saved the thread before failing
        self.assertEqual(r.returncode, 1)
        self.assertIn("CliFailed", r.stderr)
        self.assertTrue(self.sid())
        self.assertEqual(self.mark()["session"], self.sid())
        self.assertEqual(cooldown.read(str(self.stack))["dropped"], 1)

    def test_ts9_codex_first_turn_fails_nothing_saved(self):
        """TS 9: thread.started came but codex saved no thread file: both files go, the next turn starts a new thread."""
        self.say("x")
        r = self.turn(FAKE_CLI_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertFalse((self.cell / "session.txt").exists())
        self.assertFalse((self.cell / ".session_home").exists())
        self.make_due()
        self.say("y")
        self.ok_turn()
        self.assertEqual(len(self.calls()), 2)
        self.assertNotIn("resume", self.calls()[-1]["argv"])
        self.assertTrue(self.sid())

    def test_codex_thread_gone_opens_new(self):
        self.say("hello")
        self.ok_turn()
        old = (self.cell / "session.txt").read_text().strip()
        for p in (self.home / ".codex" / "sessions").rglob("*.jsonl"):
            p.unlink()
        self.say("next")
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        new = (self.cell / "session.txt").read_text().strip()
        self.assertTrue(new and new != old)


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
        self.assertTrue(out.startswith("[aos] session: "))
        self.assertNotIn("--- record", out)
        self.assertIn(".stack/history.jsonl", out)
        self.assertTrue(out.endswith("The new message follows.\n\n"))

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
            self.assertTrue(stdin.startswith("[aos] session: "))
            self.assertNotIn("--- record", stdin)
            self.assertTrue(stdin.endswith("The new message follows.\n\nagain"))
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
        import re as _re
        saved = os.path.join(self.cs.account_dir("claude"), "projects",
                             _re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(str(self.ws))))
        os.makedirs(saved, exist_ok=True)
        open(os.path.join(saved, "mine.jsonl"), "w").close()            # the CLI saved this conversation here
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

    TRUST_SCREEN = """ Accessing workspace:
 /tmp/x/fresh
 Quick safety check: Is this a project you created or one you trust? (Like your own code, a well-known open source project, or work from your team). If not,
 take a moment to review what's in this folder first.
 Claude Code'll be able to read, edit, and execute files here.
 Security guide
 \u276f No, exit
   Yes, I trust this folder
 Enter to confirm \u00b7 Esc to cancel
"""

    def screen_tmux(self, screen, seen):
        def tmux(*args, **kw):
            seen.append(args[0])
            return subprocess.CompletedProcess(args, 0, screen if args[0] == "capture-pane" else "", "")
        return tmux

    def test_trust_prompt_not_typed(self):
        """11-10 late: claude waiting at its trust-this-folder menu = TrustMissing, nothing pasted (the default is No, exit)."""
        variants = [self.TRUST_SCREEN,
                    " Do you trust the files in this folder?\n\n \u276f 1. Yes, proceed\n   2. No, exit\n\n Enter to confirm \u00b7 Esc to exit\n",
                    " Do you TRUST this directory?\n > 1. Yes, trust it\n   2. No - exit\n"]
        for screen in variants:
            seen = []
            with self.mock.patch.object(self.cs.Cell, "tmux", side_effect=self.screen_tmux(screen, seen)), \
                    self.mock.patch.object(self.cs.Cell, "clients", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "TrustMissing"):
                    self.cs.live(self.cfg, self.cell, "Q")
            self.assertNotIn("load-buffer", seen, screen)
            self.assertNotIn("send-keys", seen)

    def test_ordinary_screen_still_typed(self):
        for screen in ("> I trust you, do not exit yet\n? for shortcuts\n", "", "\u276f 1. Yes\n  2. No, exit\n"):
            seen = []
            with self.mock.patch.object(self.cs.Cell, "tmux", side_effect=self.screen_tmux(screen, seen)), \
                    self.mock.patch.object(self.cs.Cell, "clients", return_value=[]), \
                    self.mock.patch.object(self.cs.Cell, "alive", return_value=True):
                with self.assertRaisesRegex(RuntimeError, "ReplyMissing"):        # pasted, the stub never answers
                    self.cs.live(dict(self.cfg, timeout_ms=300), self.cell, "Q")
            self.assertIn("load-buffer", seen, screen)
        self.assertFalse(self.cs.trust_prompt(self.TRUST_SCREEN.replace("trust", "know")))
        with self.mock.patch.object(self.cs.Cell, "tmux", side_effect=self.screen_tmux(self.TRUST_SCREEN, [])), \
                self.mock.patch.object(self.cs.Cell, "clients", return_value=[]), \
                self.mock.patch.object(self.cs.Cell, "alive", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "ReplyMissing"):            # codex: not checked
                self.cs.live(dict(self.cfg, kind="codex", timeout_ms=300), self.cell, "Q")

    def test_hook_writes_marker(self):
        self.cell.write("ws.txt", os.path.relpath(self.ws, self.cell.path) + "\n")
        payload = json.dumps({"hook_event_name": "Stop", "session_id": "hook-id", "last_assistant_message": "hi"})
        r = subprocess.run([sys.executable, str(REPO / "proto8" / "lib" / "agent" / "cli_session.py"), "hook", "claude",
                            self.cell.path], input=payload, capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cell.read("session.txt"), "hook-id")
        self.assertEqual(json.loads(self.cell.read(".session_home")),
                         {"session": "hook-id", "ws": os.path.realpath(self.ws), "home": os.path.realpath(self.home / ".claude"),
                          "machine": cli_session.machine_id()})

    def test_ts8_machine_id_falls_back_to_hostname(self):
        import socket
        with self.mock.patch.object(self.cs, "open", create=True, side_effect=OSError("no machine-id")):
            self.assertEqual(self.cs.machine_id(), socket.gethostname())
        self.assertTrue(self.cs.machine_id())


class TtySocket(unittest.TestCase):
    """TS 10: the screen's tmux socket lives under ${XDG_RUNTIME_DIR:-/tmp}/aos-tty-<uid>/, not in the cell."""

    def setUp(self):
        from unittest import mock
        import hashlib
        self.mock, self.cs = mock, cli_session
        self.tmp = tempfile.TemporaryDirectory(prefix="ts-tty-")
        self.addCleanup(self.tmp.cleanup)
        self.t = Path(self.tmp.name)
        self.xdg = self.t / "xdg"
        self.xdg.mkdir(mode=0o700)
        self.cell = cli_session.Cell(str(self.t / "stack" / "claude"))
        self.hash = hashlib.sha256(os.path.realpath(self.cell.path).encode()).hexdigest()[:16]
        for patcher in (mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(self.xdg)}),
                        mock.patch.object(cli_session, "die", Screen.raise_die)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dir = self.xdg / ("aos-tty-%d" % os.getuid())

    def test_path_and_length(self):
        sock = self.cs.tty_socket(self.cell.path)
        self.assertEqual(sock, str(self.dir / (self.hash + ".sock")))
        self.assertLess(len(sock.encode()), 108)
        self.assertFalse(self.dir.exists())                      # looking does not create anything
        self.assertEqual(self.cell.sock(), sock)

    def test_xdg_missing_or_unusable_falls_back_to_tmp(self):
        tmp_dir = "/tmp/aos-tty-%d" % os.getuid()
        for bad in (str(self.t / "nope"), "", "relative/dir", str(self.t / "file")):
            (self.t / "file").write_text("")
            with self.mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": bad}):
                self.assertEqual(self.cs.tty_socket(self.cell.path), os.path.join(tmp_dir, self.hash + ".sock"))
        with self.mock.patch.dict(os.environ):
            os.environ.pop("XDG_RUNTIME_DIR")
            self.assertEqual(self.cs.tty_socket(self.cell.path), os.path.join(tmp_dir, self.hash + ".sock"))

    def test_make_creates_0700_and_fixes_mode(self):
        sock = self.cs.tty_socket(self.cell.path, make=True)
        self.assertEqual(os.stat(self.dir).st_mode & 0o777, 0o700)
        self.assertEqual(os.path.dirname(sock), str(self.dir))
        os.chmod(self.dir, 0o755)
        self.cs.tty_socket(self.cell.path, make=True)
        self.assertEqual(os.stat(self.dir).st_mode & 0o777, 0o700)

    def test_make_refuses_symlinked_folder(self):
        other = self.t / "other"
        other.mkdir()
        os.symlink(other, self.dir)
        with self.assertRaises(RuntimeError) as e:
            self.cs.tty_socket(self.cell.path, make=True)
        self.assertEqual(str(e.exception), "CellBad")

    def test_moved_cell_other_hash(self):
        a = self.cs.tty_socket(self.cell.path)
        moved = self.t / "stack2"
        os.rename(self.t / "stack", moved)
        b = self.cs.tty_socket(str(moved / "claude"))
        self.assertNotEqual(a, b)

    def test_old_socket_in_cell_still_found(self):
        """A screen opened before TS 10 (socket in the cell) is still found; a new one never goes there."""
        import socket
        old = socket.socket(socket.AF_UNIX)
        self.addCleanup(old.close)
        old.bind(self.cell.file("tty.sock"))
        self.assertEqual(self.cs.tty_socket(self.cell.path), self.cell.file("tty.sock"))
        self.assertEqual(self.cs.tty_socket(self.cell.path, make=True), str(self.dir / (self.hash + ".sock")))

    @unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
    def test_real_tmux_screen_outside_the_cell(self):
        sock = self.cs.tty_socket(self.cell.path, make=True)
        self.addCleanup(subprocess.run, ["tmux", "-S", sock, "kill-server"], capture_output=True)
        self.assertFalse(self.cell.alive())
        r = self.cell.tmux("new-session", "-d", "-s", self.cs.TMUX_SESSION, "sleep 60", new=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.cell.alive())
        self.assertTrue(os.path.exists(sock))
        self.assertEqual(sorted(os.listdir(self.cell.path)), [])   # nothing made in the cell (no tty.sock)
        self.assertTrue(self.cs.close(self.cell))
        self.assertFalse(self.cell.alive())
        self.assertFalse(os.path.exists(sock))                   # close removes the socket file too
        self.assertEqual(subprocess.run(["tmux", "-S", sock, "has-session"], capture_output=True).returncode, 1)


if __name__ == "__main__":
    unittest.main()
