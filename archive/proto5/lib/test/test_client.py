"""交件者放單、等待的讀取順序、逾時與延遲 ack。"""
from pathlib import Path
import subprocess
import sys
import time
from unittest import mock

import aos_client as client
import aos_home as home
from _util import Base, LIB


class ClientCase(Base):
    def setUp(self):
        super().setUp()
        home.ensure_queue(self.d)

    def test_name(self):
        self.assertRegex(client.new_name("agent"), r"^agent-\d+-\d+\.json$")

    def test_submit(self):
        self.assertEqual(client.submit(self.d, "method", {"x": 1}, name="x.json"), "x.json")
        obj = home.read_json(Path(self.d) / "requests/x.json")
        self.assertEqual(obj, {"jsonrpc": "2.0", "id": "x", "method": "method", "params": {"x": 1}})

    def test_submit_exists(self):
        client.submit(self.d, "first", name="x.json")
        with self.assertRaises(home.RequestExists):
            client.submit(self.d, "second", name="x.json")

    def test_wait_checks_request_first(self):
        seen = []
        def exists(path):
            seen.append(path.parent.name)
            return False if path.parent.name == "requests" else True
        with mock.patch.object(Path, "exists", exists), mock.patch.object(client, "read_json", return_value={}) as read:
            self.assertEqual(client.wait_response(self.d, "x.json", timeout_ms=0), {})
        self.assertEqual(seen, ["requests", "responses"])
        read.assert_called_once()

    def test_wait_does_not_ack_while_request_exists(self):
        client.submit(self.d, "x", name="x.json")
        home.write_json(Path(self.d) / "responses/x.json", home.result_response("x", {}))
        with self.assertRaises(client.ClientError) as caught:
            client.wait_response(self.d, "x.json", timeout_ms=0)
        self.assertEqual(caught.exception.code, "ReadFailed")
        self.assertTrue(self.exists("requests/x.json"))
        self.assertTrue(self.exists("responses/x.json"))

    def test_wait_reads_after_request_deleted(self):
        response = home.result_response("x", {"ok": True})
        home.write_json(Path(self.d) / "responses/x.json", response)
        self.assertEqual(client.wait_response(self.d, "x.json", timeout_ms=0), response)

    def test_timeout_does_not_cancel(self):
        client.submit(self.d, "x", name="x.json")
        with self.assertRaises(client.ClientError):
            client.wait_response(self.d, "x.json", timeout_ms=1, poll_ms=1)
        self.assertTrue(self.exists("requests/x.json"))

    def test_ack_posts_notification(self):
        name = client.ack(self.d, "x.json")
        self.assertTrue(name.startswith("ack-"))
        env = home.read_request(Path(self.d) / "requests" / name)
        self.assertTrue(env.notify)
        self.assertEqual(env.params, {"name": "x.json"})

    def test_call_acknowledges(self):
        response = home.result_response("x", {})
        with mock.patch.object(client, "wait_response", return_value=response):
            self.assertEqual(client.call(self.d, "x", name="x.json"), response)
        self.assertEqual(len(list((Path(self.d) / "requests").glob("ack-*.json"))), 1)

    def test_call_deferred_ack(self):
        response = home.result_response("x", {})
        with mock.patch.object(client, "wait_response", return_value=response):
            self.assertEqual(client.call(self.d, "x", name="x.json", acknowledge=False), response)
        self.assertEqual(len(list((Path(self.d) / "requests").glob("ack-*.json"))), 0)

    def test_invalid_poll(self):
        with self.assertRaises(client.ClientError):
            client.wait_response(self.d, "x.json", poll_ms=0)

    def test_end_to_end_real_cpu(self):
        self.inst({"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 2}, "info.json")
        executable = str(Path(LIB).parent / "cli/aos-cpu")
        proc = subprocess.Popen([sys.executable, executable, self.d], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        def cleanup():
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
            proc.stderr.close()
        self.addCleanup(cleanup)
        deadline = time.monotonic() + 5
        while not self.exists("state.json"):
            if proc.poll() is not None:
                self.fail("cpu exited: " + proc.stderr.read())
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.002)
        response = client.call(self.d, "aos-exec", {"target": "/bin/true"}, name="work.json",
                               timeout_ms=5000, poll_ms=2)
        self.assertEqual(response["result"]["code"], 0)
        deadline = time.monotonic() + 5
        while self.exists("responses/work.json"):
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.002)
        home.post_request(self.d, client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        self.assertEqual(proc.wait(timeout=5), 0)
