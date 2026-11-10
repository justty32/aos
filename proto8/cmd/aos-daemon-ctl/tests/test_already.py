"""test_already - 對已在那個狀態的列下 stop／sleep／start／wake＝印「名字: already 狀態」、退 0、不寄信（cli-sweep Q4＝A，使用者 11-10）。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROTO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(PROTO / "py"), str(PROTO / "lib")]
import daemon_ctl as dc  # noqa: E402

CTL = PROTO / "cmd" / "aos-daemon-ctl" / "bin" / "aos-daemon-ctl"
AGENT = PROTO / "cmd" / "aos-agent" / "bin" / "aos-agent"


class Already(unittest.TestCase):
    def test_need_phase(self):
        for cmd, ph, word in (("stop", "stopped", "stopped"), ("sleep", "sleeping", "sleeping"),
                              ("start", "running", "running"), ("wake", "running", "running"),
                              ("start", "stuck", "running")):
            with self.assertRaises(dc.Already) as cm:
                dc.need_phase(cmd, "ann", {"phase": ph})
            self.assertEqual(str(cm.exception), "ann: already %s" % word)
        with self.assertRaises(dc.Fail) as cm:            # 不是「已經是」的組合照舊 PhaseBad
            dc.need_phase("start", "ann", {"phase": "sleeping"})
        self.assertEqual(cm.exception.code, "PhaseBad")
        dc.need_phase("stop", "ann", {"phase": "running"})   # 正常的照過

    def test_cli_exits_zero_without_sending(self):
        d = tempfile.mkdtemp(prefix="already-")
        try:
            Path(d, "procs_state.json").write_text(json.dumps({"procs": {"ann": {"phase": "stopped", "exec": "x"}}}) + "\n")
            r = subprocess.run([sys.executable, str(CTL), "-d", d, "stop", "ann"], capture_output=True, text=True)
            self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (0, "ann: already stopped", ""))
            self.assertFalse(os.path.exists(os.path.join(d, "procs_requests")))   # 沒寄信（沒建信箱）
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
