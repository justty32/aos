"""proto5/tools/base/bash：在 root 底下跑一句 bash，逾時、輸出截斷、背景行程收掉。
共用底（ToolCase：假 agent 家、run_tool）在 test_tools_base.py。
"""
import os
import time
import unittest

from test_tools_base import ToolCase


class TestBash(ToolCase):

    def test_basic_output_stdout_and_stderr_merged(self):
        out = self.assertOk(self.run_tool('bash', {'command': 'echo out; echo err >&2'}))
        self.assertIn('out', out.splitlines())
        self.assertIn('err', out.splitlines())

    def test_cwd_is_root(self):
        out = self.assertOk(self.run_tool('bash', {'command': 'pwd'}))
        self.assertEqual(out.strip(), os.path.realpath(self.ws))

    def test_nonzero_exit_is_exit_code_error_with_output_first(self):
        code, out, j = self.run_tool('bash', {'command': 'echo before; exit 3'})
        self.assertEqual(code, 1)
        self.assertEqual(j['error'], 'ExitCode')
        self.assertEqual(j['exit_code'], 3)
        lines = out.rstrip('\n').splitlines()
        self.assertEqual(lines[0], 'before')
        self.assertTrue(lines[-1].startswith('{"ok"'), lines[-1])
        self.assertLess(lines.index('before'), len(lines) - 1)

    def test_timeout(self):
        start = time.monotonic()
        code, out, j = self.run_tool('bash', {'command': 'sleep 30', 'timeout': 1}, timeout=10)
        elapsed = time.monotonic() - start
        self.assertEqual(code, 1)
        self.assertEqual(j['error'], 'Timeout')
        self.assertEqual(j['timeout'], 1)
        self.assertLess(elapsed, 6, '逾時後該在幾秒內回，實際花了 %.1fs' % elapsed)

    def test_timeout_zero_is_bad_arguments(self):
        self.assertErr(self.run_tool('bash', {'command': 'echo hi', 'timeout': 0}), 'BadArguments')

    def test_timeout_601_is_bad_arguments(self):
        self.assertErr(self.run_tool('bash', {'command': 'echo hi', 'timeout': 601}), 'BadArguments')

    def test_empty_command_is_bad_arguments(self):
        self.assertErr(self.run_tool('bash', {'command': ''}), 'BadArguments')

    def test_blank_command_is_bad_arguments(self):
        self.assertErr(self.run_tool('bash', {'command': '   '}), 'BadArguments')

    def test_output_over_2000_lines_is_truncated_to_tail(self):
        cmd = 'python3 -c "\nfor i in range(2500):\n    print(i)\n"'
        out = self.assertOk(self.run_tool('bash', {'command': cmd}))
        lines = out.rstrip('\n').splitlines()
        self.assertIn('[output truncated', lines[0])
        self.assertEqual(lines[-1], '2499')
        self.assertNotIn('\n0\n', out)  # 開頭的行不該還在

    def test_background_process_does_not_block_and_gets_reaped(self):
        marker = self.wpath('bg.marker')
        start = time.monotonic()
        out = self.assertOk(self.run_tool(
            'bash', {'command': '(sleep 1 && echo done > bg.marker) & echo started'}, timeout=10))
        elapsed = time.monotonic() - start
        self.assertIn('started', out)
        self.assertLess(elapsed, 0.8, '背景行程不該讓工具卡住，實際花了 %.2fs' % elapsed)
        time.sleep(1.5)
        self.assertFalse(os.path.exists(marker), '背景行程該在工具結束時被收掉，不該活到寫出 marker')

    def test_empty_stdin_cat_returns_immediately(self):
        start = time.monotonic()
        code, out, j = self.run_tool('bash', {'command': 'cat'}, timeout=5)
        elapsed = time.monotonic() - start
        self.assertEqual(code, 0)
        self.assertLess(elapsed, 3)
        self.assertEqual(out.strip(), '(no output)')


if __name__ == '__main__':
    unittest.main()
