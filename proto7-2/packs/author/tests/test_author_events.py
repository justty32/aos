"""must 收件與回條／確認窗口的故障驗收。"""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_author import AUTHOR, TestAuthorHelpers, author, pub, regular_files
from aos7_fs import read_json, write_json
_, reader, store = pub._events()


class TestAuthorEvents(TestAuthorHelpers):
    def setup_event(self):
        node = self.mknode()
        path = self.request(node)
        events = str(Path(node, "events"))
        self.assertEqual(self.good(pub.send_request(node, str(path), events))["seq"], 1)
        return node, path, events

    def acked(self, events):
        return store.load_state(events)["channels"]["must"]["acked_upto"]

    def saved_once(self, node, path):
        files = list(Path(node, "author/req").glob("*/request.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_bytes(), path.read_bytes())

    def test_basic(self):
        node, path, events = self.setup_event()
        self.assertTrue(self.good(pub.send_request(node, str(path), events))["dup"])
        self.assertEqual(self.good(pub.intake(node, events))["handled"],
                         [dict(seq=1, rid="csv1", result="registered")])
        self.saved_once(node, path)
        self.assertEqual(self.acked(events), 1)
        self.assertEqual(self.good(pub.intake(node, events))["handled"], [])

    def test_after_receipt_three_kills(self):
        node, path, events = self.setup_event()
        for _ in range(3):
            self.cli(node, "intake", rc=-9, crash="intake-after-receipt")
            self.assertEqual(self.acked(events), 0)
        self.assertEqual(self.good(pub.intake(node, events))["handled"], [])
        self.assertEqual(self.acked(events), 1)
        self.saved_once(node, path)
        self.assertEqual(read_json(str(Path(node, "author/events.json")))["last"]["result"], "registered")

    def test_before_receipt_retry(self):
        node, path, events = self.setup_event()
        self.cli(node, "intake", rc=-9, crash="intake-before-receipt")
        self.assertEqual(self.acked(events), 0)
        self.assertFalse(Path(node, "author/events.json").exists())
        got = self.good(pub.intake(node, events))["handled"]
        self.assertEqual(got[0]["seq"], 1)
        self.assertIn(got[0]["result"], ("registered", "dup"))
        self.saved_once(node, path)
        self.assertEqual(self.acked(events), 1)

    def test_full_not_sent(self):
        node = self.mknode()
        path = self.request(node, "unsent")
        events = str(Path(node, "events"))
        ep, _, _ = pub._events()
        for n in range(3):
            r = ep.publish(events, "other", "fill/%d" % n, {}, must=True,
                           node=os.path.basename(node), config=dict(keep_segments=1, segment_bytes=1))
            self.assertEqual(r["why"], "full" if n == 2 else None)
        self.refused(pub.send_request(node, str(path), events), "full")
        self.cli(node, "send", path, rc=5)
        self.assertFalse(Path(node, "author").exists())
        self.assertEqual(len(self.good(pub.intake(node, events))["handled"]), 2)
        self.assertEqual(regular_files(Path(node, "author")), ["author.lock", "events.json"])
        self.assertFalse(Path(node, "author/req/unsent/request.json").exists())

    def test_conflict_and_bad_payload_then_good(self):
        node, path, events = self.setup_event()
        doc = json.loads(path.read_bytes())
        doc["goal"] += "另文"
        self.refused(pub.send_request(node, str(self.source("changed.json", doc)), events), "conflict")
        ep, _, _ = pub._events()
        bad = dict(v=1, rid="bad", request_sha="0" * 64, request=path.read_text())
        self.good(ep.publish(events, "author.request", "author/bad", bad, must=True, node=os.path.basename(node)))
        other = self.request(node, "next")
        self.good(pub.send_request(node, str(other), events))
        self.assertEqual([r["result"] for r in self.good(pub.intake(node, events, 2))["handled"]],
                         ["registered", "invalid"])
        self.assertEqual(read_json(str(Path(node, "author/events.json")))["last"]["result"], "invalid")
        self.assertEqual(self.acked(events), 2)
        self.assertEqual(self.good(pub.intake(node, events))["handled"][0]["result"], "registered")
        self.assertEqual(self.acked(events), 3)

    def test_events_path_conflict(self):
        node, _, events = self.setup_event()
        self.good(pub.intake(node, events))
        self.refused(pub.intake(node, str(Path(node, "different"))), "conflict")

    def test_unknown_does_not_consume(self):
        node, _, events = self.setup_event()
        with mock.patch.object(author, "_register_raw", return_value=author.result(False, "unknown", error="讀不到")):
            self.refused(pub.intake(node, events), "unknown")
        self.assertEqual(self.acked(events), 0)
        self.assertFalse(Path(node, "author/events.json").exists())
        write_json(str(Path(node, "author/events.json")), {})
        self.refused(pub.intake(node, events), "unknown")

    def test_unencodable_path_does_not_block(self):
        node, path, events = self.setup_event()
        self.good(pub.intake(node, events))
        raw = path.read_text().replace('"data.csv"', '"\\ud800.csv"').replace('"csv1"', '"odd"')
        self.assertIn("\\ud800", raw)
        odd = Path(self.root, "odd.json")
        odd.write_text(raw)
        self.good(pub.send_request(node, str(odd), events))
        self.good(pub.send_request(node, str(self.request(node, "after")), events))
        self.assertEqual([r["result"] for r in self.good(pub.intake(node, events))["handled"]],
                         ["invalid", "registered"])
        self.assertEqual(self.acked(events), 3)

    def test_receipt_tmp_swept(self):
        node, _, events = self.setup_event()
        env = dict(os.environ, AOS7_TEST_CRASH="tmp:events.json")
        for _ in range(3):
            p = subprocess.run([sys.executable, str(AUTHOR), "intake"], cwd=node, env=env,
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(p.returncode, -9, (p.stdout, p.stderr))
        self.assertEqual(self.acked(events), 0)
        self.good(pub.intake(node, events))
        self.assertEqual(self.acked(events), 1)
        self.assertEqual(regular_files(Path(node, "author")),
                         ["author.lock", "events.json", "req/csv1/request.json"])
