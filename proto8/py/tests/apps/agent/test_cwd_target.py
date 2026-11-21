"""aos-agent with no -t and no AOS_AGENT finds the target in the cwd (./.stack, then ./); with no -d and no AOS_DAEMON the daemon is two folders up from that stack (user 11-21).

A real isolated daemon at <root>/.stack (so the root looks like a tree root) hosts ann (stack <daemon>/procs/ann)
and bob (stack <root>/ws-bob/.stack, inside its workspace). The marker of an agent's stack is stderr.txt, which the
daemon writes in every proc's stack when it starts it.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import env_helper  # noqa: E402  同夾的共用零件


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[4]
BIN = PROTO / "bin" / "aos-agent"
ENV = env_helper.clean_env(path=[PROTO / "bin"])


@unittest.skipUnless(shutil.which("aos-daemon", path=ENV["PATH"]) and shutil.which("aos-post", path=ENV["PATH"]),
                     "aos-daemon and aos-post are required")
class CwdTarget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="cwd-target-")
        cls.root = Path(os.path.realpath(cls.temp.name))
        cls.daemon = cls.root / ".stack"
        cls.daemon.mkdir()
        cls.defn = cls.root / "def"
        cls.defn.mkdir()
        (cls.defn / "interfaces.json").write_text('{"aos-agent": {}}\n')
        (cls.defn / "_entry").write_text("#!/bin/sh\nexec sleep 60\n")
        (cls.defn / "_entry").chmod(0o755)
        config = cls.root / "daemon.json"
        config.write_text('{"interval_ms": 20, "procs": {}}\n')
        cls.err = open(cls.root / "daemon.err", "w")
        cls.process = subprocess.Popen(["aos-daemon", str(config)], cwd=cls.root, env=dict(ENV, AOS_STACK=str(cls.daemon)),
                                       stdout=subprocess.DEVNULL, stderr=cls.err)
        try:
            env_helper.until(lambda: (cls.daemon / "state.json").exists(), 20)
            (cls.root / "ws-bob").mkdir()
            cls.run_ok(["-d", str(cls.daemon), "ctl", "add", "-n", "ann", "-w", str(cls.root), str(cls.defn)])
            cls.run_ok(["-d", str(cls.daemon), "ctl", "add", "-n", "bob", "-w", str(cls.root / "ws-bob"),
                        "-s", str(cls.root / "ws-bob" / ".stack"), str(cls.defn)])
            cls.ann = cls.daemon / "procs" / "ann"
            cls.bob = cls.root / "ws-bob" / ".stack"
            env_helper.until(lambda: (cls.ann / "stderr.txt").exists() and (cls.bob / "stderr.txt").exists(), 20)
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if cls.process.poll() is None:
            subprocess.run(["aos-daemon-ctl", "-d", str(cls.daemon), "shutdown", "--timeout-s", "20"],
                           cwd=cls.root, env=ENV, capture_output=True, text=True, timeout=25)
        cls.process.wait(timeout=25)
        cls.err.close()
        cls.temp.cleanup()

    @classmethod
    def run_ok(cls, args):
        p = subprocess.run([sys.executable, str(BIN), *args], cwd=cls.root, env=ENV, capture_output=True, text=True, timeout=60)
        if p.returncode:
            raise AssertionError(p.stderr)
        return p.stdout

    def agent(self, cwd, *args, daemon=True, **env):
        e = dict(ENV, AOS_DAEMON=str(self.daemon)) if daemon else dict(ENV)
        e.update(env)
        return subprocess.run([sys.executable, str(BIN), *args], cwd=cwd, env=e, capture_output=True, text=True, timeout=60)

    def where(self, cwd, *args, **env):
        p = self.agent(cwd, "ctl", "where", *args, **env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stderr, "")                      # found in the cwd: nothing extra on stderr
        return p.stdout.strip()

    def test_inside_the_agents_stack(self):
        self.assertEqual(self.where(self.ann), str(self.ann))
        p = self.agent(self.ann, "ctl", "state")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.startswith("who       ann "), p.stdout)

    def test_folder_whose_dot_stack_is_the_agents_stack(self):
        self.assertEqual(self.where(self.root / "ws-bob"), str(self.bob))

    def test_flag_and_env_win_over_the_cwd(self):
        self.assertEqual(self.where(self.ann, "-t", "bob"), str(self.bob))
        self.assertEqual(self.where(self.ann, AOS_AGENT="bob"), str(self.bob))
        self.assertEqual(self.where(self.ann, "-t", "ann", AOS_AGENT="bob"), str(self.ann))
        self.assertEqual(self.where(self.ann, AOS_AGENT=""), str(self.ann))     # empty = not set

    def test_tree_root_is_not_a_target(self):
        p = self.agent(self.root, "ctl", "where")             # ./.stack is the daemon's (no stderr.txt), ./ is not a stack
        self.assertEqual(p.returncode, 1)
        self.assertIn("error: TargetMissing", p.stderr)
        self.assertIn("./.stack has no stderr.txt", p.stderr)
        self.assertIn("./ has no stderr.txt", p.stderr)

    def test_inside_a_subfolder_of_the_stack(self):
        sub = self.ann / "sub"
        sub.mkdir(exist_ok=True)
        p = self.agent(sub, "say", "hi")
        self.assertEqual(p.returncode, 1)
        self.assertIn("error: TargetMissing", p.stderr)
        self.assertIn("no ./.stack folder", p.stderr)
        self.assertFalse((self.ann / "queue").exists() and any((self.ann / "queue" / "new").glob("*")))

    def test_marked_but_not_on_the_table(self):
        stray = self.root / "stray" / ".stack"
        stray.mkdir(parents=True)
        (stray / "stderr.txt").write_text("")
        (stray.parent / "stderr.txt").write_text("")           # ./ would match too, but ./.stack is decided first
        p = self.agent(stray.parent, "ctl", "where")
        self.assertEqual(p.returncode, 1)
        self.assertIn("error: InstanceMissing ./.stack (%s) looks like an agent's stack" % stray, p.stderr)

    def where_no_daemon(self, cwd, *args, **env):
        p = self.agent(cwd, "ctl", "where", *args, daemon=False, **env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stderr, "")
        return p.stdout.strip()

    def test_daemon_two_levels_up_from_the_agents_stack(self):
        self.assertEqual(self.where_no_daemon(self.ann), str(self.ann))         # <daemon>/procs/ann: nothing to give
        p = self.agent(self.ann, "ctl", "ls", daemon=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("bob\t", p.stdout)
        self.assertEqual(self.where_no_daemon(self.ann, "-t", "bob"), str(self.bob))   # -t names an agent on that daemon
        self.assertEqual(self.where_no_daemon(self.ann, AOS_AGENT="bob"), str(self.bob))

    def test_daemon_flag_and_env_win_over_the_cwd(self):
        other = self.root / "other"
        other.mkdir(exist_ok=True)
        p = self.agent(self.ann, "ctl", "where", AOS_DAEMON=str(other))         # AOS_DAEMON wins, even if wrong
        self.assertIn("error: StateMissing", p.stderr)
        self.assertEqual(self.where_no_daemon(self.ann, "-d", str(self.daemon)), str(self.ann))

    def test_daemon_not_found_from_the_cwd(self):
        p = self.agent(self.root, "ctl", "ls", daemon=False)                   # tree root: ./.stack itself is not taken
        self.assertEqual(p.returncode, 1)
        self.assertIn("error: DaemonMissing no --daemon, AOS_DAEMON not set, and no daemon two levels up", p.stderr)
        self.assertIn("./.stack has no stderr.txt, ./ has no stderr.txt", p.stderr)
        p = self.agent(self.root / "ws-bob", "ctl", "where", daemon=False)    # bob's stack is ws-bob/.stack: two up is the root
        self.assertIn("error: DaemonMissing", p.stderr)
        self.assertIn("but %s two levels up is not a daemon's stack" % self.root, p.stderr)
        fake = self.root / "fake"
        ghost = fake / "procs" / "ghost"
        ghost.mkdir(parents=True, exist_ok=True)
        (ghost / "stderr.txt").write_text("")
        (fake / "procs_state.json").write_text('{"procs": {}}\n')
        p = self.agent(ghost, "ctl", "where", daemon=False)
        self.assertIn("error: DaemonMissing", p.stderr)
        self.assertIn("but the daemon %s two levels up has no agent with that stack" % fake, p.stderr)

if __name__ == "__main__":
    unittest.main()
