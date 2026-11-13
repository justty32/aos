"""test_copy_tree - 驗 copy_tree.py：在暫存夾自建小 git repo 與小樹，抄五夾、每夾有 .aos-source.json 記 commit；舊內容被換掉；--stamp-only、--dry-run、髒工作樹提醒與幾種錯。不起任何行程、不碰真的樹。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "copy_tree.py")
FOLDERS = ("lib", "templates", "knowledge", "py", "kernel")


def sh(cwd, *argv):
    subprocess.run(argv, cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class CopyTree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="copy-tree-")
        self.repo = os.path.join(self.tmp.name, "repo")
        self.tree = os.path.join(self.tmp.name, "tree")
        os.makedirs(self.tree)
        for n in FOLDERS:
            os.makedirs(os.path.join(self.repo, "proto8", n, "sub"))
            with open(os.path.join(self.repo, "proto8", n, "sub", "a.txt"), "w") as fh:
                fh.write("v1 " + n)
        sh(self.repo, "git", "init", "-q")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "one")
        self.commit = subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"], stdout=subprocess.PIPE,
                                     check=True).stdout.decode().strip()

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, *args):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": self.tmp.name}
        p = subprocess.run([sys.executable, TOOL, *args], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return p.returncode, p.stdout.decode(), p.stderr.decode()

    def read_stamp(self, n):
        with open(os.path.join(self.tree, n, ".aos-source.json")) as fh:
            return json.load(fh)

    def test_copies_all_five_with_stamp(self):
        os.makedirs(os.path.join(self.tree, "knowledge"))
        with open(os.path.join(self.tree, "knowledge", "old.txt"), "w") as fh:
            fh.write("old")
        rc, out, err = self.run_tool("--repo", self.repo, self.tree)
        self.assertEqual((rc, err), (0, ""), out)
        for n in FOLDERS:
            with open(os.path.join(self.tree, n, "sub", "a.txt")) as fh:
                self.assertEqual(fh.read(), "v1 " + n)
            s = self.read_stamp(n)
            self.assertEqual((s["commit"], s["ref"], s["how"]), (self.commit, "HEAD", "git archive"))
            self.assertEqual(s["from"], os.path.join(self.repo, "proto8", n))
            self.assertRegex(s["copied_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
        self.assertFalse(os.path.exists(os.path.join(self.tree, "knowledge", "old.txt")))   # 整夾換掉
        self.assertEqual(sorted(os.listdir(self.tree)), sorted(FOLDERS))                     # 暫存夾收掉了
        self.assertIn("done: 5 folder(s), commit " + self.commit, out)

    def test_dirty_worktree_warns_and_copies_commit(self):
        with open(os.path.join(self.repo, "proto8", "lib", "sub", "a.txt"), "w") as fh:
            fh.write("dirty")
        rc, out, err = self.run_tool("--repo", self.repo, self.tree, "lib")
        self.assertEqual(rc, 0, err)
        self.assertEqual(err.strip(), "copy_tree.py: warning: proto8/lib has uncommitted changes; they are not copied (copying %s)" % self.commit[:9])
        with open(os.path.join(self.tree, "lib", "sub", "a.txt")) as fh:
            self.assertEqual(fh.read(), "v1 lib")
        self.assertFalse(os.path.exists(os.path.join(self.tree, "py")))

    def test_stamp_only_and_dry_run(self):
        os.makedirs(os.path.join(self.tree, "knowledge"))
        rc, out, err = self.run_tool("--repo", self.repo, "--dry-run", self.tree, "knowledge")
        self.assertEqual(rc, 0, err)
        self.assertIn("would copy proto8/knowledge", out)
        self.assertEqual(os.listdir(os.path.join(self.tree, "knowledge")), [])
        rc, out, err = self.run_tool("--repo", self.repo, "--stamp-only", self.tree, "knowledge")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.read_stamp("knowledge")["how"], "stamp-only")
        self.assertFalse(os.path.exists(os.path.join(self.tree, "knowledge", "sub")))          # 沒抄

    def test_errors(self):
        cases = [
            (("--repo", self.repo), "ArgumentsBad"),
            (("--repo", self.repo, os.path.join(self.tmp.name, "nope")), "ArgumentsBad"),
            (("--repo", self.repo, os.path.join(self.repo, "proto8")), "ArgumentsBad"),        # 樹在 repo 裡
            (("--repo", self.repo, self.tree, "docs"), "ArgumentsBad"),
            (("--repo", self.repo, "--ref", "nosuch", self.tree), "RefBad"),
            (("--repo", self.repo, "--stamp-only", self.tree, "lib"), "FolderMissing"),
            (("--bogus", self.tree), "FlagUnknown"),
        ]
        for args, code in cases:
            rc, out, err = self.run_tool(*args)
            self.assertEqual(rc, 1, args)
            self.assertTrue(err.startswith("copy_tree.py: error: %s " % code), (args, err))
        self.assertEqual(os.listdir(self.tree), [])


if __name__ == "__main__":
    unittest.main()
