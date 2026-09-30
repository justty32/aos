"""除錯 CLI：`python3 -m aos_inst <目標>`。"""
import json
import os
import subprocess
import sys

from tests.util import TmpCase

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cli(*args):
    env = dict(os.environ, PYTHONPATH=HERE)
    return subprocess.run([sys.executable, "-m", "aos_inst"] + list(args), env=env,
                          capture_output=True, text=True)


class Cli(TmpCase):
    def test_prints_plan(self):
        self.write("inst.json", {"argv": ["echo", "hi"], "cwd": {"$opt": "mkdir", "$val": "w"},
                                 "id": "t"})
        r = cli(self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        plan = json.loads(r.stdout)
        self.assertEqual(plan["argv"], ["echo", "hi"])
        self.assertEqual(plan["extra"], {"id": "t"})
        self.assertFalse(os.path.exists(self.path("w")))    # 只印，不建目錄

    def test_error_is_125(self):
        self.write("inst.json", {"argv": []})
        r = cli(self.dir)
        self.assertEqual(r.returncode, 125)
        self.assertTrue(r.stderr.startswith("EmptyArgv: "), r.stderr)

    def test_usage_is_2(self):
        self.assertEqual(cli().returncode, 2)
        self.assertEqual(cli("a", "b").returncode, 2)
        r = cli(self.dir)                                   # 空資料夾
        self.assertEqual(r.returncode, 2)
        self.assertTrue(r.stderr.startswith("Usage: "), r.stderr)
