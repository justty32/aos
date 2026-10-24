"""test_sandbox - proto8/sandbox 的 aos-sandbox（身分 s6-setuidgid、上限 s6-softlimit、看得到什麼與連網 bwrap）。

設計：proto8/thinking/2026-10-24-sandbox.md。主角是「自我改進的被改函數讀不到判準檔」：同一支偷看判準的函數，
工作區沒 sandbox.json 時拿滿分（偷看得到）、有 sandbox.json 時零分（讀不到）。
要 bwrap（沒有整檔跳過）；s6 那幾支照 PATH 找，找不到再看試驗場 ~/code/try/sandbox/s6-root/bin（使用者自己編的，見紀錄），
都沒有就只跳過用到 s6 的幾個。身分那層用 `unshare --user --map-root-user --map-auto` 當假 root 試（同 proto6 帳號模組的測法），拿不到就跳過。"""
import json, os, shutil, socket, subprocess, tempfile, threading, time, unittest
from pathlib import Path

from aos_bins import ROOT, path_with  # noqa: E402

SANDBOX_BIN = str(ROOT / "sandbox" / "bin")
BOX = str(ROOT / "sandbox" / "bin" / "aos-sandbox")
SELF = str(ROOT / "demo" / "self-improve")
TRY_RUN = str(ROOT / "demo" / "self-improve" / "improver" / "tools" / "try_run" / "_entry")


def s6_dir():
    found = shutil.which("s6-softlimit")
    if found:
        return os.path.dirname(found)
    d = os.path.expanduser("~/code/try/sandbox/s6-root/bin")
    return d if os.path.exists(os.path.join(d, "s6-softlimit")) else None


S6 = s6_dir()
PATH = path_with(os.pathsep.join([SANDBOX_BIN] + ([S6] if S6 else []) + [os.environ.get("PATH", "")]))
HAS_BWRAP = shutil.which("bwrap") is not None and subprocess.run(
    ["bwrap", "--ro-bind", "/", "/", "--unshare-all", "true"], capture_output=True).returncode == 0
FAKE_ROOT = shutil.which("unshare") is not None and subprocess.run(
    ["unshare", "--user", "--map-root-user", "--map-auto", "true"], capture_output=True).returncode == 0


def env(**more):
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e["PATH"] = PATH
    e.update(more)
    return e


@unittest.skipUnless(HAS_BWRAP, "沒有 bwrap 或這台不給開 user namespace")
class SandboxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="test_sandbox."))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "judge").mkdir()
        (self.tmp / "judge" / "cases.json").write_text('[{"stdout": "SECRET"}]')
        (self.tmp / "fn").mkdir()

    def cfg(self, obj, name="box.json"):
        p = self.tmp / name
        p.write_text(json.dumps(obj))
        return str(p)

    def box(self, cfg, *prog, stdin="", **kw):
        return subprocess.run([BOX, cfg, *prog], input=stdin, capture_output=True, text=True,
                              env=env(), cwd=self.tmp, timeout=60, **kw)

    def dry(self, cfg):
        r = subprocess.run([BOX, "--dry-run", cfg, "true"], capture_output=True, text=True, env=env(), cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def assert_error(self, r, code):
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertRegex(r.stderr, r"^aos-sandbox: %s " % code)

    # ---- 看得到什麼
    def test_unlisted_path_is_invisible(self):
        secret = str(self.tmp / "judge" / "cases.json")
        self.assertEqual(subprocess.run(["cat", secret], capture_output=True, text=True).stdout, '[{"stdout": "SECRET"}]')
        r = self.box(self.cfg({"rw": ["fn"]}), "cat", secret)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("No such file", r.stderr)
        r = self.box(self.cfg({"rw": ["fn"]}), "ls", os.path.expanduser("~"))   # 家目錄整個看不到
        self.assertNotEqual(r.returncode, 0)

    def test_ro_and_rw(self):
        (self.tmp / "data").mkdir()
        (self.tmp / "data" / "in.txt").write_text("hello")
        c = self.cfg({"ro": ["data"], "rw": ["fn"]})
        r = self.box(c, "sh", "-c", "cat data/in.txt > fn/out.txt")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.tmp / "fn" / "out.txt").read_text(), "hello")
        r = self.box(c, "sh", "-c", "echo x > data/in.txt")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Read-only", r.stderr)
        self.assertEqual((self.tmp / "data" / "in.txt").read_text(), "hello")
        r = self.box(c, "touch", "/usr/x")
        self.assertIn("Read-only", r.stderr)

    def test_tmp_is_private(self):
        (Path(tempfile.gettempdir()) / ("sbx-%d" % os.getpid())).write_text("host")
        self.addCleanup(os.remove, Path(tempfile.gettempdir()) / ("sbx-%d" % os.getpid()))
        r = self.box(self.cfg({}), "ls", "-A", "/tmp")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    # ---- 網路
    def test_net_off_by_default_on_when_asked(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(4)
        self.addCleanup(srv.close)
        threading.Thread(target=lambda: [srv.accept() for _ in range(2)], daemon=True).start()
        code = "import socket; socket.create_connection(('127.0.0.1', %d), timeout=3); print('connected')" % srv.getsockname()[1]
        r = self.box(self.cfg({}), "python3", "-c", code)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("connected", r.stdout)
        r = self.box(self.cfg({"net": True}, "net.json"), "python3", "-c", code)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "connected"), r.stderr)

    # ---- 透明轉交
    def test_exit_code_stdin_stdout_pass_through(self):
        r = self.box(self.cfg({}), "sh", "-c", "tr a-z A-Z; exit 7", stdin="abc")
        self.assertEqual((r.returncode, r.stdout), (7, "ABC"))

    def test_commands_makes_aos_exec_runnable(self):
        (self.tmp / "fn" / "_entry").write_text("#!/bin/sh\necho in-box\n")
        (self.tmp / "fn" / "_entry").chmod(0o755)
        (self.tmp / "ws").mkdir()
        c = self.cfg({"commands": ["aos-exec"], "rw": ["fn", "ws"]})
        r = self.box(c, "aos-exec", "--ws", "ws", "fn")
        self.assertEqual((r.returncode, r.stdout), (0, "in-box\n"), r.stderr)
        r = self.box(self.cfg({"rw": ["fn", "ws"]}, "no.json"), "aos-exec", "--ws", "ws", "fn")
        self.assertNotEqual(r.returncode, 0)                 # 沒列 commands：沙箱裡沒有 aos-exec

    def test_timeout_kills_whole_group_through_box(self):
        """單子的 timeout_ms 照樣打得到沙箱裡的程式（不 --new-session，同一個行程群組）。"""
        mark = "sbx-sleep-%d" % os.getpid()
        (self.tmp / "inst.json").write_text(json.dumps(
            {"argv": ["aos-sandbox", "box.json", "sh", "-c", "exec -a %s sleep 30" % mark], "timeout_ms": 500}))
        self.cfg({})
        t0 = time.time()
        r = subprocess.run(["aos-exec", "inst.json"], capture_output=True, text=True, env=env(), cwd=self.tmp, timeout=30)
        self.assertLess(time.time() - t0, 10)
        self.assertEqual(r.returncode, 143, r.stderr)
        time.sleep(0.3)
        self.assertEqual(subprocess.run(["pgrep", "-f", mark], capture_output=True).returncode, 1)   # 沒留孤兒

    def test_env_default_whitelist(self):
        """設定沒寫 env＝只帶 PATH、語系、aos 的六個（10-24）：外面的 key 不跟著進去；寫了 env＝只帶那幾個。"""
        prog = 'echo "${SBX_KEY-none}|${AOS_WS-none}|${LANG-none}"'
        r = subprocess.run([BOX, self.cfg({}), "sh", "-c", prog], capture_output=True, text=True, cwd=self.tmp,
                           env=env(SBX_KEY="leaked", AOS_WS="/w", LANG="C.UTF-8"))
        self.assertEqual((r.returncode, r.stdout), (0, "none|/w|C.UTF-8\n"), r.stderr)
        r = subprocess.run([BOX, self.cfg({"env": ["PATH", "SBX_KEY"]}, "e.json"), "sh", "-c", prog], capture_output=True,
                           text=True, cwd=self.tmp, env=env(SBX_KEY="leaked", AOS_WS="/w", LANG="C.UTF-8"))
        self.assertEqual((r.returncode, r.stdout), (0, "leaked|none|none\n"), r.stderr)

    # ---- 設定檔與錯
    def test_pointer_and_env_directive(self):
        (self.tmp / "_metainfo").write_text(json.dumps({"summary": "x", "sandbox": {"rw": [{"$env": "BOXDIR", "$path": "/fn"}]}}))
        r = subprocess.run([BOX, "--dry-run", "_metainfo#/sandbox", "true"], capture_output=True, text=True,
                           env=env(BOXDIR=str(self.tmp)), cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(str(self.tmp / "fn"), json.loads(r.stdout))

    def test_errors(self):
        self.assert_error(subprocess.run([BOX, "--nope", "a", "b"], capture_output=True, text=True, env=env()), "FlagUnknown")
        self.assert_error(subprocess.run([BOX, "a"], capture_output=True, text=True, env=env()), "ArgumentsBad")
        self.assert_error(self.box(str(self.tmp / "none.json"), "true"), "CfgMissing")
        self.assert_error(self.box(self.cfg([1], "arr.json"), "true"), "CfgBad")
        self.assert_error(self.box(self.cfg({"net": "no"}, "b1.json"), "true"), "CfgBad")
        self.assert_error(self.box(self.cfg({"mem_mb": 0}, "b2.json"), "true"), "CfgBad")
        self.assert_error(self.box(self.cfg({"rw": [{"$env": "NOPE_NOT_SET"}]}, "b3.json"), "true"), "CfgBad")
        self.assert_error(self.box(self.cfg({"rw": ["nope"]}, "b4.json"), "true"), "PathMissing")
        self.assert_error(self.box(self.cfg({"commands": ["no-such-cmd-x"]}, "b5.json"), "true"), "CommandMissing")
        self.assert_error(self.box(self.cfg({"x": 1}, "b6.json") + "#/nope", "true"), "CfgMissing")
        if os.geteuid() != 0:
            self.assert_error(self.box(self.cfg({"user": "nobody"}, "b7.json"), "true"), "UserBad")

    def test_dry_run_chain_order(self):
        chain = self.dry(self.cfg({"user": "aos-run", "mem_mb": 64, "cpu_s": 2, "net": True}))
        names = [os.path.basename(a) for a in chain]
        self.assertEqual(names[0], "s6-softlimit")
        mb64 = str(64 * 1024 * 1024)
        self.assertEqual(chain[1:7], ["-a", mb64, "-d", mb64, "-t", "2"])
        self.assertLess(names.index("s6-setuidgid"), names.index("bwrap"))   # 先換身分、再開 namespace
        self.assertIn("--share-net", chain)
        self.assertNotIn("--new-session", chain)
        self.assertNotIn("--share-net", self.dry(self.cfg({}, "plain.json")))

    # ---- s6 那層
    @unittest.skipUnless(S6, "沒有 s6-softlimit")
    def test_softlimit_mem_and_cpu(self):
        r = self.box(self.cfg({"mem_mb": 100}), "python3", "-c", "x = bytearray(400 * 1024 * 1024)")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("MemoryError", r.stderr)
        fn = self.tmp / "fn" / "_entry"                  # 有上限時 aos-exec 照樣跑得起來（-m 連堆疊一起限，開執行緒就 EAGAIN）
        fn.write_text(json.dumps({"argv": ["python3", "-c", "print('ran')"]}))   # 單子形的入口（10-24 撞到的就是這種）
        r = self.box(self.cfg({"mem_mb": 1024, "commands": ["aos-exec"], "rw": [str(self.tmp)]}, "mem2.json"),
                     "aos-exec", "--ws", str(self.tmp), str(self.tmp / "fn"))
        self.assertEqual((r.returncode, r.stdout), (0, "ran\n"), r.stderr)
        t0 = time.time()
        r = self.box(self.cfg({"cpu_s": 1}, "cpu.json"), "python3", "-c", "while True: pass")
        self.assertEqual(r.returncode, 128 + 24)        # SIGXCPU
        self.assertLess(time.time() - t0, 20)

    @unittest.skipUnless(S6 and FAKE_ROOT, "沒有 s6 或拿不到 unshare --map-auto 的假 root")
    def test_identity_layer_in_fake_root(self):
        """假 root（namespace 裡的 0＝我自己）裡把判準設成只有擁有者能讀：不換身分讀得到，換成 1001 就讀不到——就算路徑綁進來了。"""
        d = Path(tempfile.mkdtemp(prefix="sbx-id."))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        d.chmod(0o755)
        (d / "secret.txt").write_text("SECRET")
        (d / "secret.txt").chmod(0o600)
        (d / "same.json").write_text(json.dumps({"ro": [str(d)]}))
        (d / "other.json").write_text(json.dumps({"ro": [str(d)], "user": "1001:1001"}))
        run = lambda c: subprocess.run(["unshare", "--user", "--map-root-user", "--map-auto", BOX, str(d / c),
                                        "sh", "-c", "id -u; cat %s" % (d / "secret.txt")],
                                       capture_output=True, text=True, env=env(), timeout=60)
        r = run("same.json")
        self.assertEqual((r.returncode, r.stdout), (0, "0\nSECRET"), r.stderr)
        r = run("other.json")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "1001\n")
        self.assertIn("Permission denied", r.stderr)


@unittest.skipUnless(HAS_BWRAP, "沒有 bwrap 或這台不給開 user namespace")
class BashBoxedTest(unittest.TestCase):
    """sandbox/examples/bash-boxed：lib/base 的 bash 原封不動、外面包一層 aos-sandbox——寫得進工作區、出不去、連不了網。"""

    def test_bash_tool_boxed(self):
        root = Path(tempfile.mkdtemp(prefix="test_sandbox_bash."))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "ws").mkdir()
        (root / "outside.txt").write_text("outside")
        cmd = ("echo made > f.txt; cat %s || echo no-outside; "
               "python3 -c \"import socket; socket.create_connection(('127.0.0.1', 9), timeout=2)\" 2>&1 | tail -1"
               % (root / "outside.txt"))
        r = subprocess.run(["aos-exec", "--ws", str(root / "ws"), str(ROOT / "sandbox" / "examples" / "bash-boxed")],
                           input=json.dumps({"command": cmd}), capture_output=True, text=True, env=env(), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((root / "ws" / "f.txt").read_text(), "made\n")
        self.assertIn("no-outside", r.stdout)
        self.assertNotIn("outside\n", r.stdout.replace("no-outside", ""))
        self.assertRegex(r.stdout, r"Network is unreachable|Connection refused")


CHEAT = """#!/usr/bin/env python3
# 偷看判準的函數：照 stdin 去判準檔裡找答案
import json, sys
s = sys.stdin.read()
try:
    cases = json.load(open(%r))
except OSError:
    print("看不到判準"); sys.exit(0)
print(next((c["stdout"] for c in cases if c.get("stdin") == s), ""), end="")
"""


@unittest.skipUnless(HAS_BWRAP, "沒有 bwrap 或這台不給開 user namespace")
class SelfImproveSandboxTest(unittest.TestCase):
    """自我改進的被改函數：原本讀得到判準檔（偷看拿滿分），工作區放了 sandbox.json 就讀不到（零分）。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="test_sandbox_si."))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.ws = self.root / "ws"
        (self.ws / "judge").mkdir(parents=True)
        (self.ws / "target").mkdir()
        cases = [{"stdin": "a", "stdout": "ANSWER-A"}, {"stdin": "b", "stdout": "ANSWER-B", "hidden": True}]
        (self.ws / "judge" / "cases.json").write_text(json.dumps(cases))
        (self.ws / "goal.txt").write_text("把 a 變成 ANSWER-A")
        (self.ws / "budget.json").write_text('{"rounds": 0}')            # 只判原版、不改進（不用腦）
        entry = self.ws / "target" / "_entry"
        entry.write_text(CHEAT % str(self.ws / "judge" / "cases.json"))
        entry.chmod(0o755)

    def run_self_improve(self):
        stack = self.root / "stack"
        r = subprocess.run(["aos-exec", "--ws", str(self.ws), SELF], capture_output=True, text=True, timeout=120,
                           env=env(AOS_STACK=str(stack) + "/"))
        verdict = json.loads((stack / "versions" / "v000" / "verdict.json").read_text())
        return r, verdict

    def test_sandbox_false_function_reads_judge(self):
        (self.ws / "sandbox.json").write_text("false")                 # 明寫不關
        r, v = self.run_self_improve()
        self.assertEqual(r.returncode, 0, r.stderr)                     # 偷看就「達成」了
        self.assertEqual((v["score"], v["total"], v["passed"]), (2, 2, True))

    def test_default_boxes_function(self):
        """工作區沒放 sandbox.json＝用 demo/self-improve/sandbox.json 關（10-24 定：預設就關）；外面的 key 也帶不進去。"""
        entry = self.ws / "target" / "_entry"
        entry.write_text((CHEAT % str(self.ws / "judge" / "cases.json")).replace(
            "import json, sys\n", "import json, os, sys\nprint('key=' + os.environ.get('SI_TEST_KEY', 'none'), file=sys.stderr)\n"))
        r = subprocess.run(["aos-exec", "--ws", str(self.ws), SELF], capture_output=True, text=True, timeout=120,
                           env=env(AOS_STACK=str(self.root / "stack") + "/", SI_TEST_KEY="leaked"))
        self.assertEqual(r.returncode, 2, r.stderr)
        runs = [json.loads(x) for x in (self.root / "stack" / "versions" / "v000" / "runs.jsonl").read_text().splitlines()]
        self.assertEqual([x["stdout"] for x in runs], ["看不到判準\n", "看不到判準\n"])
        self.assertTrue(all("key=none" in x["stderr"] for x in runs), runs)

    def test_default_without_bwrap_stops(self):
        """預設要關卻沒有 bwrap：停下說 SandboxMissing，不靜靜改成不關。"""
        stack = self.root / "stack"
        bare = self.root / "bin"
        bare.mkdir()
        for name in ("aos-exec", "aos-loop", "aos-fsm", "python3", "aos-sandbox"):
            os.symlink(shutil.which(name, path=PATH), bare / name)
        r = subprocess.run(["aos-exec", "--ws", str(self.ws), SELF], capture_output=True, text=True, timeout=120,
                           env=env(AOS_STACK=str(stack) + "/", PATH=str(bare)))
        self.assertEqual(r.returncode, 1)
        self.assertIn("self-improve: SandboxMissing", r.stderr)

    def test_with_sandbox_function_cannot_read_judge(self):
        (self.ws / "sandbox.json").write_text(json.dumps(
            {"commands": ["aos-exec"], "rw": [{"$env": "IMPROVE_RUN"}], "net": False}))
        r, v = self.run_self_improve()
        self.assertEqual(r.returncode, 2, r.stderr)                     # 沒達成、預算 0 輪用完
        self.assertEqual((v["score"], v["passed"]), (0, False))
        runs = [json.loads(x) for x in (self.root / "stack" / "versions" / "v000" / "runs.jsonl").read_text().splitlines()]
        self.assertEqual([x["stdout"] for x in runs], ["看不到判準\n", "看不到判準\n"])

    def test_try_run_is_boxed_too(self):
        """改進者的 try_run 也照 IMPROVE_SANDBOX 關：同一支函數在 try_run 裡也讀不到判準。"""
        iws = self.root / "iws"
        shutil.copytree(self.ws / "target", iws / "target")
        call = lambda e: subprocess.run([TRY_RUN], input='{"stdin": "a"}', capture_output=True, text=True,
                                        env=env(AOS_WS=str(iws), **e), timeout=60)
        self.assertIn("ANSWER-A", call({}).stdout)
        box = self.root / "box.json"
        box.write_text(json.dumps({"commands": ["aos-exec"], "rw": [{"$env": "IMPROVE_RUN"}]}))
        out = call({"IMPROVE_SANDBOX": str(box)}).stdout
        self.assertIn("看不到判準", out)
        self.assertNotIn("ANSWER-A", out)


FORGE = """import json, os, sys
mb, ticks, secret = os.environ["AOS_KERNEL"], sys.argv[1], sys.argv[2]
lid = "%020d.1.%s" % (1, ticks)                      # 冒充 pid 1（外面的 init）：kernel 看信號以為寄信的人還在
os.makedirs(os.path.join(mb, "tmp", lid))
json.dump({"inst": {"argv": ["cat", secret], "cwd": "/"}, "env": {"PATH": "/usr/bin:/bin"}},
          open(os.path.join(mb, "tmp", lid, "letter.json"), "w"))
os.rename(os.path.join(mb, "tmp", lid), os.path.join(mb, "new", lid))
print("posted")
"""


@unittest.skipUnless(HAS_BWRAP, "沒有 bwrap 或這台不給開 user namespace")
class KernelMailboxTest(unittest.TestCase):
    """10-24 堵 kernel 信箱後門：關在沙箱裡的程式寄「單子＝cat 判準」給沙箱外的 kernel——預設看不到信箱、寄不出去；
    明寫 kernel: true 才寄得到，這時要靠 kernel.json 的 accept 擋（不在名單＝InstUnknown、不跑）。"""

    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="test_sandbox_kernel."))
        self.addCleanup(shutil.rmtree, self.t, ignore_errors=True)
        self.mb, self.stack, self.ws = self.t / "mb", self.t / "stack", self.t / "ws"
        for d in (self.stack, self.ws, *(self.mb / b for b in ("tmp", "new", "cur", "done"))):
            d.mkdir(parents=True)
        self.secret = self.t / "judge.json"
        self.secret.write_text("SECRET-JUDGE")
        (self.ws / "cat.json").write_text(json.dumps({"argv": ["cat", str(self.secret)]}))

    def cfg(self, obj, name="box.json"):
        p = self.t / name
        p.write_text(json.dumps(obj))
        return str(p)

    def box(self, cfg, *prog):
        return subprocess.run([BOX, cfg, *prog], capture_output=True, text=True, timeout=60,
                              env=env(AOS_KERNEL=str(self.mb)), cwd=self.t)

    def kernel(self, doc):
        (self.t / "kernel.json").write_text(json.dumps(dict(doc, mailbox=str(self.mb))))
        r = subprocess.run(["aos-kernel-llm", "kernel.json"], capture_output=True, text=True, timeout=60,
                           env=env(AOS_STACK=str(self.stack)), cwd=self.t)
        self.assertEqual(r.returncode, 0, r.stderr)

    def leaked(self):
        return any("SECRET-JUDGE" in p.read_text(errors="replace") for p in self.mb.rglob("*") if p.is_file())

    def test_default_box_cannot_reach_kernel(self):
        prog = ("echo \"kernel=${AOS_KERNEL-unset}\"; aos-gate ws/cat.json; "
                "mkdir %s/new/x && echo wrote" % self.mb)
        r = self.box(self.cfg({"commands": ["aos-gate"], "rw": ["ws"]}), "sh", "-c", prog)
        self.assertIn("kernel=unset", r.stdout)                         # AOS_KERNEL 不帶進去
        self.assertIn("aos-gate: MailboxMissing", r.stderr)
        self.assertNotIn("wrote", r.stdout)                             # 直接寫信箱也寫不到（沒綁進來）
        self.kernel({})
        self.assertEqual(list((self.mb / "done").iterdir()), [])
        self.assertFalse((self.stack / "served.jsonl").exists())
        self.assertFalse(self.leaked())

    def test_bound_path_covering_mailbox_is_cfg_bad(self):
        for c in ({"rw": [str(self.t)]}, {"ro": [str(self.mb / "new")]}, {"env": ["PATH", "AOS_KERNEL"]}):
            r = self.box(self.cfg(c, "cover.json"), "true")
            self.assertEqual(r.returncode, 1, (c, r.stderr))
            self.assertRegex(r.stderr, r"^aos-sandbox: CfgBad .*kernel: true")

    def test_kernel_true_needs_accept(self):
        """kernel: true＝信箱寫得到，冒充寄信的人很容易（信號只是 pid＋啟動時間）；kernel 沒 accept 就照跑 cat 判準，有 accept 就 InstUnknown。"""
        ticks = Path("/proc/1/stat").read_text().rpartition(")")[2].split()[19]
        c = self.cfg({"rw": ["ws"], "kernel": True})
        r = self.box(c, "python3", "-c", FORGE, ticks, str(self.secret))
        self.assertEqual((r.returncode, r.stdout), (0, "posted\n"), r.stderr)
        self.kernel({"accept": [{"argv": ["python3", "brain.py"], "cwd": str(self.ws)}]})
        (lid,) = os.listdir(self.mb / "done")
        self.assertEqual(json.loads((self.mb / "done" / lid / "reply.json").read_text())["error"]["code"], "InstUnknown")
        self.assertFalse(self.leaked())
        shutil.rmtree(self.mb / "done" / lid)
        r = self.box(c, "python3", "-c", FORGE, ticks, str(self.secret))   # 對照：kernel 沒 accept＝後門真的在
        self.kernel({})
        self.assertTrue(self.leaked())


if __name__ == "__main__":
    unittest.main()
