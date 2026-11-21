"""Tests of the kernel compile entry (from aos.py.kernel import defs; aos/kernel_spec): what it writes, the templates it matches, hooks, errors, the command line, and one live round of a compiled station."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_spec_helpers import LIB, PROTO, fake_home, env_with  # noqa: E402
from aos.py.kernel import defs  # noqa: E402
from aos.spec_base import Program  # noqa: E402

KT = PROTO / "templates" / "kernel"
SKEL = KT / "kernel-python"
HEAD = "import sys\nsys.path.insert(0, %r)\nfrom aos.py.kernel import defs\nfrom aos.py import fn\n" % str(LIB)
NIGHT = '''
@fn.hook("before_verdict")
def no_night_jobs(event):
    """Refuse procs named night-something."""
    names = (event.get("body") or {}).get("procs_added") or {}
    if any(str(n).startswith("night") for n in names):
        return fn.block("no night jobs here")
'''


def read(p):
    return json.loads(Path(p).read_text())


def bare(v):
    """the value without description keys (the templates are hand-written and say less)."""
    if isinstance(v, dict):
        return {k: bare(x) for k, x in v.items() if k != "description"}
    return v


def run(script, *argv, home=None):
    return subprocess.run([sys.executable, str(script), *argv], text=True, capture_output=True, timeout=60, env=env_with(home))


class Templates(unittest.TestCase):
    """Compiling the knobs of a hand-written kernel template gives that template (descriptions and the _entry form aside)."""

    def check(self, template, kernel):
        out = kernel.dry_run()
        self.assertEqual(out["_entry"]["argv"], read(KT / template / "_entry"))
        for name, value in out.items():
            if name in ("_entry", "README.md"):
                continue
            with self.subTest(template=template, file=name):
                self.assertEqual(bare(value), bare(read(KT / template / name)))

    def test_procs_kernel(self):
        self.check("procs-kernel", defs.Kernel("x", knobs=read(KT / "procs-kernel/kernel.json")))

    def test_daemon_kernel(self):
        self.check("daemon-kernel", defs.Kernel("x", knobs=read(KT / "daemon-kernel/kernel.json"), body=defs.daemon()))

    def test_llm_kernel(self):
        knobs = bare(read(KT / "llm-kernel/kernel.json"))
        out = defs.Kernel("x", program="kernel_llm", knobs=knobs).dry_run()
        self.assertEqual(sorted(out), ["README.md", "_entry", "daemon.json", "interfaces.json", "kernel.json"])
        self.check("llm-kernel", defs.Kernel("x", program="kernel_llm", knobs=knobs))

    def test_every_ms(self):
        self.assertEqual(defs.Kernel("x", body=defs.loop(every_ms=1000)).dry_run()["loop.json"]["interval_ms"], 1000)
        self.assertEqual(defs.Kernel("x", body=defs.daemon(every_ms=0)).dry_run()["daemon.json"]["interval_ms"], 0)

    def test_any_key_goes_through(self):
        """11-21「任意鍵照傳」(same as the agent's defs.loop): any key, as it is, unchecked; same name as a compiled key = yours wins."""
        plain = defs.Kernel("x", body=defs.loop()).dry_run()["loop.json"]
        loop = defs.Kernel("x", body=defs.loop(every_ms=1000, max=3, on_start=["true"], x_y=None)).dry_run()["loop.json"]
        self.assertEqual(loop, dict(plain, interval_ms=1000, max=3, on_start=["true"], x_y=None,
                                    description=plain["description"].replace("every 300 ms", "every 1000 ms")))
        daemon = defs.Kernel("x", body=defs.daemon(interval_ms=50, procs={})).dry_run()["daemon.json"]
        self.assertEqual((daemon["interval_ms"], daemon["procs"]), (50, {}))     # procs given = no sweeper row
        self.assertIn("every 50 ms", daemon["description"])
        self.assertEqual(defs.Kernel("x", body=defs.daemon(interval_ms="x")).dry_run()["daemon.json"]["interval_ms"], "x")   # unchecked
        self.assertRaisesRegex(defs.SpecBad, "every_ms or interval_ms, not both", defs.Kernel("x", body=defs.daemon(every_ms=1, interval_ms=1)).dry_run)


class Hooks(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kernel-spec-"))
        self.addCleanup(shutil.rmtree, self.tmp)

    def compile(self, body, *argv):
        script = self.tmp / "k" / "kernel.py"
        script.parent.mkdir(exist_ok=True)
        script.write_text(HEAD + body)
        return run(script, *argv)

    def test_function_hooks_go_to_kernel_json_and_loop_hooks_json(self):
        r = self.compile(NIGHT + '''
@fn.hook("after_start")
def hello(event):
    return None
defs.main(defs.Kernel("No night jobs.", hooks=[no_night_jobs, hello, {"log": {"event": "after_verdict", "handler": "log.py"}}]))
''', "--compile")
        self.assertEqual(r.returncode, 0, r.stderr)
        k = self.tmp / "k"
        self.assertEqual(read(k / "kernel.json")["hooks"], {"no_night_jobs": {"event": "before_verdict", "handler": "fn/no_night_jobs.py"},
                                                            "log": {"event": "after_verdict", "handler": "log.py"}})
        self.assertEqual(read(k / "loop_hooks.json")["hooks"], {"hello": {"event": "after_start", "handler": "fn/hello.py"}})
        for name in ("no_night_jobs", "hello"):
            self.assertEqual(os.stat(k / "fn" / (name + ".py")).st_mode & 0o777, 0o755)
        self.assertIn("fn.main(no_night_jobs)", (k / "fn/no_night_jobs.py").read_text())

    def test_daemon_body_has_no_loop_points(self):
        r = self.compile('''
defs.main(defs.Kernel("x", body=defs.daemon(), hooks={"h": {"event": "before_run", "handler": "h.py"}}))
''', "--dry-run")
        self.assertEqual(r.returncode, 1)
        self.assertIn("SpecBad hooks: hook h: event must be one of before_verdict, after_verdict, before_reply", r.stderr)

    def test_later_wins_and_none_drops(self):
        h = {"event": "before_verdict", "handler": "a.py"}
        out = defs.Kernel("x", hooks=[{"a": h, "b": h}, {"a": dict(h, handler="z.py"), "b": None}]).dry_run()
        self.assertEqual(out["kernel.json"]["hooks"], {"a": dict(h, handler="z.py")})
        self.assertEqual(out["loop_hooks.json"]["hooks"], {})

    def test_block_where_it_cannot_block(self):
        r = self.compile('''
@fn.hook("after_start")
def stop(event):
    return fn.block("no")
defs.main(defs.Kernel("x", hooks=[stop]))
''', "--dry-run")
        self.assertEqual(r.returncode, 1)
        self.assertIn("after_start cannot be blocked", r.stderr)

    def test_function_cannot_use_defs(self):
        r = self.compile('''
@fn.hook("before_verdict")
def h(event):
    return defs.PUBLIC
defs.main(defs.Kernel("x", hooks=[h]))
''', "--dry-run")
        self.assertEqual(r.returncode, 1)
        self.assertIn("SpecBad", r.stderr)


class Errors(unittest.TestCase):
    def bad(self, kernel, words):
        with self.assertRaises(defs.SpecBad) as e:
            kernel.dry_run()
        self.assertIn(words, str(e.exception))

    def test_spec_bad(self):
        self.bad(defs.Kernel(""), "description must be a non-empty string")
        self.bad(defs.Kernel("x", program="kernel2"), "program must be one of kernel, kernel_llm")
        self.bad(defs.Kernel("x", knobs=[1]), "knobs must be a dict")
        self.bad(defs.Kernel("x", knobs={"hooks": {}}), "knobs must not set hooks: use hooks=")
        self.bad(defs.Kernel("x", knobs={"description": "y"}), "knobs must not set description")
        self.bad(defs.Kernel("x", body="loop"), "body must come from defs.loop")
        self.bad(defs.Kernel("x", body=defs.loop(every_ms=-1)), "every_ms must be a whole number")
        self.bad(defs.Kernel("x", hooks="h"), "hooks must be a dict")
        self.bad(defs.Kernel("x", knobs={"x": float("nan")}), "cannot be written as JSON")

    def test_unknown_names(self):
        with self.assertRaises(AttributeError):
            defs.Kernel("x").knob = {}
        with self.assertRaises(AttributeError):
            defs.extern               # noqa: B018


class CommandLine(unittest.TestCase):
    def test_skeleton_committed_files_match_kernel_py(self):
        with tempfile.TemporaryDirectory(prefix="kernel-python-") as tmp:
            home = fake_home(tmp)
            dest = Path(tmp) / "kernel-python"
            dest.mkdir()
            shutil.copy(SKEL / "kernel.py", dest)
            r = run(dest / "kernel.py", "--compile", home=home)
            self.assertEqual(r.returncode, 0, r.stderr)
            for name in ("_entry", "loop.json", "kernel.json"):
                with self.subTest(name=name):
                    self.assertEqual((dest / name).read_bytes(), (SKEL / name).read_bytes(),
                                     "run python3 kernel.py --compile in templates/kernel/kernel-python")

    def test_flags(self):
        with tempfile.TemporaryDirectory(prefix="kernel-cli-") as tmp:
            home = fake_home(tmp)
            dest = Path(tmp) / "perm"
            dest.mkdir()
            shutil.copy(SKEL / "kernel.py", dest)
            r = run(dest / "kernel.py", "--dry-run", home=home)
            self.assertEqual((r.returncode, sorted(json.loads(r.stdout))), (0, ["README.md", "_entry", "kernel.json", "loop.json"]))
            self.assertEqual(sorted(p.name for p in dest.iterdir()), ["kernel.py"])
            r = run(dest / "kernel.py", "--help", home=home)
            self.assertTrue(r.stdout.startswith("usage: python3 kernel.py --compile [FOLDER] | --dry-run | --help"))
            r = run(dest / "kernel.py", "--static", home=home)
            self.assertEqual((r.returncode, r.stderr.split(" (")[0]), (1, "perm: error: FlagUnknown --static"))
            r = run(dest / "kernel.py", home=home)
            self.assertIn("perm: error: ArgumentsBad give --compile or --dry-run", r.stderr)

    def test_main_takes_one_kernel(self):
        with tempfile.TemporaryDirectory(prefix="kernel-main-") as tmp:
            script = Path(tmp) / "kernel.py"
            script.write_text(HEAD + "defs.main({'a': 1})\n")
            r = run(script, "--dry-run")
            self.assertEqual(r.returncode, 1)
            self.assertIn("SpecBad defs.main takes one kernel", r.stderr)


class Live(unittest.TestCase):
    """One round of the real station program over a compiled kernel.json: the function hook refuses night1, day1 goes on."""

    def test_round(self):
        post = shutil.which("aos-post")
        if not post or not os.environ.get("AOS_HOME"):
            self.skipTest("needs an installed aos (aos-post on PATH, AOS_HOME set)")
        tmp = Path(tempfile.mkdtemp(prefix="kernel-live-"))
        self.addCleanup(shutil.rmtree, tmp)
        k = tmp / "perm"
        k.mkdir()
        (k / "kernel.py").write_text(HEAD + NIGHT + 'defs.main(defs.Kernel("No night jobs.", hooks=[no_night_jobs]))\n')
        env = dict(env_with(None), AOS_HOME=os.environ["AOS_HOME"])
        self.assertEqual(subprocess.run([sys.executable, str(k / "kernel.py"), "--compile"], capture_output=True, env=env).returncode, 0)
        stack, daemon, box = tmp / "stack", tmp / "daemon", tmp / "replies"
        stack.mkdir()
        daemon.mkdir()
        env.update(AOS_STACK=str(stack), AOS_DAEMON=str(daemon))

        def p(*a, body=None):
            r = subprocess.run([post, *map(str, a)], input="" if body is None else json.dumps(body), text=True, capture_output=True, env=env)
            self.assertIn(r.returncode, (0, 10), r.stderr)
            return r.stdout.strip()
        for mailbox in (box, stack / "requests", daemon / "procs_requests"):
            p("init", mailbox)
        for name in ("night1", "day1"):
            p("send", "--reply-to", box, stack / "requests", name, body={"procs_added": {name: {"exec": {"argv": ["true"]}}}})
        station = Path(os.environ["AOS_HOME"]) / "lib" / "tools" / "aos" / "kernel" / "_entry"
        r = subprocess.run([sys.executable, str(station), str(k / "kernel.json")], text=True, capture_output=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        p("take-all", box)
        replies = [read(d / "letter.json")["body"] for d in sorted((box / "cur").iterdir())]
        self.assertEqual(replies, [{"applied": False, "error": {"code": "HookRejected", "msg": "no night jobs here"}}])
        p("take-all", daemon / "procs_requests")
        forwarded = [read(d / "letter.json")["body"] for d in sorted((daemon / "procs_requests" / "cur").iterdir())]
        self.assertEqual(forwarded, [{"procs_added": {"day1": {"exec": {"argv": ["true"]}}}}])


if __name__ == "__main__":
    unittest.main()
