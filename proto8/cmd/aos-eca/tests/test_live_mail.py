"""驗沒開畫面、cli.json 寫 "live_mail": true 的一整輪（wake-1114 主案 S）：aos-eca-turn 起 claude 之後 queue 又來的信，
這一輪就寫進 stream-json 的 stdin、併進同一個回答；history＝u1、u2、一行 assistant；信都收掉。CLI 用 fake_claude_stream。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_switch import TURN, Base  # noqa: E402


class LiveMail(Base):
    def setUp(self):
        super().setUp()
        self.sbin = self.t / "bin-stream"                          # 排在 PATH 最前：claude＝fake_claude_stream
        self.sbin.mkdir()
        (self.sbin / "claude").symlink_to(HERE / "fake_claude_stream")

    def env(self, **more):
        env = super().env(**more)
        if hasattr(self, "sbin"):                                   # Base.setUp 也叫 env（aos-post init），那時還沒有 sbin
            env["PATH"] = "%s:%s" % (self.sbin, env["PATH"])
        return env

    def received(self):
        return [c["line"] for c in self.calls()]

    def run_with_late_letter(self, cfg):
        self.write_cfg(cfg)
        self.say("SLOW:3 first")
        p = subprocess.Popen([str(TURN), "--on-empty", "idle", str(self.defn)], env=self.env(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        end = time.time() + 10
        while time.time() < end and self.received()[:1] != ["SLOW:3 first"]:   # CLI 收到第一封了
            time.sleep(0.1)
        self.say("second")
        out, err = p.communicate(timeout=30)
        return p.returncode, err

    def test_letter_arriving_mid_turn_joins_the_same_answer(self):
        code, err = self.run_with_late_letter({"live_mail": True})
        self.assertEqual(code, 0, err)
        self.assertEqual([(m["role"], m["content"]) for m in self.history()],
                         [("user", "SLOW:3 first"), ("user", "second"), ("assistant", "FAKE: SLOW:3 first | second")])
        self.assertEqual(self.queue(), [])
        self.assertEqual(self.received(), ["SLOW:3 first", "second"])
        argv = self.calls()[0]["argv"]
        self.assertIn("--input-format", argv)
        self.assertIn("--replay-user-messages", argv)

    def test_cap_zero_leaves_the_letter_for_the_next_turn(self):
        code, err = self.run_with_late_letter({"live_mail": True, "live_mail_cap": {"letters": 0}})
        self.assertEqual(code, 0, err)
        self.assertEqual([(m["role"], m["content"]) for m in self.history()],
                         [("user", "SLOW:3 first"), ("assistant", "FAKE: SLOW:3 first")])
        self.assertEqual(len(self.queue()), 1)
        self.assertEqual(self.received(), ["SLOW:3 first"])

    def test_switch_off_keeps_the_old_turn(self):
        """沒寫 live_mail（接線後所有既有 eca 的樣子）：中途來的信不進這一輪、留給下一輪，argv 沒有 MID_FLAGS，題目照舊整段給。"""
        code, err = self.run_with_late_letter({})
        self.assertEqual(code, 0, err)
        self.assertEqual([(m["role"], m["content"]) for m in self.history()],
                         [("user", "SLOW:3 first"), ("assistant", "FAKE: SLOW:3 first")])
        self.assertEqual(len(self.queue()), 1)
        argv = self.calls()[0]["argv"]
        self.assertNotIn("--input-format", argv)
        self.assertNotIn("--replay-user-messages", argv)
        self.assertEqual(self.received(), ["SLOW:3 first"])
        self.ok_turn()                                              # 下一輪照常答那封（假 CLI 不寫對話檔＝aos 開新對話帶紀錄，回答尾巴是題目）
        last = [m["content"] for m in self.history()][-2:]
        self.assertEqual(last[0], "second")
        self.assertTrue(last[1].startswith("FAKE: ") and last[1].endswith("second"), last[1])
        self.assertEqual(self.queue(), [])


if __name__ == "__main__":
    unittest.main()
