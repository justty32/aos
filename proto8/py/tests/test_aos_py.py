"""test_aos_py - 入口 aos.py 的通用代理（不起 daemon）：細則表逐列翻成哪條 argv（用一支假的 aos-agent／aos-daemon-ctl 把 argv 印回來）、遙控器頂層照 aos-agent 子指令表擋錯、json=True 的整份／JSONL／空、Text 與 None、Failed 的欄位、echo 印在 stderr、repr 不跑指令、轉匯出 defs／std、import 入口不先載入別的。"""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

PROTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROTO / "py"))

# 假指令：stdout 印出自己的 argv（JSON），或 FAKE_OUT；FAKE_FAIL＝印一行錯誤、退 1
FAKE = """#!%s
import json, os, sys
if os.environ.get("FAKE_FAIL"):
    sys.stderr.write("some noise\\n" + os.path.basename(sys.argv[0]) + ": error: " + os.environ["FAKE_FAIL"] + "\\n")
    sys.exit(1)
sys.stdout.write(os.environ["FAKE_OUT"] if "FAKE_OUT" in os.environ else json.dumps(sys.argv[1:]) + "\\n")
""" % sys.executable


class Proxy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="aos-py-"))
        for name in ("aos-agent", "aos-daemon-ctl"):
            (cls.tmp / name).write_text(FAKE)
            (cls.tmp / name).chmod(0o755)
        cls.old_path = os.environ["PATH"]
        os.environ["PATH"] = str(cls.tmp) + os.pathsep + cls.old_path

    @classmethod
    def tearDownClass(cls):
        os.environ["PATH"] = cls.old_path
        for p in cls.tmp.iterdir():
            p.unlink()
        cls.tmp.rmdir()

    def setUp(self):
        for k in ("FAKE_OUT", "FAKE_FAIL"):
            os.environ.pop(k, None)
        from aos.py import agent
        self.agent = agent
        self.a = agent.attach("ann", daemon="/d/.stack")

    def argv(self, out):
        return json.loads(out)

    def test_rows_of_the_table(self):
        a = self.a
        head = ["--daemon", "/d/.stack", "--target", "ann"]
        cases = [
            (lambda: a.ctl.stop(), ["ctl", "stop"]),
            (lambda: a.ctl.set_def("x"), ["ctl", "set-def", "x"]),
            (lambda: a.history.ls(3), ["history", "ls", "3"]),
            (lambda: a.tools.add("lib/t", no_cache=True), ["tools", "add", "--no-cache", "lib/t"]),
            (lambda: a.ctl.ls(j=True), ["ctl", "ls", "-j"]),
            (lambda: a.listen(timeout_s=20, letter=None), ["listen", "--timeout-s", "20"]),
            (lambda: a.hook.add(event="before_tool", replace=False, w="."), ["hook", "add", "--event", "before_tool", "-w", "."]),
            (lambda: a.hook.add(path_json={"$env": "AOS_HOME", "$path": "/x"}), ["hook", "add", "--path-json", '{"$env": "AOS_HOME", "$path": "/x"}']),
            (lambda: a.ctl.add("agents/bob", envs=["A=1", "B=2"]), ["ctl", "add", "--envs", "A=1", "--envs", "B=2", "agents/bob"]),
            (lambda: a.system.set(from_="me"), ["system", "set", "--from", "me"]),
            (lambda: a.goal.set("-x", "y"), ["goal", "set", "--", "-x", "y"]),
            (lambda: a.llm.set({"model": "fake"}, 2), ["llm", "set", '{"model": "fake"}', "2"]),
            (lambda: a("peek", "/status"), ["peek", "/status"]),
        ]
        for f, want in cases:
            with self.subTest(want=want):
                self.assertEqual(self.argv(f()), head + want)

    def test_say_returns_the_letter_name_and_is_the_same_function(self):
        os.environ["FAKE_OUT"] = "ann-20261119-1\n"
        self.assertEqual(self.a.say("hi"), "ann-20261119-1")
        self.assertIs(type(self.a.say("hi")), str)
        self.assertEqual(self.agent.say("hi", target="ann", daemon="/d/.stack"), self.a.say("hi"))
        os.environ.pop("FAKE_OUT")
        self.assertEqual(self.argv(self.a.say("-h")),["--daemon", "/d/.stack", "--target", "ann", "say", "--", "-h"])

    def test_module_level_pointing_flags_go_first(self):
        agent = self.agent
        self.assertEqual(self.argv(agent.ctl.ls()), ["ctl", "ls"])                 # daemon 不給：庫什麼都不加
        self.assertEqual(self.argv(agent.ctl.rm("ann", daemon="/d")), ["--daemon", "/d", "ctl", "rm", "ann"])
        self.assertEqual(self.argv(agent.history.ls(target="bob")), ["--target", "bob", "history", "ls"])
        b = agent.attach("bob")
        self.assertEqual(self.argv(b.ctl.state()), ["--target", "bob", "ctl", "state"])
        self.assertEqual(repr(b), "<aos-agent --target bob>")

    def test_returns(self):
        os.environ["FAKE_OUT"] = '{"a": 1}\n'
        self.assertEqual(self.a.ctl.state(json=True), {"a": 1})
        os.environ["FAKE_OUT"] = '{"a": 1}\n{"a": 2}\n'
        self.assertEqual(self.a.history.ls(json=True), [{"a": 1}, {"a": 2}])
        os.environ["FAKE_OUT"] = "\n"
        self.assertIsNone(self.a.history.ls(json=True))
        self.assertIsNone(self.a.ctl.stop())
        os.environ["FAKE_OUT"] = "one\ttwo\n"
        out = self.a.tools.ls()
        self.assertIsInstance(out, str)
        self.assertEqual(repr(out), "one\ttwo")                                       # REPL 印出來跟 shell 一樣
        os.environ["FAKE_OUT"] = "not json\n"
        from aos.py import Failed
        with self.assertRaises(Failed) as e:
            self.a.tools.ls(json=True)
        self.assertEqual(e.exception.code, "JsonBad")
        os.environ["FAKE_OUT"] = "[]\n"
        self.assertEqual(self.a.tools.ls(json=True), [])

    def test_json_flag_is_added(self):
        os.environ["FAKE_OUT"] = "{}\n"
        from aos.py import _shell
        self.assertEqual(_shell.argv_of("aos-agent", [], ["ctl", "state"], ("who",), {"json": True}),
                         ["aos-agent", "ctl", "state", "--json", "who"])

    def test_failed_fields(self):
        from aos.py import Failed
        os.environ["FAKE_FAIL"] = "TargetMissing no agent ann"
        with self.assertRaises(Failed) as e:
            self.a.ctl.stop()
        x = e.exception
        self.assertEqual(str(x), "aos-agent: error: TargetMissing no agent ann")
        self.assertEqual((x.program, x.code, x.reason, x.exit), ("aos-agent", "TargetMissing", "no agent ann", 1))
        self.assertEqual(x.argv[-2:], ["ctl", "stop"])
        os.environ.pop("FAKE_FAIL")
        with self.assertRaises(Failed) as e:
            from aos.py import _shell
            _shell.call(["/no/such/aos-thing"])
        self.assertEqual(e.exception.code, "CommandMissing")
        from aos.py import Timeout
        self.assertTrue(issubclass(Timeout, TimeoutError) and issubclass(Timeout, Failed))

    def test_top_level_names_follow_the_subcommand_table(self):
        from aos.apps.agent import SUBS
        a = self.a
        for name in ("resume", "where", "history_x", "breakpoint"):
            with self.subTest(name=name):
                with self.assertRaises(AttributeError):
                    getattr(a, name)
        with self.assertRaises(AttributeError):
            a._secret
        self.assertFalse(hasattr(a, "__wrapped__"))
        for name in SUBS:
            self.assertTrue(hasattr(a, name), name)
        self.assertTrue({"bp", "look", "say", "ctl", "stack"} <= set(dir(a)))
        with self.assertRaises(AttributeError):
            self.agent.resume
        from aos.py import daemon_ctl
        with self.assertRaises(AttributeError):
            daemon_ctl.attach(".stack").bogus
        with self.assertRaises(AttributeError):
            daemon_ctl.bogus

    def test_repr_runs_nothing(self):
        os.environ["FAKE_FAIL"] = "Boom would have run"
        self.assertEqual(repr(self.a), "<aos-agent --daemon /d/.stack --target ann>")
        self.assertEqual(repr(self.a.ctl.set_def), "<aos-agent --daemon /d/.stack --target ann ctl set-def>")

    def test_attach_gives_an_attached(self):
        """遙控器的類別叫 Attached（11-21 從 Agent 改名，跟 defs.Agent 分開；不留舊名）。"""
        self.assertIs(type(self.a), self.agent.Attached)
        self.assertFalse(hasattr(self.agent, "Agent"))

    def test_daemon_ctl(self):
        from aos.py import daemon_ctl
        self.assertEqual(self.argv(daemon_ctl.ls(j=True)), ["ls", "-j"])
        self.assertEqual(self.argv(daemon_ctl.shutdown(daemon="/d", timeout_s=5)), ["--daemon", "/d", "shutdown", "--timeout-s", "5"])
        d = daemon_ctl.attach("/d")
        self.assertEqual(self.argv(d.rm("ann")), ["--daemon", "/d", "rm", "ann"])
        self.assertEqual(repr(d.sweep), "<aos-daemon-ctl --daemon /d sweep>")

    def test_echo_goes_to_stderr(self):
        import aos.py
        err = io.StringIO()
        try:
            aos.py.echo = True
            with redirect_stderr(err):
                self.a.ctl.stop()
        finally:
            aos.py.echo = False
        self.assertEqual(err.getvalue(), "$ aos-agent --daemon /d/.stack --target ann ctl stop\n")
        err = io.StringIO()
        with redirect_stderr(err):
            self.a.ctl.stop()
        self.assertEqual(err.getvalue(), "")


class Entry(unittest.TestCase):
    def run_py(self, code):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env["PYTHONPATH"] = str(PROTO / "py")
        return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30)

    def test_import_loads_nothing_else(self):
        r = self.run_py("import sys, aos.py; from aos.py import agent, daemon_ctl, Failed; "
                        "print(sorted(m for m in sys.modules if m.startswith('aos.') and m not in ('aos.py', 'aos.py._shell', 'aos.py.agent', 'aos.py.daemon_ctl')))")
        self.assertEqual((r.returncode, r.stdout), (0, "[]\n"), r.stderr)

    def test_defs_and_std(self):
        r = self.run_py("import aos.agent_spec as s, aos.agent_spec_lib as l\n"
                        "from aos.py.agent import defs\nfrom aos.py import agent, std\n"
                        "print(defs is s, agent.defs is s, std is l.std, defs.std is std, callable(defs.main), callable(agent.defs.lib))")
        self.assertEqual((r.returncode, r.stdout), (0, "True True True True True True\n"), r.stderr)
        r = self.run_py("from aos.py import ag")
        self.assertIn("ImportError", r.stderr)                                       # 入口頂層不轉出 ag

    def test_flags_take_double_dash(self):
        """位置參數以 - 開頭時代理先放 --：aos.flags 認得（在任何位置參數前的 -- 丟掉、後面照原樣）。"""
        from aos import flags
        opts, rest = flags.parse(["--", "-h", "x"], {"--timeout-s": "t"}, anywhere=True)
        self.assertEqual((opts, rest), ({}, ["-h", "x"]))


if __name__ == "__main__":
    unittest.main()
