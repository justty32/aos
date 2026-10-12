"""proto8-1 的自動測試（aos-seq、aos-par、aos-if、aos-not）。只用標準庫：

    python3 -m unittest discover -s proto8-1/tests

每個測試在 mktemp 建的暫存資料夾裡跑，跑完刪掉。
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(HERE, "lib")
BIN = os.path.join(HERE, "bin")
SEQ = os.path.join(LIB, "aos_seq.py")
PAR = os.path.join(LIB, "aos_par.py")
IF = os.path.join(LIB, "aos_if.py")
NOT = os.path.join(LIB, "aos_not.py")
sys.path.insert(0, os.path.join(HERE, "..", "proto8", "lib"))

from aos_loop import Loop  # noqa: E402


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


class Tasks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos-test-")
        self.addCleanup(shutil.rmtree, self.tmp)

    def p(self, *parts):
        return os.path.join(self.tmp, *parts)

    def read(self, name):
        with open(self.p(name)) as f:
            return f.read()

    def inst(self, name, argv):
        """寫 NAME/inst.json（cwd＝暫存資料夾），回資料夾的絕對路徑。"""
        os.makedirs(self.p(name))
        with open(self.p(name, "inst.json"), "w") as f:
            json.dump({"argv": argv, "cwd": self.tmp}, f)
        return self.p(name)

    def sh(self, name, sh):
        """跑完在 log 附加一行 NAME。"""
        return self.inst(name, ["sh", "-c", "(%s); r=$?; echo %s >> log; exit $r" % (sh, name)])

    def cli(self, prog, *targets):
        return subprocess.run([sys.executable, prog] + list(targets), capture_output=True, text=True, cwd=self.tmp)

    def until(self, cond, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if cond():
                return
            time.sleep(0.02)
        self.fail("等不到")

    def test_seq_order_and_stop_on_failure(self):
        a, b, c = self.sh("a", "true"), self.sh("b", "exit 3"), self.sh("c", "true")
        self.assertEqual(self.cli(SEQ, a, b, c).returncode, 3)
        self.assertEqual(self.read("log"), "a\nb\n")
        os.remove(self.p("log"))
        self.assertEqual(self.cli(SEQ, "a", "c").returncode, 0)     # 相對路徑從 cwd 算
        self.assertEqual(self.read("log"), "a\nc\n")

    def test_bad_target_runs_nothing(self):
        a = self.sh("a", "true")
        for prog in (SEQ, PAR):
            r = self.cli(prog, a, self.p("nope.json"))
            self.assertEqual(r.returncode, 125)
            self.assertTrue(r.stderr.startswith("ReadFailed"))
            self.assertEqual(self.cli(prog).returncode, 125)
        self.assertFalse(os.path.exists(self.p("log")))

    def test_launch_error(self):
        a, bad, c = self.sh("a", "true"), self.inst("bad", ["/no/such/prog"]), self.sh("c", "true")
        r = self.cli(SEQ, a, bad, c)
        self.assertEqual((r.returncode, self.read("log")), (127, "a\n"))
        self.assertTrue(r.stderr.startswith("CommandNotFound"))
        os.remove(self.p("log"))
        r = self.cli(PAR, a, bad, c)
        self.assertEqual((r.returncode, sorted(self.read("log").split())), (127, ["a", "c"]))

    def test_par_concurrent_and_first_failure_in_order(self):
        a, b, c = self.sh("a", "sleep 0.5; exit 4"), self.sh("b", "exit 5"), self.sh("c", "sleep 0.5")
        t0 = time.monotonic()
        self.assertEqual(self.cli(PAR, a, b, c).returncode, 4)
        self.assertLess(time.monotonic() - t0, 1.2)
        self.assertEqual(sorted(self.read("log").split()), ["a", "b", "c"])

    def test_nesting(self):
        # (seq a (par x y) z)，par 那一層用 bin/ 的薄入口
        a, x, y, z = (self.sh(n, "true") for n in "axyz")
        inner = self.inst("inner", [os.path.join(BIN, "aos-par"), x, y])
        self.assertEqual(self.cli(SEQ, a, inner, z).returncode, 0)
        log = self.read("log").split()
        self.assertEqual((log[0], sorted(log[1:3]), log[3]), ("a", ["x", "y"], "z"))

    def test_if(self):
        ok, ng, t, e = self.sh("ok", "true"), self.sh("ng", "exit 2"), self.sh("t", "exit 3"), self.sh("e", "exit 4")
        for args, code, log in (((ok, t, e), 3, "ok t"), ((ng, t, e), 4, "ng e"), ((ng, t), 0, "ng"), ((ok, t), 3, "ok t")):
            with self.subTest(args=args):
                self.assertEqual(self.cli(IF, *args).returncode, code)
                self.assertEqual(self.read("log").split(), log.split())
                os.remove(self.p("log"))
        for args in ((ok,), (ok, t, e, e)):
            self.assertEqual(self.cli(IF, *args).returncode, 125)
        self.assertFalse(os.path.exists(self.p("log")))
        bad = self.inst("bad", ["/no/such/prog"])
        self.assertEqual(self.cli(IF, bad, t, e).returncode, 127)      # 條件起不來不跑 ELSE
        self.assertFalse(os.path.exists(self.p("log")))

    def test_not(self):
        ok, ng, bad = self.sh("ok", "true"), self.sh("ng", "exit 2"), self.inst("bad", ["/no/such/prog"])
        self.assertEqual([self.cli(NOT, x).returncode for x in (ok, ng, bad)], [1, 0, 127])
        self.assertEqual(self.cli(NOT, ok, ng).returncode, 125)

    def test_if_signal_skips_branch(self):
        c = self.inst("c", ["sh", "-c", "echo $$ > c.pid; exec sleep 30"])
        t = self.sh("t", "true")
        proc = subprocess.Popen([sys.executable, IF, c, t, t], cwd=self.tmp)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        self.until(lambda: os.path.exists(self.p("c.pid")))
        time.sleep(0.1)
        proc.send_signal(signal.SIGINT)
        self.assertEqual(proc.wait(5), 128 + signal.SIGINT)
        self.assertFalse(os.path.exists(self.p("log")))

    def signal_test(self, prog):
        s1 = self.inst("s1", ["sh", "-c", "echo $$ > s1.pid; exec sleep 30"])
        s2 = self.inst("s2", ["sh", "-c", "echo $$ > s2.pid; exec sleep 30"])
        proc = subprocess.Popen([sys.executable, prog, s1, s2], cwd=self.tmp)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        self.until(lambda: os.path.exists(self.p("s1.pid")))
        pid = int(self.read("s1.pid"))
        time.sleep(0.1)
        proc.send_signal(signal.SIGTERM)
        self.assertEqual(proc.wait(5), 128 + signal.SIGTERM)
        self.assertFalse(alive(pid))
        return os.path.exists(self.p("s2.pid"))

    def test_seq_signal_stops_rest(self):
        self.assertFalse(self.signal_test(SEQ))

    def test_par_signal_stops_all(self):
        self.signal_test(PAR)
        self.until(lambda: os.path.exists(self.p("s2.pid")))
        self.until(lambda: not alive(int(self.read("s2.pid"))))

    def test_loop_remove_clears_children(self):
        # daemon 那邊整群收：aos-seq 的子程式沒開 new_session，跟著一起收掉
        s1 = self.inst("s1", ["sh", "-c", "echo $$ > s1.pid; exec sleep 30"])
        top = self.inst("top", [os.path.join(BIN, "aos-seq"), s1])
        loop = Loop(stop_poll_ms=10)
        self.addCleanup(loop.shutdown)
        loop.add(top, {})
        self.until(lambda: os.path.exists(self.p("s1.pid")))
        pid = int(self.read("s1.pid"))
        loop.remove(top + "/inst.json", False)    # False＝當場收掉這次
        self.until(lambda: not alive(pid))


if __name__ == "__main__":
    unittest.main()
