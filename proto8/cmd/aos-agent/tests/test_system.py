"""Test aos-agent system on a fake daemon table (11-11 self-system): get / get -l / get --json, set from stdin and from a file, empty text, reset, missing and bad declarations, and llm set system refused (11-11 ruling: error and point here)."""
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
JSON_BIN = REPO / "proto8" / "impls" / "aos-json" / "bin"


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = str(JSON_BIN) + os.pathsep + os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return env


class System(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-system-"))
        self.d = self.tmp / "d"
        self.defn = self.tmp / "defs" / "bob"
        self.defn.mkdir(parents=True)
        self.declare({"system": "system.txt", "llm": "llm.json", "llm_keys": ["model"]})
        (self.defn / "system.txt").write_text("You are bob.\n")
        (self.tmp / "ws").mkdir()
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps(
            {"procs": {"bob": {"phase": "stopped", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn)}}}))
        self.own = self.stack / "system.txt"

    def declare(self, decl):
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": decl}))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def agent(self, *args, ok=True, stdin=None, sub="system"):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), sub, "--target", "bob", *args],
                           env=clean_env(), capture_output=True, text=True, timeout=60, cwd=self.tmp,
                           input=stdin, stdin=None if stdin is not None else subprocess.DEVNULL)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def test_get_forms(self):
        self.assertEqual(self.agent().stdout, "You are bob.\n")
        self.assertEqual(self.agent("get", "-l").stdout, "definition\t%s\nYou are bob.\n" % (self.defn / "system.txt"))
        j = json.loads(self.agent("get", "--json").stdout)
        self.assertEqual(j, {"text": "You are bob.\n", "from": "definition", "file": str(self.defn / "system.txt"), "bytes": 13})
        self.assertIn("give -l or --json", self.agent("get", "-l", "--json", ok=False).stderr)
        self.assertIn("CommandUnknown", self.agent("show", ok=False).stderr)

    def test_set_from_stdin_and_file_then_reset(self):
        r = self.agent("set", stdin="End every sentence with ~.\n")
        self.assertIn("takes effect from its next brain call", r.stdout)
        self.assertIn("created %s" % self.own, r.stderr)
        self.assertEqual(self.own.read_text(), "End every sentence with ~.\n")
        self.assertEqual(self.agent("get", "-l").stdout, "agent\t%s\nEnd every sentence with ~.\n" % self.own)
        (self.tmp / "new.txt").write_text("Be short.")
        self.agent("set", "new.txt")
        self.assertEqual(self.agent().stdout, "Be short.\n")             # get adds the missing newline
        self.assertEqual(self.own.read_text(), "Be short.")
        self.assertEqual((self.defn / "system.txt").read_text(), "You are bob.\n")   # the definition is never written
        self.assertIn("PathMissing", self.agent("set", "nope.txt", ok=False).stderr)
        self.agent("reset", "-y")
        self.assertFalse(self.own.exists())
        self.assertEqual(self.agent().stdout, "You are bob.\n")
        self.assertIn("there was no own system text", self.agent("reset", "-y").stdout)

    def test_empty_text_is_kept(self):
        r = self.agent("set", "-", stdin="")
        self.assertIn("the text is empty", r.stderr)
        self.assertEqual(self.own.read_text(), "")
        r = self.agent("get", "-l")
        self.assertEqual(r.stdout, "agent\t%s\n" % self.own)
        self.assertIn("no system text", r.stderr)

    def test_definition_file_missing_is_empty(self):
        (self.defn / "system.txt").unlink()
        j = json.loads(self.agent("get", "--json").stdout)
        self.assertEqual((j["from"], j["text"]), ("none", ""))

    def test_missing_and_bad_declaration(self):
        self.declare({"llm": "llm.json"})
        self.assertIn("SystemMissing bob does not declare system", self.agent(ok=False).stderr)
        for bad in ("/etc/passwd", "../x.txt", "", 3):
            self.declare({"system": bad})
            self.assertIn("SystemBad", self.agent(ok=False).stderr, bad)
        (self.defn / "sys").mkdir()
        self.declare({"system": "sys"})
        self.assertIn("SystemBad", self.agent(ok=False).stderr)

    def test_codex_note(self):
        (self.defn / "cli.json").write_text('{"kind": "codex"}')
        self.assertIn("codex keeps the system text a conversation started with", self.agent("set", stdin="x").stderr)
        self.assertIn("codex keeps the system text", self.agent("reset", "-y").stderr)
        (self.defn / "cli.json").write_text('{"kind": "claude"}')
        self.assertNotIn("codex keeps", self.agent("set", stdin="x").stderr)

    def test_llm_set_system_points_here(self):
        # 11-11 使用者翻案「報錯並指路」：不存、錯誤行指到 aos-agent system
        r = self.agent("set", "model=m", "system=be nice", sub="llm", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-agent: error: ArgumentsBad system is not a brain setting: change the system text with aos-agent system set", r.stderr)
        self.assertTrue(r.stderr.rstrip().endswith("set [FILE | -])"), r.stderr)
        self.assertNotIn("warning:", r.stderr)
        self.assertFalse((self.stack / "llm.json").exists())          # 一鍵都沒存（連同一次給的 model）
        self.assertEqual(self.agent("set", "model=m", sub="llm").returncode, 0)   # 其他鍵照舊


if __name__ == "__main__":
    unittest.main()
