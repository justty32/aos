"""aos-exec 的 § 14～§ 20 新規則（N-57～N-62、C-73、P-40）。案例移植自 proto8/impls/aos-exec/tests/test_cli.py；
錯誤一行認原因開頭的字：入口不存在／入口壞／起不來／單子跑不起來／工作區不存在。10-23 起 bin 版也帶代號（照 10-23 命名統合）
（「aos-exec: 代號 原因」），代號由 own_error 統一檢查再拿掉，所以下面的斷言照舊認「aos-exec: 原因」；test_raw_codes 直接看代號。
跟 test_exec.py 重複的（WS、STACK、巢狀、args 透傳…）不再移植。"""
import json, os, signal, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()   # 錯誤一行的代號（照 10-23 命名統合）：檢查對得上原因開頭再拿掉

ROOT = Path(__file__).resolve().parent.parent
EXEC = str(ROOT / "bin" / "aos-exec")
BIN_DIR = str(ROOT / "bin")


def env_of(extra=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    # aos 的程式都不動 PATH（ideas § 24）：入口裡叫 aos-exec，由呼叫者把 bin/ 放 PATH 最前面（env 可蓋掉）
    e["PATH"] = os.pathsep.join([BIN_DIR] + [p for p in e.get("PATH", "").split(os.pathsep) if p != BIN_DIR])
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


def prog(parent, name, body, entry="_entry"):
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
        put(Path(self.t, "q", "_entry.json"), doc)
        return run("--ws", self.t, str(Path(self.t, "q")), *args, **kw)

    # ───── A. impls 的 A 段裡 test_exec.py 沒有的 ─────

    def test_usage_and_ws_missing(self):
        rc, _, _, stderr = run()
        self.assertEqual((rc, stderr.startswith("aos-exec: usage: ")), (1, True))
        d = prog(self.t, "p", "echo hi\n")
        self.assertEqual(run("--ws", str(Path(self.t, "nope")), d)[:3:2], (1, "工作區不存在"))

    # ───── 命令列：aos-exec [旗標...] XXX [args...]（10-21 ideas）─────

    def test_flags_ws_forms_and_priority(self):
        d = prog(self.t, "p", 'echo "$AOS_WS|$#|$*"\n')
        a = Path(self.t, "a"); a.mkdir()
        b = Path(self.t, "b"); b.mkdir()
        for flags in (("--ws", str(a)), ("--ws=%s" % a,)):
            self.assertEqual(run(*flags, d, "x")[:2], (0, "%s|1|x\n" % a.resolve()))
        # --ws 蓋過 $AOS_WS；--ws -／--ws=（空）／沒給＝沿用 $AOS_WS
        self.assertEqual(run("--ws", str(a), d, env={"AOS_WS": str(b)})[1], "%s|0|\n" % a.resolve())
        for flags in (("--ws", "-"), ("--ws=",), ()):
            self.assertEqual(run(*flags, d, env={"AOS_WS": str(b)})[1], "%s|0|\n" % b, flags)
        # 重複給＝最後一個算
        self.assertEqual(run("--ws", str(b), "--ws", str(a), d)[1], "%s|0|\n" % a.resolve())

    def test_old_positional_ws_is_now_an_arg(self):
        d = prog(self.t, "p", 'echo "$AOS_WS|$#|$*"\n')
        other = Path(self.t, "other"); other.mkdir()
        # 舊寫法 aos-exec XXX WS args：WS 不再認，跟後面的一起原樣當 args
        rc, out, _, _ = run(d, str(other), "x", cwd=self.t)
        self.assertEqual((rc, out), (0, "%s|2|%s x\n" % (Path(self.t).resolve(), other)))
        self.assertEqual(run(d, "-", "x", cwd=self.t)[1], "%s|2|- x\n" % Path(self.t).resolve())

    def test_after_xxx_nothing_is_parsed(self):
        d = prog(self.t, "p", 'echo "$#|$*"\n')
        self.assertEqual(run("--ws", self.t, d, "--ws", "zz", "--nope", "--")[:2], (0, "4|--ws zz --nope --\n"))

    def test_double_dash_ends_flags(self):
        prog(self.t, "-p", 'echo "dash|$*"\n')
        self.assertEqual(run("--ws", self.t, "--", "-p", "a", cwd=self.t)[:2], (0, "dash|a\n"))
        self.assertEqual(run("--", "-p", cwd=self.t)[:2], (0, "dash|\n"))

    def test_usage_errors(self):
        d = prog(self.t, "p", "echo hi\n")
        for argv in (("--nope", d), ("-x", d), ("--nope=1", d), ("--ws",), ("--ws", self.t), ("--ws=" + self.t,),
                     ("--",), ("--ws", self.t, "--")):
            rc, out, err, stderr = run(*argv)
            self.assertEqual((rc, out, len(stderr.splitlines())), (1, "", 1), argv)
            self.assertTrue(stderr.startswith("aos-exec: usage: aos-exec [--ws WS] [--dotenv-override] XXX [args...]"), stderr)
        self.assertIn("--nope", run("--nope", d)[3])

    def test_raw_codes(self):
        # 代號照 10-23 命名統合（使用者 10-22「錯誤訊息多代號也遵循」）：stderr 原樣是「程式名: 代號 原因」
        d = prog(self.t, "p", "echo hi\n")
        put(Path(d, "loop.json"), {"val": 3})
        put(Path(d, "fsm.json"), {"start": "a", "states": {"a": {"val": "p", "next": "zz"}}})
        put(Path(d, "daemon.json"), {"state": "state.json", "loops": {"state.json": "p"}})
        Path(d, "bad.json").write_text("{nope")
        dot = prog(self.t, "dot", "echo hi\n")
        Path(dot, ".env").write_text("no-equals\n")
        st = Path(self.t, "st")
        st.mkdir()
        Path(st, "state.txt").mkdir()   # fsm 的 state.txt 在但讀不了（是資料夾）
        put(Path(d, "ok.json"), {"start": "a", "states": {"a": {"val": "p", "next": "a"}}})
        loop, fsm, daemon = (str(ROOT / "bin" / n) for n in ("aos-loop", "aos-fsm", "aos-daemon"))
        e = env_of({"AOS_STACK": str(st)})
        for argv, head in (([EXEC, "--nope", d], "aos-exec: FlagUnknown usage: "),
                           ([EXEC, "--ws"], "aos-exec: ArgumentsBad usage: "),
                           ([EXEC], "aos-exec: ArgumentsBad usage: "),
                           ([EXEC, "--ws", str(Path(self.t, "nope")), d], "aos-exec: WsMissing 工作區不存在："),
                           ([EXEC, "--ws", self.t, str(Path(self.t, "nope"))], "aos-exec: EntryMissing 入口不存在："),
                           ([EXEC, "--ws", self.t, dot], "aos-exec: DotenvBad .env 壞："),
                           ([loop, str(Path(d, "loop.json"))], "aos-loop: CfgBad val 要是"),
                           ([loop], "aos-loop: ArgumentsBad usage: "),
                           ([loop, "--bogus", "x"], "aos-loop: FlagUnknown usage: "),
                           ([loop, str(Path(d, "none.json"))], "aos-loop: CfgMissing 讀不到或不是 JSON："),
                           ([loop, str(Path(d, "bad.json"))], "aos-loop: CfgBad 讀不到或不是 JSON："),
                           ([loop, str(Path(d, "loop.json")) + "#/nope"], "aos-loop: CfgMissing 設定檔指不到："),
                           ([loop, str(Path(d, "loop.json")) + "#val"], "aos-loop: CfgBad 設定檔 "),
                           ([fsm, str(Path(d, "fsm.json"))], "aos-fsm: CfgBad 狀態 a 的 next zz 不在表上"),
                           ([fsm, str(Path(d, "ok.json"))], "aos-fsm: StateBad 讀不了 "),
                           ([daemon, str(Path(d, "daemon.json"))], "aos-daemon: CfgBad loops 的名字")):
            r = subprocess.run(argv, capture_output=True, text=True, env=e, cwd=self.t)
            self.assertEqual((r.returncode, r.raw_stderr.count("\n")), (1, 1), (argv, r.raw_stderr))
            self.assertTrue(r.raw_stderr.startswith(head), (head, r.raw_stderr))

    def test_json_argv_entries(self):
        put(Path(self.t, "p", "_entry.json"), ["sh", "-c", "echo $1:$AOS_WS; exit 5", "sh"])
        ws = Path(self.t, "ws"); ws.mkdir()
        rc, out, _, _ = run("--ws", str(ws), str(Path(self.t, "p")), "x")
        self.assertEqual((rc, out.strip()), (5, "x:%s" % ws.resolve()))
        put(Path(self.t, "m", "main.json"), ["echo", "hi"])
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "m")), env={"AOS_ENTRY": "main"})[:2], (0, "hi\n"))

    def test_small_shell_wrapper_to_json(self):
        d = prog(self.t, "p", 'exec aos-exec _entry.json "$@"\n')
        put(Path(d, "_entry.json"), ["echo", "a"])
        self.assertEqual(run("--ws", self.t, d, "b")[:2], (0, "a b\n"))

    # ───── B. § 14～§ 19 ─────

    def test_json_array_without_x_and_shebang_skipped(self):
        put(Path(self.t, "p", "_entry"), ["sh", "-c", "echo $1", "sh"])
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "p")), "hi")[:2], (0, "hi\n"))
        put(Path(self.t, "s", "_entry"), '#!/usr/bin/env aos-exec\n["echo", "sb"]\n')
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "s")))[:2], (0, "sb\n"))

    def test_not_x_not_json_and_x_without_shebang(self):
        put(Path(self.t, "p", "_entry"), "echo hi\n")
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "p")))[:3:2], (1, "入口壞"))
        put(Path(self.t, "x", "_entry"), 'echo "hi:$1:$0"\n', 0o755)
        x = str(Path(self.t, "x"))      # § 22：+x 沒 #! 同 execvp 改用 /bin/sh 跑（$0＝那個檔）
        self.assertEqual(run("--ws", self.t, x, "a")[:2], (0, "hi:a:%s\n" % Path(x, "_entry").resolve()))

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
        put(Path(self.t, "q", "_entry.json"), ["sh", "-c", "echo $$"])
        for path in (d, str(Path(self.t, "q"))):
            p = subprocess.Popen([EXEC, "--ws", self.t, path], stdout=subprocess.PIPE, text=True, env=env_of())
            self.assertEqual(p.communicate()[0].strip(), str(p.pid), path)

    def test_exec_restores_sigpipe(self):
        # Python 預設忽略 SIGPIPE；exec 前要還原，不然入口寫壞掉的管子不會被 SIGPIPE 收掉
        d = prog(self.t, "p", "grep SigIgn /proc/$$/status\n")
        rc, out, _, _ = run("--ws", self.t, d)
        self.assertEqual((rc, int(out.split()[1], 16) & (1 << (signal.SIGPIPE - 1))), (0, 0))

    def test_json_kinds(self):
        self.assertEqual(self.json_entry({"val": "x", "max": 3})[:3:2], (1, "入口壞"))   # loop 設定不是入口
        self.assertEqual(self.json_entry({"_entry": ["sh", "-c", "echo hi"]})[:2], (0, "hi\n"))
        # 10-21 晚起沒 argv 的物件＝資料夾、一路往下（原「只往下一層」，ideas 10-21 § 6）
        self.assertEqual(self.json_entry({"_entry": {"_entry": ["echo", "deep"]}})[:2], (0, "deep\n"))
        self.assertEqual(self.json_entry({"_entry": {"other": ["true"]}})[:3:2], (1, "入口壞"))
        for bad in ({"_entry": 3}, 3, [], ["echo", 1], None):
            self.assertEqual(self.json_entry(bad)[:3:2], (1, "入口壞"), bad)
        put(Path(self.t, "r", "main.json"), {"main": ["echo", "m"], "_entry": ["echo", "no"]})
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "r")), env={"AOS_ENTRY": "main"})[:2], (0, "m\n"))

    def test_string_redirect(self):
        prog(self.t, "a/sub", "echo sub:$1\n")
        put(Path(self.t, "a", "_entry.json"), {"_entry": "sub"})
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "a")), "x")[:2], (0, "sub:x\n"))
        put(Path(self.t, "b", "tool.json"), ["sh", "-c", "pwd"])
        put(Path(self.t, "b", "_entry.json"), {"_entry": "tool.json"})
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "b")))[:2], (0, str(Path(self.t, "b").resolve()) + "\n"))
        put(Path(self.t, "c", "tool.json"), ["echo", "補"])
        put(Path(self.t, "c", "_entry.json"), {"_entry": "tool"})
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "c")))[:2], (0, "補\n"))
        put(Path(self.t, "d", "x", "y.json"), {"_entry": "../z.json"})
        put(Path(self.t, "d", "z.json"), ["echo", "z"])
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "d", "x", "y.json")))[:2], (0, "z\n"))

    def test_string_redirect_loop(self):
        put(Path(self.t, "a.json"), {"_entry": "b.json"})
        put(Path(self.t, "b.json"), {"_entry": "a.json"})
        rc, _, err, stderr = run("--ws", self.t, str(Path(self.t, "a.json")))
        self.assertEqual((rc, err, "→" in stderr), (1, "入口壞", True))
        put(Path(self.t, "s", "_entry.json"), {"_entry": "."})
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "s")))[:3:2], (1, "入口壞"))

    def test_json_completion_and_file_cd(self):
        put(Path(self.t, "prog.json"), ["echo", "p"])
        self.assertEqual(run("--ws", self.t, "prog", cwd=self.t)[:2], (0, "p\n"))
        put(Path(self.t, "prog.txt.json"), ["echo", "no"])
        self.assertEqual(run("--ws", self.t, "prog.txt", cwd=self.t)[:3:2], (1, "入口不存在"))
        put(Path(self.t, "dir", "x.json"), ["sh", "-c", "pwd"])
        self.assertEqual(run("--ws", self.t, "dir/x.json", cwd=self.t)[:2], (0, str(Path(self.t, "dir").resolve()) + "\n"))

    def test_pointer(self):
        put(Path(self.t, "cfg.json"), {"tools": {"stamp": ["echo", "st"], "deep": {"_entry": ["echo", "dp"]},
                                                 "list": [["echo", "l0"]]}, "a/b": ["echo", "esc"]})
        t = self.t
        self.assertEqual(run("--ws", t, "cfg.json#/tools/stamp", cwd=t)[:2], (0, "st\n"))
        self.assertEqual(run("--ws", t, "cfg.json#/tools/deep", cwd=t)[:2], (0, "dp\n"))
        self.assertEqual(run("--ws", t, "cfg.json#/tools/list/0", cwd=t)[:2], (0, "l0\n"))
        self.assertEqual(run("--ws", t, "cfg.json#/a~1b", cwd=t)[:2], (0, "esc\n"))
        self.assertEqual(run("--ws", t, "cfg#/tools/stamp", cwd=t)[:2], (0, "st\n"))
        self.assertEqual(run("--ws", t, "cfg.json#tools", cwd=t)[:3:2], (1, "入口壞"))
        self.assertEqual(run("--ws", t, "cfg.json#", cwd=t)[:3:2], (1, "入口壞"))
        self.assertEqual(run("--ws", t, "cfg.json#/nope", cwd=t)[:3:2], (1, "入口不存在"))
        prog(t, "p", "echo hi\n")
        self.assertEqual(run("--ws", t, "p/_entry#/x", cwd=t)[:3:2], (1, "入口壞"))
        self.assertEqual(run("--ws", t, "p#/x", cwd=t)[:3:2], (1, "入口壞"))
        put(Path(t, "r.json"), {"_entry": "cfg.json#/tools/stamp"})
        self.assertEqual(run("--ws", t, "r.json", cwd=t)[:2], (0, "st\n"))

    def test_cf_cd(self):
        d = prog(self.t, "p", 'echo "$AOS_CF|$AOS_CD|$(pwd)"\n')
        real = Path(d).resolve()
        self.assertEqual(run("--ws", self.t, d)[1].strip(), "%s/_entry|%s|%s" % (real, real, real))
        put(Path(self.t, "j", "_entry.json"), ["sh", "-c", 'echo "$AOS_CF|$AOS_CD"'])
        rj = Path(self.t, "j").resolve()
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "j")))[1].strip(), "%s/_entry.json|%s" % (rj, rj))
        put(Path(self.t, "k", "_entry.json"), {"_entry": "sub/t.json"})
        put(Path(self.t, "k", "sub", "t.json"), ["sh", "-c", 'echo "$AOS_CF|$AOS_CD"'])
        rk = Path(self.t, "k", "sub").resolve()
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "k")))[1].strip(), "%s/t.json|%s" % (rk, rk))
        os.symlink(str(Path(self.t, "j")), str(Path(self.t, "link")))
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "link")))[1].strip(), "%s/_entry.json|%s" % (rj, rj))

    def test_cf_nested(self):
        inner = prog(self.t, "outer/inner", 'echo "in:$AOS_CF"\n')
        outer = prog(self.t, "outer", 'echo "out:$AOS_CF"; aos-exec inner; echo "out:$AOS_CF"\n')
        ro = Path(outer).resolve()
        rc, out, _, _ = run("--ws", self.t, outer)
        self.assertEqual((rc, out.split()),
                         (0, ["out:%s/_entry" % ro, "in:%s/_entry" % Path(inner).resolve(), "out:%s/_entry" % ro]))

    def test_path_passed_as_is(self):
        # ideas § 24：aos 的程式都不動 PATH，原樣傳下去（不加自己的 bin）
        d = prog(self.t, "p", 'echo "$PATH"\n')
        for path in (BIN_DIR + ":/usr/bin:/bin", "/usr/bin:/bin"):
            self.assertEqual(run("--ws", self.t, d, env={"PATH": path})[1].strip(), path)

    def test_entry_dir_beats_json(self):
        # 10-21 晚起 $AOS_ENTRY 指到資料夾＝走進去（N-61、ideas 10-21 J3），所以同名資料夾贏過旁邊的 .json
        prog(Path(self.t, "p"), "_entry", "echo dir\n")
        put(Path(self.t, "p", "_entry.json"), ["echo", "no"])
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "p")))[:2], (0, "dir\n"))

    # ───── C. inst 單子（行程內 aos_inst.run，以子程式的碼結束）─────

    def test_inst_exit_code(self):
        self.assertEqual(self.json_entry({"argv": ["sh", "-c", "exit 3"]})[:3:2], (3, None))
        self.assertEqual(self.json_entry({"argv": ["sh", "-c", "exit 10"]})[0], 10)
        self.assertEqual(self.json_entry({"argv": ["sh", "-c", "kill -TERM $$"]})[0], 143)
        self.assertEqual(self.json_entry({"argv": ["true"]})[0], 0)

    def test_inst_stays_as_supervisor(self):
        put(Path(self.t, "q", "_entry.json"), {"argv": ["sh", "-c", "echo $$"]})
        p = subprocess.Popen([EXEC, "--ws", self.t, str(Path(self.t, "q"))], stdout=subprocess.PIPE, text=True, env=env_of())
        out = p.communicate()[0].strip()
        self.assertEqual((p.returncode, out != str(p.pid), out.isdigit()), (0, True, True))

    def test_inst_shebang_not_x(self):
        put(Path(self.t, "p", "_entry"), '#!/usr/bin/env 隨便\n{"argv": ["echo", "sb"]}\n')   # 沒 +x：第一行 #! 跳過
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "p")), "x")[:2], (0, "sb x\n"))

    def test_inst_args_pointer_key(self):
        self.assertEqual(self.json_entry({"argv": ["echo", "a"]}, "b", "c")[:2], (0, "a b c\n"))
        put(Path(self.t, "cfg.json"), {"tools": {"stamp": {"argv": ["echo", "st"]}}})
        self.assertEqual(run("--ws", self.t, "cfg.json#/tools/stamp", "x", cwd=self.t)[:2], (0, "st x\n"))
        self.assertEqual(self.json_entry({"_entry": {"argv": ["echo", "in"]}})[:2], (0, "in\n"))
        put(Path(self.t, "r.json"), {"_entry": "cfg.json#/tools/stamp"})
        self.assertEqual(run("--ws", self.t, "r.json", cwd=self.t)[:2], (0, "st\n"))

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
        self.json_entry({"argv": ["echo", "s"], "stdout": {"$env": "AOS_STACK", "$path": "out"}})
        self.assertEqual(Path(self.t, ".stack", "out").read_text(), "s\n")
        q = Path(self.t, "q").resolve()
        self.assertEqual(self.json_entry({"argv": ["echo", {"$env": "AOS_CD"}, {"$env": "AOS_CF"}]})[:2],
                         (0, "%s %s/_entry.json\n" % (q, q)))
        rc, _, err, stderr = self.json_entry({"argv": ["echo", {"$env": "AOS_NOPE_XYZ"}]})
        self.assertEqual((rc, err, "AOS_NOPE_XYZ" in stderr), (1, "單子跑不起來", True))

    def test_inst_timeout_kills_group(self):
        rc = self.json_entry({"argv": ["sh", "-c", "sleep 100 & echo $! > pid; wait"], "timeout_ms": 200})[0]
        pid = int(Path(self.t, "q", "pid").read_text())
        time.sleep(0.1)
        self.assertEqual((rc, alive(pid)), (143, False))

    def start(self, doc):
        put(Path(self.t, "q", "_entry.json"), doc)
        return subprocess.Popen([EXEC, "--ws", self.t, str(Path(self.t, "q"))], stdout=subprocess.PIPE, text=True,
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
        put(Path(self.t, "q", "_entry"), "{not json")
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "q")))[:3:2], (1, "入口壞"))
        os.remove(Path(self.t, "q", "_entry"))
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
