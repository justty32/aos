"""test_env_sh - 驗 proto8/env.sh 與起手範本裡那份薄 env.sh（11-18 S6）：AOS_HOME 由人設、env.sh 不設它，沒設就報一行錯、什麼都不改；有設時 bash 與 zsh 都 source 得過，AOS_* 只剩 AOS_HOME，CLAUDE 那三個清掉，$AOS_HOME/bin 排 PATH 第一（有 frontend/bin 才多它一段）。只 source、不起任何行程。"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[2]
ENV_SH = PROTO / "env.sh"
TREE_ENV_SH = PROTO / "templates" / "starts" / "start-api" / "env.sh"
BASE_PATH = "/usr/bin:/bin"

# 模擬 agent 的 shell：帶著活樹的 AOS_*（11-13 15:24 起樹事故就是 AOS_STACK 沒清）
INHERITED = {
    "AOS_STACK": "/nowhere/ws/.stack/procs/someone",
    "AOS_DAEMON": "/nowhere/daemon",
    "AOS_KERNEL": "/nowhere/kernel",
    "AOS_CLOCK": "/nowhere/clock",
    "AOS_WS": "/nowhere/ws",
    "AOS_CF": "x",
    "AOS_SOME_NEW_VAR_2": "y",
    "CLAUDECODE": "1",
    "CLAUDE_CODE_ENTRYPOINT": "cli",
    "CLAUDE_CODE_SSE_PORT": "1234",
}
SHELLS = {"bash": ["--noprofile", "--norc"], "zsh": ["-f"]}


def source_and_dump(shell, env_sh, cwd, home, aos_home):
    """在乾淨的環境（只有 PATH、HOME、INHERITED，aos_home 不是 None 時加 AOS_HOME）用 shell source env_sh 兩次，
    回 (結束碼, {名: 值}, stderr)：source 後 env 印出來的 AOS_*、CLAUDE*、PATH。source 失敗＝結束碼 3。"""
    env = {"PATH": BASE_PATH, "HOME": home}
    env.update(INHERITED)
    if aos_home is not None:
        env["AOS_HOME"] = aos_home
    script = 'source "$1"; a=$?; source "$1"; b=$?; env; [ $a = 0 ] && [ $b = 0 ] || exit 3'
    p = subprocess.run([shell] + SHELLS[shell] + ["-c", script, "x", env_sh], env=env, cwd=cwd,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    left = {}
    for line in p.stdout.decode("utf-8", "replace").splitlines():
        name, eq, value = line.partition("=")
        if eq and (name.startswith("AOS_") or name.startswith("CLAUDE") or name == "PATH"):
            left[name] = value
    return p.returncode, left, p.stderr.decode("utf-8", "replace")


class EnvShTest(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="aos-env-sh-"))
        self.home = os.path.join(self.tmp, "proto8")
        for d in ("cmd/aos-a/bin", "frontend/bin", "bin", "cpp/aos-exec/src"):   # cmd/aos-a/bin: a leftover that must not go on PATH
            os.makedirs(os.path.join(self.home, d))
        shutil.copy(ENV_SH, os.path.join(self.home, "env.sh"))
        open(os.path.join(self.home, "install.py"), "w").close()            # what makes a folder an aos home
        self.tree = os.path.join(self.tmp, "tree")
        os.makedirs(self.tree)
        shutil.copy(TREE_ENV_SH, os.path.join(self.tree, "env.sh"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def need(self, shell):
        if shutil.which(shell, path=BASE_PATH) is None:
            self.skipTest("%s not installed" % shell)

    def build(self):
        exe = os.path.join(self.home, "bin/aos-exec")
        with open(exe, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(exe, 0o755)

    def assert_ready(self, code, left, err, home, frontend=True, built=True):
        self.assertEqual(code, 0, err)
        path = left.pop("PATH").split(":")
        self.assertEqual(left, {"AOS_HOME": home})
        want = [os.path.join(home, "bin")] + ([os.path.join(home, "frontend/bin")] if frontend else [])
        self.assertEqual(path[:len(want)], want)                 # 這個家的 bin/ 第一，source 兩次也不重複
        self.assertEqual(path[len(want):], BASE_PATH.split(":"))
        if built:
            self.assertEqual(err, "")
        else:
            self.assertIn("not installed yet; run: python3 %s/install.py" % home, err)

    def assert_refused(self, code, left, err, want):
        self.assertEqual(code, 3)                               # source 回非 0，殼沒有被關掉
        self.assertIn("env.sh: error: EnvBad " + want, err)
        self.assertEqual(err.count("\n"), 2, err)               # source 兩次，各一行
        self.assertEqual(left["PATH"], BASE_PATH)               # 什麼都沒改
        self.assertEqual(left.get("AOS_STACK"), INHERITED["AOS_STACK"])
        self.assertEqual(left.get("CLAUDECODE"), "1")

    def test_home_env_sh(self):
        self.build()
        for shell in SHELLS:
            self.need(shell)
            for how, cwd in ((os.path.join(self.home, "env.sh"), self.tmp), ("./env.sh", self.home)):
                with self.subTest(shell=shell, source=how):
                    self.assert_ready(*source_and_dump(shell, how, cwd, self.tmp, self.home), home=self.home)

    def test_tree_env_sh(self):
        self.build()
        for shell in SHELLS:
            self.need(shell)
            with self.subTest(shell=shell):
                self.assert_ready(*source_and_dump(shell, "./env.sh", self.tree, self.tmp, self.home), home=self.home)

    def test_aos_home_not_set(self):
        for shell in SHELLS:
            self.need(shell)
            for how, cwd in ((os.path.join(self.home, "env.sh"), self.tmp), ("./env.sh", self.tree)):
                with self.subTest(shell=shell, source=how):
                    self.assert_refused(*source_and_dump(shell, how, cwd, self.tmp, None), want="AOS_HOME is not set")
                with self.subTest(shell=shell, source=how, empty=True):
                    self.assert_refused(*source_and_dump(shell, how, cwd, self.tmp, ""), want="AOS_HOME is not set")

    def test_aos_home_wrong(self):
        self.need("bash")
        nowhere = os.path.join(self.tmp, "no-such-home")
        self.assert_refused(*source_and_dump("bash", os.path.join(self.home, "env.sh"), self.tmp, self.tmp, nowhere),
                            want="AOS_HOME=%s is not an aos home" % nowhere)
        for how, cwd in ((os.path.join(self.home, "env.sh"), self.tmp), ("./env.sh", self.tree)):
            with self.subTest(source=how):        # AOS_HOME pointing at a tree: the tree's env.sh must not source itself forever
                self.assert_refused(*source_and_dump("bash", how, cwd, self.tmp, self.tree), want="AOS_HOME=%s is not an aos home" % self.tree)

    def test_aos_home_decides_not_the_file(self):
        """家裡那份不看自己在哪：從 A 家 source，AOS_HOME 指 B 家，PATH 放的是 B 的 bin/，另印一行提醒（agent 的殼帶著活樹的 AOS_HOME 時最容易中）。"""
        other = os.path.join(self.tmp, "other")
        os.makedirs(os.path.join(other, "bin"))
        open(os.path.join(other, "install.py"), "w").close()
        for shell in SHELLS:
            self.need(shell)
            with self.subTest(shell=shell):
                code, left, err = source_and_dump(shell, os.path.join(self.home, "env.sh"), self.tmp, self.tmp, other)
                self.assertIn("env.sh: warning: AOS_HOME is %s, not %s where this env.sh is" % (other, self.home), err)
                self.assert_ready(code, left, err, home=other, frontend=False, built=False)

    def test_one_segment_without_frontend(self):
        self.need("bash")
        self.build()
        shutil.rmtree(os.path.join(self.home, "frontend"))
        self.assert_ready(*source_and_dump("bash", "./env.sh", self.tree, self.tmp, self.home), home=self.home, frontend=False)

    def test_not_built_warns(self):
        self.need("bash")
        self.assert_ready(*source_and_dump("bash", "./env.sh", self.tree, self.tmp, self.home), home=self.home, built=False)

    def test_run_instead_of_sourced(self):
        """bash env.sh（沒 source）沒設 AOS_HOME：照樣一行錯、退 1，不是一串殼的錯。"""
        self.need("bash")
        for f in (os.path.join(self.home, "env.sh"), os.path.join(self.tree, "env.sh")):
            with self.subTest(file=f):
                p = subprocess.run(["bash", "--noprofile", "--norc", f], env={"PATH": BASE_PATH, "HOME": self.tmp},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                self.assertEqual(p.returncode, 1)
                self.assertEqual(p.stderr.decode().count("\n"), 1, p.stderr)


if __name__ == "__main__":
    unittest.main()
