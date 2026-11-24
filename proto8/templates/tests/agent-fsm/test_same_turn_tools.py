"""Pin when a tool added in the middle of a turn works in agent-fsm (11-10 tools-def, user "3.同一輪就生效"): brain and act re-read the registry on every step, so the next reply in the same turn sees and calls it; a call in the same reply that added it is ToolUnknown."""
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
GROW = '''import json, sys
reg = sys.argv[1]
data = json.load(open(reg))
data["tools"]["clock2"] = {"path": sys.argv[2]}
json.dump(data, open(reg, "w"))
print("added clock2")
'''


class SameTurnTools(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="aos-same-turn-"))
        self.defn, self.stack, kernel = self.root / "def", self.root / "st", self.root / "k"
        for d in (self.defn, self.stack, kernel):
            d.mkdir()
        grow = self.root / "grow"
        grow.mkdir()
        (grow / "grow.py").write_text(GROW)
        reg = self.defn / "tools.json"
        (grow / "_entry.json").write_text(json.dumps({"argv": ["python3", "grow.py", str(reg), str(CLOCK)]}))
        (grow / "_tooldef.json").write_text(json.dumps({"description": "Add clock2 to my tools."}))
        reg.write_text(json.dumps({"tools": {"grow": {"path": str(grow)}}}))
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"llm": "llm.json", "tools": "tools.json"}}))
        (self.defn / "llm.json").write_text('{"model":"fake"}')
        (self.stack / "history.jsonl").write_text('{"role":"user","content":"hi"}\n')
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") or k == "AOS_HOME"}
        bins = [str(PROTO / "bin")] + [str(PROTO / "bin")]
        env["PATH"] = os.pathsep.join(bins + [env["PATH"]])
        env.update(AOS_STACK=str(self.stack), AOS_CD=str(self.defn), AOS_WS=str(self.root),
                   AOS_LLM_KERNEL=str(kernel), PYTHONDONTWRITEBYTECODE="1")
        self.env = env

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def cell(self, name, *args):
        r = subprocess.run([sys.executable, str(CELLS / (name + ".py")), *args], env=self.env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)

    def reply(self, *names):
        calls = [{"id": "c%d" % i, "type": "function", "function": {"name": n, "arguments": "{}"}} for i, n in enumerate(names)]
        with open(self.stack / "history.jsonl", "a") as f:
            f.write(json.dumps({"role": "assistant", "content": None, "tool_calls": calls}) + "\n")
        self.cell("act")
        lines = (self.stack / "history.jsonl").read_text().splitlines()
        return [json.loads(x)["content"] for x in lines[-len(names):]]

    def offered(self):
        self.cell("brain", "--history", "task")
        req = json.loads((self.stack / "think" / "request.json").read_text())["request"]
        shutil.rmtree(self.stack / "think")
        return sorted(t["function"]["name"] for t in req.get("tools", []))

    def test_added_tool_works_from_the_next_reply_of_the_same_turn(self):
        self.assertEqual(self.offered(), ["grow"])
        added, same_reply = self.reply("grow", "clock2")
        self.assertIn("added clock2", added)
        self.assertIn("ToolUnknown", same_reply)               # the same reply: act read the list before the calls
        self.assertEqual(self.offered(), ["clock2", "grow"])   # next thought: in the tool list
        self.assertRegex(self.reply("clock2")[0], r"\d{4}-\d\d-\d\dT")   # next reply: callable


if __name__ == "__main__":
    unittest.main()
