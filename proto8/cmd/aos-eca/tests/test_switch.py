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
from agent import cli_ask, cli_base, cli_cell, cli_screen, cooldown  # noqa: E402

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
                                       "machine": cli_cell.machine_id()})
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
        self.assertEqual(self.mark()["machine"], cli_cell.machine_id())

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

    def test_external_server_not_connected_is_a_warning(self):
        """11-13: claude's init event says an external server of cli.json did not connect: one warning line, the turn goes on."""
        (self.defn / "demo.json").write_text(json.dumps({"description": "x", "mcp_server": {
            "name": "demo", "transport": "stdio", "command": "sh", "args": ["-c", "exit 0"]}}))
        self.write_cfg({"mcp_servers": ["demo.json"]})
        self.say("x")
        status = [{"name": "aos", "status": "connected"}, {"name": "demo", "status": "failed"}, {"name": "theirs", "status": "failed"}]
        r = self.ok_turn(FAKE_CLI_MCP=json.dumps(status))
        self.assertEqual([l for l in r.stderr.splitlines() if "MCP server" in l],
                         ["cli_session: warning: external MCP server demo was not connected when claude started (status failed)"])
        self.assertEqual(self.history()[-1]["content"], "FAKE: x")
        self.say("y")
        status[1]["status"] = "connected"
        self.assertNotIn("MCP server", self.ok_turn(FAKE_CLI_MCP=json.dumps(status)).stderr)

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

    def test_cfgbad_flag_keeps_the_letter(self):
        """11-13: print_flags repeats a flag aos adds itself: stopped before the letter is claimed, no cooldown, codex never called."""
        self.write_cfg({"print_flags": ["--skip-git-repo-check"]})
        self.say("x")
        r = self.turn()
        self.assertEqual(r.returncode, 1)
        self.assertIn("error: CfgBad", r.stderr)
        self.assertIn("print_flags has --skip-git-repo-check, which aos adds itself; remove it", r.stderr)
        self.assertEqual(len(os.listdir(self.stack / "queue" / "new")), 1)
        self.assertEqual(os.listdir(self.stack / "queue" / "cur"), [])
        self.assertIsNone(cooldown.read(str(self.stack)))
        self.assertEqual(self.calls(), [])
        self.write_cfg({})                                              # fixed: the same letter is answered
        self.ok_turn()
        self.assertEqual(self.calls()[-1]["stdin"], "x")
        self.assertEqual(self.queue(), [])

    def sub_thread(self, tid, parent):
        """A multi-agent sub-agent rollout as codex 0.167.2 writes its first line (11-13)."""
        d = self.home / ".codex" / "sessions" / "2026" / "11" / "10"
        d.mkdir(parents=True, exist_ok=True)
        (d / ("rollout-x-%s.jsonl" % tid)).write_text(json.dumps({"type": "session_meta", "payload": {
            "id": tid, "parent_thread_id": parent, "thread_source": "subagent",
            "source": {"subagent": {"thread_spawn": {"parent_thread_id": parent, "depth": 1}}}}}) + "\n")

    def test_session_on_a_subagent_thread_resumes_its_parent(self):
        """11-13: session.txt was left on a sub-agent thread (codex refuses to resume one): the turn goes to its parent."""
        self.say("hello")
        self.ok_turn()
        parent = self.sid()
        self.sub_thread("child", parent)
        self.sub_thread("grandchild", "child")
        (self.cell / "session.txt").write_text("grandchild\n")
        (self.cell / ".session_home").write_text(json.dumps(dict(self.mark(), session="grandchild")) + "\n")
        self.say("again")
        r = self.ok_turn()
        last = self.calls()[-1]
        self.assertEqual(last["argv"][1:4], ["exec", "resume", parent])
        self.assertEqual(last["stdin"], "again")
        self.assertEqual(self.sid(), parent)
        self.assertEqual(self.mark()["session"], parent)
        self.assertIn("warning: session.txt names a codex sub-agent thread grandchild; resuming its parent thread %s" % parent, r.stderr)
        self.assertEqual(self.queue(), [])
        self.assertIsNone(cooldown.read(str(self.stack)))

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
        self.tmp = tempfile.TemporaryDirectory(prefix="t3-screen-")
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.ws, self.home = t / "ws", t / "home"
        self.ws.mkdir()
        self.home.mkdir()
        self.cell = cli_cell.Cell(str(t / "cell"))
        for patcher in (mock.patch.dict(os.environ, {"HOME": str(self.home)}),
                        mock.patch.object(cli_base, "die", self.raise_die)):
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
        with self.mock.patch.object(cli_cell.Cell, "alive", return_value=False), \
                self.mock.patch.object(cli_cell.Cell, "tmux", side_effect=tmux):
            with self.assertRaises(RuntimeError):                # TmuxMissing after the decision
                cli_screen.start(self.cfg, self.cell, str(self.ws), "")
        self.assertFalse(os.path.exists(self.cell.file("session.txt")))
        self.assertFalse(os.path.exists(self.cell.file(".session_home")))
        self.assertNotIn("--resume", seen[-1])

    def test_start_keeps_own_session(self):
        cli_cell.mark_session("claude", self.cell, str(self.ws), "mine")
        import re as _re
        saved = os.path.join(cli_cell.account_dir("claude"), "projects",
                             _re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(str(self.ws))))
        os.makedirs(saved, exist_ok=True)
        open(os.path.join(saved, "mine.jsonl"), "w").close()            # the CLI saved this conversation here
        seen = []

        def tmux(*args, **kw):
            seen.append(args)
            raise FileNotFoundError("tmux")
        with self.mock.patch.object(cli_cell.Cell, "alive", return_value=False), \
                self.mock.patch.object(cli_cell.Cell, "tmux", side_effect=tmux):
            with self.assertRaises(RuntimeError):
                cli_screen.start(self.cfg, self.cell, str(self.ws), "")
        self.assertEqual(seen[-1][seen[-1].index("--resume") + 1], "mine")

    def test_live_new_conversation_gets_capped_reseed(self):
        got, limits = [], []

        def live(cfg, cell, prompt, on_busy, handed, *rest):
            got.append(prompt)
            return "ok"
        self.cfg["reseed_bytes"] = 48000
        with self.mock.patch.object(cli_cell.Cell, "alive", return_value=True), \
                self.mock.patch.object(cli_ask, "live", side_effect=live):
            cli_ask.ask(self.cfg, self.cell, str(self.ws), str(self.ws), str(self.ws), "Q",
                        reseed=lambda n: limits.append(n) or "R\n\n")
            self.cell.write("session.txt", "s1\n")               # the hook wrote it after the first turn
            cli_ask.ask(self.cfg, self.cell, str(self.ws), str(self.ws), str(self.ws), "Q2",
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
            with self.mock.patch.object(cli_cell.Cell, "tmux", side_effect=self.screen_tmux(screen, seen)), \
                    self.mock.patch.object(cli_cell.Cell, "clients", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "TrustMissing"):
                    cli_ask.live(self.cfg, self.cell, "Q")
            self.assertNotIn("load-buffer", seen, screen)
            self.assertNotIn("send-keys", seen)

    def test_ordinary_screen_still_typed(self):
        for screen in ("> I trust you, do not exit yet\n? for shortcuts\n", "", "\u276f 1. Yes\n  2. No, exit\n"):
            seen = []
            with self.mock.patch.object(cli_cell.Cell, "tmux", side_effect=self.screen_tmux(screen, seen)), \
                    self.mock.patch.object(cli_cell.Cell, "clients", return_value=[]), \
                    self.mock.patch.object(cli_cell.Cell, "alive", return_value=True):
                with self.assertRaisesRegex(RuntimeError, "ReplyMissing"):        # pasted, the stub never answers
                    cli_ask.live(dict(self.cfg, timeout_ms=300), self.cell, "Q")
            self.assertIn("load-buffer", seen, screen)
        self.assertFalse(cli_ask.trust_prompt(self.TRUST_SCREEN.replace("trust", "know")))
        with self.mock.patch.object(cli_cell.Cell, "tmux", side_effect=self.screen_tmux(self.TRUST_SCREEN, [])), \
                self.mock.patch.object(cli_cell.Cell, "clients", return_value=[]), \
                self.mock.patch.object(cli_cell.Cell, "alive", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "ReplyMissing"):            # codex: not checked
                cli_ask.live(dict(self.cfg, kind="codex", timeout_ms=300), self.cell, "Q")

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
                          "machine": cli_cell.machine_id()})

    def test_ts8_machine_id_falls_back_to_hostname(self):
        import socket
        with self.mock.patch.object(cli_cell, "open", create=True, side_effect=OSError("no machine-id")):
            self.assertEqual(cli_cell.machine_id(), socket.gethostname())
        self.assertTrue(cli_cell.machine_id())


class ScreenClose(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import runpy
        cls.screen = runpy.run_path(str(TURN.with_name("aos-eca-screen")))

    def setUp(self):
        from unittest import mock
        self.mock = mock
        self.tmp = tempfile.TemporaryDirectory(prefix="screen-close-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.defn = self.root / "def"
        self.defn.mkdir()
        self.stack = self.root / "stack"
        (self.stack / "claude").mkdir(parents=True)
        self.closed = []

    def close_screen(self):
        out, err = io.StringIO(), io.StringIO()
        code = 0
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env["AOS_STACK"] = str(self.stack)
        def close(cell):
            self.closed.append(Path(cell.path).name)
            return True
        with self.mock.patch.dict(os.environ, env, clear=True), \
                self.mock.patch.object(sys, "argv", ["aos-eca-screen", "--eca", str(self.defn), "close"]), \
                self.mock.patch.object(cli_cell, "close", side_effect=close), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                self.screen["main"]()
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def test_close_with_invalid_cli_json_still_closes(self):
        (self.defn / "cli.json").write_text(json.dumps({
            "kind": "claude", "print_flags": ["--output-format", "json"]}))
        code, out, err = self.close_screen()
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "closed\n")
        self.assertEqual(self.closed, ["claude"])
        self.assertEqual(len(err.splitlines()), 1)
        self.assertTrue(err.startswith("aos-eca-screen: warning: cli.json of %s is not valid (CfgBad " % self.defn), err)
        self.assertIn("print_flags has --output-format", err)
        self.assertTrue(err.endswith("; closing the screen by its kind only\n"), err)
        self.assertFalse((self.stack / "codex").exists())

    def test_close_without_usable_kind_closes_existing_known_cells(self):
        (self.stack / "codex").mkdir()
        for contents in ("{bad", "{}", '{"kind": ""}'):
            with self.subTest(contents=contents):
                self.closed.clear()
                (self.defn / "cli.json").write_text(contents)
                code, out, err = self.close_screen()
                self.assertEqual(code, 0, err)
                self.assertEqual(out, "closed\n")
                self.assertCountEqual(self.closed, ["claude", "codex"])
                self.assertEqual(len(err.splitlines()), 1)
                self.assertIn("aos-eca-screen: warning:", err)

    def test_close_with_missing_cli_json_closes_existing_cell(self):
        code, out, err = self.close_screen()
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "closed\n")
        self.assertEqual(self.closed, ["claude"])
        self.assertEqual(len(err.splitlines()), 1)
        self.assertIn("CfgMissing", err)
        self.assertFalse((self.stack / "codex").exists())

    def test_close_with_invalid_cli_json_still_refuses_busy_cell(self):
        (self.defn / "cli.json").write_text(json.dumps({
            "kind": "claude", "print_flags": ["--output-format", "json"]}))
        with (self.stack / "claude" / "lock").open("w") as lock:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, out, err = self.close_screen()
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertEqual(self.closed, [])
        self.assertIn("aos-eca-screen: error: SessionBad busy answering", err)


class TtySocket(unittest.TestCase):
    """TS 10: the screen's tmux socket lives under ${XDG_RUNTIME_DIR:-/tmp}/aos-tty-<uid>/, not in the cell."""

    def setUp(self):
        from unittest import mock
        import hashlib
        self.mock = mock
        self.tmp = tempfile.TemporaryDirectory(prefix="ts-tty-")
        self.addCleanup(self.tmp.cleanup)
        self.t = Path(self.tmp.name)
        self.xdg = self.t / "xdg"
        self.xdg.mkdir(mode=0o700)
        self.cell = cli_cell.Cell(str(self.t / "stack" / "claude"))
        self.hash = hashlib.sha256(os.path.realpath(self.cell.path).encode()).hexdigest()[:16]
        for patcher in (mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(self.xdg)}),
                        mock.patch.object(cli_base, "die", Screen.raise_die)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dir = self.xdg / ("aos-tty-%d" % os.getuid())

    def test_path_and_length(self):
        sock = cli_cell.tty_socket(self.cell.path)
        self.assertEqual(sock, str(self.dir / (self.hash + ".sock")))
        self.assertLess(len(sock.encode()), 108)
        self.assertFalse(self.dir.exists())                      # looking does not create anything
        self.assertEqual(self.cell.sock(), sock)

    def test_xdg_missing_or_unusable_falls_back_to_tmp(self):
        tmp_dir = "/tmp/aos-tty-%d" % os.getuid()
        for bad in (str(self.t / "nope"), "", "relative/dir", str(self.t / "file")):
            (self.t / "file").write_text("")
            with self.mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": bad}):
                self.assertEqual(cli_cell.tty_socket(self.cell.path), os.path.join(tmp_dir, self.hash + ".sock"))
        with self.mock.patch.dict(os.environ):
            os.environ.pop("XDG_RUNTIME_DIR")
            self.assertEqual(cli_cell.tty_socket(self.cell.path), os.path.join(tmp_dir, self.hash + ".sock"))

    def test_make_creates_0700_and_fixes_mode(self):
        sock = cli_cell.tty_socket(self.cell.path, make=True)
        self.assertEqual(os.stat(self.dir).st_mode & 0o777, 0o700)
        self.assertEqual(os.path.dirname(sock), str(self.dir))
        os.chmod(self.dir, 0o755)
        cli_cell.tty_socket(self.cell.path, make=True)
        self.assertEqual(os.stat(self.dir).st_mode & 0o777, 0o700)

    def test_make_refuses_symlinked_folder(self):
        other = self.t / "other"
        other.mkdir()
        os.symlink(other, self.dir)
        with self.assertRaises(RuntimeError) as e:
            cli_cell.tty_socket(self.cell.path, make=True)
        self.assertEqual(str(e.exception), "CellBad")

    def test_moved_cell_other_hash(self):
        a = cli_cell.tty_socket(self.cell.path)
        moved = self.t / "stack2"
        os.rename(self.t / "stack", moved)
        b = cli_cell.tty_socket(str(moved / "claude"))
        self.assertNotEqual(a, b)

    def test_old_socket_in_cell_still_found(self):
        """A screen opened before TS 10 (socket in the cell) is still found; a new one never goes there."""
        import socket
        old = socket.socket(socket.AF_UNIX)
        self.addCleanup(old.close)
        old.bind(self.cell.file("tty.sock"))
        self.assertEqual(cli_cell.tty_socket(self.cell.path), self.cell.file("tty.sock"))
        self.assertEqual(cli_cell.tty_socket(self.cell.path, make=True), str(self.dir / (self.hash + ".sock")))

    @unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
    def test_real_tmux_screen_outside_the_cell(self):
        sock = cli_cell.tty_socket(self.cell.path, make=True)
        self.addCleanup(subprocess.run, ["tmux", "-S", sock, "kill-server"], capture_output=True)
        self.assertFalse(self.cell.alive())
        r = self.cell.tmux("new-session", "-d", "-s", cli_base.TMUX_SESSION, "sleep 60", new=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.cell.alive())
        self.assertTrue(os.path.exists(sock))
        self.assertEqual(sorted(os.listdir(self.cell.path)), [])   # nothing made in the cell (no tty.sock)
        self.assertTrue(cli_cell.close(self.cell))
        self.assertFalse(self.cell.alive())
        self.assertFalse(os.path.exists(sock))                   # close removes the socket file too
        self.assertEqual(subprocess.run(["tmux", "-S", sock, "has-session"], capture_output=True).returncode, 1)


if __name__ == "__main__":
    unittest.main()
