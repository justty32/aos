# Check loop.json gate / gate_timeout_ms (idle-polling cut 1, 11-25): 10 skips the round (no body, no count, no points, state stays
# waiting), 0 runs it, anything else (other code, timeout, cannot start) is one warning and the body runs; ctl still works while skipping.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

BIN = Path(__file__).resolve().parents[3] / 'bin' / 'aos-loop'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}

LOG_SH = '#!/bin/sh\n# append the name to $LOG, then the tail\necho "%s" >> "$LOG"\n%s'
# 閘：照 answers 檔一行一個碼依序回，用完就一直回最後一個
GATE_SH = '''#!/bin/sh
# answer the next code from $ANSWERS (the last one forever when used up); log "gate"
echo gate >> "$LOG"
n=$(cat "$ASKED" 2>/dev/null || echo 0); n=$((n + 1)); echo $n > "$ASKED"
code=$(sed -n "${n}p" "$ANSWERS"); [ -n "$code" ] || code=$(tail -n 1 "$ANSWERS")
%s
exit $code
'''


class Gate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-loop-gate-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        self.log, self.stack = self.d / 'log.txt', self.d / 'stack'
        self.stack.mkdir()
        self.env = dict(ENV, LOG=str(self.log), ANSWERS=str(self.d / 'answers'), ASKED=str(self.d / 'asked'),
                        AOS_STACK=str(self.stack) + '/')
        for name in ('body', 'before'):
            self.script(name, LOG_SH % (name, ''))
        self.script('gate', GATE_SH % '')

    def script(self, name, text):
        p = self.d / name
        p.write_text(text)
        p.chmod(0o755)
        return str(p)

    def answers(self, *codes):
        (self.d / 'answers').write_text(''.join('%d\n' % c for c in codes))

    def cfg(self, **kw):
        doc = {'exec': str(self.d / 'body'), 'gate': str(self.d / 'gate'), 'interval_ms': 20, 'ctl': None, 'state': None, 'state_flux': None}
        doc.update(kw)
        p = self.d / 'loop.json'
        p.write_text(json.dumps({k: v for k, v in doc.items() if v != 'omit'}))
        return str(p)

    def names(self):
        return self.log.read_text().split() if self.log.exists() else []

    def run_loop(self, cfg, *flags, timeout=20):
        p = subprocess.run([str(BIN), *flags, cfg], env=self.env, cwd=self.d, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stderr

    def test_10_skips_the_round_without_counting_or_points(self):
        self.answers(10, 10, 10, 0, 10, 0)
        code, err = self.run_loop(self.cfg(max=2, on_before_run=str(self.d / 'before'), state='state.json'), '--enable-counters')
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(self.names(), ['gate'] * 3 + ['gate', 'before', 'body', 'gate', 'gate', 'before', 'body'])
        self.assertEqual((self.stack / 'counter_runs.txt').read_text().strip(), '2')   # max and counter count only real runs

    def test_skipping_keeps_state_waiting_and_ctl_works(self):
        self.answers(10)
        p = subprocess.Popen([str(BIN), self.cfg(ctl='ctl.json', state='state.json')], env=self.env, cwd=self.d,
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        try:
            end = time.monotonic() + 5
            while self.names().count('gate') < 5 and time.monotonic() < end:
                time.sleep(.02)
            state = json.loads((self.stack / 'state.json').read_text())
            self.assertEqual(state['phase'], 'waiting')
            written = (self.stack / 'state.json').stat().st_mtime_ns
            time.sleep(.3)
            self.assertEqual((self.stack / 'state.json').stat().st_mtime_ns, written)   # skipped rounds do not rewrite it
            (self.stack / 'ctl.json').write_text(json.dumps({'cmd': 'stop', 'seq': 1}))
            self.assertEqual(p.wait(timeout=5), 0)
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
        self.assertNotIn('body', self.names())
        self.assertEqual(p.stderr.read(), '')
        p.stderr.close()

    def test_a_broken_gate_warns_once_and_the_body_runs(self):
        for tail, extra, word in (('', {}, 'exited 3'),
                                  ('sleep 5\n', {'gate_timeout_ms': 200}, 'did not finish in 200 ms'),
                                  (None, {}, 'exited 1')):                          # aos-exec says why on its own line
            with self.subTest(word=word):
                if self.log.exists():
                    self.log.unlink()
                (self.d / 'asked').unlink(missing_ok=True)
                self.answers(3)
                if tail is None:
                    cfg = self.cfg(max=3, gate=str(self.d / 'nowhere'), **extra)
                else:
                    self.script('gate', GATE_SH % tail)
                    cfg = self.cfg(max=3, **extra)
                code, err = self.run_loop(cfg)
                self.assertEqual(code, 0, err)
                self.assertEqual(self.names().count('body'), 3)
                warnings = [l for l in err.splitlines() if 'warning: gate' in l]
                self.assertEqual(len(warnings), 1, err)
                self.assertIn(word, warnings[0])
                self.assertIn('running the body anyway', warnings[0])

    def test_recovering_then_failing_again_warns_again(self):
        self.answers(3, 0, 3, 0)
        code, err = self.run_loop(self.cfg(max=4))
        self.assertEqual(code, 0, err)
        self.assertEqual(len([l for l in err.splitlines() if 'warning: gate' in l]), 2)

    def test_bad_keys_are_cfgbad(self):
        for kw, word in (({'gate_timeout_ms': -1}, 'gate_timeout_ms must be'), ({'gate': 'omit', 'gate_timeout_ms': 5}, 'without gate'),
                         ({'gate': 3}, 'gate')):
            with self.subTest(kw=kw):
                code, err = self.run_loop(self.cfg(**kw))
                self.assertEqual(code, 1)
                self.assertIn('CfgBad', err)
                self.assertIn(word, err)

    def test_without_gate_nothing_changes(self):
        self.answers(10)
        code, err = self.run_loop(self.cfg(max=2, gate='omit'))
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(self.names(), ['body', 'body'])


if __name__ == '__main__':
    unittest.main()
