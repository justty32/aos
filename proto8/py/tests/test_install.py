"""test_install - proto8/install.py in a throwaway home with a fake make: fills bin/ (C++ + the Python entries of py/entries.json), lib/ (py/ copy + C++ libraries) and include/, a rerun gives the same result and drops old entries, a rerun copies over without emptying first and then removes leftovers (never what make made), a failed build leaves the old install, a bad entries.json is one error line, the aos package imports only from lib/, the last lines follow AOS_HOME."""
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
if [ -n "$dry" ]; then
  echo "g++ -O3 -c aos-x/src/a.cpp -o build/obj/aos-x/src/a.o"
  [ -n "$FAKE_MAKE_EMPTY" ] && exit 0
  echo "mkdir -p $libdir; rm -f $libdir/libaos-x.a"; echo "ar rcs $libdir/libaos-x.a build/obj/aos-x/src/a.o"
  echo "g++ -O3 -static-pie -pthread -o $bindir/aos-x build/obj/aos-x/src/main.o $libdir/libaos-x.a"
  exit 0
fi
[ -n "$FAKE_MAKE_FAIL" ] && { echo boom; exit 2; }
[ -n "$FAKE_MAKE_UPTODATE" ] && [ -f "$bindir/aos-x" ] && exit 0
mkdir -p "$bindir" "$libdir" && printf '#!/bin/sh\\n' > "$bindir/aos-x" && chmod +x "$bindir/aos-x" && : > "$libdir/libaos-x.a"
"""
# a small py/: the aos package, one tool with its own tests, the package tests and docs (those two are not installed)
PY_FILES = ("aos/__init__.py", "aos/tool_io.py", "aos/agentlib/__init__.py", "aos/agentlib/hooks.py", "tools/base/t/_entry",
            "tools/base/t/tests/test_t.py", "packs/p.json", "tests/test_m.py", "docs/d.md", "aos/apps/__init__.py")
# S5: one command whose logic is in aos/apps/y/ (main.py, and a module of its own next to it); its entry comes from entries.json
APP_MAIN = """import os, sys
from aos.apps.y import helper
if __name__ == "__main__":
    print(helper.X, sys.argv[1:], os.path.basename(sys.argv[0]), __name__)
    sys.exit(3)
"""
ENTRIES = '{"description": "d", "commands": {"aos-y": "aos.apps.y.main"}}\n'
LIB_FILES = ["aos/__init__.py", "aos/agentlib/__init__.py", "aos/agentlib/hooks.py", "aos/apps/__init__.py", "aos/apps/y/helper.py",
             "aos/apps/y/main.py", "aos/tool_io.py", "entries.json", "libaos-x.a", "packs/p.json", "tools/base/t/_entry"]


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-install-"))
        self.home = self.tmp / "proto8"
        (self.home / "cpp" / "aos-x" / "include" / "aos" / "x").mkdir(parents=True)
        (self.home / "cpp" / "aos-x" / "include" / "aos" / "x" / "x.hpp").write_text("#pragma once\n")
        (self.home / "cpp" / "Makefile").write_text("all:\n")
        for name in PY_FILES:
            (self.home / "py" / name).parent.mkdir(parents=True, exist_ok=True)
            (self.home / "py" / name).write_text("x = 1\n")
        (self.home / "py" / "tools/base/t/_entry").chmod(0o755)
        (self.home / "py" / "aos/apps/y").mkdir(parents=True)
        (self.home / "py" / "aos/apps/y/main.py").write_text(APP_MAIN)
        (self.home / "py" / "aos/apps/y/helper.py").write_text("X = 'from-lib'\n")
        (self.home / "py" / "entries.json").write_text(ENTRIES)
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
        self.assertEqual(sorted(p.name for p in (self.home / "bin").iterdir()), ["aos-x", "aos-y"])
        self.assertIn("(1 C++, 1 Python entries)", r.stdout)
        self.assertTrue((self.home / "include" / "aos" / "x" / "x.hpp").is_file())
        self.assertIn("aos-x/src/a.cpp", (self.home / "cpp" / "compile_commands.json").read_text())
        self.assertIn("export AOS_HOME=%s" % self.home, r.stdout)
        self.assertEqual(self.lib_files(), LIB_FILES)
        self.assertTrue(os.access(self.home / "lib" / "tools/base/t/_entry", os.X_OK))
        (self.home / "bin" / "stale").write_text("old\n")          # something a later version no longer builds
        (self.home / "include" / "stale.hpp").write_text("old\n")
        (self.home / "lib" / "aos" / "stale.py").write_text("old\n")   # a module py/ no longer has
        (self.home / "py" / "aos" / "tool_io.py").write_text("x = 2\n")  # a change in py/ shows up only after the next install
        self.assertEqual((self.home / "lib" / "aos" / "tool_io.py").read_text(), "x = 1\n")
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(p.name for p in (self.home / "bin").iterdir()), ["aos-x", "aos-y"])
        self.assertFalse((self.home / "include" / "stale.hpp").exists())
        self.assertEqual(self.lib_files(), LIB_FILES)
        self.assertEqual((self.home / "lib" / "aos" / "tool_io.py").read_text(), "x = 2\n")

    def test_aos_package_only_from_lib(self):
        """S4: the shared modules are one package aos (py/aos, installed as lib/aos); it imports with lib/ on the path, and
        outside the home nothing else puts an aos on the path (no .pth, no site-packages)."""
        self.assertEqual(self.run_install().returncode, 0)
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.tmp), "PYTHONNOUSERSITE": "1"}
        code = "import aos.tool_io, aos.agentlib.hooks; print(aos.tool_io.__file__)"
        r = subprocess.run([sys.executable, "-c", code], cwd=self.home / "lib", env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual((r.returncode, r.stdout), (0, "%s\n" % (self.home / "lib" / "aos" / "tool_io.py")), r.stderr)
        r = subprocess.run([sys.executable, "-c", "import aos"], cwd=self.tmp, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ModuleNotFoundError: No module named 'aos'", r.stderr)

    def test_python_entry(self):
        """S5: bin/aos-y is a small generated Python file: it puts lib/ (not py/) on sys.path and runs aos.apps.y.main as __main__."""
        self.assertEqual(self.run_install().returncode, 0)
        entry = self.home / "bin" / "aos-y"
        self.assertTrue(os.access(entry, os.X_OK))
        self.assertIn("generated by install.py from py/entries.json", entry.read_text())
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.tmp), "PYTHONNOUSERSITE": "1"}
        (self.home / "py" / "aos/apps/y/helper.py").write_text("X = 'from-py'\n")     # not installed yet: the entry must not see it
        link = self.tmp / "elsewhere"
        link.mkdir()
        (link / "aos-y").symlink_to(entry)                                            # a link to the entry still finds its home
        for exe in (entry, link / "aos-y"):
            r = subprocess.run([sys.executable, str(exe), "a", "--b"], cwd=self.tmp, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual((r.returncode, r.stdout), (3, "from-lib ['a', '--b'] main.py __main__\n"), r.stderr)

    def test_next_steps_follow_aos_home(self):
        """S6: AOS_HOME is the user's to set; the last lines say to set it (unset), that it is fine (here), or warn (another home)."""
        cases = ((None, "next: export AOS_HOME=%s" % self.home, ""),
                 (str(self.home) + "/", "AOS_HOME already points at this home", ""),
                 (str(self.tmp), "", "install.py: warning: AOS_HOME is %s, not this home %s" % (self.tmp, self.home)))
        for value, out, err in cases:
            with self.subTest(aos_home=value):
                r = self.run_install(env={} if value is None else {"AOS_HOME": value})
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(out, r.stdout)
                self.assertIn("then: cp -r $AOS_HOME/templates/starts/start-api ~/aos-home", r.stdout)
                if err:
                    self.assertIn(err, r.stderr)
                    self.assertNotIn("export AOS_HOME", r.stdout)
                else:
                    self.assertEqual(r.stderr, "")

    def test_entries_rerun_drops_old(self):
        self.assertEqual(self.run_install().returncode, 0)
        (self.home / "py" / "entries.json").write_text('{"commands": {"aos-z": "aos.apps.y.main"}}')
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(p.name for p in (self.home / "bin").iterdir()), ["aos-x", "aos-z"])

    def test_entries_bad(self):
        for text, want in (("{", "EntriesBad cannot read py/entries.json"),
                           ('{"commands": {}}', 'EntriesBad py/entries.json needs a non-empty object "commands"'),
                           ('{"commands": {"y": "aos.apps.y.main"}}', 'EntriesBad py/entries.json: bad line "y"'),
                           ('{"commands": {"aos-y": "os.path"}}', 'EntriesBad py/entries.json: bad line "aos-y"'),
                           ('{"commands": {"aos-y": "aos.apps.nope.main"}}', "but py/aos/apps/nope/main.py does not exist"),
                           ('{"commands": {"aos-x": "aos.apps.y.main"}}', "aos-x is also a C++ executable in bin/")):
            with self.subTest(entries=text):
                (self.home / "py" / "entries.json").write_text(text)
                r = self.run_install()
                self.assertEqual(r.returncode, 1)
                self.assertTrue(r.stderr.startswith("install.py: error: EntriesBad "), r.stderr)
                self.assertIn(want, r.stderr)
                self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)

    def test_symlink_kept(self):
        """S5: the aos-sandbox examples hold relative symlinks into lib/tools; lib/ keeps them as links (not copies, not broken)."""
        ex = self.home / "py" / "aos" / "apps" / "y" / "ex"
        ex.mkdir()
        (ex / "inner").symlink_to("../../../../tools/base/t")
        self.assertEqual(self.run_install().returncode, 0)
        got = self.home / "lib" / "aos" / "apps" / "y" / "ex" / "inner"
        self.assertTrue(got.is_symlink())
        self.assertEqual(os.readlink(got), "../../../../tools/base/t")
        self.assertTrue((got / "_entry").is_file())

    def lib_files(self, pyc=False):
        """lib/ 的檔（相對路徑）；pyc＝False 不列 __pycache__（第 0 刀起 install.py 編的 .pyc 另由 test_lib_is_compiled… 驗）。"""
        lib = self.home / "lib"
        return sorted(str(p.relative_to(lib)) for p in lib.rglob("*")
                      if p.is_file() and (pyc or "__pycache__" not in p.relative_to(lib).parts))

    def test_py_missing(self):
        shutil.rmtree(self.home / "py")
        r = self.run_install()
        self.assertEqual(r.returncode, 1)
        self.assertIn("install.py: error: SourceMissing %s not found" % (self.home / "py" / "aos" / "__init__.py"), r.stderr)
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

    # ---- 第零刀（線 aos-pylib-cut-1119）：照抄之後刪孤兒，不先整夾刪 ----
    def test_rerun_keeps_unchanged_files_and_removes_leftovers(self):
        """A rerun does not empty lib/ first: unchanged files keep their inode, a changed one is replaced by a rename,
        a module (and its folder) deleted from py/ is gone from lib/, and what make made stays even when make rewrote nothing."""
        self.assertEqual(self.run_install().returncode, 0)
        lib = self.home / "lib"
        (self.home / "py" / "aos" / "tool_io.py").write_text("x = 2\n")
        shutil.rmtree(self.home / "py" / "aos" / "agentlib")                         # a whole module folder deleted from py/
        (self.home / "lib" / "aos" / "__pycache__").mkdir(exist_ok=True)
        (self.home / "lib" / "aos" / "__pycache__" / "x.pyc").write_text("old\n")
        init_ino = (lib / "aos" / "__init__.py").stat().st_ino
        r = self.run_install(env={"FAKE_MAKE_UPTODATE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("removed 5 left over", r.stdout)                                # + the two .pyc of the deleted folder (第 0 刀)
        self.assertEqual((lib / "aos" / "__init__.py").stat().st_ino, init_ino)        # untouched
        self.assertEqual((lib / "aos" / "tool_io.py").read_text(), "x = 2\n")
        self.assertFalse((lib / "aos" / "agentlib").exists())                         # file and folder gone
        self.assertFalse((lib / "aos" / "__pycache__" / "x.pyc").exists())            # a .pyc without its .py is removed
        self.assertEqual(sorted(p.name for p in (self.home / "bin").iterdir()), ["aos-x", "aos-y"])   # make made nothing new
        self.assertTrue((lib / "libaos-x.a").exists())
        self.assertEqual([p for p in lib.rglob(".*install-tmp")], [])

    def test_lib_is_compiled_and_stale_bytecode_goes(self):
        """idle-polling 第 0 刀（使用者 11-24 第 5 題「a」）：install.py 把 lib/ 的 .py 編成 .pyc（放 lib/ 的 __pycache__）；
        py/ 改了重裝＝.pyc 跟著新的；py/ 刪了的模組，它的 .pyc 一起清；py/ 本身不會多出 __pycache__。"""
        import importlib.util
        self.assertEqual(self.run_install().returncode, 0)
        lib = self.home / "lib"
        src = lib / "aos" / "tool_io.py"
        pyc = Path(importlib.util.cache_from_source(str(src)))
        self.assertTrue(pyc.is_file())
        self.assertIn("compiled to .pyc", self.run_install(env={"FAKE_MAKE_UPTODATE": "1"}).stdout)
        (self.home / "py" / "aos" / "tool_io.py").write_text("x = 3\n")
        self.assertEqual(self.run_install(env={"FAKE_MAKE_UPTODATE": "1"}).returncode, 0)
        r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); import aos.tool_io as t; print(t.x, t.__cached__)"
                            % str(lib)], capture_output=True, text=True, env={"PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(r.stdout.split()[0], "3", r.stderr)                          # the new source, not a stale .pyc
        (self.home / "py" / "aos" / "tool_io.py").unlink()
        self.assertEqual(self.run_install(env={"FAKE_MAKE_UPTODATE": "1"}).returncode, 0)
        self.assertFalse(pyc.exists())
        self.assertFalse(any(p.name == "__pycache__" for p in (self.home / "py").rglob("*")))

    def test_a_module_that_does_not_compile_is_a_warning(self):
        (self.home / "py" / "aos" / "broken.py").write_text("def (\n")
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("install.py: warning: cannot compile aos/broken.py", r.stderr)
        self.assertTrue((self.home / "lib" / "aos" / "broken.py").is_file())

    def test_failed_rebuild_keeps_the_old_install(self):
        self.assertEqual(self.run_install().returncode, 0)
        before = self.lib_files(pyc=True)
        (self.home / "py" / "aos" / "tool_io.py").unlink()
        r = self.run_install(env={"FAKE_MAKE_FAIL": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.lib_files(pyc=True), before)                            # nothing removed, nothing half-copied
        self.assertEqual(sorted(p.name for p in (self.home / "bin").iterdir()), ["aos-x", "aos-y"])

    def test_dry_run_naming_nothing_removes_nothing(self):
        """If make's dry run names nothing it puts into bin/, install stops before touching anything (it would not know what is C++)."""
        self.assertEqual(self.run_install().returncode, 0)
        r = self.run_install(env={"FAKE_MAKE_EMPTY": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("install.py: error: BuildBad make -n -B names nothing it puts into bin/", r.stderr)
        self.assertEqual(sorted(p.name for p in (self.home / "bin").iterdir()), ["aos-x", "aos-y"])
        self.assertIn("libaos-x.a", self.lib_files())

    def test_dir_becomes_file_and_symlink_dirs(self):
        """py/ turns a folder into a file: lib/ follows; a symlinked folder in py/ stays one link in lib/ and is not walked into on rerun."""
        (self.home / "py" / "aos" / "z").mkdir()
        (self.home / "py" / "aos" / "z" / "a.py").write_text("x\n")
        (self.home / "py" / "aos" / "link").symlink_to("agentlib")
        self.assertEqual(self.run_install().returncode, 0)
        shutil.rmtree(self.home / "py" / "aos" / "z")
        (self.home / "py" / "aos" / "z").write_text("now a file\n")
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.home / "lib" / "aos" / "z").read_text(), "now a file\n")
        self.assertTrue((self.home / "lib" / "aos" / "link").is_symlink())
        self.assertTrue((self.home / "lib" / "aos" / "agentlib" / "hooks.py").is_file())


if __name__ == "__main__":
    unittest.main()
