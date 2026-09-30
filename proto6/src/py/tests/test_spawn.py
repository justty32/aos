"""開程序（inst.md〈執行與錯誤〉）：結束碼對應、exit 檔、環境、串流、setsid、逾時。"""
import os
import stat
import sys
import time

from aos_inst import InstError
from aos_inst.spawn import run, status_to_code
from tests.util import TmpCase

PY = sys.executable


class Spawn(TmpCase):
    def go(self, inst, **kw):
        return run(self.plan(inst), **kw)

    def read(self, rel):
        with open(self.path(rel)) as f:
            return f.read()

    def test_exit_code_and_exit_file(self):
        r = self.go({"argv": ["sh", "-c", "exit 7"], "envs": {"PATH": os.defpath}, "exit": "code"},
                    base_env={})
        self.assertEqual((r.exit_code, r.timed_out, r.finalize_error), (7, False, None))
        self.assertEqual(self.read("code"), "7\n")

    def test_exit_append_and_mkdir(self):
        inst = {"argv": [PY, "-c", "pass"], "exit": {"$opt": ["append", "mkdir"], "$val": "d/code"}}
        self.go(inst)
        self.go(inst)
        self.assertEqual(self.read("d/code"), "0\n0\n")

    def test_127_and_126_write_exit(self):
        r = self.go({"argv": ["no-such-prog-aos"], "exit": "code"})
        self.assertEqual(r.exit_code, 127)
        self.assertEqual(self.read("code"), "127\n")
        self.write("noexec", "#!/bin/sh\n", raw=True)
        r = self.go({"argv": ["./noexec"], "exit": "code"})
        self.assertEqual(r.exit_code, 126)
        self.assertEqual(self.read("code"), "126\n")

    def test_signal_is_128_plus_n(self):
        r = self.go({"argv": [PY, "-c", "import os,signal; os.kill(os.getpid(), signal.SIGUSR1)"]})
        self.assertEqual(r.exit_code, 128 + 10)
        self.assertEqual(status_to_code(-9), 137)

    def test_timeout_term(self):
        t = time.monotonic()
        r = self.go({"argv": [PY, "-c", "import time; time.sleep(30)"], "exit": "code"},
                    timeout=0.2, grace=5)
        self.assertEqual((r.exit_code, r.timed_out), (143, True))
        self.assertLess(time.monotonic() - t, 3)
        self.assertEqual(self.read("code"), "143\n")

    def test_timeout_kill_after_grace(self):
        prog = ("import signal,sys,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                "print('ready', flush=True); time.sleep(30)")
        self.write("ready", "", raw=True)
        r = self.go({"argv": [PY, "-c", prog], "stdout": "ready"}, timeout=0.3, grace=0.3)
        self.assertEqual((r.exit_code, r.timed_out), (137, True))

    def test_timeout_kills_whole_group(self):
        # 孫子在同一個 process group，逾時要一起收
        prog = "sleep 30 & echo $! > pid; wait"
        r = self.go({"argv": ["sh", "-c", prog]}, timeout=0.3, grace=0.5)
        self.assertTrue(r.timed_out)
        pid = int(self.read("pid"))
        time.sleep(0.05)
        with self.assertRaises(ProcessLookupError):
            for _ in range(50):
                os.kill(pid, 0)
                time.sleep(0.02)

    def test_setsid(self):
        self.go({"argv": [PY, "-c", "import os; print(os.getsid(0) == os.getpid())"], "stdout": "o"})
        self.assertEqual(self.read("o"), "True\n")

    def test_env_overlay_clear_forced(self):
        code = "import os,json; print(json.dumps({k: os.environ.get(k) for k in ('A','B','F')}))"
        self.go({"argv": [PY, "-c", code], "envs": {"B": "b"}, "stdout": "o"},
                base_env={"A": "a"}, forced_env={"F": "f"})
        self.assertEqual(self.read("o"), '{"A": "a", "B": "b", "F": "f"}\n')
        self.go({"argv": [PY, "-c", code], "envs": {"$opt": "clear", "$val": {"B": "b"}}, "stdout": "o"},
                base_env={"A": "a"}, forced_env={"F": "f"})
        self.assertEqual(self.read("o"), '{"A": null, "B": "b", "F": "f"}\n')

    def test_path_lookup_uses_final_path(self):
        self.write("bin/hello", "#!/bin/sh\necho hi-from-path\n", raw=True)
        os.chmod(self.path("bin/hello"), stat.S_IRWXU)
        self.go({"argv": ["hello"], "envs": {"PATH": self.path("bin")}, "stdout": "o"},
                base_env={"PATH": "/nonexistent"})
        self.assertEqual(self.read("o"), "hi-from-path\n")

    def test_streams(self):
        self.write("in.txt", "hello", raw=True)
        code = "import sys; d=sys.stdin.read(); print(d); print('err', file=sys.stderr)"
        self.go({"argv": [PY, "-c", code], "stdin": "in.txt", "stdout": "o",
                 "stderr": {"$opt": "merge"}})
        self.assertEqual(sorted(self.read("o").split()), ["err", "hello"])
        self.write("o", "old\n", raw=True)
        self.go({"argv": [PY, "-c", "print('new')"], "stdout": {"$opt": "append", "$val": "o"}})
        self.assertEqual(self.read("o"), "old\nnew\n")
        self.go({"argv": [PY, "-c", "import sys; print('e', file=sys.stderr)"],
                 "stderr": {"$opt": "mkdir", "$val": "logs/err"}})
        self.assertEqual(self.read("logs/err"), "e\n")

    def test_stderr_override(self):
        self.go({"argv": [PY, "-c", "import sys; print('e', file=sys.stderr)"],
                 "stderr": {"$opt": "merge"}, "stdout": "o"}, stderr_override=self.path("ovr"))
        self.assertEqual((self.read("o"), self.read("ovr")), ("", "e\n"))

    def test_prepare_failed_no_exit(self):
        with self.assertRaises(InstError) as cm:
            self.go({"argv": [PY, "-c", "pass"], "exit": "nodir/code"})
        self.assertEqual(cm.exception.code, "PrepareFailed")
        with self.assertRaises(InstError) as cm:
            self.go({"argv": [PY, "-c", "pass"], "cwd": "missing", "exit": "../code"})
        self.assertEqual(cm.exception.code, "PrepareFailed")
        self.assertFalse(os.path.exists(self.path("code")))
        with self.assertRaises(InstError) as cm:
            self.go({"argv": [PY, "-c", "pass"], "stdin": "no-such-input"})
        self.assertEqual(cm.exception.code, "PrepareFailed")

    def test_cwd_mkdir_in_spawn(self):
        self.go({"argv": [PY, "-c", "import os; print(os.getcwd())"],
                 "cwd": {"$opt": "mkdir", "$val": "w"}, "stdout": "o"})
        self.assertEqual(self.read("w/o").strip(), self.path("w"))

    def test_finalize_failed(self):
        os.makedirs(self.path("code"))          # exit 路徑是資料夾，寫不進去
        r = self.go({"argv": [PY, "-c", "raise SystemExit(3)"], "exit": "code"})
        self.assertEqual(r.exit_code, 3)
        self.assertEqual(r.finalize_error.code, "FinalizeFailed")
