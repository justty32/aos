"""kernel CLI 的 --target、init --config、halt、help、ack 與人讀摘要。"""
import contextlib
import io
import json

import aos_kernel as kernel
from _kernel_util import KernelCase, read_json, wait_for
import aos_client


class KernelCLI(KernelCase):
    def init_config(self, config, name='kernel.json'):
        path = self.root / name
        path.write_text(config if isinstance(config, str) else json.dumps(config), encoding='utf-8')
        return path

    def test_init_config_adds_kernel_cpu_and_defaults(self):
        config = self.init_config({'cpus': {'0': {}, 'llm': {'pool': 'llm', 'envs': {'AOS_LLM_CONFIG': '/abs/llm.json'}}},
                                   'tick_ms': 250})
        result = self.good_cli('init', self.home, '--config', config)
        self.assertEqual(result.stdout, 'initialized %s\n' % self.home.absolute())
        info = read_json(self.home / 'info.json')
        self.assertEqual(info['cpus'], {'k': {'pool': 'kernel'}, '0': {},
                                        'llm': {'pool': 'llm', 'envs': {'AOS_LLM_CONFIG': '/abs/llm.json'}}})
        self.assertEqual(info['_metainfo'], {'_type': 'kernel', '_version': 1})
        self.assertEqual((info['tick_ms'], info['interval_ms'], info['bad_after']), (250, 1000, 10))
        kernel.load_info(self.home)

    def test_init_config_explicit_kernel_cpu(self):
        config = self.init_config({'cpus': {'kk': {'pool': 'kernel'}, '0': {}}})
        self.good_cli('init', self.home, '--config', config)
        self.assertEqual(read_json(self.home / 'info.json')['cpus'], {'kk': {'pool': 'kernel'}, '0': {}})

    def test_init_without_config_is_usage_error(self):
        result = self.cli('init', self.home)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertTrue(result.stderr.startswith('aos-kernel: Usage: init 要給 --config FILE'), result.stderr)
        self.assertIn('"cpus"', result.stderr)
        self.assertFalse(self.home.exists())

    def test_init_bad_config_exit_1_without_writes(self):
        cases = ['{', '[]', {'cpus': []}, {}, {'cpus': {'k': {}}}, {'cpus': {'a': {'pool': 'kernel'}, 'b': {'pool': 'kernel'}}},
                 {'cpus': {'0': {}}, 'daemon': '/abs/D'}, {'cpus': {'0': {}}, 'tick_ms': -1},
                 {'cpus': {'../bad': {}}}, {'cpus': {'0': {}}, '_metainfo': {'_type': 'daemon', '_version': 1}}]
        for i, config in enumerate(cases):
            with self.subTest(config=config):
                path = self.init_config(config, 'bad%d.json' % i)
                result = self.cli('init', self.home, '--config', path)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(len(result.stderr.splitlines()), 1)
                self.assertIn('K＝%s，取自 --target' % self.home, result.stderr)
                self.assertFalse(self.home.exists())
        result = self.cli('init', self.home, '--config', self.root / 'missing.json')
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith('aos-kernel: ReadFailed: '))
        self.assertFalse(self.home.exists())

    def test_init_config_null_and_directive_pool(self):
        """fix-r4（astra 審查）：JSON null 不能落回預設家；pool 用指示詞時照解完的值決定補不補 k。"""
        import os
        result = self.cli('init', self.home, '--config', self.init_config('null', 'null.json'))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(self.home.exists())
        config = self.init_config({'cpus': {'s': {'pool': {'$env': 'AOSTEST_POOL'}}, '0': {}}}, 'dir.json')
        result = self.raw_cli('init', '--target', self.home, '--config', config,
                              env=dict(os.environ, AOSTEST_POOL='kernel'), cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(read_json(self.home / 'info.json')['cpus']), ['s', '0'])

    def test_check_bad_info_names_source(self):
        import os
        env = {k: v for k, v in os.environ.items() if k != 'AOS_KERNEL_HOME'}
        result = self.raw_cli('check', env=env, cwd=self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn('取自 目前資料夾', result.stdout + result.stderr)

    def test_init_config_daemon_rejected(self):
        path = self.init_config({'cpus': {'0': {}}, 'daemon': '/abs/D'})
        result = self.cli('init', self.home, '--config', path)
        self.assertTrue(result.stderr.startswith('aos-kernel: FieldTypeMismatch: --config 不能寫 daemon'), result.stderr)

    def test_init_help_has_config_example(self):
        text = self.good_cli('init', '-h').stdout
        self.assertIn('--config', text)
        self.assertIn('"AOS_LLM_CONFIG"', text)
        self.assertNotIn('--cpu', text)

    def test_target_three_sources_and_error_names_source(self):
        import os
        self.initialize()
        env = {k: v for k, v in os.environ.items() if k != 'AOS_KERNEL_HOME'}
        result = self.raw_cli('ls', '--target', self.home, env=env, cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith('health '))
        result = self.raw_cli('ls', env=dict(env, AOS_KERNEL_HOME=str(self.home)), cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.raw_cli('ls', env=env, cwd=self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('kernel  沒 boot 過', result.stdout)
        missing = self.root / 'nope'
        for args, extra, cwd, source in [
                (('--target', missing), {}, self.root, '取自 --target）'),
                ((), {'AOS_KERNEL_HOME': str(missing)}, self.root, '取自 AOS_KERNEL_HOME）'),
                ((), {}, self.root, '取自 目前資料夾（沒給 --target、也沒設 AOS_KERNEL_HOME））')]:
            with self.subTest(source=source):
                result = self.raw_cli('ls', *args, env=dict(env, **extra), cwd=cwd)
                self.assertEqual(result.returncode, 1)
                where = missing if args or extra else self.root
                self.assertTrue(result.stderr.rstrip().endswith('（K＝%s，%s' % (where, source)), result.stderr)
                self.assertEqual(len(result.stderr.splitlines()), 1)

    def test_positional_kernel_is_usage_error(self):
        self.initialize()
        result = self.raw_cli('ls', self.home)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.startswith('aos-kernel: Usage: '))
        result = self.raw_cli('ls', '--target', '')
        self.assertEqual(result.returncode, 2)

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
            for command in ('init', 'boot', 'tick', 'add', 'rm', 'ls', 'halt', 'ack', 'check'):
                self.assertIn(command, result.stdout)
            self.assertNotIn('stop', result.stdout)

    def test_subcommand_help(self):
        for command in ('init', 'boot', 'tick', 'add', 'rm', 'ls', 'halt', 'ack', 'check'):
            result = self.good_cli(command, '-h')
            self.assertIn('--target', result.stdout)
            self.assertIn('usage: aos-kernel ' + command, result.stdout)
            if command == 'add':
                self.assertIn('--once', result.stdout)
                self.assertIn('INST', result.stdout)
            if command in ('boot', 'check'):
                self.assertIn('--daemon-target', result.stdout)

    def test_ls_json_matches_status_without_ledger(self):
        self.initialize()
        actual = json.loads(self.good_cli('ls', self.home, '--json').stdout)
        self.assertEqual(actual["health"]["code"], "stopped")
        self.assertEqual(actual["_metainfo"], {"_type": "aos_kernel_ls", "_version": 1})
        self.assertEqual([c["name"] for c in actual["cpus"]], list(self.info["cpus"]))
        self.assertEqual((actual["procs"], actual["queue"]), ([], []))
        self.assertIsNone(actual["kernel"]["phase"])

    def test_ls_summary_includes_cpus_and_procs(self):
        self.setup_running()
        self.add(self.job('raise SystemExit(100)'), 'visible')
        self.kernel_stop()
        expected = kernel.status(self.home)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(kernel.main(['ls', '--target', str(self.home), '--json']), 0)
        actual = json.loads(output.getvalue())
        self.assertEqual(actual["health"]["code"], "stopped")
        visible = next(p for p in actual["procs"] if p["name"] == "visible")
        self.assertEqual({k: visible[k] for k in ("once", "status", "runs", "fails")},
                         {k: expected["procs"]["visible"][k] for k in ("once", "status", "runs", "fails")})
        self.assertEqual(actual["kernel"]["last_seq"], expected["last_seq"])
        summary = self.good_cli('ls', self.home).stdout
        self.assertFalse(summary.startswith('{'))
        rows = {line.split()[0]: line for line in summary.splitlines() if line.startswith('  ')}
        self.assertIn('  池 ', summary)
        for name in self.info['cpus']:
            self.assertTrue(any(line.split()[:2] in (['kernel', name], ['llm', name], ['default', name], [name])
                                or (len(line.split()) > 1 and line.split()[1] == name)
                                for line in summary.splitlines() if line.startswith('  ')), name)
        self.assertIn('visible', rows)
        self.assertIn('反覆', rows['visible'])
        self.assertIn('queue ', summary)

    def test_ls_summary_without_ledger(self):
        self.initialize()
        text = self.good_cli('ls', self.home).stdout
        self.assertIn('kernel  沒 boot 過  seq -  daemon dead', text)
        self.assertIn('  kcpu -  沒在跑  requests 0', text)
        self.assertIn('（daemon 沒在跑，孩子狀態不明）', text)  # fix-r5：不印孩子表的舊狀態
        row = next(line for line in text.splitlines() if line.split()[:2] == ['llm', 'llm'])
        self.assertEqual(row.split()[2:], ['閒', '-', '-'])
        self.assertIn('proc    0 個', text)
        self.assertIn('queue   -', text)

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

    def test_new_help_and_usage(self):
        for command, flags in [('init', ['--config']), ('halt', ['--wait-ms', '--no-wait']), ('check', ['--daemon-target', '--probe']), ('ls', ['--json', '--verbose'])]:
            text = self.good_cli(command, '-h').stdout
            for flag in flags:
                self.assertIn(flag, text)
            if command == 'check':
                self.assertNotIn('--agent', text)  # advice-r1：搬到 aos-agent check
        for args in [('halt', '--wait-ms', '-1'), ('check', '--unknown'), ('stop',), ('check', '--daemon', 'D')]:
            self.assertEqual(self.cli(args[0], self.home, *args[1:]).returncode, 2)

    def test_halt_without_ledger_posts_nothing(self):
        self.initialize()
        self.assertEqual(self.good_cli('halt', self.home).stdout, 'stopped\n')
        self.assertEqual(list((self.home / 'requests').iterdir()), [])

    def test_halt_no_wait_posts_without_info_or_ledger(self):
        (self.home / "requests").mkdir(parents=True)
        result = self.good_cli('halt', self.home, '--no-wait')
        self.assertEqual((result.stdout, result.stderr), ('', ''))
        files = list((self.home / 'requests').glob('stop-*.json'))
        self.assertEqual(len(files), 1)
        self.assertEqual(read_json(files[0])['method'], 'stop')

    def test_halt_dead_daemon_and_missing_kernel_cpu_do_not_post(self):
        from unittest.mock import patch
        self.initialize(daemon=str(self.daemon))
        self.write(self.home / 'state.json', {'phase': 'running', 'cpus': {}, 'kcpu': 'k'})
        for alive in (False, True):
            with patch.object(kernel.aos_daemon, 'is_alive', return_value=alive), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(kernel.stop(self.home), 0)
            self.assertEqual(out.getvalue(), 'not running\n')
            self.assertEqual(list((self.home / 'requests').iterdir()), [])

    def test_halt_ignores_other_kernel_same_names(self):
        self.initialize(daemon=str(self.daemon))
        self.write(self.home / 'state.json', {'phase': 'stopped', 'cpus': {'0': {}}, 'kcpu': 'k'})
        self.write(self.daemon / 'state.json', {'children': {
            'k': {'target': str(self.root / 'other/cpus/k/inst.json')},
            '0': {'target': str(self.home / 'cpus-other/0/inst.json')}}})
        self.assertEqual(self.good_cli('halt', self.home).stdout, 'stopped\n')
        self.assertEqual(list((self.home / 'requests').iterdir()), [])

    def test_halt_waits_for_removed_and_ledger_only_cpus(self):
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

    def test_halt_timeout_retains_posted_request(self):
        from unittest.mock import patch
        self.initialize(daemon=str(self.daemon))
        self.write(self.home / 'state.json', {'phase': 'running', 'cpus': {}, 'kcpu': 'k'})
        self.write(self.daemon / 'state.json', {'children': {'k': {'target': str(self.home / 'cpus/k/inst.json')}}})
        with patch.object(kernel.aos_daemon, 'is_alive', return_value=True), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(kernel.main(['halt', '--target', str(self.home), '--wait-ms', '0']), 1)
        self.assertEqual(err.getvalue(), 'aos-kernel: Timeout: 等了 0 ms 還沒停好（stop 已放、不撤回），用 aos-kernel ls --target %s 看（K＝%s，取自 --target）\n' % (self.home, self.home))
        self.assertEqual(len(list((self.home / 'requests').glob('stop-*.json'))), 1)

    def test_halt_real_daemon_returns_after_children_disappear(self):
        self.setup_running()
        self.assertEqual(self.good_cli('halt', self.home).stdout, 'stopped\n')
        self.assertEqual(self.state()['phase'], 'stopped')
        self.assertEqual(self.dstate()['children'], {})
        self.assertEqual(self.good_cli('halt', self.home).stdout, 'stopped\n')

    def test_bad_agent_summary_points_to_stderr_and_json_unchanged(self):
        self.initialize()
        agent = self.root / 'agent'
        agent.mkdir()
        target = agent / 'tick.json'
        for stderr in ('log/agent.err', {'$opt': 'append', '$val': 'log/agent.err'}):
            self.write(target, {'argv': ['aos-agent', 'tick', '--target', str(agent)], 'stderr': stderr})
            proc = dict(target=str(target), once=False, status='bad', runs=3, fails=3, pending=None)
            self.write(self.home / 'state.json', {'procs': {'agent': proc}})
            text = self.good_cli('ls', self.home).stdout
            self.assertIn('  agent 壞了，看 %s\n' % (agent / 'log/agent.err'), text)
            data = json.loads(self.good_cli('ls', self.home, '--json').stdout)
            self.assertEqual(data['procs'][0]['look'], str(agent / 'log/agent.err'))
            self.assertEqual({k: data['procs'][0][k] for k in ('target', 'once', 'status', 'runs', 'fails')},
                             {k: proc[k] for k in ('target', 'once', 'status', 'runs', 'fails')})

    def test_bad_summary_stderr_fallbacks(self):
        target = self.root / 'inst.json'
        self.assertEqual(kernel._stderr_hint(str(target)), str(target))
        for value in ({'$env': 'ERR'}, {'$opt': 'append', '$val': {'$env': 'ERR'}}, None):
            self.write(target, {'stderr': value})
            self.assertEqual(kernel._stderr_hint(str(target)), str(target) + ' 的 stderr 設定')

    def fake_daemon_snapshot(self, phase='running', alive=True, missing=True):
        import fcntl
        self.initialize(daemon=str(self.daemon))
        if alive:
            lock = (self.daemon / '.daemon.lock').open('w')
            self.addCleanup(lock.close)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.write(self.home / 'state.json', {'phase': phase, 'kcpu': 'k'})
        children = {} if missing else {
            name: {'target': str(self.home / 'cpus' / name / 'inst.json'), 'state': 'alive'}
            for name in self.info['cpus']}
        self.write(self.daemon / 'state.json', {'children': children})

    def test_ls_missing_cpu_hint_and_json_unchanged(self):
        self.fake_daemon_snapshot()
        text = self.good_cli('ls', self.home).stdout
        row = next(line for line in text.splitlines() if line.split()[:2] == ['kernel', 'k'])
        self.assertEqual(row.split()[2:], ['tick', '-', 'missing'])
        self.assertEqual(text.splitlines()[0],
                         'health 停機中（aos-kernel boot --target %s --daemon-target %s）' %
                         (self.home, self.daemon))
        actual = json.loads(self.good_cli('ls', self.home, '--json').stdout)
        self.assertEqual(actual["health"]["code"], "stopped")
        self.assertEqual({c["name"]: c["child"] for c in actual["cpus"]}, dict.fromkeys(self.info["cpus"], "missing"))

    def test_ls_all_cpus_present_has_no_hint(self):
        self.fake_daemon_snapshot(missing=False)
        self.assertNotIn('hint ', self.good_cli('ls', self.home).stdout)

    def test_ls_stopped_missing_cpus_has_no_restart_hint(self):
        self.fake_daemon_snapshot(phase='stopped')
        self.assertNotIn('hint ', self.good_cli('ls', self.home).stdout)

    def test_ls_stopping_missing_cpus_has_restart_hint(self):
        self.fake_daemon_snapshot(phase='stopping')
        self.assertTrue(self.good_cli('ls', self.home).stdout.startswith('health 停機中（'))

    def test_ls_dead_daemon_hint(self):
        self.fake_daemon_snapshot(alive=False)
        self.assertEqual(self.good_cli('ls', self.home).stdout.splitlines()[0],
                         'health 停機中（aos-kernel boot --target %s --daemon-target %s）' %
                         (self.home, self.daemon))

    def test_ls_hint_default_daemon_and_absolute_kernel(self):
        import os
        from unittest.mock import patch
        self.initialize()
        out = io.StringIO()
        with patch.dict(os.environ, {'AOS_DAEMON_HOME': str(self.daemon)}), contextlib.redirect_stdout(out):
            self.assertEqual(kernel.main(['ls', '--target', os.path.relpath(self.home)]), 0)
        self.assertIn('aos-kernel boot --target %s --daemon-target %s' % (self.home, self.daemon), out.getvalue())

    def test_check_old_agent_flag_points_to_aos_agent_check(self):
        for extra in (('--agent', 'A'), ('--agent', 'A', '--agent=B'), ('--agent',)):
            with self.subTest(extra=extra):
                result = self.cli('check', self.home, *extra)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertEqual(len(result.stderr.splitlines()), 1)
                self.assertIn('aos-kernel: Usage: --agent 搬走了：agent 的檢查改用 aos-agent check --target %s'
                              % ('DIR' if len(extra) == 1 else 'A'), result.stderr)

    def test_check_repeated_daemon_is_usage_error(self):
        result = self.cli('check', self.home, '--daemon-target=A', '--daemon-target', 'B')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr,
                         'aos-kernel: Usage: --daemon-target 只能給一次；要查多個請分開跑 check\n')

    def test_check_single_options_pass_scalar_values(self):
        from unittest.mock import patch
        with patch('aos_kernel_check.check', return_value=0) as check:
            self.assertEqual(kernel.main(['check', '--target', str(self.home), '--daemon-target', 'D']), 0)
        check.assert_called_once_with(str(self.home), 'D', note=check.call_args.kwargs['note'], probe=False)

    def test_check_omitted_options_pass_none(self):
        from unittest.mock import patch
        with patch('aos_kernel_check.check', return_value=0) as check:
            self.assertEqual(kernel.main(['check', '--target', str(self.home)]), 0)
        check.assert_called_once_with(str(self.home), None, note=check.call_args.kwargs['note'], probe=False)
