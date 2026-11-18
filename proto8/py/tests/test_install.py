"""test_install - proto8/install.py in a throwaway home with a fake make: fills bin/, lib/ (py/ copy + C++ libraries) and include/, a rerun gives the same result, missing make is one error line."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

INSTALL = Path(__file__).resolve().parents[2] / "install.py"

# fake make: writes one executable into BINDIR=, one library into LIBDIR= and one compile line for the dry run
FAKE_MAKE = """#!/bin/sh
for a in "$@"; do case "$a" in BINDIR=*) bindir="${a#BINDIR=}";; LIBDIR=*) libdir="${a#LIBDIR=}";; -n) dry=1;; esac; done
if [ -n "$dry" ]; then echo "g++ -O3 -c aos-x/src/a.cpp -o build/obj/aos-x/src/a.o"; exit 0; fi
[ -n "$FAKE_MAKE_FAIL" ] && { echo boom; exit 2; }
mkdir -p "$bindir" "$libdir" && printf '#!/bin/sh\\n' > "$bindir/aos-x" && chmod +x "$bindir/aos-x" && : > "$libdir/libaos-x.a"
"""
# a small py/: shared modules, one tool with its own tests, the package tests and docs (those two are not installed)
PY_FILES = ("tool_io.py", "tools/base/t/_entry", "tools/base/t/tests/test_t.py", "packs/p.json", "tests/test_m.py", "docs/d.md")
LIB_FILES = ["libaos-x.a", "packs/p.json", "tool_io.py", "tools/base/t/_entry"]


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-install-"))
        self.home = self.tmp / "proto8"
        (self.home / "cpp" / "aos-x" / "include" / "aos" / "x").mkdir(parents=True)
        (self.home / "cpp" / "aos-x" / "include" / "aos" / "x" / "x.hpp").write_text("#pragma once\n")
        (self.home / "cpp" / "Makefile").write_text("all:\n")
        for name in PY_FILES:
            (self.home / "py" / name).parent.mkdir(parents=True, exist_ok=True)
            (self.home / "py" / name).write_text("x\n")
        (self.home / "py" / "tools/base/t/_entry").chmod(0o755)
        shutil.copy(INSTALL, self.home / "install.py")
        self.tools = self.tmp / "tools"
        self.tools.mkdir()
        for name in ("g++", "gcc", "ar"):
            os.symlink(shutil.which("true") or "/bin/true", self.tools / name)
        (self.tools / "g++").unlink()
        (self.tools / "g++").write_text("#!/bin/sh\necho 13.3.0\n")
        (self.tools / "g++").chmod(0o755)
        (self.tools / "make").write_text(FAKE_MAKE)
        (self.tools / "make").chmod(0o755)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_install(self, *args, env=None):
        e = {"PATH": "%s:/usr/bin:/bin" % self.tools, "HOME": str(self.tmp)}
        e.update(env or {})
        return subprocess.run([sys.executable, str(self.home / "install.py"), *args], cwd=self.home,
                              env=e, capture_output=True, text=True, timeout=60)

    def test_install_and_rerun(self):
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(p.name for p in (self.home / "bin").iterdir()), ["aos-x"])
        self.assertTrue((self.home / "include" / "aos" / "x" / "x.hpp").is_file())
        self.assertIn("aos-x/src/a.cpp", (self.home / "cpp" / "compile_commands.json").read_text())
        self.assertIn("export AOS_HOME=%s" % self.home, r.stdout)
        self.assertEqual(self.lib_files(), LIB_FILES)
        self.assertTrue(os.access(self.home / "lib" / "tools/base/t/_entry", os.X_OK))
        (self.home / "bin" / "stale").write_text("old\n")          # something a later version no longer builds
        (self.home / "include" / "stale.hpp").write_text("old\n")
        (self.home / "lib" / "stale.py").write_text("old\n")       # a module py/ no longer has
        (self.home / "py" / "tool_io.py").write_text("new\n")      # a change in py/ shows up only after the next install
        self.assertEqual((self.home / "lib" / "tool_io.py").read_text(), "x\n")
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(p.name for p in (self.home / "bin").iterdir()), ["aos-x"])
        self.assertFalse((self.home / "include" / "stale.hpp").exists())
        self.assertEqual(self.lib_files(), LIB_FILES)
        self.assertEqual((self.home / "lib" / "tool_io.py").read_text(), "new\n")

    def lib_files(self):
        lib = self.home / "lib"
        return sorted(str(p.relative_to(lib)) for p in lib.rglob("*") if p.is_file())

    def test_py_missing(self):
        shutil.rmtree(self.home / "py")
        r = self.run_install()
        self.assertEqual(r.returncode, 1)
        self.assertIn("install.py: error: SourceMissing %s not found" % (self.home / "py" / "tool_io.py"), r.stderr)
        self.assertFalse((self.home / "lib").exists())

    def test_missing_make(self):
        (self.tools / "make").unlink()
        r = self.run_install(env={"PATH": str(self.tools)})
        self.assertEqual(r.returncode, 1)
        self.assertIn("install.py: error: DepMissing make not found on PATH", r.stderr)
        self.assertFalse((self.home / "bin").exists())

    def test_check_only(self):
        r = self.run_install("--check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("required", r.stdout)
        self.assertFalse((self.home / "bin").exists())

    def test_build_failed(self):
        r = self.run_install(env={"FAKE_MAKE_FAIL": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("install.py: error: BuildFailed make exited 2, see cpp/build/build.log", r.stderr)


if __name__ == "__main__":
    unittest.main()
