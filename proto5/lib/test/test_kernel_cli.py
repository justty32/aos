"""kernel CLI（kernel-cli.md）：--target、init、help、ack、ls 的按池摘要與行程計數。用假 daemon，不拉真行程。"""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import aos_home
import aos_kernel as kernel
import aos_kernel_ls
from _kernel_fake import FakeCase

CLI = Path(__file__).resolve().parents[2] / "cli" / "aos-kernel"
COMMANDS = ('init', 'boot', 'cpu', 'tick', 'add', 'rm', 'ls', 'halt', 'ack', 'check')


class CLICase(FakeCase):
    def main(self, *args, code=0, target=True):
        args = [str(a) for a in args]
        if target:
            depth = 2 if args[0] == 'cpu' else 1
            args = [*args[:depth], '--target', str(self.K), *args[depth:]]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = kernel.main(args)
        self.assertEqual(result, code, out.getvalue() + err.getvalue())
        return out.getvalue(), err.getvalue()

    def raw_cli(self, *args, cwd=None, env=None):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], cwd=cwd, env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)

    def config(self, value, name='kernel.json'):
        path = self.root / name
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding='utf-8')
        return path


class Init(CLICase):
    def test_init_without_config_has_only_kernel_pool(self):
        env = {k: v for k, v in os.environ.items() if k != 'AOS_DAEMON_HOME'}
        with patch.dict(os.environ, env, clear=True):
            out, _ = self.main('init')
        self.assertEqual(out, 'initialized %s\n' % self.K)
        info = self.info()
        self.assertEqual(info['pools'], {'kernel': {'count': 1}})
        self.assertNotIn('daemon', info)
        for name in ('requests', 'responses', 'pools'):
            self.assertTrue((self.K / name).is_dir())
        self.assertFalse((self.K / 'cpus').exists())

    def test_init_config_and_daemon_sources(self):
        config = self.config({'pools': {'default': {'count': 2}}, 'tick_ms': 250, 'daemon': '/abs/Dc'})
        self.main('init', '--config', config)
        info = self.info()
        self.assertEqual(info['pools'], {'default': {'count': 2}, 'kernel': {'count': 1}})
        self.assertEqual((info['tick_ms'], info['daemon']), (250, '/abs/Dc'))
        self.assertEqual(info['_metainfo'], {'_type': 'kernel', '_version': 2})
        other = self.root / 'K2'
        self.main('init', '--target', self.root / 'K3', '--config', config, '--daemon', 'Dx', target=False)
        self.assertEqual(aos_home.read_json(self.root / 'K3' / 'info.json')['daemon'], os.path.abspath('Dx'))
        with patch.dict(os.environ, {'AOS_DAEMON_HOME': str(self.root / 'De')}):
            self.main('init', '--target', other, '--config', self.config({'pools': {}}, 'e.json'), target=False)
        self.assertEqual(aos_home.read_json(other / 'info.json')['daemon'], str(self.root / 'De'))

    def test_init_existing_home_refused(self):
        self.main('init')
        _, err = self.main('init', code=1)
        self.assertTrue(err.startswith('aos-kernel: AlreadyExists: '), err)

    def test_init_bad_config_exit_1_without_writes(self):
        cases = ['{', '[]', 'null', {'pools': []}, {'pools': {'kernel': {'count': 2}}}, {'pools': {'a/b': {'count': 1}}},
                 {'pools': {'x': {}}}, {'pools': {}, 'tick_ms': -1}, {'pools': {}, 'daemon': 'relative'},
                 {'pools': {}, '_metainfo': {'_type': 'daemon', '_version': 1}}]
        for i, value in enumerate(cases):
            with self.subTest(config=value):
                _, err = self.main('init', '--config', self.config(value, 'bad%d.json' % i), code=1)
                self.assertEqual(len(err.splitlines()), 1)
                self.assertIn('K＝%s，取自 --target' % self.K, err)
                self.assertFalse(self.K.exists())
        _, err = self.main('init', '--config', self.root / 'missing.json', code=1)
        self.assertTrue(err.startswith('aos-kernel: ReadFailed: '))


class Help(CLICase):
    def test_help_lists_all_commands(self):
        for flag in ('-h', '--help'):
            result = self.raw_cli(flag)
            self.assertEqual(result.returncode, 0, result.stderr)
            for command in COMMANDS:
                self.assertIn(command, result.stdout)
            self.assertNotIn('stop', result.stdout)

    def test_subcommand_help(self):
        for command in COMMANDS:
            result = self.raw_cli(command, '-h')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('usage: aos-kernel ' + command, result.stdout)
            if command != 'cpu':
                self.assertIn('--target', result.stdout)
            self.assertNotIn('--daemon-target', result.stdout if command != 'check' else '')
        text = self.raw_cli('init', '-h').stdout
        self.assertIn('aos-kernel cpu add', text)
        self.assertIn('"AOS_LLM_CONFIG"', text)
        text = self.raw_cli('ls', '-h').stdout
        for flag in ('--pool', '--procs', '--json'):
            self.assertIn(flag, text)

    def test_cpu_help(self):
        text = self.raw_cli('cpu', '-h').stdout
        for word in ('add', 'rm', 'ls', 'aos-kernel cpu rm default/3', '下次 boot'):
            self.assertIn(word, text)
        for sub, flags in (('add', ('--pool', '--count', '--env', '--daemon', '--dpool', '--target')),
                           ('rm', ('P/<i>', '--pool', '--count', '--target')), ('ls', ('--pool', '--json', '--target'))):
            result = self.raw_cli('cpu', sub, '-h')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('usage: aos-kernel cpu ' + sub, result.stdout)
            for flag in flags:
                self.assertIn(flag, result.stdout)

    def test_usage_errors(self):
        self.init({})
        for args in [('halt', '--wait-ms', '-1'), ('check', '--unknown'), ('stop',), ('cpu',), ('cpu', 'nope'),
                     ('boot', '--daemon-target', 'D'), ('init', '--cpu', 'x'), ('ls', '--pool', ''),
                     ('check', '--daemon', 'D')]:
            with self.subTest(args=args):
                result = self.raw_cli(*args, '--target', self.K)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertTrue(result.stderr.startswith('aos-kernel: '), result.stderr)

    def test_positional_kernel_and_empty_target(self):
        self.init({})
        self.assertEqual(self.raw_cli('ls', self.K).returncode, 2)
        self.assertEqual(self.raw_cli('ls', '--target', '').returncode, 2)
        self.assertEqual(self.raw_cli('cpu', 'ls', '--target', '').returncode, 2)

    def test_target_three_sources_and_error_names_source(self):
        self.init({})
        env = {k: v for k, v in os.environ.items() if k != 'AOS_KERNEL_HOME'}
        for args, extra, cwd in ((('--target', self.K), {}, self.root), ((), {'AOS_KERNEL_HOME': str(self.K)}, self.root),
                                 ((), {}, self.K)):
            result = self.raw_cli('ls', *args, env=dict(env, **extra), cwd=cwd)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.startswith('health 停機中'))
            result = self.raw_cli('cpu', 'ls', *args, env=dict(env, **extra), cwd=cwd)
            self.assertEqual(result.returncode, 0, result.stderr)
        missing = self.root / 'nope'
        for args, extra, source in [
                (('--target', missing), {}, '取自 --target）'),
                ((), {'AOS_KERNEL_HOME': str(missing)}, '取自 AOS_KERNEL_HOME）'),
                ((), {}, '取自 目前資料夾（沒給 --target、也沒設 AOS_KERNEL_HOME））')]:
            with self.subTest(source=source):
                result = self.raw_cli('ls', *args, env=dict(env, **extra), cwd=self.root)
                self.assertEqual(result.returncode, 1)
                where = missing if args or extra else self.root
                self.assertTrue(result.stderr.rstrip().endswith('（K＝%s，%s' % (where, source)), result.stderr)
                self.assertEqual(len(result.stderr.splitlines()), 1)


class Ls(CLICase):
    def running(self):
        self.init({'default': {'count': 2}, 'llm': {'count': 1}})
        self.boot()
        self.settle()

    def test_ls_without_ledger(self):
        self.init({'default': {'count': 2}})
        lines = self.main('ls')[0].splitlines()
        self.assertEqual(lines[0], 'health 停機中（aos-kernel boot --target %s）' % self.K)
        self.assertTrue(lines[1].startswith('kernel  沒 boot 過  seq -  daemon alive  tick '), lines[1])
        self.assertEqual(lines[2], '  kcpu kernel/0  沒在跑  requests 0')
        self.assertEqual(lines[3], 'pool    1 個工作池：要 2 顆、忙 0、閒 0')
        self.assertTrue(lines[4].startswith('  kernel   want 1  sent -'), lines[4])
        self.assertTrue(lines[5].startswith('  default  want 2  sent -'), lines[5])
        self.assertEqual(lines[6:], ['proc    0 個', 'queue   -'])

    def test_ls_pools_counts_and_bad(self):
        self.running()
        self.add('a')
        self.add('b')
        self.add('c', pool='llm')
        self.tick()
        state = self.state()
        state['procs']['b'].update(status='bad')
        state['procs']['z'] = dict(state['procs']['a'], status='done')
        aos_home.write_state(self.K, state)
        aos_home.write_json(self.root / 'work.json', {'argv': ['x'], 'stderr': 'log/err.txt'})
        lines = self.main('ls')[0].splitlines()
        self.assertTrue(lines[4].startswith('  kernel '), lines[4])
        self.assertTrue(lines[5].startswith('  default  want 2  sent 2  busy 2  idle 0  draining 0   daemon default: running 2'), lines[5])
        self.assertTrue(lines[6].startswith('  llm      want 1  sent 1  busy 1  idle 0'), lines[6])
        self.assertEqual(lines[7], 'proc    4 個（反覆 4、once 0）：bad 1、done 1、running 2')
        self.assertEqual(lines[9].split(), ['b', '反覆', 'bad', '0', '0', '-'])
        self.assertEqual(lines[10], '  （其餘 3 個沒事的沒列；--procs 全列）')
        self.assertEqual(lines[11], '  b 壞了，看 %s' % (self.root / 'log/err.txt'))
        self.assertEqual(lines[12], 'queue   -')
        self.assertEqual(len(lines), 13)
        procs = self.main('ls', '--procs')[0].splitlines()[9:13]
        self.assertEqual([line.split()[0] for line in procs], ['a', 'b', 'c', 'z'])

    def test_ls_pool_filter(self):
        self.running()
        self.add('a')
        self.add('c', pool='llm')
        state = self.tick()
        key = state['on']['a']
        lines = self.main('ls', '--pool', 'default', '--procs')[0].splitlines()
        self.assertTrue(lines[4].startswith('  default  want 2'), lines[4])
        self.assertIn('    %s  busy a  daemon pending' % key, lines)
        self.assertEqual(sum(1 for line in lines if line.startswith('    default/')), 2)
        self.assertIn('proc    1 個（反覆 1、once 0）：running 1', lines)
        self.assertEqual(lines[-2].split()[:3], ['a', '反覆', 'running'])
        self.assertNotIn('llm', '\n'.join(lines[3:]))
        data = json.loads(self.main('ls', '--pool', 'llm', '--json')[0])
        self.assertEqual(list(data['pools']), ['llm'])
        self.assertEqual([p['name'] for p in data['procs']], ['c'])
        self.assertEqual([(c['cpu'], c['status']) for c in data['pools']['llm']['cpus']], [('llm/0', 'busy')])
        _, err = self.main('ls', '--pool', 'nope', code=1)
        self.assertTrue(err.startswith('aos-kernel: NotFound: '), err)

    def test_ls_json_follows_status(self):
        self.running()
        data = json.loads(self.main('ls', '--json')[0])
        self.assertIn(data['health']['code'], ('ok', 'stall'))
        status = json.loads(json.dumps(kernel.status(self.K)))
        self.assertEqual((data['kernel']['chain'], data['kernel']['phase'], data['kernel']['last_seq']),
                         (status['chain'], status['phase'], status['last_seq']))
        self.assertEqual({p: r['summary'] for p, r in data['pools'].items()},
                         {p: e['summary'] for p, e in status['pools'].items()})

    def test_ls_error_line(self):
        self.running()
        self.fake.errors['default'] = ['NameTaken']
        self.edit_info(default={'count': 3})
        self.ticks(2)
        lines = self.main('ls')[0].splitlines()
        self.assertEqual(lines[0], 'health 池 default：NameTaken（NameTaken）')
        self.assertIn('daemon default: 錯誤 NameTaken（NameTaken）', lines[5])

    def test_bad_summary_stderr_fallbacks(self):
        target = self.root / 'inst.json'
        self.assertEqual(aos_kernel_ls.stderr_hint(str(target)), str(target))
        for value in ({'$env': 'ERR'}, {'$opt': 'append', '$val': {'$env': 'ERR'}}, None):
            aos_home.write_json(target, {'stderr': value})
            self.assertEqual(aos_kernel_ls.stderr_hint(str(target)), str(target))  # advice-r1：沒有字面 stderr 就指 target
        aos_home.write_json(target, {'stderr': {'$opt': 'append', '$val': 'a.log'}})
        self.assertEqual(aos_kernel_ls.stderr_hint(str(target)), str(self.root / 'a.log'))


class Misc(CLICase):
    def test_ack_missing_response_does_not_post(self):
        self.init({})
        out, err = self.main('ack', '/elsewhere/missing.json', code=1)
        self.assertTrue(err.startswith('aos-kernel: NotFound: '))
        self.assertEqual(out, '')
        self.assertEqual(list((self.K / 'requests').iterdir()), [])

    def test_ack_by_name_or_path(self):
        self.init({})
        for use_path in (False, True):
            name = 'r-%s.json' % use_path
            aos_home.write_json(self.K / 'responses' / name, {'result': {}})
            self.assertEqual(self.main('ack', self.K / 'responses' / name if use_path else name), ('', ''))
            acks = [aos_home.read_json(p) for p in (self.K / 'requests').glob('ack-*.json')]
            self.assertIn(name, [a['params']['name'] for a in acks])

    def test_add_unknown_pool_hints_cpu_add(self):
        self.init({})
        error = aos_home.params_error('x', 'pool 必須是現有的工作池', ['params', 'pool'])
        with patch('aos_client.wait_response', return_value=error), patch('aos_client.ack'):
            _, err = self.main('add', self.root / 'job.json', '--pool', 'gpu', code=1)
        self.assertIn('先 aos-kernel cpu add --target %s --pool gpu' % self.K, err)
        self.assertTrue(err.startswith('aos-kernel: FieldTypeMismatch: '), err)

    def test_halt_without_ledger_posts_nothing(self):
        self.init({})
        self.assertEqual(self.main('halt')[0], 'stopped\n')
        self.assertEqual(list((self.K / 'requests').iterdir()), [])

    def test_halt_no_wait_posts(self):
        (self.K / 'requests').mkdir(parents=True)
        self.assertEqual(self.main('halt', '--no-wait'), ('', ''))
        files = list((self.K / 'requests').glob('stop-*.json'))
        self.assertEqual(len(files), 1)

    def test_check_repeated_daemon_is_usage_error(self):
        out, err = self.main('check', '--daemon-target', 'A', '--daemon-target=B', code=2)
        self.assertEqual(out, '')
        self.assertEqual(err, 'aos-kernel: Usage: --daemon-target 只能給一次；要查多個請分開跑 check\n')

    def test_check_old_agent_flag_points_to_aos_agent_check(self):
        for extra in (('--agent', 'A'), ('--agent', 'A', '--agent=B'), ('--agent',)):
            with self.subTest(extra=extra):
                out, err = self.main('check', *extra, code=2)
                self.assertEqual(out, '')
                self.assertEqual(len(err.splitlines()), 1)
                self.assertIn('aos-kernel: Usage: --agent 搬走了：agent 的檢查改用 aos-agent check --target %s'
                              % ('DIR' if len(extra) == 1 else 'A'), err)

    def test_check_options_pass_scalars(self):
        with patch('aos_kernel_check.check', return_value=0) as check:
            self.main('check', '--daemon-target', 'D')
        check.assert_called_once_with(str(self.K), 'D', note=check.call_args.kwargs['note'], probe=False)
        with patch('aos_kernel_check.check', return_value=0) as check:
            self.main('check')
        check.assert_called_once_with(str(self.K), None, note=check.call_args.kwargs['note'], probe=False)

    def test_bad_agent_summary_points_to_stderr(self):
        self.init({})
        agent = self.root / 'agent'
        agent.mkdir()
        target = agent / 'tick.json'
        for stderr in ('log/agent.err', {'$opt': 'append', '$val': 'log/agent.err'}):
            aos_home.write_json(target, {'argv': ['aos-agent', 'tick', '--target', str(agent)], 'stderr': stderr})
            proc = dict(target=str(target), once=False, status='bad', runs=3, fails=3, pending=None)
            aos_home.write_json(self.K / 'state.json', {'procs': {'agent': proc}})
            text = self.main('ls')[0]
            self.assertIn('  agent 壞了，看 %s\n' % (agent / 'log/agent.err'), text)
            data = json.loads(self.main('ls', '--json')[0])
            self.assertEqual(data['procs'][0]['look'], str(agent / 'log/agent.err'))
            self.assertEqual({k: data['procs'][0][k] for k in ('target', 'once', 'status', 'runs', 'fails')},
                             {k: proc[k] for k in ('target', 'once', 'status', 'runs', 'fails')})
