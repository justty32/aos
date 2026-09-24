"""kernel CLI 的 cpu 選項、help、ack 與人讀摘要。"""
import contextlib
import io
import json

import aos_kernel as kernel
from _kernel_util import KernelCase, read_json, wait_for
import aos_client


class KernelCLI(KernelCase):
    def test_init_cpu_defaults_and_named_pool(self):
        self.good_cli('init', self.home, '--cpu', '0', '--cpu', 'llm:llm')
        self.assertEqual(read_json(self.home / 'info.json')['cpus'],
                         {'k': {'pool': 'kernel'}, '0': {}, 'llm': {'pool': 'llm'}})
        kernel.load_info(self.home)

    def test_init_explicit_kernel_cpu(self):
        self.good_cli('init', self.home, '--cpu', 'kk:kernel', '--cpu', '0')
        self.assertEqual(read_json(self.home / 'info.json')['cpus'],
                         {'kk': {'pool': 'kernel'}, '0': {}})

    def test_init_invalid_cpus_are_usage_errors_without_writes(self):
        for values in [('a:kernel', 'b:kernel'), ('0', '0:llm'), ('k',),
                       ('../bad',), ('.',), ('..',), ('',)]:
            with self.subTest(values=values):
                args = [part for value in values for part in ('--cpu', value)]
                result = self.cli('init', self.home, *args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertTrue(result.stderr.startswith('aos-kernel: Usage: '))
                self.assertEqual(len(result.stderr.splitlines()), 1)
                self.assertFalse(self.home.exists())

    def test_ack_missing_response_does_not_post(self):
        self.initialize()
        result = self.cli('ack', self.home, '/elsewhere/missing.json')
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith('aos-kernel: NotFound: '))
        self.assertEqual(result.stdout, '')
        self.assertEqual(list((self.home / 'requests').iterdir()), [])

    def test_help_lists_all_commands(self):
        for flag in ('-h', '--help'):
            result = self.good_cli(flag)
            for command in ('init', 'boot', 'tick', 'add', 'rm', 'ls', 'stop', 'ack'):
                self.assertIn(command, result.stdout)

    def test_subcommand_help(self):
        for command in ('init', 'boot', 'tick', 'add', 'rm', 'ls', 'stop', 'ack'):
            result = self.good_cli(command, '-h')
            self.assertIn('usage: aos-kernel ' + command, result.stdout)
            if command == 'add':
                self.assertIn('--once', result.stdout)

    def test_ls_json_matches_status_without_ledger(self):
        self.initialize()
        self.assertEqual(json.loads(self.good_cli('ls', self.home, '--json').stdout),
                         kernel.status(self.home))

    def test_ls_summary_includes_cpus_and_procs(self):
        self.setup_running()
        self.add(self.job('raise SystemExit(100)'), 'visible')
        self.kernel_stop()
        expected = kernel.status(self.home)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(kernel.main(['ls', str(self.home), '--json']), 0)
        self.assertEqual(json.loads(output.getvalue()), expected)
        summary = self.good_cli('ls', self.home).stdout
        self.assertFalse(summary.startswith('{'))
        for name in self.info['cpus']:
            self.assertIn('cpu ' + name + '  pool ', summary)
        self.assertIn('proc visible  repeat ', summary)
        self.assertIn('queue ', summary)

    def test_ls_summary_without_ledger(self):
        self.initialize()
        text = self.good_cli('ls', self.home).stdout
        self.assertIn('chain -  phase -  last_seq -  daemon dead', text)
        self.assertIn('kernel cpu -  current -  requests 0', text)
        self.assertIn('cpu llm  pool llm  idle  missing', text)

    def test_ack_once_response_by_filename_or_path(self):
        self.setup_running()
        for use_path in (False, True):
            with self.subTest(use_path=use_path):
                output = self.good_cli('add', self.home, self.job(), '--once').stdout
                name = output.split()[0]
                aos_client.wait_response(self.home, name, timeout_ms=5000, poll_ms=5)
                response = self.home / 'responses' / name
                result = self.good_cli('ack', self.home, response if use_path else name)
                self.assertEqual((result.stdout, result.stderr), ('', ''))
                wait_for(lambda: not response.exists())
        self.kernel_stop()
