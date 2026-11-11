"""mail_notify（on_clock 的 hook handler）：沒信箱、沒新信安靜；新信合成一句寄進 queue、只帶封數與寄件人；通知過的不重複；first（剛起來）不提醒、只把等著的記成已知；讀掉的自然掉出記錄。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[3]
ENTRY = PROTO / "lib" / "agent" / "mail_notify" / "_entry"


@unittest.skipUnless(shutil.which("aos-mailbox") and shutil.which("aos-post"), "aos-mailbox / aos-post not on PATH")
class MailNotify(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stack = Path(os.path.realpath(self.tmp.name)) / "b"
        self.cell = self.stack / "hooks" / "mail_notify"
        self.cell.mkdir(parents=True)

    def fire(self, first=False):
        ev = {"event": "on_clock", "hook": "mail_notify", "stack": str(self.stack), "first": first}
        r = subprocess.run([str(ENTRY)], input=json.dumps(ev), text=True, capture_output=True, timeout=30,
                           env=dict(os.environ, AOS_STACK=str(self.cell)))
        self.assertEqual((r.returncode, r.stderr, r.stdout), (0, "", ""))

    def send(self, sender, title="t", text="secret body text"):
        r = subprocess.run(["aos-mailbox", "send", "--box", str(self.stack / "mailbox"), "--from", sender,
                            "--status", "REQUEST", "--title", title, text], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)

    def notices(self):
        box = self.stack / "queue" / "new"
        if not box.is_dir():
            return []
        return [json.loads((d / "letter.json").read_text())["body"]["content"] for d in sorted(box.iterdir())]

    def test_quiet_without_mailbox_or_news(self):
        self.fire(first=True)
        self.assertFalse((self.stack / "mailbox").exists())   # 不替人建信箱
        self.assertEqual(self.notices(), [])
        subprocess.run(["aos-mailbox", "-s", str(self.stack), "where"], capture_output=True, check=True)
        self.fire()
        self.assertEqual(self.notices(), [])
        self.assertFalse((self.stack / "queue").exists())     # 沒新信＝連 queue 都不碰

    def test_one_line_per_batch_and_no_repeats(self):
        subprocess.run(["aos-mailbox", "-s", str(self.stack), "where"], capture_output=True, check=True)
        self.send("A")
        self.fire()
        self.assertEqual(self.notices(), ["[aos] new_mail: 1 new letter from A. Look with mailbox_peek, read with mailbox_read."])
        self.fire()
        self.assertEqual(len(self.notices()), 1)              # 通知過的不再提
        for who in ("B", "B", "A"):
            self.send(who)
        self.fire()
        got = self.notices()
        self.assertEqual(got[1], "[aos] new_mail: 3 new letters from B, A. Look with mailbox_peek, read with mailbox_read.")
        self.assertNotIn("secret", "".join(got))               # 不帶內文
        subprocess.run(["aos-mailbox", "-s", str(self.stack), "read", "--all"], capture_output=True, check=True)
        self.fire()
        self.assertEqual(json.loads((self.cell / "notified.json").read_text()), [])   # 讀掉的掉出記錄
        self.assertEqual(len(self.notices()), 2)

    def test_first_only_marks_waiting_letters(self):
        # 使用者 11-11 選項框「只提醒新到的」：剛起來（first）不提醒信箱裡等著的，只記成已知；之後新到的才提醒
        subprocess.run(["aos-mailbox", "-s", str(self.stack), "where"], capture_output=True, check=True)
        self.send("A")
        self.send("B")
        self.fire(first=True)
        self.assertEqual(self.notices(), [])
        self.assertEqual(len(json.loads((self.cell / "notified.json").read_text())), 2)
        self.fire()
        self.assertEqual(self.notices(), [])                   # 等著的兩封不會在下一次被當新信
        self.send("C")
        self.fire()
        self.assertEqual(self.notices(), ["[aos] new_mail: 1 new letter from C. Look with mailbox_peek, read with mailbox_read."])
        (self.cell / "notified.json").unlink()                 # 沒有記錄（例：小格被清）也一樣：first 只記不提醒
        self.send("D")
        self.fire(first=True)
        self.assertEqual(len(self.notices()), 1)
        self.assertEqual(len(json.loads((self.cell / "notified.json").read_text())), 4)

    def test_many_senders_are_cut(self):
        subprocess.run(["aos-mailbox", "-s", str(self.stack), "where"], capture_output=True, check=True)
        for who in "ABCDEFG":
            self.send(who)
        self.fire()
        self.assertEqual(self.notices(), ["[aos] new_mail: 7 new letters from A, B, C, D, E and 2 more. "
                                          "Look with mailbox_peek, read with mailbox_read."])

    def test_errors(self):
        r = subprocess.run([str(ENTRY)], input="not json", text=True, capture_output=True, timeout=30,
                           env=dict(os.environ, AOS_STACK=str(self.cell)))
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("mail_notify: error: ArgumentsBad "), r.stderr)
        r = subprocess.run([str(ENTRY), "--help"], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0)
        self.assertIn("usage: mail_notify", r.stdout)


if __name__ == "__main__":
    unittest.main()
