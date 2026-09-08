# 跑法：cd proto4-1 && python3 -m unittest discover -s test
import os, sys, shutil, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aos_kernel import Kernel, exec_inst, parse_spec

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fx")
def fx(n): return os.path.join(FX, n)
def rm(*names):
    for n in names:
        p = os.path.join(FX, n)
        if os.path.exists(p): os.remove(p)
def clean():
    rm("counter/count.txt", "noshebang/ran.txt", "cfg/out.log", "py/seen.txt", "stdin/got.txt")


class ExecInst(unittest.TestCase):
    def setUp(self): clean()
    def tearDown(self): clean()

    def test_direct_exec(self):
        r = exec_inst(fx("a"), 1)
        self.assertTrue(r["ok"]); self.assertEqual(r["code"], 0); self.assertEqual(r["mode"], "exec")

    def test_no_shebang_falls_back_to_sh(self):
        r = exec_inst(fx("noshebang"), 4)
        self.assertEqual(r["mode"], "sh"); self.assertTrue(r["ok"])
        self.assertEqual(open(fx("noshebang/ran.txt")).read().strip(), "no shebang, tick=4")

    def test_cwd_env_tick(self):
        exec_inst(fx("py"), 9)
        self.assertEqual(open(fx("py/seen.txt")).read(), "%s 9 %s" % (fx("py"), fx("py")))

    def test_config_env_args_stdout_stderr(self):
        exec_inst(fx("cfg"), 2)
        out = open(fx("cfg/out.log")).read()
        self.assertIn("tick=2 K=v1 args=2 x y", out)   # env、args、stdout 到檔
        self.assertIn("to-stderr", out)               # stderr 併進 stdout

    def test_stdin_file(self):
        exec_inst(fx("stdin"), 1)
        self.assertEqual(open(fx("stdin/got.txt")).read().strip(), "hello-stdin")

    def test_exit_map(self):
        self.assertEqual(exec_inst(fx("exitmap"), 1)["ok"], True)                 # 3 在 ok 裡
        self.assertEqual(exec_inst(fx("exitmap"), 2)["action"], "pause")
        self.assertEqual(exec_inst(fx("exitmap"), 3)["action"], "unregister")
        r = exec_inst(fx("errmap"), 1)
        self.assertFalse(r["ok"]); self.assertEqual(r["error"], "退出碼 1")

    def test_no_exit_config_swallows_any_code(self):
        r = exec_inst(fx("exit1"), 1)
        self.assertTrue(r["ok"]); self.assertEqual(r["code"], 1); self.assertIsNone(r["error"])
        r = exec_inst(fx("empty"), 1)          # 空的 {} 跟沒有檔一樣
        self.assertTrue(r["ok"]); self.assertEqual(r["code"], 7)

    def test_bad_config_and_version(self):
        self.assertIn("config.json 壞了", exec_inst(fx("badcfg"), 1)["error"])
        self.assertIn("不認識的 config 版本", exec_inst(fx("badver"), 1)["error"])

    def test_missing_inst(self):
        self.assertIn("找不到", exec_inst(fx("noinst"), 1)["error"])

    def test_timeout(self):
        r = exec_inst(fx("slow"), 1)
        self.assertFalse(r["ok"]); self.assertIn("砍掉", r["error"])


class KernelTest(unittest.TestCase):
    def setUp(self): clean()
    def tearDown(self): clean()

    def test_register_defaults(self):
        k = Kernel()
        p = k.register(fx("a"))
        self.assertEqual((p["name"], p["interval"], p["runs"]), ("a", 1, 0))
        self.assertEqual(k.register(fx("iv"))["interval"], 2)          # config 的 interval
        self.assertEqual(k.register(fx("iv"), "iv2", 3)["interval"], 3)  # 命令列優先
        self.assertEqual(k.register(fx("a"), "z", 0)["interval"], 1)     # 0 當 1
        self.assertEqual([p["name"] for p in k.ls()], ["a", "iv", "iv2", "z"])

    def test_step_interval_pause_unregister(self):
        k = Kernel()
        k.register(fx("a")); k.register(fx("iv"))
        self.assertEqual(k.step(), ["a"]); self.assertEqual(k.step(), ["a", "iv"])
        k.pause("a"); self.assertEqual(k.step(), [])
        k.resume("a"); self.assertEqual(k.step(), ["a", "iv"])
        k.unregister("iv"); self.assertEqual(k.step(), ["a"])
        self.assertEqual(k.procs["a"]["runs"], 4)
        self.assertEqual(k.procs["a"]["last"], {"code": 0, "mode": "exec"})

    def test_counter_keeps_state_in_its_own_files(self):
        k = Kernel(); k.register(fx("counter"))
        self.assertEqual(k.run(3), 3)
        self.assertEqual(open(fx("counter/count.txt")).read().strip(), "3")

    def test_errors_are_recorded_and_others_keep_running(self):
        k = Kernel(); k.register(fx("errmap")); k.register(fx("a")); k.register(fx("badcfg"))
        k.step()
        self.assertEqual(k.procs["errmap"]["error"], "退出碼 1")
        self.assertIn("壞了", k.procs["badcfg"]["error"])
        self.assertEqual(k.procs["a"]["runs"], 1)
        self.assertEqual(k.procs["errmap"]["runs"], 0)

    def test_exit_code_actions(self):
        k = Kernel(); k.register(fx("exitmap"))
        k.step(); self.assertFalse(k.procs["exitmap"]["paused"])
        k.step(); self.assertTrue(k.procs["exitmap"]["paused"])
        k.resume("exitmap"); k.step()
        self.assertNotIn("exitmap", k.procs)

    def test_run_with_interval_really_sleeps(self):
        import time
        k = Kernel(); k.register(fx("a"))
        t0 = time.time(); k.run(2, 1)
        self.assertGreaterEqual(time.time() - t0, 2)

    def test_parse_spec(self):
        self.assertEqual(parse_spec("./w"), ("./w", None, None))
        self.assertEqual(parse_spec("n=./w:3"), ("./w", "n", 3))
        self.assertEqual(parse_spec("C:/x"), ("C:/x", None, None))


if __name__ == "__main__":
    unittest.main()
