"""Test the tool-python skeleton (written with fn): its compiled _tooldef.json/_metainfo.json match tool.py byte for byte, and a copy outside the repo runs with only AOS_HOME or with a copy of the aos package next to it."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
os.environ.setdefault("AOS_HOME", str(Path(__file__).resolve().parents[3]))   # 路徑規則一（11-17）：範本的格只經 AOS_HOME 找 lib，測試給它這份 proto8

sys.dont_write_bytecode = True
SKEL = Path(__file__).resolve().parents[2] / "tools" / "tool-python"
PROTO = SKEL.parents[2]


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

    def test_compiled_files_are_fresh(self):
        for flag, name in (("--tooldef", "_tooldef.json"), ("--metainfo", "_metainfo.json")):
            r = subprocess.run([sys.executable, str(SKEL / "tool.py"), flag], capture_output=True, text=True, timeout=30)
            self.assertEqual(json.loads(r.stdout), json.loads((SKEL / name).read_text()), "run tool.py --compile in the skeleton")

    def test_compile_gives_the_committed_bytes(self):
        dest = self.root / "add"
        shutil.copytree(SKEL, dest)
        for name in ("_tooldef.json", "_metainfo.json"):
            (dest / name).unlink()
        r = subprocess.run([sys.executable, str(dest / "tool.py"), "--compile"], capture_output=True, text=True, timeout=30)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout, "wrote %s/_tooldef.json\nwrote %s/_metainfo.json\n" % (dest, dest))
        for name in ("_tooldef.json", "_metainfo.json"):
            self.assertEqual((dest / name).read_bytes(), (SKEL / name).read_bytes(), "run tool.py --compile in the skeleton")

    def test_no_tests_or_cache_in_skeleton(self):
        self.assertEqual(sorted(p.name for p in SKEL.iterdir()), ["README.md", "_entry.json", "_metainfo.json", "_tooldef.json", "tool.py"])

    def test_copy_runs_with_aos_home(self):
        dest = self.root / "anywhere" / "add"
        shutil.copytree(SKEL, dest)
        r = self.exec(dest, '{"a": 2, "b": 3}', AOS_HOME=str(PROTO))
        self.assertEqual((r.returncode, r.stdout), (0, "5\n"), r.stderr)
        r = self.exec(dest, '{"a": 2}')
        self.assertEqual(r.returncode, 1)
        self.assertIn("add: error: HomeMissing AOS_HOME is not set", r.stdout)

    def test_copy_runs_with_modules_next_to_it(self):
        dest = self.root / "add2"
        shutil.copytree(SKEL, dest)
        shutil.copytree(PROTO / "py" / "aos", dest / "aos")
        r = self.exec(dest, '{"a": 2, "b": 0.5}')
        self.assertEqual((r.returncode, r.stdout), (0, "2.5\n"), r.stderr)


if __name__ == "__main__":
    unittest.main()
