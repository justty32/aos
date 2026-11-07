# Verify swap failures restore the live definition and never consume retained history.
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import swap
import tool_io


class SwapRecovery(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='aos-swap-recovery-', dir='/tmp')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.defs, self.source = self.root / 'defs', self.root / 'source'
        for root, data in ((self.defs, b'old\0\xff'), (self.source, b'new\0\xfe')):
            (root / 'd').mkdir(parents=True)
            (root / 'd/data').write_bytes(data)
        self.args = {'defs': str(self.defs), 'target': 'd', 'from': str(self.source), 'daemons': []}

    def assert_old_is_live(self):
        self.assertEqual((self.defs / 'd/data').read_bytes(), b'old\0\xff')
        self.assertEqual((self.source / 'd/data').read_bytes(), b'new\0\xfe')
        self.assertFalse((self.defs / '.prev/d').exists())
        self.assertEqual(list((self.defs / '.prev').glob('.tmp-*')), [])

    def test_partial_candidate_copy_restores_live_bytes(self):
        def partial_copy(source, destination, **kwargs):
            destination.mkdir()
            (destination / 'partial').write_bytes(b'incomplete')
            raise OSError('injected copy failure')

        with patch.object(swap.shutil, 'copytree', partial_copy):
            with self.assertRaises(tool_io.Error) as caught:
                swap.promote(self.args)
        self.assertEqual(caught.exception.code, 'SwapFailed')
        self.assert_old_is_live()

    def test_candidate_install_failure_restores_live_bytes(self):
        rename = os.rename

        def fail_install(source, destination):
            if Path(source).name.startswith('.tmp-'):
                raise OSError('injected install failure')
            return rename(source, destination)

        with patch.object(swap.os, 'rename', fail_install):
            with self.assertRaises(tool_io.Error) as caught:
                swap.promote(self.args)
        self.assertEqual(caught.exception.code, 'SwapFailed')
        self.assert_old_is_live()

    def test_rollback_move_failure_keeps_live_and_previous_bytes(self):
        promoted = swap.promote(self.args)
        previous = Path(promoted['prev'])
        rename = os.rename

        def fail_restore(source, destination):
            if Path(source) == previous:
                raise OSError('injected rollback failure')
            return rename(source, destination)

        with patch.object(swap.os, 'rename', fail_restore):
            with self.assertRaises(tool_io.Error) as caught:
                swap.rollback(self.args)
        self.assertEqual(caught.exception.code, 'SwapFailed')
        self.assertEqual((self.defs / 'd/data').read_bytes(), b'new\0\xfe')
        self.assertEqual((previous / 'data').read_bytes(), b'old\0\xff')
        self.assertEqual(list((self.defs / '.prev').glob('.tmp-*')), [])


if __name__ == '__main__':
    unittest.main()
