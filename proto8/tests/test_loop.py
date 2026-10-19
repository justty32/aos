"""aos-loop 直接叫（不經 aos-exec）的案例：PATH 原樣、訊號轉給那拍（ideas § 24）。
訊號案例移植自 proto8/impls/aos-loop/tests/test_cli.py 的 C 段；其他 aos-loop 案例在 test_exec.py（經 agent 叫）。"""
import json, os, signal, subprocess, tempfile, time, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"
LOOP = str(BIN / "aos-loop")


def env_of(extra=None):
    # aos 的程式都不動 PATH：字串 run 要叫的 aos-exec 由呼叫者放進 PATH
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e["PATH"] = str(BIN) + os.pathsep + e.get("PATH", "")
    e.update(extra or {})
    return e


def wait_file(path, secs=10):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if Path(path).exists():
            return True
        time.sleep(0.02)
    return False


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = Path(self._t.name)
        self.addCleanup(self._t.cleanup)

    def prog(self, name, body):
        d = self.t / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "_exec").write_text("#!/bin/sh\n" + body)
        (d / "_exec").chmod(0o755)

    def loop(self, cfg):
        (self.t / "loop.json").write_text(json.dumps(cfg))

    def start(self, env=None):
        return subprocess.Popen([LOOP, "loop.json"], cwd=str(self.t), env=env_of(env), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)

    def test_string_run_path_as_is(self):
        # ideas § 24：字串 run 那拍看到的 PATH 跟 loop 收到的一樣（不加任何 bin）
        self.prog("cell", 'echo "$PATH" > "$AOS_STACK/path"\n')
        self.loop({"run": "cell", "max": 1})
        path = str(BIN) + ":/usr/bin:/bin"
        r = subprocess.run([LOOP, "loop.json"], cwd=str(self.t), env=env_of({"PATH": path}), capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.t / ".aos" / "path").read_text().strip(), path)

    def test_sigterm_forwarded_to_string_lap(self):
        # 那拍收到 SIGTERM 收好自己、退 0；loop 不起下一拍，以 143 結束
        self.prog("c", 'trap \'echo got >> "$AOS_STACK/log"; exit 0\' TERM\n'
                       'echo lap >> "$AOS_STACK/log"; touch "$AOS_STACK/up"\nwhile :; do sleep 0.05; done\n')
        self.loop({"run": "c", "max": 5})
        p = self.start()
        ok = wait_file(self.t / ".aos" / "up")
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=20)
        self.assertEqual((ok, p.returncode, out, err, (self.t / ".aos" / "log").read_text().split()),
                         (True, 143, "", "", ["lap", "got"]))

    def test_sigint_forwarded_to_inst_lap(self):
        s = self.t / "stack"
        s.mkdir()
        self.loop({"run": {"argv": ["sh", "-c", 'trap \'echo got > "$AOS_STACK/got"; exit 0\' INT; '
                                    'touch "$AOS_STACK/up"; while :; do sleep 0.05; done']}, "max": 5})
        p = self.start({"AOS_STACK": str(s)})
        ok = wait_file(s / "up")
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=20)
        self.assertEqual((ok, p.returncode, err, (s / "got").exists()), (True, 130, "", True))

    def test_sighup_lap_dies(self):
        # 那拍不接、被 SIGHUP 停掉：loop 還是以 128＋1 結束（不另說「第幾圈失敗」）
        self.prog("c", 'touch "$AOS_STACK/up"\nexec sleep 30\n')
        self.loop({"run": "c", "max": 5})
        p = self.start()
        ok = wait_file(self.t / ".aos" / "up")
        p.send_signal(signal.SIGHUP)
        out, err = p.communicate(timeout=20)
        self.assertEqual((ok, p.returncode, err), (True, 129, ""))


if __name__ == "__main__":
    unittest.main()
