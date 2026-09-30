"""測試共用：暫存資料夾、寫 JSON、解計畫。"""
import json
import os
import shutil
import tempfile
import unittest

from aos_inst import InstError, grant_only, load_plan

ME = os.getuid()


class TmpCase(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.realpath(tempfile.mkdtemp(prefix="aos_inst_"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def write(self, rel, obj, raw=False):
        p = self.path(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb" if raw and isinstance(obj, bytes) else "w") as f:
            f.write(obj if raw else json.dumps(obj))
        return p

    def plan(self, inst, env=None, authorize=None, create_dirs=False, **kw):
        """把 inst 寫成 <dir>/inst.json 再 load_plan(<dir>)。"""
        if inst is not None:
            self.write("inst.json", inst)
        return load_plan(self.dir, authorize or grant_only([ME]), env={} if env is None else env,
                         create_dirs=create_dirs, **kw)

    def code(self, inst, **kw):
        """預期被拒，回代號。"""
        with self.assertRaises(InstError) as cm:
            self.plan(inst, **kw)
        return cm.exception.code

    def assertCode(self, code, inst, **kw):
        self.assertEqual(self.code(inst, **kw), code)
