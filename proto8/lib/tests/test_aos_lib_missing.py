"""lib/aos 的工具抄到找不到 lib 的地方時，一律印一行 ModuleMissing、退 1（cl-9 對齊成標準樣板，不再是 traceback）。"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
AOS = Path(__file__).resolve().parents[1] / 'aos'
# 給腦用的兩邊印；不是給腦用的（tool_io.start(..., echo=False)）只印 stderr
STDERR_ONLY = {'defs', 'kernel', 'llm_forward', 'measure'}
NAME = {'metainfo_check': 'metainfo-check'}


class LibMissing(unittest.TestCase):
    def test_each_tool_says_module_missing(self):
        tools = sorted(p.parent.name for p in AOS.glob('*/_entry'))
        self.assertGreater(len(tools), 10)
        env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH' and not k.startswith('AOS_')}
        with tempfile.TemporaryDirectory() as tmp:
            for tool in tools:
                with self.subTest(tool=tool):
                    dest = Path(tmp) / tool
                    shutil.copytree(AOS / tool, dest, ignore=shutil.ignore_patterns('tests', '__pycache__'))
                    # -s：不讀 user site，install.sh 寫的 aos-proto8.pth 不算數
                    run = subprocess.run([sys.executable, '-s', '-B', str(dest / '_entry')], cwd=tmp, env=env,
                                         stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
                    self.assertEqual(run.returncode, 1)
                    lines = run.stderr.splitlines()
                    self.assertEqual(len(lines), 1, run.stderr)
                    self.assertRegex(lines[0], r'^%s: error: ModuleMissing \w+\.py not in the tool folder' % NAME.get(tool, tool))
                    self.assertEqual(run.stdout, '' if tool in STDERR_ONLY else run.stderr)


if __name__ == '__main__':
    unittest.main()
