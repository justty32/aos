# test_slash verifies slash validation, deduplication, reply states and masked multiline history.
import copy
import http.client
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import tempfile
import threading
import unittest
from unittest.mock import patch

if any(k.startswith("AOS_") for k in os.environ):
    raise SystemExit("test_slash: run through tests/run.sh")

VIEW = Path(__file__).resolve().parents[1] / "bin" / "aos-view"
loader = importlib.machinery.SourceFileLoader("view_slash_test", str(VIEW))
spec = importlib.util.spec_from_loader(loader.name, loader)
v = importlib.util.module_from_spec(spec)
loader.exec_module(v)


class Slash(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="slash-", dir=os.environ.get("VIEW_TEST_TMP") or str(Path.home() / ".aos/scratch/ok-pano-b"))
        self.home = v.Home(self.tmp)
        Path(self.home.state).mkdir()
        self.node = {"kind": "agent", "state": "running", "queued": 0,
                     "live": {"cli": "claude", "in_turn": False}}
        self.tree = {"nodes": {"board": self.node}}
        self.run = patch.object(v, "run", return_value=(0, "L-slash\n", "")).start()
        self.run_json = patch.object(v, "run_json", return_value=None).start()
        v.SLASH_CACHE.clear()
        v.PEEK.clear()
        # A peek never runs a real aos-agent here: the thread is captured, subprocess.run is a mock.
        self.peeks = []
        patch.object(v, "start_peek", side_effect=self.peeks.append).start()
        self.sub = patch.object(v.subprocess, "Popen").start()
        self.killpg = patch.object(v.os, "killpg").start()
        self.addCleanup(patch.stopall)
        self.env = patch.dict(os.environ)
        self.env.start()
        os.environ.pop("VIEW_SLASH_FIXTURE", None)

    def send(self, text="/goal", name="board"):
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
        self.assertFalse(self.send().startswith("!"))
        self.run.assert_called_once()
        self.assertIn("併成一批", v.do_compact({"name": "board"}, self.tree, self.home))
        self.run.assert_called_once()

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
        self.assertEqual(ret, {"letter": "L-slash", "dup": False})
        self.assertNotIn("board", v.DELIVERY_CACHE)
        rec = json.loads((Path(self.home.state) / "sent.jsonl").read_text())
        self.assertEqual((rec["kind"], rec["text"], rec["to"], rec["ok"]), ("slash", text, "board", True))
        self.assertEqual(v.read_sent(self.home), [])

    def record(self, age=0, **fields):
        rec = {"at": datetime.fromtimestamp(v.time.time() - age, timezone.utc).isoformat(),
               "kind": "slash", "to": "board", "text": "/goal", "ok": True, "letter": "L-old"}
        rec.update(fields)
        v.log_sent(self.home, rec)
        return rec

    def test_duplicate_and_resend_after_answer(self):
        ret = {}
        self.assertFalse(v.do_slash({"name": "board", "text": "/goal"}, self.tree, self.home, ret).startswith("!"))
        self.assertFalse(ret["dup"])
        v.SLASH_CACHE["board"] = {"at": v.time.time(), "rows": [{"message": {
            "role": "assistant", "content": "stale answer", "aos": {"answer_to": ["L-slash"]}}}]}
        self.run_json.side_effect = [{"history": {"messages": 0}}]
        result = v.do_slash({"name": "board", "text": "  /goal  "}, self.tree, self.home, ret)
        self.assertEqual(result, "/goal 已在排隊（還沒回），不重送")
        self.assertEqual(ret, {"dup": True, "letter": "L-slash"})
        self.run.assert_called_once()
        self.assertEqual(len((Path(self.home.state) / "sent.jsonl").read_text().splitlines()), 1)
        self.run_json.side_effect = [{"history": {"messages": 1}}, [{"message": {
            "role": "assistant", "content": "done", "aos": {"answer_to": ["L-slash"]}}}]]
        self.run.return_value = (0, "L-next\n", "")
        self.assertFalse(v.do_slash({"name": "board", "text": "/goal"}, self.tree, self.home, ret).startswith("!"))
        self.assertEqual(ret, {"dup": False, "letter": "L-next"})
        self.assertEqual(self.run.call_count, 2)

    def test_concurrent_requests_send_only_once(self):
        started, release, second_started, second_say = (threading.Event() for _ in range(4))
        results, errors, returns = [], [], [{}, {}]

        def slow_run(*args, **kwargs):
            if started.is_set():
                second_say.set()
            started.set()
            if not release.wait(5):
                raise RuntimeError("timed out waiting to finish send")
            return 0, "L-slash\n", ""

        def send(i):
            try:
                if i == 1:
                    second_started.set()
                results.append(v.do_slash({"name": "board", "text": "/goal"}, self.tree, self.home, returns[i]))
            except Exception as exc:
                errors.append(exc)

        self.run.side_effect = slow_run
        threads = [threading.Thread(target=send, args=(i,)) for i in range(2)]
        threads[0].start()
        try:
            self.assertTrue(started.wait(2))
            threads[1].start()
            self.assertTrue(second_started.wait(2))
            self.assertFalse(second_say.wait(0.2))
        finally:
            release.set()
            for thread in threads:
                if thread.ident is not None:
                    thread.join(5)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertTrue(all(not result.startswith("!") for result in results))
        self.assertEqual(returns, [{"dup": False, "letter": "L-slash"}, {"dup": True, "letter": "L-slash"}])
        self.run.assert_called_once()
        self.assertEqual(len((Path(self.home.state) / "sent.jsonl").read_text().splitlines()), 1)

    def test_old_or_different_requests_do_not_deduplicate(self):
        self.record(age=1801)
        self.record(text="/clear")
        self.record(to="other")
        self.record(ok=False)
        self.record(letter=None)
        self.record(kind="compact")
        ret = {}
        v.do_slash({"name": "board", "text": "/goal"}, self.tree, self.home, ret)
        self.assertEqual(ret, {"dup": False, "letter": "L-slash"})
        self.run.assert_called_once()
        self.run_json.assert_not_called()

    def test_latest_matching_request_controls_deduplication(self):
        older = self.record(age=5, letter="L-older", text="  /goal  ")
        self.record(at=older["at"], letter="L-newer")
        self.run_json.side_effect = [{"history": {"messages": 1}}, [{"message": {
            "role": "assistant", "content": "done", "aos": {"answer_to": ["L-older"]}}}]]
        ret = {}
        v.do_slash({"name": "board", "text": "/goal"}, self.tree, self.home, ret)
        self.assertEqual(ret, {"dup": True, "letter": "L-newer"})
        self.run.assert_not_called()

    def test_slash_rows_range_cache_and_unknown(self):
        rows = [{"message": {"role": "user", "content": str(i)}} for i in range(300)]
        self.run_json.side_effect = [{"history": {"messages": 900}}, rows]
        with patch.object(v.time, "time", return_value=100):
            self.assertEqual(v.slash_rows("board"), rows)
            self.assertEqual(v.slash_rows("board"), rows)
        self.assertEqual(self.run_json.call_count, 2)
        self.run_json.assert_any_call(["aos-agent", "ctl", "state", "-t", "board", "history", "-j"], timeout=8)
        self.run_json.assert_called_with(["aos-agent", "history", "-t", "board", "ls", "-j", "601-"], timeout=8)
        self.run_json.side_effect = [None, {"history": {"messages": 1}}, None,
                                     {"history": {"messages": 1}}, rows[:1]]
        with patch.object(v.time, "time", return_value=103):
            self.assertIsNone(v.slash_rows("board"))
            self.assertIsNone(v.slash_rows("other"))
            self.assertEqual(v.slash_rows("third"), rows[:1])
        self.run_json.assert_called_with(["aos-agent", "history", "-t", "third", "ls", "-j", "1-"], timeout=8)

    def test_slash_state(self):
        user = {"message": {"role": "user", "content": "/status", "aos": {"letter": "L-one"}}}
        answer = {"message": {"role": "assistant", "content": "first\nsecond", "aos": {"answer_to": ["L-other", "L-one"]}}}
        self.assertEqual(v.slash_state(None, "L-one"), ("unknown", ""))
        self.assertEqual(v.slash_state([], "L-one"), ("waiting", ""))
        self.assertEqual(v.slash_state([user], "L-one"), ("doing", ""))
        self.assertEqual(v.slash_state([user, answer], "L-one"), ("answered", "first\nsecond"))
        self.assertEqual(v.slash_state([user, answer], "missing"), ("waiting", ""))
        secret = "sk-" + "a" * 24
        answer["message"]["content"] = [{"type": "text", "text": secret + "\n" + "x" * 4100}]
        state, text = v.slash_state([answer], "L-one")
        self.assertEqual(state, "answered")
        self.assertEqual(len(text), 4000)
        self.assertTrue(text.endswith("…"))
        self.assertNotIn(secret, text)
        self.assertIn("\n", text)

    def test_slash_results_window_filters_and_limit(self):
        self.record(age=86401, letter="L-expired")
        for fields in ({"kind": "compact"}, {"ok": False}, {"letter": None}, {"to": "other"}):
            self.record(**fields)
        with (Path(self.home.state) / "sent.jsonl").open("a") as f:
            f.write("not json\n[]\n")
        self.assertEqual(v.slash_results(self.home, "board", self.node), {"items": [], "in_turn": False})
        for i in range(12):
            self.record(age=20 - i, letter="L-%d" % i)
        self.node["live"]["in_turn"] = True
        with patch.object(v, "slash_rows", return_value=[]):
            got = v.slash_results(self.home, "board", self.node)
        self.assertTrue(got["in_turn"])
        self.assertEqual([r["letter"] for r in got["items"]], ["L-%d" % i for i in range(11, 1, -1)])
        self.assertEqual(set(got["items"][0]), {"letter", "command", "at", "state", "text"})
        self.assertIsInstance(got["items"][0]["at"], (int, float))
        with patch.object(v, "slash_sent", return_value=[{"letter": "L-bad-time", "text": "/status", "at": "bad"}]), \
                patch.object(v, "slash_rows", return_value=[]):
            self.assertIsNone(v.slash_results(self.home, "board", self.node)["items"][0]["at"])
        self.assertEqual((got["items"][0]["command"], got["items"][0]["state"], got["items"][0]["text"]),
                         ("/goal", "waiting", ""))

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
                payload = json.dumps({"name": "board", "text": "/goal"})
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
                self.assertEqual((status, json.loads(body)["letter"], json.loads(body)["dup"]), (200, "L-slash", False))
                status, body = req("POST", payload, h)
                self.assertEqual((status, json.loads(body)["letter"], json.loads(body)["dup"]), (200, "L-slash", True))
                self.run.assert_called_once()
                path = "/api/slash_results?name=board"
                self.assertEqual(json.loads(req("GET", path=path)[1]), {"items": [{
                    "letter": "L-slash", "command": "/goal", "at": v.parse_time(json.loads(
                        (Path(self.home.state) / "sent.jsonl").read_text())["at"]), "state": "unknown", "text": ""}],
                    "in_turn": False})
                self.assertEqual(req("GET", headers={"Host": "bad"}, path=path)[0], 403)
                for name in ("", "missing", "proc"):
                    self.tree["nodes"]["proc"] = {"kind": "proc"}
                    self.assertEqual(req("GET", path="/api/slash_results?name=" + name)[0], 400)
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



class Peek(unittest.TestCase):
    """/status and /usage go through `aos-agent peek`: no queue, no history, answered while in a turn."""

    setUp = Slash.setUp

    def answer(self, code=0, out="", err="", timeout=False):
        proc = self.sub.return_value
        proc.pid, proc.returncode = 4321, code
        proc.communicate.side_effect = ([v.subprocess.TimeoutExpired("aos-agent", 300), ("", "")] if timeout else
                                        [(out, err)])
        self.peeks.pop(0)()

    def items(self):
        return v.slash_results(self.home, "board", self.node)["items"]

    def test_peek_in_turn_with_queue(self):
        self.node.update(queued=3, live={"cli": "claude", "in_turn": True})
        ret = {}
        result = v.do_slash({"name": "board", "text": "/usage"}, self.tree, self.home, ret)
        self.assertFalse(result.startswith("!"), result)
        self.assertIn("不用排隊", result)
        self.run.assert_not_called()
        self.run_json.assert_not_called()
        self.assertFalse(ret["dup"])
        self.assertTrue(ret["letter"].startswith("peek-"))
        sent = [json.loads(x) for x in Path(self.home.state, "sent.jsonl").read_text().splitlines()]
        self.assertEqual([(r["how"], r["text"], r["letter"]) for r in sent], [("peek", "/usage", ret["letter"])])
        self.assertEqual([(i["command"], i["state"]) for i in self.items()], [("/usage", "doing")])
        self.answer(out="Current session: 12% used\n")
        argv = self.sub.call_args.args[0]
        self.assertEqual(argv, ["aos-agent", "peek", "-t", "board", "/usage"])
        self.assertIs(self.sub.call_args.kwargs["stdin"], v.subprocess.DEVNULL)
        self.assertTrue(self.sub.call_args.kwargs["start_new_session"])
        self.killpg.assert_not_called()
        self.assertEqual([(i["state"], i["text"]) for i in self.items()], [("answered", "Current session: 12% used")])
        self.run.assert_not_called()

    def test_peek_dedup_only_while_doing(self):
        ret = {}
        v.do_slash({"name": "board", "text": "/status"}, self.tree, self.home, ret)
        first = ret["letter"]
        again = {}
        self.assertIn("還在做", v.do_slash({"name": "board", "text": " /status "}, self.tree, self.home, again))
        self.assertEqual(again, {"dup": True, "letter": first})
        self.assertEqual(len(self.peeks), 1)
        other = {}
        v.do_slash({"name": "board", "text": "/usage"}, self.tree, self.home, other)
        self.assertFalse(other["dup"])
        self.answer(out="ok")
        later = {}
        v.do_slash({"name": "board", "text": "/status"}, self.tree, self.home, later)
        self.assertFalse(later["dup"])
        self.assertNotEqual(later["letter"], first)

    def test_peek_failure_and_timeout(self):
        v.do_slash({"name": "board", "text": "/usage"}, self.tree, self.home, {})
        self.answer(code=2, err="aos-agent: CliFailed usage failed\n")
        v.do_slash({"name": "board", "text": "/status"}, self.tree, self.home, {})
        self.answer(timeout=True)
        self.killpg.assert_called_once_with(4321, v.signal.SIGKILL)       # the whole group, not only aos-agent
        got = {i["command"]: (i["state"], i["text"]) for i in self.items()}
        self.assertEqual(got["/usage"], ("answered", "（沒做成）aos-agent: CliFailed usage failed"))
        self.assertEqual(got["/status"], ("answered", "（沒做成）timeout after 300s"))
        v.do_slash({"name": "board", "text": "/usage"}, self.tree, self.home, {})
        self.sub.side_effect = ValueError("boom")
        self.peeks.pop(0)()
        self.assertEqual(self.items()[0]["text"], "（沒做成）ValueError: boom")    # never stuck in "doing"
        self.assertFalse(v.do_slash({"name": "board", "text": "/usage"}, self.tree, self.home, {}).startswith("!"))

    def test_only_newest_peek_rows_keep_queued_ones_visible(self):
        self.node["live"]["in_turn"] = True
        v.do_slash({"name": "board", "text": "/goal"}, self.tree, self.home, {})
        for _ in range(12):
            v.do_slash({"name": "board", "text": "/status"}, self.tree, self.home, {})
            self.answer(out="ok")
        with patch.object(v, "slash_rows", return_value=[]):
            got = [i["command"] for i in self.items()]
        self.assertEqual(sorted(got), ["/goal", "/status"])

    def test_peek_result_survives_restart(self):
        v.do_slash({"name": "board", "text": "/status"}, self.tree, self.home, {})
        self.answer(out="Model: x\nsk-ant-api03-" + "a" * 40)
        v.PEEK.clear()
        (state, text), = [(i["state"], i["text"]) for i in self.items()]
        self.assertEqual(state, "answered")
        self.assertTrue(text.startswith("Model: x\n"))
        self.assertNotIn("a" * 40, text)
        v.do_slash({"name": "board", "text": "/usage"}, self.tree, self.home, {})
        v.PEEK.clear()
        self.assertEqual(self.items()[0]["state"], "unknown")

    def test_peek_keeps_gates(self):
        self.assertTrue(v.do_slash({"name": "board", "text": "/usage now"}, self.tree, self.home).startswith("!"))
        self.node["state"] = "stopped"
        self.assertTrue(v.do_slash({"name": "board", "text": "/usage"}, self.tree, self.home).startswith("!"))
        self.assertEqual(self.peeks, [])


if __name__ == "__main__":
    unittest.main()
