"""Test aos-agent ctl state (11-10 self-family self_state): the overview (one line per part), picked parts, all, --json, and parts that are not available."""
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
PARTS = ["who", "state", "tools", "llm", "hooks", "history", "mailbox", "children", "resources", "time"]


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return env


class State(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-state-"))
        self.d = self.tmp / "d"
        self.defn = self.tmp / "defs" / "bob"
        self.defn.mkdir(parents=True)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"tools": "tools.json", "llm": "llm.json", "history": "history.jsonl"}}))
        (self.defn / "tools.json").write_text(json.dumps({"tools": {"clock": {"path": str(REPO / "proto8" / "lib" / "base" / "wall_clock")}}}))
        (self.defn / "llm.json").write_text(json.dumps({"model": "m1"}))
        (self.defn / "children.json").write_text(json.dumps({"max_children": 2}))
        (self.tmp / "ws").mkdir()
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps({"procs": {
            "bob": {"phase": "paused", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn), "limits": {"memory_max": "1G"}},
            "kid": {"phase": "running", "stack": "procs/kid", "ws": "../ws"}}}))
        (self.stack / "llm.json").write_text(json.dumps({"model": "m2"}))
        (self.stack / "history.jsonl").write_text("".join(json.dumps(m) + "\n" for m in (
            {"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}, {"role": "user", "content": "bye"})))
        book = self.stack / "tools" / "agents_children"
        book.mkdir(parents=True)
        (book / "children.json").write_text(json.dumps([{"name": "kid", "stack": "procs/kid"}]))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def state(self, *args, ok=True):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "ctl", "state", "--target", "bob", *args],
                           env=clean_env(), capture_output=True, text=True, timeout=120, cwd=self.tmp, stdin=subprocess.DEVNULL)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def test_overview_one_line_per_part(self):
        out = self.state().stdout.splitlines()
        self.assertEqual([l.split()[0] for l in out], PARTS)
        row = {l.split()[0]: l.split(None, 1)[1] for l in out}
        self.assertTrue(row["who"].startswith("bob (def %s" % self.defn))
        self.assertIn("1 tools (clock)", row["tools"])
        self.assertIn("model=m2", row["llm"])
        self.assertIn("changed by it: model", row["llm"])
        self.assertIn("3 messages", row["history"])
        self.assertIn("assistant 1, user 2", row["history"])
        self.assertNotIn(" 0 bytes", row["history"])
        self.assertEqual(row["children"], "1/2 children (kid running)")
        self.assertIn("limits memory_max=1G; no running process", row["resources"])
        self.assertIn("not running", row["time"])
        self.assertTrue(row["hooks"].startswith("not available ("), row["hooks"])   # 沒宣告 hooks
        self.assertIn("0 letters waiting", row["mailbox"])

    def test_picked_parts_and_all(self):
        out = self.state("history", "llm").stdout
        self.assertEqual([l for l in out.splitlines() if l.startswith("== ")], ["== history", "== llm"])
        self.assertIn("3\tuser\tbye", out)
        out = self.state("all").stdout
        self.assertEqual([l[3:] for l in out.splitlines() if l.startswith("== ")], PARTS)

    def test_json(self):
        j = json.loads(self.state("-j").stdout)
        self.assertEqual(list(j), PARTS)
        self.assertEqual(j["history"]["messages"], 3)
        self.assertEqual(j["llm"]["settings"], {"model": "m2"})
        self.assertEqual(j["children"]["max_children"], 2)
        self.assertEqual(j["hooks"]["available"], False)
        j = json.loads(self.state("--json", "tools").stdout)
        self.assertEqual(list(j), ["tools"])
        self.assertEqual(j["tools"]["names"], ["clock"])

    def test_unknown_part(self):
        p = self.state("bogus", ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("aos-agent: error: ArgumentsBad unknown part bogus", p.stderr)


if __name__ == "__main__":
    unittest.main()
