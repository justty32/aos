# test_zone.py - aos-user 段 1 驗收（規劃 04 段 1 的 1～7 條＋verify＋網頁的 Host／token／重答）；全部在暫存夾，不碰 ~/.aos/user。
# 跑法（先清掉 AOS_* 環境）：python3 -m unittest discover -s $AOS_HOME/frontend/aos-user/tests -v
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "aos-user")
sys.path.insert(0, os.path.dirname(HERE))
import zone as Z  # noqa: E402

DECIDE = {"what": "two questions about the clock", "questions": [
    {"id": "q1", "question": "Support cron?", "eli5": "Clocks could ring by calendar. Or not.",
     "options": [{"key": "a", "label": "yes"}, {"key": "b", "label": "no"}], "recommend": "a", "why": "cheap"},
    {"id": "q2", "question": "Default tick?", "eli5": "How often it ticks. Faster costs more.",
     "options": [{"key": "a", "label": "1s"}, {"key": "b", "label": "1m"}], "recommend": "a"}]}


class T(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="zone-test-")
        self.zone = os.path.join(self.root, "user")
        self.agent = os.path.join(self.root, "agent")
        os.makedirs(self.agent)
        subprocess.run(["aos-post", "init", os.path.join(self.agent, "mailbox")], check=True)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.run_("init")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_(self, *args, stdin=None, agent=False, ok=True):
        env = dict(self.env, AOS_USER_ZONE=self.zone)
        if agent:
            env["AOS_STACK"] = self.agent
        p = subprocess.run([TOOL] + list(args), input=stdin, capture_output=True, text=True, env=env)
        if ok and p.returncode not in (0, 10):
            self.fail("aos-user %s failed: %s" % (" ".join(args), p.stderr))
        return p

    def send(self, data, kind="decide", title="clock questions"):
        return self.run_("send", "--kind", kind, "--title", title, stdin=json.dumps(data), agent=True).stdout.strip()

    def agent_new(self):
        d = os.path.join(self.agent, "mailbox", "new")
        return [json.load(open(os.path.join(d, n, "letter.json"))) for n in sorted(os.listdir(d))]

    def test_1_init_twice_keeps_files(self):
        door = os.path.join(self.zone, "door.json")
        with open(door, "w") as f:
            f.write('{"door": "mine"}')
        p = self.run_("init")
        self.assertIn("nothing changed", p.stdout)
        self.assertEqual(json.load(open(door)), {"door": "mine"})
        self.assertEqual(oct(os.stat(os.path.join(self.zone, "web", "token")).st_mode & 0o777), "0o600")

    def test_2_3_send_ls_show_answer(self):
        name = self.send(DECIDE)
        rows = json.loads(self.run_("ls", "--json").stdout)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["questions"], 2)
        self.run_("show", "1")
        self.assertTrue(os.path.isdir(os.path.join(self.zone, "mailbox", "cur", name)))
        p = self.run_("answer", "1", "q1:a", "q2:b*", "--note", "fine")
        self.assertIn("answered", p.stdout)
        got = self.agent_new()
        self.assertEqual(len(got), 1)
        b = got[0]["body"]
        for k in Z.STANDARD:
            self.assertIn(k, b)
        self.assertEqual(got[0]["in_reply_to"], name)
        self.assertEqual([a["differs"] for a in b["answers"]], [False, True])
        self.assertEqual(b["answer_line"], "q1:a、q2:b*（備註：fine）")
        month = time.strftime("%Y-%m")
        self.assertTrue(os.path.exists(os.path.join(self.zone, "done", month, name, "reply.json")))
        self.assertEqual(self.run_("ls").returncode, 10)

    def test_4_reply_box_missing(self):
        name = self.send(DECIDE)
        shutil.rmtree(os.path.join(self.agent, "mailbox"))
        p = self.run_("answer", "1", "q1:a", "q2:a", ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("MailboxMissing", p.stderr)
        self.assertTrue(os.path.isdir(os.path.join(self.zone, "mailbox", "cur", name)))
        self.assertTrue(os.path.exists(os.path.join(self.zone, "drafts", name + ".json")))

    def test_4b_own_reply_box_made(self):
        """11-23 使用者選 b：從沒收過信的 agent（stack 沒 mailbox/）第一次 send，自己的回信信箱先建好再寄。"""
        own = os.path.join(self.agent, "mailbox")
        shutil.rmtree(own)
        p = self.run_("send", "--kind", "decide", "--title", "first letter", stdin=json.dumps(DECIDE), agent=True)
        name = p.stdout.strip()
        self.assertIn("made your reply mailbox", p.stderr)
        for s in ("tmp", "new", "cur"):
            self.assertTrue(os.path.isdir(os.path.join(own, s)))
        lt = json.load(open(os.path.join(self.zone, "mailbox", "new", name, "letter.json")))
        self.assertEqual(os.path.normpath(os.path.join(self.zone, "mailbox", lt["reply_to"])), own)  # aos-post 存相對專區信箱的路徑
        self.run_("answer", "1", "--all-recommend")
        self.assertEqual(self.agent_new()[0]["in_reply_to"], name)
        p = self.run_("send", "--kind", "decide", "--title", "again", "--reply-to", own,   # 明寫自己的也算
                      stdin=json.dumps(DECIDE), agent=True)
        self.assertNotIn("made your reply mailbox", p.stderr)

    def test_4c_other_reply_box_not_made(self):
        """--reply-to 指到別處、$AOS_STACK 夾不在、$AOS_STACK 沒設：都不建，照舊 MailboxMissing，什麼都沒寄。"""
        other = os.path.join(self.root, "someone", "mailbox")
        p = self.run_("send", "--kind", "decide", "--title", "x", "--reply-to", other,
                      stdin=json.dumps(DECIDE), agent=True, ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("MailboxMissing", p.stderr)
        self.assertIn("aos-post init " + other, p.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.root, "someone")))
        shutil.rmtree(self.agent)
        p = self.run_("send", "--kind", "decide", "--title", "x", stdin=json.dumps(DECIDE), agent=True, ok=False)
        self.assertIn("MailboxMissing", p.stderr)
        self.assertIn("no stack is made for you", p.stderr)
        self.assertFalse(os.path.exists(self.agent))
        mine = os.path.join(self.root, "mine", "mailbox")
        p = self.run_("send", "--kind", "decide", "--title", "x", "--reply-to", mine,
                      stdin=json.dumps(DECIDE), ok=False)
        self.assertIn("$AOS_STACK is not set", p.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.root, "mine")))
        self.assertEqual(os.listdir(os.path.join(self.zone, "mailbox", "new")), [])

    def test_4d_own_reply_box_cannot_be_made(self):
        """自己的回信信箱建不起來（mailbox 是個一般檔）：一行錯誤、什麼都沒寄。"""
        own = os.path.join(self.agent, "mailbox")
        shutil.rmtree(own)
        with open(own, "w") as f:
            f.write("not a folder")
        p = self.run_("send", "--kind", "decide", "--title", "x", stdin=json.dumps(DECIDE), agent=True, ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("cannot make your reply mailbox", p.stderr)
        self.assertEqual(len(p.stderr.strip().splitlines()), 1)
        self.assertEqual(os.listdir(os.path.join(self.zone, "mailbox", "new")), [])

    def test_5_old_format(self):
        env = dict(self.env)
        subprocess.run(["aos-mailbox", "-s", self.agent, "send", "--box", os.path.join(self.zone, "mailbox"),
                        "--status", "NEEDS-USER", "--title", "old style question", "--decide", "a or b", "pick one"],
                       check=True, env=env, capture_output=True)
        rows = json.loads(self.run_("ls", "--json").stdout)
        self.assertEqual(rows[0]["format"], "old")
        self.run_("reply", "1", "take a")
        got = self.agent_new()
        self.assertEqual(got[0]["body"]["text"], "take a")

    def test_6_schema_bad(self):
        bad = json.loads(json.dumps(DECIDE))
        del bad["questions"][0]["recommend"]
        p = self.run_("send", "--kind", "decide", "--title", "x", stdin=json.dumps(bad), agent=True, ok=False)
        self.assertIn("SchemaBad", p.stderr)
        bad2 = json.loads(json.dumps(DECIDE))
        bad2["questions"][1]["options"] = [{"key": "a", "label": "only one"}]
        p = self.run_("send", "--kind", "decide", "--title", "x", stdin=json.dumps(bad2), agent=True, ok=False)
        self.assertIn("SchemaBad", p.stderr)
        p = self.run_("send", "--kind", "decide", "--title", "x", stdin=json.dumps(dict(DECIDE, risk="irreversible",
                      deadline="2026-12-01", default_if_silent="go")), agent=True, ok=False)
        self.assertIn("SchemaBad", p.stderr)
        self.assertEqual(os.listdir(os.path.join(self.zone, "mailbox", "new")), [])

    def test_7_dedupe(self):
        self.send(dict(DECIDE, dedupe_key="clock"))
        self.send(dict(DECIDE, dedupe_key="clock"))
        rows = json.loads(self.run_("ls", "--json").stdout)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["same"]), 1)
        self.run_("answer", "1", "--all-recommend")
        self.assertEqual(len(self.agent_new()), 2)

    def test_8_verify(self):
        self.send(DECIDE)
        self.run_("answer", "1", "q1:a", "q2:a")
        d = os.path.join(self.agent, "mailbox", "new")
        letter = os.path.join(d, os.listdir(d)[0])
        p = self.run_("verify", letter)
        self.assertIn("ok:", p.stdout)
        lj = os.path.join(letter, "letter.json")
        x = json.load(open(lj))
        x["body"]["answers"][0]["answer"] = "b"
        json.dump(x, open(lj, "w"))
        p = self.run_("verify", letter, ok=False)
        self.assertIn("VerifyBad", p.stderr)

    def test_9_fyi_ok_and_partial(self):
        self.send({"what": "build is green"}, kind="fyi", title="fyi build")
        p = self.run_("answer", "1", "q1:a", ok=False)
        self.assertIn("no questions", p.stderr)
        self.run_("ok", "1")
        self.assertEqual(self.agent_new(), [])
        self.send(DECIDE)
        p = self.run_("answer", "1", "q1:a", ok=False)
        self.assertIn("AnswerMissing", p.stderr)

    def test_10_web(self):
        import web
        port = 18766
        srv = web.ThreadingHTTPServer(("127.0.0.1", port), web.make_handler(self.zone, port))
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            name = self.send(DECIDE)
            base = "http://127.0.0.1:%d" % port
            r = urllib.request.urlopen(base + "/")
            self.assertIn("clock questions", r.read().decode())
            req = urllib.request.Request(base + "/", headers={"Host": "evil.example:%d" % port})
            with self.assertRaises(urllib.error.HTTPError) as c:
                urllib.request.urlopen(req)
            self.assertEqual(c.exception.code, 403)
            tok = open(os.path.join(self.zone, "web", "token")).read().strip()
            form = urllib.parse.urlencode({"token": tok, "letter": name, "action": "answer",
                                           "q_q1": "b", "q_q2": "a", "note": "web"}).encode()
            with self.assertRaises(urllib.error.HTTPError) as c:      # 沒 cookie
                urllib.request.urlopen(urllib.request.Request(base + "/answer", data=form))
            self.assertEqual(c.exception.code, 403)
            h = {"Cookie": "zt=" + tok}
            urllib.request.urlopen(urllib.request.Request(base + "/answer", data=form, headers=h))
            got = self.agent_new()
            self.assertEqual(got[0]["body"]["via"], "web")
            self.assertEqual(got[0]["body"]["answer_line"], "q1:b*、q2:a（備註：web）")
            with self.assertRaises(urllib.error.HTTPError) as c:      # 第二個分頁再答
                urllib.request.urlopen(urllib.request.Request(base + "/answer", data=form, headers=h))
            self.assertEqual(c.exception.code, 409)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
