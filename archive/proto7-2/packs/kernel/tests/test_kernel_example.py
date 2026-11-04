"""〔kernel〕監督 brain 範例整圈（examples/supervise-brain/run.py，練習用的 AI、真心跳）：卡住第 6 回合寄一封 NEEDS-USER、
第 12 回合 kill 綁當時 run 回條 ok、brain 重起從 task.json 接續不重問 AI、監督者被 SIGKILL 後 brain 照辦（I01）、
正常信零動作。房子開在測試暫存根，收尾照 CoreCase 收程序再刪。"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
TOP = os.path.dirname(os.path.dirname(PACK))
sys.path.insert(0, os.path.join(TOP, "tests"))
sys.path.insert(0, os.path.join(TOP, "modules", "mail"))

from base import CoreCase  # noqa: E402
from aos7_mail import letter  # noqa: E402

RUN = os.path.join(PACK, "examples", "supervise-brain", "run.py")


class SuperviseBrainExample(CoreCase):
    def test_example_round_trip(self):
        p = subprocess.run([sys.executable, "-B", RUN, "--house", self.root, "--keep"], capture_output=True,
                           text=True, timeout=300, cwd=TOP)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("全部做到", p.stdout)
        node = os.path.join(self.root, "bob")
        with open(os.path.join(node, ".aos", "tasks", "kernel", "state.json")) as f:
            state = json.load(f)
        kills = [d for d in state["done"] if d["op"] == "kill"]
        notes = [d for d in state["done"] if d["op"] == "notify"]
        self.assertEqual([d["result"] for d in kills], ["ok"])
        self.assertEqual([d["result"] for d in notes], ["sent"])
        # 跳號 tock 只處理最新，忙的機器上老化可能一次多 1：只要求到門檻才動作、先寄信後 kill。
        self.assertGreaterEqual(notes[0]['basis']['age'], 6)
        self.assertGreaterEqual(kills[0]['basis']['age'], 12)
        self.assertEqual(state["pending"], [])
        box = os.path.join(self.root, "you", "inbox")
        mails = [letter(os.path.join(d, f)) for d, _, fs in os.walk(box) for f in fs if f.endswith(".md")]
        kernel = [m for m in mails if m["from"] == "kernel"]
        self.assertEqual([m["status"] for m in kernel], ["NEEDS-USER"])
        self.assertIn("做 5 回合的整理", kernel[0]["title"])
        self.assertEqual(sorted(m["status"] for m in mails if m["from"] == "bob"), ["BLOCKED", "DONE"])

    def test_house_nonempty_preserved(self):
        from pathlib import Path
        marker = Path(self.root, '不能刪.txt')
        marker.write_text('保留', encoding='utf-8')
        p = subprocess.run([sys.executable, '-B', RUN, '--house', self.root], capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(len(p.stderr.splitlines()), 1)
        self.assertTrue(p.stderr.startswith('run.py: '))
        self.assertEqual(marker.read_text(), '保留')

    def test_house_cleanup_ownership_on_failure(self):
        import importlib.util
        from pathlib import Path
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('kernel_demo', RUN)
        demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
        for existing in (True, False):
            house = Path(self.root, 'empty' if existing else 'new')
            if existing:
                house.mkdir()
            def fail(*args):
                (house / 'partial').write_text('本次建立')
                return subprocess.CompletedProcess(args, 1, '', '故意失敗')
            with patch.object(demo, 'sh', side_effect=fail), patch.object(sys, 'argv', [RUN, '--house', str(house)]):
                self.assertEqual(demo.main(), 1)
            self.assertEqual(house.exists(), existing)
            if existing:
                self.assertEqual(list(house.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
