"""Test board_set / board_clear / board_wait / board_read / board_ls wrap aos-comm for the calling agent's root (real aos-comm and aos-agent, hand-written daemon table)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
AGENT = Path(__file__).resolve().parents[2]
PROTO = AGENT.parents[1]


class BoardTools(unittest.TestCase):
    def setUp(self):
        # 暫存夾不刪（使用者 11-14 不刪規則）：放在 $TMPDIR 底下，帶 board-tools- 字頭
        self.tmp = Path(tempfile.mkdtemp(prefix="board-tools-"))
        for n in ("ws", "alice/mailbox", "bob", "d"):
            (self.tmp / n).mkdir(parents=True)
        (self.tmp / "d" / "procs_state.json").write_text(json.dumps(
            {"procs": {"alice": {"stack": "../alice", "phase": "running"}, "bob": {"stack": "../bob", "phase": "sleeping"}}}))
        path = "%s:%s:%s" % (PROTO / "cmd" / "aos-comm" / "bin", PROTO / "cmd" / "aos-agent" / "bin", os.environ["PATH"])
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(PATH=path, AOS_WS=str(self.tmp / "ws"), AOS_DAEMON=str(self.tmp / "d"), PYTHONDONTWRITEBYTECODE="1",
                        HOME=str(self.tmp), AOS_USER_ZONE=str(self.tmp / "zone"))

    def tool(self, name, args):
        (self.tmp / "alice" / "tools" / name).mkdir(parents=True, exist_ok=True)   # 工具小格；目標要認回 alice（05 A2）
        env = dict(self.env, AOS_STACK=str(self.tmp / "alice" / "tools" / name))
        r = subprocess.run([sys.executable, str(AGENT / name / "_entry")], input=json.dumps(args), capture_output=True,
                           text=True, env=env, timeout=60)
        return r

    def ok(self, name, args):
        r = self.tool(name, args)
        self.assertEqual(r.returncode, 0, (name, r.stdout, r.stderr))
        return r.stdout

    def board(self):
        return json.loads((self.tmp / "alice" / "board.json").read_text())

    def test_board_set(self):
        out = self.ok("board_set", {"mode": "dnd", "text": "running the tests", "back_in": "30m", "deputy": "bob"})
        self.assertIn("board written", out)
        b = self.board()
        self.assertEqual((b["mode"], b["text"], b["deputy"], b["seq"]), ("dnd", "running the tests", "bob", 1))
        self.assertIn("expires_at", b)
        self.assertFalse((self.tmp / "alice" / "tools" / "board_set" / "board.json").exists())
        r = self.tool("board_set", {"text": "no mode"})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.startswith("board_set: error: ArgumentsBad "), r.stdout)

    def test_board_clear(self):
        self.ok("board_set", {"mode": "away"})
        self.assertIn('"mode": "here"', self.ok("board_clear", {}))
        self.assertEqual((self.board()["mode"], self.board()["seq"]), ("here", 2))

    def test_board_wait(self):
        self.assertIn("added the waiting line", self.ok("board_wait", {"who": "user", "what": "approve the plan"}))
        self.assertEqual([w["who"] for w in self.board()["waiting_on"]], ["user"])
        self.assertIn("removed the waiting lines for user", self.ok("board_wait", {"who": "user", "done": True}))
        self.assertNotIn("waiting_on", self.board())
        self.assertIn("nothing removed", self.ok("board_wait", {"who": "user", "done": True}))

    def test_board_read(self):
        r = json.loads(self.ok("board_read", {}))
        self.assertEqual((r["who"], r["posted"]), ("me", False))
        self.ok("board_set", {"mode": "busy", "doing": "reviewing"})
        r = json.loads(self.ok("board_read", {}))
        self.assertEqual((r["mode"], r["board"]["doing"], "stack" in r), ("busy", "reviewing", False))
        (self.tmp / "bob" / "board.json").write_text(json.dumps(
            {"format": "board/1", "updated_at": r["board"]["updated_at"], "mode": "dnd"}))
        r = json.loads(self.ok("board_read", {"who": "bob"}))
        self.assertEqual((r["mode"], r["asleep"]), ("away", True))                     # sleeping＝不在

    def test_board_ls(self):
        self.ok("board_set", {"mode": "dnd", "doing": "tests"})
        lines = self.ok("board_ls", {}).splitlines()
        self.assertEqual(lines[0], "NAME\tMODE\tDOING\tWAITING FOR\tBACK")
        self.assertEqual(lines[1], "alice\tdnd\ttests\t-\t-")
        self.assertTrue(lines[2].startswith("bob\taway (no board, asleep)"), lines)
        self.assertTrue(lines[-1].startswith("2 procs: 1 dnd, 1 away"), lines)
        r = self.tool("board_ls", {"scope": "everything"})
        self.assertTrue(r.stdout.startswith("board_ls: error: ArgumentsBad "), r.stdout)


if __name__ == "__main__":
    unittest.main()
