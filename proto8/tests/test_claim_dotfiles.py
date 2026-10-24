"""test_claim_dotfiles.py：demo 各 agent 認領題目時不撿 new/ 裡 . 開頭的檔（10-24 審後）。

N-05：寫檔的人先寫同資料夾 . 開頭的暫存檔再改名，所以 new/ 裡 . 開頭的是還沒寫完的題。agent-dan 範本（與從它、從 agent-bob
抄出來的各隻）原本 os.listdir 照單全收、排序後 . 開頭的排最前，會先把寫到一半的檔搬進 cur/。
這裡不列名單：掃 demo/ 底下所有寫著 ls("new") 的 brain.py 與 for d in ("cur", "new") 的 idle.py，新抄出來的一隻自動算進來。
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent / "demo"


def find(name, pattern):
    out = []
    for p in sorted(DEMO.rglob(name)):
        if "__pycache__" in p.parts:
            continue
        if re.search(pattern, p.read_text(encoding="utf-8")):
            out.append(p)
    return out


BRAINS = find("brain.py", r'ls\("new"\)')
IDLES = find("idle.py", r'for d in \("cur", "new"\)')


def env_of(ws, stack):
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e.update({"AOS_WS": str(ws), "AOS_STACK": str(stack)})
    return e


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = Path(self._t.name)
        self.addCleanup(self._t.cleanup)

    def fresh(self, name, files):
        ws, stack = self.t / name / "ws", self.t / name / "stack"
        (ws / "new").mkdir(parents=True)
        stack.mkdir(parents=True)
        for f, text in files.items():
            (ws / "new" / f).write_text(text)
        return ws, stack

    def test_found_all(self):
        # 找得到範本與幾隻代表（掃描本身壞掉時不會靜靜地什麼都不測）
        rel = {str(p.relative_to(DEMO)) for p in BRAINS}
        for want in ("agent-dan/brain.py", "agent-bob/brain.py", "agent-pip/brain.py", "self-improve/improver/brain.py"):
            self.assertIn(want, rel)
        self.assertIn("agent-ann/idle.py", {str(p.relative_to(DEMO)) for p in IDLES})

    def test_brain_skips_dotfile(self):
        # new/ 有寫到一半的 .a.tmp（排序在前）和一題 b.txt：認領 b.txt，.a.tmp 留在 new/
        for brain in BRAINS:
            name = str(brain.relative_to(DEMO)).replace("/", "_")
            with self.subTest(brain=name):
                ws, stack = self.fresh(name, {".a.tmp": "半", "b.txt": "1+1=?"})
                subprocess.run([sys.executable, brain.name], cwd=str(brain.parent), env=env_of(ws, stack),
                               capture_output=True, text=True, timeout=60)
                self.assertEqual(sorted(os.listdir(ws / "cur")), ["b.txt"])
                self.assertEqual(sorted(os.listdir(ws / "new")), [".a.tmp"])

    def test_brain_only_dotfile_is_empty(self):
        # new/ 只有寫到一半的檔＝沒題目：退非 0、什麼都不搬
        for brain in BRAINS:
            name = str(brain.relative_to(DEMO)).replace("/", "_")
            with self.subTest(brain=name):
                ws, stack = self.fresh(name, {".q.txt": "半"})
                r = subprocess.run([sys.executable, brain.name], cwd=str(brain.parent), env=env_of(ws, stack),
                                   capture_output=True, text=True, timeout=60)
                self.assertNotEqual(r.returncode, 0)
                self.assertEqual(sorted(os.listdir(ws / "new")), [".q.txt"])
                self.assertFalse((ws / "cur").exists() and os.listdir(ws / "cur"))

    def test_idle_only_dotfile_stops(self):
        for idle in IDLES:
            name = str(idle.relative_to(DEMO)).replace("/", "_")
            with self.subTest(idle=name):
                ws, stack = self.fresh(name, {".q.txt": "半"})
                r = subprocess.run([sys.executable, idle.name], cwd=str(idle.parent), env=env_of(ws, stack),
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, 10)
                (ws / "new" / "q.txt").write_text("1")
                r = subprocess.run([sys.executable, idle.name], cwd=str(idle.parent), env=env_of(ws, stack),
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
