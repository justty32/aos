#!/usr/bin/env python3
"""test_cli.py：aos-gate 命令列的測試（ctest 會跑）。只用標準庫（unittest）。

    python3 tests/test_cli.py bin/aos-gate

不需要真的 kernel：測試自己當 kernel（看 new/ 裡的信、搬到 cur/、done/、寫回信），所以只測閘門這一半。
A 段：命令列、信箱、單子檔的錯；B 段：信的內容（指示詞在閘門的環境解、AOS_CF／AOS_CD／AOS_CO、cwd 轉絕對、整份環境、priority 原樣）；
C 段：回信原樣交回（stdout、stderr、碼、kernel 回的錯、讀不懂的回信）；D 段：訊號撤信、信不見了、kernel 不在時一直等。
gate＋kernel 一起跑的在 proto8/tests/test_kernel_llm.py。
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

BIN = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                      os.path.join(os.path.dirname(__file__), "..", "bin", "aos-gate"))


def until(f, secs=5):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        v = f()
        if v:
            return v
        time.sleep(0.01)
    return None


class Case(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.t = Path(self.td.name)
        self.mb = self.t / "mb"
        self.mb.mkdir()

    def tearDown(self):
        self.td.cleanup()

    def env(self, extra=None, kernel=True):
        e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        if kernel:
            e["AOS_KERNEL"] = str(self.mb)
        e.update(extra or {})
        return e

    def inst(self, doc, name="q.json"):
        p = self.t / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc) if not isinstance(doc, str) else doc)
        return name

    def start(self, spec="q.json", extra=None, kernel=True, cwd=None):
        return subprocess.Popen([BIN, spec], env=self.env(extra, kernel), cwd=cwd or self.t, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)

    def run_g(self, spec="q.json", extra=None, kernel=True):
        return subprocess.run([BIN, spec], env=self.env(extra, kernel), cwd=self.t, capture_output=True, text=True,
                              timeout=30)

    def own_error(self, r, code):
        rc, err = (r.returncode, r.stderr)
        self.assertEqual(rc, 1, err)
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertTrue(err.startswith("aos-gate: %s " % code), err)

    def letter(self):
        """等 new/ 出現一封信，回 (id, letter)。"""
        ids = until(lambda: os.listdir(self.mb / "new") if (self.mb / "new").exists() else [])
        self.assertTrue(ids, "沒寄信")
        return ids[0], json.loads((self.mb / "new" / ids[0] / "letter.json").read_text())

    def answer(self, id, reply, out=None, err=None):
        """假 kernel：new → cur、寫 stdout／stderr／reply.json、cur → done。"""
        (self.mb / "cur").mkdir(exist_ok=True)
        os.rename(self.mb / "new" / id, self.mb / "cur" / id)
        d = self.mb / "cur" / id
        if out is not None:
            (d / "stdout.txt").write_text(out)
        if err is not None:
            (d / "stderr.txt").write_text(err)
        (d / "reply.json").write_text(reply if isinstance(reply, str) else json.dumps(reply))
        (self.mb / "done").mkdir(exist_ok=True)
        os.rename(d, self.mb / "done" / id)


class A_Errors(Case):
    def test_usage(self):
        r = subprocess.run([BIN], env=self.env(), capture_output=True, text=True)
        self.own_error(r, "ArgumentsBad")
        r = subprocess.run([BIN, "a", "b"], env=self.env(), capture_output=True, text=True)
        self.own_error(r, "ArgumentsBad")
        r = subprocess.run([BIN, "--x", "1", "a"], env=self.env(), capture_output=True, text=True)
        self.own_error(r, "FlagUnknown")

    def test_mailbox_missing(self):
        self.inst({"argv": ["true"]})
        self.own_error(self.run_g(kernel=False), "MailboxMissing")
        self.own_error(self.run_g(extra={"AOS_KERNEL": ""}), "MailboxMissing")
        self.own_error(self.run_g(extra={"AOS_KERNEL": str(self.t / "nope")}), "MailboxMissing")
        self.assertFalse((self.mb / "new").exists())

    def test_inst_file_errors(self):
        self.own_error(self.run_g("nope.json"), "CfgMissing")
        self.inst("{", "bad.json")
        self.own_error(self.run_g("bad.json"), "CfgBad")
        self.inst([1], "arr.json")
        self.own_error(self.run_g("arr.json"), "CfgBad")
        self.inst({"argv": [{"$env": "NOT_SET_X"}]}, "d.json")
        self.own_error(self.run_g("d.json"), "DirectiveBad")
        self.assertEqual(os.listdir(self.mb / "new") if (self.mb / "new").exists() else [], [])

    def test_priority_bad_not_sent(self):
        for p in ("urgent", True, [1], {"level": "x"}, {"deadline": "soon"}, {"deadline": "2026-10-24T10:00:00"}):
            self.inst({"argv": ["true"], "priority": p})
            self.own_error(self.run_g(), "PriorityBad")
        self.assertEqual(os.listdir(self.mb / "new") if (self.mb / "new").exists() else [], [])


class B_Letter(Case):
    def test_letter_shape(self):
        (self.t / "sub").mkdir()
        self.inst({"big": {"argv": ["echo", {"$env": "FOO"}, {"$env": "AOS_CO"}], "cwd": "sub",
                           "stdout": {"$env": "AOS_CD", "$path": "/o.txt"}, "priority": {"level": "high", "x": 1}}},
                  "cells/q.json")
        p = self.start("cells/q.json#/big", extra={"FOO": "bar"})
        id, letter = self.letter()
        cd = str((self.t / "cells").resolve())
        self.assertEqual(letter["inst"]["argv"], ["echo", "bar", "/big"])   # 指示詞在閘門的環境解
        self.assertEqual(letter["inst"]["cwd"], cd + "/sub")                 # 從單子檔的資料夾算、轉絕對
        self.assertEqual(letter["inst"]["stdout"], cd + "/o.txt")
        self.assertEqual(letter["priority"], {"level": "high", "x": 1})    # 原樣
        self.assertEqual(letter["env"]["FOO"], "bar")                        # 整份環境
        self.assertEqual(letter["env"]["AOS_CF"], cd + "/q.json")
        self.assertEqual(letter["env"]["AOS_CD"], cd)
        self.assertEqual(letter["env"]["AOS_CO"], "/big")
        self.assertEqual(letter["env"]["AOS_KERNEL"], str(self.mb))
        pid, t = id.split(".")[1:]
        self.assertEqual(int(pid), p.pid)
        self.assertEqual(os.listdir(self.mb / "tmp"), [])
        self.answer(id, {"code": 0, "signal": None})
        p.communicate(timeout=10)

    def test_cwd_default(self):
        self.inst({"argv": ["true"]})
        p = self.start()
        id, letter = self.letter()
        self.assertEqual(letter["inst"]["cwd"], str(self.t.resolve()))
        self.assertIsNone(letter["priority"])
        self.answer(id, {"code": 0, "signal": None})
        p.communicate(timeout=10)

    def test_ids_in_order(self):
        self.inst({"argv": ["true"]})
        ps = []
        for _ in range(3):
            ps.append(self.start())
            until(lambda: len(os.listdir(self.mb / "new")) == len(ps) if (self.mb / "new").exists() else False)
        ids = sorted(os.listdir(self.mb / "new"))
        self.assertEqual([int(i.split(".")[1]) for i in ids], [p.pid for p in ps])   # 字典序＝寄的先後
        for i in ids:
            self.answer(i, {"code": 0, "signal": None})
        for p in ps:
            p.communicate(timeout=10)


class C_Relay(Case):
    def test_relay(self):
        self.inst({"argv": ["true"]})
        p = self.start()
        id, _ = self.letter()
        self.answer(id, {"code": 7, "signal": None}, out="答案\n", err="警告\n")
        out, err = p.communicate(timeout=10)
        self.assertEqual((p.returncode, out, err), (7, "答案\n", "警告\n"))
        self.assertFalse((self.mb / "done" / id).exists())   # 讀完就刪

    def test_signal_code(self):
        self.inst({"argv": ["true"]})
        p = self.start()
        id, _ = self.letter()
        self.answer(id, {"code": 143, "signal": 15})
        p.communicate(timeout=10)
        self.assertEqual(p.returncode, 143)

    def test_kernel_error(self):
        self.inst({"argv": ["true"]})
        p = self.start()
        id, _ = self.letter()
        self.answer(id, {"error": {"code": "DeadlineMissed", "msg": "輪到之前時限已過，沒跑"}})
        out, err = p.communicate(timeout=10)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(err, "aos-gate: DeadlineMissed 輪到之前時限已過，沒跑\n")

    def test_reply_bad(self):
        for bad in ("{", {"code": "0"}, {"error": "x"}, {}):
            self.inst({"argv": ["true"]})
            p = self.start()
            id, _ = self.letter()
            self.answer(id, bad)
            out, err = p.communicate(timeout=10)
            self.own_error(subprocess.CompletedProcess([], p.returncode, out, err), "ReplyBad")
            self.assertFalse((self.mb / "done" / id).exists())


class D_Wait(Case):
    def test_withdraw_in_new(self):
        self.inst({"argv": ["true"]})
        p = self.start()
        self.letter()
        p.send_signal(signal.SIGTERM)
        p.communicate(timeout=10)
        self.assertEqual(p.returncode, 143)
        self.assertEqual(os.listdir(self.mb / "new"), [])
        self.assertEqual(os.listdir(self.mb / "tmp"), [])

    def test_leave_running_in_cur(self):
        self.inst({"argv": ["true"]})
        p = self.start()
        id, _ = self.letter()
        (self.mb / "cur").mkdir()
        os.rename(self.mb / "new" / id, self.mb / "cur" / id)   # kernel 認領了、正在跑
        p.send_signal(signal.SIGINT)
        p.communicate(timeout=10)
        self.assertEqual(p.returncode, 130)
        self.assertTrue((self.mb / "cur" / id).exists())         # 讓它跑完，kernel 之後清

    def test_letter_missing(self):
        self.inst({"argv": ["true"]})
        p = self.start()
        id, _ = self.letter()
        import shutil
        shutil.rmtree(self.mb / "new" / id)
        out, err = p.communicate(timeout=10)
        self.own_error(subprocess.CompletedProcess([], p.returncode, out, err), "LetterMissing")

    def test_no_kernel_keeps_waiting(self):
        self.inst({"argv": ["true"]})
        p = self.start()
        id, _ = self.letter()
        time.sleep(0.5)
        self.assertIsNone(p.poll())   # 沒有 kernel：信堆著、一直等（等多久由包它那格的 timeout_ms 守）
        self.answer(id, {"code": 0, "signal": None})
        p.communicate(timeout=10)
        self.assertEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]], verbosity=1)
