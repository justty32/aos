"""test_env_sh - 驗 proto8/env.sh：bash 與 zsh 都 source 得過，source 後 AOS_* 只剩 AOS_HOME（＝env.sh 所在的 proto8），CLAUDE 那三個清掉，這個家的 cmd/*/bin 與安裝產物 bin/ 排在 PATH 最前。只 source、不起任何行程。"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[3]
ENV_SH = PROTO / "env.sh"

# 模擬 agent 的 shell：帶著活樹的 AOS_*（11-13 15:24 起樹事故就是 AOS_STACK 沒清）
INHERITED = {
    "AOS_STACK": "/nowhere/ws/.stack/procs/someone",
    "AOS_DAEMON": "/nowhere/daemon",
    "AOS_KERNEL": "/nowhere/kernel",
    "AOS_CLOCK": "/nowhere/clock",
    "AOS_HOME": "/nowhere/wrong-home",
    "AOS_WS": "/nowhere/ws",
    "AOS_CF": "x",
    "AOS_SOME_NEW_VAR_2": "y",
    "CLAUDECODE": "1",
    "CLAUDE_CODE_ENTRYPOINT": "cli",
    "CLAUDE_CODE_SSE_PORT": "1234",
}


def source_and_dump(shell, argv, env_sh, cwd, home):
    """在乾淨的環境（只有 PATH、HOME 與 INHERITED）用 shell source env_sh 兩次，回 (結束碼, {名: 值}, stderr)：source 後 env 印出來的 AOS_*、CLAUDE*、PATH。"""
    env = {"PATH": "/usr/bin:/bin", "HOME": home}
    env.update(INHERITED)
    script = 'source "$1" || exit 3; source "$1" || exit 3; env'
    p = subprocess.run([shell] + argv + ["-c", script, "x", env_sh], env=env, cwd=cwd,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    left = {}
    for line in p.stdout.decode("utf-8", "replace").splitlines():
        name, eq, value = line.partition("=")
        if eq and (name.startswith("AOS_") or name.startswith("CLAUDE") or name == "PATH"):
            left[name] = value
    return p.returncode, left, p.stderr.decode("utf-8", "replace")


class EnvShTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos-env-sh-")
        self.home = os.path.join(os.path.realpath(self.tmp), "proto8")
        for d in ("cmd/aos-a/bin", "cmd/aos-a/tests", "bin", "cpp/aos-exec/src"):
            os.makedirs(os.path.join(self.home, d))
        shutil.copy(ENV_SH, os.path.join(self.home, "env.sh"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def check(self, shell, argv, built=True):
        if shutil.which(shell, path="/usr/bin:/bin") is None:
            self.skipTest("%s not installed" % shell)
        exe = os.path.join(self.home, "bin/aos-exec")
        if built:
            with open(exe, "w") as f:
                f.write("#!/bin/sh\n")
            os.chmod(exe, 0o755)
        for how, cwd in ((os.path.join(self.home, "env.sh"), self.tmp), ("./env.sh", self.home)):
            with self.subTest(shell=shell, source=how):
                code, left, err = source_and_dump(shell, argv, how, cwd, self.tmp)
                self.assertEqual(code, 0)
                path = left.pop("PATH").split(":")
                self.assertEqual(left, {"AOS_HOME": self.home})
                want = sorted([os.path.join(self.home, "cmd/aos-a/bin"), os.path.join(self.home, "bin")])
                self.assertEqual(sorted(path[:2]), want)           # 這個家的指令排最前，source 兩次也不重複
                self.assertEqual(path[2:], ["/usr/bin", "/bin"])
                if built:
                    self.assertEqual(err, "")
                else:
                    self.assertIn("not installed yet", err)

    def test_bash(self):
        self.check("bash", ["--noprofile", "--norc"])

    def test_zsh(self):
        self.check("zsh", ["-f"])

    def test_not_built_warns(self):
        self.check("bash", ["--noprofile", "--norc"], built=False)


if __name__ == "__main__":
    unittest.main()
