"""aos-agent tools new／test／wrap-py（spec/aos-agent/tools-dev.md）。

大部分用 --no-jail 跑（快、不靠 bwrap）；關牢那幾條在 aos-jail 開不起來時 skip。
fixture：test/fixtures/wrap_fixture.py（每種支援的型別各一支、每種拒收原因各一支、實用的 count_words）。
"""
import filecmp
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
PROTO = LIB.parent
CLI = PROTO / 'cli' / 'aos-agent'
FIXTURE = HERE / 'fixtures' / 'wrap_fixture.py'
BASE_COMMON = PROTO / 'tools' / 'base' / '_common.py'
sys.path.insert(0, str(LIB))

import aos_agent_tools_dev as dev  # noqa: E402
from aos_agent_home import AgentError  # noqa: E402

JAIL_OK = dev.jail_ready()[0]
ACCEPTED = ['echo', 'double', 'half', 'negate', 'join_words', 'total', 'pick', 'maybe', 'scale', 'legacy',
            'stats', 'boom', 'not_json', 'no_doc', 'count_words', 'outer']
REJECTED = {'no_annotation': '參數 a 沒有型別註解',
            'star_args': '有 *items',
            'star_kwargs': '有 **options',
            'positional_only': '有 positional-only 參數（/ 前面的 a）',
            'custom_class': '參數 p：型別 Point 不支援',
            'fetch': 'async def（不支援）',
            'cached': '有 decorator（@functools.lru_cache(maxsize=None)）',
            'inner': '不是頂層（在函式 outer 裡）'}


def env():
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for key in ('AOS_TOOL_ROOT', 'AOS_TOOL_FENCE', 'AOS_KERNEL_HOME'):
        e.pop(key, None)
    return e


def agent(*args, cwd, code=None):
    r = subprocess.run([sys.executable, str(CLI), *map(str, args)], cwd=cwd, env=env(), stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=120)
    if code is not None:
        assert r.returncode == code, 'exit %s (want %s)\nstdout:\n%s\nstderr:\n%s' % (r.returncode, code, r.stdout,
                                                                                      r.stderr)
    return r


class Temp(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix='aos-tools-dev-')))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)

    def agent(self, *args, code=None):
        return agent(*args, cwd=self.d, code=code)

    def wrap(self, *extra, code=0):
        return self.agent('tools', 'wrap-py', FIXTURE, *extra, code=code)

    def leftovers(self):
        return [p.name for p in self.d.iterdir() if p.name.startswith('.')]


# ------------------------------------------------------------------ wrap-py：靜態讀 ----

class AnalyzeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = dev.analyze(FIXTURE.read_text(encoding='utf-8'), str(FIXTURE))
        cls.rows = {r[0]: r for r in cls.result['rows']}

    def test_accepted(self):
        self.assertEqual(list(self.result['functions']), ACCEPTED)
        for name in ACCEPTED:
            self.assertEqual(self.rows[name][1], 'ok', name)

    def test_rejection_reasons(self):
        """拒收表逐條對：每支拒收的原因字串要對到。"""
        for name, why in REJECTED.items():
            with self.subTest(name=name):
                self.assertEqual(self.rows[name][1], 'reject')
                self.assertIn(why, self.rows[name][2])

    def test_private_skipped(self):
        self.assertEqual(self.rows['_private'][1:3], ['skip', '私有（底線開頭）'])
        self.assertNotIn('Point', self.rows)                     # 類別不是函式；它的方法（沒有）也不列

    def test_schemas(self):
        tools = {n: dev.tool_entry('fx', n, s)['function'] for n, s in self.result['functions'].items()}
        props = lambda n: tools[n]['parameters']['properties']  # noqa: E731
        self.assertEqual(props('echo')['text'], {'type': 'string'})
        self.assertEqual(props('double')['n'], {'type': 'integer'})
        self.assertEqual(props('half')['x'], {'type': 'number'})
        self.assertEqual(props('negate')['flag'], {'type': 'boolean'})
        self.assertEqual(props('join_words')['words'],
                         {'type': 'array', 'items': {'type': 'string'}, 'description': 'The words to join.'})
        self.assertEqual(props('join_words')['sep'], {'type': 'string', 'description': 'Separator between words.',
                                                      'default': ' '})
        self.assertEqual(tools['join_words']['parameters']['required'], ['words'])
        self.assertEqual(props('total')['counts'], {'type': 'object', 'additionalProperties': {'type': 'integer'},
                                                    'description': 'Name to count.'})   # NumPy 風格
        self.assertEqual(props('pick')['color'], {'type': 'string', 'enum': ['red', 'green', 'blue']})
        self.assertEqual(props('maybe'), {'label': {'type': 'string'}, 'times': {'type': 'integer'}})
        self.assertNotIn('required', tools['maybe']['parameters'])
        self.assertEqual(props('scale')['factor'], {'type': 'number', 'description': 'Multiplier.', 'default': 2.0})
        self.assertEqual(tools['scale']['parameters']['required'], ['value'])
        self.assertEqual(props('legacy')['table'], {'type': 'object', 'additionalProperties': {'type': 'number'}})
        self.assertEqual(tools['join_words']['description'], 'Join words with a separator.')
        self.assertEqual(tools['no_doc']['description'], 'no_doc')
        self.assertEqual(tools['count_words']['description'],
                         'Count words in a text file in the project and return the most common ones.')

    def test_kwonly_recorded(self):
        kinds = {p['name']: p['kind'] for p in self.result['functions']['scale']['params']}
        self.assertEqual(kinds, {'value': 'normal', 'factor': 'kwonly', 'round_to': 'kwonly'})

    def test_no_doc_warning(self):
        self.assertIn('no_doc 沒有 docstring（第一段），描述先用函式名', self.result['warnings'])

    def test_unsupported_types(self):
        cases = {'def f(a: int | str): pass': '聯集只收 X | None',
                 'def f(a: dict[int, str]): pass': 'dict 的鍵只收 str',
                 'def f(a: Literal["a", 1]): pass': 'Literal 的值要是同一種 JSON 型別',
                 'def f(a: tuple[int, int]): pass': '型別 tuple[int, int] 不支援',
                 'def f(a: Any): pass': '型別 Any 不支援',
                 'def f(a: None): pass': '型別 None 不支援'}
        for src, why in cases.items():
            with self.subTest(src=src):
                row = dev.analyze(src)['rows'][0]
                self.assertEqual(row[1], 'reject')
                self.assertIn(why, row[2])

    def test_string_annotation_and_union_none(self):
        r = dev.analyze('import typing\ndef f(a: "int", b: typing.Union[str, None] = None, c: None | bool = None): pass')
        self.assertEqual([p['type'] for p in r['functions']['f']['params']],
                         [{'t': 'int'}, {'t': 'optional', 'of': {'t': 'str'}}, {'t': 'optional', 'of': {'t': 'bool'}}])

    def test_only(self):
        r = dev.analyze(FIXTURE.read_text(encoding='utf-8'), only=['echo', 'double'])
        self.assertEqual(list(r['functions']), ['echo', 'double'])
        self.assertEqual({n: s for n, s, _, _ in r['rows']}['half'], 'skip')
        with self.assertRaises(AgentError) as cm:
            dev.analyze('def f(a: int): pass', only=['g'])
        self.assertEqual(cm.exception.code, 'NotFound')

    def test_redefinition_last_wins(self):
        r = dev.analyze('def f(a: int): pass\ndef f(b: str): pass')
        self.assertEqual(r['rows'][0][1], 'reject')
        self.assertIn('第 2 行又定義了一次', r['rows'][0][2])
        self.assertEqual([p['name'] for p in r['functions']['f']['params']], ['b'])

    def test_syntax_error(self):
        with self.assertRaises(AgentError) as cm:
            dev.analyze('def f(:\n')
        self.assertEqual(cm.exception.code, 'SyntaxError')


# ------------------------------------------------------------------ wrap-py：產包 ----

class WrapCliTests(Temp):
    def test_outputs_package(self):
        out = self.wrap().stdout
        self.assertIn('拒收  custom_class', out)
        self.assertIn('跳過  _private', out)
        pack = self.d / 'wrap_fixture'
        for f in ('wrap_fixture.json', 'run', 'src/wrap_fixture.py', 'wrap.json', '_common.py', 'config.json',
                  'README.md'):
            self.assertTrue((pack / f).is_file(), f)
        self.assertTrue(os.access(pack / 'run', os.X_OK))
        self.assertTrue(filecmp.cmp(pack / '_common.py', BASE_COMMON, shallow=False))
        tools = json.loads((pack / 'wrap_fixture.json').read_text())
        self.assertEqual([t['function']['name'] for t in tools], ACCEPTED)
        for t in tools:
            self.assertNotIn('_jail', t)
            self.assertEqual(t['_meta']['argv'], ['tools/wrap_fixture/run', t['function']['name']])
        info = json.loads((pack / 'wrap.json').read_text())
        self.assertEqual(info['sha256'], hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
        self.assertEqual(info['source'], str(FIXTURE))
        self.assertEqual({r['name']: r['reason'] for r in info['rejected']}.keys(), REJECTED.keys())
        self.assertEqual([r['name'] for r in info['skipped']], ['_private'])
        self.assertIn('generated', info)
        readme = (pack / 'README.md').read_text()
        self.assertIn('不需要任何額外掛載', readme)
        self.assertIn('custom_class', readme)
        self.assertEqual(self.leftovers(), [])

    def test_name_only_out(self):
        (self.d / 'o').mkdir()
        out = self.wrap('--only', 'count_words', '--name', 'words', '--out', 'o').stdout
        self.assertIn('跳過  echo', out)
        tools = json.loads((self.d / 'o/words/words.json').read_text())
        self.assertEqual([t['function']['name'] for t in tools], ['count_words'])
        self.assertEqual(tools[0]['_meta']['argv'], ['tools/words/run', 'count_words'])
        self.assertIn('BadName', self.wrap('--name', 'a.b', code=1).stderr)
        self.assertIn('NotFound', self.wrap('--only', 'nope', code=1).stderr)
        self.assertIn('NotFound', self.wrap('--out', 'missing', code=1).stderr)

    def test_already_exists_and_force(self):
        self.wrap()
        err = self.wrap(code=1).stderr
        self.assertIn('aos-agent: AlreadyExists', err)
        (self.d / 'wrap_fixture' / 'stale').write_text('x')
        self.wrap('--force')
        self.assertFalse((self.d / 'wrap_fixture' / 'stale').exists())
        self.assertEqual(self.leftovers(), [])

    def test_nothing_to_wrap_writes_nothing(self):
        src = self.d / 'bad.py'
        src.write_text('def f(a): pass\nasync def g(b: int): pass\n')
        r = self.agent('tools', 'wrap-py', src, code=1)
        self.assertIn('拒收  f', r.stdout)
        self.assertIn('aos-agent: NothingToWrap', r.stderr)
        self.assertFalse((self.d / 'bad').exists())
        self.assertEqual(self.leftovers(), [])

    def test_unreadable_and_syntax_error(self):
        self.assertIn('aos-agent: NotFound', self.agent('tools', 'wrap-py', 'nope.py', code=1).stderr)
        (self.d / 'broken.py').write_text('def f(:\n')
        self.assertIn('aos-agent: SyntaxError', self.agent('tools', 'wrap-py', 'broken.py', code=1).stderr)
        self.assertFalse((self.d / 'broken').exists())

    def test_default_pack_name_sanitized(self):
        src = self.d / 'my.tool-x.py'
        src.write_text('def f(a: int) -> int:\n    """F."""\n    return a\n')
        self.agent('tools', 'wrap-py', src, code=0)
        self.assertTrue((self.d / 'my_tool-x' / 'my_tool-x.json').is_file())

    def test_wrapped_package_passes_tools_test(self):
        self.wrap()
        out = self.agent('tools', 'test', './wrap_fixture', '--no-jail', code=0).stdout
        self.assertTrue(out.startswith('沒關牢（給了 --no-jail）'), out[:80])
        self.assertIn('PASS  wrap_fixture  import', out)
        self.assertIn('PASS  count_words  ok', out)
        self.assertTrue(out.rstrip().endswith('條，0 條沒過'), out[-200:])

    def test_install_check_and_ls_jail(self):
        """產的包 tools add 進 init 生的家：check 每支 ok、沒有 agent／access 的 bad；tools ls 顯示 jail。"""
        self.wrap()
        self.agent('init', '--target', 'h', code=0)
        self.agent('tools', 'add', './wrap_fixture', '--target', 'h', code=0)
        out = self.agent('check', '--target', 'h').stdout
        for name in ACCEPTED:
            self.assertIn('ok   agent/tool/%s: 可執行 tools/wrap_fixture/run' % name, out)
        bad = [l for l in out.splitlines() if l.startswith('bad') and not l.startswith('bad  kernel')]
        self.assertEqual(bad, [], out)
        ls = self.agent('tools', 'ls', '--target', 'h', '--json', code=0).stdout
        rows = {t['name']: t for t in json.loads(ls)['tools']}
        for name in ACCEPTED:
            self.assertIs(rows[name]['jail'], True, name)


# ------------------------------------------------------------------ wrap-py：run ----

class RunTests(Temp):
    """直接叫產出的 run（不關牢）：cwd＝假 agent 家，工作根目錄＝家裡的 workspace/。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix='aos-tools-dev-run-')))
        agent('tools', 'wrap-py', FIXTURE, '--name', 'fx', cwd=cls.tmp, code=0)
        cls.home = cls.tmp / 'home'
        shutil.copytree(cls.tmp / 'fx', cls.home / 'tools' / 'fx')
        (cls.home / 'workspace').mkdir()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def call(self, fn, args, raw=None):
        r = subprocess.run([str(self.home / 'tools/fx/run'), fn], cwd=self.home, env=env(), capture_output=True,
                           text=True, input=raw if raw is not None else json.dumps(args), timeout=30)
        return r.returncode, r.stdout, r.stderr

    def ok(self, fn, args, want):
        code, out, err = self.call(fn, args)
        self.assertEqual((code, out), (0, want + '\n'), err)

    def bad(self, fn, args, code_name='BadArguments', raw=None, contains=None):
        code, out, err = self.call(fn, args, raw)
        self.assertEqual(code, 1, out + err)
        last = json.loads(out.splitlines()[-1])
        self.assertEqual((last['ok'], last['error']), (False, code_name), out)
        if contains:
            self.assertIn(contains, last['message'])
        return last, out, err

    def test_str_int_float_bool(self):
        self.ok('echo', {'text': 'hi 你好'}, 'hi 你好')
        self.bad('echo', {'text': 1}, contains='must be a string')
        self.ok('double', {'n': 21}, '42')
        self.bad('double', {'n': True}, contains='must be an integer')   # int 不收 bool
        self.bad('double', {'n': 1.5})
        self.ok('half', {'x': 3}, '1.5')                                  # float 收 int
        self.bad('half', {'x': False})
        self.ok('negate', {'flag': False}, 'true')
        self.bad('negate', {'flag': 1}, contains='must be a boolean')

    def test_list_dict(self):
        self.ok('join_words', {'words': ['a', 'b'], 'sep': '-'}, 'a-b')
        self.bad('join_words', {'words': ['a', 1]}, contains='argument "words"[1] must be a string')
        self.bad('join_words', {'words': 'ab'}, contains='must be an array')
        self.ok('total', {'counts': {'a': 1, 'b': 2}}, '3')
        self.bad('total', {'counts': {'a': 'x'}}, contains='argument "counts"["a"] must be an integer')
        self.bad('total', {'counts': [1]}, contains='must be an object')
        self.ok('legacy', {'names': ['n'], 'table': {'b': 1, 'a': 2.5}}, '{"names": ["n"], "keys": ["a", "b"]}')

    def test_literal_optional_kwonly_defaults(self):
        self.ok('pick', {'color': 'red'}, 'picked red')
        self.bad('pick', {'color': 'pink'}, contains='must be one of ["red", "green", "blue"]')
        self.ok('maybe', {}, "label=None times=None")
        self.ok('maybe', {'label': None, 'times': 3}, "label=None times=3")
        self.bad('maybe', {'times': 'x'})
        self.ok('scale', {'value': 1.5, 'factor': 3, 'round_to': 1}, '4.5')
        self.ok('scale', {'value': 2}, '4.0')
        self.ok('scale', {'value': 2, 'factor': None}, '4.0')     # 非必填給 null＝沒給
        self.bad('double', {'n': None}, contains='argument "n" must be an integer')   # 必填給 null＝型別錯

    def test_extra_missing_not_object(self):
        self.bad('echo', {'text': 'a', 'more': 1}, contains='unknown argument(s): more')
        self.bad('echo', {}, contains='missing required argument "text"')
        self.bad('echo', None, raw='[]', contains='must be a JSON object')
        self.bad('echo', None, raw='{bad', contains='not valid JSON')
        self.bad('nosuch', {}, code_name='UnknownFunction')

    def test_returns(self):
        code, out, _ = self.call('stats', {'numbers': [1, 2, 3]})
        self.assertEqual((code, json.loads(out)), (0, {'min': 1.0, 'max': 3.0, 'mean': 2.0}))
        self.bad('not_json', {'n': 1}, code_name='ResultNotJSON', contains='not JSON-serializable')

    def test_python_error_has_no_traceback(self):
        last, out, err = self.bad('boom', {'message': 'kaboom'}, code_name='PythonError')
        self.assertEqual(last['message'], 'ValueError: kaboom')
        self.assertEqual(last['exception'], 'ValueError')
        self.assertNotIn('Traceback', out + err)
        last, out, err = self.bad('stats', {'numbers': []}, code_name='PythonError')   # min() 空序列
        self.assertNotIn('Traceback', out + err)

    def test_count_words_reads_work_root(self):
        (self.home / 'workspace' / 'notes.txt').write_text('The cat and the dog and THE bird\n')
        code, out, err = self.call('count_words', {'path': 'notes.txt', 'top': 2})
        self.assertEqual(code, 0, out + err)
        self.assertEqual(json.loads(out), {'path': 'notes.txt', 'total_words': 8, 'distinct_words': 5,
                                           'top': [['the', 3], ['and', 2]]})
        self.bad('count_words', {'path': 'none.txt'}, code_name='PythonError', contains='FileNotFoundError')

    def test_import_failed(self):
        home = self.d / 'h'
        shutil.copytree(self.home, home)
        (home / 'tools/fx/src/wrap_fixture.py').write_text('import no_such_module_xyz\n')
        r = subprocess.run([str(home / 'tools/fx/run'), 'echo'], cwd=home, env=env(), capture_output=True, text=True,
                           input='{"text": "a"}', timeout=30)
        self.assertEqual(r.returncode, 1)
        last = json.loads(r.stdout.splitlines()[-1])
        self.assertEqual(last['error'], 'ImportFailed')
        self.assertIn('ModuleNotFoundError', last['message'])
        self.assertNotIn('Traceback', r.stdout + r.stderr)
        r = subprocess.run([str(home / 'tools/fx/run'), '--check-import'], cwd=home, env=env(), capture_output=True,
                           text=True, stdin=subprocess.DEVNULL, timeout=30)
        self.assertEqual(r.returncode, 1)
        self.assertIn('ImportFailed', r.stdout)
        # tools test 把它報成一條 FAIL import
        out = agent('tools', 'test', home / 'tools/fx', '--no-jail', '--tool', 'echo', cwd=self.d, code=1).stdout
        self.assertIn('FAIL  fx  import', out)


# ------------------------------------------------------------------ tools new ----

class NewTests(Temp):
    def test_skeleton(self):
        out = self.agent('tools', 'new', 'demo', code=0).stdout
        self.assertIn('下一步', out)
        self.assertIn('aos-agent tools add ./demo --target 家', out)
        pack = self.d / 'demo'
        self.assertEqual(sorted(p.name for p in pack.iterdir()),
                         sorted(['demo.json', 'demo', '_common.py', 'config.json', 'cases.json', 'README.md']))
        self.assertTrue(os.access(pack / 'demo', os.X_OK))
        self.assertIn('# TODO: 在這裡寫你的程式', (pack / 'demo').read_text())
        self.assertTrue(filecmp.cmp(pack / '_common.py', BASE_COMMON, shallow=False))
        tool = json.loads((pack / 'demo.json').read_text())[0]
        self.assertEqual(tool['_meta'], {'argv': ['tools/demo/demo']})
        self.assertNotIn('_jail', tool)
        self.assertEqual(tool['function']['parameters']['required'], ['text'])
        self.assertEqual(json.loads((pack / 'config.json').read_text()), {'root': 'workspace'})
        self.assertIn('tools test ./demo', (pack / 'README.md').read_text())
        self.assertEqual(self.leftovers(), [])

    def test_skeleton_passes_tools_test(self):
        self.agent('tools', 'new', 'demo', code=0)
        out = self.agent('tools', 'test', './demo', '--no-jail', code=0).stdout
        for case in ('program', 'ok', 'type:text', 'type:count', 'missing:text', 'not-object', 'repeat',
                     'missing-text', 'count-not-int', 'count-zero'):
            self.assertIn('PASS  demo  %s  (' % case, out)
        self.assertIn('10 條，0 條沒過', out)

    def test_exists_force_badname_out(self):
        self.agent('tools', 'new', 'demo', code=0)
        self.assertIn('aos-agent: AlreadyExists', self.agent('tools', 'new', 'demo', code=1).stderr)
        (self.d / 'demo' / 'demo').write_text('broken')
        self.agent('tools', 'new', 'demo', '--force', code=0)
        self.assertIn('TODO', (self.d / 'demo' / 'demo').read_text())
        for bad in ('a.b', '.hidden', 'a/b', 'a b'):
            with self.subTest(name=bad):
                self.assertIn('aos-agent: BadName', self.agent('tools', 'new', bad, code=1).stderr)
        self.assertIn('aos-agent: NotFound', self.agent('tools', 'new', 'x', '--out', 'nowhere', code=1).stderr)
        (self.d / 'o').mkdir()
        self.agent('tools', 'new', 'y', '--out', 'o', code=0)
        self.assertTrue((self.d / 'o/y/y.json').is_file())
        self.assertEqual(self.leftovers(), [])

    def test_skeleton_installs_and_checks(self):
        self.agent('tools', 'new', 'demo', code=0)
        self.agent('init', '--target', 'h', code=0)
        self.agent('tools', 'add', './demo', '--target', 'h', code=0)
        out = self.agent('check', '--target', 'h').stdout
        self.assertIn('ok   agent/tool/demo: 可執行 tools/demo/demo', out)
        self.assertEqual([l for l in out.splitlines() if l.startswith('bad') and 'kernel' not in l], [], out)
        self.assertIn('demo  -     tools/demo.json  jail', self.agent('tools', 'ls', '--target', 'h', code=0).stdout)


# ------------------------------------------------------------------ tools test ----

BROKEN = '''#!/usr/bin/env python3
import json, sys
args = json.load(sys.stdin)
print(args["text"].upper())
'''


class TestCmdTests(Temp):
    def pack(self, name='shout', program=BROKEN, tools=None, extra=None):
        pack = self.d / name
        pack.mkdir()
        tools = tools or [{'type': 'function',
                           'function': {'name': name, 'description': 'Shout.',
                                        'parameters': {'type': 'object',
                                                       'properties': {'text': {'type': 'string'}},
                                                       'required': ['text']}},
                           '_meta': {'argv': ['tools/%s/run' % name]}}]
        (pack / (name + '.json')).write_text(json.dumps(tools))
        (pack / 'run').write_text(program)
        os.chmod(pack / 'run', 0o755)
        for rel, body in (extra or {}).items():
            (pack / rel).write_text(body)
        return './' + name

    def test_broken_package_fails(self):
        """型別錯不回 BadArguments、崩出 Traceback＝FAIL；正例照樣 PASS。"""
        r = self.agent('tools', 'test', self.pack(), '--no-jail', code=1)
        out = r.stdout
        self.assertIn('PASS  shout  ok', out)
        for case in ('type:text', 'missing:text', 'not-object'):
            self.assertIn('FAIL  shout  %s' % case, out)
        self.assertIn('期待 錯誤 BadArguments（退 1，最後一行 JSON）；得到 退 1', out)
        self.assertIn('Error', out)                                    # stderr 最後一行（例外）有帶出來
        self.assertTrue(out.rstrip().endswith('5 條，3 條沒過'), out)

    def test_traceback_on_stdout_fails_even_if_exit_0(self):
        prog = '#!/bin/sh\necho "Traceback (most recent call last):"\n'
        out = self.agent('tools', 'test', self.pack(program=prog), '--no-jail', code=1).stdout
        self.assertIn('FAIL  shout  ok', out)

    def test_args_single_run(self):
        r = self.agent('tools', 'test', self.pack(), '--no-jail', '--args', '{"text": "hi"}', code=0)
        self.assertEqual(r.stdout, 'HI\n')
        self.assertIn('退出碼 0', r.stderr)
        self.assertIn('沒關牢', r.stderr)
        r = self.agent('tools', 'test', './shout', '--no-jail', '--args', '[]', code=1)
        self.assertIn('退出碼 1', r.stderr)

    def test_args_needs_tool_when_many(self):
        self.agent('tools', 'new', 'demo', code=0)
        tools = json.loads((self.d / 'demo/demo.json').read_text())
        tools.append(json.loads(json.dumps(tools[0]).replace('"name": "demo"', '"name": "demo2"')))
        (self.d / 'demo/demo.json').write_text(json.dumps(tools))
        r = self.agent('tools', 'test', './demo', '--no-jail', '--args', '{"text": "a"}', code=2)
        self.assertIn('--tool', r.stderr)
        r = self.agent('tools', 'test', './demo', '--no-jail', '--tool', 'demo2', '--args', '{"text": "a"}', code=0)
        self.assertEqual(r.stdout, 'a\n')
        self.assertIn('NotFound', self.agent('tools', 'test', './demo', '--no-jail', '--tool', 'zz', code=1).stderr)

    def test_json_format(self):
        r = self.agent('tools', 'test', self.pack(), '--no-jail', '--json', code=1)
        doc = json.loads(r.stdout)
        self.assertEqual((doc['_type'], doc['_version'], doc['package'], doc['jail']),
                         ('aos_agent_tools_test', 1, 'shout', False))
        self.assertIn('--no-jail', doc['jail_note'])
        self.assertEqual((doc['total'], doc['failed']), (5, 3))
        self.assertEqual(doc['tools'][0]['name'], 'shout')
        self.assertIsInstance(doc['tools'][0]['tokens'], int)
        case = next(c for c in doc['cases'] if c['case'] == 'type:text')
        self.assertEqual(set(case), {'tool', 'case', 'pass', 'ms', 'expect', 'got', 'exit_code'})
        self.assertIs(case['pass'], False)
        r = self.agent('tools', 'test', './shout', '--no-jail', '--json', '--args', '{"text": "a"}', code=0)
        run = json.loads(r.stdout)
        self.assertEqual((run['_type'], run['exit_code'], run['stdout']), ('aos_agent_tools_run', 0, 'A\n'))

    def test_case_file_contains_and_files(self):
        spec = self.pack()
        cases = [{'tool': 'shout', 'args': {'text': 'a'}, 'expect': 'ok', 'contains': 'A'},
                 {'name': 'wrong', 'tool': 'shout', 'args': {'text': 'a'}, 'expect': 'ok', 'contains': 'zzz'},
                 {'name': 'code', 'tool': 'shout', 'args': {'text': 'a'}, 'expect': 'NotFound'}]
        (self.d / 'c.json').write_text(json.dumps(cases))
        out = self.agent('tools', 'test', spec, '--no-jail', '--case', 'c.json', code=1).stdout
        self.assertIn('PASS  shout  case0', out)
        self.assertIn('FAIL  shout  wrong', out)
        self.assertIn("輸出含 'zzz'", out)
        self.assertIn('FAIL  shout  code', out)
        for bad in ({'tool': 'nope', 'args': {}, 'expect': 'ok'}, {'tool': 'shout', 'expect': 'ok'},
                    {'tool': 'shout', 'args': {}, 'expect': 'ok', 'files': {'../x': 'a'}}):
            (self.d / 'c.json').write_text(json.dumps([bad]))
            self.assertIn('CasesInvalid', self.agent('tools', 'test', spec, '--no-jail', '--case', 'c.json',
                                                     code=1).stderr)

    def test_bad_packages(self):
        self.assertIn('aos-agent: NotFound', self.agent('tools', 'test', './none', code=1).stderr)
        self.assertIn('aos-agent: NotFound', self.agent('tools', 'test', 'no_such_builtin', code=1).stderr)
        spec = self.pack(tools=[{'type': 'function', 'function': {'name': 'x'}}])
        self.assertIn('aos-agent: ToolInvalid', self.agent('tools', 'test', spec, '--no-jail', code=1).stderr)

    def test_program_missing_or_not_executable(self):
        spec = self.pack()
        os.chmod(self.d / 'shout' / 'run', 0o644)
        out = self.agent('tools', 'test', spec, '--no-jail', code=1).stdout
        self.assertIn('FAIL  shout  program', out)
        self.assertIn('沒有執行位', out)
        self.assertTrue(out.rstrip().endswith('1 條，1 條沒過'), out)

    def test_common_drift_warning_and_token_note(self):
        long = 'Word ' * 400
        tools = [{'type': 'function', 'function': {'name': 'shout', 'description': long,
                                                   'parameters': {'type': 'object', 'properties': {}}},
                  '_meta': {'argv': ['tools/shout/run']}}]
        prog = '#!/bin/sh\necho ok\n'
        out = self.agent('tools', 'test', self.pack(program=prog, tools=tools, extra={'_common.py': '# old\n'}),
                         '--no-jail').stdout
        self.assertIn('警告：_common.py 跟 proto5/tools/base/_common.py 不一樣', out)
        self.assertIn('資源軸扣分', out)

    def test_builtin_name(self):
        out = self.agent('tools', 'test', 'files', '--no-jail', '--tool', 'json_edit').stdout
        self.assertIn('包 files（%s）' % (PROTO / 'tools' / 'files'), out)
        self.assertIn('json_edit  not-object', out)

    @unittest.skipUnless(JAIL_OK, 'aos-jail（bwrap）開不起來')
    def test_jailed_run(self):
        """有 bwrap：預設關牢，工具在牢裡跑得起來；count_words 讀得到固定案例放進 workspace 的檔。"""
        self.agent('tools', 'new', 'demo', code=0)
        out = self.agent('tools', 'test', './demo', code=0).stdout
        self.assertIn('關在牢裡跑', out.splitlines()[0])
        self.assertNotIn('沒關牢', out)
        self.wrap('--only', 'count_words', '--name', 'words')
        cases = [{'name': 'count', 'tool': 'count_words', 'args': {'path': 'a.txt', 'top': 1}, 'expect': 'ok',
                  'contains': '[["b", 2]]', 'files': {'a.txt': 'a b b\n'}},
                 {'name': 'outside', 'tool': 'count_words', 'args': {'path': '/etc/hostname'},
                  'expect': 'PythonError'}]
        (self.d / 'c.json').write_text(json.dumps(cases))
        out = self.agent('tools', 'test', './words', '--case', 'c.json', code=0).stdout
        self.assertIn('PASS  words  import', out)
        self.assertIn('PASS  count_words  count', out)
        self.assertIn('PASS  count_words  outside', out)          # 牢裡看不到 /etc/hostname
        r = self.agent('tools', 'test', './words', '--args', '{"path": "."}', code=1)
        self.assertIn('/work/ws', r.stdout)


# ------------------------------------------------------------------ 用法錯 ----

class UsageTests(Temp):
    def test_usage_errors_exit_2(self):
        for args in (['tools', 'new'], ['tools', 'new', 'a', 'b'], ['tools', 'new', 'x', '--target', 'h'],
                     ['tools', 'new', 'x', '--json'], ['tools', 'new', 'x', '--only', 'a'],
                     ['tools', 'test', 'x', '--args', 'not json'], ['tools', 'test', 'x', '--args', '{}', '--case', 'c'],
                     ['tools', 'test', 'x', '--force'], ['tools', 'test', 'x', '--out', 'd'],
                     ['tools', 'wrap-py', 'f.py', '--only', ''], ['tools', 'wrap-py', 'f.py', '--name', ''],
                     ['tools', 'wrap-py', 'f.py', '--no-jail'], ['tools', 'add', 'base', '--out', 'd'],
                     ['tools', 'ls', '--no-jail'], ['tools', 'ls', '--tool', 'x']):
            with self.subTest(args=args):
                r = self.agent(*args, code=2)
                self.assertIn('aos-agent: Usage', r.stderr)

    def test_no_home_needed(self):
        """new／test／wrap-py 在沒有 info.json 的資料夾也能跑（別的 tools 動作要家）。"""
        self.agent('tools', 'new', 'demo', code=0)
        self.assertIn('NotAnAgent', self.agent('tools', 'ls', code=1).stderr)


if __name__ == '__main__':
    unittest.main()
