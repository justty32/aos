"""事件包按職責分組的測試。"""
from _events_store import *


class TestStore(EventsCase):
    def test_append_basic(self):
        for i in range(1, 4):
            self.assertEqual(self.append(i), {"ok": True, "seq": i, "dup": False, "why": None})
        self.assertEqual(set(os.listdir(self.d)), {"obs.active.jsonl", "state.json", "state.json.lock"})
        for row in self.rows():
            self.assertEqual((row["stream"], row["v"]), ("n/obs", 1))
            self.assertEqual(list(row)[:8], ["v", "stream", "seq", "kind", "capture", "event_id", "source", "at"])
        self.assert_layout()

    def test_dup(self):
        self.append()
        self.assertEqual(self.append()["dup"], True)
        self.assertEqual(self.append()["seq"], 1)
        self.assertEqual(len(self.rows()), 1)
        self.append(ch="must")
        self.assertEqual(len(self.rows("must")), 1)

    def test_too_large(self):
        self.append(config={"segment_bytes": 1, "max_record_bytes": 500})
        before = self.contents()
        self.assertEqual(self.append(2, payload={"pad": "漢" * 1000})["why"], "too_large")
        self.assertEqual(self.contents(), before)
        self.assertEqual(self.channel()["next_seq"], 2)

    def test_node_and_config(self):
        self.append(config={"keep_segments": 2})
        self.assertEqual(store.append(self.d, "obs", {}, node="other")["why"], "unknown")
        result = self.append(2, config={"keep_segments": 4, "unused": 8})
        self.assertTrue(result["config_ignored"])
        self.assertEqual(store.load_state(self.d)["config"]["keep_segments"], 2)
        self.assertIsNone(store.recover(self.d, node="other"))

    def test_bad_state(self):
        os.makedirs(self.d)
        path = os.path.join(self.d, "state.json")
        for data in (b"{", b"[]", b'{"v": 1}', b'{"v": 1, "node": "n", "channels": {}}'):
            with open(path, "wb") as f:
                f.write(data)
            self.assertEqual(self.append()["why"], "unknown")
            self.assertIsNone(store.recover(self.d, node="n"))
            with self.assertRaises(Unknown):
                store.ack(self.d, 1)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), data)

    def test_locked_and_load_state(self):
        self.assertIsNone(store.load_state(self.d))
        self.append()
        with open(os.path.join(self.d, "state.json.lock"), "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            start = time.monotonic()
            self.assertIsNotNone(store.load_state(self.d))
            self.assertLess(time.monotonic() - start, 0.2)
            with mock.patch.object(store, "LOCK_TIMEOUT", 0.05):
                self.assertEqual(self.append(2)["why"], "unknown")
                self.assertIsNone(store.recover(self.d, node="n"))
                with self.assertRaises(Unknown):
                    store.ack(self.d, 1)
            self.assertLess(time.monotonic() - start, 1)

    def test_value_errors(self):
        cases = [("x", {}, "n"), ("obs", [], "n"), ("obs", {}, ""), ("obs", {}, 1)]
        cases += [("obs", {k: 1}, "n") for k in ("seq", "stream", "v")]
        cases += [("obs", {"capture": "published", "event_id": v}, "n") for v in (None, "", 3)]
        for ch, rec, node in cases:
            with self.subTest(ch=ch, rec=rec, node=node), self.assertRaises(ValueError):
                store.append(self.d, ch, rec, node=node)
        for v in (0, -1, True, "2"):
            with self.assertRaises(ValueError):
                self.append(config={"segment_bytes": v})
        for v in (True, "2", None):
            with self.assertRaises(ValueError):
                store.ack(self.d, v)

    def test_ack(self):
        self.assertEqual(store.ack(self.d, 100), 0)
        for i in range(1, 4):
            self.append(i, ch="must")
        self.assertEqual(store.ack(self.d, 2), 2)
        self.assertEqual(store.ack(self.d, 1), 2)
        self.assertEqual(store.ack(self.d, 999), 3)

    def test_oserror(self):
        self.append()
        with mock.patch.object(store, "write_json", side_effect=OSError("EIO")):
            self.assertEqual(self.append(2)["why"], "unknown")
            self.assertIsNone(store.recover(self.d, node="n"))
            with self.assertRaises(Unknown):
                store.ack(self.d, 1)
        self.assertTrue(self.append(2)["dup"])



class TestRecovery(EventsCase):
    def test_torn_and_tmp(self):
        self.append()
        with open(os.path.join(self.d, "obs.active.jsonl"), "ab") as f:
            f.write(b'{"seq": 2')
        with open(os.path.join(self.d, ".state.json.tmp.99999"), "w") as f:
            f.write("stale")
        self.assertEqual(self.append(2)["seq"], 2)
        self.assertEqual(self.channel()["torn"], 1)
        self.assert_layout()

    def test_missing_state(self):
        for i in range(1, 10):
            self.append(i, config={"segment_bytes": 1, "keep_segments": 2}, capture="sample", source={"node": "a", "round": i})
        os.unlink(os.path.join(self.d, "state.json"))
        self.assertEqual(self.append(10, config={"segment_bytes": 1, "keep_segments": 2})["seq"], 10)
        self.assertEqual(store.load_state(self.d)["sample"], {"a": 9})
        self.assertGreater(self.channel()["dropped_upto"], 0)
        self.assert_layout()

    def test_destination_exists(self):
        self.append(config={"segment_bytes": 1})
        dest = os.path.join(self.d, "obs.000000000001.jsonl")
        with open(dest, "w") as f:
            f.write("collision\n")
        before = self.contents()
        state = store.load_state(self.d)
        self.assertEqual(self.append(2)["why"], "unknown")
        self.assertEqual(self.contents(), before)
        self.assertEqual(store.load_state(self.d), state)

    def test_fast_path(self):
        self.append()
        with mock.patch.object(store, "_scan", side_effect=AssertionError("不應掃已知活躍段")):
            self.assertIsNotNone(store.recover(self.d, node="n"))
        self.assertEqual(self.channel()["next_seq"], 2)



class TestRotation(EventsCase):
    def test_obs_retention(self):
        for i in range(1, 40):
            self.assertTrue(self.append(i, config={"segment_bytes": 1})["ok"])
            self.assert_layout()
        self.assertGreater(self.channel()["dropped_upto"], 0)

    def test_must_full_ack(self):
        for i in range(1, 6):
            self.assertTrue(self.append(i, ch="must", config={"segment_bytes": 1})["ok"])
        before = self.contents()
        for _ in range(2):
            self.assertEqual(self.append(6, ch="must")["why"], "full")
            self.assertEqual(self.contents(), before)
        self.assertEqual(self.channel("must")["refused"], 2)
        self.assertEqual(store.ack(self.d, 2), 2)
        self.assertEqual(self.contents(), before)  # ack 本身不清段。
        self.assertTrue(self.append(6, ch="must")["ok"])
        self.assertEqual(self.channel("must")["dropped_upto"], 2)
        self.assert_layout("must")
        store.ack(self.d, 100)
        self.assertTrue(self.append(7, ch="must")["ok"])
        self.assert_layout("must")



if __name__ == "__main__":
    unittest.main()
