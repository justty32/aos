# test_zone.py - aos-user 段 1 驗收（規劃 04 段 1 的 1～7 條＋verify＋網頁的 Host／token／重答）＋逐題留言與公告（11-23）；全部在暫存夾，不碰 ~/.aos/user。
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

    # ---- 逐題留言（11-23 使用者「我不能自己留言？比如q3:"我覺得這個不錯"這樣」）----

    def answer_body(self):
        got = self.agent_new()
        self.assertEqual(len(got), 1)
        return got[0]["body"]

    def test_11_comment_three_ways(self):
        """q1:a:留言＝選 a 並留言；q2:一段話＝other；q3:other:留言；留言可有冒號、空白、中文；--note 並存。"""
        name = self.send(DECIDE3)
        self.run_("answer", "1", "q1:a:這個不錯: 真的", "q2:我覺得這個不錯", "q3:other:a: b c", "--note", "整封")
        b = self.answer_body()
        self.assertEqual(b["answers"], [
            {"id": "q1", "answer": "a", "differs": False, "comment": "這個不錯: 真的"},
            {"id": "q2", "answer": "other", "differs": True, "comment": "我覺得這個不錯"},
            {"id": "q3", "answer": "other", "differs": True, "comment": "a: b c"}])
        self.assertEqual(b["answer_line"], "q1:a「這個不錯: 真的」、q2:other*「我覺得這個不錯」、q3:other*「a: b c」（備註：整封）")
        self.assertIn('comment: "我覺得這個不錯"', b["what"])
        self.assertEqual(b["note"], "整封")
        self.assertEqual(self.agent_new()[0]["in_reply_to"], name)

    def test_12_plain_keys_have_no_comment(self):
        """沒留言的題沒有 comment 這一格；q:c* 與 q:c*:留言 照舊算 differs。"""
        self.send(DECIDE)
        self.run_("answer", "1", "q1:a", "q2:b*:slower is fine")
        b = self.answer_body()
        self.assertNotIn("comment", b["answers"][0])
        self.assertEqual(b["answers"][1], {"id": "q2", "answer": "b", "differs": True, "comment": "slower is fine"})
        self.assertEqual(b["answer_line"], "q1:a、q2:b*「slower is fine」")

    def test_13_code_like_but_not_an_option(self):
        """像代號卻不是選項：報錯、教 other:TEXT、什麼都沒寄（免得打錯字被當成留言）。"""
        name = self.send(DECIDE)
        for bad in ("q1:d", "q1:d*", "q1:zz:hello", "q1:", "q9:a", "nokey"):
            p = self.run_("answer", "1", bad, "q2:a", ok=False)
            self.assertEqual(p.returncode, 1, bad)
            self.assertIn("ArgumentsBad", p.stderr, bad)
        p = self.run_("answer", "1", "q1:d", "q2:a", ok=False)
        self.assertIn("q1:other:TEXT", p.stderr)
        self.assertEqual(self.agent_new(), [])
        self.assertTrue(os.path.isdir(os.path.join(self.zone, "mailbox", "cur", name)))

    def test_14_comment_verify_and_tamper(self):
        """留言是回信的一部分：verify 通過；改了留言就不過。"""
        self.send(DECIDE)
        self.run_("answer", "1", "q1:b:no cron for now", "q2:a")
        d = os.path.join(self.agent, "mailbox", "new")
        letter = os.path.join(d, os.listdir(d)[0])
        self.assertIn("ok:", self.run_("verify", letter).stdout)
        lj = os.path.join(letter, "letter.json")
        with open(lj) as f:
            x = json.load(f)
        x["body"]["answers"][0]["comment"] = "yes cron"
        with open(lj, "w") as f:
            json.dump(x, f)
        p = self.run_("verify", letter, ok=False)
        self.assertIn("VerifyBad", p.stderr)
        self.assertIn("answers", p.stderr)

    def test_15_draft_keeps_comment(self):
        name = self.send(DECIDE)
        p = self.run_("answer", "1", "q1:我再想想", ok=False)
        self.assertIn("AnswerMissing", p.stderr)
        with open(os.path.join(self.zone, "drafts", name + ".json")) as f:
            dr = json.load(f)
        self.assertEqual(dr["answers"], [{"id": "q1", "answer": "other", "differs": True, "comment": "我再想想"}])

    def test_16_web_comment_and_announce(self):
        import web
        port = 18769
        srv = web.ThreadingHTTPServer(("127.0.0.1", port), web.make_handler(self.zone, port))
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            name = self.send(DECIDE)
            base = "http://127.0.0.1:%d" % port
            tok = open(os.path.join(self.zone, "web", "token")).read().strip()
            h = {"Cookie": "zt=" + tok}

            def post(path, data):
                return urllib.request.urlopen(urllib.request.Request(base + path, data=urllib.parse.urlencode(
                    dict(data, token=tok)).encode(), headers=h)).read().decode()
            post("/answer", {"letter": name, "action": "draft", "q_q1": "a", "c_q1": "ok: fine", "c_q2": "own words"})
            with open(os.path.join(self.zone, "drafts", name + ".json")) as f:
                dr = json.load(f)
            self.assertEqual(dr["answers"], [{"id": "q1", "answer": "a", "comment": "ok: fine"},
                                             {"id": "q2", "answer": "other", "comment": "own words"}])
            page = urllib.request.urlopen(base + "/l/" + name).read().decode()
            self.assertIn("name='c_q1' placeholder=", page)
            self.assertIn(">ok: fine</textarea>", page)
            post("/answer", {"letter": name, "action": "answer", "q_q1": "a", "c_q1": "ok: fine", "c_q2": "1m"})
            b = self.answer_body()
            self.assertEqual(b["answer_line"], "q1:a「ok: fine」、q2:other*「1m」")   # 只寫留言＝other，留言像代號也不會被當代號
            self.assertEqual(b["via"], "web")
            post("/announce", {"action": "set", "text": "lunch", "for": "90m"})
            self.assertEqual(self.door()["announce"]["text"], "lunch")
            self.assertIn("lunch", urllib.request.urlopen(base + "/").read().decode())
            self.assertIn("lunch", urllib.request.urlopen(base + "/door").read().decode())
            post("/announce", {"action": "clear"})
            self.assertNotIn("announce", self.door())
        finally:
            srv.shutdown()
            srv.server_close()

    # ---- 公告（11-23 使用者「aos-user annouce "我去睡午覺，一小時後回來"」）----

    def door(self):
        with open(os.path.join(self.zone, "door.json")) as f:
            return json.load(f)

    def test_20_announce_show_set_replace_clear(self):
        p = self.run_("announce")
        self.assertEqual((p.returncode, p.stdout.strip()), (10, "no announcement"))
        self.run_("announce", "我去睡午覺，一小時後回來")
        a = self.door()["announce"]
        self.assertEqual((a["text"], a["until"]), ("我去睡午覺，一小時後回來", None))
        self.assertIn("announce: 我去睡午覺", self.run_("announce").stdout)
        self.run_("announce", "back", "at", "three")           # 新的蓋掉舊的；多個字併成一句
        self.assertEqual(self.door()["announce"]["text"], "back at three")
        self.assertIn("back at three", json.loads(self.run_("door").stdout)["announce"]["text"])
        self.assertIn("announcement taken down", self.run_("announce", "--clear").stdout)
        self.assertNotIn("announce", self.door())
        self.assertIn("no announcement to take down", self.run_("announce", "--clear").stdout)
        for bad in (("--clear", "x"), ("--until", "2026-01-01"), ("x", "--for", "5x"), ("x", "--for", "0m"),
                    ("x", "--until", "2020-01-01"), ("x", "--until", "soon"), ("x", "--for", "1h", "--until", "2099-01-01")):
            p = self.run_("announce", *bad, ok=False)
            self.assertEqual(p.returncode, 1, bad)
            self.assertIn("ArgumentsBad", p.stderr, bad)

    def test_21_announce_until_and_for(self):
        self.run_("announce", "away", "--until", "2099-11-23T15:00")
        self.assertTrue(self.door()["announce"]["until"].startswith("2099-11-23T15:00:00"))
        self.run_("announce", "nap", "--for", "90m")
        a = self.door()["announce"]
        left = (Z.parse_deadline(a["until"]) - Z.parse_deadline(a["at"])).total_seconds()
        self.assertTrue(5390 <= left <= 5410, left)
        self.run_("announce", "trip", "--until", "2099-12-01")        # 只寫日期＝那天結束
        self.assertTrue(self.door()["announce"]["until"].startswith("2099-12-02T00:00:00"))

    def test_22_announce_expired_is_gone(self):
        """過期的：announce、door、ls 都不再出現（檔不動）；tick 時從門上拿掉。"""
        d = self.door()
        d["announce"] = {"text": "old nap", "at": "2020-01-01T10:00:00+0000", "until": "2020-01-01T11:00:00+0000"}
        with open(os.path.join(self.zone, "door.json"), "w") as f:
            json.dump(d, f)
        self.assertEqual(self.run_("announce").returncode, 10)
        self.assertNotIn("announce", json.loads(self.run_("door").stdout))
        self.assertNotIn("announcement", self.run_("ls").stdout)
        self.assertIn("announce", self.door())
        Z.tick(self.zone, notifier=lambda *a: None)
        self.assertNotIn("announce", self.door())
        self.assertEqual(self.door()["mode"], "normal")

    def test_23_announce_keeps_mode_and_ls_reminds(self):
        self.run_("door", "--mode", "away")
        before = self.door()
        self.run_("announce", "out until five", "--for", "2h")
        after = self.door()
        self.assertEqual(after["mode"], "away")
        self.assertEqual({k: v for k, v in after.items() if k != "announce"}, before)
        self.run_("door", "--mode", "normal")                   # 切模式不動公告
        self.assertEqual(self.door()["announce"]["text"], "out until five")
        self.assertIn("your announcement is up", self.run_("ls").stdout)
        self.send(DECIDE)
        out = self.run_("ls").stdout.strip().splitlines()
        self.assertIn("aos-user announce --clear", out[-1])
        self.assertEqual(len(json.loads(self.run_("ls", "--json").stdout)), 1)   # --json 不多印
        self.run_("announce", "--clear")
        self.assertEqual(self.door(), dict(before, mode="normal"))


DECIDE3 = {"what": "three questions", "questions": DECIDE["questions"] + [
    {"id": "q3", "question": "Name?", "eli5": "What to call it. Short is better.",
     "options": [{"key": "a", "label": "tick"}, {"key": "b", "label": "beat"}, {"key": "c", "label": "pulse"}],
     "recommend": "b"}]}


if __name__ == "__main__":
    unittest.main()
