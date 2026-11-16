# test_slash verifies command validation, bare delivery, fixture reloads and masked multiline history.
import copy
import http.client
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

if any(k.startswith("AOS_") for k in os.environ):
    raise SystemExit("test_slash: run through tests/run.sh")

VIEW = Path(__file__).resolve().parents[1] / "aos-view"
loader = importlib.machinery.SourceFileLoader("view_slash_test", str(VIEW))
spec = importlib.util.spec_from_loader(loader.name, loader)
v = importlib.util.module_from_spec(spec)
loader.exec_module(v)


class Slash(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="slash-", dir=str(Path.home() / ".aos/scratch/ok-pano-1116"))
        self.home = v.Home(self.tmp)
        Path(self.home.state).mkdir()
        self.node = {"kind": "agent", "state": "running", "queued": 0,
                     "live": {"cli": "claude", "in_turn": False}}
        self.tree = {"nodes": {"board": self.node}}
        self.run = patch.object(v, "run", return_value=(0, "L-slash\n", "")).start()
        self.addCleanup(patch.stopall)
        self.env = patch.dict(os.environ)
        self.env.start()
        os.environ.pop("VIEW_SLASH_FIXTURE", None)

    def send(self, text="/status", name="board"):
        return v.do_slash({"name": name, "text": text}, self.tree, self.home)

    def fixture(self, commands):
        p = Path(self.tmp) / "commands.json"
        p.write_text(json.dumps(commands))
        os.environ["VIEW_SLASH_FIXTURE"] = str(p)
        return p

    def test_agent_gate(self):
        self.assertTrue(self.send(name="missing").startswith("!"))
        self.node["kind"] = "proc"
        self.assertTrue(self.send().startswith("!"))
        self.run.assert_not_called()

    def test_text_gate(self):
        for text in ("", "status", "/status\n/exit", "/goal " + "x" * 1000, "/status\r/exit"):
            with self.subTest(text=text[:30]):
                self.assertTrue(self.send(text).startswith("!"))
        self.run.assert_not_called()

    def test_known_command_gate(self):
        self.assertIn("目前送不進去", self.send("/unknown"))
        self.run.assert_not_called()

    def test_argument_gate(self):
        self.assertTrue(self.send("/status extra").startswith("!"))
        commands = copy.deepcopy(v.SLASH_CMDS)
        commands[0]["args"] = "required"
        self.fixture(commands)
        self.assertTrue(self.send("/compact").startswith("!"))
        self.assertFalse(self.send("/compact plan").startswith("!"))

    def test_running_gate(self):
        self.node["state"] = "stopped"
        self.assertIn("沒在跑", self.send())
        self.run.assert_not_called()

    def test_cli_gate(self):
        self.node["live"] = None
        self.assertTrue(self.send().startswith("!"))
        self.node["live"] = {"cli": "other"}
        self.assertTrue(self.send().startswith("!"))
        self.run.assert_not_called()
        stack = Path(self.tmp) / "stack"
        (stack / "codex").mkdir(parents=True)
        self.node.update(live=None, stack=str(stack))
        self.assertFalse(self.send().startswith("!"))

    def test_queue_gate(self):
        self.node["queued"] = 1
        self.assertIn("併成一批", self.send())
        self.run.assert_not_called()

    def test_success_bare_stdin_audit_and_cache(self):
        ret = {}
        v.DELIVERY_CACHE["board"] = {"old": True}
        self.node["live"]["in_turn"] = True
        text = "/compact  keep  the plan"
        result = v.do_slash({"name": "board", "text": "  " + text + "  "}, self.tree, self.home, ret)
        self.assertIn("已把 /compact 送進 board 的畫面", result)
        self.assertIn("這一輪結束才會做", result)
        self.run.assert_called_once_with(["aos-agent", "say", "-t", "board", "--from", v.PAGE_FROM, "-"],
                                         timeout=20, stdin=text)
        self.assertEqual(ret, {"letter": "L-slash"})
        self.assertNotIn("board", v.DELIVERY_CACHE)
        rec = json.loads((Path(self.home.state) / "sent.jsonl").read_text())
        self.assertEqual((rec["kind"], rec["text"], rec["to"], rec["ok"]), ("slash", text, "board", True))
        self.assertEqual(v.read_sent(self.home), [])

    def test_delivery_failure(self):
        self.run.return_value = (1, "", "delivery failed")
        self.assertTrue(self.send().startswith("!"))
        rec = json.loads((Path(self.home.state) / "sent.jsonl").read_text())
        self.assertEqual((rec["ok"], rec["letter"], rec["error"]), (False, None, "delivery failed"))

    def test_compact_compatibility(self):
        self.node["live"]["in_turn"] = True
        self.assertIn("這一輪結束才會壓", v.do_compact({"name": "board"}, self.tree, self.home))
        self.assertEqual(self.run.call_args.kwargs["stdin"], "/compact")
        rec = json.loads((Path(self.home.state) / "sent.jsonl").read_text())
        self.assertEqual(rec["kind"], "compact")

    def test_fixture_reload_for_sends(self):
        commands = v.SLASH_CMDS + [{"name": "context", "args": "none", "how": "screen", "confirm": False, "cli": ["claude"]}]
        p = self.fixture(commands)
        self.assertFalse(self.send("/context").startswith("!"))
        self.node["live"]["cli"] = "codex"
        self.assertTrue(self.send("/context").startswith("!"))
        self.node["live"]["cli"] = "claude"
        p.write_text(json.dumps(v.SLASH_CMDS))
        self.assertIn("目前送不進去", self.send("/unknown"))

    def test_http_gates_and_get_shape(self):
        collector = type("Collector", (), {"get": lambda _: (self.tree, None)})()
        srv = v.Server(("127.0.0.1", 0), v.Handler)
        srv.home, srv.collector, srv.token = self.home, collector, "test-token"
        srv.outbox = type("Outbox", (), {"sent": lambda *args: None})()
        thread = threading.Thread(target=srv.serve_forever)
        with patch.object(v, "revs_of", return_value={}):
            thread.start()
            try:
                port = srv.server_address[1]
                def req(method, body=None, headers=None, path="/api/slash"):
                    c = http.client.HTTPConnection("127.0.0.1", port)
                    c.request(method, path, body, headers or {})
                    r = c.getresponse()
                    result = r.status, r.read().decode()
                    c.close()
                    return result
                h = {"Content-Type": "application/json", "X-View-Token": "test-token", "Cookie": "aosview=test-token"}
                payload = json.dumps({"name": "board", "text": "/status"})
                self.assertEqual(json.loads(req("GET")[1]), {"commands": v.SLASH_CMDS})
                p = self.fixture([])
                self.assertEqual(json.loads(req("GET")[1]), {"commands": []})
                p.write_text(json.dumps(v.SLASH_CMDS))
                self.assertEqual(len(json.loads(req("GET")[1])["commands"]), 7)
                for headers, body, status in (({}, payload, 415), (dict(h, Host="bad"), payload, 403),
                    (dict(h, Origin="http://bad"), payload, 403), (dict(h, Cookie="aosview=bad"), payload, 403),
                    (dict(h, **{"X-View-Token": "bad"}), payload, 403), (h, "{", 400),
                    (h, json.dumps({"name": "board", "text": 7}), 400), (h, "x" * 65537, 413)):
                    with self.subTest(status=status, body=body[:40]):
                        self.assertEqual(req("POST", body, headers)[0], status)
                status, body = req("POST", payload, h)
                self.assertEqual((status, json.loads(body)["letter"]), (200, "L-slash"))
                self.assertEqual(req("POST", json.dumps({"name": "board"}), h, "/api/compact")[0], 200)
            finally:
                srv.shutdown()
                thread.join()
                srv.server_close()

    def test_long_light_reason_keeps_masked_full_text(self):
        collector = v.Collector(self.home)
        secret = "sk-" + "a" * 24
        reason = "failure detail; " * 35 + secret + " final detail"
        node = {"state": "stopped", "reason": reason, "children": []}
        self.assertEqual(collector.light(node, {})[1], "crashed: " + v.short(reason, 80))
        self.assertEqual(len(collector.light(node, {})[1][len("crashed: "):]), 80)
        self.assertEqual(collector.why_full(node, {}), "crashed: " + v.mask(reason))
        self.assertNotIn(secret, collector.why_full(node, {}))
        self.assertTrue(collector.why_full(node, {}).endswith(" final detail"))
        node["reason"] = "timeout: " + reason
        self.assertEqual(collector.why_full(node, {}),
                         "stopped: a turn ran long and was cut by a timeout, not a crash (%s)" % v.mask(node["reason"]))
        node.update(state="running", reason=None, cooldown={"failures": 3, "reason": reason})
        self.assertEqual(collector.why_full(node, {}), "brain failed 3x: " + v.mask(reason))
        node["cooldown"]["reason"] = "detail " * 500
        self.assertEqual(len(collector.why_full(node, {})), 2000)
        self.assertTrue(collector.why_full(node, {}).endswith("…"))
        node.update(state="sleeping", cooldown=None)
        self.assertEqual(collector.why_full(node, {}), collector.light(node, {})[1])

    def test_tree_exposes_why_full_for_all_nodes(self):
        secret = "sk-" + "b" * 24
        reason = "long failure " * 30 + secret + " end"
        rows = [{"name": name, "state": "stopped", "reason": reason, "stack": None, "queued": 0}
                for name in ("boss", "boss-child")]
        v.write_json(Path(self.home.dir) / "config.json", {"externals": []})
        collector = v.Collector(self.home)
        with patch.dict(os.environ, VIEW_LS_FIXTURE="unused", VIEW_ASKS_FIXTURE="unused"), \
                patch.object(v, "table_rows", return_value=rows), patch.object(v, "ingest", return_value={}):
            tree = collector._collect()
        self.assertEqual(set(tree["nodes"]), {"boss", "boss-child"})
        for node in tree["nodes"].values():
            self.assertEqual(node["why_full"], "crashed: " + v.mask(reason))
            self.assertEqual(node["why"], "crashed: " + v.short(reason, 80))
            self.assertNotIn(secret, node["why_full"])

    def test_history_and_full_masking(self):
        secret = "sk-" + "abcdef0123456789" * 2
        content = "[aos] slash: /context: printed:\n" + ("row content " * 12 + "\n") * 18 + secret
        def row(text, role="assistant", line=1):
            return {"line": line, "message": {"role": role, "content": text}}
        hist = [row("old"), row(content, line=2), row("latest user", "user", 3)]
        state = {"state": {"last_answer": "upstream short"}}
        with patch.object(v, "run_json", side_effect=[state, hist]):
            got = v.agent_json("board")
        item = got["history"][1]
        self.assertEqual(item["slash"], "/context")
        self.assertGreater(len(item["text"]), 600)
        self.assertIn("\n", item["text"])
        self.assertNotIn(secret, json.dumps(got))
        self.assertEqual(got["now"]["last_answer_full"], item["text"])
        self.assertFalse(got["now"]["last_answer_cut"])
        long = row(content * 3)
        self.assertEqual(len(v.history_item(long)["text"]), 4000)
        self.assertTrue(v.history_item(long)["text"].endswith("…"))
        self.assertEqual((len(v.last_full([long])[0]), v.last_full([long])[1]), (4000, True))
        self.assertEqual(v.last_full([]), (None, False))
        self.assertEqual(v.last_full([row("user only", "user")]), (None, False))
        ordinary = v.history_item(row("ordinary\n" + "x" * 700))
        self.assertEqual(len(ordinary["text"]), 600)
        self.assertNotIn("\n", ordinary["text"])
        self.assertNotIn("slash", ordinary)
        self.assertNotIn("slash", v.history_item(row(content, "user")))
        self.assertEqual(v.last_full([row([{"type": "text", "text": "first\nsecond"}])]), ("first\nsecond", False))


if __name__ == "__main__":
    unittest.main()
