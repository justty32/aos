# 驗證 autoreply_tick.py（清淨中自動回信、ok-* 一小時一次提醒、不回自己／urgent／自動回信、每封最多回一次、信讀掉就從 replied.json 移除）與 quiet.py status 的自動回信計數、config 讀法。
# 用真的 aos-mailbox；兩個暫存 stack（me、他人）各有信箱，不需要 daemon。
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import quiet  # noqa: E402


class AutoreplyTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="autoreply-test-", dir=os.environ.get("QUIET_TEST_TMP")))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env["PATH"] = os.pathsep.join([str(Path.home() / ".local" / "bin"), self.env["PATH"]])
        self.me = self.stack("me")
        (self.me / "quiet").mkdir()
        self.config({"urgent_senders": ["xiaosi"], "no_reply_senders": ["muted"], "redirect": {"senders": ["ok-*"], "to": "xiaosi"}})

    def stack(self, name):
        p = self.root / name
        p.mkdir()
        subprocess.run(["aos-mailbox", "-s", str(p), "where"], check=True, capture_output=True, env=self.env)
        return p

    def config(self, d):
        (self.me / "quiet" / "config.json").write_text(json.dumps(d))

    def run_cmd(self, *argv, text=None):
        return subprocess.run([str(a) for a in argv], input=text, capture_output=True, text=True, env=self.env)

    def mail(self, sender, title="hello", status="REQUEST"):
        """a letter from `sender` (its own stack) into my mailbox; returns the letter name."""
        s = self.root / sender
        if not s.exists():
            self.stack(sender)
        r = self.run_cmd("aos-mailbox", "-s", s, "send", "--box", self.me / "mailbox", "--from", sender, "--status", status, "--title", title, "text")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def tick(self):
        r = self.run_cmd(TOOLS / "autoreply_tick.py", text=json.dumps({"event": "on_clock", "stack": str(self.me)}))
        self.assertEqual(r.returncode, 0, r.stderr)

    def inbox(self, who):
        """(status, title, what, in_reply_to) of every letter waiting at `who`."""
        out = []
        for p in sorted((self.root / who / "mailbox" / "new").iterdir()):
            d = json.loads((p / "letter.json").read_text())
            out.append((d["body"]["status"], d["body"]["title"], d["body"]["what"], d.get("in_reply_to"), d["body"]["from"]))
        return out

    def quiet_on(self, spec="30m"):
        self.assertEqual(self.run_cmd(TOOLS / "quiet.py", "--stack", self.me, spec).returncode, 0)

    def replied(self):
        return json.loads((self.me / "autoreply" / "replied.json").read_text())

    def test_not_quiet_and_not_ok_means_no_reply(self):
        self.mail("bob")
        self.tick()
        self.assertEqual(self.inbox("bob"), [])

    def test_quiet_replies_once_and_leaves_the_letter(self):
        self.quiet_on()
        name = self.mail("bob")
        self.tick()
        self.tick()
        got = self.inbox("bob")
        self.assertEqual(len(got), 1)
        st, title, what, irt, frm = got[0]
        self.assertEqual((st, irt, frm), ("PROGRESS", name, "me"))
        self.assertTrue(title.startswith("[auto] me is in quiet time (until "), title)
        self.assertIn("xiaosi", what)
        self.assertIn("NEEDS-USER", what)
        self.assertTrue((self.me / "mailbox" / "new" / name).is_dir())     # 只看不收
        self.assertEqual(self.replied(), [name])

    def test_no_reply_to_xiaosi_muted_self_or_an_auto_reply(self):
        self.quiet_on()
        self.mail("xiaosi-digest")
        self.mail("muted-one")
        self.mail("me")
        self.mail("carol", title="[auto] carol is in quiet time (until 10:00): letter received, will be handled later")
        self.tick()
        for who in ("xiaosi-digest", "muted-one", "carol"):
            self.assertEqual(self.inbox(who), [], who)
        self.assertEqual(len(self.inbox("me")), 4)  # 自己寄給自己的那封還在、沒多出回信
        self.assertFalse((self.me / "autoreply" / "replied.json").exists())

    def test_two_auto_repliers_do_not_ping_pong(self):
        # 對方也是自動回信工具：我回它一封（它不會回「[auto]」開頭的），所以到此為止
        self.quiet_on()
        self.mail("bob")
        self.tick()
        title = self.inbox("bob")[0][1]
        self.mail("bob", title=title)           # bob 的自動回信回到我這
        self.tick()
        self.assertEqual(len(self.inbox("bob")), 1)

    def test_ok_reminder_once_an_hour_per_sender_even_when_not_quiet(self):
        a = self.mail("ok-kf")
        self.tick()
        got = self.inbox("ok-kf")
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0][1].startswith("[auto] reports to me should go to xiaosi"), got[0][1])
        self.mail("ok-kf")                       # 第二封：一小時內不再提醒
        self.tick()
        self.assertEqual(len(self.inbox("ok-kf")), 1)
        self.mail("ok-misc")                     # 別的寄件人照提醒
        self.tick()
        self.assertEqual(len(self.inbox("ok-misc")), 1)
        rem = self.me / "autoreply" / "reminded.json"
        d = json.loads(rem.read_text())
        d["ok-kf"] = time.time() - 3700          # 過了一小時
        rem.write_text(json.dumps(d))
        self.mail("ok-kf")
        self.tick()
        self.assertEqual(len(self.inbox("ok-kf")), 2)
        self.assertIn(a, self.replied())

    def test_quiet_and_ok_gives_one_letter_that_counts_as_the_reminder(self):
        self.quiet_on()
        self.mail("ok-kf")
        self.tick()
        got = self.inbox("ok-kf")
        self.assertEqual(len(got), 1)
        self.assertIn("quiet time", got[0][1])
        self.assertIn("send your reports to xiaosi", got[0][2])
        self.quiet_on("off")
        self.mail("ok-kf")                      # 清淨結束後的下一封：一小時內不再提醒
        self.tick()
        self.assertEqual(len(self.inbox("ok-kf")), 1)

    def test_replied_list_forgets_letters_that_were_read(self):
        self.quiet_on()
        a, b = self.mail("bob"), self.mail("amy")
        self.tick()
        self.assertEqual(sorted(self.replied()), sorted([a, b]))
        shutil.rmtree(self.me / "mailbox" / "new" / a)       # 讀掉
        self.tick()
        self.assertEqual(self.replied(), [b])

    def test_letters_from_before_the_quiet_time_are_not_answered(self):
        self.mail("bob")
        time.sleep(1.1)
        self.quiet_on()
        self.tick()
        self.assertEqual(self.inbox("bob"), [])

    def test_status_counts_auto_replies_and_resets_on_a_new_quiet_time(self):
        self.quiet_on()
        self.mail("bob")
        self.mail("amy")
        self.mail("ok-kf")
        self.tick()
        out = self.run_cmd(TOOLS / "quiet.py", "--stack", self.me, "status").stdout
        self.assertIn("auto-replies sent this quiet time: 3", out)
        self.quiet_on("90s")
        self.assertIn("auto-replies sent this quiet time: 0", self.run_cmd(TOOLS / "quiet.py", "--stack", self.me, "status").stdout)

    def test_autoreply_can_be_turned_off_and_no_config_means_nobody_is_special(self):
        self.config({"autoreply": False})
        self.quiet_on()
        self.mail("bob")
        self.tick()
        self.assertEqual(self.inbox("bob"), [])
        (self.me / "quiet" / "config.json").unlink()
        self.tick()                              # 沒設定：照回（他人都不特別），自己的名字取 stack 資料夾名
        self.assertIn("[auto] me is in quiet time", self.inbox("bob")[0][1])
        self.assertEqual(quiet.config(str(self.me))["urgent"], [])


if __name__ == "__main__":
    unittest.main()
