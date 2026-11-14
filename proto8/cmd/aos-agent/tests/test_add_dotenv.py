"""Test ctl add dotenv override wrapping and definition environment precedence on an isolated daemon."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
BIN = PROTO / "cmd" / "aos-agent" / "bin" / "aos-agent"
sys.path[:0] = [str(PROTO / "py"), str(PROTO / "lib")]
import daemon_ctl as dc
from daemon_ctl.entry import daemon_ref

ENV = {key: value for key, value in os.environ.items() if not key.startswith("AOS_")}
ENV["PATH"] = os.pathsep.join(str(path) for path in sorted((PROTO / "impls").glob("*/bin"))) + os.pathsep + os.pathsep.join(
    str(path) for path in sorted((PROTO / "cmd").glob("*/bin"))) + os.pathsep + ENV["PATH"]
ENV["PYTHONDONTWRITEBYTECODE"] = "1"


def until(condition, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = condition()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError("timed out")


class AddLetterDotenv(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="add-letter-dotenv-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.definition = self.root / "definition"
        self.definition.mkdir()
        entry = self.definition / "_entry"
        entry.write_text("#!/bin/sh\nexit 0\n")
        entry.chmod(0o755)
        self.daemon = self.root / "stack"
        self.daemon.mkdir()

    def spec(self, **options):
        _, letter = dc.add_letter(str(self.definition), name="ann", daemon=str(self.daemon), **options)
        return letter["procs_added"]["ann"]

    def test_override_and_envs_share_one_single(self):
        single = self.spec(dotenv_override=True, envs={"A": "1"})["exec"]
        self.assertEqual(single, {"argv": ["aos-exec", "--dotenv-override", "--",
                                         daemon_ref(str(self.definition), str(self.daemon))], "envs": {"A": "1"}})

    def test_override_only_and_kept_absolute_target(self):
        single = self.spec(dotenv_override=True, kept={"exec"})["exec"]
        self.assertEqual(single, {"argv": ["aos-exec", "--dotenv-override", "--", str(self.definition)]})

    def test_without_override_preserves_plain_and_envs_shapes(self):
        self.assertEqual(self.spec()["exec"], str(self.definition))
        self.assertEqual(self.spec(envs={"A": "1"})["exec"], {
            "argv": ["aos-exec", "--", daemon_ref(str(self.definition), str(self.daemon))], "envs": {"A": "1"}})

    def test_loop_directive_target_uses_original_exec_pointer(self):
        config = self.root / "body.json"
        config.write_text(json.dumps({"exec": {"$env": "BODY"}, "interval_ms": 20}))
        _, letter = dc.add_letter(str(config), name="ann", daemon=str(self.daemon), dotenv_override=True)
        self.assertEqual(letter["procs_added"]["ann"]["exec"]["argv"], [
            "aos-exec", "--dotenv-override", "--", daemon_ref(str(config) + "#/exec", str(self.daemon))])


@unittest.skipUnless(shutil.which("aos-daemon", path=ENV["PATH"]) and shutil.which("aos-post", path=ENV["PATH"]),
                     "aos-daemon and aos-post are required")
class AddDotenvDaemon(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="add-dotenv-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(os.path.realpath(self.temp.name))
        self.daemon = self.root / "stack"
        self.daemon.mkdir()
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.definition = self.root / "definition"
        self.definition.mkdir()
        (self.definition / "interfaces.json").write_text('{"aos-agent": {}}\n')
        (self.definition / ".env").write_text("PATH=%s:${PATH}\nMARK=from-env\n" % self.bin)
        entry = self.definition / "_entry"
        entry.write_text('#!/bin/sh\nprintf \'%s\\n%s\\n\' "$PATH" "$MARK" > "$AOS_WS/environment.txt"\nsleep 60\n')
        entry.chmod(0o755)
        config = self.root / "daemon.json"
        config.write_text('{"interval_ms": 20, "procs": {}}\n')
        self.env = dict(ENV, MARK="outside")
        self.err = open(self.root / "daemon.err", "w")
        self.addCleanup(self.err.close)
        self.process = subprocess.Popen(["aos-daemon", str(config)], cwd=self.root,
                                        env=dict(self.env, AOS_STACK=str(self.daemon)),
                                        stdout=subprocess.DEVNULL, stderr=self.err)
        self.addCleanup(self.stop_daemon)
        until(lambda: (self.daemon / "state.json").exists())

    def stop_daemon(self):
        if self.process.poll() is None:
            result = subprocess.run(["aos-daemon-ctl", "-d", str(self.daemon), "shutdown", "--timeout-s", "20"],
                                    cwd=self.root, env=self.env, capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.process.wait(timeout=25)

    def attach(self, override):
        flags = ["--dotenv-override"] if override else []
        result = subprocess.run([sys.executable, str(BIN), "-d", str(self.daemon), "ctl", "add", "-n", "ann",
                                 "-w", str(self.workspace), *flags, str(self.definition)], cwd=self.root, env=self.env,
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.workspace / "environment.txt"
        until(output.exists)
        lines = until(lambda: output.read_text().splitlines() if len(output.read_text().splitlines()) == 2 else None)
        return lines, json.loads((self.daemon / "procs_state.json").read_text())["procs"]["ann"]

    def test_override_changes_path_and_mark_and_records_single(self):
        lines, row = self.attach(True)
        self.assertEqual(lines, [str(self.bin) + os.pathsep + self.env["PATH"], "from-env"])
        self.assertIsNone(row["exec"])
        target = row["launch"]["exec"]
        self.assertIsInstance(target, list)
        self.assertEqual(len(target), 1)
        path, separator, pointer = target[0].partition("#")
        self.assertEqual((separator, pointer), ("#", "/exec"))
        single = json.loads((self.daemon / path).read_text())["exec"]
        self.assertIsInstance(single, dict)
        self.assertEqual(single["argv"][:3], ["aos-exec", "--dotenv-override", "--"])

    def test_default_keeps_existing_environment(self):
        lines, row = self.attach(False)
        self.assertEqual(lines, [self.env["PATH"], "outside"])
        self.assertIsInstance(row["exec"], str)


if __name__ == "__main__":
    unittest.main()
