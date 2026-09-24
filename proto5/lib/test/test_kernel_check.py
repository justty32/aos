"""啟動前檢查（kernel-cli.md 的 check）：只用假家、flock 與手寫的 summary.json，不啟動 daemon。"""
import contextlib
import fcntl
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import aos_daemon_ticks
import aos_home
import aos_kernel as kernel
import aos_kernel_store
import aos_kernel_check as check


class KernelCheck(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='aos-kcheck-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home, self.daemon = self.root / 'K', self.root / 'D'
        self.daemon.mkdir()
        self.config = self.root / 'llm.json'
        self.put(self.config, {'_metainfo': {'_type': 'llm_config', '_version': 1},
                               'models': {'small': {'endpoint': 'http://localhost:4000/v1', 'model': 'test'}}})
        kernel.init(self.home, {'daemon': str(self.daemon), 'pools': {
            'default': {'count': 1}, 'llm': {'count': 1, 'envs': {'AOS_LLM_CONFIG': str(self.config)}}}})
        self.info = aos_home.read_json(self.home / 'info.json')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for name in check.COMMANDS:
            self.executable(self.bin / name)
        env = patch.dict(os.environ, {'PATH': str(self.bin)})
        env.start()
        self.addCleanup(env.stop)

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        aos_home.write_json(path, value)

    def save(self):
        self.put(self.home / 'info.json', self.info)

    def executable(self, path):
        path.write_text('#!/bin/sh\nexit 0\n')
        path.chmod(0o755)

    def run_check(self, *args, code=0):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = kernel.main(['check', '--target', str(self.home), *map(str, args)])
        self.assertEqual(result, code, out.getvalue() + err.getvalue())
        self.assertEqual(err.getvalue(), '')
        return out.getvalue()

    def run_agent_check(self, agent, *args, code=0):
        """advice-r1：agent 的檢查搬到 aos-agent check；K 由 AOS_KERNEL_HOME 給。"""
        import aos_agent_cli
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'AOS_KERNEL_HOME': str(self.home)}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = aos_agent_cli.main(['check', '--target', str(agent), *map(str, args)])
        self.assertEqual(result, code, out.getvalue() + err.getvalue())
        self.assertEqual(err.getvalue(), '')
        return out.getvalue()

    def lock_daemon(self, daemon=None, pid=None):
        daemon = daemon or self.daemon
        daemon.mkdir(exist_ok=True)
        lock = (daemon / '.daemon.lock').open('w')
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.put(daemon / 'state.json', {'pid': pid or os.getpid()})

    def agent(self, **fields):
        agent = self.root / 'agent'
        self.put(agent / 'info.json', {'_metainfo': {'_type': 'llm_agent', '_version': 1},
                                      'llm': {'model': 'small'}, **fields})
        return agent

    # ---- 帳本與 daemon 摘要 ----
    def ledger(self, phase='running', pools=None, registered=True, **reg):
        """寫 sqlite 帳本（one-boot）；registered：daemon 那邊有沒有替這個 K 開 tick 的登記（reg 蓋在登記檔上）。"""
        pools = pools or {'default': 1, 'llm': 1}
        entries = {}
        for name, sent in pools.items():
            entry = kernel.new_pool(str(self.daemon), name)
            entry['sent'] = {'count': sent, 'skip': []}
            entries[name] = entry
        aos_kernel_store.write(self.home, {'chain': 'c', 'phase': phase, 'ticker': str(self.daemon),
                                           'pools': entries, 'busy': {}, 'procs': {}})
        path = aos_daemon_ticks.reg_path(self.daemon, self.home)
        if registered:
            self.put(path, {'home': str(self.home), 'cli': '/x/aos-kernel', 'every_ms': 5, 'timeout_ms': 60000, **reg})
        else:
            path.unlink(missing_ok=True)

    def summary(self, dpool, running, **extra):
        self.put(self.daemon / 'pools' / dpool / 'summary.json',
                 {'pool': dpool, 'count': running, 'running': running, 'pending': 0, 'dead': 0, 'failed': 0,
                  'killing': 0, 'draining': 0, **extra})

    # ---- info／daemon／path ----
    def test_valid_info_llm_and_daemon_warning(self):
        text = self.run_check()
        for expected in ('ok   info:', 'warn daemon: daemon 沒在跑：%s（池 default、llm）；aos up 會開它' % self.daemon,
                         'ok   path:', check.SHELL_NOTE, 'ok   pools: 池：default 1、llm 1',
                         'ok   llm/llm: 模型代號：small', '設定檢查通過；未測模型連線'):
            self.assertIn(expected, text)

    def test_bad_info_stops_checks(self):
        self.put(self.home / 'info.json', {})
        text = self.run_check(code=1)
        self.assertEqual(len(text.splitlines()), 1)
        self.assertIn('bad  info: NotAHome:', text)

    def test_every_daemon_in_pool_table_is_checked(self):
        other = self.root / 'D2'
        self.info['pools']['gpu'] = {'count': 1, 'daemon': str(other)}
        self.save()
        self.lock_daemon(pid=999999999)
        text = self.run_check()
        # run.md 碰到的問題 5：daemon 剛開、還沒收到任何 scale 單時，分清楚「kernel 設定的池」跟
        # 「daemon 目前真的有的池」，不要讓人以為 daemon 已經有這些池了。
        self.assertIn('ok   daemon: daemon 活著：%s'
                      '（kernel 設定的池：default、llm；daemon 目前有：還沒有）' % self.daemon, text)
        self.assertIn('warn daemon: daemon 沒在跑：%s（池 gpu）；aos up 會開它（只開 daemon：aos-daemon boot --target %s）' % (other, other), text)

    def test_daemon_alive_reports_pools_it_actually_has(self):
        self.lock_daemon(pid=999999999)
        self.summary('default', 1)
        text = self.run_check()
        self.assertIn('ok   daemon: daemon 活著：%s'
                      '（kernel 設定的池：default、llm；daemon 目前有：default）' % self.daemon, text)

    def test_pool_without_daemon_is_bad(self):
        del self.info['daemon']
        self.save()
        text = self.run_check(code=1)
        self.assertIn('bad  daemon: 池 default 解不出 daemon 家（boot 會報 NoDaemon）', text)

    def test_daemon_target_adds_one_and_supplies_path(self):
        other = self.root / 'D2'
        self.lock_daemon(other, pid=2 ** 31 - 1)
        text = self.run_check('--daemon-target', other)
        self.assertIn('ok   daemon: daemon 活著：%s（--daemon-target，池表沒用到）' % other, text)
        self.assertIn(check.SHELL_NOTE, text)   # /proc 讀不到就退回 shell

    def test_path_missing_commands(self):
        with patch.dict(os.environ, {'PATH': str(self.root / 'missing')}):
            text = self.run_check(code=1)
        self.assertIn('bad  path:', text)
        self.assertIn('export PATH=%s:$PATH' % (Path(check.__file__).resolve().parents[1] / 'cli'), text)

    def test_kernel_daemon_proc_environment(self):
        self.lock_daemon()
        with patch.object(check.shutil, 'which', return_value='/bin/tool'):
            text = self.run_check()
        self.assertIn('（daemon 的 PATH）', text)

    # ---- dirs ----
    def test_required_dirs(self):
        self.assertIn('ok   dirs: requests/、responses/、pools/ 都在', self.run_check())
        for name in ('requests', 'responses', 'pools'):
            (self.home / name).rmdir()
        text = self.run_check(code=1)
        expected = '、'.join(str(self.home / name) + '/' for name in ('requests', 'responses', 'pools'))
        self.assertIn('bad  dirs: 缺 %s；手建的家請 mkdir -p 補上（aos-kernel init 會建）' % expected, text)

    # ---- pools／llm ----
    def test_pools_do_not_require_llm(self):
        del self.info['pools']['llm']
        del self.info['pools']['default']
        self.save()
        text = self.run_check()
        self.assertIn('ok   pools: 池：還沒有工作池', text)
        self.assertIn('warn daemon: daemon 沒在跑：%s（替 kernel 開 tick；池表沒用到）' % self.daemon, text)
        self.assertNotIn('llm/', text)

    def test_legacy_kernel_pool_in_info_warns(self):
        """one-boot：舊 info 還留著 kernel 池＝讀得過、略過、warn 可以刪。"""
        self.info['pools']['kernel'] = {'count': 1}
        self.save()
        text = self.run_check()
        self.assertIn('warn pools: info 還有 kernel 池（舊版留下的）', text)
        self.assertIn('ok   pools: 池：default 1、llm 1', text)

    def test_legacy_ledger_warns(self):
        self.lock_daemon(pid=999999999)
        self.put(self.home / 'state.json', {'chain': 'c', 'phase': 'running', 'pools': {}, 'busy': {}, 'procs': {}})
        text = self.run_check()
        self.assertIn('warn ledger: 帳本還是舊的 K/state.json；aos up（或 aos-kernel boot）會換成 sqlite', text)
        self.assertNotIn('cpus:', text)

    def test_llm_every_pool_with_config(self):
        self.info['pools']['big'] = {'count': 0, 'envs': {'AOS_LLM_CONFIG': str(self.root / 'missing.json')}}
        self.save()
        text = self.run_check(code=1)
        self.assertIn('ok   llm/llm:', text)
        self.assertIn('bad  llm/big:', text)
        self.assertNotIn('llm/default', text)

    def test_llm_invalid_configs(self):
        for value in (str(self.root / 'missing.json'), 'relative.json', ''):
            with self.subTest(value=value):
                self.info['pools']['llm']['envs']['AOS_LLM_CONFIG'] = value
                self.save()
                self.assertIn('bad  llm/llm:', self.run_check(code=1))
        self.info['pools']['llm']['envs']['AOS_LLM_CONFIG'] = str(self.config)
        self.save()
        for raw in ('{', '{}', '{"_metainfo":{"_type":"llm_config","_version":1},"models":{"bad":{}}}'):
            self.config.write_text(raw)
            self.assertIn('bad  llm/llm:', self.run_check(code=1))

    def test_llm_env_reference_and_unknown_directive(self):
        envs = self.info['pools']['llm']['envs']
        envs['AOS_LLM_CONFIG'] = {'$env': 'MODEL_CONFIG'}
        self.save()
        with patch.dict(os.environ, {'MODEL_CONFIG': str(self.config)}):
            self.assertIn('ok   llm/llm:', self.run_check())
        with patch.dict(os.environ, {'PATH': str(self.bin)}, clear=True):
            self.assertIn('bad  llm/llm:', self.run_check(code=1))
        envs['AOS_LLM_CONFIG'] = {'$ref': 'config.json'}
        self.save()
        self.assertIn('無法靜態判斷', self.run_check())

    def test_pool_envs_json_overrides_info(self):
        self.info['pools']['llm']['envs']['AOS_LLM_CONFIG'] = '/does/not/exist'
        self.save()
        envs = self.home / 'pools/llm/envs.json'
        self.put(envs, {'AOS_LLM_CONFIG': str(self.config), 'PATH': str(self.bin)})
        text = self.run_check()
        self.assertIn('warn envs/llm: %s 跟 info 的 envs 不同' % envs, text)
        self.assertIn('ok   path/llm:', text)
        self.assertIn('ok   llm/llm:', text)
        self.put(envs, {'AOS_LLM_CONFIG': str(self.config), 'PATH': '/missing'})
        self.assertIn('bad  path/llm:', self.run_check(code=1))
        self.put(envs, [])
        self.assertIn('bad  envs/llm:', self.run_check(code=1))

    def test_whole_envs_directive_warns(self):
        self.info['pools']['llm']['envs'] = {'$ref': 'envs.json'}
        self.save()
        self.assertNotIn('llm/llm', self.run_check())   # 沒 --agent：看不出有沒有 AOS_LLM_CONFIG 就不查
        self.assertIn('warn llm/llm: envs 無法靜態判斷', self.run_agent_check(self.agent(), code=1))

    # ---- --agent ----
    def test_agent_valid(self):
        text = self.run_agent_check(self.agent())
        for item in ('agent', 'agent/tick.pool', 'agent/llm.pool', 'agent/tool_pool', 'agent/llm.model'):
            self.assertIn('ok   %s:' % item, text)

    def test_agent_uses_only_its_llm_pool(self):
        self.info['pools']['other'] = {'count': 1, 'envs': {'AOS_LLM_CONFIG': str(self.root / 'missing.json')}}
        self.save()
        text = self.run_agent_check(self.agent())
        self.assertIn('ok   llm/llm:', text)
        self.assertNotIn('llm/other', text)
        agent = self.agent(llm={'pool': 'default', 'model': 'small'})
        text = self.run_agent_check(agent, code=1)
        self.assertIn('bad  llm/default: 沒設 AOS_LLM_CONFIG', text)
        self.assertIn('bad  agent/llm.model:', text)

    def test_agent_unknown_kernel_and_empty_pools(self):
        self.info['pools']['empty'] = {'count': 0}
        self.save()
        agent = self.agent(tick={'pool': 'kernel'}, llm={'pool': 'missing', 'model': 'unknown'}, tool_pool='empty')
        text = self.run_agent_check(agent, code=1)
        self.assertIn('bad  agent/tick.pool: 池 kernel 是 kernel 池', text)
        self.assertIn('bad  agent/llm.pool: 池 missing 不在 pools；請修改 agent info，或 aos-kernel cpu add --target %s --pool missing'
                      % self.home, text)
        self.assertIn('warn agent/tool_pool: 池 empty 的 count 是 0，工作會一直排隊', text)
        self.assertIn('bad  agent/llm.model:', text)

    def test_agent_invalid_info(self):
        agent = self.agent()
        self.put(agent / 'info.json', {})
        self.assertIn('bad  agent: MetainfoInvalid:', self.run_agent_check(agent, code=1))

    def test_agent_tools(self):
        agent = self.agent(tools=['tools.json'])
        local = agent / 'tool'
        self.executable(local)

        def tool(name, cmd):
            # 測的是 argv[0] 找不找得到；_jail: false 免得沒 access.json 的 bad（09-24 裁決 4）混進來
            return {'type': 'function', 'function': {'name': name}, '_meta': {'argv': [cmd]}, '_jail': False}
        self.put(agent / 'tools.json', [tool('relative', './tool'), tool('absolute', str(local)), tool('path', 'aos-exec'),
                                       {'type': 'function', 'function': {'name': 'dyn'}, '_meta': {'argv': [{'$env': 'T'}]},
                                        '_jail': False}])
        text = self.run_agent_check(agent)
        self.assertIn('ok   agent/tool/relative', text)
        self.assertIn('ok   agent/tool/path', text)
        self.assertIn('warn agent/tool/dyn:', text)
        local.chmod(0o644)
        self.assertIn('bad  agent/tool/relative', self.run_agent_check(agent, code=1))

    def test_agent_tool_directive_warns(self):
        agent = self.agent(tools=['tools.json'])
        self.put(agent / 'tools.json', [{'type': 'function', 'function': {'name': 'dynamic'},
                                       '_meta': {'argv': [{'$env': 'TOOL'}]}, '_jail': False}])
        self.assertIn('warn agent/tool/dynamic:', self.run_agent_check(agent))
    def test_llm_envs_resolved_in_that_pools_daemon(self):
        """納入審查 P1：池 envs 的 $env 照拉這池的 daemon 的環境解，不是 kernel 池的 daemon。"""
        other = self.root / 'D2'
        good = self.root / 'good.json'
        self.put(good, {'_metainfo': {'_type': 'llm_config', '_version': 1},
                        'models': {'small': {'endpoint': 'http://localhost:4000/v1', 'model': 'test'}}})
        self.info['pools']['llm'] = {'count': 1, 'daemon': str(other),
                                     'envs': {'AOS_LLM_CONFIG': {'$env': 'LLM_PATH'}}}
        self.save()
        envs = {str(self.daemon): {'PATH': str(self.bin), 'LLM_PATH': str(self.root / 'wrong.json')},
                str(other): {'PATH': str(self.bin), 'LLM_PATH': str(good)}}
        with patch('aos_kernel_check.daemon_environment', side_effect=lambda d, alive: (envs[d], '（假）')):
            text = self.run_check()
            self.assertIn('ok   llm/llm: 模型代號：small', text)
            text = self.run_agent_check(self.agent())
            self.assertIn('ok   agent/llm.model:', text)

    # ---- cpus（各池摘要） ----
    def test_cpus_all_present(self):
        self.lock_daemon(pid=999999999)
        self.ledger()
        for pool in ('default', 'llm'):
            self.summary(pool, 1)
        text = self.run_check()
        self.assertIn('ok   cpus: 各池都在 daemon 那邊（default 1、llm 1）', text)
        self.assertIn('ok   tick: daemon %s 每 5 ms 開一格 tick' % self.daemon, text)

    def test_tick_unregistered_error_gone_short(self):
        """one-boot：「kernel cpu 不在」換成「daemon 沒登記替這個 kernel 開 tick」（bad tick）；池的錯與少顆照舊。"""
        self.lock_daemon(pid=999999999)
        for phase in ('running', 'stopping'):
            with self.subTest(phase=phase):
                self.ledger(phase, {'default': 2, 'llm': 1}, registered=False)
                state = aos_kernel_store.read(self.home)
                state['pools']['llm']['error'] = {'code': 'NameTaken', 'message': 'owner /x'}
                aos_kernel_store.write(self.home, state)
                self.summary('default', 1, dead=1)
                text = self.run_check(code=1)
                self.assertIn('bad  tick: daemon %s 沒在替這個 kernel 開 tick：執行 aos up 或 aos-kernel boot --target %s'
                              % (self.daemon, self.home), text)
                self.assertIn('bad  cpus: 池 llm：NameTaken（owner /x）：執行 aos-kernel boot --target %s' % self.home, text)
                self.assertIn('warn cpus: 池 default 少 1 顆（daemon 在補；看 aos-daemon ls --target %s --pool default）'
                              % self.daemon, text)
        self.ledger(fails=4, last_exit=1)
        text = self.run_check(code=1)
        self.assertIn('warn tick: tick 連敗 4 次（最後退出 1）；看 daemon 的 stderr（例如 D/daemon.log）', text)
        self.assertIn('bad  cpus: 池 llm：池不見了', text)

    def test_cpus_skipped_without_ledger_stopped_or_dead_daemon(self):
        self.assertNotIn('cpus:', self.run_check())
        self.ledger()
        self.assertNotIn('cpus:', self.run_check())       # daemon 沒活
        self.lock_daemon(pid=999999999)
        self.ledger('stopped')
        self.assertNotIn('cpus:', self.run_check())

    def test_probe_uses_llm_configs(self):
        with patch.object(check, 'probe_endpoint', return_value=('ok', '通')) as probe:
            text = self.run_check('--probe')
        probe.assert_called_once()
        self.assertIn('ok   probe/small: 通', text)
        self.assertIn('設定檢查通過；模型連線也測過', text)
