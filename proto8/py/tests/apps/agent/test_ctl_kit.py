"""Test aos-agent ctl add / set-def --kit on a real aos-daemon: the kit's system.txt and tools.json become the agent's own copies in its stack (replacing ones already there), the definition is not changed; eca definitions take kits too; bad kits are refused before anything changes; a failed attach puts replaced copies back."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from env_helper import until  # noqa: E402  同夾的共用零件


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[4]
BIN = PROTO / "bin" / "aos-agent"
KITS = PROTO / "templates" / "agents" / "kits"
ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
ENV["PATH"] = str(PROTO / "bin") + ":" + ENV["PATH"]
ENV["PYTHONDONTWRITEBYTECODE"] = "1"


class CtlKit(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="ctl-kit-")))
        self.d = self.tmp / "stack"
        self.d.mkdir()
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        (self.tmp / "daemon.json").write_text('{"interval_ms": 20, "procs": {}}\n')
        self.defn = self.definition("fsmish")
        self.err = open(self.tmp / "daemon.err", "w")
        self.p = subprocess.Popen(["aos-daemon", str(self.tmp / "daemon.json")], cwd=self.tmp, env=dict(ENV, AOS_STACK=str(self.d)),
                                  stdout=subprocess.DEVNULL, stderr=self.err)
        until(lambda: (self.d / "state.json").exists())

    def tearDown(self):
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

    def definition(self, name, eca=False, cli='{"kind": "claude"}\n'):
        """A body declaring system and tools (as agent-fsm does) that records the system text it sees, then waits for ctl.json."""
        d = self.tmp / name
        d.mkdir()
        (d / "interfaces.json").write_text(json.dumps({"aos-agent": {"tools": "tools.json", "system": "system.txt"}}))
        (d / "tools.json").write_text('{"tools": {}}\n')
        (d / "system.txt").write_text("stock system of %s\n" % name)
        if eca:
            (d / "cli.json").write_text(cli)
        (d / "_entry").write_text('#!/bin/sh\nhead -c 40 "$AOS_STACK/system.txt" >> "$AOS_STACK/seen.txt" 2>/dev/null || echo none >> "$AOS_STACK/seen.txt"\n'
                                  'while [ ! -e "$AOS_STACK/ctl.json" ]; do sleep 0.05; done\nrm -f "$AOS_STACK/ctl.json"\n')
        (d / "_entry").chmod(0o755)
        return d

    def agent(self, *args):
        return subprocess.run([str(BIN), "--daemon", str(self.d), *args], cwd=self.tmp, env=ENV, capture_output=True, text=True, timeout=90)

    def code(self, r):
        return r.stderr.strip().splitlines()[-1].split("error: ", 1)[1].split()[0] if "error: " in r.stderr else None

    def rows(self):
        try:
            return json.loads((self.d / "procs_state.json").read_text())["procs"]
        except (OSError, ValueError):
            return {}

    def stock(self):
        self.assertEqual((self.defn / "system.txt").read_text(), "stock system of fsmish\n")
        self.assertEqual((self.defn / "tools.json").read_text(), '{"tools": {}}\n')

    def test_add_writes_own_copies_before_start(self):
        r = self.agent("ctl", "add", "-n", "ann", "-w", str(self.ws), "--kit", str(KITS / "gather"), "fsmish")
        self.assertEqual(r.returncode, 0, r.stderr)
        st = self.d / "procs" / "ann"
        self.assertEqual(r.stdout.strip(), str(st))
        self.assertEqual((st / "system.txt").read_bytes(), (KITS / "gather" / "system.txt").read_bytes())
        self.assertEqual((st / "tools.json").read_bytes(), (KITS / "gather" / "tools.json").read_bytes())
        self.assertIn("kit ", r.stderr)
        self.assertIn("system reset -y", r.stderr)
        self.stock()
        until(lambda: (st / "seen.txt").exists())
        self.assertNotIn("stock system", (st / "seen.txt").read_text())     # the body saw the kit's text from its first start
        g = self.agent("system", "--target", "ann", "get", "-l")
        self.assertEqual(g.returncode, 0, g.stderr)
        self.assertTrue(g.stdout.startswith("agent\t"), g.stdout)

    def test_tools_ls_after_kit_does_not_ask_whether_the_stack_was_copied(self):
        """setdef-night-1118: the kit's tools.json layers straight on the stock packs; tools ls used to ask 'was the stack copied
        from another agent?'. AOS_HOME is set so the kit's $env pointers resolve (without it there is nothing to compare)."""
        self.assertEqual(self.agent("ctl", "add", "-n", "ann", "-w", str(self.ws), "--kit", str(KITS / "gather"), "fsmish").returncode, 0)
        r = subprocess.run([str(BIN), "--daemon", str(self.d), "tools", "--target", "ann", "ls"], cwd=self.tmp,
                           env=dict(ENV, AOS_HOME=str(PROTO)), capture_output=True, text=True, timeout=90)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("board_read", r.stdout)                      # the kit's tools are what it lists
        self.assertNotIn("copied from another agent", r.stderr)
        st = self.d / "procs" / "ann" / "tools.json"              # a copy that points at another definition's file still warns
        other = self.definition("other")
        st.write_text(json.dumps({"$override": str(other / "tools.json"), "tools": {}}))
        r = subprocess.run([str(BIN), "--daemon", str(self.d), "tools", "--target", "ann", "ls"], cwd=self.tmp,
                           env=dict(ENV, AOS_HOME=str(PROTO)), capture_output=True, text=True, timeout=90)
        self.assertIn("was the stack copied from another agent?", r.stderr)

    def test_add_kit_missing_or_incomplete(self):
        r = self.agent("ctl", "add", "-n", "ann", "--kit", str(self.tmp / "nope"), "fsmish")
        self.assertEqual((r.returncode, self.code(r)), (1, "KitMissing"), r.stderr)
        half = self.tmp / "half"
        half.mkdir()
        (half / "system.txt").write_text("x\n")
        r = self.agent("ctl", "add", "-n", "ann", "--kit", str(half), "fsmish")
        self.assertEqual((r.returncode, self.code(r)), (1, "KitMissing"), r.stderr)
        (half / "tools.json").write_text("[]\n")
        r = self.agent("ctl", "add", "-n", "ann", "--kit", str(half), "fsmish")
        self.assertEqual((r.returncode, self.code(r)), (1, "KitBad"), r.stderr)
        self.assertNotIn("ann", self.rows())
        self.assertFalse((self.d / "procs" / "ann" / "system.txt").exists())

    def test_add_eca_definition_takes_kit(self):
        """11-18 evening, the user: eca definitions take kits too. The copies land in the stack; stderr says the CLI's own tools stay."""
        self.definition("ecaish", eca=True)
        r = self.agent("ctl", "add", "-n", "eve", "-w", str(self.ws), "--kit", str(KITS / "gather"), "ecaish")
        self.assertEqual(r.returncode, 0, r.stderr)
        st = self.d / "procs" / "eve"
        self.assertEqual((st / "system.txt").read_bytes(), (KITS / "gather" / "system.txt").read_bytes())
        self.assertEqual((st / "tools.json").read_bytes(), (KITS / "gather" / "tools.json").read_bytes())
        self.assertIn("eca definition", r.stderr)
        self.assertIn("do not hold", r.stderr)
        self.assertEqual((self.tmp / "ecaish" / "system.txt").read_text(), "stock system of ecaish\n")
        self.assertIn("eve", self.rows())

    def test_add_eca_cli_naming_tools_refused(self):
        """A cli.json with its own tools key never reads the stack copy, so the kit would do nothing there."""
        self.definition("ecatools", eca=True, cli='{"kind": "claude", "tools": "tools.json"}\n')
        r = self.agent("ctl", "add", "-n", "eve", "--kit", str(KITS / "gather"), "ecatools")
        self.assertEqual((r.returncode, self.code(r)), (1, "KitBad"), r.stderr)
        self.assertIn("cli.json", r.stderr)
        self.assertNotIn("eve", self.rows())
        self.assertFalse((self.d / "procs" / "eve" / "system.txt").exists())

    def test_add_replaces_own_copy(self):
        """11-18 evening, the user: an own copy already there is replaced (no reset first)."""
        st = self.tmp / "own"
        st.mkdir()
        (st / "system.txt").write_text("my own words\n")
        r = self.agent("ctl", "add", "-n", "ann", "-s", str(st), "-w", str(self.ws), "--kit", str(KITS / "gather"), "fsmish")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("replaced %s" % (st / "system.txt"), r.stderr)
        self.assertIn("wrote %s" % (st / "tools.json"), r.stderr)
        self.assertEqual((st / "system.txt").read_bytes(), (KITS / "gather" / "system.txt").read_bytes())
        self.assertIn("ann", self.rows())

    def test_undo_puts_replaced_copies_back(self):
        """When the attach fails, undo removes what was new and writes back what was replaced; unsure failures keep them."""
        sys.path.insert(0, str(PROTO / "lib"))
        try:
            from aos.apps.agent.ctl import kit
            from aos.apps.agent.common import Fail
        finally:
            sys.path.pop(0)
        st = self.tmp / "own"
        st.mkdir()
        (st / "system.txt").write_text("my own words\n")
        steps = kit.plan(str(KITS / "review"), str(self.defn), str(st), "ann")
        self.assertEqual([a for _, _, _, a in steps], ["replace", "create"])
        made = kit.write(steps)
        self.assertEqual((st / "system.txt").read_bytes(), (KITS / "review" / "system.txt").read_bytes())
        kit.undo(made, Fail("WaitFailed", "x"))
        self.assertTrue((st / "tools.json").exists())            # unsure: kept
        kit.undo(made, Fail("AddRejected", "x"))
        self.assertEqual((st / "system.txt").read_text(), "my own words\n")
        self.assertFalse((st / "tools.json").exists())
        self.assertEqual(sorted(os.listdir(st)), ["system.txt"])  # no temp files left behind

    def test_add_same_copy_is_kept(self):
        st = self.tmp / "own"
        st.mkdir()
        shutil.copy(KITS / "gather" / "system.txt", st / "system.txt")
        r = self.agent("ctl", "add", "-n", "ann", "-s", str(st), "--kit", str(KITS / "gather"), "fsmish")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("kept (same)", r.stderr)
        self.assertEqual((st / "tools.json").read_bytes(), (KITS / "gather" / "tools.json").read_bytes())

    def test_add_stack_json_needs_plain_stack(self):
        r = self.agent("ctl", "add", "-n", "ann", "--stack-json", json.dumps(str(self.tmp / "s2")), "--kit", str(KITS / "gather"), "fsmish")
        self.assertEqual((r.returncode, self.code(r)), (1, "ArgumentsBad"), r.stderr)
        self.assertIn("--kit needs to know the stack", r.stderr)

    def test_set_def_kit_then_swap_then_reset(self):
        r = self.agent("ctl", "add", "-n", "ann", "--auto-restart", "-w", str(self.ws), "fsmish")
        self.assertEqual(r.returncode, 0, r.stderr)
        st = self.d / "procs" / "ann"
        until(lambda: (st / "seen.txt").exists())
        r = self.agent("ctl", "set-def", "--kit", str(KITS / "review"), "ann", "fsmish")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((st / "system.txt").read_bytes(), (KITS / "review" / "system.txt").read_bytes())
        self.assertEqual((st / "tools.json").read_bytes(), (KITS / "review" / "tools.json").read_bytes())
        self.assertNotIn("still overrides the old definition", r.stderr)
        self.stock()
        until(lambda: len((st / "seen.txt").read_text().splitlines()) >= 2)
        self.assertEqual(self.rows()["ann"].get("phase"), "running")
        # another kit straight over it (11-18 evening, the user: no reset first)
        size = (st / "seen.txt").stat().st_size                  # head -c 40 adds no newline: wait for growth, not lines
        r = self.agent("ctl", "set-def", "--kit", str(KITS / "gather"), "ann", "fsmish")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("replaced", r.stderr)
        self.assertEqual((st / "system.txt").read_bytes(), (KITS / "gather" / "system.txt").read_bytes())
        self.stock()
        until(lambda: (st / "seen.txt").stat().st_size > size)
        self.assertEqual(self.rows()["ann"].get("phase"), "running")
        # drop it with the existing reset commands: back to the definition's
        for what in ("system", "tools"):
            r = self.agent(what, "--target", "ann", "reset", "-y")
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((st / "system.txt").exists())
        self.assertFalse((st / "tools.json").exists())

    def test_help_mentions_kit(self):
        for sub in ("add", "set-def"):
            r = self.agent("ctl", sub, "--help")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("--kit KIT", r.stdout)
            self.assertIn("replaced", r.stdout)
            self.assertIn("eca definition", r.stdout)


if __name__ == "__main__":
    unittest.main()
