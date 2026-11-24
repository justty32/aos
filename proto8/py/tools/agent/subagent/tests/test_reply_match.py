"""Test subagent op ask / op listen letter against the real aos-agent and simulated bodies (reply-match-1114): each asker gets its own answer, bodies not upgraded yet fall back, and the pre-change _entry (say + listen) reads the new history the same way."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

sys.dont_write_bytecode = True
TOOL = Path(__file__).resolve().parents[1] / "_entry"
PROTO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROTO / "py" / "tests" / "apps" / "agent"))
import reply_fixture as rf  # noqa: E402

# aos-agent on PATH for the tool: ctl ls / who answered from the fake table (procs_state.json), everything else goes to the real aos-agent -d <fake daemon>.
WRAP = r'''#!/usr/bin/env python3
import json, os, sys
argv, d = sys.argv[1:], os.environ["FAKE_DAEMON"]
rows = json.load(open(os.path.join(d, "procs_state.json")))["procs"]
table = [dict(r, name=n, stack=os.path.join(d, r["stack"])) for n, r in rows.items()]
if argv[:2] == ["ctl", "ls"]:
    print(json.dumps(table))
elif argv[:2] == ["ctl", "who"]:
    s = os.environ["AOS_STACK"]
    r = max((r for r in table if s == r["stack"] or s.startswith(r["stack"] + "/")), key=lambda r: len(r["stack"]))
    print(json.dumps({"name": r["name"], "stack": r["stack"], "ws": None, "def": None, "daemon": d}))
else:
    os.execv(sys.executable, [sys.executable, os.environ["REAL_AGENT"], "-d", d] + argv)
'''


class SubagentReply(unittest.TestCase):
    def setUp(self):
        self.d = rf.Daemon(self, names=("mom", "kid"))
        self.cell = self.d.stack("mom") / "tools" / "subagent"
        self.cell.mkdir(parents=True)
        (self.cell / "subagents.json").write_text(json.dumps([{"name": "kid", "stack": str(self.d.stack("kid"))}]))
        (self.d.bin / "aos-agent").write_text(WRAP)
        (self.d.bin / "aos-agent").chmod(0o755)
        self.ws = self.d.root / "ws"
        self.ws.mkdir()

    def run_tool(self, args, tool=TOOL):
        env = self.d.env(AOS_WS=str(self.ws), AOS_DAEMON=str(self.d.dir), AOS_STACK=str(self.cell),
                         FAKE_DAEMON=str(self.d.dir), REAL_AGENT=str(rf.AGENT_BIN))
        return subprocess.Popen([sys.executable, str(tool)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=env)

    def tool(self, args, tool=TOOL):
        p = self.run_tool(args, tool)
        out, err = p.communicate(json.dumps(args), timeout=60)
        return p.returncode, out, err

    def test_op_ask_each_gets_its_own(self):
        rf.Body(self, self.d.stack("kid"), think_s=0.6)
        ps = [(self.run_tool(None), {"op": "ask", "name": "kid", "text": t, "timeout_s": 20}) for t in ("alpha", "beta")]
        for p, args in ps:
            p.stdin.write(json.dumps(args))
            p.stdin.close()
        got = [(p.wait(60), p.stdout.read(), p.stderr.read()) for p, _ in ps]
        for p, _ in ps:
            p.stdout.close()
            p.stderr.close()
        self.assertEqual([(c, o) for c, o, _ in got], [(0, "re: [say from mom] alpha\n"), (0, "re: [say from mom] beta\n")], [e for _, _, e in got])

    def test_op_ask_old_body_falls_back(self):
        rf.Body(self, self.d.stack("kid"), upgraded=False)
        code, out, err = self.tool({"op": "ask", "name": "kid", "text": "hi", "timeout_s": 20})
        self.assertEqual((code, out), (0, "re: [say from mom] hi\n"), err)   # 11-24：上層 agent 寄的話帶「[say from 名字] 」
        self.assertIn("kid's body is not upgraded yet", err)

    def test_op_ask_dropped(self):
        rf.Body(self, self.d.stack("kid"), drop=lambda n, t: "blocked")
        code, out, err = self.tool({"op": "ask", "name": "kid", "text": "hi", "timeout_s": 20})
        self.assertEqual(code, 1, err)
        self.assertIn("subagent: error: LetterDropped ", out)

    def test_op_listen_letter(self):
        code, first, err = self.tool({"op": "say", "name": "kid", "text": "first"})
        self.assertEqual(code, 0, err)
        self.tool({"op": "say", "name": "kid", "text": "second"})
        rf.Body(self, self.d.stack("kid"), think_s=0.2)
        code, out, err = self.tool({"op": "listen", "name": "kid", "letter": first.strip(), "timeout_s": 20})
        self.assertEqual((code, out), (0, "re: [say from mom] first\n"), err)

    def test_pre_change_entry_reads_new_history_the_same(self):
        """lib/ is swapped only at the tree swap: the old _entry (say, then listen without a letter) against bodies that already write aos keys."""
        old = rf.base_tree(self, "lib") / "lib" / "agent" / "subagent" / "_entry"
        outs = {}
        for upgraded in (True, False):
            for f in ("history.jsonl", "letters.json"):
                p = self.d.stack("kid") / f
                if p.exists():
                    p.rename(self.d.root / ("%s.%s.%f" % (f, upgraded, time.time())))   # moved aside, not deleted
            body = rf.Body(self, self.d.stack("kid"), upgraded=upgraded, shape="eca", think_s=0.3)
            got = [self.tool({"op": "ask", "name": "kid", "text": t, "timeout_s": 20}, tool=old)[:2] for t in ("one", "two")]
            got.append(self.tool({"op": "listen", "name": "kid", "last": 2}, tool=old)[:2])
            body.stop.set()
            body.t.join(10)
            outs[upgraded] = got
            self.assertEqual((self.d.stack("kid") / "letters.json").exists(), upgraded)
        self.assertEqual(outs[True], outs[False])
        self.assertEqual(outs[True][:2], [(0, "re: one\n"), (0, "re: two\n")])


if __name__ == "__main__":
    unittest.main()
