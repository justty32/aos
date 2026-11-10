"""Test aos-agent llm on a fake daemon table (11-10 晚使用者「換」「跳warinig就好」): ls / ls -l / ls --json, set (unread key = warning, stored), rm KEY, reset, and show gone."""
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


class Llm(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-llm-"))
        self.d = self.tmp / "d"
        self.defn = self.tmp / "defs" / "bob"
        self.defn.mkdir(parents=True)
        (self.defn / "interfaces.json").write_text(json.dumps(
            {"aos-agent": {"llm": "llm.json", "llm_keys": ["model", "temperature"]}}))
        (self.defn / "llm.json").write_text(json.dumps({"model": "smart", "temperature": "0.7"}))
        (self.tmp / "ws").mkdir()
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps(
            {"procs": {"bob": {"phase": "stopped", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn)}}}))
        self.own = self.stack / "llm.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def agent(self, *args, ok=True):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "llm", "--target", "bob", *args],
                           env=clean_env(), capture_output=True, text=True, timeout=60, cwd=self.tmp, stdin=subprocess.DEVNULL)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def test_ls_forms(self):
        self.assertEqual(self.agent().stdout, "model=smart\ntemperature=0.7\n")
        self.agent("set", "temperature=0.1")
        self.assertEqual(self.agent("ls", "-l").stdout,
                         "model=smart\tdefinition\ntemperature=0.1\tagent\tdefinition: 0.7\n")
        rows = json.loads(self.agent("ls", "--json").stdout)
        self.assertEqual(rows[1], {"key": "temperature", "value": "0.1", "from": "agent", "definition": "0.7"})
        self.assertIn("unknown subcommand show", self.agent("show", ok=False).stderr)

    def test_set_unread_key_warns_and_stores(self):
        r = self.agent("set", "top_k=5")
        self.assertIn("top_k is not a setting the body of bob reads (it reads: model, temperature); stored anyway", r.stderr)
        self.assertEqual(json.loads(self.own.read_text()), {"top_k": "5"})
        self.assertNotIn("stored anyway", self.agent("set", "model=fast").stderr)

    def test_rm_and_reset(self):
        self.agent("set", "model=fast", "temperature=0")
        self.agent("rm", "model")
        self.assertEqual(json.loads(self.own.read_text()), {"temperature": "0"})
        r = self.agent("rm", "model", ok=False)
        self.assertIn("KeyMissing model not changed for bob (changed: temperature)", r.stderr)
        r = self.agent("rm", "temperature")
        self.assertFalse(self.own.exists())
        self.assertEqual(r.stdout, "model=smart\ntemperature=0.7\n")
        self.agent("set", "model=fast")
        self.agent("reset", "-y")
        self.assertFalse(self.own.exists())


if __name__ == "__main__":
    unittest.main()
