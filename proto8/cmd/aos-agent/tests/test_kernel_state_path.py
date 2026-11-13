"""Test aos-agent ctl with AOS_KERNEL set: table commands ask it where the table is (query letter) and read that file, letter commands read only their own reply; a fake kernel answers, a real aos-daemon sits behind it."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
BIN = PROTO / "cmd" / "aos-agent" / "bin" / "aos-agent"
DAEMON = os.environ.get("AOS_TEST_DAEMON_BIN", "aos-daemon")     # another aos-daemon build to test against (optional)
ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
ENV["PATH"] = ":".join(str(p) for p in sorted((PROTO / "impls").glob("*/bin"))) + ":" + ":".join(
    str(p) for p in sorted((PROTO / "cmd").glob("*/bin"))) + ":" + ENV["PATH"]
ENV["PYTHONDONTWRITEBYTECODE"] = "1"

sys.path[:0] = [str(PROTO / "py"), str(PROTO / "lib")]
import daemon_ctl as dc  # noqa: E402
WIRED = callable(getattr(dc, "state_path", None))   # aos-agent uses daemon_ctl.state_path only once the wiring is in


def until(cond, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = cond()
        if v:
            return v
        time.sleep(0.05)
    raise AssertionError("timed out")


class FakeKernel(threading.Thread):
    """Stands in for a kernel on mailbox BOX. A procs_state_path query is answered with `table` (answers=True) or dropped
    (answers=False: a kernel that only attaches procs); `refuse` answers everything else with that error; any other letter
    is forwarded to the real daemon's mailbox under the same name with the sender's reply box, so the daemon replies itself."""

    def __init__(self, box, daemon_box, table, answers=True, refuse=None):
        super().__init__(daemon=True)
        self.box, self.daemon_box, self.table, self.answers, self.refuse = Path(box), str(daemon_box), table, answers, refuse
        self.seen, self.stop = [], threading.Event()

    def post(self, args, body):
        subprocess.run(["aos-post", "send"] + args, input=json.dumps(body), text=True, stdout=subprocess.DEVNULL, check=True, env=ENV)

    def run(self):
        while not self.stop.is_set():
            for name in sorted(os.listdir(self.box / "new")):
                cur = self.box / "cur" / name
                try:
                    os.rename(self.box / "new" / name, cur)
                except OSError:
                    continue
                letter = json.loads((cur / "letter.json").read_text())
                body = letter["body"]
                self.seen.append(body)
                reply_to = os.path.normpath(os.path.join(self.box, letter["reply_to"])) if letter.get("reply_to") else None
                if "procs_state_path" in body:
                    if self.answers and reply_to:
                        self.post(["--in-reply-to", name, reply_to], {"applied": True, "procs_state_path": self.table})
                elif self.refuse:
                    if reply_to:
                        self.post(["--in-reply-to", name, reply_to], {"applied": False, "error": self.refuse})
                else:
                    self.post((["--reply-to", reply_to] if reply_to else []) + [self.daemon_box, name], body)
                shutil.rmtree(cur)
            time.sleep(0.02)

    def close(self):
        self.stop.set()
        self.join(5)


@unittest.skipUnless(WIRED, "aos-agent is not wired to daemon_ctl.state_path yet (kernel-framework batch 5 wiring patch)")
class KernelStatePath(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="kernel-state-path-")))
        self.d = self.tmp / "stack"
        self.d.mkdir()
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        (self.tmp / "daemon.json").write_text('{"interval_ms": 20, "procs": {}}\n')
        self.body = self.tmp / "body"
        self.body.mkdir()
        (self.body / "interfaces.json").write_text('{"aos-agent": {}}\n')
        # a body that stays until a stop is written into its ctl window (a pause is left alone), then takes the window with it
        (self.body / "_entry").write_text('#!/bin/sh\nwhile ! grep -q stop "$AOS_STACK/ctl.json" 2>/dev/null; do sleep 0.05; done\n'
                                          'rm -f "$AOS_STACK/ctl.json"\n')
        (self.body / "_entry").chmod(0o755)
        self.err = open(self.tmp / "daemon.err", "w")
        self.p = subprocess.Popen([DAEMON, str(self.tmp / "daemon.json")], cwd=self.tmp, env=dict(ENV, AOS_STACK=str(self.d)),
                                  stdout=subprocess.DEVNULL, stderr=self.err)
        until(lambda: (self.d / "state.json").exists())
        r = self.agent("ctl", "add", "-n", "ann", "-w", str(self.ws), str(self.body), AOS_DAEMON=str(self.d))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.box = self.tmp / "station" / "requests"            # what AOS_KERNEL points at
        subprocess.run(["aos-post", "init", str(self.box)], check=True, stdout=subprocess.DEVNULL, env=ENV)
        self.elsewhere = self.tmp / "elsewhere"                 # a cwd with no ./.stack
        self.elsewhere.mkdir()
        self.kernel = None

    def tearDown(self):
        if self.kernel:
            self.kernel.close()
        try:
            self.p.send_signal(signal.SIGTERM)                 # only the daemon this test started
            self.p.wait(timeout=20)
        finally:
            self.err.close()
            root = str(self.tmp)
            for pid in (int(n) for n in os.listdir("/proc") if n.isdigit()):   # leftovers: only by cwd inside this test's folder
                try:
                    cwd = os.readlink("/proc/%d/cwd" % pid)
                except OSError:
                    continue
                if pid != os.getpid() and (cwd == root or cwd.startswith(root + os.sep)):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass
            shutil.rmtree(self.tmp, ignore_errors=True)

    def agent(self, *args, **env):
        return subprocess.run([sys.executable, str(BIN), *args], capture_output=True, text=True, timeout=60,
                              env=dict(ENV, **env), cwd=self.elsewhere if hasattr(self, "elsewhere") else self.tmp)

    def serve(self, table=None, **kw):
        self.kernel = FakeKernel(self.box, self.d / "procs_requests", str(table or self.d / "procs_state.json"), **kw)
        self.kernel.start()

    def rows(self):
        return json.loads((self.d / "procs_state.json").read_text())["procs"]

    def queries(self):
        return [b for b in self.kernel.seen if "procs_state_path" in b]

    def test_table_commands_read_the_file_the_kernel_answers_with(self):
        shown = self.tmp / "shown"                              # a trimmed table somewhere else, under another file name
        (shown / "procs" / "kid").mkdir(parents=True)
        (shown / "table.json").write_text(json.dumps({"procs": {
            "kid": {"phase": "running", "stack": str(shown / "procs" / "kid"), "ws": str(self.ws)},
            "rel": {"phase": "stopped", "stack": "procs/rel"}}}))
        self.serve(shown / "table.json")
        env = dict(AOS_KERNEL=str(self.box), AOS_DAEMON=str(self.d))   # AOS_DAEMON is passed on but must not be read
        r = self.agent("ctl", "ls", "--json", **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = {row["name"]: row["stack"] for row in json.loads(r.stdout)}
        self.assertEqual(got, {"kid": str(shown / "procs" / "kid"), "rel": str(shown / "procs" / "rel")})   # not ann
        self.assertEqual(self.queries(), [{"procs_state_path": True}])                                  # asked once per run
        r = self.agent("ctl", "who", "--json", "--stack", str(shown / "procs" / "kid" / "tools" / "x"), **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        who = json.loads(r.stdout)
        self.assertEqual((who["name"], who["stack"], who["daemon"]), ("kid", str(shown / "procs" / "kid"), str(shown)))
        r = self.agent("ctl", "where", "rel", **env)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, str(shown / "procs" / "rel")), r.stderr)

    def test_only_AOS_KERNEL_is_enough(self):
        self.serve()
        r = self.agent("ctl", "ls", "--json", AOS_KERNEL=str(self.box))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([(row["name"], row["stack"]) for row in json.loads(r.stdout)], [("ann", str(self.d / "procs" / "ann"))])
        r = self.agent("ctl", "state", "-t", "ann", "state", AOS_KERNEL=str(self.box))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.box / "reply" / "new").is_dir())      # a shell has no AOS_STACK: replies come to $AOS_KERNEL/reply/

    def test_nobody_answers_is_KernelFailed_not_a_read_of_AOS_DAEMON(self):
        env = dict(AOS_KERNEL=str(self.box), AOS_DAEMON=str(self.d))
        started = time.monotonic()
        r = self.agent("ctl", "ls", "--json", **env)                # default wait: 3 s
        took = time.monotonic() - started
        self.assertEqual((r.returncode, r.stdout), (1, ""), r.stderr)
        self.assertIn("error: KernelFailed no reply from AOS_KERNEL=%s within 3 s" % self.box, r.stderr)
        self.assertGreaterEqual(took, 3)
        self.assertLess(took, 8)
        started = time.monotonic()
        r = self.agent("ctl", "who", "--json", "--timeout-s", "0.3", "--stack", str(self.d / "procs" / "ann"), **env)
        self.assertEqual((r.returncode, r.stdout), (1, ""), r.stderr)
        self.assertIn("error: KernelFailed", r.stderr)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(os.listdir(self.box / "new"), [])          # unanswered queries are withdrawn

    def test_letter_commands_work_with_a_kernel_that_only_attaches(self):
        self.serve(answers=False)
        env = dict(AOS_KERNEL=str(self.box))                        # no AOS_DAEMON at all
        stack = self.tmp / "stacks" / "bob"
        r = self.agent("ctl", "add", "-n", "bob", "-w", str(self.ws), "-s", str(stack), str(self.body), **env)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, str(stack)), r.stderr)
        self.assertIn("routing via AOS_KERNEL=", r.stderr)
        until(lambda: self.rows().get("bob", {}).get("phase") == "running")
        r = self.agent("ctl", "stop", "bob", **env)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "stop accepted for bob; aos-agent ctl start --target bob to carry on"), r.stderr)
        until(lambda: self.rows()["bob"]["phase"] == "stopped")
        r = self.agent("ctl", "start", "bob", **env)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "start accepted for bob"), r.stderr)
        until(lambda: self.rows()["bob"]["phase"] == "running")
        r = self.agent("ctl", "sleep", "-t", "bob", **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        until(lambda: self.rows()["bob"]["phase"] == "sleeping")
        r = self.agent("ctl", "wake", "bob", **env)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "wake accepted for bob"), r.stderr)
        until(lambda: self.rows()["bob"]["phase"] == "running")
        r = self.agent("ctl", "rm", "bob", **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("rm accepted for bob", r.stdout)
        until(lambda: "bob" not in self.rows())
        self.assertTrue(stack.is_dir())
        self.assertEqual(self.queries(), [])                        # none of them asked for the table
        r = self.agent("ctl", "ls", "--timeout-s", "0.3", **env)    # a table command against this kernel: it never answers
        self.assertEqual(r.returncode, 1)
        self.assertIn("error: KernelFailed", r.stderr)

    def test_add_without_a_stack_prints_nothing_and_says_where_to_ask(self):
        self.serve(answers=False)
        r = self.agent("ctl", "add", "-n", "cat", "-w", str(self.ws), str(self.body), AOS_KERNEL=str(self.box))
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)
        self.assertIn("aos-agent ctl where cat", r.stderr)
        until(lambda: "cat" in self.rows())

    def test_refused_letter_carries_the_code(self):
        self.serve(refuse={"code": "SlotMissing", "msg": "too many procs"})
        r = self.agent("ctl", "add", "-n", "bob", "-w", str(self.ws), str(self.body), AOS_KERNEL=str(self.box))
        self.assertEqual((r.returncode, r.stdout), (1, ""), r.stderr)
        self.assertIn("error: AddRejected the add letter was refused: SlotMissing too many procs", r.stderr)
        r = self.agent("ctl", "stop", "ann", AOS_KERNEL=str(self.box))
        self.assertIn("error: CtlRejected the stop letter was refused: SlotMissing too many procs", r.stderr)

    def test_no_reply_to_a_letter_is_DaemonFailed_and_the_letter_is_withdrawn(self):
        r = self.agent("ctl", "stop", "--timeout-s", "0.5", "ann", AOS_KERNEL=str(self.box), AOS_DAEMON=str(self.d))
        self.assertEqual(r.returncode, 1)
        self.assertIn("error: DaemonFailed no reply to the stop letter sent to AOS_KERNEL=%s within 0.5 s; letter withdrawn" % self.box, r.stderr)
        self.assertEqual(os.listdir(self.box / "new"), [])
        self.assertEqual(self.rows()["ann"]["phase"], "running")

    def test_rm_purge_and_pause_look_the_agent_up_through_the_kernel(self):
        self.serve()
        env = dict(AOS_KERNEL=str(self.box))
        r = self.agent("ctl", "pause", "--no-wait", "ann", **env)   # writes ann's ctl window: needs its stack from the table
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((self.d / "procs" / "ann" / "ctl.json").read_text())["cmd"], "pause")
        r = self.agent("ctl", "rm", "--purge", "-y", "ann", **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("removed ann (deleted stack %s)" % (self.d / "procs" / "ann"), r.stdout)
        self.assertNotIn("ann", self.rows())
        self.assertFalse((self.d / "procs" / "ann").exists())
        self.assertTrue(self.queries())

    def test_set_def_reads_the_row_through_the_kernel(self):
        self.serve()
        env = dict(AOS_KERNEL=str(self.box))
        new = self.tmp / "new"
        shutil.copytree(self.body, new)
        r = self.agent("ctl", "set-def", "ann", str(new), **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("definition of ann set to %s for its next start" % new, r.stdout)
        self.assertEqual(self.rows()["ann"]["def"], os.path.relpath(self.body, self.d))        # still the old one until it starts again
        r = self.agent("ctl", "set-def", "--restart", "ann", str(new), **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("definition of ann is now %s" % new, r.stdout)
        self.assertEqual((self.rows()["ann"]["phase"], os.path.normpath(os.path.join(self.d, self.rows()["ann"]["def"]))), ("running", str(new)))

    def test_without_AOS_KERNEL_nothing_is_asked(self):
        r = self.agent("ctl", "ls", "--json", AOS_DAEMON=str(self.d))
        self.assertEqual([row["name"] for row in json.loads(r.stdout)], ["ann"], r.stderr)
        r = self.agent("ctl", "who", "--json", "--stack", str(self.d / "procs" / "ann"), AOS_DAEMON=str(self.d))
        self.assertEqual(json.loads(r.stdout)["daemon"], str(self.d))
        r = self.agent("ctl", "stop", "ann", AOS_DAEMON=str(self.d))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("stopped, stack kept (%s)" % (self.d / "procs" / "ann"), r.stdout)
        self.assertEqual(os.listdir(self.box / "new"), [])
        self.assertFalse((self.box / "reply").exists())

    def test_daemon_flag_names_the_daemon_and_asks_nobody(self):
        started = time.monotonic()
        r = self.agent("-d", str(self.d), "ctl", "ls", "--json", AOS_KERNEL=str(self.box))   # nobody serves the kernel box
        self.assertEqual([row["name"] for row in json.loads(r.stdout)], ["ann"], r.stderr)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(os.listdir(self.box / "new"), [])
        self.assertFalse((self.box / "reply").exists())

    def test_real_daemon_as_the_kernel(self):
        """AOS_KERNEL = the daemon's own mailbox: needs an aos-daemon that answers procs_state_path (kernel-framework batch 4)."""
        r = self.agent("ctl", "ls", "--json", AOS_KERNEL=str(self.d / "procs_requests"))
        if r.returncode and "does not carry procs_state_path" in r.stderr:
            self.skipTest("this aos-daemon does not answer procs_state_path yet (set AOS_TEST_DAEMON_BIN to one that does)")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([(row["name"], row["stack"]) for row in json.loads(r.stdout)], [("ann", str(self.d / "procs" / "ann"))])


if __name__ == "__main__":
    unittest.main()
