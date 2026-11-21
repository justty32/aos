"""Test declared file validation in aos.declared_files and that it imports alone (without aos.agentlib, without touching sys.path)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
from aos.declared_files import declared_files


class DeclaredFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="declared-files-")
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.path = self.folder / "interfaces.json"

    def declare(self, value):
        self.path.write_text(json.dumps(value), encoding="utf-8")
        return declared_files(self.folder)

    def test_missing_or_undeclared_interface(self):
        self.assertEqual(declared_files(self.folder), {})
        self.assertEqual(self.declare({"another-interface": {"tools": "ignored.json"}}), {})

    def test_only_known_declarations_are_returned(self):
        files = {key: "cfg/%s.json" % key for key in ("tools", "llm", "system")}
        self.assertEqual(self.declare({"aos-agent": dict(files, other="ignored", hooks="cfg/hooks.json")}), files)
        self.assertEqual(self.declare({"aos-agent": files, "hooks": "hooks.json", "hookeds": "hookeds.json"}), files)   # top level: aos.hook_point's

    def test_bad_shapes(self):
        for value, message in (([], "%s must be a JSON object" % self.path),
                               ({"aos-agent": []}, "aos-agent in %s must be a JSON object" % self.path)):
            with self.subTest(value=value), self.assertRaises(ValueError) as cm:
                self.declare(value)
            self.assertEqual(str(cm.exception), message)

    def test_bad_relative_paths(self):
        (self.folder / "directory").mkdir()
        for key in ("tools", "llm", "system"):
            for value in (None, 1, "", "/absolute.json", "../outside.json", "cfg/../outside.json", "directory"):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError) as cm:
                    self.declare({"aos-agent": {key: value}})
                self.assertEqual(str(cm.exception),
                                 "%s in %s must name a file by a relative path inside the definition" % (key, self.path))

    def test_invalid_json_and_unreadable_interface(self):
        self.path.write_text("not JSON", encoding="utf-8")
        with self.assertRaises(ValueError) as cm:
            declared_files(self.folder)
        self.assertTrue(str(cm.exception).startswith("cannot read %s: " % self.path))
        other = self.folder / "other"
        (other / "interfaces.json").mkdir(parents=True)
        with self.assertRaises(ValueError) as cm:
            declared_files(other)
        self.assertTrue(str(cm.exception).startswith("cannot read %s: " % (other / "interfaces.json")))

    def run_import(self, code):
        env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        result = subprocess.run([sys.executable, "-I", "-S", "-c", code],
                                cwd=self.folder, env=env, capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_shared_module_imports_without_agentlib(self):
        # Copy only the package root and the shared module, so no aos.agentlib can satisfy an import.
        isolated = self.folder / "lib"
        (isolated / "aos").mkdir(parents=True)
        for name in ("__init__.py", "declared_files.py"):
            (isolated / "aos" / name).write_bytes((LIB / "aos" / name).read_bytes())
        self.run_import("import importlib.util, sys; sys.dont_write_bytecode = True; "
                        "sys.path.insert(0, %r); assert importlib.util.find_spec('aos.agentlib') is None; "
                        "from aos.declared_files import declared_files; "
                        "assert declared_files(%r) == {}; assert 'aos.agentlib' not in sys.modules"
                        % (str(isolated), str(self.folder)))

    def test_import_leaves_the_path_alone(self):
        self.run_import("import sys; sys.dont_write_bytecode = True; sys.path.insert(0, %r); "
                        "before = list(sys.path); from aos import declared_files; "
                        "assert sys.path == before; assert declared_files.declared_files(%r) == {}"
                        % (str(LIB), str(self.folder)))


if __name__ == "__main__":
    unittest.main()
