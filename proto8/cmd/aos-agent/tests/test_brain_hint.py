# 驗證問腦記錄與 llm kernel 停機時 listen／say 的一次提示及安靜失敗。
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PROTO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(PROTO / 'cmd/aos-agent'), str(PROTO / 'py'), str(PROTO / 'lib')]
from aos_agent import common, hints, listen, say

BIN = PROTO / 'cmd/aos-agent/bin/aos-agent'


class BrainHint(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='brain-hint-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.daemon = self.root / 'daemon'
        self.stack = self.daemon / 'procs/kid'
        self.kernel = self.root / 'kernel'
        self.kernel.mkdir()
        for name in ('think/reply/new', 'queue/new', 'queue/cur', 'queue/tmp'):
            (self.stack / name).mkdir(parents=True)
        (self.stack / 'queue/cur/000000000001.question').mkdir()
        self.pending = self.stack / 'think/pending.txt'
        self.pending.write_text('brain-letter\nignored second line\n')
        self.wait_path = self.stack / 'think/brain_wait.json'
        self.wait_path.write_text(json.dumps({'letter': 'brain-letter', 'kernel': str(self.kernel)}))
        self.row = {'phase': 'running', 'stack': 'procs/kid', 'def': str(self.root / 'definition')}
        self.write_table()
        (self.stack / 'state.json').write_text('{"phase":"running"}')
        self.agent = common.Agent('kid', dict(self.row, stack=str(self.stack)))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}

    def write_table(self):
        (self.daemon / 'procs_state.json').write_text(json.dumps({'procs': {'kid': self.row}}))

    def state(self, phase='running', pid=None):
        (self.kernel / 'state.json').write_text(json.dumps({'phase': phase, 'pid': pid}))

    def cli(self, command='listen', *args):
        return subprocess.run([sys.executable, str(BIN), '-d', str(self.daemon), command,
                               '-t', 'kid', *args], env=self.env, capture_output=True, text=True, timeout=15)

    def wait(self):
        return self.cli('listen', '--timeout-s', '0.01')

    def assert_quiet(self):
        result = self.wait()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('AnswerMissing', result.stderr)
        self.assertNotIn('waiting for its brain', result.stderr)
        return result

    def test_missing_wait_record(self):
        self.wait_path.rename(self.root / 'old-brain-wait.json')
        self.assert_quiet()

    def test_mismatch_bad_json_and_wrong_types(self):
        for text in ('{"letter":"other","kernel":"/unused"}', '{broken', '[]',
                     '{"letter":"brain-letter","kernel":true}'):
            with self.subTest(text=text):
                self.wait_path.write_text(text)
                self.assert_quiet()

    def test_missing_state_and_stopped_phase(self):
        result = self.wait()
        self.assertIn('no llm daemon there (no state.json)', result.stderr)
        self.state('stopped', os.getpid())
        self.assertIn('is not running (state.json phase stopped)', self.wait().stderr)
        self.state('', os.getpid())
        self.assertIn('state.json phase ?', self.wait().stderr)

    def test_dead_pid(self):
        process = subprocess.Popen(['true'])
        process.wait()
        self.state(pid=process.pid)
        self.assertIn('pid gone', self.wait().stderr)

    def test_live_phases(self):
        for phase in ('running', 'waiting', 'stopping'):
            with self.subTest(phase=phase):
                self.state(phase, os.getpid())
                self.assert_quiet()

    def test_invalid_pids_never_reach_kill(self):
        for pid in (True, 0, -1, None, '123'):
            with self.subTest(pid=pid), patch.object(hints, 'label', return_value='running'), \
                    patch.object(hints.os, 'kill') as kill:
                self.state(pid=pid)
                self.assertIn('pid gone', hints.brain_hint(self.agent))
                kill.assert_not_called()

    def test_permission_error_means_alive(self):
        self.state(pid=123)
        with patch.object(hints, 'label', return_value='running'), \
                patch.object(hints.os, 'kill', side_effect=PermissionError) as kill:
            self.assertIsNone(hints.brain_hint(self.agent))
            kill.assert_called_once_with(123, 0)

    def test_bad_state_or_other_oserror_is_silent(self):
        for text in ('{bad', '[]', 'null'):
            with self.subTest(text=text):
                (self.kernel / 'state.json').write_text(text)
                self.assert_quiet()
        with patch.object(hints, 'label', return_value='running'), \
                patch('builtins.open', side_effect=OSError('unreadable')), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertIsNone(hints.brain_hint(self.agent))
        self.assertEqual(err.getvalue(), '')

    def test_reply_already_in_new(self):
        (self.stack / 'think/reply/new/different-reply-name').mkdir()
        self.assert_quiet()

    def test_hidden_reply_does_not_hide_hint(self):
        (self.stack / 'think/reply/new/.tmp').mkdir()
        self.assertIn('waiting for its brain', self.wait().stderr)

    def test_paused_and_stopped_agent(self):
        (self.stack / 'state.json').write_text('{"phase":"paused"}')
        self.assert_quiet()
        self.row['phase'] = 'stopped'
        self.write_table()
        self.assert_quiet()

    def test_timeout_keeps_original_error_and_appends_hint(self):
        result = self.cli('listen', '--timeout-s', '1')
        self.assertEqual(result.returncode, 1)
        error = next(line for line in result.stderr.splitlines() if 'error: AnswerMissing' in line)
        self.assertIn('waited 1 s;', error)
        self.assertIn('is not answered yet (the letter is in queue/cur/); kid is waiting for its brain', error)
        self.assertEqual(result.stdout, '')

    def test_hint_warns_only_once_over_three_seconds(self):
        result = self.cli('listen', '--timeout-s', '3')
        warnings = [line for line in result.stderr.splitlines() if 'warning:' in line and 'waiting for its brain' in line]
        self.assertEqual(len(warnings), 1, result.stderr)
        self.assertTrue(warnings[0].endswith('. Still waiting, Ctrl-C to leave'))

    def test_handed_over_path_warns_and_appends_timeout(self):
        (self.stack / 'queue/cur/000000000001.question').rename(self.root / 'handed-letter')
        (self.stack / 'history.jsonl').write_text('{"role":"user","content":"hi"}\n')
        result = self.cli('listen', '--timeout-s', '1')
        self.assertIn('warning: kid is waiting for its brain', result.stderr)
        self.assertIn('was handed over and is not answered yet; kid is waiting for its brain', result.stderr)

    def test_say_warns_after_successful_send(self):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(common.TOP, {'daemon': str(self.daemon)}, clear=True), \
                patch.object(say, 'target', return_value=self.agent), \
                patch.object(say, 'on_table', return_value=True), \
                patch.object(say.sender, 'put', return_value='sent-letter'), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            say.cmd(['--from', 'tester', 'hi'])
        self.assertEqual(out.getvalue(), 'sent-letter\n')
        self.assertIn('warning: kid is waiting for its brain', err.getvalue())

    def test_cooldown_missing_folder(self):
        self.pending.rename(self.root / 'old-pending.txt')
        record = {'code': 'SendFailed', 'reason': 'send exited 1 (llm kernel folder not found)',
                  'until': '2099-01-01T00:00:00Z', 'failures': 1, 'dropped': 0}
        path = self.stack / 'cooldown.json'
        path.write_text(json.dumps(record))
        result = self.wait()
        self.assertIn('kid cannot reach its brain: send exited 1 (llm kernel folder not found); '
                      'it retries by itself once the folder appears', result.stderr)
        self.pending.write_text('\n')
        self.assertIn('cannot reach its brain', self.wait().stderr)
        for code, reason in (('BrainFailed', record['reason']), ('SendFailed', 'other reason')):
            path.write_text(json.dumps(dict(record, code=code, reason=reason)))
            self.assertNotIn('cannot reach its brain', self.wait().stderr)


if __name__ == '__main__':
    unittest.main()
