"""11-25 (user's ruling on bgmail report items 7 and 8): claude -p is done at its first type=result. A fake claude that keeps running
after its first result (the way claude -p waits for a background task, then answers a second turn) is stopped with its whole process
group and every descendant, the exit counts as 0, and the answer is the first result. A fake that exits by itself is unchanged."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
from aos.agentlib import cli_print  # noqa: E402

FAKE = r'''#!/usr/bin/env python3
import json, os, subprocess, sys, time
sys.stdin.read()
mode, mark = sys.argv[1], sys.argv[2]
def out(ev):
    print(json.dumps(ev), flush=True)
out({"type": "system", "subtype": "init", "session_id": "s1"})
if mode == "background":
    kid = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])       # the background task (same group)
    away = subprocess.Popen([sys.executable, "-c", "import os, time; os.setsid(); time.sleep(60)"])   # one that left the group
    open(mark, "w").write("%d %d" % (kid.pid, away.pid))
out({"type": "result", "subtype": "success", "is_error": False, "result": "first answer", "session_id": "s1"})
if mode == "background":
    time.sleep(30)                                         # claude -p waiting for the background task
    out({"type": "result", "subtype": "success", "is_error": False, "result": "the background task finished", "session_id": "s1"})
'''


def alive(pid):
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().split(")")[-1].split()[0] not in ("Z", "X")
    except OSError:
        return False


class FirstResult(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="first-result-"))
        self.fake = self.tmp / "claude"
        self.fake.write_text(FAKE)
        self.fake.chmod(0o755)
        self.mark = self.tmp / "pids"

    def run_fake(self, mode):
        started = time.time()
        code, lines = cli_print.run_claude_stream([str(self.fake), mode, str(self.mark)], "hi", str(self.tmp), 0,
                                                  str(self.tmp / "live.jsonl"))
        return code, lines, time.time() - started

    def test_keeps_running_after_result_is_stopped_with_its_children(self):
        code, lines, took = self.run_fake("background")
        self.assertEqual(code, 0)
        self.assertLess(took, cli_print.RESULT_GRACE_S + cli_print.STOP_GRACE_S * 2 + 5)     # not the fake's 30 s
        results = [json.loads(l)["result"] for l in lines if '"result"' in l]
        self.assertEqual(results, ["first answer"])                                          # nothing after the first result
        kid, away = map(int, self.mark.read_text().split())
        deadline = time.time() + 5
        while (alive(kid) or alive(away)) and time.time() < deadline:
            time.sleep(0.1)
        self.assertFalse(alive(kid), "background child left running")
        self.assertFalse(alive(away), "child in its own session left running")
        self.assertEqual(open(self.tmp / "live.jsonl").read().count('"type": "result"'), 1)

    def test_exits_by_itself_unchanged(self):
        code, lines, took = self.run_fake("plain")
        self.assertEqual(code, 0)
        self.assertLess(took, cli_print.RESULT_GRACE_S)
        self.assertEqual([json.loads(l)["result"] for l in lines if '"result"' in l], ["first answer"])

    def test_print_claude_answers_with_the_first_result(self):
        """print_claude takes the first result line even when more follow (11-25 item 8)."""
        from unittest.mock import patch
        from aos.agentlib import cli_cell
        lines = [json.dumps({"type": "result", "is_error": False, "result": r, "session_id": "s"}) + "\n" for r in ("one", "two")]
        cfg = {"kind": "claude", "flags": [], "print_flags": [], "external": [], "registry": None, "sub_registry": None,
               "cli_settings": None, "cli_def": str(self.tmp)}
        cell = cli_cell.Cell(str(self.tmp / "cell"))
        os.makedirs(cell.path, exist_ok=True)
        with patch.object(cli_print, "run_claude_stream", return_value=(0, lines)), \
                patch.object(cli_print, "mcp_argv", return_value=[]), patch.object(cli_print, "system_argv", return_value=[]), \
                patch.object(cli_print, "mark_session"):
            self.assertEqual(cli_print.print_claude(cfg, cell, str(self.tmp), str(self.tmp), "hi", None, "s"), "one")

if __name__ == "__main__":
    unittest.main()
