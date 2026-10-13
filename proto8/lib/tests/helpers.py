"""proto8/lib 測試共用的部分：路徑、暫存資料夾的基底類別 `Tmp`、`alive()`。不是測試檔（discover 只收 test*.py）。

每個測試在 mktemp 建的暫存資料夾裡跑，跑完刪掉。
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INST = os.path.join(LIB, "aos_inst.py")
LOOP = os.path.join(LIB, "aos_loop.py")
DAEMON = os.path.join(LIB, "aos_daemon.py")
sys.path.insert(0, LIB)


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos-test-")
        self.addCleanup(shutil.rmtree, self.tmp)

    def p(self, *parts):
        return os.path.join(self.tmp, *parts)

    def write(self, name, doc):
        path = self.p(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(doc if isinstance(doc, str) else json.dumps(doc))
        return path

    def read(self, name):
        with open(self.p(name)) as f:
            return f.read()

    def inst(self, name, sh, **keys):
        """寫 NAME/inst.json：在暫存資料夾裡用 sh 跑 SH。回資料夾的絕對路徑。"""
        self.write(name + "/inst.json", dict({"argv": ["sh", "-c", sh], "cwd": self.tmp}, **keys))
        return self.p(name)

    def until(self, cond, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            v = cond()
            if v:
                return v
            time.sleep(0.02)
        self.fail("等不到")


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
