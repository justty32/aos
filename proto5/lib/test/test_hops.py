"""aos_hops：AOS_HOPS 沒設什麼都不寫；設了一行一件；分析把牆上時間切成一跳一跳（2026-09-24 tick-gap）。"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import aos_hops  # noqa: E402


def rec(t, who, ev, **kw):
    return dict({"t": t, "pid": kw.pop("pid", 1), "who": who, "ev": ev}, **kw)


class MarkTest(unittest.TestCase):
    def test_off_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(aos_hops.ENV, None)
            aos_hops.mark("cpu", "pick", request="x")
            self.assertEqual(os.listdir(d), [])
            self.assertFalse(aos_hops.on())

    def test_on_appends_one_line_each(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "hops.jsonl")
            with mock.patch.dict(os.environ, {aos_hops.ENV: path}):
                aos_hops.mark("cpu", "pick", request="a")
                aos_hops.mark("agent", "begin", boot=True, agent="bob")
            with open(path) as f:
                lines = [json.loads(x) for x in f]
            self.assertEqual([(x["who"], x["ev"]) for x in lines], [("cpu", "pick"), ("agent", "begin")])
            self.assertEqual(lines[0]["request"], "a")
            self.assertIn("boot", lines[1])
            if lines[1]["boot"] is not None:          # Linux：行程開始時間不會比現在晚
                self.assertLessEqual(lines[1]["boot"], lines[1]["t"] + 0.02)

    def test_unwritable_path_is_ignored(self):
        with mock.patch.dict(os.environ, {aos_hops.ENV: "/nonexistent-dir/x/hops.jsonl"}):
            aos_hops.mark("cpu", "pick")                # 不丟例外


class AnalyzeTest(unittest.TestCase):
    def records(self):
        """一輪：say 投輸入 → kernel 派 agent → agent 送 think → kernel 放工作 → llm → 回音叫醒 → 派 agent → 結清退 0。"""
        return [
            rec(0.0, "agent", "end", agent="bob", code=102),
            rec(5.0, "wake", "sent", agent="bob"),
            rec(5.05, "kernel", "begin", pid=10),
            rec(5.06, "kernel", "req", pid=10, name="aa-bob-wake.json", method="wake", proc="agent-bob"),
            rec(5.07, "kernel", "dispatch", pid=10, proc="agent-bob", cpu="default/0", request="k-1.json"),
            rec(5.20, "cpu", "pick", request="k-1.json"),
            rec(5.23, "agent", "begin", agent="bob"),
            rec(5.24, "agent", "send", agent="bob", kind="think", jobs=["aw-bob-1-0"]),
            rec(5.25, "agent", "end", agent="bob", code=102),
            rec(5.29, "kernel", "begin", pid=11),
            rec(5.30, "kernel", "req", pid=11, name="aw-bob-1-0.json", method="add", proc="aw-bob-1-0", wake="agent-bob"),
            rec(5.31, "kernel", "dispatch", pid=11, proc="aw-bob-1-0", cpu="llm/0", request="k-2.json"),
            rec(5.42, "cpu", "done", request="k-1.json"),
            rec(5.45, "cpu", "pick", request="k-2.json"),
            rec(5.48, "llm", "http_start", batch="aw-bob-1"),
            rec(7.48, "llm", "http_end", batch="aw-bob-1"),
            rec(7.49, "llm", "end", batch="aw-bob-1"),
            rec(7.60, "cpu", "done", request="k-2.json"),
            rec(7.64, "kernel", "begin", pid=12),
            rec(7.65, "kernel", "resp", pid=12, proc="aw-bob-1-0", cpu="llm/0", code=0),
            rec(7.66, "kernel", "reply", pid=12, name="aw-bob-1-0.json", wake="agent-bob"),
            rec(8.66, "kernel", "begin", pid=13),
            rec(8.67, "kernel", "dispatch", pid=13, proc="agent-bob", cpu="default/1", request="k-3.json"),
            rec(8.80, "cpu", "pick", request="k-3.json"),
            rec(8.83, "agent", "begin", agent="bob"),
            rec(8.84, "agent", "end", agent="bob", code=0),
        ]

    def test_partition_sums_to_wall_and_names_hops(self):
        table, wall = aos_hops.hops(aos_hops.timeline(self.records(), "bob"))
        self.assertAlmostEqual(sum(sum(v) for k, v in table.items() if k != aos_hops.IDLE), wall, places=3)
        self.assertAlmostEqual(wall, (8.84 - 5.0) * 1000, places=3)
        self.assertAlmostEqual(sum(table[aos_hops.MODEL]), 2000, places=3)
        self.assertAlmostEqual(sum(table[aos_hops.IDLE]), 5000, places=3)     # 閒著那段另記
        wait = [k for k in table if k.startswith("⑮")]
        self.assertEqual(len(wait), 1)
        self.assertAlmostEqual(sum(table[wait[0]]), 1010, places=3)            # 叫醒後等下一格才派

    def test_other_agents_are_ignored(self):
        records = self.records() + [rec(6.0, "agent", "begin", agent="amy"), rec(6.1, "cpu", "pick", request="zz")]
        self.assertEqual(len(aos_hops.timeline(records, "bob")), len(aos_hops.timeline(self.records(), "bob")))

    def test_report_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "hops.jsonl")
            with open(path, "w") as f:
                for r in self.records():
                    f.write(json.dumps(r) + "\n")
                f.write("not json\n")
            out = json.loads(aos_hops.report(path, as_json=True))
            self.assertEqual(list(out), ["bob"])
            self.assertEqual(out["bob"]["wall_ms"], 3840)
            self.assertIn("bob", aos_hops.report(path))


if __name__ == "__main__":
    unittest.main()
