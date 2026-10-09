"""〔modules〕可選模組（不在核心）：counter 示範任務、歷史 module（modules/README.md）。

從 tests/test_subdaemon_modules.py 的 TestModules 與 tests/test_matrix_misc.py 的 TestHistoryMaxLines（A2-10）搬來，內容未改。
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tests"))  # tests/：base、_matrix

import argparse  # noqa: E402
import importlib.util  # noqa: E402
import unittest  # noqa: E402

from base import MODULES, DaemonCase  # noqa: E402
from _matrix import MatrixCase  # noqa: E402
from aos7_fs import read_json, write_json  # noqa: E402
from aos7_taskside import read_jsonl  # noqa: E402


class TestModules(DaemonCase):
    """〔observe〕counter 示範任務與歷史 module（F62）。"""
    def test_counter_reads_previous_state_and_gets_tock(self):
        node = self.mknode("a", [{"name": "c", "mode": "keep",
                                  "argv": ["python3", os.path.join(MODULES, "counter.py"), "2"]}], interval_ms=100)
        self.start_daemon(register=["a"])
        st_path = os.path.join(self.slot(node, "c"), "state.json")
        self.wait_for(lambda: (read_json(st_path) or {}).get("count", 0) >= 6, 20)
        st = read_json(st_path)
        self.assertGreaterEqual(len(st["runs"]), 3)
        self.assertEqual(st["runs"], sorted(set(st["runs"])))   # run 遞增，同一個槽接著數

    def test_history_module_appends_last_rounds(self):
        node = self.mknode("a", [{"name": "j", "argv": ["true"]},
                                 {"name": "history", "mode": "keep",
                                  "argv": ["python3", os.path.join(MODULES, "history.py"), "--status",
                                           "--max-lines", "1000"]}], interval_ms=100)
        self.start_daemon(register=["a"])
        hp = os.path.join(node, "history", "a.jsonl")
        self.wait_for(lambda: len(read_jsonl(hp)) >= 8, 20)
        rows = read_jsonl(hp)
        covered = []
        for r in rows:
            if "gap" in r:
                covered += list(range(r["gap"][0], r["gap"][1] + 1))
            else:
                covered.append(r["round"])
        self.assertEqual(covered, list(range(covered[0], covered[0] + len(covered))))   # 跳號都記了 gap
        self.assertTrue(read_jsonl(os.path.join(node, "history", "daemon-events.jsonl")))


class TestHistoryMaxLines(MatrixCase):
    """〔observe〕歷史 module 的 --max-lines 套到事件檔（A2-10，F62）。"""
    def test_max_lines_applies_to_daemon_events(self):
        spec = importlib.util.spec_from_file_location("aos7_matrix_history", os.path.join(MODULES, "history.py"))
        hist = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hist)
        node = self.mknode("a")
        out = os.path.join(node, "history")
        me = {"root": self.root, "node": node, "node_id": "a", "task": os.path.join(node, ".aos", "tasks", "h")}
        args = argparse.Namespace(src=["a"], status=True, out=out, max_lines=2)
        st = {}
        for k in range(1, 6):
            write_json(os.path.join(node, ".aos", "last-round.json"), {"round": k, "ended": [], "alive": []})
            write_json(os.path.join(self.root, ".aosd", "status.json"), {"last_event": {"ev": "e%d" % k, "at": str(k)}})
            hist.once(me, args, lambda p: None, st)
        rows = read_jsonl(os.path.join(out, "daemon-events.jsonl"))
        self.assertLessEqual(len(rows), 2, "daemon-events.jsonl 沒套 --max-lines：%d 行" % len(rows))
        self.assertEqual(rows[-1]["ev"], "e5")
        self.assertLessEqual(len(read_jsonl(os.path.join(out, "a.jsonl"))), 2)


class TestHistoryNames(MatrixCase):
    """〔observe〕來源檔名可逆編碼，且不占 daemon 事件檔名（R8-17）。"""

    def sample(self, ids, status=False):
        spec = importlib.util.spec_from_file_location("aos7_names_history", os.path.join(MODULES, "history.py"))
        hist = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hist)
        rows = {}
        for nid in ids:
            node = self.mknode(nid)
            rows[nid] = {"round": 1, "ended": [], "alive": [], "source": nid}
            write_json(os.path.join(node, ".aos", "last-round.json"), rows[nid])
        out = os.path.join(self.root, "history")
        me = {"root": self.root, "node_id": ids[0]}
        args = argparse.Namespace(src=ids, status=status, out=out, max_lines=0)
        self.assertTrue(hist.once(me, args, lambda p: None, {}))
        return out, rows

    def test_slash_and_plus_sources_have_separate_histories(self):
        out, rows = self.sample(["a/b", "a+b", "a%2Bb", "plain"])
        for nid, name in [("a/b", "a+b"), ("a+b", "a%2Bb"), ("a%2Bb", "a%252Bb"), ("plain", "plain")]:
            self.assertEqual(read_jsonl(os.path.join(out, name + ".jsonl")), [rows[nid]])

    def test_daemon_events_source_does_not_mix_with_status(self):
        event = {"ev": "register", "at": "1"}
        write_json(os.path.join(self.root, ".aosd", "status.json"), {"last_event": event})
        out, rows = self.sample(["daemon-events"], status=True)
        self.assertEqual(read_jsonl(os.path.join(out, "daemon-events.jsonl")), [event])
        self.assertEqual(read_jsonl(os.path.join(out, "daemon%2Devents.jsonl")), [rows["daemon-events"]])


if __name__ == "__main__":
    unittest.main()
