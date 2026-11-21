# test_delivery - delivery() marks what the user sent as queued / read / replied / unknown.
# No CLI is run: run_json is replaced by a fixture. Run through tests/run.sh.
import importlib.machinery
import importlib.util
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
VIEW = os.path.join(os.path.dirname(HERE), "bin", "aos-frontend")
if any(k.startswith("AOS_") for k in os.environ):
    sys.exit("test_delivery: AOS_* variables are set; run through tests/run.sh")
loader = importlib.machinery.SourceFileLoader("aosview_t", VIEW)
spec = importlib.util.spec_from_loader("aosview_t", loader)
V = importlib.util.module_from_spec(spec)
loader.exec_module(V)


class Delivery(unittest.TestCase):
    def setUp(self):
        V.DELIVERY_CACHE.clear()
        self.calls = []
        prefix = V.SAY_PREFIX

        def fake(args, timeout=15):
            self.calls.append(args)
            if args[:3] == ["aos-agent", "ctl", "state"]:
                return {"state": {"queued": 3}, "mailbox": {"waiting": 1, "letters": [{"letter": "m-wait"}]}, "history": {"messages": 4}}
            if args[:2] == ["aos-agent", "history"]:
                return [{"line": 3, "message": {"role": "user", "content": prefix + " hello there  (reply...)"}}]
            return None
        V.run_json = fake

    def test_states(self):
        now = time.time()
        outs = [{"letter": "m-wait", "kind": "mail", "sent_at": now - 50, "what": "x"},
                {"letter": "m-gone", "kind": "mail", "sent_at": now - 40, "what": "y"},
                {"letter": "m-ans", "kind": "mail", "sent_at": now - 30, "what": "z"},
                {"letter": "s-read", "kind": "say", "sent_at": now - 20, "what": "hello there"},
                {"letter": "s-new", "kind": "say", "sent_at": now - 10, "what": "not yet seen"},
                {"letter": "old", "kind": "mail", "sent_at": now - 9 * 86400, "what": "o"}]
        ins = [{"from": "bob", "in_reply_to": "m-ans", "sent_at": now - 25}]
        V.delivery("bob", outs, ins, now)
        got = {o["letter"]: o.get("delivery") for o in outs}
        self.assertEqual(got, {"m-wait": "queued", "m-gone": "read", "m-ans": "replied", "s-read": "read",
                               "s-new": "queued", "old": None})
        # bob's reply at now-25 came after s-read? no: s-read is now-20, reply earlier -> must not count
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(outs[0].get("queue_ahead"), 0)
        self.assertEqual(outs[4].get("queue_ahead"), 2)   # 3 queued, the newest say is last in the FIFO

    def test_unknown_and_cache(self):
        V.run_json = lambda args, timeout=15: None
        now = time.time()
        outs = [{"letter": "a", "kind": "mail", "sent_at": now - 5, "what": "x"},
                {"letter": "b", "kind": "say", "sent_at": now - 5, "what": "y"}]
        V.delivery("bob", outs, [], now)
        self.assertEqual([o["delivery"] for o in outs], ["unknown", "unknown"])


class Board(unittest.TestCase):
    def test_board(self):
        import tempfile
        d = tempfile.mkdtemp(prefix="aosview-board-")
        home = V.Home(d)
        self.assertIsNone(V.board_get(home))
        self.assertIn("空的", V.board_text(home))
        ok, msg = V.do_board({"text": "去睡午覺 sk-abcdefghijklmnopqrstuvwx", "back": "15:30"}, home)
        self.assertTrue(ok)
        b = V.board_get(home)
        self.assertTrue(b["text"].startswith("去睡午覺"))
        self.assertNotIn("abcdefghijklmnop", b["text"])       # masked
        self.assertIn("預計回來：15:30", V.board_text(home))
        ok, _ = V.do_board({"text": "x" * 1001}, home)
        self.assertFalse(ok)
        ok, msg = V.do_board({"text": ""}, home)
        self.assertTrue(ok and V.board_get(home) is None)


@unittest.skipUnless(__import__("shutil").which("aos-post"), "needs aos-post on PATH")
class Mail(unittest.TestCase):
    def test_mail_makes_the_agents_mailbox(self):
        """An agent that never got a letter has no <stack>/mailbox yet: the page's mail makes it, then sends."""
        import shutil
        import tempfile
        d = tempfile.mkdtemp(prefix="aosview-mail-")
        self.addCleanup(shutil.rmtree, d, True)
        stack = os.path.join(d, "procs", "ann")
        os.makedirs(stack)
        home = V.Home(os.path.join(d, "view"))
        home.init()
        tree = {"nodes": {"ann": {"kind": "agent", "stack": stack}}}
        ok, msg, letter = V.do_mail({"name": "ann", "title": "t1", "what": "what time"}, tree, home)
        self.assertTrue(ok, msg)
        self.assertTrue(os.path.isfile(os.path.join(stack, "mailbox", "new", letter, "letter.json")))
        ok, msg, letter2 = V.do_mail({"name": "ann", "title": "t2", "what": "again"}, tree, home)
        self.assertTrue(ok, msg)
        self.assertEqual(len(os.listdir(os.path.join(stack, "mailbox", "new"))), 2)


if __name__ == "__main__":
    unittest.main()
