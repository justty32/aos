"""畫家 demo（demo/paint）：畫家 agent 經工具叫畫筆 agent；frame 巢狀、同 frame 續聊、frame 放 brain.json 換腦只換那一層。

用假腦（demo/paint/brain/fake.py）；frame 在暫存資料夾，定義資料夾 painter/、brush/ 不動。
"""
import importlib.util
import json
import os
import subprocess
import sys
import unittest

from helpers import ENV, LIB, Tmp

PAINT = os.path.realpath(os.path.join(LIB, "..", "demo", "paint"))
PAINTER = os.path.join(PAINT, "painter")
_spec = importlib.util.spec_from_file_location("paint_run", os.path.join(PAINT, "run.py"))
paint_run = importlib.util.module_from_spec(_spec)           # demo 的 run.py（tree_hash、bind_brain）
_spec.loader.exec_module(paint_run)


class PaintDemoTest(Tmp):
    def call(self, frame, q):
        self.write(frame + "/frame.json", {"parent": PAINTER})
        self.write(frame + "/args.json", {"question": q})
        rc = subprocess.run(["aos", "loop", os.path.join(PAINTER, "loop.json")], cwd=self.p(frame), env=ENV,
                            stdout=subprocess.DEVNULL, timeout=60).returncode
        self.assertEqual(rc, 0)
        return json.loads(self.read(frame + "/ret.json"))["reply"]

    def test_nested_frames_and_continue(self):
        before = paint_run.tree_hash(PAINT)
        r1 = self.call("A", "幫我畫一隻貓")
        self.assertIn("第 1 幅", r1)
        self.assertIn("橘、白、黑", r1)
        # 畫筆的 frame＝畫家的 work/1/（frame.json 指回 brush/）；調色盤在畫筆的 work/1/ 跑
        self.assertEqual(json.loads(self.read("A/work/1/frame.json")), {"parent": os.path.join(PAINT, "brush")})
        self.assertEqual(json.loads(self.read("A/work/1/work/1/args.json")), {"subject": "一隻貓"})
        self.assertEqual(json.loads(self.read("A/loop/state.json"))["state"], "done")       # stop_on_end
        # 同一個 frame 續聊：history 接下去，畫筆開新的 work/2/
        r2 = self.call("A", "再畫一隻狗")
        self.assertIn("第 2 幅", r2)
        self.assertIn("棕、白", r2)
        self.assertEqual(len(json.loads(self.read("A/history.json"))), 8)
        self.assertEqual(len(json.loads(self.read("A/work/2/history.json"))), 4)
        self.assertEqual(paint_run.tree_hash(PAINT), before)

    def test_brain_binding_only_reaches_own_frame(self):
        # 只放 brain.json：畫家換腦，畫筆（frame 在 work/1/，frame.json 指 brush/）照用定義的腦
        alt = os.path.join(PAINT, "brain", "fake-alt.json")
        self.write("B/brain.json", self.read_abs(alt))
        r = self.call("B", "幫我畫一片海")
        self.assertTrue(r.startswith("〔換過的假腦〕"))
        self.assertIn("畫筆說：備好了：藍、白。", r)
        # bind_brain 再綁工具：畫筆也換
        os.makedirs(self.p("C"))
        paint_run.bind_brain(self.p("C"), alt)
        self.assertIn("畫筆說：〔換過的假腦〕備好了", self.call("C", "幫我畫一片海"))

    def test_run_script(self):
        p = subprocess.run([sys.executable, os.path.join(PAINT, "run.py")], env=ENV, capture_output=True,
                           text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr)
        for s in ("第 2 幅", "〔換過的假腦〕", "沒有（雜湊一樣）", "暫存資料夾刪掉了"):
            self.assertIn(s, p.stdout)

    def read_abs(self, path):
        with open(path) as f:
            return f.read()


if __name__ == "__main__":
    unittest.main()
