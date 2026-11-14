# 驗證 wait 寄出後的 brain_wait.json、絕對 kernel 路徑與寫入失敗不改結束碼。
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from test_selfheal import Base, CELLS


class BrainWaitFile(Base):
    def test_success_records_pending_letter_and_absolute_kernel(self):
        daemon = self.root / 'daemon'
        kernel = daemon / 'kernel'
        kernel.mkdir(parents=True)
        result = self.wait(10, AOS_DAEMON=str(daemon), AOS_LLM_KERNEL='kernel')
        record = json.loads((self.stack / 'think/brain_wait.json').read_text())
        self.assertEqual(record, {'letter': self.pending(), 'kernel': str(kernel)})
        self.assertTrue(os.path.isabs(record['kernel']))
        self.assertEqual(result.stderr, '')
        self.assertEqual(list((self.stack / 'think').glob('.brain_wait.json.*.tmp')), [])

    def test_missing_kernel_folder_writes_no_record(self):
        self.wait(10)
        self.assertEqual(self.pending(), 'letter-1')
        self.assertFalse((self.stack / 'think/brain_wait.json').exists())

    @unittest.skipIf(os.geteuid() == 0, 'root bypasses directory write permissions')
    def test_unwritable_think_after_pending_only_warns(self):
        kernel = self.root / 'kernel'
        kernel.mkdir()
        launcher = self.root / 'run_wait.py'
        launcher.write_text(
            '# Make think read-only immediately after the pending letter is saved.\n'
            'import os, runpy, sys\n'
            'sys.path.insert(0, ' + repr(str(CELLS)) + ')\n'
            'import atomic_file\n'
            'original = atomic_file.write_atomic\n'
            'def save(path, text, die):\n'
            '    original(path, text, die)\n'
            '    os.chmod(os.path.dirname(path), 0o555)\n'
            'atomic_file.write_atomic = save\n'
            'runpy.run_path(' + repr(str(CELLS / 'wait.py')) + ', run_name="__main__")\n')
        try:
            result = subprocess.run([sys.executable, str(launcher)],
                                    env=dict(self.env, AOS_LLM_KERNEL=str(kernel)),
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 10, result.stderr)
            self.assertEqual(self.pending(), 'letter-1')
            self.assertFalse((self.stack / 'think/brain_wait.json').exists())
            self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
            self.assertIn('agent-fsm: warning: cannot write ', result.stderr)
            self.assertIn('brain_wait.json', result.stderr)
            self.assertNotIn('error:', result.stderr)
        finally:
            (self.stack / 'think').chmod(0o755)


if __name__ == '__main__':
    unittest.main()
