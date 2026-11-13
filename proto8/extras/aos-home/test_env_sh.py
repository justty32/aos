"""test_env_sh - 驗 env.sh：bash 與 zsh 都 source 得過，source 後環境裡的 AOS_* 只剩 AOS_HOME（＝env.sh 所在的資料夾），CLAUDE 那三個也清掉。只 source、不起任何行程。"""
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_SH = os.path.join(HERE, "env.sh")

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


def source_and_dump(shell, argv, env_sh, cwd):
    """在乾淨的環境（只有 PATH、HOME 與 INHERITED）用 shell source env_sh，回 (結束碼, {名: 值})：source 後 env 印出來的 AOS_* 與 CLAUDE*。"""
    env = {"PATH": "/usr/bin:/bin", "HOME": cwd}
    env.update(INHERITED)
    script = 'source "$1" || exit 3; env'
    p = subprocess.run([shell] + argv + ["-c", script, "x", env_sh], env=env, cwd=cwd,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    left = {}
    for line in p.stdout.decode("utf-8", "replace").splitlines():
        name, eq, value = line.partition("=")
        if eq and (name.startswith("AOS_") or name.startswith("CLAUDE")):
            left[name] = value
    return p.returncode, left


class EnvShTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos-env-sh-")
        self.home = os.path.join(os.path.realpath(self.tmp), "home")
        os.mkdir(self.home)
        shutil.copy(ENV_SH, os.path.join(self.home, "env.sh"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def check(self, shell, argv):
        if shutil.which(shell, path="/usr/bin:/bin") is None:
            self.skipTest("%s not installed" % shell)
        for how in (os.path.join(self.home, "env.sh"), "./env.sh"):
            with self.subTest(shell=shell, source=how):
                code, left = source_and_dump(shell, argv, how, self.home)
                self.assertEqual(code, 0)
                self.assertEqual(left, {"AOS_HOME": self.home})

    def test_bash(self):
        self.check("bash", ["--noprofile", "--norc"])

    def test_zsh(self):
        self.check("zsh", ["-f"])


if __name__ == "__main__":
    unittest.main()
