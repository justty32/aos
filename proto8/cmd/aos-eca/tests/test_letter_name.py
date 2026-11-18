"""Test that a letter's sender (body "name", set by aos-agent say for an eca) reaches the CLI side as parts and never enters history, and that letters arriving while a turn waits are handed over at once (11-13 a2a)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROTO = HERE.parents[2]
TURN = PROTO / "cmd" / "aos-eca" / "bin" / "aos-eca-turn"
LOCAL_BIN = os.path.expanduser("~/.local/bin")
# 換掉 cli_ask.ask 的啟動檔：把收到的 prompt 與 parts 記下來、叫 handed、回固定答案（不起 CLI）
SPY = """import json, os, runpy, subprocess, sys
sys.argv[0] = %(turn)r
sys.path[:0] = [%(py)r, %(lib)r, %(eca)r]
from aos.agentlib import cli_ask
def ask(cfg, cell, tool_dir, ws, stack, prompt, on_busy="yield", handed=None, reseed=None, parts=None, more=None):
    row = {"prompt": prompt, "parts": parts, "late": []}
    if handed:
        handed()
    for body in json.loads(os.environ.get("SPY_LATE", "[]")):          # 等回答時又來的信
        sent = subprocess.run(["aos-post", "send", "--ordered", os.path.join(stack, "queue")], input=json.dumps(body), text=True,
                              check=True, capture_output=True)
        with open(os.environ["SPY_LOG"] + ".sigs", "a") as f:             # 信名（回答配對的斷言用）
            f.write(sent.stdout.strip() + "\\n")
        got = more.take() if more else None
        row["late"].append(got)
        if got:
            more.sent() if os.environ.get("SPY_DELIVER", "1") == "1" else more.unsent()
    with open(os.environ["SPY_LOG"], "a") as f:
        f.write(json.dumps(row) + "\\n")
    return "spy answer"
cli_ask.ask = ask
runpy.run_path(%(turn)r, run_name="__main__")
"""


class LetterName(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="eca-name-")
        self.addCleanup(tmp.cleanup)
        self.t = Path(tmp.name)
        self.defn, self.ws, self.stack, self.home = (self.t / n for n in ("def", "ws", "stack", "home"))
        for d in (self.defn, self.ws, self.stack, self.home):
            d.mkdir()
        (self.defn / "cli.json").write_text(json.dumps({"kind": "claude", "timeout_ms": 30000}))
        self.log = self.t / "spy.jsonl"
        self.spy = self.t / "spy_turn.py"
        self.spy.write_text(SPY % {"turn": str(TURN), "py": str(PROTO / "py"), "lib": str(PROTO / "py"), "eca": str(PROTO / "cmd" / "aos-eca")})
        subprocess.run(["aos-post", "init", str(self.stack / "queue")], env=self.env(), check=True, capture_output=True)

    def env(self, **more):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("AOS_", "CLAUDE"))}
        env.update(PATH="%s:%s" % (LOCAL_BIN, env.get("PATH", "")), HOME=str(self.home), AOS_STACK=str(self.stack),
                   AOS_WS=str(self.ws), SPY_LOG=str(self.log), PYTHONDONTWRITEBYTECODE="1")
        env.update(more)
        return env

    def turn(self, **env):
        r = subprocess.run([sys.executable, str(self.spy), "--on-empty", "idle", str(self.defn)], env=self.env(**env),
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [json.loads(l) for l in self.log.read_text().splitlines()]

    def history(self):
        return [json.loads(l) for l in (self.stack / "history.jsonl").read_text().splitlines()]

    def box(self, stage):
        return sorted(n for n in os.listdir(self.stack / "queue" / stage) if not n.startswith("."))

    def send(self, body):
        r = subprocess.run(["aos-post", "send", "--ordered", str(self.stack / "queue")], check=True, capture_output=True,
                           input=json.dumps(body), env=self.env(), text=True)
        return r.stdout.strip()

    def late_sigs(self):
        p = Path(str(self.log) + ".sigs")
        return p.read_text().split() if p.exists() else []

    def letters(self):
        return json.loads((self.stack / "letters.json").read_text())

    def test_name_goes_to_parts_not_history(self):
        a = self.send({"role": "user", "name": "bob", "content": "hello"})
        b = self.send({"role": "user", "content": "[aos] new_mail: 1 new letter from amy."})
        seen = self.turn()
        self.assertEqual(seen, [{"prompt": "hello\n\n[aos] new_mail: 1 new letter from amy.", "late": [],
                                 "parts": [["bob", "hello"], [None, "[aos] new_mail: 1 new letter from amy."]]}])
        self.assertEqual(self.history(), [{"role": "user", "content": "hello", "aos": {"letter": a}},
                                          {"role": "user", "content": "[aos] new_mail: 1 new letter from amy.", "aos": {"letter": b}},
                                          {"role": "assistant", "content": "spy answer", "aos": {"answer_to": [a, b]}}])

    def test_letters_arriving_mid_turn_are_handed_over_at_once(self):
        """11-13「馬上送」：等回答時又來的信一封一封認領、交出去就接進 history、收掉；壞信照舊丟。"""
        first = self.send({"role": "user", "content": "first"})
        late = [{"role": "user", "name": "amy", "content": "second"}, {"role": "tool", "content": "bad letter"},
                {"role": "user", "content": "third"}]
        seen = self.turn(SPY_LATE=json.dumps(late))
        second, bad, third = self.late_sigs()
        self.assertEqual(seen[0]["late"], [[["amy", "second"]], [], [[None, "third"]]])
        self.assertEqual(self.history(), [{"role": "user", "content": "first", "aos": {"letter": first}},
                                          {"role": "user", "content": "second", "aos": {"letter": second}},
                                          {"role": "user", "content": "third", "aos": {"letter": third}},
                                          {"role": "assistant", "content": "spy answer", "aos": {"answer_to": [first, second, third]}}])
        got = self.letters()
        self.assertEqual(got["pending"], [])
        self.assertEqual([(x["letter"], x["reason"]) for x in got["dropped"]], [(bad, "bad")])   # 中途的壞信也記 dropped
        self.assertEqual((self.box("new"), self.box("cur")), ([], []))
        self.assertIn("rejected", (self.stack / "mailbox_warning.txt").read_text())

    def test_a_slash_command_mid_turn_waits_for_the_next_turn(self):
        first = self.send({"role": "user", "content": "first"})
        seen = self.turn(SPY_LATE=json.dumps([{"role": "user", "content": "/clear"}, {"role": "user", "content": "after"}]))
        self.assertEqual(seen[0]["late"], [[], []])                              # 遇到 slash 就停手，後面的也不拿
        self.assertEqual(self.history(), [{"role": "user", "content": "first", "aos": {"letter": first}},
                                          {"role": "assistant", "content": "spy answer", "aos": {"answer_to": [first]}}])
        self.assertEqual((len(self.box("new")), len(self.box("cur"))), (1, 1))

    def test_a_late_letter_that_was_not_delivered_stays(self):
        first = self.send({"role": "user", "content": "first"})
        seen = self.turn(SPY_LATE=json.dumps([{"role": "user", "content": "second"}, {"role": "user", "content": "third"}]), SPY_DELIVER="0")
        self.assertEqual(seen[0]["late"], [[[None, "second"]], []])
        self.assertEqual(self.history(), [{"role": "user", "content": "first", "aos": {"letter": first}},
                                          {"role": "assistant", "content": "spy answer", "aos": {"answer_to": [first]}}])
        self.assertEqual(self.letters()["pending"], [])                         # 沒投出去的那封沒記進 pending
        self.assertEqual((len(self.box("new")), len(self.box("cur"))), (1, 1))

if __name__ == "__main__":
    unittest.main()
