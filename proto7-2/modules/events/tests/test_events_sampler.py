"""事件包按職責分組的測試。"""
from _events_store import *


class TestSampler(EventsCase):
    def setUp(self):
        super().setUp()
        node = os.path.join(self.root, "n")
        task = os.path.join(node, ".aos", "tasks", "events")
        os.makedirs(task)
        self.me = {"root": self.root, "node": node, "node_id": "n", "task": task}
        self.args = argparse.Namespace(src=None, status=False, daemon_log=False, out=self.d,
                                       keep=4, segment_bytes=4096)
        self.st = store.recover(self.d, node="n", config={"segment_bytes": 4096})
        self.lr = os.path.join(node, ".aos", "last-round.json")
        self.log = os.path.join(self.root, ".aosd", "log.jsonl")
        os.makedirs(os.path.dirname(self.log))

    def once(self, r=None, **extra):
        if r is not None:
            write_json(self.lr, dict(extra, round=r))
        return sampler.once(self.me, self.args, lambda p: None, self.st)

    def write_log(self, data, mode="ab"):
        with open(self.log, mode) as f:
            f.write(data)

    def run_sampler(self, point="", *args):
        write_json(os.path.join(self.me["task"], "tock.json"), {"round": 1, "run": 1})
        env = dict(os.environ, AOS7_ROOT=self.root, AOS7_NODE=self.me["node"], AOS7_NODE_ID="n",
                   AOS7_TASK=self.me["task"], AOS7_TID="events#1", AOS7_RUN="1", AOS7_TEST_CRASH=point)
        return subprocess.run([sys.executable, os.path.join(EVENTS, "aos7-events"), "--rounds", "1", "--out", self.d, *args],
                              env=env, capture_output=True, text=True, timeout=20)

    def test_300_rounds(self):
        for r in range(1, 301):
            self.once(r, pad="x" * 500)
            self.assert_layout()
        self.assertGreater(self.channel()["dropped_upto"], 0)
        self.assertEqual(store.load_state(self.d)["sample"], {"n": 300})

    def test_gaps_and_reset(self):
        for r in (1, 2, 5, 1):
            self.once(r)
        gaps = [r for r in self.rows() if r["kind"] == "gap"]
        self.assertEqual(gaps[0]["payload"], {"from": 3, "to": 4, "why": "round_skip"})
        self.assertEqual(gaps[1]["payload"], {"from": 5, "to": 1, "why": "source_reset_unknown"})
        self.assertEqual(gaps[1]["source"]["round"], 0)
        self.assertEqual(self.rows()[-1]["payload"]["last_round"]["round"], 1)
        self.once(1)
        self.assertEqual(len(self.rows()), 6)

    def test_status_and_invalid_source(self):
        write_json(self.lr, {"round": True})
        self.assertFalse(self.once())
        self.args.status = True
        path = os.path.join(self.root, ".aosd", "status.json")
        write_json(path, {"last_event": {"ev": "start"}})
        self.once()
        self.once()
        self.assertEqual(len(self.rows()), 1)
        self.st = store.recover(self.d, node="n")  # 重起：去重鍵在 state.status_last，不再記一筆。
        self.once()
        self.assertEqual(len(self.rows()), 1)
        write_json(path, {"last_event": {"ev": "stop"}})
        self.once()
        self.assertEqual(len(self.rows()), 2)

    def test_status_dedup_across_restarts(self):
        """V2：同一 status 事件跨真重起（子程序 ×3）、state 遺失重推、舊 state 缺欄位都只記一筆。"""
        write_json(os.path.join(self.root, ".aosd", "status.json"), {"last_event": {"ev": "start", "n": 1}})
        # 整行已 flush、status_last 未存就被殺：重起由恢復掃尾推回（astra V2 #2）。
        self.assertEqual(self.run_sampler("events:after-append", "--status").returncode, -9)
        self.assertEqual(store.load_state(self.d).get("status_last"), None)
        for _ in range(3):
            self.assertEqual(self.run_sampler("", "--status").returncode, 0)
        self.assertEqual([r["kind"] for r in self.rows()].count("daemon.status"), 1)
        st = read_json(os.path.join(self.d, "state.json"))
        del st["status_last"]   # 舊 state 缺欄位視為空：記一次後補上
        write_json(os.path.join(self.d, "state.json"), st)
        for _ in range(2):
            self.assertEqual(self.run_sampler("", "--status").returncode, 0)
        self.assertEqual([r["kind"] for r in self.rows()].count("daemon.status"), 2)
        os.unlink(os.path.join(self.d, "state.json"))   # state 遺失：從留存紀錄推回
        self.assertEqual(self.run_sampler("", "--status").returncode, 0)
        self.assertEqual([r["kind"] for r in self.rows()].count("daemon.status"), 2)
        self.assertEqual(store.load_state(self.d)["status_last"], store.status_key({"ev": "start", "n": 1}))

    def test_snapshot_truncated_and_retry(self):
        self.once(1, pad="漢" * 30000)
        self.assertEqual(self.rows()[0]["payload"], {"last_round": {"round": 1}, "truncated": True})
        with mock.patch.object(store, "append", return_value={"ok": False, "why": "unknown"}):
            self.assertFalse(self.once(5))
        self.assertEqual(self.st["sample"]["n"], 1)
        self.once(5)
        self.assertEqual(len(self.rows()), 3)

    def test_log_offsets(self):
        self.args.daemon_log = True
        self.write_log(b'{"i": 1}\ntrue\nunparsed\npartial')
        self.once()
        first = self.rows()
        self.assertEqual([r["payload"] for r in first], [{"i": 1}, True, {"unparsed": "unparsed\n"}])
        self.write_log(b'\n{"i": 2}\n')
        self.once()
        rows = self.rows()
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[-1]["payload"], {"i": 2})
        self.assertEqual(rows[0]["source"]["off_from"], 0)
        for a, b in zip(rows, rows[1:]):
            self.assertEqual(a["source"]["off_to"], b["source"]["off_from"])
        self.assertEqual(store.load_state(self.d)["daemon_log"]["offset"], os.stat(self.log).st_size)
        before = open(self.log, "rb").read()
        self.once()
        self.assertEqual(open(self.log, "rb").read(), before)
        self.assertEqual(len(self.rows()), 5)

    def test_log_replaced_and_shorter(self):
        self.args.daemon_log = True
        self.write_log(b'{"long": "abcdefghijk"}\n')
        self.once()
        old = os.stat(self.log).st_ino
        # 保留舊 fd，防止檔系統立即重用 inode。
        with open(self.log, "rb"):
            os.unlink(self.log)
            self.write_log(b'1\n')
            self.assertNotEqual(os.stat(self.log).st_ino, old)
            self.once()
        self.write_log(b'\n', "wb")
        self.once()
        gaps = [r for r in self.rows() if r["kind"] == "gap"]
        self.assertEqual(len(gaps), 2)
        for gap in gaps:
            self.assertEqual(gap["payload"]["why"], "source_reset_unknown")
            self.assertEqual(gap["source"]["off_to"], 0)
        self.assertEqual(self.rows()[-1]["source"]["off_from"], 0)

    def test_log_too_large_and_failure(self):
        self.args.daemon_log = True
        data = json.dumps({"pad": "x" * 70000}).encode() + b"\n"
        self.write_log(data)
        with mock.patch.object(store, "append", return_value={"ok": False, "why": "unknown"}):
            self.once()
        self.assertIsNone(self.st["daemon_log"])
        self.once()
        self.assertEqual(self.rows()[0]["payload"], {"too_large": True, "bytes": len(data)})

    def test_crash_gap(self):
        self.once(1)
        for r in (5, 9, 13):
            write_json(self.lr, {"round": r})
            self.assertEqual(self.run_sampler("events:sample-after-gap").returncode, -9)
            self.assertEqual(self.run_sampler().returncode, 0)
            rows = self.rows()
            self.assertEqual(sum(x["kind"] == "gap" and x["source"]["round"] == r - 1 for x in rows), 1)
            self.assertEqual(sum(x["kind"] == "round.observed" and x["source"]["round"] == r for x in rows), 1)

    def test_crash_snapshot(self):
        for r in (1, 2, 3):
            write_json(self.lr, {"round": r})
            self.assertEqual(self.run_sampler("events:after-append").returncode, -9)
            self.assertEqual(self.run_sampler().returncode, 0)
        self.assertEqual([r["source"]["round"] for r in self.rows()], [1, 2, 3])

    def test_crash_log(self):
        for i in range(3):
            self.write_log((json.dumps({"i": i}) + "\n").encode())
            self.assertEqual(self.run_sampler("events:after-append", "--daemon-log").returncode, -9)
            self.assertEqual(self.run_sampler("", "--daemon-log").returncode, 0)
        rows = self.rows()
        self.assertEqual([r["payload"]["i"] for r in rows], [0, 1, 2])
        self.assertEqual(rows[0]["source"]["off_from"], 0)
        for a, b in zip(rows, rows[1:]):
            self.assertEqual(a["source"]["off_to"], b["source"]["off_from"])
        self.assertEqual(rows[-1]["source"]["off_to"], os.stat(self.log).st_size)



if __name__ == "__main__":
    unittest.main()
