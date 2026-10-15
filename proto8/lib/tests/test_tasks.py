"""proto8/lib 的自動測試：tasks（aos seq／par／if）。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

巢狀那一層用 `aos par`（PATH 照 helpers.ENV）。
"""
import json
import os
import signal
import subprocess
import sys
import time
import unittest

from helpers import ENV, LIB, LOOP, Tmp, alive

SEQ, PAR, IF = (os.path.join(LIB, x) for x in ("aos_seq.py", "aos_par.py", "aos_if.py"))


class Tasks(Tmp):
    def sh(self, name, sh):
        """跑完在 log 附加一行 NAME。"""
        return self.inst(name, "(%s); r=$?; echo %s >> log; exit $r" % (sh, name))

    def cli(self, prog, *targets):
        return subprocess.run([sys.executable, prog] + list(targets), capture_output=True, text=True, cwd=self.tmp, env=ENV)

    def errors(self, r):
        """stderr 是 JSON 串流（N-12）：每行一份，回 error 的 code 清單。"""
        return [json.loads(x)["error"]["code"] for x in r.stderr.splitlines()]

    def test_seq_order_and_stop_on_failure(self):
        a, b, c = self.sh("a", "true"), self.sh("b", "exit 3"), self.sh("c", "true")
        self.assertEqual(self.cli(SEQ, a, b, c).returncode, 3)
        self.assertEqual(self.read("log"), "a\nb\n")
        os.remove(self.p("log"))
        self.assertEqual(self.cli(SEQ, "a", "c").returncode, 0)     # 相對路徑從 cwd 算
        self.assertEqual(self.read("log"), "a\nc\n")

    def test_bad_target_fails_at_that_step(self):
        # 跑到哪讀到哪（原本「先全部驗過才跑」拿掉）：壞的那一步 aos_inst 自己報錯，前面的已經跑了
        a = self.sh("a", "true")
        r = self.cli(SEQ, a, self.p("nope.json"))
        self.assertEqual((r.returncode, self.errors(r), self.read("log")), (1, ["ReadFailed"], "a\n"))
        os.remove(self.p("log"))
        r = self.cli(PAR, a, self.p("nope.json"))
        self.assertEqual((r.returncode, self.errors(r), self.read("log")), (1, ["ReadFailed"], "a\n"))
        for prog in (SEQ, PAR):
            r = self.cli(prog)
            self.assertEqual((r.returncode, self.errors(r)), (1, ["Usage"]))

    def test_code_from_inst_stdout(self):
        # 碼從 aos_inst 的 stdout 結果來（沒有 exit 檔）
        a, b = self.sh("a", "true"), self.sh("b", "exit 2")
        for prog, args, code in ((SEQ, (a, b), 2), (PAR, (b, a), 2), (IF, (b, a, b), 2)):
            with self.subTest(prog=os.path.basename(prog), args=args):
                self.assertEqual(self.cli(prog, *args).returncode, code)

    def test_inherited_stdout_does_not_confuse_result(self):
        # stdout 接呼叫者的（/dev/stdout）：子程式自己的輸出（甚至長得像結果）混在 aos_inst 的 stdout 前面，碼照樣取最後那份結果
        a = self.inst("a", "echo '{\"code\": 0}'; echo hi; exit 6", stdout="/dev/stdout")
        r = self.cli(SEQ, a)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (6, "", ""))

    def test_half_json_ignored(self):
        # 被殺時最後一份只寫一半：解析不了就忽略，只認完整的；因此找不到結果＝沒有結果（ResultUnreadable）
        import aos_tasks
        self.assertEqual(aos_tasks._code('{"id": "a", "code": 3}\n{"id": "b", "co'), 3)
        self.assertIsNone(aos_tasks._code('{"id": "a", "co'))

    def test_launch_error(self):
        a, bad, c = self.sh("a", "true"), self.inst("bad", "x", argv=["/no/such/prog"]), self.sh("c", "true")
        r = self.cli(SEQ, a, bad, c)
        self.assertEqual((r.returncode, self.read("log")), (1, "a\n"))
        self.assertEqual(self.errors(r), ["CommandNotFound"])          # aos_inst 的 stderr 原樣流過來，也是 JSON
        self.assertEqual(r.stdout, "")                                  # aos_inst 的結果 JSON 不漏出來
        os.remove(self.p("log"))
        r = self.cli(PAR, a, bad, c)
        self.assertEqual((r.returncode, sorted(self.read("log").split())), (1, ["a", "c"]))

    def test_stdout_stays_clean(self):
        # 子 inst 的結果 JSON 不漏到 tasks 的 stdout；tasks 自己也不吐（空的 JSON 串流，結果在退出碼）
        a, b = self.sh("a", "true"), self.sh("b", "exit 2")
        inner = self.inst("inner", "x", argv=["aos", "par", a, b])
        for prog, args, code in ((SEQ, (a, b), 2), (PAR, (a, b), 2), (IF, (b, a), 0), (SEQ, (a, inner), 2)):
            with self.subTest(prog=os.path.basename(prog)):
                r = self.cli(prog, *args)
                self.assertEqual((r.returncode, r.stdout, r.stderr), (code, "", ""))
        r = self.cli(SEQ, self.p("nope"))
        self.assertEqual((r.stdout, self.errors(r)), ("", ["ReadFailed"]))

    def test_par_concurrent_and_first_failure_in_order(self):
        a, b, c = self.sh("a", "sleep 0.5; exit 4"), self.sh("b", "exit 5"), self.sh("c", "sleep 0.5")
        t0 = time.monotonic()
        self.assertEqual(self.cli(PAR, a, b, c).returncode, 4)
        self.assertLess(time.monotonic() - t0, 1.2)
        self.assertEqual(sorted(self.read("log").split()), ["a", "b", "c"])

    def test_nesting(self):
        # (seq a (par x y) z)，par 那一層寫指令名 `aos par`
        a, x, y, z = (self.sh(n, "true") for n in "axyz")
        inner = self.inst("inner", "x", argv=["aos", "par", x, y])
        self.assertEqual(self.cli(SEQ, a, inner, z).returncode, 0)
        log = self.read("log").split()
        self.assertEqual((log[0], sorted(log[1:3]), log[3]), ("a", ["x", "y"], "z"))

    def test_if(self):
        ok, ng, t, e = self.sh("ok", "true"), self.sh("ng", "exit 2"), self.sh("t", "exit 3"), self.sh("e", "exit 4")
        for args, code, log in (((ok, t, e), 3, "ok t"), ((ng, t, e), 4, "ng e"), ((ng, t), 0, "ng"), ((ok, t), 3, "ok t"),
                                ((ng, e, t), 3, "ng t")):          # 反過來＝分支對調（沒有 aos-not）
            with self.subTest(args=args):
                self.assertEqual(self.cli(IF, *args).returncode, code)
                self.assertEqual(self.read("log").split(), log.split())
                os.remove(self.p("log"))
        for args in ((ok,), (ok, t, e, e)):
            self.assertEqual(self.cli(IF, *args).returncode, 1)
        self.assertFalse(os.path.exists(self.p("log")))
        bad = self.inst("bad", "x", argv=["/no/such/prog"])
        self.assertEqual(self.cli(IF, bad, t, e).returncode, 1)      # 條件起不來不跑 ELSE
        self.assertFalse(os.path.exists(self.p("log")))

    def test_if_signal_skips_branch(self):
        c = self.inst("c", "echo $$ > c.pid; exec sleep 30")
        t = self.sh("t", "true")
        proc = subprocess.Popen([sys.executable, IF, c, t, t], cwd=self.tmp, env=ENV)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        self.until(lambda: os.path.exists(self.p("c.pid")))
        time.sleep(0.1)
        proc.send_signal(signal.SIGINT)
        self.assertEqual(proc.wait(5), 1)                    # 被訊號停＝1（stderr 一份 Signaled）
        self.assertFalse(os.path.exists(self.p("log")))

    def signal_test(self, prog):
        s1 = self.inst("s1", "echo $$ > s1.pid; exec sleep 30")
        s2 = self.inst("s2", "echo $$ > s2.pid; exec sleep 30")
        proc = subprocess.Popen([sys.executable, prog, s1, s2], cwd=self.tmp, env=ENV)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        self.until(lambda: os.path.exists(self.p("s1.pid")))
        pid = int(self.read("s1.pid"))
        time.sleep(0.1)
        proc.send_signal(signal.SIGTERM)
        self.assertEqual(proc.wait(5), 1)
        self.assertFalse(alive(pid))
        return os.path.exists(self.p("s2.pid"))

    def test_seq_signal_stops_rest(self):
        self.assertFalse(self.signal_test(SEQ))

    def test_par_signal_stops_all(self):
        self.signal_test(PAR)
        self.until(lambda: os.path.exists(self.p("s2.pid")))
        self.until(lambda: not alive(int(self.read("s2.pid"))))

    def test_loop_signal_clears_children(self):
        # aos-loop 被收掉：aos seq 的子程式沒開新 session，跟著整群一起收掉
        s1 = self.inst("s1", "echo $$ > s1.pid; exec sleep 30")
        top = self.inst("top", "x", argv=["aos", "seq", s1])
        self.write("l.json", {"inst": {"$ref": top + "/inst.json"}, "ctl": "l.ctl.json", "state": "l.state.json"})
        proc = subprocess.Popen([sys.executable, LOOP, "l.json"], cwd=self.tmp, stdout=subprocess.DEVNULL, env=ENV)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        self.until(lambda: os.path.exists(self.p("s1.pid")))
        pid = int(self.read("s1.pid"))
        proc.send_signal(signal.SIGTERM)                       # 當場收掉＝對 loop 送訊號
        self.assertEqual(proc.wait(10), 1)
        self.until(lambda: not alive(pid))


if __name__ == "__main__":
    unittest.main()
