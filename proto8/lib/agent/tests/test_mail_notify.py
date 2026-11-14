"""mail_notify（on_clock 的 hook handler）：沒信箱、沒新信安靜；新信合成一句寄進 queue、只帶封數與寄件人；通知過的不重複；全新起來（first、沒有 notified.json 也沒有非空 history）只把等著的記成已知；跑過的 stack（有非空 history）當睡醒、在等的提醒一次；睡醒（first、有記錄）睡前提醒過的不重複、睡著時新到的提醒一次；讀掉的自然掉出記錄。"""
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
        # 全新起來（first、沒有記錄也沒有 history）不提醒信箱裡等著的，只記成已知；之後新到的才提醒
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
        (self.cell / "notified.json").unlink()                 # 沒有記錄也沒有 history：first 只記不提醒
        self.send("D")
        self.fire(first=True)
        self.assertEqual(len(self.notices()), 1)
        self.assertEqual(len(json.loads((self.cell / "notified.json").read_text())), 4)

    def test_first_without_record_but_with_history_tells_waiting(self):
        (self.stack / "history.jsonl").write_text('{"role": "user", "content": "before"}\n')
        self.assertFalse((self.cell / "notified.json").exists())
        subprocess.run(["aos-mailbox", "-s", str(self.stack), "where"], capture_output=True, check=True)
        self.send("A")
        waiting = sorted(d.name for d in (self.stack / "mailbox" / "new").iterdir())
        self.assertEqual(len(waiting), 1)
        self.fire(first=True)
        self.assertEqual(self.notices(), ["[aos] new_mail: 1 new letter from A. Look with mailbox_peek, read with mailbox_read."])
        self.assertEqual(json.loads((self.cell / "notified.json").read_text()), waiting)
        self.fire(first=True)
        self.fire()
        self.assertEqual(len(self.notices()), 1)

    def test_first_without_record_and_empty_history_only_marks(self):
        (self.stack / "history.jsonl").write_text("")
        (self.cell / "history.jsonl").write_text('{"role": "user", "content": "hook only"}\n')
        self.assertFalse((self.cell / "notified.json").exists())
        subprocess.run(["aos-mailbox", "-s", str(self.stack), "where"], capture_output=True, check=True)
        self.send("A")
        waiting = sorted(d.name for d in (self.stack / "mailbox" / "new").iterdir())
        self.assertEqual(len(waiting), 1)
        self.fire(first=True)
        self.assertEqual(self.notices(), [])
        self.assertEqual(json.loads((self.cell / "notified.json").read_text()), waiting)
        self.fire()
        self.assertEqual(self.notices(), [])

    def test_wake_tells_letters_that_came_while_asleep(self):
        # 使用者 11-11 選項框「睡著時新到的要提」：睡醒（first、有記錄）照 notified.json 比——睡前提醒過的不再提，睡著時到的提醒一次
        subprocess.run(["aos-mailbox", "-s", str(self.stack), "where"], capture_output=True, check=True)
        self.send("A")
        self.fire()
        self.assertEqual(len(self.notices()), 1)               # 睡前：A 提醒過
        self.send("B")                                         # 睡著時到的
        self.send("C")
        self.fire(first=True)                                  # 睡醒
        got = self.notices()
        self.assertEqual(got[1:], ["[aos] new_mail: 2 new letters from B, C. Look with mailbox_peek, read with mailbox_read."])
        self.fire(first=True)                                  # 再睡再醒、沒有新的：不重複
        self.fire()
        self.assertEqual(len(self.notices()), 2)

    def test_first_letter_while_asleep_without_mailbox_before(self):
        # 起來時連信箱都沒有、也沒有信：照樣留一份空記錄，睡著時才到的第一封醒來提得到
        self.fire(first=True)
        self.assertEqual(json.loads((self.cell / "notified.json").read_text()), [])
        self.assertFalse((self.stack / "mailbox").exists())
        subprocess.run(["aos-mailbox", "-s", str(self.stack), "where"], capture_output=True, check=True)   # 睡著時信箱才建好、寄來第一封
        self.send("A")
        self.fire(first=True)
        self.assertEqual(self.notices(), ["[aos] new_mail: 1 new letter from A. Look with mailbox_peek, read with mailbox_read."])

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
