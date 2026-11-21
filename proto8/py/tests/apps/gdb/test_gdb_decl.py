"""aos-gdb 拿 hook 宣告當參考（aos.gdb.decl、--hooks／--def-hooks）：沒載入＝跟以前一樣；載入後列點與欄位、多出種類與主詞、下斷點對不上只提醒照下；壞的宣告一行 warning 不擋；成立的事件存 hit.json、a.bp.event() 照宣告排；對真的樹（假腦）自訂點 before_save 下斷點、aos-hook fire 發事件、停下看事件。"""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

PROTO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROTO / "py"))
import aos.gdb as g  # noqa: E402
from aos.gdb import decl, trigger  # noqa: E402
from test_gdb_trigger import FAKE_AGENT, FAKE_DAEMON_CTL, ENTRY, spec  # noqa: E402

FSM = PROTO / "templates" / "agent-fsm" / "hooks.json"
LOOP = PROTO / "py" / "aos" / "apps" / "hook" / "loop_hooks.json"
SAVER = {"description": "Hook points of a test saver.",
         "before_save": {"description": "before a file is saved",
                         "input": {"type": "object", "properties": {"event": {"const": "before_save"}, "hook": {}, "stack": {},
                                                                    "file": {"description": "the file name"}, "size": {}}},
                         "condition": "file", "subject": "path", "phase": "before", "block": True},
         "after_save": {"input": {"properties": {"file": {}}}},
         "odd_one": {"input": {"properties": {"x": {}}}, "condition": "times"},   # 欄位名撞到 a.bp.add 的參數：不當主詞
         "class": {"input": {}}}                                                  # Python 保留字：不當種類


def quiet(fn, *a, **kw):
    """跑 fn，回 (結果, stderr 的字)。"""
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        r = fn(*a, **kw)
    return r, err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        decl.current.clear()
        self.tmp = Path(tempfile.mkdtemp(prefix="gdb-decl-"))
        self.saver = self.tmp / "saver_hooks.json"
        self.saver.write_text(json.dumps(SAVER))

    def tearDown(self):
        decl.current.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)


class NoDecl(Base):
    """沒載入任何宣告：種類、主詞、提醒都跟以前一樣。"""

    def test_defaults_unchanged(self):
        self.assertFalse(decl.current)
        self.assertEqual(g.kinds(), g.KINDS)
        for k in g.KINDS:
            want = (g.SUBJECT[k], "name") if k in g.SUBJECT else None
            self.assertEqual(g.subject_of(k), want, k)
        self.assertEqual(decl.warnings("before_run", "before_run", py="ev['zzz']"), [])
        self.assertIn("no hook declarations loaded", repr(decl.current))
        add = g.Breakpoints(g.Target("ann", "/d")).add
        self.assertEqual(set(dir(add)), set(g.KINDS))
        self.assertNotIn("declared", repr(add))

    def test_layout_without_declaration(self):
        text = decl.layout({"event": "x", "hook": "gdb_0001", "stack": "/s", "b": 1, "a": "t"}, "x")
        self.assertEqual(text.splitlines()[0], "event x")
        self.assertEqual([l.split()[0] for l in text.splitlines()[1:]], ["event", "hook", "stack", "b", "a"])
        self.assertNotIn("#", text)


class Load(Base):
    def test_good_and_bad_files(self):
        bad_json = self.tmp / "bad.json"
        bad_json.write_text("{not json")
        no_input = self.tmp / "noinput.json"
        no_input.write_text(json.dumps({"p": {"description": "no input"}}))
        listy = self.tmp / "list.json"
        listy.write_text("[]")
        _, err = quiet(decl.current.load, FSM, self.tmp / "missing.json", bad_json, no_input, listy, LOOP)
        lines = err.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(l.startswith("hooks.load: warning: ") and l.endswith("going on without it") for l in lines), lines)
        self.assertEqual(decl.current.files, [str(FSM), str(LOOP)])
        self.assertIn("before_tool", decl.current.points)
        self.assertIn("before_run", decl.current.points)
        self.assertEqual(decl.current.fields("after_tool")[-3:], ["content", "code", "timed_out"])
        self.assertIsNone(decl.current.fields("nope"))

    def test_first_file_wins_and_clear(self):
        other = self.tmp / "other.json"
        other.write_text(json.dumps({"before_save": {"input": {"properties": {"zzz": {}}}}}))
        decl.current.load(self.saver, other)
        self.assertIn("file", decl.current.fields("before_save"))
        decl.current.clear()
        self.assertFalse(decl.current)
        self.assertEqual(g.kinds(), g.KINDS)

    def test_listing(self):
        decl.current.load(FSM, LOOP, self.saver)
        text = repr(decl.current)
        self.assertTrue(text.startswith("hook declarations (only for reference): "))
        rows = {l.split()[0]: l for l in text.splitlines() if l and not l.startswith(("  /", "hook ", "("))}
        self.assertIn("hold", rows["before_tool"])
        self.assertIn("tool= (name)", rows["before_tool"])
        self.assertIn("name, id, arguments", rows["before_tool"])
        self.assertIn("pause", rows["before_save"])
        self.assertIn("path= (file)", rows["before_save"])
        self.assertIn("needs an interval", rows["on_clock"])
        self.assertIn("not a kind", rows["class"])

    def test_load_def(self):
        d = self.tmp / "def"
        d.mkdir()
        shutil.copy(self.saver, d / "hooks.json")
        (d / "interfaces.json").write_text(json.dumps({"hooks": ["hooks.json", str(LOOP)], "hookeds": "hookeds.json"}))
        _, err = quiet(decl.current.load_def, str(d))
        self.assertEqual(err, "")
        self.assertEqual(decl.current.files, [str(d / "hooks.json"), str(LOOP)])
        decl.current.clear()
        (d / "interfaces.json").write_text(json.dumps({"hookeds": "hookeds.json"}))
        _, err = quiet(decl.current.load_def, str(d))
        self.assertIn("has no \"hooks\"", err)
        (d / "interfaces.json").write_text(json.dumps({"hooks": 3}))
        _, err = quiet(decl.current.load_def, str(d))
        self.assertIn("hooks.load_def: warning: ", err)
        self.assertFalse(decl.current)

    def test_load_def_from_a_remote_that_cannot_answer(self):
        class Gone:
            name = "ghost"

            class ctl:
                @staticmethod
                def state(*a, **kw):
                    raise g.Failed("aos-agent: error: TargetMissing ghost is not on the table")
        _, err = quiet(decl.current.load_def, Gone())
        self.assertIn("cannot ask where the definition of ghost is", err)


class Kinds(Base):
    def test_extra_kinds_and_subjects(self):
        decl.current.load(FSM, self.saver)
        ks = g.kinds()
        self.assertEqual(ks[:len(g.EVENTS)], g.EVENTS)
        self.assertEqual(ks[len(g.EVENTS):], ("before_save", "after_save", "odd_one", "tool_error", "watch"))
        self.assertEqual(g.subject_of("before_save"), ("path", "file"))
        self.assertIsNone(g.subject_of("after_save"))
        self.assertIsNone(g.subject_of("odd_one"))                  # condition 撞到參數名
        self.assertEqual(g.subject_of("before_tool"), ("tool", "name"))
        self.assertEqual(g.subject_of("tool_error"), ("tool", "name"))
        self.assertEqual(g.subject_of("before_run"), None)          # 宣告沒有這點：照預設（沒有主詞）
        add = g.Breakpoints(g.Target("ann", "/d")).add
        import inspect
        self.assertEqual(list(inspect.signature(add.before_save).parameters)[0], "path")
        self.assertIn("before a file is saved", add.before_save.__doc__)
        r = repr(add)
        self.assertIn("hook declarations loaded", r)
        self.assertIn("before_run(*, sh=None", r)
        self.assertRegex(r, r"before_run\(.*\)   \(not declared\)")
        self.assertNotRegex(r, r"before_tool\(.*\(not declared\)")

    def test_py_fields(self):
        self.assertEqual(decl.py_fields("ev['name'] == 'x' and ev.get('code') and ev['arguments'].get('path')"), ["name", "code", "arguments"])
        self.assertEqual(decl.py_fields(lambda e: e["content"].startswith("x")), ["content"])

        def f(event, n=3):
            return len(event.get("letters") or []) > n
        self.assertEqual(decl.py_fields(f), ["letters"])
        self.assertEqual(decl.py_fields("ev[1"), [])
        self.assertEqual(decl.py_fields(3), [])

    def test_warnings(self):
        decl.current.load(FSM)
        self.assertEqual(decl.warnings("after_tool", "after_tool", py="ev['code'] != 0"), [])
        w = decl.warnings("after_tool", "after_tool", py=lambda ev: ev["nam"] == "x")
        self.assertEqual(len(w), 1)
        self.assertIn("ev['nam'], not declared in the input of after_tool", w[0])
        self.assertEqual(decl.warnings("before_run", "before_run"),
                         ["before_run is not in the loaded hook declarations (hooks lists them); added anyway"])


class Add(Base):
    """a.bp.add 對假的 aos-agent：掛的參數、trigger.json、提醒行。"""

    def setUp(self):
        super().setUp()
        (self.tmp / "stack").mkdir()
        (self.tmp / "daemon" / "procs").mkdir(parents=True)
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        for name, text in (("aos-agent", FAKE_AGENT), ("aos-daemon-ctl", FAKE_DAEMON_CTL)):
            (bin_ / name).write_text(text)
            (bin_ / name).chmod(0o755)
        (self.tmp / "MODE").write_text("ok")
        self.old = {k: os.environ.get(k) for k in ("PATH", "FAKE_DIR")}
        os.environ["PATH"] = str(bin_) + os.pathsep + os.environ["PATH"]
        os.environ["FAKE_DIR"] = str(self.tmp)
        self.bp = g.Breakpoints(g.Target("ann", str(self.tmp / "daemon")))

    def tearDown(self):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        super().tearDown()

    def args(self):
        return json.loads((self.tmp / "add_args.json").read_text())

    def spec_of(self, b):
        return json.loads((self.tmp / "stack" / "hookeds" / g._hook(b.id) / trigger.SPEC).read_text())

    def test_without_declaration_same_as_before(self):
        b, err = quiet(self.bp.add.before_tool, "write", py="ev['nam'] == 1")
        self.assertEqual(err, "")
        s = self.spec_of(b)
        self.assertNotIn("field", s)
        self.assertEqual((s["how"], s["tools"]), ("hold", ["write"]))
        a = self.args()
        self.assertEqual(a[a.index("--condition") + 1], "write")
        with self.assertRaises(AttributeError):
            self.bp.add.before_save

    def test_declared_point_with_its_own_subject(self):
        decl.current.load(FSM, self.saver)
        bp = g.Breakpoints(g.Target("ann", str(self.tmp / "daemon")))
        b, err = quiet(bp.add.before_save, "a.txt")
        self.assertEqual(err, "")
        self.assertEqual(b.kind, "before_save")
        s = self.spec_of(b)
        self.assertEqual((s["event"], s["how"], s["tools"], s["field"]), ("before_save", "pause", ["a.txt"], "file"))
        self.assertEqual(s["about"], "event before_save with file a.txt")
        a = self.args()
        self.assertEqual(a[a.index("--event") + 1], "before_save")
        self.assertNotIn("--condition", a)                           # 不是 agent 一家的點：篩法交給 gdb_trigger
        self.assertTrue(trigger.check(s, {"file": "a.txt"}))
        self.assertFalse(trigger.check(s, {"file": "b.txt", "name": "a.txt"}))
        with self.assertRaises(g.Failed):
            bp.add.after_save("x")                                   # 沒宣告 condition：沒有主詞

    def test_mismatch_only_warns(self):
        decl.current.load(FSM)
        bp = g.Breakpoints(g.Target("ann", str(self.tmp / "daemon")))
        b, err = quiet(bp.add.before_run)
        self.assertEqual(err, "a.bp.add.before_run: warning: before_run is not in the loaded hook declarations (hooks lists them); added anyway\n")
        self.assertEqual(b.kind, "before_run")
        b2, err = quiet(bp.add.tool_error, "write", times=2)
        self.assertEqual(err, "")
        b3, err = quiet(bp.add.after_tool, py=lambda ev: ev.get("contnt") == "")
        self.assertIn("a.bp.add.after_tool: warning: the py condition reads ev['contnt']", err)
        self.assertEqual(sorted(r["id"] for r in bp.ls(quiet=True)), [b.id, b2.id, b3.id])


class Handler(Base):
    """gdb_trigger 成立時存 hit.json、不成立不存；字條的 detail 帶宣告給的欄位。"""

    def test_hit_json_and_field_in_note(self):
        stack = self.tmp / "stack"
        cell = stack / "hookeds" / "gdb_0001"
        cell.mkdir(parents=True)
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        (bin_ / "aos-agent").write_text('#!/bin/sh\necho \'{"cmd": "pause", "seq": 7}\' > "%s/ctl.json"\n' % stack)
        (bin_ / "aos-agent").chmod(0o755)
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(PATH=str(bin_) + os.pathsep + env["PATH"], AOS_STACK=str(cell) + "/", PYTHONDONTWRITEBYTECODE="1")
        s = spec(event="before_save", tools=["a.txt"], field="file")
        trigger.write_json(str(cell / trigger.SPEC), s)

        def fire(ev):
            doc = dict({"event": "before_save", "hook": "gdb_0001", "stack": str(stack)}, **ev)
            return subprocess.run([str(ENTRY)], input=json.dumps(doc), capture_output=True, text=True, env=env, timeout=30)
        r = fire({"file": "b.txt", "size": 1})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse((cell / trigger.HIT).exists())
        r = fire({"file": "a.txt", "size": 2})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(json.loads((cell / trigger.HIT).read_text())["size"], 2)
        note = trigger.read_log(str(stack))[-1]
        self.assertEqual(note["detail"]["file"], "a.txt")

    def test_brief_and_validate(self):
        self.assertEqual(trigger.brief({"file": "x", "name": "n"}, field="file"), {"name": "n", "file": "x"})
        self.assertNotIn("file", trigger.brief({"file": "x"}))
        with self.assertRaises(trigger.Bad):
            spec(field="")


class Cli(Base):
    """aos-gdb 的 --hooks／--def-hooks（不接 agent，stdin 餵 REPL）。"""

    def run_gdb(self, *args, stdin="print('N', len(hooks.points))\n"):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(PYTHONPATH=str(PROTO / "py"), PYTHONDONTWRITEBYTECODE="1", AOS_DAEMON=str(self.tmp))
        return subprocess.run([sys.executable, str(PROTO / "py" / "aos" / "apps" / "gdb" / "main.py")] + list(args),
                              input=stdin, capture_output=True, text=True, env=env, timeout=60)

    def test_no_flags(self):
        r = self.run_gdb()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("N 0", r.stdout)
        self.assertNotIn("hook declarations", r.stderr)
        self.assertNotIn("warning", r.stderr)

    def test_hooks_files_and_a_bad_one(self):
        r = self.run_gdb("--hooks", str(FSM), "--hooks", str(self.tmp / "missing.json"), "--hooks=%s" % self.saver,
                         stdin="print('N', len(hooks.points)); print('K', 'before_save' in dir(agent.attach('x').bp.add))\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("N 13", r.stdout)
        self.assertIn("K True", r.stdout)
        warns = [l for l in r.stderr.splitlines() if "warning" in l]
        self.assertEqual(len(warns), 1)
        self.assertTrue(warns[0].startswith("aos-gdb: warning: cannot read hook points "))
        self.assertIn("hook declarations: 13 point(s) from 2 file(s)", r.stderr)

    def test_def_hooks_needs_a_name(self):
        r = self.run_gdb("--def-hooks")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("aos-gdb: warning: --def-hooks needs an agent NAME", r.stderr)
        self.assertIn("N 0", r.stdout)

    def test_help(self):
        r = self.run_gdb("--help", stdin="")
        self.assertEqual(r.returncode, 0)
        self.assertIn("--hooks FILE", r.stdout)
        self.assertIn("--def-hooks", r.stdout)
        self.assertIn("a.bp.event()", r.stdout)


ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
ENV.update(AOS_HOME=str(PROTO), PATH=str(PROTO / "bin") + os.pathsep + ENV["PATH"], PYTHONDONTWRITEBYTECODE="1")


def until(cond, timeout=30, every=0.1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = cond()
        if v:
            return v
        time.sleep(every)
    raise AssertionError("timed out")


@unittest.skipUnless((PROTO / "bin" / "aos-exec").exists(), "needs an installed copy (python3 install.py)")
class Live(unittest.TestCase):
    """真的樹（start-api、假腦）：從 ann 的定義讀宣告、自訂點 before_save 下斷點（主詞 path＝比 file 欄）、aos-hook fire 發事件、停下、a.bp.event() 照宣告排。"""

    @classmethod
    def setUpClass(cls):
        decl.current.clear()
        cls.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="gdb-decl-live-")))
        cls.tree = cls.tmp / "tree"
        shutil.copytree(PROTO / "templates" / "start-api", cls.tree, symlinks=True)
        cls.saver = cls.tmp / "saver_hooks.json"
        cls.saver.write_text(json.dumps(SAVER))
        cls.log = open(cls.tmp / "root.log", "w")
        cls.root = subprocess.Popen(["aos-exec", "root"], cwd=cls.tree, env=ENV, stdin=subprocess.DEVNULL,
                                    stdout=cls.log, stderr=subprocess.STDOUT, start_new_session=True)
        until(lambda: (cls.tree / ".stack" / "state.json").exists())
        cls.sh("aos-daemon-ctl -d .stack add --auto-restart llm")
        cls.sh("aos-agent -d .stack ctl add --auto-restart -w . agents/ann")
        os.environ.update(AOS_HOME=str(PROTO), PATH=ENV["PATH"])
        from aos.py import agent
        cls.a = agent.attach("ann", daemon=str(cls.tree / ".stack"))
        cls.a.bp.timeout_s = 60

    @classmethod
    def tearDownClass(cls):
        decl.current.clear()
        try:
            cls.sh("aos-daemon-ctl -d .stack shutdown", check=False)
            try:
                cls.root.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(cls.root.pid, signal.SIGKILL)               # 只收這個測試自己起的那一群
                cls.root.wait()
        finally:
            cls.log.close()
            shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def sh(cls, cmd, check=True, stdin=None):
        r = subprocess.run(cmd, shell=True, cwd=cls.tree, env=ENV, capture_output=True, text=True, timeout=60, input=stdin)
        if check and r.returncode:
            raise AssertionError("%s: %s" % (cmd, r.stderr))
        return r.stdout

    def test_custom_point_from_the_declaration(self):
        a = self.a
        _, err = quiet(decl.current.load_def, a)                     # ann 的 interfaces.json：aos-loop 四點（指示詞）＋ agent-fsm 那份
        self.assertEqual(err, "")
        self.assertIn("before_run", decl.current.points)
        self.assertIn("before_tool", decl.current.points)
        decl.current.load(self.saver)
        b = a.bp.add.before_save(path="a.txt")
        who = a.ctl.state("who", json=True)["who"]
        fire = "aos-hook fire -q --def %s --stack %s before_save" % (who["def"], who["stack"])
        self.sh(fire, stdin=json.dumps({"file": "b.txt", "size": 1}))
        time.sleep(1.5)
        self.assertFalse(a.bp.stopped())                             # 主詞不合：不停
        self.sh(fire, stdin=json.dumps({"file": "a.txt", "size": 7, "extra": True}))
        until(lambda: a.bp.stopped())
        w = a.bp.why()
        self.assertEqual(w.breakpoint, b.id)
        self.assertTrue(a.bp._stopped_head(w).startswith("stopped at breakpoint %d (before_save: a.txt)" % b.id))
        ev = repr(a.bp.event())
        self.assertTrue(ev.startswith("event before_save at breakpoint %d (gdb_%04d); fields in the order the declaration gives" % (b.id, b.id)), ev)
        self.assertRegex(ev, r'\n  file +"a.txt"   # the file name')
        self.assertRegex(ev, r"\n  extra +true   # not declared")
        a.bp.rm(b)
        r = a.bp.resume()
        self.assertIn(r.outcome, ("idle", "stopped"))
        self.assertIn("is not stopped at a breakpoint", repr(a.bp.event()))


if __name__ == "__main__":
    unittest.main()
