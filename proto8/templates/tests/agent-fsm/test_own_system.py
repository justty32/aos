"""Test the agent-fsm think cell with the declared system (11-11 self-system): self_system get, set, the next think sends the new text whole (replacing the definition's), empty = no system message, reset = back to the definition's."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

CELLS = Path(__file__).resolve().parents[2] / 'agent-fsm'   # 範本本身
PROTO = CELLS.parents[1]
TOOL = PROTO / "lib" / "agent" / "self_system" / "_entry"


class OwnSystem(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="aos-own-system-"))
        self.defn, self.d, kernel, self.ws = self.root / "def", self.root / "d", self.root / "k", self.root / "ws"
        for x in (self.defn, self.d, kernel, self.ws):
            x.mkdir()
        decl = json.loads((CELLS / "interfaces.json").read_text())["aos-agent"]
        self.assertEqual(decl["system"], "system.txt")                   # the template declares it
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"llm": "llm.json", "system": decl["system"]}}))
        (self.defn / "llm.json").write_text('{"model":"fake"}')
        (self.defn / "system.txt").write_text("You are the definition.\n")
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps(
            {"procs": {"bob": {"phase": "running", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn)}}}))
        (self.stack / "history.jsonl").write_text('{"role":"user","content":"hi"}\n')
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        bins = [str(p) for p in (PROTO / "impls").glob("*/bin")] + [str(PROTO / "cmd" / n / "bin") for n in ("aos-tools", "aos-agent")]
        env["PATH"] = os.pathsep.join(bins + [env["PATH"]])
        env.update(AOS_STACK=str(self.stack), AOS_CD=str(self.defn), AOS_WS=str(self.ws), AOS_DAEMON=str(self.d),
                   AOS_LLM_KERNEL=str(kernel), PYTHONDONTWRITEBYTECODE="1")
        self.env = env

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def system_sent(self):
        r = subprocess.run([sys.executable, str(CELLS / "brain.py"), "--history", "task"], env=self.env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        msgs = json.loads((self.stack / "think" / "request.json").read_text())["request"]["messages"]
        shutil.rmtree(self.stack / "think")
        return msgs[0]["content"] if msgs[0]["role"] == "system" else None

    def self_system(self, args):
        env = dict(self.env, AOS_STACK=str(self.stack / "tools" / "self_system"))   # what aos-tools call gives the tool
        r = subprocess.run([sys.executable, str(TOOL)], input=json.dumps(args), env=env,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_get_set_think_reset(self):
        self.assertEqual(self.system_sent(), "You are the definition.\n")
        self.assertEqual(self.self_system({"op": "get"}), "You are the definition.\n")
        out = self.self_system({"op": "set", "text": "End every sentence with ~.\n"})
        self.assertIn("next brain call", out)
        self.assertEqual(self.system_sent(), "End every sentence with ~.\n")   # whole text replaced, from the next think
        self.assertTrue(self.self_system({"op": "get", "long": True}).startswith("agent\t%s\n" % (self.stack / "system.txt")))
        self.self_system({"op": "set", "text": ""})
        self.assertIsNone(self.system_sent())                                   # empty = no system message
        self.self_system({"op": "reset"})
        self.assertFalse((self.stack / "system.txt").exists())
        self.assertEqual(self.system_sent(), "You are the definition.\n")
        self.assertEqual((self.defn / "system.txt").read_text(), "You are the definition.\n")

    def test_explicit_flag_ignores_own_copy(self):
        (self.stack / "system.txt").write_text("mine\n")
        (self.defn / "other.txt").write_text("other\n")
        r = subprocess.run([sys.executable, str(CELLS / "brain.py"), "--system", "other.txt"], env=self.env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        msgs = json.loads((self.stack / "think" / "request.json").read_text())["request"]["messages"]
        self.assertEqual(msgs[0], {"role": "system", "content": "other\n"})

    def test_definition_file_missing_means_no_system(self):
        (self.defn / "system.txt").unlink()
        self.assertIsNone(self.system_sent())


if __name__ == "__main__":
    unittest.main()
