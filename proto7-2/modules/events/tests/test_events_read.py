"""事件讀者手寫 fixture；保存端到位後再驗發布與中斷接續。"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))

import json  # noqa: E402
import signal  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from unittest.mock import patch  # noqa: E402
from base import MODULES, HERE  # noqa: E402
from aos7_fs import locked, write_json, read_json  # noqa: E402

EVENTS = os.path.join(MODULES, "events")
sys.path.insert(0, EVENTS)
import aos7_events_read as reader  # noqa: E402


def record(seq, **extra):
    """藍圖 §3 的完整事件。"""
    return dict({"v": 1, "stream": "a/obs", "seq": seq, "kind": "item", "capture": "published",
                 "source": {"node": "a", "round": seq, "run": 1}, "at": "2026-10-09T00:00:00+08:00",
                 "payload": {"item": seq}}, **extra)


class Fixtures(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aos72-events-")
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def segment(self, name, rows, tail=b""):
        with open(os.path.join(self.dir, name), "wb") as f:
            for row in rows:
                f.write(row if isinstance(row, bytes) else (json.dumps(row, ensure_ascii=False) + "\n").encode())
            f.write(tail)

    def state(self, **channel):
        write_json(os.path.join(self.dir, "state.json"), {"v": 1, "node": "a", "channels": {"obs": channel}})

    def seqs(self, result):
        return [r["seq"] for r in result["records"]]

    def cli(self, script, *args, env=None):
        return subprocess.run([sys.executable, os.path.join(EVENTS, script), "--events", self.dir, *args],
                              capture_output=True, text=True, timeout=20, env=env)


class TestEventsRead(Fixtures):
    def test_segments_and_limit(self):
        for name, seqs in (("obs.000000000001.jsonl", [1, 2]), ("obs.000000000003.jsonl", [3, 4]),
                           ("obs.active.jsonl", [5, 6]), ("must.active.jsonl", [90]), ("obs.7.jsonl", [70])):
            self.segment(name, [record(s) for s in seqs])
        self.state(next_seq=7)
        whole = reader.read(self.dir, "obs")
        self.assertEqual(self.seqs(whole), list(range(1, 7)))
        self.assertEqual(whole["errors"], [])
        first = reader.read(self.dir, "obs", limit=3)
        second = reader.read(self.dir, "obs", first["next_cursor"])
        self.assertEqual(self.seqs(first) + self.seqs(second), self.seqs(whole))
        self.assertEqual(second["next_cursor"], 7)

    def test_torn_tail_reconnects(self):
        self.segment("obs.active.jsonl", [record(1)], json.dumps(record(2)).encode())
        first = reader.read(self.dir, "obs")
        self.assertEqual((self.seqs(first), first["next_cursor"], first["errors"]), ([1], 2, []))
        self.assertEqual(reader.read(self.dir, "obs", 2)["next_cursor"], 2)
        with open(os.path.join(self.dir, "obs.active.jsonl"), "ab") as f:
            f.write(b"\n")
        self.assertEqual(self.seqs(reader.read(self.dir, "obs", 2)), [2])

    def test_bad_line_explains_one_missing_seq(self):
        self.segment("obs.active.jsonl", [record(1), b"broken\n", record(3), b"[]\n", record(5),
                                          b'{"seq":true}\n', record(7)])
        result = reader.read(self.dir, "obs")
        self.assertEqual(self.seqs(result), [1, 3, 5, 7])
        self.assertEqual([e["kind"] for e in result["errors"]], ["bad_line"] * 3)
        self.assertEqual(result["errors"][0], {"kind": "bad_line", "file": "obs.active.jsonl",
                                              "offset": len((json.dumps(record(1)) + "\n").encode())})

    def test_holes_and_retention(self):
        self.segment("obs.active.jsonl", [record(4), record(5)])
        self.state(dropped_upto=3, next_seq=6)
        r = reader.read(self.dir, "obs", 1)
        self.assertEqual(r["gaps"], [{"kind": "retention", "from": 1, "to": 3}])
        self.assertEqual(self.seqs(r), [4, 5])
        self.state(dropped_upto=0)
        r = reader.read(self.dir, "obs", 1)
        self.assertEqual((self.seqs(r), r["next_cursor"]), ([], 1))
        self.assertIn({"kind": "seq_hole", "from": 1, "to": 3}, r["errors"])
        self.segment("obs.active.jsonl", [record(1), b"bad\n", record(4)])
        r = reader.read(self.dir, "obs")
        self.assertEqual((self.seqs(r), r["next_cursor"]), ([1], 2))
        self.assertIn({"kind": "seq_hole", "from": 2, "to": 3}, r["errors"])
        self.state(acked_upto=3)
        self.assertEqual(self.seqs(reader.read(self.dir, "obs")), [1])
        self.state(dropped_upto=3)
        self.assertEqual(self.seqs(reader.read(self.dir, "obs")), [1, 4])

    def test_order_stops_and_bad_credit_does_not_carry(self):
        for seqs in ([1, 2, 2, 3], [1, 2, 1, 3]):
            self.segment("obs.active.jsonl", [record(s) for s in seqs])
            r = reader.read(self.dir, "obs")
            self.assertEqual((self.seqs(r), r["next_cursor"]), ([1, 2], 3))
            self.assertEqual(r["errors"][-1]["kind"], "seq_order")
        self.segment("obs.active.jsonl", [record(1), b"bad\n", record(2), record(4)])
        self.assertEqual(reader.read(self.dir, "obs")["errors"][-1]["kind"], "seq_hole")

    def test_retry_relists_once(self):
        self.segment("obs.active.jsonl", [record(1), record(3)])
        snapshot = reader._snapshot
        calls = []
        def rotate(*args):
            calls.append(1)
            if len(calls) == 2:
                self.segment("obs.active.jsonl", [record(1), record(2), record(3)])
            return snapshot(*args)
        with patch.object(reader, "_snapshot", side_effect=rotate):
            r = reader.read(self.dir, "obs")
        self.assertEqual((len(calls), self.seqs(r), r["errors"]), (2, [1, 2, 3], []))

    def test_no_cursor_does_not_skip_unlisted_front(self):
        """不給游標：列檔時前段剛被輪替走（只看到 3），不得從 3 起讀；重列後讀全。"""
        self.segment("obs.active.jsonl", [record(3)])
        self.state(next_seq=4)
        snapshot = reader._snapshot
        calls = []
        def rotate(*args):
            calls.append(1)
            if len(calls) == 2:
                self.segment("obs.000000000001.jsonl", [record(1), record(2)])
            return snapshot(*args)
        with patch.object(reader, "_snapshot", side_effect=rotate):
            r = reader.read(self.dir, "obs")
        self.assertEqual((len(calls), self.seqs(r), r["errors"]), (2, [1, 2, 3], []))

    def test_acked_hole_relists_before_retention(self):
        """must 已確認到 3、讀到 1 與 4：ack 不是淘汰證明，先重列；重列後讀全。"""
        self.segment("must.active.jsonl", [record(1), record(4)])
        write_json(os.path.join(self.dir, "state.json"), {"v": 1, "node": "a", "channels": {"must": {"acked_upto": 3}}})
        snapshot = reader._snapshot
        calls = []
        def relist(*args):
            calls.append(1)
            if len(calls) == 2:
                self.segment("must.active.jsonl", [record(1), record(2), record(3), record(4)])
            return snapshot(*args)
        with patch.object(reader, "_snapshot", side_effect=relist):
            r = reader.read(self.dir, "must")
        self.assertEqual((len(calls), self.seqs(r), r["gaps"]), (2, [1, 2, 3, 4], []))

    def test_cross_segment_hole_and_retry_retention(self):
        self.segment("obs.000000000001.jsonl", [record(1)])
        self.segment("obs.active.jsonl", [record(3)])
        r = reader.read(self.dir, "obs")
        self.assertEqual((self.seqs(r), r["next_cursor"]), ([1], 2))
        self.assertEqual(r["errors"], [{"kind": "seq_hole", "from": 2, "to": 2}])
        snapshot = reader._snapshot
        calls = []
        def rotate(*args):
            calls.append(1)
            if len(calls) == 2:
                self.state(dropped_upto=2)
            return snapshot(*args)
        with patch.object(reader, "_snapshot", side_effect=rotate):
            r = reader.read(self.dir, "obs", 2)
        self.assertEqual((self.seqs(r), r["errors"]), ([3], []))
        self.assertEqual(r["gaps"], [{"kind": "retention", "from": 2, "to": 2}])

    def test_filters_gaps_and_coverage(self):
        rows = [record(1, capture="sample"), record(2, capture="source_log"),
                record(3, kind="gap", payload={"why": "round_skip", "from": 7, "to": 9}),
                record(4, kind="gap", payload={"why": "source_reset_unknown"}),
                record(5, kind="gap", source={"node": "b"}, payload={"why": "other"}),
                record(6, capture="alien")]
        self.segment("obs.active.jsonl", rows)
        r = reader.read(self.dir, "obs", kind="no-match", source="a")
        self.assertEqual((r["records"], r["next_cursor"]), ([], 7))
        self.assertEqual(r["gaps"], [{"kind": "round_skip", "seq": 3, "source": rows[2]["source"], "from": 7, "to": 9},
                                    {"kind": "source_reset_unknown", "seq": 4, "source": rows[3]["source"]}])
        self.assertEqual([c["mode"] for c in r["coverage"]], ["sampled", "log_tail", "per_event", "per_event", "unknown"])
        self.assertEqual([c["from_seq"] for c in r["coverage"]], [1, 2, 3, 5, 6])
        r = reader.read(self.dir, "obs", kind="item", source="a", round=2, run=1, limit=1)
        self.assertEqual((self.seqs(r), r["next_cursor"]), ([2], 3))
        self.assertEqual(reader.read(self.dir, "obs", run=99)["next_cursor"], 7)
        self.assertEqual(reader.read(self.dir, "obs")["gaps"][-1]["kind"], "other")

    def test_empty_and_bad_state_and_text(self):
        self.assertEqual(reader.read(self.dir, "obs")["earliest_cursor"], 1)
        self.state(next_seq=8)
        r = reader.read(self.dir, "obs")
        self.assertEqual((r["next_cursor"], r["errors"]), (1, [{"kind": "seq_hole", "from": 1, "to": 7}]))
        self.state(next_seq=8, dropped_upto=7)
        self.assertEqual(reader.read(self.dir, "obs")["next_cursor"], 8)
        self.state(next_seq=8)
        r = reader.read(self.dir, "obs", 3)
        self.assertEqual((r["next_cursor"], r["errors"]), (3, [{"kind": "seq_hole", "from": 3, "to": 7}]))
        self.state(dropped_upto=5)
        self.assertEqual(reader.read(self.dir, "obs")["earliest_cursor"], 6)
        for content in (b"broken", b"[]"):
            self.segment("state.json", [], content)
            self.assertEqual(reader.read(self.dir, "obs")["errors"], [{"kind": "state_unreadable"}])
        self.segment("obs.active.jsonl", [record(1), b"bad\n", record(3, kind="gap", payload={"why": "round_skip"})])
        p = self.cli("aos7_events_read.py", "--text")
        self.assertEqual(p.returncode, 0, p.stderr)
        for text in ('1 item a {"item": 1}', "# gap", "# error", "# next_cursor 4"):
            self.assertIn(text, p.stdout)
        self.assertEqual(self.cli("aos7_events_read.py", "--ack", "1").returncode, 2)


class TestEventsPublish(Fixtures):
    def setUp(self):
        super().setUp()
        import aos7_events_pub
        self.pub = aos7_events_pub

    def publish(self, event_id, **kw):
        return self.pub.publish(self.dir, "item", event_id, {"x": 1}, must=True, node="a", **kw)

    def test_dup_usage_node_and_ack(self):
        first = self.publish("a/1")
        self.assertTrue(first["ok"])
        self.assertEqual(self.publish("a/1"), dict(first, dup=True))
        self.assertEqual(len(reader.read(self.dir, "must")["records"]), 1)
        with patch.object(self.pub.store, "append") as append:
            for kind, eid, payload, src in (("", "id", {}, None), ("k", "", {}, None),
                                          ("k", "x" * 129, {}, None), ("k", "id", {1}, None), ("k", "id", {}, [])):
                self.assertEqual(self.pub.publish(self.dir, kind, eid, payload, source=src)["why"], "usage")
            append.assert_not_called()
        self.assertTrue(self.pub.publish(self.dir, "item", "a/2", {}, must=True)["ok"])
        p = self.cli("aos7_events_read.py", "--channel", "must", "--ack", "1")
        self.assertEqual((p.returncode, json.loads(p.stdout)), (0, {"acked_upto": 1}))
        fresh = os.path.join(self.dir, "fresh")   # 新建時 config 不合 → store 丟 ValueError → usage、沒寫
        r = self.pub.publish(fresh, "item", "a/3", {}, node="a", config={"keep_segments": 0})
        self.assertEqual(r["why"], "usage")
        self.assertIsNone(self.pub.store.load_state(fresh))
        with locked(os.path.join(self.dir, "state.json")):
            p = self.cli("aos7_events_read.py", "--channel", "must", "--ack", "2")
        self.assertEqual(p.returncode, 4, p.stderr)

    def test_full_cli_and_lock_timeout(self):
        config = {"keep_segments": 1, "segment_bytes": 1}
        for i in range(20):
            result = self.publish("a/%d" % i, config=config)
            if not result["ok"]:
                break
        self.assertEqual(result["why"], "full")
        before = reader.read(self.dir, "must")["records"]
        args = ("--kind", "item", "--event-id", "full", "--payload", "{}", "--node", "a", "--must")
        p = self.cli("aos7_events_pub.py", *args)
        self.assertEqual(p.returncode, 3, p.stderr)
        self.assertEqual(reader.read(self.dir, "must")["records"], before)
        with locked(os.path.join(self.dir, "state.json")):
            p = self.cli("aos7_events_pub.py", *args)
        self.assertEqual(p.returncode, 4, p.stderr)

    def test_demo_waits_for_save_ack(self):
        """示範發布者：發後確認前被殺、或保存回 unknown，都不推進進度、不做下一件；重跑同 event_id 只留一筆。"""
        events, state, out = [os.path.join(self.dir, n) for n in ("events", "state.json", "out")]
        args = [sys.executable, os.path.join(EVENTS, "examples", "demo_pub.py"), "--events", events,
                "--node", "a", "--state", state, "--out", out, "--n", "3"]
        env = dict(os.environ, AOS7_TEST_HOOKS=os.path.join(HERE, "_hooks.py"))
        env.pop("AOS7_TEST_CRASH", None)
        p = subprocess.run(args, env=dict(env, AOS7_TEST_CRASH="events:demo-after-publish"), capture_output=True, timeout=20)
        self.assertEqual(p.returncode, -signal.SIGKILL, p.stderr)
        self.assertIsNone(read_json(state))
        self.assertFalse(os.path.exists(os.path.join(out, "item-2.txt")))
        with locked(os.path.join(events, "state.json")):
            p = subprocess.run(args, env=env, capture_output=True, timeout=20)
        self.assertEqual(p.returncode, 4, p.stderr)
        self.assertIsNone(read_json(state))
        self.assertFalse(os.path.exists(os.path.join(out, "item-2.txt")))
        p = subprocess.run(args, env=env, capture_output=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        r = reader.read(events, "must")
        self.assertEqual(([x["event_id"] for x in r["records"]], r["errors"]), (["a/demo/1", "a/demo/2", "a/demo/3"], []))

    def test_demo_crashes_three_items_per_point(self):
        for point in ("events:demo-after-publish", "events:after-append", "events:demo-after-work"):
            with self.subTest(point=point), tempfile.TemporaryDirectory(prefix="aos72-demo-") as root:
                events, state, out = [os.path.join(root, n) for n in ("events", "state.json", "out")]
                args = [sys.executable, os.path.join(EVENTS, "examples", "demo_pub.py"), "--events", events,
                        "--node", "a", "--state", state, "--out", out]
                env = dict(os.environ, AOS7_TEST_HOOKS=os.path.join(HERE, "_hooks.py"))
                env.pop("AOS7_TEST_CRASH", None)
                # 每次補完當件再提高 n，確保三次 kill 打在不同件號。
                for i in range(1, 4):
                    command = args + ["--n", str(i)]
                    p = subprocess.run(command, env=dict(env, AOS7_TEST_CRASH=point), capture_output=True, timeout=20)
                    self.assertEqual(p.returncode, -signal.SIGKILL, p.stderr)
                    p = subprocess.run(command, env=env, capture_output=True, timeout=20)
                    self.assertEqual(p.returncode, 0, p.stderr)
                p = subprocess.run(args + ["--n", "5"], env=env, capture_output=True, timeout=20)
                self.assertEqual(p.returncode, 0, p.stderr)
                r = reader.read(events, "must")
                self.assertEqual(r["errors"], [])
                self.assertEqual(self.seqs(r), list(range(1, 6)))
                self.assertEqual([rec["event_id"] for rec in r["records"]], ["a/demo/%d" % i for i in range(1, 6)])
                self.assertEqual(read_json(state), {"done_upto": 5})
                for i in range(1, 6):
                    with open(os.path.join(out, "item-%d.txt" % i)) as f:
                        self.assertEqual(f.read(), "item %d: ok\n" % i)


class TestNewbieCli(Fixtures):
    """第一次跑不靠 daemon：pub 不給 --event-id／--node 也能寫；--help 講清 obs／must。"""
    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(EVENTS, "aos7-events"), *args],
                              capture_output=True, text=True, timeout=20)

    def test_pub_defaults_without_daemon(self):
        events = os.path.join(self.dir, "n1", "events")
        outs = []
        for _ in range(2):
            p = self.run_cli("pub", "--events", events, "--kind", "hello", "--payload", '{"msg": "hi"}')
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            outs.append(json.loads(p.stdout))
        self.assertEqual([o["seq"] for o in outs], [1, 2])
        self.assertTrue(all(o["event_id"].startswith("auto/") for o in outs))
        self.assertNotEqual(outs[0]["event_id"], outs[1]["event_id"])
        import aos7_events_store as store
        self.assertEqual(store.load_state(events)["node"], "n1")   # 新建時 node＝上一層資料夾名
        recs = reader.read(events, "obs")["records"]
        self.assertEqual([(r["source"]["node"], r["payload"]) for r in recs], [("n1", {"msg": "hi"})] * 2)
        p = self.run_cli("pub", "--events", events, "--kind", "x", "--payload", "{}", "--event-id", "x/1")
        self.assertNotIn("event_id", json.loads(p.stdout))   # 自己給 id 時輸出格式不變
        p = self.run_cli("read", "--events", events, "--text")
        self.assertIn('1 hello n1 {"msg": "hi"}', p.stdout)

    def test_existing_state_node_wins_and_bad_state_stays_usage(self):
        events = os.path.join(self.dir, "n1", "events")
        import aos7_events_pub as pub
        self.assertTrue(pub.publish(events, "k", "e1", {}, node="other")["ok"])
        p = self.run_cli("pub", "--events", events, "--kind", "k", "--payload", "{}")
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertEqual(reader.read(events, "obs", 2)["records"][0]["source"]["node"], "other")
        with open(os.path.join(events, "state.json"), "w") as f:
            f.write("broken")
        p = self.run_cli("pub", "--events", events, "--kind", "k", "--payload", "{}")
        self.assertEqual((p.returncode, json.loads(p.stdout)["why"]), (2, "usage"))
        fresh = os.path.join(self.dir, "n2", "events")   # 明給壞 source.node 仍是用法錯，不被預設 node 蓋過
        for bad in ('{"node": ""}', '{"node": 0}'):
            p = self.run_cli("pub", "--events", fresh, "--kind", "k", "--payload", "{}", "--source", bad)
            self.assertEqual(p.returncode, 2, p.stdout)
        self.assertFalse(os.path.exists(fresh))

    def test_auto_id_printed_on_unknown(self):
        events = os.path.join(self.dir, "n1", "events")
        self.assertEqual(self.run_cli("pub", "--events", events, "--kind", "k", "--payload", "{}").returncode, 0)
        with locked(os.path.join(events, "state.json")):
            p = self.run_cli("pub", "--events", events, "--kind", "k", "--payload", "{}")
        out = json.loads(p.stdout)
        self.assertEqual((p.returncode, out["why"]), (4, "unknown"))
        self.assertTrue(out["event_id"].startswith("auto/"))

    def test_help_explains(self):
        top = self.run_cli("--help").stdout
        self.assertIn("aos7-events pub --help", top)
        pub_help = self.run_cli("pub", "--help").stdout
        for text in ("must＝", "ack", "--event-id", "不存在會自動建"):
            self.assertIn(text, pub_help)
        self.assertIn("--channel must --ack", self.run_cli("read", "--help").stdout)


if __name__ == "__main__":
    unittest.main()
