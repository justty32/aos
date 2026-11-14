# test_scope - unittest for scope.py: write_scope(env) from AOS_WS / AOS_WRITE_ALLOW / the deny sources, and its CLI.
import json, os, subprocess, sys, tempfile, unittest

sys.dont_write_bytecode = True   # importing scope.py must not leave __pycache__ next to it

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.dirname(HERE)
SCOPE = os.path.join(DIR, "scope.py")
sys.path.insert(0, DIR)
import scope   # noqa: E402
sys.path.pop(0)


class Scope(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.t = os.path.realpath(self.tmp.name)
        self.ws = os.path.join(t, "ws")
        self.home = os.path.join(t, "home")
        self.daemon = os.path.join(t, "d")
        self.stack = os.path.join(self.daemon, "procs", "w-01")
        self.defdir = os.path.join(t, "defs", "w")
        for d in (self.ws, self.home, self.stack, self.defdir, os.path.join(t, "extra")):
            os.makedirs(d)
        self.env = {"AOS_WS": self.ws, "HOME": self.home}

    def tearDown(self):
        self.tmp.cleanup()

    def cfg(self, data):
        p = os.path.join(self.t, "guard.json")
        with open(p, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        self.env["AOS_GUARD_CFG"] = p
        return p

    def test_only_ws(self):
        self.assertEqual(scope.write_scope(self.env), {"allow": [{"path": self.ws, "from": "AOS_WS"}], "deny": []})

    def test_allow_entries(self):
        os.makedirs(os.path.join(self.home, "h"))
        self.env["AOS_WRITE_ALLOW"] = os.pathsep.join([os.path.join(self.t, "extra"), "", "~/h", "../extra/sub", "~"])
        got = scope.write_scope(self.env)["allow"]
        self.assertEqual(got, [{"path": self.ws, "from": "AOS_WS"},
                               {"path": os.path.join(self.t, "extra"), "from": "AOS_WRITE_ALLOW"},
                               {"path": os.path.join(self.home, "h"), "from": "AOS_WRITE_ALLOW"},
                               {"path": os.path.join(self.t, "extra", "sub"), "from": "AOS_WRITE_ALLOW"},
                               {"path": self.home, "from": "AOS_WRITE_ALLOW"}])

    def test_tilde_user_not_expanded(self):
        self.env["AOS_WRITE_ALLOW"] = "~nobody/x"
        self.assertEqual(scope.write_scope(self.env)["allow"][1]["path"], os.path.join(self.ws, "~nobody", "x"))

    def test_symlink_resolved(self):
        link = os.path.join(self.t, "link")
        os.symlink(os.path.join(self.t, "extra"), link)
        self.env["AOS_WRITE_ALLOW"] = link
        self.assertEqual(scope.write_scope(self.env)["allow"][1]["path"], os.path.join(self.t, "extra"))

    def test_deny_sources_in_order(self):
        self.env.update(AOS_STACK=os.path.join(self.stack, "hooks", "guard") + "/", AOS_CD=os.path.join(self.t, "cd"),
                        AOS_DAEMON=self.daemon, AOS_WRITE_DENY=os.pathsep.join(["secret", "~/s"]))
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs": {"w-01": {"stack": "procs/w-01", "def": self.defdir}}}, f)
        self.cfg({"deny_roots": ["cfgdeny", 3, ""]})
        self.assertEqual(scope.write_scope(self.env)["deny"], [
            {"path": self.stack, "from": "AOS_STACK"},
            {"path": os.path.join(self.t, "cd"), "from": "AOS_CD"},
            {"path": self.defdir, "from": "definition"},
            {"path": os.path.join(self.ws, "secret"), "from": "AOS_WRITE_DENY"},
            {"path": os.path.join(self.home, "s"), "from": "AOS_WRITE_DENY"},
            {"path": os.path.join(self.ws, "cfgdeny"), "from": "guard.json"}])

    def test_tool_cell_stripped(self):
        self.env["AOS_STACK"] = os.path.join(self.stack, "tools", "shell")
        self.assertEqual(scope.write_scope(self.env)["deny"], [{"path": self.stack, "from": "AOS_STACK"}])

    def test_plain_stack_kept(self):
        self.env["AOS_STACK"] = self.stack
        self.assertEqual(scope.own_stack(self.env), self.stack)

    def test_definition_deepest_row(self):
        inner = os.path.join(self.stack, "sub")
        os.makedirs(inner)
        other = os.path.join(self.t, "defs", "inner")
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs": {"w-01": {"stack": "procs/w-01", "def": self.defdir},
                                 "w-sub": {"stack": "procs/w-01/sub", "def": other}, "x": "junk"}}, f)
        self.env.update(AOS_DAEMON=self.daemon, AOS_STACK=inner)
        self.assertEqual(scope.definition(self.env), other)
        self.env["AOS_STACK"] = self.stack
        self.assertEqual(scope.definition(self.env), self.defdir)

    def test_definition_skipped(self):
        self.env.update(AOS_STACK=self.stack)
        self.assertIsNone(scope.definition(self.env))                              # no daemon
        self.env["AOS_DAEMON"] = self.daemon
        self.assertIsNone(scope.definition(self.env))                              # no table
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs": {"w-01": {"stack": "procs/w-01"}}}, f)
        self.assertIsNone(scope.definition(self.env))                              # row without def
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs": {"w-01": {"stack": "procs/w-01", "def": self.defdir}}}, f)
        self.assertEqual(scope.definition(self.env), self.defdir)
        self.env["AOS_KERNEL"] = os.path.join(self.t, "k")
        self.assertIsNone(scope.definition(self.env))                              # table only by letter

    def test_errors(self):
        with self.assertRaises(scope.ScopeError) as c:
            scope.write_scope({"HOME": self.home})
        self.assertEqual(c.exception.code, "WsMissing")
        self.cfg({"write_roots": ["/x"]})
        with self.assertRaises(scope.ScopeError) as c:
            scope.write_scope(self.env)
        self.assertEqual(c.exception.code, "CfgBad")
        self.assertIn("AOS_WRITE_ALLOW", c.exception.why)
        for bad in ("{x", "[]", {"deny_roots": "x"}):
            self.cfg(bad)
            with self.assertRaises(scope.ScopeError):
                scope.write_scope(self.env)
        self.env["AOS_GUARD_CFG"] = os.path.join(self.t, "missing.json")
        with self.assertRaises(scope.ScopeError) as c:
            scope.write_scope(self.env)
        self.assertEqual(c.exception.code, "CfgMissing")
        self.assertNotIn("missing.json", c.exception.why)   # the variable is named, its value is not printed

    def test_default_env_is_os_environ(self):
        old = dict(os.environ)
        try:
            for k in [k for k in os.environ if k.startswith("AOS_")]:
                del os.environ[k]
            os.environ["AOS_WS"] = self.ws
            self.assertEqual(scope.write_scope()["allow"], [{"path": self.ws, "from": "AOS_WS"}])
        finally:
            os.environ.clear()
            os.environ.update(old)


class Cli(unittest.TestCase):
    def run_cli(self, args, env):
        base = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        base.update(env)
        return subprocess.run([sys.executable, SCOPE] + args, capture_output=True, text=True, env=base, timeout=30)

    def test_prints_json(self):
        with tempfile.TemporaryDirectory() as t:
            t = os.path.realpath(t)
            p = self.run_cli([], {"AOS_WS": t, "AOS_WRITE_DENY": os.path.join(t, "x")})
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(p.stdout), {"allow": [{"path": t, "from": "AOS_WS"}],
                                                    "deny": [{"path": os.path.join(t, "x"), "from": "AOS_WRITE_DENY"}]})

    def test_error_line(self):
        p = self.run_cli([], {})
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stdout, "")
        self.assertTrue(p.stderr.startswith("scope: error: WsMissing "), p.stderr)

    def test_help_and_bad_args(self):
        p = self.run_cli(["--help"], {})
        self.assertEqual(p.returncode, 0)
        self.assertIn("AOS_WRITE_ALLOW", p.stdout)
        p = self.run_cli(["x"], {})
        self.assertEqual(p.returncode, 1)
        self.assertIn("ArgumentsBad", p.stderr)


if __name__ == "__main__":
    unittest.main()
