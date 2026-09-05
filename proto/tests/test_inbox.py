"""aosp/inbox.py：投遞、去重回信、無效投遞隔離、process() 分流、背壓。"""
import os
import sys

PROTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from aosp import fsutil, inbox, layout  # noqa: E402
from .helpers import LandCase  # noqa: E402


def _scan_kind(land, kind):
    return [obj for _p, obj in inbox.scan(land) if isinstance(obj, dict) and obj.get("kind") == kind]


class TestDeliverBasics(LandCase):
    def setUp(self):
        super().setUp()
        self.sender = layout.Land(os.path.join(self.tmp, "sender"))
        layout.init(self.sender.root)

    def test_deliver_writes_final_json_no_temp_left(self):
        obj = inbox.make("mail", self.sender.root, subject="hi", body="test")
        ok, info = inbox.deliver(self.land, obj)
        self.assertTrue(ok, msg="正常投遞應該成功，實際 %r" % (info,))
        final = os.path.join(self.land.inbox, "%s.json" % obj["id"])
        self.assertTrue(os.path.isfile(final), msg="投遞成功後檔案該在 .aos/inbox/<id>.json：%s" % final)
        self.assertFalse(os.path.isfile(final + ".temp"),
                          msg="投遞完不該留下 .temp 檔：%s" % (final + ".temp"))

    def test_duplicate_id_rejected_and_sender_gets_mail(self):
        obj = inbox.make("mail", self.sender.root, subject="hi", body="test")
        ok1, _ = inbox.deliver(self.land, obj)
        self.assertTrue(ok1, msg="第一次投遞應該成功")
        ok2, info2 = inbox.deliver(self.land, dict(obj))
        self.assertFalse(ok2, msg="同一個 id 再投一次應該被拒絕，實際 %r" % (info2,))
        replies = _scan_kind(self.sender, "mail")
        rejected = [m for m in replies if m.get("subject") == "rejected"]
        self.assertTrue(rejected,
                        msg="重複投遞被拒絕後，投遞者的收件匣應該收到一則 subject=rejected 的信，"
                            "實際投遞者收件匣裡的信：%r" % replies)


class TestProcessInvalidDeliveries(LandCase):
    def setUp(self):
        super().setUp()
        self.sender = layout.Land(os.path.join(self.tmp, "sender"))
        layout.init(self.sender.root)

    def _deliver_raw(self, obj):
        # 繞過 inbox.deliver() 沒做的驗證，直接放進收件匣（deliver() 本身不驗證，process() 才驗證）
        ok, info = inbox.deliver(self.land, obj)
        self.assertTrue(ok, msg="deliver() 本身不驗證內容，只要有 id 就該收下：%r" % (info,))
        return obj["id"]

    def _assert_rejected_and_mailed(self, obj_id):
        rejected_path = os.path.join(self.land.inbox_rejected, "%s.json" % obj_id)
        self.assertTrue(os.path.isfile(rejected_path),
                         msg="無效投遞該被 process() 搬到 .aos/inbox/rejected/<id>.json：%s" % rejected_path)
        inbox_path = os.path.join(self.land.inbox, "%s.json" % obj_id)
        self.assertFalse(os.path.isfile(inbox_path),
                          msg="搬走之後不該還留在收件匣：%s" % inbox_path)
        replies = _scan_kind(self.sender, "mail")
        rejected_mail = [m for m in replies if m.get("subject") == "rejected"]
        self.assertTrue(rejected_mail,
                        msg="無效投遞被拒後，投遞者應該收到一則 subject=rejected 的信，實際 %r" % replies)

    def test_missing_kind_rejected(self):
        obj = {"format_version": 1, "id": fsutil.new_id(), "from": self.sender.root,
               "at": fsutil.now_iso()}
        obj_id = self._deliver_raw(obj)
        inbox.process(self.land, tick=0)
        self._assert_rejected_and_mailed(obj_id)

    def test_unknown_kind_rejected(self):
        obj = {"format_version": 1, "id": fsutil.new_id(), "from": self.sender.root,
               "at": fsutil.now_iso(), "kind": "not-a-real-kind"}
        obj_id = self._deliver_raw(obj)
        inbox.process(self.land, tick=0)
        self._assert_rejected_and_mailed(obj_id)

    def test_inst_kind_without_argv_rejected(self):
        obj = {"format_version": 1, "id": fsutil.new_id(), "from": self.sender.root,
               "at": fsutil.now_iso(), "kind": "inst", "inst": {}}
        obj_id = self._deliver_raw(obj)
        inbox.process(self.land, tick=0)
        self._assert_rejected_and_mailed(obj_id)


class TestProcessRouting(LandCase):
    def setUp(self):
        super().setUp()
        self.sender = layout.Land(os.path.join(self.tmp, "sender"))
        layout.init(self.sender.root)

    def test_mail_kind_moved_to_mail_dir(self):
        obj = inbox.make("mail", self.sender.root, subject="hi", body="hello")
        inbox.deliver(self.land, obj)
        done = inbox.process(self.land, tick=0)
        self.assertIn(obj["id"], done["mail"], msg="process() 的回報應該列出這筆信，實際 %r" % done)
        self.assertTrue(os.path.isfile(os.path.join(self.land.mail, "%s.json" % obj["id"])),
                         msg="kind:mail 該被搬到 .aos/mail/")
        self.assertFalse(os.path.isfile(os.path.join(self.land.inbox, "%s.json" % obj["id"])),
                          msg="搬走之後不該還留在收件匣")

    def test_inst_kind_runs_and_produces_result(self):
        obj = inbox.make("inst", self.sender.root,
                          inst={"argv": [sys.executable, "-c", "pass"]})
        inbox.deliver(self.land, obj)
        done = inbox.process(self.land, tick=0)
        self.assertEqual(len(done["inst"]), 1, msg="process() 該回報跑了這一筆指令，實際 %r" % done)
        result_path = self.land.result_file(0, obj["id"])
        self.assertTrue(os.path.isfile(result_path),
                         msg="kind:inst 被 process() 跑起來，結果檔該出現：%s" % result_path)
        res = fsutil.read_json(result_path)
        self.assertEqual(res.get("exit_code"), 0, msg="pass 應該以 0 結束，實際 %r" % res)

    def test_llm_kind_left_untouched(self):
        obj = inbox.make("llm", self.sender.root, prompt="p.txt", result="r.txt")
        inbox.deliver(self.land, obj)
        done = inbox.process(self.land, tick=0)
        self.assertIn(obj["id"], done["left"], msg="kind:llm 該被回報成留在原地，實際 %r" % done)
        inbox_path = os.path.join(self.land.inbox, "%s.json" % obj["id"])
        self.assertTrue(os.path.isfile(inbox_path),
                        msg="kind:llm 不該被 process() 動掉，應該還留在收件匣：%s" % inbox_path)


class TestInboxBackpressure(LandCase):
    def setUp(self):
        super().setUp()
        self.sender = layout.Land(os.path.join(self.tmp, "sender"))
        layout.init(self.sender.root)
        cfg = fsutil.read_json(self.land.config, {}) or {}
        cfg["inbox_max"] = 1
        fsutil.write_json(self.land.config, cfg)

    def test_over_inbox_max_is_rejected(self):
        obj1 = inbox.make("mail", self.sender.root, subject="one", body="1")
        ok1, info1 = inbox.deliver(self.land, obj1)
        self.assertTrue(ok1, msg="inbox_max=1 時，第一筆該收下，實際 %r" % (info1,))

        obj2 = inbox.make("mail", self.sender.root, subject="two", body="2")
        ok2, info2 = inbox.deliver(self.land, obj2)
        self.assertFalse(ok2,
                         msg="inbox_max=1 已經有 1 封時，第二筆該被背壓拒收，實際 %r" % (info2,))
