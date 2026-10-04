"""budget 包測試共用：預算資料夾、帳任務子程序、call 子程序、獨立核帳。

獨立核帳（audit）不用包裡的程式，只讀檔重算：帳的 log 每一筆（＝每次持久轉移，log 與餘額同一次原子寫入）
重放後都要「可用＋在途＋已用＝初始額度」且非負；每個 K 最多一次 reserve、一次 settle；後端受理計數＝有支用的效果數
（同 K 第二次效果會讓計數多出來）；結算量＝入口終局回條的 used；效果只能經入口（有效果就有入口紀錄）。
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
TOP = os.path.dirname(os.path.dirname(PACK))
sys.path.insert(0, os.path.join(TOP, "tests"))
sys.path.insert(0, PACK)

from base import CoreCase  # noqa: E402
import _proc  # noqa: E402
from aos7_fs import read_json, write_json  # noqa: E402

BUDGET = os.path.join(PACK, "bin", "aos7-budget")
EXAMPLES = os.path.join(PACK, "examples")
PY = sys.executable


def grant(**kw):
    g = {"v": 1, "grant": "g1", "budget": "demo", "holder": "api", "resource": "fakeapi.calls", "gateway": "fakeapi",
         "amount": 3, "clock": "completed_tock", "from": 0, "until": 1000, "delegate": False}
    g.update(kw)
    return g


def set_clock(node, c, open_=False):
    """把本 node 的 completed_tock 設成 c（closed 回合 c；open 時寫 round c+1）。"""
    write_json(os.path.join(node, ".aos", "round.json"), {"round": c + 1 if open_ else c, "open": open_})


class BudgetMixin:
    """要 self.root；node 預設 <root>/a。"""

    def setup_budget(self, node, g=None, init=True, clock=5):
        os.makedirs(os.path.join(node, ".aos"), exist_ok=True)
        if clock is not None:
            set_clock(node, clock)
        bd = os.path.join(node, "budget", "demo")
        os.makedirs(bd, exist_ok=True)
        write_json(os.path.join(bd, "grant.json"), g or grant())
        if init:
            r = self.cli(node, "init", "budget/demo")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return bd

    def cli(self, node, *args, timeout=30, env=None):
        return subprocess.run([PY, BUDGET, *args], cwd=node, capture_output=True, text=True, timeout=timeout,
                              start_new_session=True, env=dict(os.environ, **env) if env else None)

    def call_args(self, request, holder="api", payload=None, extra=()):
        a = ["call", "budget/demo", "--holder", holder, "--request", request, *extra]
        if payload is not None:
            a += ["--payload", payload]
        return a

    def call(self, node, request, **kw):
        """跑一次 call，回 (退出碼, 最後一行 JSON)。"""
        p = self.cli(node, *self.call_args(request, **kw))
        return p.returncode, last_json(p.stdout)

    def popen(self, node, *args):
        p = subprocess.Popen([PY, BUDGET, *args], cwd=node, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, start_new_session=True)
        _proc.track(self, p, group=True)
        return p

    def start_ledger(self, node):
        return self.popen(node, "ledger", "budget/demo")

    def payload(self, node, name, **kw):
        path = os.path.join(node, name)
        write_json(path, kw)
        return path

    def crash_at(self, bd, point):
        with open(os.path.join(bd, ".crash"), "w") as f:
            f.write(point)

    def ledger(self, bd):
        return read_json(os.path.join(bd, "ledger.json")) or {}

    def backend(self, bd):
        return read_json(os.path.join(bd, "backend.json")) or {"accepted": 0, "effects": {}}

    def gw(self, bd, kid):
        return read_json(os.path.join(bd, "gateway", kid + ".json"))

    def wait_for(self, pred, timeout=10, msg="timeout"):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            v = pred()
            if v:
                return v
            time.sleep(0.02)
        self.fail(msg)

    # ---------- 獨立核帳 ----------

    def audit(self, bd, final=False):
        """重放帳的 log 與後端、入口紀錄（見檔頭）。final＝全部終局：在途 0、已用＝後端實際受理量。回帳。"""
        L = read_json(os.path.join(bd, "ledger.json"))
        self.assertIsInstance(L, dict, "ledger.json 讀不到")
        init = L["initial"]
        avail, infl, used, seq = init, 0, 0, 0
        reserved, settled, amounts = set(), {}, {}
        for e in L["log"]:
            seq += 1
            self.assertEqual(e["seq"], seq, "log seq 不連續")
            k, amt = e["kid"], e["amount"]
            if e["op"] == "reserve":
                self.assertNotIn(k, reserved, "同一個 K 預留兩次")
                reserved.add(k)
                amounts[k] = amt
                avail, infl = avail - amt, infl + amt
            else:
                self.assertEqual(e["op"], "settle")
                self.assertIn(k, reserved, "沒預留就結算")
                self.assertNotIn(k, settled, "同一個 K 結算兩次")
                self.assertIn(e["used"], (0, amounts[k]))
                settled[k] = e["used"]
                infl, used, avail = infl - amounts[k], used + e["used"], avail + amounts[k] - e["used"]
            self.assertEqual((e["available"], e["inflight"], e["used_total"]), (avail, infl, used), e)
            self.assertTrue(avail >= 0 and infl >= 0 and used >= 0, e)
            self.assertEqual(avail + infl + used, init, e)
        self.assertEqual((L["available"], L["inflight"], L["used"], L["seq"]), (avail, infl, used, seq))
        for k, rec in L["ops"].items():
            self.assertIn(k, reserved)
            self.assertEqual(rec["stage"], "settled" if k in settled else "reserved", k)
        b = self.backend(bd)
        spent = {k: e for k, e in b["effects"].items() if e["used"] > 0}
        self.assertEqual(b["accepted"], len(spent), "後端受理計數跟效果數不同：同 K 效果超過一次？")
        for k in b["effects"]:
            self.assertIsNotNone(self.gw(bd, k), "後端有效果、入口沒紀錄（繞過入口）")
        for k, u in settled.items():
            g = self.gw(bd, k)
            self.assertEqual((g["stage"], g["used"]), ("done", u), k)
            eff = b["effects"].get(k)
            if g["outcome"] in ("accepted", "failed"):
                self.assertIsNotNone(eff, "結算有支用、後端卻沒效果")
                self.assertEqual(eff["used"], u)
            else:
                self.assertTrue(eff is None or eff["used"] == 0, "取消／拒絕的 K 後端卻有支用")
        if final:
            self.assertEqual(infl, 0, "還有在途")
            self.assertEqual(used, sum(e["used"] for e in spent.values()), "已用跟後端實際受理量不同")
        return L


def last_json(out):
    lines = (out or "").strip().splitlines()
    try:
        return json.loads(lines[-1]) if lines else None
    except ValueError:
        return None


class BudgetCase(BudgetMixin, CoreCase):
    pass
