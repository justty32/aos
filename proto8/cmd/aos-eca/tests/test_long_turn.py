"""Test that an eca turn longer than the old 600 s limit (scaled down) is not failed when cli.json has no timeout_ms (11-15: 0 or omitted = no limit), that a quiet turn only gets the quiet.json mark (no kill, no cooldown, letters answered), and that a written timeout_ms still limits the turn."""
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
# 跑 aos-eca-turn 之前把「很久沒動靜」的門檻從 600 秒縮成 0.3 秒、每 0.05 秒看一次（舊的 600 秒上限就照這個比例：假輪跑 1.5 秒）
SPY = """import runpy, sys
sys.argv[0] = %(turn)r
sys.path[:0] = [%(py)r, %(lib)r, %(eca)r]
from agent import quiet
quiet.AFTER_S, quiet.POLL_S, quiet.REFRESH_S = 0.3, 0.05, 0.1
runpy.run_path(%(turn)r, run_name="__main__")
"""
# 假的 claude -p：讀完題目、安靜 1.5 秒（中途看一眼 stack 有沒有 quiet.json，記下來），再印一行 result
FAKE = """#!%(python)s
import json, os, sys, time, uuid
argv = sys.argv[1:]
sid = argv[argv.index("--session-id") + 1] if "--session-id" in argv else str(uuid.uuid4())
sys.stdin.read()
seen = None
for _ in range(30):
    time.sleep(0.05)
    p = os.path.join(os.environ["AOS_STACK"], "quiet.json")
    if seen is None and os.path.exists(p):
        with open(p) as f:
            seen = json.load(f)
with open(os.environ["FAKE_SEEN"], "w") as f:
    json.dump(seen, f)
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "slow answer", "session_id": sid}))
"""


class LongTurn(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="eca-long-")
        self.addCleanup(tmp.cleanup)
        self.t = Path(tmp.name)
        self.defn, self.ws, self.stack, self.home, self.bin = (self.t / n for n in ("def", "ws", "stack", "home", "bin"))
        for d in (self.defn, self.ws, self.stack, self.home, self.bin):
            d.mkdir()
        (self.bin / "claude").write_text(FAKE % {"python": sys.executable})
        (self.bin / "claude").chmod(0o755)
        self.spy = self.t / "spy_turn.py"
        self.spy.write_text(SPY % {"turn": str(TURN), "py": str(PROTO / "lib"), "lib": str(PROTO / "lib"), "eca": str(PROTO / "cmd" / "aos-eca")})
        self.seen = self.t / "seen.json"
        subprocess.run(["aos-post", "init", str(self.stack / "queue")], env=self.env(), check=True, capture_output=True)

    def env(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("AOS_", "CLAUDE"))}
        bins = [str(self.bin)] + [str(PROTO / "bin")] + sorted(str(p) for p in (PROTO / "cmd").glob("*/bin"))
        env.update(PATH=":".join(bins + [env.get("PATH", "")]), HOME=str(self.home), AOS_STACK=str(self.stack),
                   AOS_WS=str(self.ws), FAKE_SEEN=str(self.seen), PYTHONDONTWRITEBYTECODE="1")
        return env

    def send(self, body):
        r = subprocess.run(["aos-post", "send", "--ordered", str(self.stack / "queue")], check=True, capture_output=True,
                           input=json.dumps(body), env=self.env(), text=True)
        return r.stdout.strip()

    def turn(self):
        return subprocess.run([sys.executable, str(self.spy), "--on-empty", "idle", str(self.defn)], env=self.env(),
                              capture_output=True, text=True, timeout=60)

    def history(self):
        return [json.loads(l) for l in (self.stack / "history.jsonl").read_text().splitlines()]

    def test_no_timeout_ms_lets_a_long_quiet_turn_finish_with_only_a_quiet_mark(self):
        (self.defn / "cli.json").write_text(json.dumps({"kind": "claude"}))
        a = self.send({"role": "user", "content": "take your time"})
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.history()[-1], {"role": "assistant", "content": "slow answer", "aos": {"answer_to": [a]}})
        seen = json.loads(self.seen.read_text())
        self.assertIsNotNone(seen, "quiet.json never appeared during the quiet turn")
        self.assertEqual((seen["quiet"], seen["what"]), (True, "cli_turn"))
        self.assertIsInstance(seen["pid"], int)
        self.assertFalse((self.stack / "quiet.json").exists())          # 這輪結束就收掉
        self.assertFalse((self.stack / "cooldown.json").exists())       # 慢不算失敗：沒冷卻
        letters = json.loads((self.stack / "letters.json").read_text())
        self.assertEqual(letters.get("dropped", []), [])
        self.assertEqual(letters["pending"], [])

    def test_a_written_timeout_ms_still_limits_the_turn(self):
        (self.defn / "cli.json").write_text(json.dumps({"kind": "claude", "timeout_ms": 300}))
        self.send({"role": "user", "content": "too slow for 300 ms"})
        r = self.turn()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("CliFailed", r.stderr)
        self.assertIn("did not finish within", r.stderr)
        self.assertTrue((self.stack / "cooldown.json").exists())


if __name__ == "__main__":
    unittest.main()
