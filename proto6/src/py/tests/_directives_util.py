"""aos_directives 系列測試共用：暫存資料夾與小工具的 Base 基底。"""
import json
import os
import shutil
import tempfile
import unittest

from aos_directives import DirectiveError, Document, Context


class Base(unittest.TestCase):
    """暫存資料夾＋幾個小工具。"""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="aos-directives-")
        self.addCleanup(shutil.rmtree, self.d, True)

    def write(self, name, obj, raw=False):
        """把 obj 寫成 JSON 檔（raw=True 就照字面寫，用來寫壞 JSON），回絕對路徑。"""
        p = os.path.join(self.d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(obj if raw else json.dumps(obj, ensure_ascii=False))
        return p

    def ctx(self, root, env=None, path=None):
        """純記憶體文件的 Context，中心路徑＝暫存資料夾。"""
        return Context(Document(path, root), base_dir=self.d, env={} if env is None else env)

    def fails(self, code, fn, *a):
        with self.assertRaises(DirectiveError) as cm:
            fn(*a)
        self.assertEqual(cm.exception.code, code, str(cm.exception))
        return cm.exception
