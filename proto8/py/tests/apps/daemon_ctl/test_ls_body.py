"""test_ls_body - 身體（llm kernel、框架站）最後一輪出錯時，ls 的「# daemon:」那行說出來、-j 帶 body_code（11-19 基底體檢 P5）。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROTO = Path(__file__).resolve().parents[4]
CTL = PROTO / "bin" / "aos-daemon-ctl"
ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
ENV["PATH"] = str(PROTO / "bin") + ":" + ENV["PATH"]


class LsBody(unittest.TestCase):
    def start(self, code):
        root = Path(tempfile.mkdtemp(prefix="ls-body-"))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "stack").mkdir()
        (root / "daemon.json").write_text(json.dumps({"interval_ms": 50, "procs": {},
                                                      "exec": {"argv": ["sh", "-c", "exit %d" % code]}}))
        p = subprocess.Popen(["aos-daemon", "daemon.json"], cwd=root, env=dict(ENV, AOS_STACK=str(root / "stack")),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.stop, p, root)
        end = time.monotonic() + 10
        while time.monotonic() < end:
            try:
                if json.loads((root / "stack" / "state.json").read_text()).get("body_code") == code:
                    return root
            except (OSError, ValueError):
                pass
            time.sleep(.05)
        self.fail("body never ran")

    def stop(self, p, root):
        subprocess.run([sys.executable, str(CTL), "-d", str(root / "stack"), "shutdown"], env=ENV,
                       capture_output=True, timeout=30)
        try:
            p.wait(timeout=15)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()

    def ls(self, root, *flags):
        r = subprocess.run([sys.executable, str(CTL), "-d", str(root / "stack"), "ls", *flags], env=ENV,
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_failing_body_is_on_the_daemon_line(self):
        root = self.start(3)
        self.assertRegex(self.ls(root), r"# daemon: running \(pid \d+\); its body failed last round \(code 3; ")
        self.assertEqual(json.loads(self.ls(root, "-j"))["body_code"], 3)

    def test_good_body_is_quiet(self):
        root = self.start(0)
        out = self.ls(root)
        self.assertRegex(out, r"# daemon: running \(pid \d+\)\n")
        self.assertEqual(json.loads(self.ls(root, "-j"))["body_code"], 0)


if __name__ == "__main__":
    unittest.main()
