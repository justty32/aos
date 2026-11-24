"""Test that brain and act use the agent's own tools registry in its stack ("$override" of the definition's; 11-10 aos-tools-cli step 4), and fall back to the definition's after reset."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
os.environ.setdefault("AOS_HOME", str(Path(__file__).resolve().parents[3]))   # 路徑規則一（11-17）：範本的格只經 AOS_HOME 找 lib，測試給它這份 proto8

PROTO = Path(__file__).resolve().parents[3]
CELLS = PROTO / 'py' / 'aos' / 'apps' / 'agent_fsm'   # 格的程式（11-24 起搬出範本，裝好在 lib/aos/apps/agent_fsm）
TEMPLATE = PROTO / 'templates' / 'agents' / 'agent-fsm'   # 範本本身（給人抄的定義）
CLOCK = PROTO / "py" / "tools" / "base" / "peek_now_time"


class OwnTools(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="aos-own-tools-"))
        self.defn, self.stack, kernel = self.root / "def", self.root / "st", self.root / "k"
        for d in (self.defn, self.stack, kernel):
            d.mkdir()
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"llm": "llm.json", "tools": "tools.json"}}))
        (self.defn / "llm.json").write_text('{"model":"fake"}')
        (self.defn / "tools.json").write_text(json.dumps({"tools": {"peek_now_time": {"path": str(CLOCK)}}}))
        (self.stack / "history.jsonl").write_text('{"role":"user","content":"hi"}\n')
        self.own = self.stack / "tools.json"
        self.own.write_text(json.dumps({"$override": "../def/tools.json",
                                        "tools": {"peek_now_time": None, "clock2": {"path": str(CLOCK)}}}))
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") or k == "AOS_HOME"}
        bins = [str(PROTO / "bin")] + [str(PROTO / "bin")]
        env["PATH"] = os.pathsep.join(bins + [env["PATH"]])
        env.update(AOS_STACK=str(self.stack), AOS_CD=str(self.defn), AOS_WS=str(self.root),
                   AOS_LLM_KERNEL=str(kernel), PYTHONDONTWRITEBYTECODE="1")
        self.env = env

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def cell(self, name, *args):
        return subprocess.run([sys.executable, str(CELLS / (name + ".py")), *args], env=self.env,
                              capture_output=True, text=True, timeout=30)

    def offered(self):
        r = self.cell("brain", "--history", "task")
        self.assertEqual(r.returncode, 0, r.stderr)
        req = json.loads((self.stack / "think" / "request.json").read_text())["request"]
        shutil.rmtree(self.stack / "think")
        return [t["function"]["name"] for t in req.get("tools", [])]

    def test_brain_sees_own_registry_then_definition_after_reset(self):
        self.assertEqual(self.offered(), ["clock2"])
        self.own.unlink()                                   # what aos-agent tools reset does
        self.assertEqual(self.offered(), ["peek_now_time"])

    def test_act_calls_tool_added_in_own_registry(self):
        call = {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "clock2", "arguments": "{}"}}]}
        with open(self.stack / "history.jsonl", "a") as f:
            f.write(json.dumps(call) + "\n")
        r = self.cell("act")
        self.assertEqual(r.returncode, 0, r.stderr)
        last = json.loads((self.stack / "history.jsonl").read_text().splitlines()[-1])
        self.assertEqual(last["role"], "tool")
        self.assertRegex(last["content"], r"\d{4}-\d\d-\d\dT")


if __name__ == "__main__":
    unittest.main()
