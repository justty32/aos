"""must 通道收口（RV-fix-C）：author 不替別人建 events 夾、不替別人的事件 ack；同 node 混 mail 與 author 誰都不替對方確認。"""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_author import TOP, TestAuthorHelpers, pub, write_json
_, reader, store = pub._events()
MAIL = TOP / "modules/mail/aos7-mail"


class TestAuthorMustMixed(TestAuthorHelpers):
    def acked(self, events):
        return store.load_state(events)["channels"]["must"]["acked_upto"]

    def registered(self, node, rid="csv1"):
        return Path(node, "author/req", rid, "request.json").exists()

    def blocked_cli(self, node, seq, kind):
        """CLI：退 1、stdout JSON 有 blocked、stderr 一行說是誰擋住與怎麼辦。"""
        p = subprocess.run([sys.executable, str(self.author_bin), "intake"], cwd=node,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 1, (p.stdout, p.stderr))
        self.assertEqual(json.loads(p.stdout)["blocked"]["seq"], seq)
        self.assertEqual(len(p.stderr.splitlines()), 1, p.stderr)
        for word in ("aos7-author: ", kind, "aos7-events ack"):
            self.assertIn(word, p.stderr)

    @property
    def author_bin(self):
        return TOP / "packs/author/bin/aos7-author"

    def test_send_does_not_create_events(self):
        node = self.mknode()
        path = self.request(node)
        events = str(Path(node, "events"))
        r = self.refused(pub.send_request(node, str(path), events), "conflict")   # 函式路徑也擋
        self.assertIn("aos7-up", r["error"])
        p = subprocess.run([sys.executable, str(self.author_bin), "send", str(path)], cwd=node,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 1, (p.stdout, p.stderr))
        self.assertEqual(len(p.stderr.splitlines()), 1, p.stderr)
        self.assertIn("aos7-events pub --create", p.stderr)
        self.assertFalse(os.path.lexists(events))
        self.assertFalse(Path(node, "author").exists())

    def test_foreign_blocks_until_owner_acks(self):
        node = self.mknode()
        events = str(Path(node, "events"))
        ep, _, _ = pub._events()
        self.assertTrue(ep.publish(events, "other.request", "x/1", {}, must=True, node="a")["ok"])
        self.good(pub.send_request(node, str(self.request(node)), events))
        got = self.refused(pub.intake(node, events), "conflict")
        self.assertEqual(got["blocked"], dict(seq=1, kind="other.request", event_id="x/1"))
        self.assertEqual((self.acked(events), self.registered(node)), (0, False))
        self.blocked_cli(node, 1, "other.request")
        self.assertEqual(store.ack(events, 1), 1)                                # 主人確認後才讓過
        got = self.good(pub.intake(node, events))
        self.assertEqual((got["handled"], got["acked_upto"]), ([dict(seq=2, rid="csv1", result="registered")], 2))

    def test_mail_and_author_share_node(self):
        """mail(1) author(2) mail(3)：兩邊各跑、author 重啟（含回條後被殺），誰都不替對方 ack。"""
        root = Path(self.root, "post")
        node = str(root / "bob")
        self.mknode(root=str(root), nid="bob")
        events = str(Path(node, "events"))
        os.mkdir(events)

        def mail(*args):
            p = subprocess.run([str(MAIL), "--root", str(root), *args], capture_output=True, text=True, timeout=30)
            self.assertEqual(p.returncode, 0, p.stderr)
            return p.stdout

        first = json.loads(mail("send", "alice", "bob", "第一封"))
        self.good(pub.send_request(node, str(self.request(node)), events))
        third = json.loads(mail("send", "alice", "bob", "第三封"))
        kinds = [r["kind"] for r in reader.read(events, "must")["records"]]
        self.assertEqual(kinds, ["mail.request", "author.request", "mail.request"])

        for _ in range(2):                                                       # author 先跑＋重啟：卡在 mail(1)
            got = self.refused(pub.intake(node, events), "conflict")
            self.assertEqual(got["blocked"]["kind"], "mail.request")
            self.assertEqual((self.acked(events), self.registered(node)), (0, False))
        self.blocked_cli(node, 1, "mail.request")

        mail("read", "bob")
        mail("done", "bob", Path(first["sent"]).name, "辦完第一封")
        self.assertEqual(self.acked(events), 1, "mail 只確認自己的 1，不越過 author 的 2")
        self.assertFalse(self.registered(node))

        self.cli(node, "intake", rc=-9, crash="intake-before-receipt")           # 登記好、回條前被殺
        self.assertEqual(self.acked(events), 1)
        self.assertTrue(self.registered(node))
        for handled in ([dict(seq=2, rid="csv1", result="dup")], []):           # 重啟兩次：收 2、卡在 mail(3)
            got = self.refused(pub.intake(node, events), "conflict")
            self.assertEqual((got["handled"], got["blocked"]["seq"]), (handled, 3))
            self.assertEqual(self.acked(events), 2, "author 不替 mail(3) ack")
        self.assertTrue(Path(node, "inbox", Path(third["sent"]).name).exists())

    def test_author_first_kill_after_receipt(self):
        """author(1) mail(2) author(3)：回條後 ack 前被殺、恢復補 ack 前再被殺兩次，都不越過 mail(2)。"""
        node = self.mknode()
        events = str(Path(node, "events"))
        os.mkdir(events)
        ep, _, _ = pub._events()
        self.good(pub.send_request(node, str(self.request(node)), events))
        self.assertTrue(ep.publish(events, "mail.request", "m/2", {"id": "m/2"}, must=True, node="a")["ok"])
        self.good(pub.send_request(node, str(self.request(node, "next")), events))
        for _ in range(3):
            self.cli(node, "intake", rc=-9, crash="intake-after-receipt")
            self.assertEqual(self.acked(events), 0)
        self.assertTrue(self.registered(node))
        got = self.refused(pub.intake(node, events), "conflict")
        self.assertEqual((got["handled"], got["blocked"]["seq"], self.acked(events)), ([], 2, 1))
        self.assertFalse(self.registered(node, "next"))

    def test_old_ignored_receipt_not_acked(self):
        """舊版帳 last.result=ignored（ack 前被殺）：新版不把它當處理完，從那筆重讀並停下。"""
        node = self.mknode()
        events = str(Path(node, "events"))
        ep, _, _ = pub._events()
        self.assertTrue(ep.publish(events, "mail.request", "m/1", {"id": "m/1"}, must=True, node="a")["ok"])
        self.good(pub.send_request(node, str(self.request(node)), events))
        os.makedirs(Path(node, "author"), exist_ok=True)
        last = dict(seq=1, event_id="m/1", rid=None, result="ignored", request_sha=None, error="外來 kind")
        write_json(str(Path(node, "author/events.json")), dict(v=1, events=os.path.realpath(events), cursor=2, last=last))
        for _ in range(2):
            got = self.refused(pub.intake(node, events), "conflict")
            self.assertEqual((got["blocked"]["seq"], self.acked(events)), (1, 0))
        self.assertEqual(store.ack(events, 1), 1)                                # 已確認的舊 ignored：讓過
        got = self.good(pub.intake(node, events))
        self.assertEqual(got["handled"], [dict(seq=2, rid="csv1", result="registered")])
