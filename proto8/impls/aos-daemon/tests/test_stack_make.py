# Check aos-daemon creates a missing $AOS_STACK at start (11-11, make_stack) after the config checks pass.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-daemon'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


class StackMake(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-daemon-stack-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))

    def run_daemon(self, stack, cfg=None):
        p = self.d / 'daemon.json'
        p.write_text(json.dumps(dict({'interval_ms': 20, 'procs': {}}, **(cfg or {}))))
        return subprocess.run([str(BIN), '--max', '1', str(p)], env=dict(ENV, AOS_STACK=stack), cwd=self.d,
                              capture_output=True, text=True, timeout=20)

    def test_missing_stack_is_created(self):
        st = self.d / 'a' / 'b'
        r = self.run_daemon(str(st) + '/')
        self.assertEqual((r.returncode, r.stderr), (0, ''))
        self.assertTrue((st / 'state.json').is_file())
        self.assertTrue((st / 'procs_state.json').is_file())
        self.assertTrue((st / 'procs_requests' / 'new').is_dir())

    def test_relative_stack_from_cwd(self):
        r = self.run_daemon('rel/st')
        self.assertEqual((r.returncode, r.stderr), (0, ''))
        self.assertTrue((self.d / 'rel' / 'st' / 'procs_state.json').is_file())

    def test_cannot_create(self):
        (self.d / 'f').write_text('')
        r = self.run_daemon(str(self.d / 'f' / 'x'))
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r'^aos-daemon: error: MkdirFailed cannot create AOS_STACK: ')

    def test_existing_file_is_left_alone(self):
        (self.d / 'f').write_text('keep')
        r = self.run_daemon(str(self.d / 'f'))
        self.assertEqual(r.returncode, 1)
        self.assertIn('aos-daemon: error: ', r.stderr)
        self.assertEqual((self.d / 'f').read_text(), 'keep')

    def test_bad_config_creates_nothing(self):
        r = self.run_daemon(str(self.d / 'st'), {'adopt': 'yes'})
        self.assertEqual(r.returncode, 1)
        self.assertIn('CfgBad', r.stderr)
        self.assertFalse((self.d / 'st').exists())


if __name__ == '__main__':
    unittest.main()
