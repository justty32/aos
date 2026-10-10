"""事件包按職責分組的測試。"""
from _events_read import *


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
        self.assertEqual(p.returncode, 3, p.stderr)

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
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertEqual(reader.read(self.dir, "must")["records"], before)
        with locked(os.path.join(self.dir, "state.json")):
            p = self.cli("aos7_events_pub.py", *args)
        self.assertEqual(p.returncode, 3, p.stderr)

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
        self.assertEqual(p.returncode, 3, p.stderr)
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



if __name__ == "__main__":
    unittest.main()
