# test_tick.py - aos-user 段 2 驗收：tick 收件檢查（7 題過、8 題退）、每寄件人每小時上限、退信、通知（含出門／安靜時段只報急件、關掉不報）、到期提醒、退信不繞回專區。
# 全部在暫存夾，不碰 ~/.aos/user；通知用假的 notifier 收，不真的跳 notify-send。跑法同 test_zone.py（先清掉 AOS_* 環境）。
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "aos-user")
sys.path.insert(0, os.path.dirname(HERE))
import zone as Z  # noqa: E402


def question(i, rec="a"):
    return {"id": "q%d" % i, "question": "question %d?" % i, "eli5": "Plain words. Two sentences.",
            "options": [{"key": "a", "label": "yes"}, {"key": "b", "label": "no"}], "recommend": rec}


def zone_body(n_questions=1, title="t", **more):
    b = {"zone": Z.ZONE_VER, "kind": "decide", "from": "alice", "to": "user", "status": "NEEDS-USER", "title": title,
         "what": "please decide", "host": "test", "outputs": "none", "not_done": "none", "decide": "see questions",
         "questions": [question(i) for i in range(1, n_questions + 1)]}
    b.update(more)
    return b


class Tick(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="zone-tick-")
        self.zone = os.path.join(self.root, "user")
        self.agent = os.path.join(self.root, "agent")
        os.makedirs(self.agent)
        subprocess.run(["aos-post", "init", os.path.join(self.agent, "mailbox")], check=True, capture_output=True)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        Z.init(self.zone)
        self.shown = []
        self.now = datetime.datetime(2026, 11, 13, 22, 0, 0)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def notifier(self, summary, body, urgent):
        self.shown.append((summary, body, urgent))

    def tick(self, now=None):
        return Z.tick(self.zone, now=now or self.now, notifier=self.notifier)

    def cli(self, *args, stdin=None):
        env = dict(self.env, AOS_USER_ZONE=self.zone, AOS_STACK=self.agent)
        return subprocess.run([TOOL] + list(args), input=stdin, capture_output=True, text=True, env=env)

    def raw(self, body, reply_to=None):
        """不經 aos-user send，直接用 aos-post 丟進專區（模擬不守規矩的寄件人）。"""
        env = dict(self.env, AOS_STACK=self.agent)
        rb = reply_to or os.path.join(self.agent, "mailbox")
        p = subprocess.run(["aos-post", "send", "--reply-to", rb, os.path.join(self.zone, "mailbox")],
                           input=json.dumps(body), capture_output=True, text=True, env=env, check=True)
        return p.stdout.strip()

    def agent_new(self):
        d = os.path.join(self.agent, "mailbox", "new")
        return [json.load(open(os.path.join(d, n, "letter.json"))) for n in sorted(os.listdir(d))]

    def test_1_seven_ok_eight_rejected_and_returned(self):
        b7 = {k: v for k, v in zone_body(7).items() if k in ("what", "questions")}
        p = self.cli("send", "--kind", "decide", "--title", "seven", stdin=json.dumps(b7))
        self.assertEqual(p.returncode, 0, p.stderr)
        b8 = dict(b7, questions=[question(i) for i in range(1, 9)])
        p = self.cli("send", "--kind", "decide", "--title", "eight", stdin=json.dumps(b8))
        self.assertEqual(p.returncode, 1)
        self.assertIn("SchemaBad at most 7 questions", p.stderr)
        bad = self.raw(zone_body(8, title="eight by hand"))
        r = self.tick()
        self.assertEqual(len(r["checked"]), 1)
        self.assertEqual([x["letter"] for x in r["rejected"]], [bad])
        rej = os.path.join(self.zone, "rejected", bad)
        self.assertTrue(os.path.isfile(os.path.join(rej, "letter.json")))
        self.assertIn("at most 7 questions", open(os.path.join(rej, "reason.txt")).read())
        self.assertFalse(os.path.exists(os.path.join(self.zone, "mailbox", "new", bad)))
        got = self.agent_new()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["in_reply_to"], bad)
        self.assertEqual(got[0]["body"]["status"], "FAILED")
        self.assertEqual(got[0]["body"]["returned"], bad)
        self.assertTrue(got[0]["body"]["title"].startswith("Returned: "))
        self.assertEqual(os.path.realpath(got[0]["sender"]), os.path.realpath(self.zone))
        rows = json.loads(self.cli("ls", "--json").stdout)
        self.assertEqual(len(rows), 1)
        rj = json.loads(self.cli("ls", "--rejected", "--json").stdout)
        self.assertEqual(rj[0]["letter"], bad)
        self.assertEqual(self.tick()["rejected"], [])           # 不重複檢查

    def test_2_per_hour_limit(self):
        Z.config_set(self.zone, max_per_hour=3)
        names = [self.raw(zone_body(1, title="n%d" % i)) for i in range(4)]
        r = self.tick()
        self.assertEqual(r["checked"], names[:3])
        self.assertEqual([x["letter"] for x in r["rejected"]], names[3:])
        self.assertIn("more than 3 letters", r["rejected"][0]["reason"])
        self.assertEqual(len(self.agent_new()), 1)
        late = self.raw(zone_body(1, title="an hour later"))
        r = self.tick(self.now + datetime.timedelta(minutes=61))
        self.assertEqual(r["checked"], [late])

    def test_3_notify_once_and_away_quiet(self):
        a = self.raw(zone_body(title="plain"))
        r = self.tick()
        self.assertEqual(r["notified"], [a])
        self.assertIn("1 new letter", self.shown[0][0])
        self.assertIn("plain (alice)", self.shown[0][1])
        self.assertEqual(self.tick()["notified"], [])            # 同一封只報一次
        Z.door_mode(self.zone, "away")
        b = self.raw(zone_body(title="later"))
        u = self.raw(zone_body(title="hurry", urgent=True))
        r = self.tick()
        self.assertEqual(r["notified"], [u])                     # 出門只報急件
        self.assertTrue(self.shown[-1][2])
        Z.door_mode(self.zone, "normal")
        Z.config_set(self.zone, quiet_hours="21:00-08:00")
        self.assertEqual(self.tick()["notified"], [])            # 安靜時段
        r = self.tick(self.now.replace(hour=9))
        self.assertEqual(r["notified"], [b])                     # 安靜過了才報
        c = self.raw(zone_body(title="seen first"))
        self.cli("show", c)
        self.assertEqual(self.tick(self.now.replace(hour=9))["notified"], [])   # 看過的不報

    def test_4_notify_off(self):
        Z.config_set(self.zone, notify=False)
        self.raw(zone_body(title="x"))
        r = self.tick()
        self.assertEqual(len(r["checked"]), 1)
        self.assertEqual((r["notified"], self.shown), ([], []))
        p = self.cli("notify", "on")
        self.assertIn("notify: on", p.stdout)
        self.assertEqual(len(self.tick()["notified"]), 1)       # 打開後補報還沒看過的

    def test_5_deadline_reminders(self):
        n = self.raw(zone_body(title="due", deadline="2026-11-14"))  # ＝11-15 00:00 到期
        self.tick(self.now - datetime.timedelta(days=2))
        r = self.tick(self.now)                                     # 離到期 26 小時：還不提醒
        self.assertEqual(r["reminded"], [])
        r = self.tick(self.now + datetime.timedelta(hours=3))
        self.assertEqual(r["reminded"], [{"letter": n, "stage": "soon"}])
        self.assertEqual(self.tick(self.now + datetime.timedelta(hours=4))["reminded"], [])
        r = self.tick(self.now + datetime.timedelta(days=2))
        self.assertEqual(r["reminded"], [{"letter": n, "stage": "overdue"}])
        p = self.cli("send", "--kind", "decide", "--title", "d", "--deadline", "next friday", stdin=json.dumps(
            {"questions": [question(1)]}))
        self.assertIn("SchemaBad deadline must be", p.stderr)

    def test_6_old_format_kept_broken_rejected_no_loop(self):
        env = dict(self.env, AOS_STACK=self.agent)
        subprocess.run(["aos-mailbox", "send", "--box", os.path.join(self.zone, "mailbox"), "--status", "NEEDS-USER",
                        "--title", "old way", "--", "pick one"], env=env, check=True, capture_output=True)
        loop = self.raw(zone_body(title="answer me in the zone"), reply_to=os.path.join(self.zone, "mailbox"))
        broken = os.path.join(self.zone, "mailbox", "new", "0broken")
        os.makedirs(broken)
        with open(os.path.join(broken, "letter.json"), "w") as f:
            f.write("{not json")
        r = self.tick()
        self.assertEqual(len(r["checked"]), 2)                   # 舊格式照收；回信地址在專區裡的，格式對也照收
        self.assertEqual(r["rejected"], [{"letter": "0broken", "reason": "letter.json is missing or not JSON",
                                          "returned": None, "error": "no reply_to"}])
        Z.config_set(self.zone, max_per_hour=1)
        loop2 = self.raw(zone_body(title="again"), reply_to=os.path.join(self.zone, "mailbox"))
        r = self.tick()
        self.assertEqual(r["rejected"][0]["letter"], loop2)
        self.assertIsNone(r["rejected"][0]["returned"])         # 退信地址在專區裡：不退，免得繞圈
        self.assertIn("inside the zone", r["rejected"][0]["error"])
        self.assertEqual(os.listdir(os.path.join(self.zone, "mailbox", "new")).count(loop), 1)

    def test_7_cli_tick_output(self):
        Z.config_set(self.zone, notify=False)                    # 指令列走真的 notify-send：測試裡關掉
        self.raw(zone_body(8, title="too many"))
        p = self.cli("tick")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("checked 0, rejected 1", p.stdout)
        p = self.cli("tick", "--quiet")
        self.assertEqual((p.returncode, p.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
