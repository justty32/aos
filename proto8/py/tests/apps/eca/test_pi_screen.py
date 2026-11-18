"""Test the pi kind's screen (11-18 eca-pi plan C: hook pi, the inbox in cli_a2a, a real tmux screen running fake_pi) and the rpc run loop."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
SESSION = REPO / "proto8" / "py" / "aos" / "agentlib" / "cli_session.py"
sys.path.insert(0, str(REPO / "proto8" / "py"))
from aos.agentlib import cli_a2a, cli_ask, cli_base, cli_cell, cli_pi, cli_pi_rpc, cli_screen  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="t-pi-screen-")
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.t, self.ws, self.home, self.stack = t, t / "ws", t / "home", t / "stack"
        for d in (self.ws, self.home, self.stack, t / "run", t / "bin"):
            d.mkdir()
        pi = t / "bin" / "pi"
        pi.write_text('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, HERE / "fake_pi"))
        pi.chmod(0o755)
        self.log = t / "cli_log.jsonl"
        env = {"HOME": str(self.home), "XDG_RUNTIME_DIR": str(t / "run"), "FAKE_CLI_LOG": str(self.log),
               "PATH": "%s:%s" % (t / "bin", os.environ.get("PATH", "")), "PYTHONDONTWRITEBYTECODE": "1"}
        for patcher in (mock.patch.dict(os.environ, env), mock.patch.object(cli_base, "die", self.raise_die)):
            patcher.start()
            self.addCleanup(patcher.stop)
        for k in [k for k in os.environ if k.startswith(("AOS_", "FAKE_PI_", "PI_", "TMUX"))]:
            os.environ.pop(k)
        self.cell = cli_cell.Cell(str(self.stack / "pi"))
        self.cell.write("ws.txt", os.path.relpath(self.ws, self.cell.path) + "\n")
        self.cell.write("stack.txt", os.path.relpath(self.stack, self.cell.path) + "\n")
        self.cfg = {"kind": "pi", "flags": [], "timeout_ms": 20000}

    @staticmethod
    def raise_die(code, reason):
        raise RuntimeError("%s %s" % (code, reason))

    def hook(self, payload):
        r = subprocess.run([sys.executable, str(SESSION), "hook", "pi", self.cell.path], input=json.dumps(payload),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def history(self, rows=None):
        p = self.stack / "history.jsonl"
        if rows is not None:
            p.write_text("".join(json.dumps(r) + "\n" for r in rows))
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


class Hook(Base):
    def test_turn_start_and_end(self):
        self.hook({"event": "session_start", "reason": "startup", "session_id": "s1"})
        self.assertEqual(json.loads(self.cell.read("a2a.json")), {"inbox": self.cell.file("pi_inbox")})
        self.assertTrue(os.path.isdir(self.cell.file("pi_inbox")))
        self.assertEqual(self.cell.read("session.txt"), "")                 # startup: wait for the first turn
        self.hook({"event": "agent_start", "session_id": "s1"})
        self.assertEqual(self.cell.read("session.txt"), "s1")
        self.assertTrue(os.path.exists(self.cell.file("busy.txt")))
        msgs = [{"role": "user", "text": "q"}, {"role": "assistant", "stopReason": "toolUse", "text": ""},
                {"role": "assistant", "stopReason": "stop", "text": "done"}]
        self.hook({"event": "agent_settled", "session_id": "s1", "aborted": False, "messages": msgs})
        self.assertEqual([t["text"] for t in self.cell.turns()], ["done"])
        self.assertFalse(os.path.exists(self.cell.file("busy.txt")))
        self.hook({"event": "ack", "ids": ["abc"]})
        self.assertEqual(list(cli_a2a.acked(self.cell, 0, ["abc"])), ["abc"])

    def test_new_clears_history_and_compact_replaces_it(self):
        self.history([{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}])
        self.hook({"event": "compact", "session_id": "s1", "summary": "short version"})
        rows = self.history()
        self.assertEqual(len(rows), 1)
        self.assertIn("short version", rows[0]["content"])
        self.hook({"event": "session_start", "reason": "new", "session_id": "s2"})
        self.assertEqual(self.history(), [])
        self.assertEqual(self.cell.read("session.txt"), "s2")
        self.assertTrue((self.stack / "history_removed.jsonl").exists())

    def test_inbox_post(self):
        self.assertIsNone(cli_a2a.socket_path(self.cfg, self.cell))
        cli_a2a.note_inbox(self.cell, self.cell.file("pi_inbox"))
        path = cli_a2a.socket_path(self.cfg, self.cell)
        self.assertEqual(path, self.cell.file("pi_inbox"))
        self.assertIsNone(cli_a2a.socket_path(dict(self.cfg, a2a=False), self.cell))
        ids = cli_a2a.post(self.cfg, path, [("ann", "one"), (None, "two")])
        docs = [json.loads((Path(path) / n).read_text()) for n in sorted(os.listdir(path))]
        self.assertEqual([(d["id"], d["text"]) for d in docs], list(zip(ids, ["one", "two"])))


@unittest.skipUnless(shutil.which("tmux"), "needs tmux")
class Screen(Base):
    def setUp(self):
        super().setUp()
        self.addCleanup(lambda: cli_cell.close(self.cell))

    def test_open_answer_through_inbox_and_by_typing(self):
        self.cell.write("session.txt", "")
        self.assertTrue(cli_screen.start(self.cfg, self.cell, str(self.ws), str(self.stack)))
        deadline = time.time() + 10
        while not cli_a2a.socket_path(self.cfg, self.cell) and time.time() < deadline:
            time.sleep(0.1)
        self.assertTrue(cli_a2a.socket_path(self.cfg, self.cell))
        got = cli_ask.ask(self.cfg, self.cell, str(self.ws), str(self.ws), str(self.stack), "first\n\nsecond",
                          parts=[("ann", "first"), (None, "second")])
        self.assertEqual(got, "FAKE PI: first\n\nsecond")
        sid = self.cell.read("session.txt")
        self.assertTrue(sid)
        self.assertEqual(cli_ask.ask(self.cfg, self.cell, str(self.ws), str(self.ws), str(self.stack), "typed in"), "FAKE PI: typed in")
        self.assertEqual(self.cell.read("session.txt"), sid)
        ext = Path(self.cell.file("pi-aos-screen.mjs")).read_text()
        self.assertIn(json.dumps(cli_pi.SCREEN_MODULE), ext)
        self.assertTrue(os.path.exists(cli_pi.SCREEN_MODULE))
        conf = Path(self.cell.file("tmux.conf")).read_text()
        self.assertIn("extended-keys on", conf)
        self.assertIn("set -gq extended-keys-format csi-u", conf)      # -q: tmux before 3.5 has no such option

    def test_start_resumes_the_same_session(self):
        cli_cell.mark_session("pi", self.cell, str(self.ws), "known-id")
        os.makedirs(self.cell.file("pi-sessions"))
        Path(self.cell.file("pi-sessions"), "2026-11-18T00-00-00-000Z_known-id.jsonl").write_text('{"type": "session"}\n')
        seen = []
        with mock.patch.object(cli_cell.Cell, "tmux", side_effect=lambda *a, **kw: seen.append(a) or (_ for _ in ()).throw(FileNotFoundError())):
            with self.assertRaises(RuntimeError):
                cli_screen.start(self.cfg, self.cell, str(self.ws), str(self.stack))
        argv = list(seen[-1])
        self.assertEqual(argv[argv.index("--session-id") + 1], "known-id")
        self.assertEqual(argv[argv.index("--tui-mode") + 1], "regular")
        self.assertIn("--no-approve", argv)


class Rpc(Base):
    class More:
        def __init__(self, letters, after=0):
            self.letters, self.after, self.calls, self.log = list(letters), after, 0, []

        def take(self):
            self.calls += 1
            return [(None, self.letters[0])] if self.letters and self.calls > self.after else []

        def sent(self):
            self.log.append(("sent", self.letters.pop(0)))

        def unsent(self):
            self.log.append(("unsent", self.letters.pop(0)))

    def run_rpc(self, more, delay):
        os.environ["FAKE_PI_DELAY"] = str(delay)
        argv = cli_pi.pi_argv(self.cfg, self.cell, str(self.ws), str(self.stack), "rpc-id")
        return cli_pi_rpc.run_pi_rpc(argv, "hello", str(self.ws), 30, self.cell.file("live.jsonl"), None, more, {"letters": 5, "seconds": 300})

    def test_letter_after_settled_is_a_new_prompt(self):
        more = self.More(["late"])                                        # steered in or sent after agent_settled: same answer
        code, lines, refused = self.run_rpc(more, 0)
        self.assertEqual((code, refused), (0, None))
        self.assertEqual(cli_pi.answer_of(cli_pi.messages_of(lines)), "FAKE PI: hello\n\nFAKE PI: late")
        self.assertEqual(more.log, [("sent", "late")])

    def test_cap_sends_back_the_rest(self):
        more = self.More(["a", "b", "c"])
        code, lines, _ = cli_pi_rpc.run_pi_rpc(cli_pi.pi_argv(self.cfg, self.cell, str(self.ws), str(self.stack), "cap-id"), "hello",
                                               str(self.ws), 30, self.cell.file("live.jsonl"), None, more, {"letters": 1, "seconds": 300})
        self.assertEqual(more.log, [("sent", "a")])                       # b and c are never taken: they wait for the next turn
        self.assertEqual(cli_pi.answer_of(cli_pi.messages_of(lines)), "FAKE PI: hello\n\nFAKE PI: a")


if __name__ == "__main__":
    unittest.main()
