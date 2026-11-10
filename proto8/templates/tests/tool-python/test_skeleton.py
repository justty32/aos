"""Test the tool-python skeleton: its generated _tooldef.json/_metainfo.json match tool.py, and a copy outside the repo runs with only AOS_HOME or with tool_spec.py/tool_io.py next to it."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SKEL = Path(__file__).resolve().parents[2] / "tool-python"
PROTO = SKEL.parents[1]


class Skeleton(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tool-python-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") and k != "PYTHONPATH"}
        self.env.update(PYTHONNOUSERSITE="1", AOS_WS=str(self.root))   # 不靠 install.sh 的 .pth

    def exec(self, folder, stdin, **env):
        return subprocess.run(["aos-exec", str(folder)], input=stdin, text=True, capture_output=True,
                              env=dict(self.env, **env), timeout=30)

    def test_generated_files_are_fresh(self):
        for flag, name in (("--tooldef", "_tooldef.json"), ("--metainfo", "_metainfo.json")):
            r = subprocess.run([sys.executable, str(SKEL / "tool.py"), flag], capture_output=True, text=True, timeout=30)
            self.assertEqual(json.loads(r.stdout), json.loads((SKEL / name).read_text()), "run tool.py --write-defs in the skeleton")

    def test_no_tests_or_cache_in_skeleton(self):
        self.assertEqual(sorted(p.name for p in SKEL.iterdir()), ["README.md", "_entry.json", "_metainfo.json", "_tooldef.json", "tool.py"])

    def test_copy_runs_with_aos_home(self):
        dest = self.root / "anywhere" / "add"
        shutil.copytree(SKEL, dest)
        r = self.exec(dest, '{"a": 2, "b": 3}', AOS_HOME=str(PROTO))
        self.assertEqual((r.returncode, r.stdout), (0, "5\n"), r.stderr)
        r = self.exec(dest, '{"a": 2}')
        self.assertEqual(r.returncode, 1)
        self.assertIn("add: error: ModuleMissing tool_spec.py not found", r.stdout)

    def test_copy_runs_with_modules_next_to_it(self):
        dest = self.root / "add2"
        shutil.copytree(SKEL, dest)
        for m in ("tool_spec.py", "tool_io.py"):
            shutil.copy(PROTO / "lib" / m, dest / m)
        r = self.exec(dest, '{"a": 2, "b": 0.5}')
        self.assertEqual((r.returncode, r.stdout), (0, "2.5\n"), r.stderr)


if __name__ == "__main__":
    unittest.main()
