"""第二波 B 隊 D 項：notes 包的 recall（在記憶與 archive 找原文）、context（記憶多大），
與它們要的牢內映射 mem（模板 notes: true 的成員唯讀掛自己家的 prompts/ → /work/mem）。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import aos_agent_access
import aos_agent_batch
import aos_agent_context
import aos_team_format as fmt
from _kernel_util import CLI, PY, read_json
from test_jail import bwrap_works

PROTO = Path(__file__).resolve().parents[2]
PACKAGE = PROTO / 'tools' / 'notes'
ROSTER = json.loads((PROTO / 'spec/team/examples/team.json').read_text(encoding='utf-8'))


def _call(name, args, cid='c1'):
    return {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': cid, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args, ensure_ascii=False)}}]}


# 有中文、ASCII、工具呼叫、工具結果：token 粗估兩邊要算出同一個數
HISTORY = [
    {'role': 'user', 'content': '請把 README 的安裝一節改短'},
    _call('read', {'path': 'README.md'}),
    {'role': 'tool', 'tool_call_id': 'c1', 'content': '# Install\n' + 'pip install aos ' * 40},
    {'role': 'assistant', 'content': '改好了，安裝一節現在三行。'},
    {'role': 'user', 'content': 'thanks'},
]
ARCHIVED = [
    {'role': 'user', 'content': '先記住：部署密語是 Zebra-Falcon-42，下次問你要答得出來'},
    {'role': 'assistant', 'content': '記住了。'},
    _call('write', {'path': 'deploy.txt', 'content': 'target host = blue-harbor'}, 'c9'),
    {'role': 'tool', 'tool_call_id': 'c9', 'content': 'wrote deploy.txt'},
]


def _env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ('AOS_TOOL_ROOT', 'AOS_MEM_DIR')}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env.update(extra)
    return env


class ToolCase(unittest.TestCase):
    """假 agent 家：tools/notes 複製進去，工具當子行程跑，cwd＝家（不關牢＝記憶在 prompts/）。"""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix='aos-recall-'))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        shutil.copytree(PACKAGE, self.home / 'tools' / 'notes', ignore=shutil.ignore_patterns('__pycache__'))
        self.mem = self.home / 'prompts'
        (self.mem / 'archive').mkdir(parents=True)
        self.write(self.mem / 'history.json', HISTORY)
        self.write(self.mem / 'archive' / 'aaaa1111.json', ARCHIVED + HISTORY[:2])

    @staticmethod
    def write(path, value):
        path.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def run_tool(self, name, args, code=0, env=None, raw=None):
        r = subprocess.run([str(self.home / 'tools' / 'notes' / name)],
                           input=raw if raw is not None else json.dumps(args, ensure_ascii=False),
                           cwd=self.home, capture_output=True, text=True, timeout=20, env=_env(**(env or {})))
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        self.assertEqual(r.stderr, '')
        if code:
            return json.loads(r.stdout.strip().splitlines()[-1])
        return r.stdout


class RecallTests(ToolCase):
    def test_finds_archived_text(self):
        out = self.run_tool('recall', {'query': 'zebra-falcon'})
        self.assertIn('archive/aaaa1111.json 第 1 則 user: ', out)
        self.assertIn('Zebra-Falcon-42', out)
        self.assertNotIn('unreadable', out)

    def test_all_words_case_insensitive_and_tool_calls(self):
        out = self.run_tool('recall', {'query': 'DEPLOY.TXT blue-harbor'})
        self.assertTrue(out.splitlines()[0].startswith('archive/aaaa1111.json 第 3 則 assistant: '), out)
        self.assertIn('write(', out)
        self.assertNotIn('第 4 則', out)                       # 工具結果只有 deploy.txt、沒有 blue-harbor
        self.assertIn('No match', self.run_tool('recall', {'query': 'zebra nothere'}))

    def test_current_memory_first_and_dedup(self):
        """history.json 先找；archive 裡同一則（role＋全文一樣）不再回一次。"""
        out = self.run_tool('recall', {'query': 'readme'})
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith('history.json 第 1 則 user: '), out)
        self.assertEqual(sum('請把 README' in x for x in lines), 1, out)
        self.assertFalse(any(x.startswith('archive/') and '請把' in x for x in lines), out)

    def test_limit_and_snippet_size(self):
        long = [{'role': 'tool', 'tool_call_id': 'c', 'content': ('x' * 1000) + ' needle ' + ('y' * 1000)}
                for _ in range(30)]
        long = [dict(m, content=m['content'] + str(i)) for i, m in enumerate(long)]   # 不讓去重吃掉
        self.write(self.mem / 'archive' / 'bbbb.json', long)
        out = self.run_tool('recall', {'query': 'needle'})
        lines = out.splitlines()
        self.assertEqual(len(lines), 6, out)                    # 預設 5 段＋一行「到上限了」
        self.assertIn('limit 5', lines[-1])
        for line in lines[:-1]:
            snippet = line.split(': ', 1)[1]
            self.assertLessEqual(len(snippet), 300)
            self.assertIn('needle', snippet)
            self.assertTrue(snippet.startswith('…') and snippet.endswith('…'))
        out = self.run_tool('recall', {'query': 'needle', 'limit': 20})
        self.assertLess(len(out), 4000 + 400)                   # 總量有上限
        self.assertIn('cut at 4000', out.splitlines()[-1])

    def test_broken_files_listed_separately(self):
        self.write(self.mem / 'archive' / 'bad.json', '{not json')
        self.write(self.mem / 'archive' / 'obj.json', {'a': 1})
        self.write(self.mem / 'archive' / 'mixed.json', ['junk', 3, {'role': 'user', 'content': 'zebra here too'}])
        out = self.run_tool('recall', {'query': 'zebra', 'limit': 20})
        self.assertIn('unreadable archive/bad.json: not valid JSON', out)
        self.assertIn('unreadable archive/obj.json: not a message array', out)
        self.assertIn('archive/mixed.json 第 3 則 user: zebra here too', out)   # 壞格略過，好的照找
        self.assertIn('Zebra-Falcon-42', out)
        out = self.run_tool('recall', {'query': 'nowhere'})
        self.assertIn('No match', out)
        self.assertIn('unreadable archive/bad.json', out)       # 沒命中也要說有檔讀不了

    def test_empty_memory_and_missing_folder(self):
        shutil.rmtree(self.mem / 'archive')
        (self.mem / 'history.json').unlink()
        self.assertIn('No match', self.run_tool('recall', {'query': 'x'}))
        shutil.rmtree(self.mem)
        self.assertEqual(self.run_tool('recall', {'query': 'x'}, code=1)['error'], 'ConfigInvalid')

    def test_bad_arguments(self):
        for args in ({}, {'query': ''}, {'query': '   '}, {'query': 3}, {'query': 'a' * 201},
                     {'query': 'a', 'limit': 0}, {'query': 'a', 'limit': 21}, {'query': 'a', 'limit': True},
                     {'query': 'a', 'limit': '5'}, {'query': 'a', 'path': '/etc'}):
            with self.subTest(args=args):
                self.assertEqual(self.run_tool('recall', args, code=1)['error'], 'BadArguments')
        self.assertEqual(self.run_tool('recall', None, code=1, raw='[1]')['error'], 'BadArguments')
        self.assertEqual(self.run_tool('recall', None, code=1, raw='{oops')['error'], 'BadArguments')

    def test_where_the_memory_is(self):
        other = self.home / 'elsewhere'
        other.mkdir()
        self.write(other / 'history.json', [{'role': 'user', 'content': 'from-env-dir'}])
        self.assertIn('from-env-dir', self.run_tool('recall', {'query': 'from-env-dir'}, env={'AOS_MEM_DIR': str(other)}))
        self.write(self.home / 'tools' / 'notes' / 'config.json', {'mem': 'elsewhere'})
        self.assertIn('from-env-dir', self.run_tool('recall', {'query': 'from-env-dir'}))
        # 關牢（有 AOS_TOOL_ROOT）時相對路徑不收；沒設就要有 /work/mem
        self.assertEqual(self.run_tool('recall', {'query': 'x'}, code=1, env={'AOS_TOOL_ROOT': '/work/ws'})['error'],
                         'ConfigInvalid')
        (self.home / 'tools' / 'notes' / 'config.json').unlink()
        if not os.path.isdir('/work/mem'):
            e = self.run_tool('recall', {'query': 'x'}, code=1, env={'AOS_TOOL_ROOT': '/work/ws'})
            self.assertIn('/work/mem', e['message'])

    def test_writes_nothing(self):
        before = sorted((p, p.stat().st_mtime_ns) for p in self.home.rglob('*'))
        self.run_tool('recall', {'query': 'zebra'})
        self.run_tool('context', {})
        self.assertEqual(sorted((p, p.stat().st_mtime_ns) for p in self.home.rglob('*')), before)


class ContextTests(ToolCase):
    def test_counts_and_same_tokens_as_lib(self):
        out = self.run_tool('context', {})
        want = aos_agent_context.history_tokens(HISTORY)
        self.assertIn('你的記憶 5 則（user 2／assistant 2／tool 1）、約 %d token。' % want, out)
        self.assertIn('另有壓縮封存 1 份', out)
        fat = [x for x in out.splitlines() if x.startswith('  第 ')]
        self.assertEqual(len(fat), 3)
        self.assertTrue(fat[0].startswith('  第 3 則 tool 約 %d token：# Install'
                                          % aos_agent_context.message_size(HISTORY[2])[1]), fat)

    def test_same_tokens_as_lib_on_varied_memory(self):
        """同一份記憶：工具算的＝aos_agent_context.history_tokens()（牢裡 import 不到 lib，工具抄了一份算法）。"""
        history = ARCHIVED + HISTORY + [
            {'role': 'assistant', 'content': '', 'tool_calls': [
                {'id': 'a', 'type': 'function', 'function': {'name': 'bash', 'arguments': '{"command": "ls -la ／中文"}'}},
                {'id': 'b', 'type': 'function', 'function': {'name': 'read', 'arguments': '{}'}}]},
            {'role': 'tool', 'tool_call_id': 'a', 'content': 'é ü 😀 ' * 7},
            {'role': 'tool', 'tool_call_id': 'b', 'content': ''}]
        self.write(self.mem / 'history.json', history)
        out = self.run_tool('context', {})
        self.assertIn('約 %d token。' % aos_agent_context.history_tokens(history), out.splitlines()[0])
        for i, m in enumerate(history, 1):
            t = aos_agent_context.message_size(m)[1]
            line = next((x for x in out.splitlines() if x.startswith('  第 %d 則 ' % i)), None)
            if line is not None:
                self.assertIn('約 %d token' % t, line)

    def test_empty_and_broken(self):
        (self.mem / 'history.json').unlink()
        self.assertIn('你的記憶 0 則', self.run_tool('context', {}))
        self.write(self.mem / 'history.json', '[')
        self.assertEqual(self.run_tool('context', {}, code=1)['error'], 'ReadFailed')
        self.write(self.mem / 'history.json', {'role': 'user'})
        self.assertEqual(self.run_tool('context', {}, code=1)['error'], 'ReadFailed')
        shutil.rmtree(self.mem)
        self.assertEqual(self.run_tool('context', {}, code=1)['error'], 'ConfigInvalid')

    def test_takes_no_arguments(self):
        self.assertEqual(self.run_tool('context', {'x': 1}, code=1)['error'], 'BadArguments')
        self.assertIn('你的記憶', self.run_tool('context', None, raw=''))


class DescriptionTests(unittest.TestCase):
    def test_short_descriptions(self):
        tools = {t['function']['name']: t for t in json.loads((PACKAGE / 'notes.json').read_text(encoding='utf-8'))}
        self.assertEqual(list(tools), ['note', 'recall', 'context'])
        for name in ('recall', 'context'):
            self.assertLessEqual(len(tools[name]['function']['description']), 160, name)
            self.assertEqual(tools[name]['_meta'], {'argv': ['tools/notes/%s' % name]})
            self.assertTrue(os.access(PACKAGE / name, os.X_OK))


def cli(prog, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', AOS_KERNEL_HOME='')
    return subprocess.run([PY, str(CLI / prog), *map(str, args)], capture_output=True, text=True, timeout=60,
                          env=env, stdin=subprocess.DEVNULL)


class TeamCase(unittest.TestCase):
    """照範例名冊 aos-team init 一個三人團隊（不起 kernel）。"""

    def setUp(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix='aos-team-mem-')))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / 'p').mkdir()
        self.team = self.root / 'team'
        src = self.root / 'roster.json'
        src.write_text(json.dumps(ROSTER, ensure_ascii=False), encoding='utf-8')
        r = cli('aos-team', 'init', '--config', src, '--target', self.team)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.lay = fmt.Layout(self.team)


class MemMountTests(TeamCase):
    """aos-team init：lead、worker 多掛 mem → 自己家的 prompts/（唯讀）；reviewer 沒有。"""

    def test_lead_and_worker_have_mem_readonly(self):
        for name in ('lead', 'worker-1'):
            home = self.lay.member(name)
            self.assertEqual(read_json(home / 'access.json')['mounts']['mem'], {'$opt': 'ro', '$val': 'prompts'})
            table = aos_agent_access.load(str(home))            # 唯讀可以跟信任資料（prompts/）重疊
            self.assertEqual(table['mounts']['mem'], dict(table['mounts']['mem'], path=str(home / 'prompts'), ro=True))
            names = [t['function']['name'] for t in read_json(home / 'tools' / 'notes.json')]
            self.assertEqual(names, ['note', 'recall', 'context'])
        r = cli('aos-agent', 'check', '--target', self.lay.member('lead'))
        self.assertIn('ok   access: ', r.stdout)
        self.assertNotIn('bad  access', r.stdout)

    def test_reviewer_has_no_mem(self):
        home = self.lay.member('reviewer')
        self.assertNotIn('mem', read_json(home / 'access.json')['mounts'])
        self.assertFalse((home / 'tools' / 'notes.json').exists())

    def test_rerun_on_old_home_adds_mem_only(self):
        home = self.lay.member('worker-1')
        access = read_json(home / 'access.json')
        del access['mounts']['mem']
        access['mounts']['extra'] = {'$opt': 'ro', '$val': '../../../p'}
        (home / 'access.json').write_text(json.dumps(access), encoding='utf-8')
        r = cli('aos-team', 'init', '--target', self.team)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('worker-1: access.json 補掛 mem', r.stdout)
        self.assertNotIn('補掛 notes', r.stdout)
        self.assertNotIn('lead: access.json 補掛', r.stdout)
        after = read_json(home / 'access.json')['mounts']
        self.assertEqual(after, dict(access['mounts'], mem={'$opt': 'ro', '$val': 'prompts'}))
        r = cli('aos-team', 'init', '--target', self.team)          # 再跑一次：不再補
        self.assertNotIn('補掛', r.stdout)

    def test_mem_is_reserved(self):
        roster = read_json(self.team / 'team.json')
        roster['members']['worker-2'] = {'template': 'worker', 'mail_to': ['lead'], 'mounts': {'mem': 'p'}}
        (self.team / 'team.json').write_text(json.dumps(roster, ensure_ascii=False), encoding='utf-8')
        r = cli('aos-team', 'init', '--target', self.team)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn('mem', r.stdout + r.stderr)
        self.assertIn('保留', r.stdout + r.stderr)
        self.assertFalse((self.lay.member('worker-2') / '.aos-template.json').exists()
                         and read_json(self.lay.member('worker-2') / '.aos-template.json').get('complete'))


@unittest.skipUnless(bwrap_works(), '這台沒有可用的 bwrap')
class RealJailTests(TeamCase):
    """真的關牢：用成員家的 access 表走送件路徑（tool_inst → aos-jail），recall 找得到自己 archive，/work/mem 寫不進去。"""

    def run_inst(self, home, meta, args):
        table = aos_agent_access.load(str(home))
        env = _env()
        inst = aos_agent_batch.tool_inst(meta, home, 'x', env, access=table)
        return subprocess.run(inst['argv'], cwd=inst['cwd'], input=json.dumps(args, ensure_ascii=False),
                              capture_output=True, text=True, timeout=60, env=env)

    def test_in_jail(self):
        home = self.lay.member('worker-1')
        (home / 'prompts' / 'archive').mkdir()
        (home / 'prompts' / 'archive' / 'cafe.json').write_text(json.dumps(ARCHIVED, ensure_ascii=False))
        (home / 'prompts' / 'history.json').write_text(json.dumps(HISTORY, ensure_ascii=False))
        tools = {t['function']['name']: t for t in read_json(home / 'tools' / 'notes.json')}
        r = self.run_inst(home, tools['recall']['_meta'], {'query': 'zebra-falcon'})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('archive/cafe.json 第 1 則 user: ', r.stdout)
        self.assertNotIn(str(home), r.stdout)
        r = self.run_inst(home, tools['context']['_meta'], {})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('約 %d token。' % aos_agent_context.history_tokens(HISTORY), r.stdout)
        # 同一張表：/work/mem 是唯讀的
        r = self.run_inst(home, {'argv': ['sh', '-c', 'echo x > /work/mem/x']}, {})
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('Read-only', r.stdout + r.stderr)
        self.assertFalse((home / 'prompts' / 'x').exists())
        r = self.run_inst(home, {'argv': ['sh', '-c', 'rm /work/mem/history.json']}, {})
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue((home / 'prompts' / 'history.json').exists())
