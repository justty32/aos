# test_scope - unittest for scope.py: write_scope(env) from AOS_WS / AOS_WRITE_ALLOW / the deny sources, and its CLI.
import json, os, subprocess, sys, tempfile, unittest

sys.dont_write_bytecode = True   # importing scope.py must not leave __pycache__ next to it

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.dirname(HERE)
SCOPE = os.path.join(DIR, "scope.py")
sys.path.insert(0, DIR)
import scope   # noqa: E402
sys.path.pop(0)

RULES = [{"name": "deny_parts", "parts": [".git"]}, {"name": "proc-stack"},
         {"name": "definition-marker", "marker": "interfaces.json"},
         {"name": "no-hash-outside-json", "json_tools": ["json_set", "json_add", "json_del", "json_multi_set"]},
         {"name": "no-tilde"}]


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
        self.assertEqual(scope.write_scope(self.env), {"version": 1, "allow": [{"path": self.ws, "from": "AOS_WS"}],
                                                       "deny": [], "deny_parts": [".git"], "rules": RULES})

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
        self.env.update(AOS_STACK=os.path.join(self.stack, "hookeds", "guard") + "/", AOS_CD=os.path.join(self.t, "cd"),
                        AOS_DAEMON=self.daemon, AOS_WRITE_DENY=os.pathsep.join(["secret", "~/s"]))
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs": {"w-01": {"stack": "procs/w-01", "def": self.defdir}}}, f)
        self.cfg({"deny_roots": ["cfgdeny", 3, ""]})
        self.assertEqual(scope.write_scope(self.env)["deny"], [
            {"path": self.stack, "from": "AOS_STACK"},
            {"path": os.path.join(self.t, "cd"), "from": "AOS_CD"},
            {"path": self.defdir, "from": "definition"},
            {"path": self.daemon, "from": "AOS_DAEMON"},          # the row's stack and def are listed above already
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
                                 "w-sub": {"stack": "procs/w-01/sub", "def": other}}}, f)
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
        self.assertEqual(scope.definition(self.env), self.defdir)                  # AOS_KERNEL no longer skips it

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


class ProcStack(unittest.TestCase):
    # scope.proc_stack(real): rule proc-stack, applied to one resolved path
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.t = os.path.realpath(self.tmp.name)
        self.d = os.path.join(t, "ws", "d")
        for p in (os.path.join(self.d, "procs", "a"), os.path.join(self.d, "procs", "sub", "procs", "b"),
                  os.path.join(t, "ws", "src", "procs", "x")):
            os.makedirs(p)
        for p in (self.d, os.path.join(self.d, "procs", "sub")):
            open(os.path.join(p, "procs_state.json"), "w").close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_cases(self):
        d, ws = self.d, os.path.join(self.t, "ws")
        P = scope.proc_stack
        self.assertEqual(P(os.path.join(d, "procs", "a", "tools.json")), os.path.join(d, "procs", "a"))
        self.assertEqual(P(os.path.join(d, "procs", "a", "no", "such", "f")), os.path.join(d, "procs", "a"))
        self.assertEqual(P(os.path.join(d, "procs", "new", "f")), os.path.join(d, "procs", "new"))
        self.assertEqual(P(os.path.join(d, "procs_requests", "l.json")), d)
        self.assertEqual(P(os.path.join(d, "procs")), d)
        self.assertEqual(P(d), d)
        sub = os.path.join(d, "procs", "sub")
        self.assertEqual(P(os.path.join(sub, "procs", "b", "x")), os.path.join(sub, "procs", "b"))   # deepest wins
        self.assertEqual(P(os.path.join(sub, "x")), sub)
        self.assertEqual(P(os.path.join(ws, "p", ".stack", "h.json")), os.path.join(ws, "p", ".stack"))
        self.assertEqual(P(os.path.join(ws, ".stack")), os.path.join(ws, ".stack"))
        self.assertIsNone(P(os.path.join(ws, "src", "procs", "x", "a.py")))   # procs without the marker
        self.assertIsNone(P(os.path.join(ws, "notes.txt")))
        self.assertIsNone(P(os.path.join(ws, ".stackx", "a")))


class Cli(unittest.TestCase):
    def test_rules_not_enumerated(self):
        with tempfile.TemporaryDirectory() as t:
            t = os.path.realpath(t)
            os.makedirs(os.path.join(t, "d", "procs", "other"))
            open(os.path.join(t, "d", "procs_state.json"), "w").close()
            p = self.run_cli([], {"AOS_WS": t})
            got = json.loads(p.stdout)
            self.assertEqual(got["rules"], RULES)
            self.assertEqual(got["deny"], [])   # the neighbour stack is a rule, not a listed path

    def run_cli(self, args, env):
        base = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        base.update(env)
        return subprocess.run([sys.executable, SCOPE] + args, capture_output=True, text=True, env=base, timeout=30)

    def test_prints_json(self):
        with tempfile.TemporaryDirectory() as t:
            t = os.path.realpath(t)
            p = self.run_cli([], {"AOS_WS": t, "AOS_WRITE_DENY": os.path.join(t, "x")})
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(p.stdout), {"version": 1, "allow": [{"path": t, "from": "AOS_WS"}],
                                                    "deny": [{"path": os.path.join(t, "x"), "from": "AOS_WRITE_DENY"}],
                                                    "deny_parts": [".git"], "rules": RULES})

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


class Round1(unittest.TestCase):
    # the daemon table, AOS_DAEMON, AOS_HOME and the rules in write_scope; definition_marker
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.t = os.path.realpath(self.tmp.name)
        self.ws = os.path.join(t, "ws")
        self.daemon = os.path.join(t, "d")
        for d in (self.ws, os.path.join(self.daemon, "procs", "a"), os.path.join(t, "defs", "a"),
                  os.path.join(t, "defs", "b"), os.path.join(t, "st", "b")):
            os.makedirs(d)
        self.env = {"AOS_WS": self.ws, "HOME": os.path.join(t, "home")}

    def tearDown(self):
        self.tmp.cleanup()

    def write_table(self, procs):
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs": procs}, f)

    def test_table_rows_all_denied(self):
        t = self.t
        self.write_table({"a": {"stack": "procs/a", "def": "../defs/a"}, "b": {"stack": os.path.join(t, "st", "b"),
                          "def": os.path.join(t, "defs", "b")}, "c": {"stack": "procs/c"}})
        self.env.update(AOS_DAEMON=self.daemon, AOS_STACK=os.path.join(self.daemon, "procs", "a"))
        self.assertEqual(scope.write_scope(self.env)["deny"], [
            {"path": os.path.join(self.daemon, "procs", "a"), "from": "AOS_STACK"},
            {"path": os.path.join(t, "defs", "a"), "from": "definition"},
            {"path": os.path.join(t, "st", "b"), "from": "daemon-table"},
            {"path": os.path.join(t, "defs", "b"), "from": "daemon-table"},
            {"path": os.path.join(self.daemon, "procs", "c"), "from": "daemon-table"},
            {"path": self.daemon, "from": "AOS_DAEMON"}])

    def test_table_bad_after_retry(self):
        # a table file that exists but cannot be read (or has a row without a stack string) is read once more,
        # then TableBad; the daemon writes stack as a string always and def as a string or null
        self.env["AOS_DAEMON"] = self.daemon
        for bad in ("{broken", '{"procs": {"a": {"stack": {"$env": "X"}}}}', '{"procs": {"a": 3}}',
                    '{"procs": {"a": {"stack": "procs/a", "def": 3}}}', '{"procs": {"$ref": ["gone.json"]}}'):
            with self.subTest(table=bad):
                with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
                    f.write(bad)
                with self.assertRaises(scope.ScopeError) as c:
                    scope.write_scope(self.env)
                self.assertEqual(c.exception.code, "TableBad")
                with self.assertRaises(scope.ScopeError):
                    scope.table_rows(self.env)

    def test_table_retry_reads_again(self):
        # torn read (the main file and its shards are written one by one): the second read is used
        self.env["AOS_DAEMON"] = self.daemon
        st = os.path.join(self.daemon, "procs_state.json")
        with open(st, "w", encoding="utf-8") as f:
            f.write('{"procs": {"$ref": ["part.json"]}}')
        calls = []

        def pause(s):
            calls.append(s)
            with open(os.path.join(self.daemon, "part.json"), "w", encoding="utf-8") as f:
                json.dump({"a": {"stack": "procs/a", "def": "../defs/a"}}, f)
        real_sleep, scope.time.sleep = scope.time.sleep, pause
        try:
            rows = scope.table_rows(self.env)
        finally:
            scope.time.sleep = real_sleep
        self.assertEqual(calls, [scope.TABLE_RETRY_S])
        self.assertEqual(rows, [(os.path.join(self.daemon, "procs", "a"), os.path.join(self.t, "defs", "a"))])

    def test_event_stack(self):
        ev = os.path.join(self.t, "st", "b")
        got = scope.write_scope(self.env, stack=os.path.join(ev, "tools", "x"))["deny"]
        self.assertEqual(got, [{"path": ev, "from": "event"}])
        self.env["AOS_STACK"] = ev
        self.assertEqual(scope.write_scope(self.env, stack=ev)["deny"], [{"path": ev, "from": "AOS_STACK"}])

    def test_daemon_folder_without_table(self):
        self.env["AOS_DAEMON"] = self.daemon
        self.assertEqual(scope.write_scope(self.env)["deny"], [{"path": self.daemon, "from": "AOS_DAEMON"}])
        self.assertEqual(scope.table_rows(self.env), [])

    def test_home_folders_that_exist(self):
        home = os.path.join(self.t, "aos")
        for p in ("lib", "cpp", "py", "bin", "include", "ws"):
            os.makedirs(os.path.join(home, p))
        self.env["AOS_HOME"] = home
        self.assertEqual(scope.write_scope(self.env)["deny"], [{"path": os.path.join(home, p), "from": "AOS_HOME"}
                                                               for p in ("lib", "cpp", "py", "bin", "include")])

    def test_resolve_home_flag(self):
        self.assertEqual(scope.resolve("~/x", self.ws, self.env), os.path.join(self.t, "home", "x"))
        self.assertEqual(scope.resolve("~/x", self.ws, self.env, home=False), os.path.join(self.ws, "~", "x"))

    def test_deny_parts_config(self):
        p = os.path.join(self.t, "g.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"deny_parts": [".git", ".hg"]}, f)
        self.env["AOS_GUARD_CFG"] = p
        got = scope.write_scope(self.env)
        self.assertEqual(got["rules"][0], {"name": "deny_parts", "parts": [".git", ".hg"]})
        self.assertEqual(got["deny_parts"], [".git", ".hg"])   # also a key of its own (item: --scope shape)
        self.assertEqual(got["version"], 1)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"deny_parts": ".git"}, f)
        with self.assertRaises(scope.ScopeError) as c:
            scope.write_scope(self.env)
        self.assertEqual(c.exception.code, "CfgBad")

    def test_definition_marker(self):
        d = os.path.join(self.t, "defs", "a")
        open(os.path.join(d, "interfaces.json"), "w").close()
        M = scope.definition_marker
        self.assertEqual(M(d), d)
        self.assertEqual(M(os.path.join(d, "screen", "no", "such")), d)
        self.assertIsNone(M(os.path.join(self.t, "defs", "b", "x")))
        self.assertIsNone(M(self.ws))


if __name__ == "__main__":
    unittest.main()
