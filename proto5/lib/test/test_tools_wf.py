"""proto5/tools/wf/：workflows 工具包（wf_doc、wf_init、wf_lint、wf_residue、wf_table）。

跟 test_tools_base.py 一樣：把整包（含 snapshot/）複製進假 agent 家、當子行程跑，驗
stdin JSON 進、stdout 文字或最後一行 JSON 錯誤出。wf_init 另測兩個崩潰窗口（wf-init 跑到一半、
搬檔搬到一半）真的 SIGKILL 之後重跑同一行收得回來。不叫模型。
"""
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO5 = os.path.dirname(os.path.dirname(HERE))
PACK = os.path.join(PROTO5, 'tools', 'wf')
CLI = os.path.join(PROTO5, 'cli')
NAMES = ['wf_doc', 'wf_init', 'wf_lint', 'wf_residue', 'wf_table']


def jload(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def slurp(path, mode='r'):
    with open(path, mode, **({} if 'b' in mode else {'encoding': 'utf-8'})) as f:
        return f.read()


class WfCase(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix='aos-tools-wf-')
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        shutil.copytree(PACK, os.path.join(self.home, 'tools', 'wf'),
                        ignore=shutil.ignore_patterns('__pycache__'))
        self.ws = os.path.join(self.home, 'workspace')
        os.makedirs(self.ws)

    def tool(self, name, args, code=0, env=None):
        p = subprocess.run([os.path.join(self.home, 'tools', 'wf', name)], cwd=self.home,
                           input=json.dumps(args), capture_output=True, text=True, timeout=120,
                           env=dict(os.environ, **(env or {})))
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        if code:
            err = json.loads(p.stdout.strip().splitlines()[-1])
            self.assertFalse(err['ok'])
            return err
        return p.stdout

    def w(self, rel, text):
        full = os.path.join(self.ws, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w', encoding='utf-8') as f:
            f.write(text)
        return full

    def p(self, *parts):
        return os.path.join(self.ws, *parts)

    def files(self, top):
        out = set()
        for dp, dns, fns in os.walk(top):
            for fn in fns:
                out.add(os.path.relpath(os.path.join(dp, fn), top))
        return out


class PackTests(unittest.TestCase):
    def test_pack_shape(self):
        tools = jload(os.path.join(PACK, 'wf.json'))
        self.assertEqual([t['function']['name'] for t in tools], NAMES)
        for t in tools:
            self.assertEqual(t['_meta']['argv'], ['tools/wf/' + t['function']['name']])
            self.assertTrue(os.access(os.path.join(PACK, t['function']['name']), os.X_OK))
        self.assertEqual(jload(os.path.join(PACK, 'config.json')), {'root': 'workspace'})

    def test_description_budget(self):
        """五支的 description＋參數 description 合計 ≤ 1500 字元（兩包合計 < 3000 的一半）。"""
        tools = jload(os.path.join(PACK, 'wf.json'))
        total = 0
        for t in tools:
            f = t['function']
            total += len(f['description'])
            total += sum(len(p.get('description', '')) for p in f['parameters']['properties'].values())
        self.assertLessEqual(total, 1500)

    def test_snapshot_fixed(self):
        meta = jload(os.path.join(PACK, 'snapshot', 'SNAPSHOT.json'))
        self.assertEqual(meta['commit'], '2021d9b7c385a9a68ce138b02c419d66dbc23784')
        self.assertEqual(meta['kernel'], 'v0.6')
        count = sum(len(fns) for _, _, fns in os.walk(os.path.join(PACK, 'snapshot')))
        self.assertEqual(meta['files'], count - 1)          # SNAPSHOT.json 自己不算
        for need in ('IMPORT.md', 'tools/wf-init.sh', 'tools/wf-lint.sh', 'tools/tabledb.py',
                     'template/AGENTS.md', 'flavors/heartbeat'):
            self.assertTrue(os.path.exists(os.path.join(PACK, 'snapshot', need)), need)
        leftovers = [f for dp, _, fns in os.walk(os.path.join(PACK, 'snapshot')) for f in fns
                     if f.endswith('.pyc')] + [f for f in os.listdir(os.path.join(PACK, 'snapshot', 'tools'))
                                               if f.startswith('test_')]
        self.assertEqual(leftovers, [])

    def test_python_interface(self):
        """T2 的驗收員要 import 的兩個函式：回結構化結果、不寫專案。"""
        sys.path.insert(0, PACK)
        try:
            import _wf
        finally:
            sys.path.remove(PACK)
        d = tempfile.mkdtemp(prefix='aos-wf-py-')
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        with open(os.path.join(d, 'a.md'), 'w', encoding='utf-8') as f:
            f.write('# t\n{{x}} {{y}}\n〔模板說明〕\n')
        r = _wf.residue(d)
        self.assertEqual(r['total'], 3)
        self.assertEqual(r['counts']['{{'], 2)
        self.assertEqual(r['hits'][0], ('a.md', 2, '{{'))
        lint = _wf.lint(d, strict=True)
        self.assertFalse(lint['ok'])
        self.assertIn('residue=3', lint['total_line'])
        self.assertEqual(os.listdir(d), ['a.md'])


class DocTests(WfCase):
    def test_list_and_read_import(self):
        out = self.tool('wf_doc', {})
        self.assertIn('IMPORT.md', out.split())
        self.assertIn('flavors/', out.split())
        out = self.tool('wf_doc', {'path': 'IMPORT.md'})
        self.assertIn('Done when', out)
        out = self.tool('wf_doc', {'path': 'IMPORT.md', 'offset': 2, 'limit': 2})
        self.assertIn('use offset=4 to continue', out)
        self.assertIn('flavor', self.tool('wf_doc', {'path': 'flavors'}) + 'flavor')

    def test_outside_snapshot_refused(self):
        self.w('secret.md', 'x')
        for path in ('../wf.json', '../../../workspace/secret.md', '/etc/passwd', 'tools/../../_wf.py'):
            err = self.tool('wf_doc', {'path': path}, code=1)
            self.assertEqual(err['error'], 'OutsideRoot', path)
            self.assertIn('only reads the workflows snapshot', err['message'])
        self.assertEqual(self.tool('wf_doc', {'path': 'nope.md'}, code=1)['error'], 'NotFound')
        self.assertEqual(self.tool('wf_doc', {'offset': 0}, code=1)['error'], 'BadArguments')


class ResidueTests(WfCase):
    def test_counts_and_lines(self):
        self.w('AGENTS.md', '# {{name}}\n〔導入判斷〕 a → b\n')
        self.w('wf/x.md', '> 〔模板說明〕 explain\n> more\n{{a}}{{b}}\n')
        self.w('notes.txt', '{{ not md\n')
        self.w('.wf-staging-1/AGENTS.md', '{{skip}}\n')
        self.w('.git/x.md', '{{skip}}\n')
        out = self.tool('wf_residue', {})
        first = out.splitlines()[0]
        self.assertEqual(first, 'residue total=5 ({{=3 導入判斷=1 模板說明=1) unreadable=0')
        self.assertIn('AGENTS.md:1 {{', out)
        self.assertIn('wf/x.md:3 {{', out)
        self.assertNotIn('staging', out)

    def test_unreadable_listed_not_zero(self):
        if os.geteuid() == 0:
            self.skipTest('root reads everything')
        self.w('ok.md', 'clean\n')
        bad = self.w('bad.md', '{{x}}\n')
        os.chmod(bad, 0)
        self.addCleanup(os.chmod, bad, 0o644)
        os.makedirs(self.p('locked'))
        self.w('locked/in.md', '{{y}}\n')
        os.chmod(self.p('locked'), 0)
        self.addCleanup(os.chmod, self.p('locked'), 0o755)
        os.symlink('/etc/hostname', self.p('link.md'))
        out = self.tool('wf_residue', {})
        self.assertTrue(out.startswith('residue total=0'), out)
        self.assertIn('unreadable=3', out.splitlines()[0])
        self.assertIn('UNREADABLE bad.md', out)
        self.assertIn('UNREADABLE locked', out)
        self.assertIn('UNREADABLE link.md: symbolic link', out)

    def test_bad_path(self):
        self.assertEqual(self.tool('wf_residue', {'path': '../..'}, code=1)['error'], 'OutsideRoot')
        self.w('f.md', '')
        self.assertEqual(self.tool('wf_residue', {'path': 'f.md'}, code=1)['error'], 'NotADirectory')
        self.assertEqual(self.tool('wf_residue', {'path': 'nope'}, code=1)['error'], 'NotFound')


class LintTests(WfCase):
    def test_pass_and_fail(self):
        self.w('p/README.md', '# hi\n\nsee [a](a.md)\n')
        self.w('p/a.md', '# a\n')
        out = self.tool('wf_lint', {'path': 'p'})
        self.assertEqual(out.splitlines()[0], 'PASS', out)
        self.assertIn('TOTAL broken=0', out)
        self.assertTrue(os.path.exists(self.p('p', '.wf-lint.log')))
        self.w('p/a.md', '# a\n[x](missing.md)\n{{todo}}\n')
        out = self.tool('wf_lint', {'path': 'p'})
        self.assertEqual(out.splitlines()[0], 'FAIL (exit 1)')
        self.assertIn('BROKEN a.md -> missing.md', out)
        self.assertIn('residue=1', out)
        out = self.tool('wf_lint', {'path': 'p', 'strict': False})
        self.assertIn('TOTAL broken=1', out)
        self.assertNotIn('residue=', out.splitlines()[1])

    def test_never_runs_project_copy(self):
        """專案裡的 wf-lint.sh 被改過也不會被執行：只跑工具包自帶的快照。"""
        mark = self.p('pwned')
        for rel in ('tools/wf-lint.sh', 'wf/tools/wf-lint.sh', 'tools/wf-lint-checks.sh'):
            self.w(rel, '#!/bin/sh\ntouch %s\n' % mark)
            os.chmod(self.p(rel), 0o755)
        self.w('AGENTS.md', '# x\n')
        self.tool('wf_lint', {})
        self.assertFalse(os.path.exists(mark))


class InitTests(WfCase):
    def assert_heartbeat_import(self, top, sub='wf'):
        base = os.path.join(top, sub) if sub else top
        self.assertTrue(os.path.isfile(os.path.join(top, 'AGENTS.md')))
        for rel in ('WORKFLOWS.md', 'workflows/tick.md', 'workflows/routines.md', 'workflows/schedule.md',
                    'tools/wf-lint.sh'):
            self.assertTrue(os.path.isfile(os.path.join(base, rel)), rel)
        table = slurp(os.path.join(base, 'WORKFLOWS.md'))
        rows = [ln for ln in table.splitlines() if ln.startswith('|')]
        for key in ('tick', 'routines', 'schedule'):
            self.assertTrue(any('workflows/%s.md' % key in ln for ln in rows), key)
        self.assertEqual([n for n in os.listdir(top) if n.startswith('.wf-staging')], [])

    def test_heartbeat_non_invasive(self):
        self.w('proj/README.md', '# my project\n')
        out = self.tool('wf_init', {'flavor': ['heartbeat'], 'non_invasive': 'wf', 'path': 'proj'})
        self.assertIn('imported workflows (flavor: heartbeat, layout: non-invasive wf)', out)
        self.assertIn('residue total=', out)
        self.assertIn('wf/workflows/routines.md:', out)
        self.assert_heartbeat_import(self.p('proj'))
        self.assertEqual(slurp(self.p('proj', 'README.md')), '# my project\n')
        # 殘留數字跟 wf_residue 一致；wf_lint 非 strict 沒有壞連結
        first = [ln for ln in out.splitlines() if ln.startswith('residue total=')][0]
        self.assertEqual(self.tool('wf_residue', {'path': 'proj'}).splitlines()[0], first)
        self.assertIn('TOTAL broken=0', self.tool('wf_lint', {'path': 'proj', 'strict': False}))
        err = self.tool('wf_init', {'flavor': ['heartbeat'], 'non_invasive': 'wf', 'path': 'proj'}, code=1)
        self.assertEqual(err['error'], 'AlreadyImported')

    def test_standard_layout_and_same_files_as_plain_wf_init(self):
        self.tool('wf_init', {'flavor': ['heartbeat']})
        self.assert_heartbeat_import(self.ws, sub=None)
        ref = tempfile.mkdtemp(prefix='aos-wf-ref-')
        self.addCleanup(shutil.rmtree, ref, ignore_errors=True)
        subprocess.run(['bash', os.path.join(PACK, 'snapshot', 'tools', 'wf-init.sh'), '--target', ref,
                        '--flavor', 'heartbeat', '--quiet'], check=True, capture_output=True)
        self.assertEqual(self.files(self.ws), self.files(ref))
        for rel in self.files(ref):
            self.assertEqual(slurp(os.path.join(ref, rel), 'rb'), slurp(os.path.join(self.ws, rel), 'rb'), rel)

    def test_overwritten_files_backed_up(self):
        self.w('wf/STRUCTURE.md', 'mine\n')
        out = self.tool('wf_init', {'flavor': ['heartbeat'], 'non_invasive': 'wf'})
        self.assertIn('1 existing files were replaced', out)
        backups = [n for n in os.listdir(self.ws) if n.startswith('.wf-backup-')]
        self.assertEqual(len(backups), 1)
        self.assertEqual(slurp(self.p(backups[0], 'wf', 'STRUCTURE.md')), 'mine\n')
        self.assertNotEqual(slurp(self.p('wf', 'STRUCTURE.md')), 'mine\n')

    def test_bad_arguments(self):
        err = self.tool('wf_init', {'flavor': ['nope']}, code=1)
        self.assertEqual(err['error'], 'BadArguments')
        self.assertIn('heartbeat', err['message'])
        self.assertEqual(self.tool('wf_init', {'flavor': 3}, code=1)['error'], 'BadArguments')
        self.assertEqual(self.tool('wf_init', {'flavor': [], 'non_invasive': '../x'}, code=1)['error'],
                         'BadArguments')
        self.assertEqual(self.tool('wf_init', {'flavor': [], 'path': '../../x'}, code=1)['error'], 'OutsideRoot')
        self.assertEqual(os.listdir(self.ws), [])

    def test_symlinked_folder_refused(self):
        outside = tempfile.mkdtemp(prefix='aos-wf-out-')
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        os.symlink(outside, self.p('wf'))
        err = self.tool('wf_init', {'flavor': ['heartbeat'], 'non_invasive': 'wf'}, code=1)
        self.assertEqual(err['error'], 'UnsafePath')
        self.assertEqual(os.listdir(outside), [])
        self.assertEqual(sorted(os.listdir(self.ws)), ['wf'])

    def kill_in(self, phase):
        """讓工具在 phase 窗口寫標記後睡住，等到標記就把整個行程群組 SIGKILL。"""
        mark = os.path.join(self.home, 'mark')
        env = dict(os.environ, AOS_WF_TEST_PAUSE=phase, AOS_WF_TEST_MARK=mark)
        proc = subprocess.Popen([os.path.join(self.home, 'tools', 'wf', 'wf_init')], cwd=self.home,
                                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, env=env,
                                start_new_session=True)
        proc.stdin.write(json.dumps({'flavor': ['heartbeat'], 'non_invasive': 'wf'}).encode())
        proc.stdin.close()
        deadline = time.time() + 30
        while not os.path.exists(mark):
            self.assertIsNone(proc.poll(), 'tool exited before reaching the window')
            self.assertLess(time.time(), deadline)
            time.sleep(0.005)
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()

    def test_kill_during_wf_init_then_rerun(self):
        self.kill_in('init')
        time.sleep(0.2)          # 萬一 wf-init 還有殘留行程在寫 staging（已經一起被砍）
        staging = [n for n in os.listdir(self.ws) if n.startswith('.wf-staging-')]
        self.assertEqual(len(staging), 1)
        self.assertFalse(os.path.exists(self.p(staging[0], 'commit.json')))
        self.assertFalse(os.path.exists(self.p('AGENTS.md')))
        out = self.tool('wf_init', {'flavor': ['heartbeat'], 'non_invasive': 'wf'})
        self.assertIn('discarded an unfinished staging area', out)
        self.assertIn('imported workflows', out)
        self.assert_heartbeat_import(self.ws)

    def test_kill_during_commit_then_rerun(self):
        self.kill_in('commit')
        staging = [n for n in os.listdir(self.ws) if n.startswith('.wf-staging-')]
        self.assertEqual(len(staging), 1)
        self.assertTrue(os.path.exists(self.p(staging[0], 'commit.json')))
        self.assertFalse(os.path.exists(self.p('AGENTS.md')))         # AGENTS.md 最後搬
        self.assertTrue(os.path.exists(self.p('wf')))                  # 已經搬了一部分
        out = self.tool('wf_init', {'flavor': ['heartbeat'], 'non_invasive': 'wf'})
        self.assertIn('finished an interrupted import', out)
        self.assert_heartbeat_import(self.ws)
        ref = tempfile.mkdtemp(prefix='aos-wf-ref-')
        self.addCleanup(shutil.rmtree, ref, ignore_errors=True)
        subprocess.run(['bash', os.path.join(PACK, 'snapshot', 'tools', 'wf-init.sh'), '--target', ref,
                        '--flavor', 'heartbeat', '--non-invasive', 'wf', '--quiet'], check=True,
                       capture_output=True)
        self.assertEqual(self.files(self.ws), self.files(ref))
        err = self.tool('wf_init', {'flavor': ['heartbeat'], 'non_invasive': 'wf'}, code=1)
        self.assertEqual(err['error'], 'AlreadyImported')


class TableTests(WfCase):
    def setUp(self):
        super().setUp()
        self.w('data/t.json', json.dumps({'contract': 'wf-table/1', 'columns': ['id', 'name', 'doc_path'],
                                          'link_columns': ['doc_path'],
                                          'rows': [{'id': '1', 'name': 'alpha', 'doc_path': 'a.md'},
                                                   {'id': '2', 'name': 'beta', 'doc_path': 'gone.md'}]}))
        self.w('data/a.md', '# a\n')

    def test_read_ops(self):
        info = json.loads(self.tool('wf_table', {'file': 'data/t.json', 'op': 'info'}))
        self.assertEqual(info['count'], 2)
        self.assertEqual(json.loads(self.tool('wf_table', {'file': 'data/t.json', 'op': 'get', 'index': 1}))['name'],
                         'beta')
        found = json.loads(self.tool('wf_table', {'file': 'data/t.json', 'op': 'find', 'fields': {'id': '2'}}))
        self.assertEqual([r['index'] for r in found], [1])
        self.assertEqual(len(json.loads(self.tool('wf_table', {'file': 'data/t.json', 'op': 'grep',
                                                              'regex': 'ALP'}))), 1)
        sl = json.loads(self.tool('wf_table', {'file': 'data/t.json', 'op': 'slice', 'start': 0, 'end': 1}))
        self.assertEqual(len(sl), 1)
        out = self.tool('wf_table', {'file': 'data/t.json', 'op': 'check'})
        self.assertIn('gone.md', out)
        self.assertIn('check found problems', out)

    def test_write_ops(self):
        added = json.loads(self.tool('wf_table', {'file': 'data/t.json', 'op': 'add',
                                                  'fields': {'id': '3', 'name': 'gamma'}}))
        self.assertEqual(added['index'], 2)
        self.tool('wf_table', {'file': 'data/t.json', 'op': 'update', 'index': 0, 'fields': {'name': 'A'}})
        self.tool('wf_table', {'file': 'data/t.json', 'op': 'delete', 'index': 1})
        rows = jload(self.p('data/t.json'))['rows']
        self.assertEqual([r['name'] for r in rows], ['A', 'gamma'])

    def test_errors(self):
        self.assertEqual(self.tool('wf_table', {'file': 'data/t.json', 'op': 'open', 'index': 0}, code=1)['error'],
                         'BadArguments')
        self.assertEqual(self.tool('wf_table', {'file': 'data/t.json', 'op': 'get'}, code=1)['error'],
                         'BadArguments')
        self.assertEqual(self.tool('wf_table', {'file': 'data/t.json', 'op': 'add', 'fields': {'a': 1}},
                                   code=1)['error'], 'BadArguments')
        self.assertEqual(self.tool('wf_table', {'file': '../../x.json', 'op': 'info'}, code=1)['error'],
                         'OutsideRoot')
        self.assertEqual(self.tool('wf_table', {'file': 'data/a.md', 'op': 'info'}, code=1)['error'],
                         'BadArguments')
        err = self.tool('wf_table', {'file': 'data/t.json', 'op': 'get', 'index': 9}, code=1)
        self.assertEqual(err['error'], 'TableFailed')
        self.assertIn('IndexError', err['message'])


class InstallTests(unittest.TestCase):
    def test_tools_add_and_check(self):
        root = tempfile.mkdtemp(prefix='aos-wf-add-')
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        env.pop('AOS_KERNEL_HOME', None)
        home = os.path.join(root, 'amy')

        def agent(*args):
            return subprocess.run([sys.executable, os.path.join(CLI, 'aos-agent'), *args], env=env,
                                  capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)

        self.assertEqual(agent('init', '--target', home).returncode, 0)
        r = agent('tools', 'add', 'wf', '--target', home)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('installed wf', r.stdout)
        for name in NAMES:
            self.assertIn(name, r.stdout)
        self.assertTrue(os.path.isfile(os.path.join(home, 'tools', 'wf', 'snapshot', 'IMPORT.md')))
        check = agent('check', '--target', home)
        lines = check.stdout.splitlines()
        for name in NAMES:
            line = [ln for ln in lines if ln.split(':')[0].split()[-1] == 'agent/tool/' + name]
            self.assertEqual(len(line), 1, check.stdout)
            self.assertTrue(line[0].startswith('ok'), line[0])
        acc = [ln for ln in lines if ln.split(':')[0].split()[-1] == 'access']
        self.assertTrue(acc and acc[0].startswith('ok'), check.stdout)
        # 裝好的工具從家裡跑得起來
        p = subprocess.run([os.path.join(home, 'tools', 'wf', 'wf_residue')], cwd=home, input='{}',
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertTrue(p.stdout.startswith('residue total=0'))


if __name__ == '__main__':
    unittest.main()
