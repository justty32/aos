"""測試共用的小工具：開暫存資料夾、寫檔、真的把 aos-exec 開成一個進程。

每條測試自己一個 /tmp 下的暫存資料夾，跑完 addCleanup 收掉，不弄髒 repo。
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

EXEC = os.path.join(ROOT, "aos-exec")
PY = sys.executable
DEFAULT_INST = os.path.join(".aos", "inst.json")


class ExecCase(unittest.TestCase):
    """有一個暫存資料夾 self.d 的測試基底。"""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="aos-proto4-3-")
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)

    def write(self, rel, body, executable=False):
        """在 self.d 底下寫一個檔（父目錄自動建），回絕對路徑。"""
        p = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
        if executable:
            os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)
        return p

    def inst(self, obj, rel=DEFAULT_INST):
        """寫一份 inst.json（dict 就 dump，字串就原樣寫）。"""
        raw = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
        return self.write(rel, raw)

    def read(self, rel):
        with open(os.path.join(self.d, rel), encoding="utf-8") as f:
            return f.read()

    def exists(self, rel):
        return os.path.exists(os.path.join(self.d, rel))

    def aos(self, *args, stdin="", env=None, timeout=60):
        """開一個 aos-exec 進程。env 給 dict＝整個換掉（不然繼承）。"""
        return subprocess.run([PY, EXEC] + [str(a) for a in args],
                              input=stdin, capture_output=True, text=True,
                              timeout=timeout, env=env)
