"""llmcall 測試工具：獨立帳任務、人工時鐘、限時子程序與只讀 log 重放。"""
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent
TOP = PACK.parent.parent
sys.path[:0] = [str(TOP / "tests"), str(PACK), str(PACK.parent / "budget")]
from base import CoreCase  # noqa: E402
import _proc  # noqa: E402
import aos7_budget as bg  # noqa: E402
from aos7_fs import read_json, write_json  # noqa: E402

LLMCALL = str(PACK / "bin" / "aos7-llmcall")
BUDGET = str(PACK.parent / "budget" / "bin" / "aos7-budget")
R = 300
KEYS = ["v", "call_id", "logical", "kid", "key", "req_sha", "meter", "bound", "reserve", "outcome",
        "usage", "used", "overrun", "billing", "raw_sha", "text", "settle"]


def last_json(p):
    return json.loads(p.stdout.strip().splitlines()[-1])


def tree(path):
    """包含鎖檔的逐檔內容／檔名快照。"""
    path = Path(path)
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}


class LlmcallCase(CoreCase):
    """〔llmcall〕共用空間與獨立核帳。"""

    def setUp(self):
        super().setUp()
        self.node = Path(self.root) / "a"
        self.node.mkdir()
        self.bd = self.up()
        self.req = self.request("req.json")

    def up(self, budget="llm", amount=10000, holder="author", until=1000, gateway="llm.fake"):
        write_json(str(self.node / ".aos" / "round.json"), {"round": 5, "open": False})
        bd = self.node / "budget" / budget
        write_json(str(bd / "grant.json"), {"v": 1, "grant": "g1", "budget": budget, "holder": holder,
                   "resource": "llm.tokens", "gateway": gateway, "amount": amount,
                   "clock": "completed_tock", "from": 0, "until": until, "delegate": False})
        p = self.cli("init", "budget/" + budget, binary=BUDGET)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.popen("ledger", "budget/" + budget, binary=BUDGET)
        self.wait_for(lambda: (bd / "ledger.lock").exists())
        return bd

    def request(self, name, mode="ok", usage=R, **extra):
        path = self.node / name
        write_json(str(path), {"fake": dict(mode=mode, usage=usage, **extra)})
        return str(path)

    def cli(self, *args, binary=LLMCALL, env=None):
        return subprocess.run([sys.executable, binary, *map(str, args)], cwd=self.node,
                              capture_output=True, text=True, timeout=12, start_new_session=True,
                              env=dict(os.environ, **(env or {})))

    def popen(self, *args, binary=LLMCALL):
        p = subprocess.Popen([sys.executable, binary, *map(str, args)], cwd=self.node,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        _proc.track(self, p, group=True)
        return p

    def args(self, c="c", req=None, reserve=R, holder="author", budget="llm", extra=()):
        return ["call", "budget/" + budget, "--holder", holder, "--call", c, "--request", req or self.req,
                "--reserve", str(reserve), *extra]

    def call(self, c="c", **kw):
        return self.cli(*self.args(c, **kw))

    def cd(self, c="c", budget="llm"):
        return self.node / "llmcall" / budget / c

    def kid(self, c="c", budget="llm", holder="author"):
        return bg.kid_of(bg.make_key(budget, holder, c))

    def gwpath(self, c="c", budget="llm"):
        return self.node / "budget" / budget / "gateway" / (self.kid(c, budget) + ".json")

    def gw(self, c="c", budget="llm"):
        return read_json(str(self.gwpath(c, budget)))

    def sends(self, c="c"):
        remote = read_json(str(self.node / "llmcall" / "fake-remote.json"), {})
        return remote.get("sends", {}).get(c, 0)

    def arm(self, point):
        path = self.node / "llmcall" / ".crash"
        path.parent.mkdir(exist_ok=True)
        path.write_text(point)

    def disarm(self):
        (self.node / "llmcall" / ".crash").unlink(missing_ok=True)

    def assert_receipt(self, p, rc=0):
        self.assertEqual(p.returncode, rc, p.stdout + p.stderr)
        self.assertEqual(len(p.stdout.strip().splitlines()), 1)
        obj = last_json(p)
        self.assertEqual(list(obj), KEYS)
        self.assertEqual(obj["bound"], "soft")
        return obj

    def intent(self, c="c", point="after-intent", req=None):
        self.arm(point)
        p = self.call(c, req=req)
        self.assertEqual(p.returncode, -signal.SIGKILL, p.stdout + p.stderr)
        self.assertEqual(self.gw(c)["stage"], "intent")
        return p

    def adopt(self, c="c", obj=None):
        req = read_json(str(self.cd(c) / "request.json"))
        obj = obj or {"call_id": c, "req_sha": req["req_sha"], "reply": {
            "status": "ok", "billed": True, "body": "遲到原文", "usage": {"total_tokens": R}}}
        path = self.node / "adopt.json"
        write_json(str(path), obj)
        return self.cli("adopt", "budget/llm", "--holder", "author", "--call", c, "--raw", path)

    def audit(self, bd=None):
        """只讀 ledger.json 重放，不借用 budget 的轉移／驗證函式。"""
        ledger = read_json(str((bd or self.bd) / "ledger.json"))
        self.assertIsInstance(ledger, dict)
        available, inflight, used = ledger["initial"], 0, 0
        amounts, settled = {}, set()
        for seq, e in enumerate(ledger["log"], 1):
            self.assertEqual(e["seq"], seq)
            k, amount = e["kid"], e["amount"]
            if e["op"] == "reserve":
                self.assertNotIn(k, amounts)
                amounts[k] = amount
                available -= amount
                inflight += amount
            else:
                self.assertEqual(e["op"], "settle")
                self.assertIn(k, amounts)
                self.assertNotIn(k, settled)
                self.assertEqual(amount, amounts[k])
                self.assertIs(type(e["used"]), int)
                self.assertTrue(0 <= e["used"] <= amount)
                settled.add(k)
                available += amount - e["used"]
                inflight -= amount
                used += e["used"]
            self.assertEqual((e["available"], e["inflight"], e["used_total"]), (available, inflight, used))
            self.assertGreaterEqual(min(available, inflight, used), 0)
            self.assertEqual(available + inflight + used, ledger["initial"])
        self.assertEqual((ledger["available"], ledger["inflight"], ledger["used"], ledger["seq"]),
                         (available, inflight, used, len(ledger["log"])))
        self.assertEqual(set(ledger["ops"]), set(amounts))
        for k, rec in ledger["ops"].items():
            self.assertEqual(rec["stage"], "settled" if k in settled else "reserved")
        return ledger
