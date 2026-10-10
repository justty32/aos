"""事件包按職責分組的測試。"""
from _events_read import *


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



if __name__ == "__main__":
    unittest.main()
