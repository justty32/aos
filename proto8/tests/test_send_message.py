"""test_send_message - proto8/lib/aos/send_message（寄信工具：名冊、群組、上限、送不到、同時寫）直接叫。

11-04 前叫 test_talk、還跑 demo/talk（一個 daemon 同時跑 ann、bob、cat 三隻 member 互相寄信）；demo 刪了，跑團隊的 Team 四案一起刪，
寄信工具本身的案留下、改指 lib，名冊照 demo/talk/team/roster.json 原樣寫在這裡。
設計：proto8/thinking/2026-10/24/agent-talk/README.md。"""
import json, os, shutil, subprocess, tempfile, unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
SEND = str(ROOT / "lib" / "aos" / "send_message")    # 11-04 前經 demo/talk/member/tools/send_message 這個捷徑
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_ROSTER")
ROSTER = {"kind": "roster",
          "max_hops": 8, "max_sends": 4, "max_body_bytes": 16000,
          "members": {
              "ann": {"mailbox": "ann", "role": "統籌：接使用者的題目，拆成小事分給 bob、cat，收齊後把成果寄給 user"},
              "bob": {"mailbox": "bob", "role": "查與算：用工具查時間、算數字，回報數字與算式"},
              "cat": {"mailbox": "cat", "role": "整理：把拿到的材料寫成給人看的清楚段落"},
              "user": {"mailbox": "user", "role": "人類使用者：只收信、不會回信", "human": True}},
          "groups": {"all": ["ann", "bob", "cat"]}}


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


def letters(d):
    d = Path(d)
    return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))] if d.is_dir() else []


class SendMessage(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.ws = Path(self._t.name)
        self.roster = json.loads(json.dumps(ROSTER))
        for n in ("ann", "bob", "cat", "user"):
            (self.ws / n).mkdir()
        self.write_roster()

    def tearDown(self):
        self._t.cleanup()

    def write_roster(self):
        (self.ws / "roster.json").write_text(json.dumps(self.roster, ensure_ascii=False))

    def send(self, who, args, raw=None):
        return run(EXEC, "--ws", str(self.ws / who), SEND, input=raw if raw is not None else json.dumps(args, ensure_ascii=False),
                   env={"AOS_ROSTER": str(self.ws / "roster.json")})

    def test_deliver_and_sent_copy(self):
        r = self.send("user", {"to": "ann", "subject": "hi", "body": "你好", "expect_reply": True})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("已寄出 1 封", r.stdout)
        [l] = letters(self.ws / "ann" / "new")
        self.assertEqual((l["from"], l["to"], l["counter_hops"], l["reply_to"], l["thread"]), ("user", "ann", 1, None, l["id"]))
        self.assertTrue(l["expect_reply"])
        self.assertRegex(l["sent_at"], r"\A\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}")   # 寄出的時間（10-25 前叫 at）
        self.assertNotIn("at", l)
        self.assertEqual(letters(self.ws / "user" / "sent"), [l])
        self.assertEqual(list((self.ws / "ann" / "tmp").iterdir()), [])

    def test_group_excludes_self(self):
        r = self.send("ann", {"to": "all", "body": "大家好"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(letters(self.ws / "ann" / "new"), [])
        b, c = letters(self.ws / "bob" / "new"), letters(self.ws / "cat" / "new")
        self.assertEqual((len(b), len(c), b[0]["group"], b[0]["thread"]), (1, 1, "all", c[0]["thread"]))

    def test_model_errors_one_line(self):
        """模型的錯：照 lib 契約 stderr 與 stdout 各一行「send_message: 代號 原因」、退 1（10-24 遷移前是「錯誤：…」退 0）；回不回給腦由叫它的 agent 決定。"""
        for args, code, want in (({"to": "zed", "body": "x"}, "RecipientUnknown", "不認得「zed」"),
                                 ({"to": "ann", "body": "x"}, "RecipientMissing", "沒有收件人"),
                                 ({"to": "bob", "body": ""}, "ArgumentsBad", "body 要是非空字串"),
                                 ({"to": "bob", "body": "長" * 9000}, "BodyBad", "信太大")):
            r = self.send("ann", args)
            self.assertEqual(r.returncode, 1, (args, r.stdout))
            self.assertTrue(r.stdout.startswith("send_message: %s " % code), (args, r.stdout))
            self.assertEqual(r.stdout.strip(), r.stderr.strip())
            self.assertIn(want, r.stdout)
        self.assertEqual(letters(self.ws / "bob" / "new"), [])

    def test_mailbox_missing(self):
        shutil.rmtree(self.ws / "cat")
        r = self.send("ann", {"to": ["bob", "cat"], "body": "x"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("已寄出 1 封", r.stdout)
        self.assertIn("錯誤：送不到 cat", r.stdout)                       # 送到一部分＝結果、退 0
        shutil.rmtree(self.ws / "bob")
        r = self.send("ann", {"to": ["bob", "cat"], "body": "x"})
        self.assertEqual(r.returncode, 1)                                   # 一封都送不到＝錯
        self.assertTrue(r.stdout.startswith("send_message: MailboxMissing 送不到 "), r.stdout)

    def test_env_errors_exit_1(self):
        r = run(EXEC, "--ws", str(self.ws / "ann"), SEND, input="{}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("send_message: RosterMissing", r.stderr)
        (self.ws / "stranger").mkdir()
        r = self.send("stranger", {"to": "ann", "body": "x"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("send_message: SelfUnknown", r.stderr)

    def test_thread_follows_letter_in_cur_and_limits(self):
        self.roster.update(max_hops=3, max_sends=2)
        self.write_roster()
        self.send("user", {"to": "ann", "body": "題目", "expect_reply": True})
        (self.ws / "ann" / "cur").mkdir()
        [p] = (self.ws / "ann" / "new").iterdir()
        p.rename(self.ws / "ann" / "cur" / p.name)     # 假裝 ann 認領了
        r = self.send("ann", {"to": ["bob", "cat"], "body": "幫忙"})
        self.assertIn("第 2 手", r.stdout)
        b = letters(self.ws / "bob" / "new")[0]
        self.assertEqual((b["counter_hops"], b["reply_to"], b["thread"]), (2, p.stem, json.loads((self.ws / "ann" / "cur" / p.name).read_text())["thread"]))
        r = self.send("ann", {"to": "bob", "body": "再一封"})            # 這一層已寄 2 封＝上限
        self.assertTrue(r.stdout.startswith("send_message: SendsBad 處理這一封時已經寄了 2 封"), r.stdout)
        letter = json.loads((self.ws / "ann" / "cur" / p.name).read_text())
        letter["counter_hops"] = 3
        (self.ws / "ann" / "cur" / p.name).write_text(json.dumps(letter))
        r = self.send("ann", {"to": "bob", "body": "超過"})
        self.assertTrue(r.stdout.startswith("send_message: HopsBad 這個對話串已經傳了 3 手"), r.stdout)

    def test_many_senders_at_once(self):
        with ThreadPoolExecutor(10) as ex:
            rs = list(ex.map(lambda i: self.send(("bob", "cat")[i % 2], {"to": "ann", "body": "第 %d 封" % i}), range(20)))
        self.assertTrue(all(r.returncode == 0 for r in rs), [r.stderr for r in rs])
        got = letters(self.ws / "ann" / "new")
        self.assertEqual(sorted(l["body"] for l in got), sorted("第 %d 封" % i for i in range(20)))
        self.assertEqual(list((self.ws / "ann" / "tmp").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
