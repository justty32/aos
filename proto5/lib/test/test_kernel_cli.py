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

    def test_init_envs_and_success_line(self):
        result = self.good_cli('init', self.home, '--cpu', '0', '--cpu', '1',
                               '--cpu', 'llm:llm', '--env', 'llm:AOS_LLM_CONFIG=/abs/llm.json',
                               '--env', 'k:EMPTY=', '--env', '0:RAW= a=b:$X ')
        self.assertEqual(result.stdout, 'initialized %s\n' % self.home.absolute())
        cpus = read_json(self.home / 'info.json')['cpus']
        self.assertEqual(cpus['llm'], {'pool': 'llm', 'envs': {'AOS_LLM_CONFIG': '/abs/llm.json'}})
        self.assertEqual(cpus['k']['envs'], {'EMPTY': ''})
        self.assertEqual(cpus['0']['envs'], {'RAW': ' a=b:$X '})

    def test_init_default_cpu_envs(self):
        self.good_cli('init', self.home, '--env', '2:X=y', '--env', 'k:X=z')
        self.assertEqual(read_json(self.home / 'info.json')['cpus']['2']['envs'], {'X': 'y'})

    def test_init_invalid_envs_no_writes(self):
        for envs in [('absent:X=y',), ('0:=x',), ('0:X',), ('X=y',), ('0:X=1', '0:X=2')]:
            with self.subTest(envs=envs):
                args = [part for value in envs for part in ('--env', value)]
                result = self.cli('init', self.home, *args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(self.home.exists())

    def test_new_help_and_usage(self):
        for command, flags in [('init', ['--env']), ('stop', ['--wait-ms', '--no-wait']), ('check', ['--agent'])]:
            text = self.good_cli(command, '-h').stdout
            for flag in flags:
                self.assertIn(flag, text)
        for args in [('stop', '--wait-ms', '-1'), ('check', '--unknown')]:
            self.assertEqual(self.cli(args[0], self.home, *args[1:]).returncode, 2)

    def test_stop_without_ledger_posts_nothing(self):
        self.initialize()
        self.assertEqual(self.good_cli('stop', self.home).stdout, 'stopped\n')
        self.assertEqual(list((self.home / 'requests').iterdir()), [])

    def test_stop_no_wait_posts_without_info_or_ledger(self):
        (self.home / "requests").mkdir(parents=True)
        result = self.good_cli('stop', self.home, '--no-wait')
        self.assertEqual((result.stdout, result.stderr), ('', ''))
        files = list((self.home / 'requests').glob('stop-*.json'))
        self.assertEqual(len(files), 1)
        self.assertEqual(read_json(files[0])['method'], 'stop')

    def test_stop_dead_daemon_and_missing_kernel_cpu_do_not_post(self):
        from unittest.mock import patch
        self.initialize(daemon=str(self.daemon))
        self.write(self.home / 'state.json', {'phase': 'running', 'cpus': {}, 'kcpu': 'k'})
        for alive in (False, True):
            with patch.object(kernel.aos_daemon, 'is_alive', return_value=alive), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(kernel.stop(self.home), 0)
            self.assertEqual(out.getvalue(), 'not running\n')
            self.assertEqual(list((self.home / 'requests').iterdir()), [])

    def test_stop_ignores_other_kernel_same_names(self):
        self.initialize(daemon=str(self.daemon))
        self.write(self.home / 'state.json', {'phase': 'stopped', 'cpus': {'0': {}}, 'kcpu': 'k'})
        self.write(self.daemon / 'state.json', {'children': {
            'k': {'target': str(self.root / 'other/cpus/k/inst.json')},
            '0': {'target': str(self.home / 'cpus-other/0/inst.json')}}})
        self.assertEqual(self.good_cli('stop', self.home).stdout, 'stopped\n')
        self.assertEqual(list((self.home / 'requests').iterdir()), [])

    def test_stop_waits_for_removed_and_ledger_only_cpus(self):
        from unittest.mock import patch
        self.initialize(daemon=str(self.daemon))
        state = {'phase': 'stopping', 'cpus': {'old': {}}, 'kcpu': 'k'}
        self.write(self.home / 'state.json', state)
        owned = {name: {'target': str(self.home / 'cpus' / name / 'inst.json')} for name in ('k', 'old')}
        self.write(self.daemon / 'state.json', {'children': owned})
        calls = []
        def advance(_):
            calls.append(1)
            state['phase'] = 'stopped'
            self.write(self.home / 'state.json', state)
            owned.pop('k' if len(calls) == 1 else 'old')
            self.write(self.daemon / 'state.json', {'children': owned})
        with patch.object(kernel.aos_daemon, 'is_alive', return_value=True), \
                patch.object(kernel.time, 'sleep', side_effect=advance), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(kernel.stop(self.home), 0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(out.getvalue(), 'stopped\n')

    def test_stop_timeout_retains_posted_request(self):
        from unittest.mock import patch
        self.initialize(daemon=str(self.daemon))
        self.write(self.home / 'state.json', {'phase': 'running', 'cpus': {}, 'kcpu': 'k'})
        self.write(self.daemon / 'state.json', {'children': {'k': {'target': str(self.home / 'cpus/k/inst.json')}}})
        with patch.object(kernel.aos_daemon, 'is_alive', return_value=True), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(kernel.main(['stop', str(self.home), '--wait-ms', '0']), 1)
        self.assertEqual(err.getvalue(), 'aos-kernel: Timeout: 等了 0 ms 還沒停好（stop 已放、不撤回），用 aos-kernel ls 看\n')
        self.assertEqual(len(list((self.home / 'requests').glob('stop-*.json'))), 1)

    def test_stop_real_daemon_returns_after_children_disappear(self):
        self.setup_running()
        self.assertEqual(self.good_cli('stop', self.home).stdout, 'stopped\n')
        self.assertEqual(self.state()['phase'], 'stopped')
        self.assertEqual(self.dstate()['children'], {})
        self.assertEqual(self.good_cli('stop', self.home).stdout, 'stopped\n')

    def test_bad_agent_summary_points_to_stderr_and_json_unchanged(self):
        self.initialize()
        agent = self.root / 'agent'
        agent.mkdir()
        target = agent / 'tick.json'
        for stderr in ('log/agent.err', {'$opt': 'append', '$val': 'log/agent.err'}):
            self.write(target, {'argv': ['aos-agent', 'tick', str(agent)], 'stderr': stderr})
            proc = dict(target=str(target), once=False, status='bad', runs=3, fails=3, pending=None)
            self.write(self.home / 'state.json', {'procs': {'agent': proc}})
            text = self.good_cli('ls', self.home).stdout
            self.assertIn('  看 %s\n' % (agent / 'log/agent.err'), text)
            self.assertEqual(json.loads(self.good_cli('ls', self.home, '--json').stdout)['procs']['agent'], proc)

    def test_bad_summary_stderr_fallbacks(self):
        target = self.root / 'inst.json'
        self.assertEqual(kernel._stderr_hint(str(target)), str(target))
        for value in ({'$env': 'ERR'}, {'$opt': 'append', '$val': {'$env': 'ERR'}}, None):
            self.write(target, {'stderr': value})
            self.assertEqual(kernel._stderr_hint(str(target)), str(target) + ' 的 stderr 設定')
