"""test_aos_py_live - 入口 aos.py 對真的 aos 樹（start-api 抄一份、假腦）實跑：遙控器 a.ctl.state(json=True)、a.tools.ls()、a.say／a.listen、a.stack；模組層 agent.ctl.ls、daemon_ctl；指令自己擋下的（a.ctl.ls 不吃 --target）原樣成 Failed；echo 印出的那條拿去 shell 跑結果一樣；以 - 開頭的話照送。"""
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr

PROTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROTO / "lib"))          # 裝好的那份（跟 bin/ 的指令同一份）
import aos.py  # noqa: E402
from aos.py import agent, daemon_ctl, Failed  # noqa: E402

ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
ENV.update(AOS_HOME=str(PROTO), PATH=str(PROTO / "bin") + os.pathsep + ENV["PATH"], PYTHONDONTWRITEBYTECODE="1")


def until(cond, timeout=30, every=0.1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = cond()
        if v:
            return v
        time.sleep(every)
    raise AssertionError("timed out")


class Live(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="aos-py-live-")))
        cls.daemon = str(cls.tmp / "tree" / ".stack")
        cls.tree = cls.tmp / "tree"
        shutil.copytree(PROTO / "templates" / "starts" / "start-api", cls.tree, symlinks=True)
        cls.logs = [open(cls.tmp / "root.log", "w")]
        cls.procs = [subprocess.Popen(["aos-exec", "root"], cwd=cls.tree, env=ENV, stdin=subprocess.DEVNULL,
                                      stdout=cls.logs[0], stderr=subprocess.STDOUT, start_new_session=True)]
        until(lambda: (cls.tree / ".stack" / "state.json").exists())
        subprocess.run(["aos-daemon-ctl", "-d", ".stack", "add", "--auto-restart", "llm"], cwd=cls.tree, env=ENV,
                       check=True, capture_output=True, timeout=60)   # llm kernel 掛在根上一列（start-api README）
        until(lambda: (cls.tree / ".stack" / "procs" / "llm" / "state.json").exists())
        os.environ.update(AOS_HOME=str(PROTO), PATH=ENV["PATH"])
        for k in [k for k in os.environ if k.startswith("AOS_") and k != "AOS_HOME"]:
            del os.environ[k]
        cls.daemon = str(cls.tree / ".stack")
        try:
            agent.ctl.add(str(cls.tree / "agents" / "ann"), daemon=cls.daemon, w=str(cls.tree), auto_restart=True)
        except Exception:
            cls.tearDownClass()                                       # setUpClass 失敗不會叫 tearDownClass：自己收
            raise
        cls.a = agent.attach("ann", daemon=cls.daemon)

    @classmethod
    def tearDownClass(cls):
        try:
            try:
                daemon_ctl.shutdown(daemon=cls.daemon)              # llm kernel 是根上一列，跟著睡下
            except Failed:
                pass
            for p in cls.procs:
                try:
                    p.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)          # 只收這個測試自己起的那一群
                    p.wait()
        finally:
            for f in cls.logs:
                f.close()
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_handle(self):
        a = self.a
        st = a.ctl.state("who", json=True)
        self.assertEqual(st["who"]["name"], "ann")
        self.assertEqual(a.stack, st["who"]["stack"])
        self.assertTrue(os.path.isabs(a.stack))
        tools = a.tools.ls()
        self.assertIn("peek_now_time", tools)
        self.assertIsInstance(a.tools.ls(json=True), (list, dict))
        one = a.say("hello")
        self.assertIs(type(one), str)
        self.assertIn("FAKE ANSWER to: hello", a.listen(timeout_s=30, letter=one))
        dash = a.say("-h")                                            # 以 - 開頭的話：代理先放 --，照送不當旗標
        self.assertIn("FAKE ANSWER to: -h", a.listen(timeout_s=30, letter=dash))

    def test_module_level_and_daemon_ctl(self):
        rows = agent.ctl.ls(daemon=self.daemon)
        self.assertRegex(rows, r"(?m)^ann\s")
        d = daemon_ctl.attach(self.daemon)
        self.assertIn("ann", d.ls(json=True)["procs"])
        self.assertIn("replied in", d.ping())

    def test_command_refuses_target_on_ctl_ls(self):
        with self.assertRaises(Failed) as e:
            self.a.ctl.ls()                                           # ctl ls 不吃 --target：指令自己擋，錯誤行原樣帶上來
        self.assertEqual(e.exception.program, "aos-agent")
        self.assertTrue(e.exception.code)
        self.assertEqual(e.exception.exit, 1)
        with self.assertRaises(Failed) as e:
            agent.attach("nobody", daemon=self.daemon).ctl.state()
        self.assertEqual(e.exception.program, "aos-agent")

    def test_echo_line_runs_the_same_in_shell(self):
        err = io.StringIO()
        try:
            aos.py.echo = True
            with redirect_stderr(err):
                got = self.a.tools.ls()
        finally:
            aos.py.echo = False
        line = err.getvalue().strip()
        self.assertTrue(line.startswith("$ aos-agent --daemon %s --target ann tools ls" % self.daemon), line)
        r = subprocess.run(line[2:], shell=True, env=ENV, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.stdout, got)


if __name__ == "__main__":
    unittest.main()
