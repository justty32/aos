"""統一錯誤的一行訊息與退出碼。"""
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import test_up as cases
import aos7_up as up
import aos7_up_cli as cli
import aos7_up_status as view


class UpErrors(unittest.TestCase):
    def test_child_failure_summary(self):
        for rc, expected in ((1, 1), (2, 1), (3, 3), (4, 1)):
            result = subprocess.CompletedProcess([], rc, '', '長說明\n最後原因\n')
            with patch.object(up, 'call', return_value=result):
                with self.assertRaises(view.UpError) as err:
                    up.run('bin/aos7-ctl', 'add')
            self.assertEqual(err.exception.code, expected)
            self.assertIn('最後原因', str(err.exception))
            self.assertNotIn('長說明', str(err.exception))
            if rc == 3:
                self.assertTrue(str(err.exception).startswith('不確定：'))

    def test_oserror_one_line(self):
        with patch.object(cli, 'up', side_effect=OSError('讀檔\n故障')), \
             contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.main(['/tmp/aos/bob']), 3)
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertTrue(err.getvalue().startswith('aos7-up: 不確定：'))
        self.assertIn('留著', err.getvalue())
        self.assertIn('再跑', err.getvalue())

    def test_stop_timeout(self):
        with patch.object(up, 'alive', return_value=True), \
             patch.object(up, 'run'), \
             patch.object(up.time, 'monotonic', side_effect=[0, 31]), \
             contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.main(['stop', '/tmp/aos/bob']), 3)
        self.assertIn('30 秒還沒停', err.getvalue())
        self.assertEqual(len(err.getvalue().splitlines()), 1)

    def test_bad_name_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('.bob', 'you', 'bad name'):
                node = Path(tmp) / name
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    self.assertEqual(cli.main([str(node), '-d']), 2)
                self.assertFalse(node.exists())
                self.assertEqual(len(err.getvalue().splitlines()), 1)
