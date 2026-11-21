"""Phase 1 of parent / notify_box on a real isolated daemon (ok-devt-1114 05 定稿 1.2, 1.3 and 修訂 1, ok-limits 11-14).

Only an add that already carries envs (--envs, --parent, --notify-box; subagent and fork always do) records
AOS_PARENT_STACK and AOS_NOTIFY_BOX; an add without envs is attached exactly as before.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import env_helper  # noqa: E402  同夾的共用零件


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[4]
BIN = PROTO / "bin" / "aos-agent"
SUBAGENT = PROTO / "py" / "tools" / "agent" / "subagent" / "_entry"
AGENTS_CTL = PROTO / "py" / "tools" / "agent" / "agents_ctl" / "_entry"
FORK = PROTO / "py" / "tools" / "agent" / "fork" / "_entry"
ENV = {key: value for key, value in os.environ.items() if not key.startswith("AOS_")}
ENV["PATH"] = str(PROTO / "bin") + os.pathsep + ENV["PATH"]
ENV["PYTHONDONTWRITEBYTECODE"] = "1"
ENV["AOS_HOME"] = str(PROTO)
NAMES = ("AOS_PARENT_STACK", "AOS_NOTIFY_BOX")
# the body asks who it is, like a tool of a real agent would, then idles
BODY = '#!/bin/sh\naos-agent ctl who --json > "$AOS_WS/who.json" 2> "$AOS_WS/who.err"\necho up > "$AOS_WS/up.txt"\nexec sleep 60\n'


def until(condition, timeout=20):
    return env_helper.until(condition, timeout)


@unittest.skipUnless(shutil.which("aos-daemon", path=ENV["PATH"]) and shutil.which("aos-post", path=ENV["PATH"]),
                     "aos-daemon and aos-post are required")
class AddParentDaemon(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="add-parent-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(os.path.realpath(self.temp.name))
        self.daemon = self.root / "stack"
        self.daemon.mkdir()
        self.definition = self.root / "def-exec"
        self.definition.mkdir()
        (self.definition / "interfaces.json").write_text('{"aos-agent": {}}\n')
        (self.definition / "_entry").write_text(BODY)
        (self.definition / "_entry").chmod(0o755)
        config = self.root / "daemon.json"
        config.write_text('{"interval_ms": 20, "procs": {}}\n')
        self.err = open(self.root / "daemon.err", "w")
        self.addCleanup(self.err.close)
        self.process = subprocess.Popen(["aos-daemon", str(config)], cwd=self.root, env=dict(ENV, AOS_STACK=str(self.daemon)),
                                        stdout=subprocess.DEVNULL, stderr=self.err)
        self.addCleanup(self.stop_daemon)
        until(lambda: (self.daemon / "state.json").exists())
        self.mom = Path(self.attach("mom")[0])

    def stop_daemon(self):
        if self.process.poll() is None:
            subprocess.run(["aos-daemon-ctl", "-d", str(self.daemon), "shutdown", "--timeout-s", "20"],
                           cwd=self.root, env=ENV, capture_output=True, text=True, timeout=25)
        self.process.wait(timeout=25)

    def run_agent(self, *args, stack=None, **extra):
        env = dict(ENV, AOS_DAEMON=str(self.daemon), **extra)
        if stack is not None:
            env["AOS_STACK"] = str(stack)
        return subprocess.run([sys.executable, str(BIN), "ctl", *args], cwd=self.root, env=env,
                              capture_output=True, text=True, timeout=60)

    def attach(self, name, *flags, stack=None, **extra):
        ws = self.root / ("ws-" + name)
        ws.mkdir()
        p = self.run_agent("add", "-n", name, "-w", str(ws), *flags, str(self.definition), stack=stack, **extra)
        self.assertEqual(p.returncode, 0, p.stderr)
        until(lambda: (ws / "up.txt").exists())
        return p.stdout.strip().splitlines()[-1], ws

    def tool(self, path, args, stack):
        env = dict(ENV, AOS_DAEMON=str(self.daemon), AOS_STACK=str(stack), AOS_WS=str(self.root))
        p = subprocess.run([str(path)], input=json.dumps(args), cwd=self.root, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return p.stdout

    def row(self, name):
        return self.table()[name]

    def table(self):
        return json.loads((self.daemon / "procs_state.json").read_text())["procs"]

    def cell_envs(self, name):
        """the registered names in the launch single the daemon keeps in the cell (exec type: exec.json#/exec)"""
        envs = json.loads((self.daemon / "procs" / name / "exec.json").read_text())["exec"].get("envs", {})
        return {k: envs[k] for k in NAMES if k in envs}

    def who(self, name, ws):
        """what the running child itself got from ctl who --json (asked from inside its body)"""
        until(lambda: (ws / "who.json").stat().st_size > 0 if (ws / "who.json").exists() else False)
        return json.loads((ws / "who.json").read_text())

    def test_add_without_envs_is_attached_as_before(self):
        """guard rail (修訂 1): with or without a parent on the table behind AOS_STACK, the row is the same and nothing is recorded"""
        under, ws = self.attach("under")
        p = self.run_agent("add", "-n", "fromtool", "-w", str(ws), str(self.definition), stack=self.mom / "tools" / "agents_ctl")
        self.assertEqual(p.returncode, 0, p.stderr)
        until(lambda: "fromtool" in self.table())
        plain, fromtool = self.row("under"), self.row("fromtool")
        for key in sorted(set(plain) | set(fromtool)):
            if key in ("stack", "pid", "started_at", "started_at_ticks", "boot_id", "pgid", "since", "restarts", "phase", "state"):
                continue
            with self.subTest(key=key):
                self.assertEqual(plain.get(key), fromtool.get(key))
        self.assertIsNotNone(fromtool.get("exec"))
        self.assertFalse((self.daemon / "procs" / "fromtool" / "exec.json").exists())
        j = json.loads(self.run_agent("who", "--json", "--stack", str(self.daemon / "procs" / "fromtool")).stdout)
        self.assertEqual((j["parent"], j["notify_box"]), (None, None))

    def same_row(self, plain, other):
        for key in sorted(set(plain) | set(other)):
            if key in ("stack", "pid", "started_at", "started_at_ticks", "boot_id", "pgid", "since", "restarts", "phase", "state", "last_exit"):
                continue
            with self.subTest(key=key):
                a, b = (json.loads(json.dumps(r.get(key)).replace("ws-" + n, "ws-NAME")) for r, n in ((plain, "under"), (other, "inherit")))
                self.assertEqual(a, b)

    def test_caller_environment_with_the_two_names_changes_nothing(self):
        """guard rail (head-core 11-14): the requester's own environment already has AOS_PARENT_STACK / AOS_NOTIFY_BOX;
        an add without envs is still the same row as from a clean environment, with no exec.json, and the child sees null"""
        self.attach("under")
        given = {"AOS_PARENT_STACK": "/x/inherited/mom", "AOS_NOTIFY_BOX": "/x/inherited/mom/mailbox"}
        _, ws = self.attach("inherit", stack=self.mom / "tools" / "agents_ctl", **given)
        self.same_row(self.row("under"), self.row("inherit"))
        self.assertIsInstance(self.row("inherit").get("exec"), (str, list))
        self.assertFalse((self.daemon / "procs" / "inherit" / "exec.json").exists())
        j = json.loads(self.run_agent("who", "--json", "--stack", str(self.daemon / "procs" / "inherit")).stdout)
        self.assertEqual((j["parent"], j["notify_box"]), (None, None))

    def test_set_def_still_works_on_a_row_without_envs(self):
        """guard rail (head-core 11-14): ctl set-def on a row added without envs (from a tool cell, so a parent could be found)
        is accepted, the row stays unwrapped, and the new definition runs"""
        def body(folder, text):
            folder.mkdir()
            (folder / "interfaces.json").write_text('{"aos-agent": {}}\n')
            # like test_set_def: leaves when ctl stop writes ctl.json (moved aside, so the next start does not see it)
            (folder / "_entry").write_text('#!/bin/sh\necho %s >> "$AOS_WS/ran.txt"\n'
                                           'while [ ! -e "$AOS_STACK/ctl.json" ]; do sleep 0.05; done\n'
                                           'mv "$AOS_STACK/ctl.json" "$AOS_STACK/ctl.seen.$$"\n' % text)
            (folder / "_entry").chmod(0o755)
        old, new = self.root / "def-old", self.root / "def-new"
        body(old, "old")
        body(new, "new")
        ws = self.root / "ws-sd"
        ws.mkdir()
        tool = self.mom / "tools" / "agents_ctl"
        p = self.run_agent("add", "-n", "sd", "-w", str(ws), str(old), stack=tool)
        self.assertEqual(p.returncode, 0, p.stderr)
        until(lambda: (ws / "ran.txt").exists())
        p = self.run_agent("set-def", "sd", str(new), stack=tool)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("definition of sd is now %s" % new, p.stdout)
        until(lambda: (ws / "ran.txt").read_text().split() == ["old", "new"])
        self.assertEqual(os.path.normpath(self.daemon / self.row("sd")["def"]), str(new))     # def is kept relative to the daemon
        self.assertFalse((self.daemon / "procs" / "sd" / "exec.json").exists())

    def test_parent_is_looked_up_from_the_requester(self):
        """--envs from the agent's root, a tool cell and a hook cell: parent = the agent's root stack; the child sees it itself"""
        for n, stack in enumerate((self.mom, self.mom / "tools" / "agents_ctl", self.mom / "hookeds" / "guard")):
            with self.subTest(stack=str(stack)):
                kid, ws = self.attach("kid%d" % n, "--envs", "FAKE_TOKEN=secret-value-1114", stack=stack)
                self.assertEqual(self.cell_envs("kid%d" % n), {"AOS_PARENT_STACK": str(self.mom), "AOS_NOTIFY_BOX": ""})
                j = self.who("kid%d" % n, ws)
                self.assertEqual((j["name"], j["parent"], j["notify_box"]), ("kid%d" % n, str(self.mom), None))
                self.assertNotIn("secret-value-1114", (ws / "who.json").read_text() + (ws / "who.err").read_text())
        elsewhere = self.root / "elsewhere" / "kid"          # a stack outside the daemon's procs/: the cell is that stack
        kid, ws = self.attach("far", "-s", str(elsewhere), "--envs", "X=1", stack=self.mom / "tools" / "subagent")
        self.assertEqual(json.loads((elsewhere / "exec.json").read_text())["exec"]["envs"]["AOS_PARENT_STACK"], str(self.mom))
        self.assertEqual(self.who("far", ws)["parent"], str(self.mom))
        j = json.loads(self.run_agent("who", "--json", "--stack", str(elsewhere)).stdout)
        self.assertEqual(j["parent"], str(self.mom))
        p = self.run_agent("add", "-n", "nobody", "-w", str(self.root), "--envs", "X=1", str(self.definition))
        self.assertEqual(p.returncode, 0, p.stderr)
        until(lambda: (self.daemon / "procs" / "nobody" / "exec.json").exists())
        self.assertEqual(self.cell_envs("nobody"), {"AOS_PARENT_STACK": "", "AOS_NOTIFY_BOX": ""})

    def test_explicit_values_win_and_must_agree(self):
        kid, ws = self.attach("given", "--parent", "/x/mom", "--notify-box", "/x/mom/mailbox", stack=self.mom)
        self.assertEqual(self.cell_envs("given"), {"AOS_PARENT_STACK": "/x/mom", "AOS_NOTIFY_BOX": "/x/mom/mailbox"})
        self.assertEqual((self.who("given", ws)["parent"], self.who("given", ws)["notify_box"]), ("/x/mom", "/x/mom/mailbox"))
        kid, ws = self.attach("none", "--parent", "", stack=self.mom)
        self.assertEqual(self.cell_envs("none"), {"AOS_PARENT_STACK": "", "AOS_NOTIFY_BOX": ""})
        self.attach("same", "--parent", "/x/p", "--envs", "AOS_PARENT_STACK=/x/p")
        for flags, said in ((("--parent", "/x/a", "--envs", "AOS_PARENT_STACK=/x/b"), "--parent"),
                            (("--notify-box", "/x/a", "--envs", "AOS_NOTIFY_BOX=/x/b"), "--notify-box"),
                            (("--parent", "x/rel"), "--parent"),
                            (("--notify-box", "/x/../y"), "--notify-box"),
                            (("--envs", "AOS_PARENT_STACK=rel"), "--envs AOS_PARENT_STACK"),
                            (("--envs", "AOS_NOTIFY_BOX=/a/.."), "--envs AOS_NOTIFY_BOX")):
            with self.subTest(flags=flags):
                p = self.run_agent("add", "-n", "bad", "-w", str(self.root), *flags, str(self.definition), stack=self.mom)
                self.assertEqual(p.returncode, 1)
                self.assertIn("ArgumentsBad", p.stderr)
                self.assertIn(said, p.stderr)
                self.assertNotIn("bad", self.table())

    def test_tools_subagent_and_agents_ctl(self):
        """subagent add without a box gives the parent's mailbox; an explicit '' wins; agents_ctl with envs records the parent"""
        self.tool(SUBAGENT, {"op": "add", "def": str(self.definition), "name": "sub1", "ws": "ws-sub1"}, self.mom / "tools" / "subagent")
        until(lambda: (self.root / "ws-sub1" / "up.txt").exists())
        self.assertEqual(self.cell_envs("sub1"), {"AOS_PARENT_STACK": str(self.mom), "AOS_NOTIFY_BOX": str(self.mom / "mailbox")})
        j = self.who("sub1", self.root / "ws-sub1")
        self.assertEqual((j["parent"], j["notify_box"]), (str(self.mom), str(self.mom / "mailbox")))
        self.tool(SUBAGENT, {"op": "add", "def": str(self.definition), "name": "sub2", "ws": "ws-sub2", "envs": {"AOS_NOTIFY_BOX": ""}},
                  self.mom / "tools" / "subagent")
        until(lambda: (self.daemon / "procs" / "sub2" / "exec.json").exists())
        self.assertEqual(self.cell_envs("sub2"), {"AOS_PARENT_STACK": str(self.mom), "AOS_NOTIFY_BOX": ""})
        (self.root / "ws-ac").mkdir()
        self.tool(AGENTS_CTL, {"op": "add", "def": str(self.definition), "name": "ac", "ws": str(self.root / "ws-ac"), "envs": {"X": "1"}},
                  self.mom / "tools" / "agents_ctl")
        until(lambda: (self.daemon / "procs" / "ac" / "exec.json").exists())
        self.assertEqual(self.cell_envs("ac"), {"AOS_PARENT_STACK": str(self.mom), "AOS_NOTIFY_BOX": ""})


class ForkAndSubagentThroughKernel(unittest.TestCase):
    """only AOS_KERNEL (no AOS_DAEMON): the parent is looked up through the kernel's table too"""

    def setUp(self):
        sys.path.insert(0, str(PROTO / "py" / "tools" / "agent" / "subagent" / "tests"))
        from kernel_fixture import KernelFixture
        self.fixture = KernelFixture()
        self.addCleanup(self.fixture.close)

    def cell(self, cell):
        """the launch single lives in the proc's own stack (its cell): exec.json for exec type, loop.json for loop type"""
        exec_ = json.loads(next(cell / f for f in ("exec.json", "loop.json") if (cell / f).exists()).read_text())["exec"]
        return {k: exec_["envs"][k] for k in NAMES if k in exec_.get("envs", {})}

    def test_fork_and_subagent(self):
        f = self.fixture
        f.save(f.mom / "history.jsonl", {"role": "assistant", "tool_calls": [{"id": "fork-call"}]})
        r = f.tool(FORK, {"goal": "Return a short answer.", "keep": True, "timeout_s": 10}, AOS_STACK=str(f.mom / "tools/fork"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        kid = Path(next(line.removeprefix("details: ") for line in r.stdout.splitlines() if line.startswith("details: ")))
        self.assertEqual(self.cell(kid), {"AOS_PARENT_STACK": str(f.mom), "AOS_NOTIFY_BOX": ""})
        r = f.tool(SUBAGENT, {"op": "add", "def": str(f.definition), "name": "kid", "ws": "kid"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.cell(f.mom.parent / "kid"), {"AOS_PARENT_STACK": str(f.mom), "AOS_NOTIFY_BOX": str(f.mom / "mailbox")})


    def test_kernel_that_does_not_answer_only_slows_the_add(self):
        """head-core 11-14: AOS_KERNEL points at a box whose reader forwards every letter to the real kernel except the
        procs_state_path query, which nobody answers. The add with envs still succeeds, about QUERY_S (3 s) later, with parent ''."""
        import threading
        f = self.fixture
        proxy = f.root / "proxy"
        subprocess.run(["aos-post", "init", str(proxy)], check=True, env=f.env, stdout=subprocess.DEVNULL)
        real = f.daemon_stack / "requests" / "new"
        stop, held = threading.Event(), []

        def forward():
            while not stop.is_set():
                for name in sorted(os.listdir(proxy / "new")):
                    try:
                        envelope = json.loads((proxy / "new" / name / "letter.json").read_text())
                    except (OSError, ValueError):
                        continue
                    body = envelope.get("body", {})
                    if isinstance(body, dict) and "procs_state_path" in body:
                        if name not in held:
                            held.append(name)          # the query: never answered, left for the asker to take back
                        continue
                    reply = envelope.get("reply_to")
                    if isinstance(reply, str) and not os.path.isabs(reply):
                        # aos-post keeps reply_to relative to the box it was sent to; the real kernel resolves it from its own box
                        envelope["reply_to"] = os.path.abspath(os.path.join(proxy, reply))
                        (proxy / "new" / name / "letter.json").write_text(json.dumps(envelope))
                    try:
                        os.rename(proxy / "new" / name, real / name)
                    except OSError:
                        pass
                time.sleep(0.02)

        t = threading.Thread(target=forward, daemon=True)
        t.start()
        self.addCleanup(t.join, 5)
        self.addCleanup(stop.set)
        env = dict(f.env, AOS_KERNEL=str(proxy), AOS_STACK=str(f.mom / "tools" / "agents_ctl"))
        for name, kernel in (("slow", str(proxy)), ("fast", f.env["AOS_KERNEL"])):
            with self.subTest(kernel=name):
                start = time.monotonic()
                r = subprocess.run(["aos-agent", "ctl", "add", "--envs", "X=1", "--name", name, "--stack", str(f.root / "agents" / name),
                                    str(f.definition)], cwd=f.ws, env=dict(env, AOS_KERNEL=kernel), capture_output=True, text=True, timeout=60)
                took = time.monotonic() - start
                print("%s add: rc=%d took %.1f s" % (name, r.returncode, took), flush=True)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                want = "" if name == "slow" else str(f.mom)
                self.assertEqual(self.cell(f.root / "agents" / name), {"AOS_PARENT_STACK": want, "AOS_NOTIFY_BOX": ""})
                if name == "slow":
                    self.assertGreaterEqual(took, 2.9)
                    self.assertEqual(len(held), 1)
                    self.assertEqual(os.listdir(proxy / "new"), [])      # the unanswered query was taken back
                else:
                    self.assertLess(took, 2.9)


if __name__ == "__main__":
    unittest.main()
