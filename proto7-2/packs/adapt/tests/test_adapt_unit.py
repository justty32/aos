"""〔adapt〕檢查器、鏈、每圈判定（純函式；packs/adapt/spec.md §2、§4、§6）。不起程序，跑得快；真 daemon 的矩陣在 test_adapt_flow.py。"""
import copy
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
sys.path.insert(0, PACK)

import aos7_adapt as A  # noqa: E402

ADAPT = os.path.join(PACK, "bin", "aos7-adapt")
EXAMPLE = os.path.join(PACK, "examples", "temp", "temp.json")


def example():
    with open(EXAMPLE) as f:
        return json.load(f)


def src(t_dc=None, rnd=10, seq=None, value=None):
    v = value if value is not None else {"t_dc": t_dc}
    doc = {"v": 1, "round": rnd, "value": v, "at": "x"}
    if seq is not None:
        doc["seq"] = seq
    return "ok", doc


class TestCheck(unittest.TestCase):
    """〔adapt〕檢查器：範例過；欄位、步、need、時間值錯都報，壞型別不拋例外。"""

    def rules(self, d):
        return sorted({(i["rule"], i["where"]) for i in A.check(d)})

    def test_example_passes_cli(self):
        r = subprocess.run([sys.executable, ADAPT, "check", EXAMPLE], capture_output=True, text=True)
        self.assertEqual((r.returncode, json.loads(r.stdout)), (0, []), r.stderr)

    def test_errors(self):
        d = example()
        cases = [
            (dict(d, extra=1), ("struct", "extra")),
            ({k: v for k, v in d.items() if k != "need"}, ("struct", "need")),
            (dict(d, sense="a/b"), ("type", "sense")),
            (dict(d, src="/abs/x.json"), ("type", "src")),
            (dict(d, src="../x.json"), ("type", "src")),
            (dict(d, src_clock="src/.aos/tock.json"), ("clock", "src_clock")),
            (dict(d, max_age="3s"), ("time", "max_age")),
            (dict(d, patience=-1), ("time", "patience")),
            (dict(d, stall=True), ("time", "stall")),
            (dict(d, need=["f"]), ("need", "need")),
            (dict(d, steps=d["steps"][1:]), ("step", "steps[0]")),
            (dict(d, steps=d["steps"] + [{"select": "x"}]), ("step", "steps[3]")),
            (dict(d, steps=[d["steps"][0], {"scale": {"mul": 0.1, "q": 0.01, "round": 1, "as": "c"}}]), ("err", "steps[1]")),
            (dict(d, steps=d["steps"][:2] + [{"threshold": {"ge": 80, "lt": 90, "as": "hot"}}]), ("type", "steps[2]")),
            (dict(d, steps=d["steps"][:2] + [{"threshold": {"ge": 80, "as": "c"}}]), ("struct", "steps[2]")),
            (dict(d, steps=d["steps"][:2] + [{"threshold": {"ge": 80}}]), ("struct", "steps[2]")),
            (dict(d, steps=[{"select": "a", "scale": {}}]), ("step", "steps[0]")),
            (dict(d, steps=[{"select": "a..b"}]), ("type", "steps[0]")),
        ]
        for bad, want in cases:
            with self.subTest(want=want):
                self.assertIn(want, self.rules(bad))

    def test_bad_types_no_exception(self):
        for bad in (None, [], "x", {"steps": "x", "need": 3, "sense": 1}, {"steps": [1, None, {"scale": 3}]}):
            out = A.check(bad)
            self.assertTrue(out and all(i["level"] == "error" for i in out), bad)

    def test_cli_rc1_on_error(self):
        path = os.path.join(os.environ.get("TMPDIR", "/tmp"), "aos72-test-adapt-check-%d.json" % os.getpid())
        try:
            with open(path, "w") as f:
                json.dump(dict(example(), max_age=1.5), f)
            r = subprocess.run([sys.executable, ADAPT, "check", path], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(json.loads(r.stdout)[0]["rule"], "time")
        finally:
            os.unlink(path)


class TestChain(unittest.TestCase):
    """〔adapt〕鏈：誤差界 |mul|×err+q；門檻跨誤差帶＝null；選不到、不是數字走 unknown 分支；omitted 列得出。"""

    def run_(self, t_dc, steps=None, value=None):
        return A.run_chain(steps or example()["steps"], src(t_dc, value=value)[1])

    def test_threshold_band(self):
        """誤差 0.05：80.1 判 true；80.0（區間 79.95～80.05 跨 80）判 null；79.9、79.0 判 false。"""
        for t_dc, hot in ((801, True), (800, None), (799, False), (790, False)):
            with self.subTest(t_dc=t_dc):
                ch = self.run_(t_dc)
                self.assertEqual(ch["out"]["hot"], hot, ch)
                self.assertEqual(ch["band"], [] if hot is not None else ["hot"])
                self.assertAlmostEqual(ch["out"]["c"], t_dc / 10)
                self.assertEqual(ch["err"], {"c": 0.05})

    def test_err_propagation(self):
        steps = [{"select": "value.x"}, {"scale": {"mul": -2, "q": 0.5, "round": 0}},
                 {"scale": {"mul": 0.5, "q": 0.25, "as": "y"}}, {"threshold": {"lt": 0, "as": "neg"}}]
        ch = self.run_(None, steps, value={"x": 3, "other": {"a": 1}})
        self.assertEqual(ch["out"], {"y": -3.0, "neg": True})
        self.assertEqual(ch["err"], {"y": 0.5})           # 0.5×(2×0+0.5)+0.25
        self.assertEqual(ch["omitted"], ["value.other.a"])
        self.assertEqual([t["step"] for t in ch["trace"]], ["select", "scale", "scale", "threshold"])

    def test_fail_reasons(self):
        self.assertEqual(self.run_(None, value={"nope": 1})["fail"], "select_missing")
        self.assertEqual(self.run_(None, value={"t_dc": "hot"})["fail"], "not_number")
        self.assertEqual(self.run_(None, value={"t_dc": True})["fail"], "not_number")


class TestEvaluate(unittest.TestCase):
    """〔adapt〕每圈判定：耐性撐舊值、效期用來源鐘、停太久、reset 作廢舊依據、skipped 不重算、absent。"""

    def setUp(self):
        self.d = example()
        self.fr = A.new_frame("temp", A.sha(self.d), 1)

    def step(self, my_round, ct, s, d=None):
        self.fr, reg = A.evaluate(d or self.d, self.fr, my_round, ct, s)
        return reg

    def test_ok_then_patience_then_unknown(self):
        r = self.step(2, 10, src(801, rnd=10, seq=1))
        self.assertEqual((r["state"], r["value"], r["age_src_rounds"], r["src_state"]),
                         ("ok", {"c": 80.1, "hot": True}, 0, "advancing"))
        good = r["basis"]
        bad = ("unknown", ("src_bad", "半寫"))
        for k, my in enumerate((3, 4), 1):          # patience 2：第 1、2 回合撐住
            r = self.step(my, 11, bad)
            self.assertEqual((r["state"], r["basis"], r["why"], r["held"]), ("ok", good, "src_bad", k))
        r = self.step(5, 12, bad)
        self.assertEqual((r["state"], r["value"], r["why"]), ("unknown", None, "src_bad"))
        self.assertEqual(r["last"]["basis"], good)
        r = self.step(6, 12, src(790, rnd=12, seq=2))
        self.assertEqual((r["state"], r["value"]["hot"]), ("ok", False))

    def test_expired_by_source_clock(self):
        self.step(2, 10, src(801, rnd=10))
        for my, ct, state in ((3, 13, "ok"), (4, 14, "unknown")):    # max_age 3：年齡 4 才過期
            r = self.step(my, ct, src(801, rnd=10))
            self.assertEqual(r["state"], state, r)
        self.assertEqual(r["why"], "expired")
        # 撐舊值時也看效期
        self.fr = A.new_frame("temp", A.sha(self.d), 1)
        self.step(2, 10, src(801, rnd=10))
        r = self.step(3, 14, ("unknown", ("src_unreadable", "EIO")))
        self.assertEqual((r["state"], r["why"]), ("unknown", "expired"))

    def test_stall_option(self):
        d = dict(self.d, stall=3)
        self.step(2, 10, src(801, rnd=10), d)
        states = [self.step(my, 10, src(801, rnd=10), d) for my in range(3, 8)]
        self.assertEqual([(r["stall_rounds"], r["state"]) for r in states],
                         [(1, "ok"), (2, "ok"), (3, "ok"), (4, "unknown"), (5, "unknown")])
        self.assertEqual(states[-1]["why"], "stalled")
        self.assertIsNotNone(states[-1]["last"])
        r = self.step(8, 11, src(801, rnd=11), d)
        self.assertEqual((r["state"], r["src_state"], r["stall_rounds"]), ("ok", "advancing", 0))
        # 預設 stall null：只報不翻
        self.fr = A.new_frame("temp", A.sha(self.d), 1)
        self.step(2, 10, src(801, rnd=10))
        r = [self.step(my, 10, src(801, rnd=10)) for my in range(3, 10)][-1]
        self.assertEqual((r["state"], r["src_state"], r["stall_rounds"]), ("ok", "stalled", 7))

    def test_same_round_not_double_counted(self):
        self.step(2, 10, src(801, rnd=10))
        self.step(3, 10, src(801, rnd=10))
        r = self.step(3, 10, src(801, rnd=10))     # 同一回合再算一次（重起後重播）
        self.assertEqual(r["stall_rounds"], 1)

    def test_reset_voids_old_basis(self):
        self.step(2, 57, src(801, rnd=57, seq=40))
        r = self.step(3, 0, src(801, rnd=57, seq=40))       # 來源重建：鐘倒退，舊檔還在
        self.assertEqual((r["state"], r["src_state"], r["why"]), ("unknown", "reset", "void_basis"))
        self.assertTrue(r["last"]["void"])
        r = self.step(4, 60, src(801, rnd=57, seq=40))      # 新鐘爬過舊回合，舊檔仍作廢
        self.assertEqual((r["state"], r["src_state"], r["why"]), ("unknown", "reset", "void_basis"))
        r = self.step(5, 61, ("unknown", ("src_unreadable", "x")))   # 作廢的依據不靠耐性撐
        self.assertEqual(r["state"], "unknown")
        r = self.step(6, 62, src(790, rnd=62, seq=1))
        self.assertEqual((r["state"], r["src_state"], r["basis"]["src_round"]), ("ok", "advancing", 62))
        # 檔的回合倒退也算 reset
        r = self.step(7, 63, src(790, rnd=5, seq=2))
        self.assertEqual((r["state"], r["src_state"]), ("unknown", "reset"))

    def test_skipped_counts_gaps_once(self):
        self.step(2, 10, src(801, rnd=10, seq=1))
        self.assertEqual(self.step(3, 11, src(801, rnd=11, seq=5))["skipped"], 3)
        self.assertEqual(self.step(4, 12, src(801, rnd=11, seq=5))["skipped"], 3)      # 同一版不重算
        self.assertEqual(self.step(5, 13, src(801, rnd=13, seq=6))["skipped"], 3)
        self.assertEqual(self.step(6, 14, src(801, rnd=14, seq=2))["skipped"], 3)      # 號變小不加，跟著走
        self.assertEqual(self.step(7, 15, src(801, rnd=15, seq=4))["skipped"], 4)
        self.assertEqual(self.step(8, 16, src(801, rnd=16))["skipped"], 4)              # 沒帶 seq：不管

    def test_absent_and_band_and_clock_unknown(self):
        r = self.step(2, 10, ("missing", None))
        self.assertEqual((r["state"], r["why"]), ("absent", "src_missing"))
        r = self.step(3, 10, src(800, rnd=10))
        self.assertEqual((r["state"], r["why"], r["value"]), ("unknown", "within_error_band", None))
        self.assertEqual(r["trace"][-1]["v"], None)
        r = self.step(4, 10, src(801, rnd=10))
        self.assertEqual(r["state"], "ok")
        r = self.step(5, None, src(801, rnd=10))           # 來源鐘不知道：耐性分支
        self.assertEqual((r["state"], r["why"], r["src_state"], r["age_src_rounds"]),
                         ("ok", "clock_unknown", "unknown", None))

    def test_frame_not_mutated(self):
        before = copy.deepcopy(self.fr)
        A.evaluate(self.d, self.fr, 2, 10, src(801, rnd=10, seq=3))
        self.assertEqual(self.fr, before)


if __name__ == "__main__":
    unittest.main()
