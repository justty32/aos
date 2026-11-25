# daemon.json gate (idle-polling cut 1, 11-25): before the daemon's own body (llm kernel, kernel station) runs, the gate is asked;
# 10 skips that round (body not run, not counted), 0 runs it, a broken gate is one warning and the body runs; poke --all does not ask.
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from support import ENV, PROTO, read, until, write

GATE = '#!/bin/sh\n# log "gate" and answer the code in $GATE_CODE_FILE\necho gate >> "$AOS_STACK/gates.txt"\nexit $(cat "$GATE_CODE_FILE")\n'


class Gate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-daemon-gate-')
        self.addCleanup(self.tmp.cleanup)
        self.stack = Path(self.tmp.name)
        self.gate = self.stack / 'gate.sh'
        self.gate.write_text(GATE)
        self.gate.chmod(0o755)
        self.code = self.stack / 'gate_code'
        self.proc = None
        self.addCleanup(self.close)

    def start(self, code, interval_ms=30, gate=None):
        self.code.write_text('%d\n' % code)
        write(self.stack / 'daemon.json', {
            'interval_ms': interval_ms, 'procs': {}, 'gate': gate or str(self.gate),
            'exec': [sys.executable, '-c', 'import os,pathlib; (pathlib.Path(os.environ["AOS_STACK"])/"runs.txt").open("a").write("run\\n")']})
        self.err = open(self.stack / 'daemon.err', 'w')
        self.proc = subprocess.Popen(['aos-daemon', str(self.stack / 'daemon.json')], cwd=self.stack,
                                     env=dict(ENV, AOS_STACK=str(self.stack), GATE_CODE_FILE=str(self.code)),
                                     stdout=subprocess.DEVNULL, stderr=self.err)
        until(lambda: read(self.stack / 'state.json', {}).get('pid') == self.proc.pid)

    def close(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=15)
            self.err.close()

    def count(self, name):
        p = self.stack / name
        return len(p.read_text().splitlines()) if p.exists() else 0

    def stderr(self):
        self.err.flush()
        return (self.stack / 'daemon.err').read_text()

    def test_10_skips_the_body_and_poke_all_still_runs_it(self):
        self.start(10)
        until(lambda: self.count('gates.txt') >= 5)
        self.assertEqual(self.count('runs.txt'), 0)
        subprocess.run([str(PROTO / 'bin' / 'aos-daemon-ctl'), '--daemon', str(self.stack), 'poke', '--all'],
                       env=ENV, capture_output=True, timeout=10, check=True)
        until(lambda: self.count('runs.txt') == 1)                          # forced round: no gate asked
        self.code.write_text('0\n')
        until(lambda: self.count('runs.txt') >= 3)
        self.assertNotIn('warning', self.stderr())

    def test_broken_gate_warns_once_and_runs_the_body(self):
        self.start(4)
        until(lambda: self.count('runs.txt') >= 3)
        self.assertEqual(self.stderr().count('warning: gate'), 1, self.stderr())
        self.assertIn('exited 4; running the body anyway', self.stderr())

    def test_gate_timeout_without_gate_is_cfgbad(self):
        write(self.stack / 'daemon.json', {'interval_ms': 30, 'procs': {}, 'gate_timeout_ms': 10})
        p = subprocess.run(['aos-daemon', str(self.stack / 'daemon.json')], cwd=self.stack,
                           env=dict(ENV, AOS_STACK=str(self.stack)), capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 1)
        self.assertIn('CfgBad gate_timeout_ms without gate', p.stderr)


if __name__ == '__main__':
    unittest.main()
