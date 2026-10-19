"""aos-exec 的 § 14～§ 20 新規則（N-57～N-62、C-73、P-40）。案例移植自 proto8/impls/aos-exec/tests/test_cli.py；
impls 的錯誤代號在 bin 版沒有（N-60），改認原因開頭的字：入口不存在／入口壞／起不來／單子跑不起來／工作區不存在。
跟 test_exec.py 重複的（WS、STACK、巢狀、args 透傳…）不再移植。"""
import json, os, signal, subprocess, tempfile, time, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXEC = str(ROOT / "bin" / "aos-exec")
BIN_DIR = str(ROOT / "bin")


def env_of(extra=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e["PATH"] = os.pathsep.join(p for p in e.get("PATH", "").split(os.pathsep) if p != BIN_DIR)
    e.update(extra or {})
    return e


def run(*args, env=None, cwd=None, input=None):
    """回 (退出碼, stdout, 自己的錯的原因開頭或 None, stderr)。"""
    r = subprocess.run([EXEC, *args], capture_output=True, text=True, env=env_of(env), cwd=cwd, input=input)
    err = None
    if r.returncode == 1 and r.stderr.startswith("aos-exec: ") and len(r.stderr.splitlines()) == 1:
        err = r.stderr[len("aos-exec: "):].split("：", 1)[0]
    return r.returncode, r.stdout, err, r.stderr


def put(path, text, mode=0o644):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if isinstance(text, str) else json.dumps(text))
    p.chmod(mode)
    return str(p)


def prog(parent, name, body, entry="_exec"):
    put(Path(parent) / name / entry, "#!/bin/sh\n" + body, 0o755)
    return str(Path(parent) / name)


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    os.kill(pid, 9)
    return True


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = self._t.name
        self.addCleanup(self._t.cleanup)

    def json_entry(self, doc, *args, **kw):
        put(Path(self.t, "q", "_exec.json"), doc)
        return run(str(Path(self.t, "q")), self.t, *args, **kw)

    # ───── A. impls 的 A 段裡 test_exec.py 沒有的 ─────

    def test_usage_and_ws_missing(self):
        rc, _, _, stderr = run()
        self.assertEqual((rc, stderr.startswith("aos-exec: usage: ")), (1, True))
        d = prog(self.t, "p", "echo hi\n")
        self.assertEqual(run(d, str(Path(self.t, "nope")))[:3:2], (1, "工作區不存在"))

    def test_json_argv_entries(self):
        put(Path(self.t, "p", "_exec.json"), ["sh", "-c", "echo $1:$AOS_WS; exit 5", "sh"])
        ws = Path(self.t, "ws"); ws.mkdir()
        rc, out, _, _ = run(str(Path(self.t, "p")), str(ws), "x")
        self.assertEqual((rc, out.strip()), (5, "x:%s" % ws.resolve()))
        put(Path(self.t, "m", "main.json"), ["echo", "hi"])
        self.assertEqual(run(str(Path(self.t, "m")), self.t, env={"AOS_ENTRY": "main"})[:2], (0, "hi\n"))

    def test_small_shell_wrapper_to_json(self):
        d = prog(self.t, "p", 'exec aos-exec _exec.json - "$@"\n')
        put(Path(d, "_exec.json"), ["echo", "a"])
        self.assertEqual(run(d, self.t, "b")[:2], (0, "a b\n"))

    # ───── B. § 14～§ 19 ─────

    def test_json_array_without_x_and_shebang_skipped(self):
        put(Path(self.t, "p", "_exec"), ["sh", "-c", "echo $1", "sh"])
        self.assertEqual(run(str(Path(self.t, "p")), self.t, "hi")[:2], (0, "hi\n"))
        put(Path(self.t, "s", "_exec"), '#!/usr/bin/env aos-exec\n["echo", "sb"]\n')
        self.assertEqual(run(str(Path(self.t, "s")), self.t)[:2], (0, "sb\n"))

    def test_not_x_not_json_and_x_without_shebang(self):
        put(Path(self.t, "p", "_exec"), "echo hi\n")
        self.assertEqual(run(str(Path(self.t, "p")), self.t)[:3:2], (1, "入口壞"))
        put(Path(self.t, "x", "_exec"), 'echo "hi:$1:$0"\n', 0o755)
        x = str(Path(self.t, "x"))      # § 22：+x 沒 #! 同 execvp 改用 /bin/sh 跑（$0＝那個檔）
        self.assertEqual(run(x, self.t, "a")[:2], (0, "hi:a:%s\n" % Path(x, "_exec").resolve()))

    def test_argv_sh_fallback(self):
        # § 22：argv 陣列入口的檔 +x 沒 #! → 同 execvp 改用 /bin/sh 跑（有 / 的、照 PATH 找到的都是）
        self.assertEqual(self.json_entry(["no-such-cmd-xyz"])[:3:2], (1, "起不來"))
        put(Path(self.t, "q", "noshebang"), 'echo "hi:$1"\n', 0o755)
        self.assertEqual(self.json_entry(["./noshebang"], "a")[:2], (0, "hi:a\n"))
        tools = Path(self.t, "tools")
        put(tools / "mytool", 'echo "my:$1"\n', 0o755)
        put(tools / "good", "#!/bin/sh\necho good:$1\n", 0o755)
        put(tools / "nox", "#!/bin/sh\necho nox\n", 0o644)
        path = {"PATH": "%s:/usr/bin:/bin" % tools}
        self.assertEqual(self.json_entry(["mytool", "b"], env=path)[:2], (0, "my:b\n"))
        self.assertEqual(self.json_entry(["good"], "x", env=path)[:2], (0, "good:x\n"))
        self.assertEqual(self.json_entry(["nox"], env=path)[:3:2], (1, "起不來"))
        later = Path(self.t, "later")
        put(later / "nox", "#!/bin/sh\necho later\n", 0o755)
        env = {"PATH": "%s:%s:/usr/bin:/bin" % (tools, later)}
        self.assertEqual(self.json_entry(["nox"], env=env)[:2], (0, "later\n"))   # 前段沒 +x 換下一段

    def test_exec_replaces_process(self):
        d = prog(self.t, "p", "echo $$\n")
        put(Path(self.t, "q", "_exec.json"), ["sh", "-c", "echo $$"])
        for path in (d, str(Path(self.t, "q"))):
            p = subprocess.Popen([EXEC, path, self.t], stdout=subprocess.PIPE, text=True, env=env_of())
            self.assertEqual(p.communicate()[0].strip(), str(p.pid), path)

    def test_exec_restores_sigpipe(self):
        # Python 預設忽略 SIGPIPE；exec 前要還原，不然入口寫壞掉的管子不會被 SIGPIPE 收掉
        d = prog(self.t, "p", "grep SigIgn /proc/$$/status\n")
        rc, out, _, _ = run(d, self.t)
        self.assertEqual((rc, int(out.split()[1], 16) & (1 << (signal.SIGPIPE - 1))), (0, 0))

    def test_json_kinds(self):
        self.assertEqual(self.json_entry({"run": "x", "max": 3})[:3:2], (1, "入口壞"))   # loop 設定不是入口
        self.assertEqual(self.json_entry({"_exec": ["sh", "-c", "echo hi"]})[:2], (0, "hi\n"))
        self.assertEqual(self.json_entry({"_exec": {"_exec": ["true"]}})[:3:2], (1, "入口壞"))  # 只往下一層
        for bad in ({"_exec": 3}, 3, [], ["echo", 1], None):
            self.assertEqual(self.json_entry(bad)[:3:2], (1, "入口壞"), bad)
        put(Path(self.t, "r", "main.json"), {"main": ["echo", "m"], "_exec": ["echo", "no"]})
        self.assertEqual(run(str(Path(self.t, "r")), self.t, env={"AOS_ENTRY": "main"})[:2], (0, "m\n"))

    def test_string_redirect(self):
        prog(self.t, "a/sub", "echo sub:$1\n")
        put(Path(self.t, "a", "_exec.json"), {"_exec": "sub"})
        self.assertEqual(run(str(Path(self.t, "a")), self.t, "x")[:2], (0, "sub:x\n"))
        put(Path(self.t, "b", "tool.json"), ["sh", "-c", "pwd"])
        put(Path(self.t, "b", "_exec.json"), {"_exec": "tool.json"})
        self.assertEqual(run(str(Path(self.t, "b")), self.t)[:2], (0, str(Path(self.t, "b").resolve()) + "\n"))
        put(Path(self.t, "c", "tool.json"), ["echo", "補"])
        put(Path(self.t, "c", "_exec.json"), {"_exec": "tool"})
        self.assertEqual(run(str(Path(self.t, "c")), self.t)[:2], (0, "補\n"))
        put(Path(self.t, "d", "x", "y.json"), {"_exec": "../z.json"})
        put(Path(self.t, "d", "z.json"), ["echo", "z"])
        self.assertEqual(run(str(Path(self.t, "d", "x", "y.json")), self.t)[:2], (0, "z\n"))

    def test_string_redirect_loop(self):
        put(Path(self.t, "a.json"), {"_exec": "b.json"})
        put(Path(self.t, "b.json"), {"_exec": "a.json"})
        rc, _, err, stderr = run(str(Path(self.t, "a.json")), self.t)
        self.assertEqual((rc, err, "→" in stderr), (1, "入口壞", True))
        put(Path(self.t, "s", "_exec.json"), {"_exec": "."})
        self.assertEqual(run(str(Path(self.t, "s")), self.t)[:3:2], (1, "入口壞"))

    def test_json_completion_and_file_cd(self):
        put(Path(self.t, "prog.json"), ["echo", "p"])
        self.assertEqual(run("prog", self.t, cwd=self.t)[:2], (0, "p\n"))
        put(Path(self.t, "prog.txt.json"), ["echo", "no"])
        self.assertEqual(run("prog.txt", self.t, cwd=self.t)[:3:2], (1, "入口不存在"))
        put(Path(self.t, "dir", "x.json"), ["sh", "-c", "pwd"])
        self.assertEqual(run("dir/x.json", self.t, cwd=self.t)[:2], (0, str(Path(self.t, "dir").resolve()) + "\n"))

    def test_pointer(self):
        put(Path(self.t, "cfg.json"), {"tools": {"stamp": ["echo", "st"], "deep": {"_exec": ["echo", "dp"]},
                                                 "list": [["echo", "l0"]]}, "a/b": ["echo", "esc"]})
        t = self.t
        self.assertEqual(run("cfg.json#/tools/stamp", t, cwd=t)[:2], (0, "st\n"))
        self.assertEqual(run("cfg.json#/tools/deep", t, cwd=t)[:2], (0, "dp\n"))
        self.assertEqual(run("cfg.json#/tools/list/0", t, cwd=t)[:2], (0, "l0\n"))
        self.assertEqual(run("cfg.json#/a~1b", t, cwd=t)[:2], (0, "esc\n"))
        self.assertEqual(run("cfg#/tools/stamp", t, cwd=t)[:2], (0, "st\n"))
        self.assertEqual(run("cfg.json#tools", t, cwd=t)[:3:2], (1, "入口壞"))
        self.assertEqual(run("cfg.json#", t, cwd=t)[:3:2], (1, "入口壞"))
        self.assertEqual(run("cfg.json#/nope", t, cwd=t)[:3:2], (1, "入口不存在"))
        prog(t, "p", "echo hi\n")
        self.assertEqual(run("p/_exec#/x", t, cwd=t)[:3:2], (1, "入口壞"))
        self.assertEqual(run("p#/x", t, cwd=t)[:3:2], (1, "入口壞"))
        put(Path(t, "r.json"), {"_exec": "cfg.json#/tools/stamp"})
        self.assertEqual(run("r.json", t, cwd=t)[:2], (0, "st\n"))

    def test_cf_cd(self):
        d = prog(self.t, "p", 'echo "$AOS_CF|$AOS_CD|$(pwd)"\n')
        real = Path(d).resolve()
        self.assertEqual(run(d, self.t)[1].strip(), "%s/_exec|%s|%s" % (real, real, real))
        put(Path(self.t, "j", "_exec.json"), ["sh", "-c", 'echo "$AOS_CF|$AOS_CD"'])
        rj = Path(self.t, "j").resolve()
        self.assertEqual(run(str(Path(self.t, "j")), self.t)[1].strip(), "%s/_exec.json|%s" % (rj, rj))
        put(Path(self.t, "k", "_exec.json"), {"_exec": "sub/t.json"})
        put(Path(self.t, "k", "sub", "t.json"), ["sh", "-c", 'echo "$AOS_CF|$AOS_CD"'])
        rk = Path(self.t, "k", "sub").resolve()
        self.assertEqual(run(str(Path(self.t, "k")), self.t)[1].strip(), "%s/t.json|%s" % (rk, rk))
        os.symlink(str(Path(self.t, "j")), str(Path(self.t, "link")))
        self.assertEqual(run(str(Path(self.t, "link")), self.t)[1].strip(), "%s/_exec.json|%s" % (rj, rj))

    def test_cf_nested(self):
        inner = prog(self.t, "outer/inner", 'echo "in:$AOS_CF"\n')
        outer = prog(self.t, "outer", 'echo "out:$AOS_CF"; aos-exec inner; echo "out:$AOS_CF"\n')
        ro = Path(outer).resolve()
        rc, out, _, _ = run(outer, self.t)
        self.assertEqual((rc, out.split()),
                         (0, ["out:%s/_exec" % ro, "in:%s/_exec" % Path(inner).resolve(), "out:%s/_exec" % ro]))

    def test_path_not_duplicated(self):
        d = prog(self.t, "p", 'echo "$PATH"\n')
        self.assertEqual(run(d, self.t, env={"PATH": BIN_DIR + ":/usr/bin:/bin"})[1].strip(),
                         BIN_DIR + ":/usr/bin:/bin")
        self.assertEqual(run(d, self.t, env={"PATH": "/usr/bin:/bin"})[1].strip(), BIN_DIR + ":/usr/bin:/bin")

    def test_entry_is_dir(self):
        Path(self.t, "p", "_exec").mkdir(parents=True)
        put(Path(self.t, "p", "_exec.json"), ["echo", "no"])
        self.assertEqual(run(str(Path(self.t, "p")), self.t)[:3:2], (1, "入口不存在"))

    # ───── C. inst 單子（行程內 aos_inst.run，以子程式的碼結束）─────

    def test_inst_exit_code(self):
        self.assertEqual(self.json_entry({"argv": ["sh", "-c", "exit 3"]})[:3:2], (3, None))
        self.assertEqual(self.json_entry({"argv": ["sh", "-c", "exit 10"]})[0], 10)
        self.assertEqual(self.json_entry({"argv": ["sh", "-c", "kill -TERM $$"]})[0], 143)
        self.assertEqual(self.json_entry({"argv": ["true"]})[0], 0)

    def test_inst_stays_as_supervisor(self):
        put(Path(self.t, "q", "_exec.json"), {"argv": ["sh", "-c", "echo $$"]})
        p = subprocess.Popen([EXEC, str(Path(self.t, "q")), self.t], stdout=subprocess.PIPE, text=True, env=env_of())
        out = p.communicate()[0].strip()
        self.assertEqual((p.returncode, out != str(p.pid), out.isdigit()), (0, True, True))

    def test_inst_shebang_not_x(self):
        put(Path(self.t, "p", "_exec"), '#!/usr/bin/env aos-inst\n{"argv": ["echo", "sb"]}\n')
        self.assertEqual(run(str(Path(self.t, "p")), self.t, "x")[:2], (0, "sb x\n"))

    def test_inst_args_pointer_key(self):
        self.assertEqual(self.json_entry({"argv": ["echo", "a"]}, "b", "c")[:2], (0, "a b c\n"))
        put(Path(self.t, "cfg.json"), {"tools": {"stamp": {"argv": ["echo", "st"]}}})
        self.assertEqual(run("cfg.json#/tools/stamp", self.t, "x", cwd=self.t)[:2], (0, "st x\n"))
        self.assertEqual(self.json_entry({"_exec": {"argv": ["echo", "in"]}})[:2], (0, "in\n"))
        put(Path(self.t, "r.json"), {"_exec": "cfg.json#/tools/stamp"})
        self.assertEqual(run("r.json", self.t, cwd=self.t)[:2], (0, "st\n"))

    def test_inst_streams(self):
        self.assertEqual(self.json_entry({"argv": ["cat"]}, input="hi\n")[:2], (0, "hi\n"))
        rc, _, _, stderr = self.json_entry({"argv": ["sh", "-c", "echo oops >&2"]})
        self.assertEqual((rc, stderr), (0, "oops\n"))
        q = Path(self.t, "q")
        self.assertEqual(self.json_entry({"argv": ["echo", "f"], "stdout": "out.txt"})[:2], (0, ""))
        self.assertEqual((q / "out.txt").read_text(), "f\n")
        self.json_entry({"argv": ["echo", "g"], "stdout": "out.txt", "stdout_append": True})
        self.assertEqual((q / "out.txt").read_text(), "f\ng\n")
        put(q / "in.txt", "from file\n")
        self.assertEqual(self.json_entry({"argv": ["cat"], "stdin": "in.txt"}, input="ignored")[:2],
                         (0, "from file\n"))
        self.json_entry({"argv": ["sh", "-c", "echo e >&2"], "stderr": "err.txt"})
        self.assertEqual((q / "err.txt").read_text(), "e\n")
        (q / "sub").mkdir()
        self.json_entry({"argv": ["sh", "-c", "pwd"], "cwd": "sub", "stdout": "o.txt"})
        self.assertEqual((q / "sub" / "o.txt").read_text().strip(), str((q / "sub").resolve()))
        self.assertEqual(self.json_entry({"argv": ["sh", "-c", "echo $A:$AOS_WS"], "envs": {"A": "1"}})[:2],
                         (0, "1:%s\n" % Path(self.t).resolve()))

    def test_inst_env_directive(self):
        self.json_entry({"argv": ["echo", "s"], "stdout": {"$env": "AOS_STACK", "path": "out"}})
        self.assertEqual(Path(self.t, ".aos", "out").read_text(), "s\n")
        q = Path(self.t, "q").resolve()
        self.assertEqual(self.json_entry({"argv": ["echo", {"$env": "AOS_CD"}, {"$env": "AOS_CF"}]})[:2],
                         (0, "%s %s/_exec.json\n" % (q, q)))
        rc, _, err, stderr = self.json_entry({"argv": ["echo", {"$env": "AOS_NOPE_XYZ"}]})
        self.assertEqual((rc, err, "AOS_NOPE_XYZ" in stderr), (1, "單子跑不起來", True))

    def test_inst_timeout_kills_group(self):
        rc = self.json_entry({"argv": ["sh", "-c", "sleep 100 & echo $! > pid; wait"], "timeout_ms": 200})[0]
        pid = int(Path(self.t, "q", "pid").read_text())
        time.sleep(0.1)
        self.assertEqual((rc, alive(pid)), (143, False))

    def start(self, doc):
        put(Path(self.t, "q", "_exec.json"), doc)
        return subprocess.Popen([EXEC, str(Path(self.t, "q")), self.t], stdout=subprocess.PIPE, text=True,
                                env=env_of())

    def wait_file(self, path):
        for _ in range(150):
            if path.exists() and path.read_text().strip():
                return
            time.sleep(0.02)

    def test_inst_signal_forward(self):
        p = self.start({"argv": ["sh", "-c", "sleep 100 & echo $! > pid; wait"]})
        pidfile = Path(self.t, "q", "pid")
        self.wait_file(pidfile)
        p.send_signal(signal.SIGTERM)
        rc = p.wait(timeout=3)
        p.stdout.close()
        time.sleep(0.1)
        self.assertEqual((rc, alive(int(pidfile.read_text()))), (143, False))
        p = self.start({"argv": ["sh", "-c", "trap '' TERM; echo ok > ready; while :; do sleep 0.05; done"],
                        "grace_ms": 200})
        self.wait_file(Path(self.t, "q", "ready"))
        t0 = time.monotonic()
        p.send_signal(signal.SIGTERM)
        rc = p.wait(timeout=3)
        p.stdout.close()
        self.assertEqual((rc, time.monotonic() - t0 < 2), (137, True))

    def test_inst_noshebang_runs_by_sh(self):
        # § 21「不擋」：單子的 argv[0] 是 +x 沒 #! 的檔 → 照 execvp 改用 /bin/sh 跑；§ 22 起 argv 陣列入口也一樣
        put(Path(self.t, "q", "nosb"), 'echo "sh:$1"\n', 0o755)
        self.assertEqual(self.json_entry({"argv": ["./nosb", "a"]})[:2], (0, "sh:a\n"))
        tools = Path(self.t, "tools")
        put(tools / "nosb2", 'echo "path:$1"\n', 0o755)
        env = {"PATH": "%s:/usr/bin:/bin" % tools}
        self.assertEqual(self.json_entry({"argv": ["nosb2"]}, "b", env=env)[:2], (0, "path:b\n"))
        self.assertEqual(self.json_entry(["./nosb", "a"])[:2], (0, "sh:a\n"))
        self.assertEqual(self.json_entry(["nosb2", "b"], env=env)[:2], (0, "path:b\n"))

    def test_inst_bad(self):
        put(Path(self.t, "q", "_exec"), "{not json")
        self.assertEqual(run(str(Path(self.t, "q")), self.t)[:3:2], (1, "入口壞"))
        os.remove(Path(self.t, "q", "_exec"))
        for doc in ({"argv": []}, {"argv": ["echo", 1]}, {"argv": ["true"], "timeout_ms": "5"},
                    {"argv": ["true"], "timeout_ms": 0}, {"argv": ["true"], "grace_ms": -1},
                    {"argv": ["true"], "stdout": 3}, {"argv": ["true"], "envs": {"A": 1}},
                    {"argv": ["true"], "stdout_append": 1}, {"argv": ["no-such-cmd-xyz"]},
                    {"argv": ["true"], "cwd": "nope"}, {"argv": ["true"], "stdout": "nodir/x"}):
            self.assertEqual(self.json_entry(doc)[:3:2], (1, "單子跑不起來"), doc)

    def test_inst_extra_keys_ignored(self):
        rc, out, _, stderr = self.json_entry({"argv": ["sh", "-c", "echo o; echo e >&2"], "stderr_merge": True,
                                              "id": 3})
        self.assertEqual((rc, out, stderr), (0, "o\n", "e\n"))
        rc, _, err, _ = self.json_entry({"argv": ["true"], "cwd": "made", "cwd_mkdir": True})
        self.assertEqual((rc, err, Path(self.t, "q", "made").exists()), (1, "單子跑不起來", False))


if __name__ == "__main__":
    unittest.main()
