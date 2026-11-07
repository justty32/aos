"""Verify memory writes, leaf promotion and concurrent removal through the real tool."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import unittest


ENTRY = Path(__file__).resolve().parents[1] / "_entry"
LOCK = shutil.which("aos-lock")
ROUNDS = 60

# Widen only the removal race in child interpreters; production has no test hook.
RACE_HOOK = '''# Delay removal at rename so a concurrent writer reaches the node lock.
import os
import time
_rename = os.rename
def rename(source, destination, *args, **kwargs):
    if os.path.basename(destination).startswith(".rm."):
        marker = os.environ.get("MEMORY_TEST_MARKER")
        if marker:
            open(marker, "w").close()
            time.sleep(0.12)
    return _rename(source, destination, *args, **kwargs)
os.rename = rename
'''
WAIT_HOOK = '''# Signal when the writer starts acquiring the external node lock.
import os
import subprocess
_popen = subprocess.Popen
def popen(args, *values, **kwargs):
    child = _popen(args, *values, **kwargs)
    if args[:2] == ["aos-lock", "acquire"]:
        open(os.environ["MEMORY_TEST_MARKER"], "w").close()
    return child
subprocess.Popen = popen
'''


@unittest.skipUnless(LOCK, "aos-lock must be on PATH")
class WritingTest(unittest.TestCase):
    def setUp(self):
        self.base = Path(subprocess.check_output(["mktemp", "-d"], text=True).strip())
        self.addCleanup(shutil.rmtree, self.base)
        self.root = self.base / "memory"
        self.root.mkdir()
        (self.root / "README.md").write_text("# Memory\n")
        self.env = dict(os.environ, AOS_MEMORY=str(self.root),
                        AOS_CD=str(ENTRY.parent), PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("AOS_TICK", None)

    def start_tool(self, op, path, env=None, **args):
        child = subprocess.Popen([str(ENTRY)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, env=env or self.env)
        child.stdin.write(json.dumps(dict(op=op, path=path, **args)))
        child.stdin.close()
        child.stdin = None
        return child

    def finish(self, child):
        out, err = child.communicate(timeout=15)
        return subprocess.CompletedProcess(child.args, child.returncode, out, err)

    def run_tool(self, op, path, **args):
        return self.finish(self.start_tool(op, path, **args))

    def lock(self, op, folder):
        return subprocess.run([LOCK, op, str(folder) + "/"], text=True,
                              capture_output=True, env=self.env, timeout=5)

    def assert_clean(self):
        leftovers = [str(p.relative_to(self.root)) for p in self.root.rglob("*")
                     if p.name == ".lock" or p.name.startswith(".rm.")]
        self.assertEqual(leftovers, [])
        self.assertEqual(self.lock("show", self.root).returncode, 10)

    def test_json_leaf_rejects_children_without_changing_data(self):
        raw = b'{"x": {"answer": 42}}\n'
        (self.root / "j.json").write_bytes(raw)
        result = self.run_tool("add", "j/x", text="# Child\n")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("PathBad node j is a JSON leaf; it cannot have child nodes", result.stderr)
        self.assertEqual(result.stdout, result.stderr)
        self.assertEqual((self.root / "j.json").read_bytes(), raw)
        self.assertFalse((self.root / "j").exists())
        self.assert_clean()

    def test_markdown_leaf_promotes_with_original_text(self):
        raw = b"# Parent\nOriginal summary\n"
        (self.root / "m.md").write_bytes(raw)
        result = self.run_tool("add", "m/x", text="# Child\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "m.md").exists())
        self.assertEqual((self.root / "m/README.md").read_bytes(), raw)
        self.assertEqual((self.root / "m/x.md").read_text(), "# Child\n")
        self.assert_clean()

    def race(self, recursive=False, op="add"):
        hooks = self.base / "hooks"
        hooks.mkdir()
        (hooks / "sitecustomize.py").write_text(RACE_HOOK)
        marker = self.base / "removing"
        race_env = dict(self.env, PYTHONPATH=str(hooks), MEMORY_TEST_MARKER=str(marker))
        for turn in range(ROUNDS):
            node = self.root / "d"
            node.mkdir()
            (node / "README.md").write_text("# Original\n")
            if marker.exists():
                marker.unlink()
            removing = self.start_tool("rm", "d", env=race_env, recursive=recursive)
            deadline = time.monotonic() + 5
            while not marker.exists() and removing.poll() is None and time.monotonic() < deadline:
                time.sleep(0.002)
            self.assertTrue(marker.exists(), self.finish(removing) if removing.poll() is not None else "rm did not reach rename")
            writing = self.start_tool(op, "d/x" if op == "add" else "d", text="# Written\n")
            removed, written = self.finish(removing), self.finish(writing)
            with self.subTest(turn=turn, recursive=recursive, op=op):
                self.assertEqual(removed.returncode, 0, removed.stderr)
                if op == "add":
                    self.assertFalse(removed.returncode == written.returncode == 0,
                                     "rm and add both succeeded but the new child was lost")
                elif written.returncode == 0 and node.exists():
                    self.assertEqual((node / "README.md").read_text(), "# Written\n")
                if written.returncode:
                    self.assertIn("error: NodeMissing ", written.stderr)
                self.assertFalse(node.exists(), "rm must not resurrect its target")
                self.assert_clean()

    def test_nonrecursive_remove_vs_add_existing_directory_60_rounds(self):
        self.race()

    def test_recursive_remove_vs_add_existing_directory_60_rounds(self):
        self.race(recursive=True)

    def test_remove_vs_edit_existing_directory_60_rounds(self):
        self.race(op="edit")

    def test_recursive_remove_cleans_locks_and_subtree(self):
        (self.root / "d/sub").mkdir(parents=True)
        (self.root / "d/sub/x.md").write_text("# Child\n")
        result = self.run_tool("rm", "d", recursive=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "d").exists())
        self.assert_clean()

    def test_recursive_remove_rejects_live_descendant_lock(self):
        descendant = self.root / "d/sub"
        descendant.mkdir(parents=True)
        self.assertEqual(self.lock("acquire", descendant).returncode, 0)
        try:
            result = self.run_tool("rm", "d", recursive=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("error: LockFailed ", result.stderr)
            self.assertTrue(descendant.exists())
        finally:
            self.assertEqual(self.lock("release", descendant).returncode, 0)
        self.assert_clean()

    def test_waiting_writer_reports_removed_node(self):
        node = self.root / "d"
        node.mkdir()
        self.assertEqual(self.lock("acquire", node).returncode, 0)
        hooks = self.base / "hooks"
        hooks.mkdir()
        (hooks / "sitecustomize.py").write_text(WAIT_HOOK)
        marker = self.base / "waiting"
        wait_env = dict(self.env, PYTHONPATH=str(hooks), MEMORY_TEST_MARKER=str(marker))
        child = self.start_tool("add", "d/x", env=wait_env, text="# Child\n")
        try:
            # The external lock keeps acquire waiting while the directory disappears.
            deadline = time.monotonic() + 5
            while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(0.002)
            self.assertTrue(marker.exists(), "writer did not start lock acquisition")
            renamed = self.base / "removed"
            node.rename(renamed)
            self.assertEqual(self.lock("release", renamed).returncode, 0)
            result = self.finish(child)
            self.assertEqual(result.returncode, 1)
            self.assertIn("NodeMissing node was removed while waiting for its lock", result.stderr)
            self.assertFalse(node.exists())
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()
        self.assert_clean()


if __name__ == "__main__":
    unittest.main()
