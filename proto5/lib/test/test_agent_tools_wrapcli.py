"""aos-agent tools wrap-cli 與 wrap-py --describe-with-llm／--describe（spec/aos-agent/tools-llm.md，第三波 W3-2）。

不打真模型：函式層注入假的 ask；CLI 層開一個本機假端點（AOS_LLM_CONFIG 指過去）。
產的包大多用 tools test --no-jail 跑（快、不靠 bwrap）；關牢那條在 aos-jail 開不起來時 skip。
fixture：test/fixtures/wrapcli/（argparse 腳本、GNU help、三份怪 help、echoargs.py、answers.json、opaque_funcs.py）。
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
PROTO = LIB.parent
CLI = PROTO / 'cli' / 'aos-agent'
FIX = HERE / 'fixtures' / 'wrapcli'
WRAP_FIXTURE = HERE / 'fixtures' / 'wrap_fixture.py'
sys.path.insert(0, str(LIB))

import aos_agent_tools_dev as dev  # noqa: E402
import aos_agent_tools_wrapcli as w  # noqa: E402
from aos_agent_home import AgentError  # noqa: E402

JAIL_OK = dev.jail_ready()[0]
ANSWERS = json.loads((FIX / 'answers.json').read_text(encoding='utf-8'))


def env(**extra):
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', **extra)
    for key in ('AOS_TOOL_ROOT', 'AOS_TOOL_FENCE', 'AOS_KERNEL_HOME'):
        e.pop(key, None)
    return e


def agent(*args, cwd, code=None, **extra):
    r = subprocess.run([sys.executable, str(CLI), *map(str, args)], cwd=cwd, env=env(**extra),
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
    if code is not None:
        assert r.returncode == code, 'exit %s (want %s)\nstdout:\n%s\nstderr:\n%s' % (r.returncode, code, r.stdout,
                                                                                      r.stderr)
    return r


def help_text(name):
    return w.clean_help((FIX / name).read_text(encoding='utf-8'))


def mech(name):
    if name.endswith('.py'):
        src = (FIX / name).read_text(encoding='utf-8')
        parsed = w.read_argparse(src, name)
        return parsed, w.check_params(parsed['params'], src)
    text = help_text(name)
    parsed = w.parse_help(text)
    return parsed, w.check_params(parsed['params'], text)


def by_name(params):
    return {p['name']: p for p in params}


class Temp(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix='aos-wrapcli-')))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)

    def agent(self, *args, code=None, **extra):
        return agent(*args, cwd=self.d, code=code, **extra)

    def run_tool(self, pack, args, code=None, **extra):
        return self.agent('tools', 'test', './' + pack, '--no-jail', '--args', json.dumps(args), code=code, **extra)

    def quiet(self, fn, *a, **kw):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            cwd = os.getcwd()
            os.chdir(self.d)
            try:
                result = fn(*a, **kw)
            finally:
                os.chdir(cwd)
        return result, out.getvalue()


# ------------------------------------------------------------------ help 文字：規則 ----

class CleanHelpTests(unittest.TestCase):
    def test_strips_hyperlinks_and_bold(self):
        raw = '  \x1b]8;;https://x/y\x1b\\\x1b[1m-c, --bytes\x1b[0m\x1b]8;;\x1b\\\n\tprint\r\n'
        self.assertEqual(w.clean_help(raw), '  -c, --bytes\n        print\n')

    def test_backspace_overstrike(self):
        self.assertEqual(w.clean_help('N\x08NA\x08AME\n'), 'NAME\n')


class UsageTests(unittest.TestCase):
    def parse(self, text):
        return w.parse_help(text)

    def test_bsd_cluster_and_options(self):
        r = self.parse('usage: t [-ab] [-f file] [-n NUM] src [dst]\n')
        p = by_name(r['params'])
        self.assertEqual(p['a']['kind'], 'flag')
        self.assertEqual(p['b']['kind'], 'flag')
        self.assertEqual((p['f']['kind'], p['f']['type']), ('option', 'string'))
        self.assertEqual(p['n']['type'], 'integer')
        self.assertTrue(p['src']['required'])
        self.assertFalse(p['dst']['required'])

    def test_placeholder_and_array(self):
        r = self.parse('Usage: wc [OPTION]... [FILE]...\n')
        self.assertEqual([(p['name'], p['array'], p['required']) for p in r['params']], [('file', True, False)])

    def test_required_array_and_choice(self):
        r = self.parse('usage: prog {start,stop} name ...\n')
        pos = [p for p in r['params'] if p['kind'] == 'positional']
        self.assertEqual(pos[0]['choices'], ['start', 'stop'])
        self.assertEqual((pos[1]['name'], pos[1]['array'], pos[1]['required']), ('name', True, True))

    def test_usage_on_next_line_and_angle(self):
        r = self.parse('Usage:\n  conv [options] <input> [<output>]\n')
        self.assertEqual([p['name'] for p in r['params']], ['input', 'output'])

    def test_required_option_outside_brackets(self):
        r = self.parse('usage: t -o FILE [-v]\n\n  -o FILE   output\n  -v        verbose\n')
        p = by_name(r['params'])
        self.assertTrue(p['o']['required'])
        self.assertFalse(p['v']['required'])

    def test_alternate_forms_noted(self):
        r = self.parse('Usage: wc [OPTION]... [FILE]...\n  or:  wc [OPTION]... --files0-from=F\n')
        self.assertEqual(r['notes'], [(2, '另一種用法，只照第一種解')])

    def test_positional_name_clash_gets_suffix(self):
        r = self.parse('usage: t [--file F] file\n\n  --file F   config\n')
        self.assertEqual(sorted(p['name'] for p in r['params']), ['file', 'file_arg'])


class OptionLineTests(unittest.TestCase):
    def parse(self, body):
        return w.parse_help('usage: t [options]\n\nOptions:\n' + body)

    def test_forms(self):
        r = self.parse('  -x, --long=ARG     a\n  --opt ARG          b\n  -y VAL             c\n'
                       '  --color[=WHEN]     d\n  -o <file>          e\n  --level <n>        f\n')
        p = by_name(r['params'])
        self.assertEqual(p['long']['flags'], ['-x', '--long'])
        self.assertEqual(p['long']['joiner'], '=')
        self.assertEqual(p['opt']['joiner'], ' ')
        self.assertEqual(p['y']['kind'], 'option')
        self.assertEqual(p['color']['joiner'], '=')
        self.assertEqual(p['o']['type'], 'string')
        self.assertEqual(p['level']['type'], 'integer')
        self.assertEqual(r['unparsed'], [])

    def test_description_on_next_lines(self):
        r = self.parse('  -c, --bytes\n         print the byte counts\n         and more\n      --debug\n         dbg\n')
        p = by_name(r['params'])
        self.assertEqual(p['bytes']['help'], 'print the byte counts and more')
        self.assertEqual(p['debug']['help'], 'dbg')

    def test_colon_description(self):
        p = by_name(self.parse('  --ignore-case: compare case-insensitively\n')['params'])
        self.assertEqual(p['ignore_case']['help'], 'compare case-insensitively')

    def test_choices(self):
        r = self.parse('  --mode {fast,slow}   m\n  --keep=first|last    k\n'
                       '  --total=WHEN   when to print; WHEN can be: auto, always, never\n')
        p = by_name(r['params'])
        self.assertEqual(p['mode']['choices'], ['fast', 'slow'])
        self.assertEqual(p['keep']['choices'], ['first', 'last'])
        self.assertEqual(p['total']['choices'], ['auto', 'always', 'never'])

    def test_count_when_description_shows_repeat(self):
        p = by_name(self.parse('  -v    verbose; repeat for more (-vv)\n')['params'])
        self.assertEqual((p['v']['kind'], p['v']['type']), ('count', 'integer'))

    def test_repeatable_option_is_array(self):
        p = by_name(self.parse('  --tag T    add a tag (repeatable)\n')['params'])
        self.assertEqual((p['tag']['array'], p['tag']['multi']), (True, 'repeat'))

    def test_literal_value_aliases_dropped(self):
        r = self.parse('  -c, --check, --check=diagnose-first\n        check\n  -C, --check=quiet, --check=silent\n'
                       '        quietly\n')
        p = by_name(r['params'])
        self.assertEqual(p['check']['flags'], ['-c', '--check'])
        self.assertEqual((p['C']['flags'], p['C']['kind']), (['-C'], 'flag'))
        self.assertIn('固定值寫法', [row for row in r['rows'] if row[1] == 'C'][0][2])

    def test_single_space_is_ambiguous(self):
        r = self.parse('  -v verbose output\n')
        self.assertEqual(r['params'], [])
        self.assertIn('分不出', r['unparsed'][0][2])

    def test_help_and_version_skipped(self):
        r = self.parse('  -h, --help     show help\n  --version      v\n  -V, --version-sort  natural\n')
        self.assertEqual([p['name'] for p in r['params']], ['version_sort'])
        self.assertEqual([row[0] for row in r['rows'] if row[0] != 'ok'], ['skip', 'skip'])

    def test_duplicate_flag_rejected(self):
        r = self.parse('  -a, --all   a\n  --all       again\n')
        self.assertEqual([row[0] for row in r['rows']], ['ok', 'reject'])

    def test_mention_of_unknown_flag_listed(self):
        r = w.parse_help('usage: t [options]\n\n  -a   all\n\nPass -z for NUL; like -a but -aa is fine.\n')
        self.assertEqual(len(r['unparsed']), 1)
        self.assertIn('-z', r['unparsed'][0][2])

    def test_lines_in_options_section_that_are_not_options(self):
        r = self.parse('  -a   all\n\n  something odd here\n')
        self.assertIn('不是選項行', r['unparsed'][0][2])

    def test_argparse_style_positional_section(self):
        r = w.parse_help('usage: p [-h] [--n N] src\n\npositional arguments:\n  src         the source\n\n'
                         'options:\n  -h, --help  show this help message and exit\n  --n N       count\n')
        p = by_name(r['params'])
        self.assertEqual(p['src']['help'], 'the source')
        self.assertEqual(p['n']['type'], 'integer')
        self.assertEqual(r['unparsed'], [])

    def test_description(self):
        self.assertEqual(w.parse_help('dedupe v2.1 -- remove dups\n\nusage: d\n')['description'], 'remove dups')
        self.assertEqual(w.parse_help('Usage: x [FILE]\nDo things. More.\n')['description'], 'Do things.')


class FixtureScoreTests(unittest.TestCase):
    """機械版對固定 fixture 的分數（決定性）：改規則時這裡會提醒分數變了。"""

    EXPECT = {'csvsum.py': ('csvsum', 11, 11, 11, 11), 'gnu_wc.txt': ('gnu_wc', 9, 9, 9, 9),
              'gnu_sort.txt': ('gnu_sort', 30, 28, 30, 29), 'weird_angle.txt': ('weird_angle', 8, 8, 8, 7),
              'weird_bsd.txt': ('weird_bsd', 9, 8, 8, 9), 'weird_free.txt': ('weird_free', 5, 5, 5, 5)}

    def test_scores(self):
        for fname, (key, found, type_ok, req_ok, choices_ok) in self.EXPECT.items():
            with self.subTest(fname):
                _, (params, dropped) = mech(fname)
                self.assertEqual(dropped, [])
                s = w.score(params, ANSWERS[key]['params'])
                self.assertEqual((s['found'], s['extra'], s['type_ok'], s['required_ok'], s['choices_ok']),
                                 (found, 0, type_ok, req_ok, choices_ok))

    def test_free_form_lists_what_it_could_not_read(self):
        parsed, _ = mech('weird_free.txt')
        self.assertEqual([u[0] for u in parsed['unparsed']], [13])


# ------------------------------------------------------------------ argparse ----

class ArgparseTests(unittest.TestCase):
    def test_csvsum(self):
        parsed, (params, _) = mech('csvsum.py')
        p = by_name(params)
        self.assertEqual(parsed['description'], 'Summarize the numeric columns of a CSV file.')
        self.assertEqual([x['name'] for x in params][:2], ['path', 'columns'])
        self.assertEqual((p['columns']['array'], p['columns']['required']), (True, False))
        self.assertEqual(p['limit']['type'], 'integer')
        self.assertEqual(p['ratio']['type'], 'number')
        self.assertEqual(p['mode']['choices'], ['sum', 'mean', 'max'])
        self.assertEqual(p['verbose']['kind'], 'count')
        self.assertEqual(p['no_header']['flags'], ['--no-header'])       # store_false 用旗標取名，不用 dest
        self.assertEqual((p['tag']['array'], p['tag']['multi']), (True, 'repeat'))
        self.assertTrue(p['out']['required'])
        self.assertEqual(p['delimiter']['default'], ',')
        self.assertEqual([r[0] for r in parsed['rows'] if r[1] == '--version'], ['skip'])

    def test_bad(self):
        parsed, (params, _) = mech('argparse_bad.py')
        rows = {r[1]: r for r in parsed['rows']}
        self.assertEqual(sorted(p['name'] for p in params), ['fast', 'home', 'name', 'slow'])
        self.assertIn('* 或 **', rows['*FLAGS'][2])
        self.assertIn('choices=LEVELS 不是字面值', rows['--kind'][2])
        self.assertIn('type=pathlib.Path 不支援', rows['--where'][2])
        self.assertIn('type=bool 是陷阱', rows['--yes'][2])
        self.assertIn('BooleanOptionalAction', rows['--color'][2])
        self.assertEqual(rows['--secret'][0], 'skip')
        self.assertIn('default 不是字面值', rows['home'][2])
        self.assertIn('互斥群組', rows['fast'][2])
        self.assertIn('subparsers', rows['subparsers'][2])
        self.assertIn('屬於子命令 run', rows['--times'][2])
        self.assertNotIn('default', by_name(params)['home'])

    def test_two_parsers_all_rejected(self):
        parsed, (params, _) = mech('two_parsers.py')
        self.assertEqual(params, [])
        self.assertTrue(all('2 個 ArgumentParser' in r[2] for r in parsed['rows']))

    def test_unknown_receiver_and_nargs(self):
        src = ('import argparse\np = argparse.ArgumentParser()\n'
               'def add(x):\n    x.add_argument("--a")\n'
               'p.add_argument("pair", nargs=2, type=int)\n'
               'p.add_argument("--rest", nargs=argparse.REMAINDER)\n'
               'p.add_argument_group("g").add_argument("--grouped", choices=range(1, 4), type=int)\n')
        parsed = w.read_argparse(src, 'x.py')
        rows = {r[1]: r for r in parsed['rows']}
        self.assertIn('看不出是哪個 parser', rows['--a'][2])
        self.assertIn('不是字面值', rows['--rest'][2])
        p = by_name(parsed['params'])
        self.assertEqual((p['pair']['array'], p['pair']['type'], p['pair']['required']), (True, 'integer', True))
        self.assertEqual(p['grouped']['choices'], [1, 2, 3])

    def test_segment_is_the_argparse_part(self):
        seg = w.argparse_segment((FIX / 'csvsum.py').read_text(encoding='utf-8'))
        self.assertTrue(seg.lstrip().startswith("p = argparse.ArgumentParser("))
        self.assertIn("'--version'", seg)
        self.assertNotIn('print(', seg)


# ------------------------------------------------------------------ 機械檢查 ----

class CheckParamsTests(unittest.TestCase):
    TEXT = 'usage: t [-v] [--out=FILE] [--n N] src\n  -h, --help  help\n'

    def check(self, *params):
        return w.check_params(list(params), self.TEXT)

    def test_ok_and_normalized(self):
        ok, dropped = self.check({'name': 'out', 'flags': ['--out'], 'kind': 'option', 'type': 'string'},
                                 {'name': 'v', 'flags': ['-v'], 'kind': 'flag'},
                                 {'name': 'src', 'flags': [], 'kind': 'positional', 'type': 'string',
                                  'required': True, 'help': ' a\n b '})
        self.assertEqual(dropped, [])
        p = by_name(ok)
        self.assertEqual(p['out']['joiner'], '=')                  # 原文寫 --out=FILE
        self.assertEqual(p['v']['type'], 'boolean')
        self.assertEqual(p['src']['help'], 'a b')
        self.assertEqual(p['out']['line'], 1)

    def test_drops(self):
        cases = [({'name': 'x', 'flags': ['--nope'], 'kind': 'flag'}, '原文裡找不到'),
                 ({'name': '1x', 'flags': ['-v'], 'kind': 'flag'}, '不合法'),
                 ({'name': 'x', 'flags': ['-v'], 'kind': 'switch'}, 'kind'),
                 ({'name': 'x', 'flags': ['--n'], 'kind': 'option', 'type': 'boolean'}, '開關請用 kind flag'),
                 ({'name': 'x', 'flags': ['--n'], 'kind': 'option', 'type': 'object'}, '型別'),
                 ({'name': 'x', 'flags': ['--n'], 'kind': 'option', 'type': 'integer', 'choices': ['a']}, 'choices'),
                 ({'name': 'x', 'flags': ['--help'], 'kind': 'flag'}, 'help'),
                 ({'name': 'x', 'flags': ['-h'], 'kind': 'flag', 'help': 'show help'}, 'help'),
                 ({'name': 'x', 'flags': ['-v'], 'kind': 'positional'}, '位置參數不能有旗標'),
                 ({'name': 'x', 'flags': [], 'kind': 'option', 'type': 'string'}, '至少要一個旗標'),
                 ({'name': 'x', 'flags': ['--out=FILE'], 'kind': 'option', 'type': 'string'}, '寫法不對'),
                 ({'name': 'x', 'flags': ['-v'], 'kind': 'flag', 'array': True}, '不能是陣列'),
                 ({'name': 'x', 'flags': ['-v'], 'kind': 'flag', 'required': 'yes'}, 'true／false'),
                 ('not a dict', '不是物件')]
        for param, why in cases:
            with self.subTest(param):
                ok, dropped = self.check(param)
                self.assertEqual(ok, [])
                self.assertIn(why, dropped[0][1])

    def test_duplicates(self):
        ok, dropped = self.check({'name': 'v', 'flags': ['-v'], 'kind': 'flag'},
                                 {'name': 'v', 'flags': ['--n'], 'kind': 'option', 'type': 'integer'},
                                 {'name': 'w', 'flags': ['-v'], 'kind': 'flag'})
        self.assertEqual(len(ok), 1)
        self.assertEqual([d[1] for d in dropped], ['名字 v 重複', '旗標 -v 已經有別格用了'])

    def test_not_a_list(self):
        self.assertEqual(w.check_params({'a': 1}, ''), ([], [('params', 'params 要是陣列')]))


# ------------------------------------------------------------------ 產包與產的 run ----

class PackTests(Temp):
    def test_argparse_pack_runs_and_builds_argv(self):
        self.agent('tools', 'wrap-cli', FIX / 'csvsum.py', code=0)
        pack = self.d / 'csvsum'
        self.assertEqual(sorted(p.name for p in pack.iterdir()),
                         ['README.md', '_common.py', 'config.json', 'csvsum.json', 'run', 'src', 'wrapcli.json'])
        spec = json.loads((pack / 'wrapcli.json').read_text())
        self.assertEqual(spec['exec'], ['python3', '@src/csvsum.py'])
        self.assertEqual(spec['made_by'], 'mechanical')
        tool = json.loads((pack / 'csvsum.json').read_text())[0]
        self.assertNotIn('_jail', tool)
        self.assertEqual(tool['function']['parameters']['required'], ['path', 'out'])
        self.assertEqual(tool['function']['parameters']['properties']['columns']['type'], 'array')
        r = self.run_tool('csvsum', {'path': 'a.csv', 'columns': ['x', '-y'], 'verbose': 2, 'tag': ['t1', 't2'],
                                     'out': 'o', 'no_header': True, 'mode': 'max', 'ratio': 1}, code=0)
        got = json.loads(r.stdout.splitlines()[0])
        self.assertEqual(got, {'columns': ['x', '-y'], 'delimiter': ',', 'header': False, 'limit': 10, 'mode': 'max',
                               'out': 'o', 'path': 'a.csv', 'ratio': 1.0, 'strict': False, 'tag': ['t1', 't2'],
                               'verbose': 2})
        r = self.agent('tools', 'test', './csvsum', '--no-jail', code=0)
        self.assertIn('0 條沒過', r.stdout)

    def test_bad_arguments(self):
        self.agent('tools', 'wrap-cli', FIX / 'csvsum.py', code=0)
        for args, why in (({'path': 'a'}, 'missing required argument "out"'),
                          ({'path': 'a', 'out': 'o', 'mode': 'median'}, 'must be one of'),
                          ({'path': 'a', 'out': 'o', 'zzz': 1}, 'unknown argument'),
                          ({'path': 'a', 'out': 'o', 'limit': True}, 'must be an integer'),
                          ({'path': 'a', 'out': 'o', 'verbose': 99}, '0..50'),
                          ({'path': 'a', 'out': 'o', 'columns': 'x'}, 'must be an array'),
                          ({'path': 'a\0b', 'out': 'o'}, 'NUL')):
            with self.subTest(args):
                r = self.run_tool('csvsum', args, code=1)
                last = json.loads(r.stdout.strip().splitlines()[-1])
                self.assertEqual(last['error'], 'BadArguments')
                self.assertIn(why, last['message'])

    def help_pack(self, fixture, name, **extra):
        self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--help-file', FIX / fixture, '--name', name, code=0)
        return self.d / name

    def argv(self, pack, args, **extra):
        return json.loads(self.run_tool(pack, args, code=0, **extra).stdout.splitlines()[0])

    def test_help_pack_argv(self):
        self.help_pack('weird_angle.txt', 'img')
        self.assertEqual(self.argv('img', {'input': 'in.png', 'o': 'x.jpg', 'quality': 80, 'v': 2, 'strip': True,
                                           'output': '-'}),
                         ['-o', 'x.jpg', '--quality', '80', '--strip', '-v', '-v', '--', 'in.png', '-'])
        self.help_pack('weird_free.txt', 'dd')
        self.assertEqual(self.argv('dd', {'keep': 'last', 'min_count': 3, 'sep': ','}),
                         ['--keep=last', '--min-count', '3', '--sep=,'])
        self.assertEqual(self.argv('dd', {'dry_run': False}), [])
        self.help_pack('weird_bsd.txt', 'tarx')
        self.assertEqual(self.argv('tarx', {'file': ['a', 'b'], 'C': 'dir', 'b': '20'}),
                         ['-C', 'dir', '-b', '20', 'a', 'b'])
        spec = json.loads((self.d / 'tarx' / 'wrapcli.json').read_text())
        self.assertEqual(spec['help_file'], str(FIX / 'weird_bsd.txt'))
        self.assertEqual(spec['exec'], ['python3', '@src/echoargs.py'])

    def test_multi_once_option(self):
        src = self.d / 'm.py'
        src.write_text('import argparse, json\np = argparse.ArgumentParser()\n'
                       'p.add_argument("--xs", nargs="+", type=int)\nprint(json.dumps(vars(p.parse_args())))\n')
        self.agent('tools', 'wrap-cli', src, code=0)
        self.assertEqual(self.argv('m', {'xs': [1, 2]}), {'xs': [1, 2]})

    def test_command_failed_and_empty_stdout(self):
        self.help_pack('weird_free.txt', 'dd')
        r = self.run_tool('dd', {'sep': ';'}, code=1, ECHOARGS_EXIT='3')
        lines = r.stdout.strip().splitlines()
        self.assertEqual(json.loads(lines[0]), ['--sep=;'])       # stdout 原樣在前
        last = json.loads(lines[-1])
        self.assertEqual((last['error'], last['exit_code']), ('CommandFailed', 3))
        self.assertIn('failing on purpose', last['stderr'])

    def test_timeout_kills(self):
        script = self.d / 'slow.py'
        script.write_text('import argparse, time\np = argparse.ArgumentParser()\np.add_argument("secs", type=float)\n'
                          'time.sleep(p.parse_args().secs)\n')
        self.agent('tools', 'wrap-cli', script, code=0)
        spec_file = self.d / 'slow' / 'wrapcli.json'
        spec = json.loads(spec_file.read_text())
        spec['timeout'] = 1
        spec_file.write_text(json.dumps(spec))
        r = self.run_tool('slow', {'secs': 30}, code=1)
        last = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual((last['error'], last['timeout']), ('Timeout', 1))

    def test_path_command_and_jail(self):
        self.agent('tools', 'wrap-cli', 'wc', code=0)
        spec = json.loads((self.d / 'wc' / 'wrapcli.json').read_text())
        self.assertEqual((spec['exec'], spec['mode']), (['wc'], 'help'))
        self.assertFalse((self.d / 'wc' / 'src').exists())
        if not JAIL_OK:
            self.skipTest('aos-jail 開不起來')
        r = self.agent('tools', 'test', './wc', code=0)
        self.assertIn('0 條沒過', r.stdout)

    def test_fixture_packs_pass_tools_test(self):
        for fixture in ('gnu_sort.txt', 'weird_angle.txt', 'weird_bsd.txt', 'weird_free.txt'):
            with self.subTest(fixture):
                name = fixture.split('.')[0]
                self.help_pack(fixture, name)
                r = self.agent('tools', 'test', './' + name, '--no-jail', code=0)
                self.assertIn('0 條沒過', r.stdout)

    def test_table_printed(self):
        r = self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--help-file', FIX / 'weird_free.txt', code=0)
        self.assertIn('收    keep', r.stdout)
        self.assertIn('解不出來：第 13 行', r.stdout)
        r = self.agent('tools', 'wrap-cli', FIX / 'argparse_bad.py', code=0)
        self.assertIn('拒收  --yes', r.stdout)
        self.assertIn('不收  --secret', r.stdout)

    def test_errors(self):
        r = self.agent('tools', 'wrap-cli', 'no-such-command-xyz', code=1)
        self.assertIn('NotFound', r.stderr)
        r = self.agent('tools', 'wrap-cli', FIX / 'two_parsers.py', code=1)
        self.assertIn('NothingToWrap', r.stderr)
        for bad in ('wrapcli', 'config', '-x', 'a b', '.x'):
            with self.subTest(bad):
                r = self.agent('tools', 'wrap-cli', 'wc', '--name=' + bad)
                self.assertIn('BadName', r.stderr)
        self.agent('tools', 'wrap-cli', 'wc', code=0)
        r = self.agent('tools', 'wrap-cli', 'wc', code=1)
        self.assertIn('AlreadyExists', r.stderr)
        self.agent('tools', 'wrap-cli', 'wc', '--force', code=0)
        r = self.agent('tools', 'wrap-cli', 'wc', '--help-file', self.d / 'nope.txt', code=1)
        self.assertIn('NotFound', r.stderr)
        self.assertEqual([p.name for p in self.d.iterdir() if p.name.startswith('.')], [])

    def test_help_command_that_prints_nothing(self):
        script = self.d / 'mute'
        script.write_text('#!/bin/sh\nexit 0\n')
        script.chmod(0o755)
        r = self.agent('tools', 'wrap-cli', script, code=1)
        self.assertIn('HelpFailed', r.stderr)


# ------------------------------------------------------------------ --spec ----

class SpecTests(Temp):
    def make(self):
        self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--help-file', FIX / 'weird_free.txt', '--name', 'dd',
                   code=0)
        return self.d / 'dd' / 'wrapcli.json'

    def test_edit_spec_and_rebuild(self):
        spec_file = self.make()
        spec = json.loads(spec_file.read_text())
        spec['params'].append({'name': 'zero', 'flags': ['-z', '--zero'], 'kind': 'flag', 'help': 'NUL lines'})
        edited = self.d / 'edited.json'
        edited.write_text(json.dumps(spec))
        r = self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--spec', edited, '--name', 'dd', '--force', code=0)
        self.assertIn('zero', r.stdout)
        out = json.loads(self.agent('tools', 'test', './dd', '--no-jail', '--args', '{"zero": true}', code=0)
                         .stdout.splitlines()[0])
        self.assertEqual(out, ['--zero'])
        self.assertEqual(json.loads((self.d / 'dd' / 'wrapcli.json').read_text())['made_by'], 'spec')

    def test_help_changed(self):
        help_copy = self.d / 'h.txt'
        shutil.copy(FIX / 'weird_free.txt', help_copy)
        self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--help-file', help_copy, '--name', 'dd', code=0)
        with open(help_copy, 'a') as f:
            f.write('  --new   new flag\n')
        r = self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--spec', self.d / 'dd' / 'wrapcli.json',
                       '--name', 'dd', '--force', code=1)
        self.assertIn('HelpChanged', r.stderr)

    def test_mismatch_and_invalid(self):
        spec_file = self.make()
        r = self.agent('tools', 'wrap-cli', FIX / 'csvsum.py', '--spec', spec_file, '--name', 'x', code=1)
        self.assertIn('SpecMismatch', r.stderr)
        spec = json.loads(spec_file.read_text())
        spec['params'][0]['flags'] = ['--invented']
        bad = self.d / 'bad.json'
        bad.write_text(json.dumps(spec))
        r = self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--spec', bad, '--name', 'x', code=1)
        self.assertIn('SpecInvalid', r.stderr)
        self.assertIn('--invented', r.stderr)
        bad.write_text('{"_type": "other"}')
        r = self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--spec', bad, '--name', 'x', code=1)
        self.assertIn('SpecInvalid', r.stderr)
        self.assertFalse((self.d / 'x').exists())


# ------------------------------------------------------------------ 模型版（假 ask） ----

def fake_ask(reply, calls=None):
    def ask(system, user, alias=None):
        if calls is not None:
            calls.append({'system': system, 'user': user, 'alias': alias})
        return reply, {'text': json.dumps(reply), 'usage': {'prompt_tokens': 10, 'completion_tokens': 5,
                                                             'total_tokens': 15}, 'ms': 7, 'alias': 'default',
                       'model': 'fake'}
    return ask


FREE_REPLY = {'description': 'Remove duplicate lines.', 'params': [
    {'name': 'file', 'flags': [], 'kind': 'positional', 'type': 'string', 'array': False, 'required': False},
    {'name': 'keep', 'flags': ['--keep'], 'kind': 'option', 'type': 'string', 'choices': ['first', 'last']},
    {'name': 'zero', 'flags': ['-z', '--zero'], 'kind': 'flag', 'type': 'boolean'},
    {'name': 'made_up', 'flags': ['--made-up'], 'kind': 'flag', 'type': 'boolean'},
    {'name': 'help', 'flags': ['-h', '--help'], 'kind': 'flag', 'type': 'boolean'}]}


class LlmWrapCliTests(Temp):
    def propose(self, reply=FREE_REPLY, calls=None, **kw):
        return self.quiet(w.wrap_cli, str(FIX / 'echoargs.py'), name='dd', help_file=str(FIX / 'weird_free.txt'),
                          describe_with_llm=True, ask=fake_ask(reply, calls), **kw)

    def test_proposal_not_pack(self):
        calls = []
        code, out = self.propose(calls=calls, model='fast')
        self.assertEqual(code, 0)
        self.assertFalse((self.d / 'dd').exists())
        prop = json.loads((self.d / 'dd.wrapcli.json').read_text())
        self.assertEqual(prop['made_by'], 'llm')
        self.assertEqual([p['name'] for p in prop['params']], ['file', 'keep', 'zero'])
        self.assertEqual([d['item'] for d in prop['dropped']], ['第 4 格（made_up）', '第 5 格（help）'])
        self.assertEqual(prop['help_sha256'], w._sha(help_text('weird_free.txt')))
        self.assertEqual(prop['usage']['total_tokens'], 15)
        self.assertIn('丟掉  第 4 格（made_up）（旗標 --made-up 在原文裡找不到）', out)
        self.assertIn('aos-agent tools wrap-cli %s --spec ./dd.wrapcli.json --name dd' % (FIX / 'echoargs.py'), out)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['alias'], 'fast')
        self.assertIn('--keep=first|last', calls[0]['user'])
        # 人看過 → --spec 產包（不叫模型）
        self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--spec', 'dd.wrapcli.json', '--name', 'dd', code=0)
        out = json.loads(self.agent('tools', 'test', './dd', '--no-jail', '--args', '{"zero": true, "file": "f"}',
                                    code=0).stdout.splitlines()[0])
        self.assertEqual(out, ['--zero', 'f'])
        tool = json.loads((self.d / 'dd' / 'dd.json').read_text())[0]
        self.assertTrue(tool['function']['description'].startswith('Remove duplicate lines.'))

    def test_existing_proposal_checked_before_asking(self):
        (self.d / 'dd.wrapcli.json').write_text('{}')
        calls = []
        with self.assertRaises(AgentError) as cm:
            self.propose(calls=calls)
        self.assertEqual(cm.exception.code, 'AlreadyExists')
        self.assertEqual(calls, [])
        self.propose(calls=calls, force=True)
        self.assertEqual(len(calls), 1)

    def test_bad_model_output(self):
        with self.assertRaises(AgentError) as cm:
            self.propose(reply={'description': 'x'})
        self.assertEqual(cm.exception.code, 'BadModelOutput')
        self.assertFalse((self.d / 'dd.wrapcli.json').exists())

    def test_argparse_mode_sends_segment(self):
        calls = []
        reply = {'params': [{'name': 'limit', 'flags': ['--limit'], 'kind': 'option', 'type': 'integer'}]}
        self.quiet(w.wrap_cli, str(FIX / 'csvsum.py'), describe_with_llm=True, ask=fake_ask(reply, calls))
        self.assertIn('argparse source code', calls[0]['user'])
        self.assertNotIn('print(json.dumps', calls[0]['user'])
        prop = json.loads((self.d / 'csvsum.wrapcli.json').read_text())
        self.assertEqual((prop['mode'], prop['help_file']), ('argparse', None))


# ------------------------------------------------------------------ wrap-py 描述 ----

OPAQUE = FIX / 'opaque_funcs.py'
OPAQUE_REPLY = {'proc': {'description': 'Count the lines in a text file.', 'params': {'path': 'file to read'}},
                'proc2': {'description': 'Count the words in a text file.', 'params': {'path': 'file', 'nope': 'x'}},
                'xf': {'description': '', 'params': {}},
                'calc2': {'description': 'x' * 201},
                'ghost': {'description': 'not a function'}}


class DescribeTests(Temp):
    def analyze(self, path=OPAQUE, only=None):
        return dev.analyze(Path(path).read_text(encoding='utf-8'), str(path), only)

    def test_check_describe(self):
        ok, dropped = dev.check_describe(OPAQUE_REPLY, self.analyze())
        self.assertEqual(sorted(ok), ['proc', 'proc2'])
        self.assertEqual(ok['proc']['params'], {'path': 'file to read'})
        reasons = dict(dropped)
        self.assertIn('沒有這個參數', reasons['proc2.nope'])
        self.assertIn('空的', reasons['xf'])
        self.assertIn('超過 200', reasons['calc2'])
        self.assertIn('不認得的函式', reasons['ghost'])

    def test_does_not_overwrite_docstrings(self):
        result = self.analyze(WRAP_FIXTURE, ['join_words', 'echo'])
        ok, dropped = dev.check_describe({'join_words': {'description': 'new', 'params': {'sep': 'new'}},
                                          'echo': {'params': {'text': 'the text'}}}, result)
        self.assertEqual(ok, {'echo': {'params': {'text': 'the text'}}})
        self.assertEqual(dict(dropped), {'join_words': '已有 docstring，不覆蓋', 'join_words.sep': '已有說明，不覆蓋'})

    def test_nothing_to_describe(self):
        with self.assertRaises(AgentError) as cm:
            self.quiet(dev.describe_with_llm, str(WRAP_FIXTURE), only=['join_words'], ask=fake_ask({}))
        self.assertEqual(cm.exception.code, 'NothingToDescribe')

    def test_propose_then_apply(self):
        calls = []
        code, out = self.quiet(dev.describe_with_llm, str(OPAQUE), name='opq', model='m',
                               ask=fake_ask(OPAQUE_REPLY, calls))
        self.assertEqual(code, 0)
        self.assertFalse((self.d / 'opq').exists())
        prop = json.loads((self.d / 'opq.describe.json').read_text())
        self.assertEqual(sorted(prop['functions']), ['proc', 'proc2'])
        self.assertEqual(len(prop['dropped']), 4)
        self.assertIn('return len(Path(path).read_text', calls[0]['user'])
        self.assertIn('- calc3: a "description" and "params" for a, b', calls[0]['user'])
        self.assertIn('proc   proc（沒 docstring）', out)
        self.assertIn('Count the lines in a text file.', out)
        self.assertIn('--describe ./opq.describe.json --name opq', out)
        # 人改一條再套用
        prop['functions']['xf'] = {'description': 'Reverse a string.'}
        (self.d / 'opq.describe.json').write_text(json.dumps(prop))
        r = self.agent('tools', 'wrap-py', OPAQUE, '--name', 'opq', '--describe', 'opq.describe.json', code=0)
        self.assertIn('補了 3 支', r.stdout)
        self.assertNotIn('proc 沒有 docstring', r.stdout)
        self.assertIn('警告：calc2 沒有 docstring', r.stdout)
        tools = {t['function']['name']: t['function'] for t in json.loads((self.d / 'opq' / 'opq.json').read_text())}
        self.assertEqual(tools['proc']['description'], 'Count the lines in a text file.')
        self.assertEqual(tools['proc']['parameters']['properties']['path']['description'], 'file to read')
        self.assertEqual(tools['xf']['description'], 'Reverse a string.')
        self.assertEqual(tools['calc2']['description'], 'calc2')
        info = json.loads((self.d / 'opq' / 'wrap.json').read_text())
        self.assertEqual(info['describe']['functions'], ['proc', 'proc2', 'xf'])
        r = self.agent('tools', 'test', './opq', '--no-jail', code=0)
        self.assertIn('0 條沒過', r.stdout)

    def test_apply_rejects(self):
        src = self.d / 'o.py'
        shutil.copy(OPAQUE, src)
        self.quiet(dev.describe_with_llm, str(src), ask=fake_ask(OPAQUE_REPLY))
        prop_file = self.d / 'o.describe.json'
        prop = json.loads(prop_file.read_text())
        prop['functions']['proc']['params']['bogus'] = 'x'
        bad = self.d / 'bad.json'
        bad.write_text(json.dumps(prop))
        r = self.agent('tools', 'wrap-py', src, '--describe', bad, code=1)
        self.assertIn('DescribeInvalid', r.stderr)
        bad.write_text('[]')
        r = self.agent('tools', 'wrap-py', src, '--describe', bad, code=1)
        self.assertIn('DescribeInvalid', r.stderr)
        with open(src, 'a') as f:
            f.write('\n')
        r = self.agent('tools', 'wrap-py', src, '--describe', prop_file, code=1)
        self.assertIn('SourceChanged', r.stderr)
        self.assertFalse((self.d / 'o').exists())

    def test_only_narrower_than_proposal(self):
        self.quiet(dev.describe_with_llm, str(OPAQUE), name='opq', ask=fake_ask(OPAQUE_REPLY))
        r = self.agent('tools', 'wrap-py', OPAQUE, '--name', 'opq', '--only', 'proc', '--describe',
                       'opq.describe.json', code=0)
        self.assertIn('提案裡的 proc2 這次沒包', r.stdout)


# ------------------------------------------------------------------ astra 審查（M1、M7、M8、M9、S1、S5） ----

ITEMS_SRC = ('import argparse, json\np = argparse.ArgumentParser()\n'
             'p.add_argument("--items", nargs="*")\np.add_argument("--delete", action="store_true")\n'
             'p.add_argument("--name")\np.add_argument("--pair", nargs=2)\np.add_argument("-s")\n'
             'print(json.dumps(vars(p.parse_args()), sort_keys=True))\n')


class ReviewTests(Temp):
    def last_error(self, r):
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_m1_dash_values_cannot_become_flags(self):
        (self.d / 'it.py').write_text(ITEMS_SRC)
        self.agent('tools', 'wrap-cli', self.d / 'it.py', code=0)
        r = self.run_tool('it', {'items': ['--delete']}, code=1)       # 審查反例：以前變成 delete=True
        self.assertEqual(self.last_error(r)['error'], 'BadArguments')
        self.assertIn('starts with "-"', self.last_error(r)['message'])
        r = self.run_tool('it', {'pair': ['a', '-b']}, code=1)
        self.assertEqual(self.last_error(r)['error'], 'BadArguments')
        r = self.run_tool('it', {'s': '-x'}, code=1)                   # 只有短旗標：沒有安全寫法
        self.assertEqual(self.last_error(r)['error'], 'BadArguments')
        got = json.loads(self.run_tool('it', {'name': '--delete'}, code=0).stdout.splitlines()[0])
        self.assertEqual((got['name'], got['delete']), ('--delete', False))   # argparse 長旗標用 --name=值

    def test_m1_help_mode(self):
        self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--help-file', FIX / 'weird_free.txt', '--name', 'dd',
                   code=0)
        got = json.loads(self.run_tool('dd', {'sep': '-x'}, code=0).stdout.splitlines()[0])
        self.assertEqual(got, ['--sep=-x'])                             # help 寫了 --sep=：安全
        self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--help-file', FIX / 'weird_angle.txt', '--name', 'img',
                   code=0)
        r = self.run_tool('img', {'input': 'a', 'o': '-q'}, code=1)
        self.assertEqual(self.last_error(r)['error'], 'BadArguments')
        r = self.run_tool('img', {'input': 'a', 'resize': '-1x2'}, code=1)
        self.assertEqual(self.last_error(r)['error'], 'BadArguments')

    def test_m7_nargs_length_and_schema(self):
        (self.d / 'it.py').write_text(ITEMS_SRC)
        self.agent('tools', 'wrap-cli', self.d / 'it.py', code=0)
        r = self.run_tool('it', {'pair': ['a']}, code=1)
        self.assertIn('exactly 2 items', self.last_error(r)['message'])
        got = json.loads(self.run_tool('it', {'pair': ['a', 'b']}, code=0).stdout.splitlines()[0])
        self.assertEqual(got['pair'], ['a', 'b'])
        prop = json.loads((self.d / 'it' / 'it.json').read_text())[0]['function']['parameters']['properties']['pair']
        self.assertEqual((prop['minItems'], prop['maxItems']), (2, 2))

    def test_m7_rejected_shapes(self):
        src = ('import argparse\np = argparse.ArgumentParser()\n'
               'p.add_argument("--kv", action="append", nargs=2)\n'
               'p.add_argument("a", nargs="?")\np.add_argument("b", nargs="?")\n'
               'p.add_argument("--plus", nargs="+")\n')
        parsed = w.read_argparse(src, 'x.py')
        rows = {r[1]: r for r in parsed['rows']}
        self.assertIn('append 搭配 nargs 不支援', rows['--kv'][2])
        params, dropped = w.check_params(parsed['params'], src)
        self.assertEqual([p['name'] for p in params], ['a', 'plus'])
        self.assertIn('前面已有可變長度的位置參數 a', dropped[0][1])
        (self.d / 'x.py').write_text(src + 'print(1)\n')
        self.agent('tools', 'wrap-cli', self.d / 'x.py', code=0)
        r = self.run_tool('x', {'plus': []}, code=1)
        self.assertIn('at least 1 item', self.last_error(r)['message'])
        # 人改的參數表也擋：兩個選填位置參數、亂寫 nargs
        spec = {'name': 'p', 'flags': [], 'kind': 'positional', 'type': 'string', 'array': True, 'nargs': 'x'}
        self.assertIn('nargs', w.check_params([spec], '')[1][0][1])

    def test_m8_help_env_is_minimal(self):
        script = self.d / 'envhelp'
        script.write_text('#!/usr/bin/env python3\nimport os, sys\n'
                          'print("usage: envhelp [-a]\\n  -a   all\\n" + " ".join(sorted(os.environ)))\n'
                          'print("LC_ALL=" + os.environ.get("LC_ALL", ""), "SECRET=" + os.environ.get("MY_SECRET_KEY", ""))\n')
        script.chmod(0o755)
        os.environ['MY_SECRET_KEY'] = 'hunter2'
        self.addCleanup(os.environ.pop, 'MY_SECRET_KEY', None)
        text = w.run_help(w.resolve_cmd(str(script)))
        self.assertIn('LC_ALL=C', text)
        self.assertNotIn('hunter2', text)
        self.assertNotIn('MY_SECRET_KEY', text)

    def test_m8_help_is_bounded(self):
        # 主行程印完就走，另開 session 的孫子握著 stdout 睡 60 秒：最多再收 2 秒就回
        script = self.d / 'holder'
        script.write_text('#!/usr/bin/env python3\nimport os, sys, time\nprint("usage: holder [-a]", flush=True)\n'
                          'if os.fork() == 0:\n    os.setsid()\n    time.sleep(60)\n')
        script.chmod(0o755)
        t0 = time.monotonic()
        self.assertIn('usage: holder', w.run_help(w.resolve_cmd(str(script))))
        self.assertLess(time.monotonic() - t0, 8)
        # 自己睡著不走、輸出很大：到上限就砍、HelpFailed
        slow = self.d / 'slow'
        slow.write_text('#!/usr/bin/env python3\nimport sys, time\nsys.stdout.write("x" * 3000000)\n'
                        'sys.stdout.flush()\ntime.sleep(60)\n')
        slow.chmod(0o755)
        old = w.HELP_TIMEOUT
        w.HELP_TIMEOUT = 1
        self.addCleanup(setattr, w, 'HELP_TIMEOUT', old)
        t0 = time.monotonic()
        with self.assertRaises(AgentError) as cm:
            w.run_help(w.resolve_cmd(str(slow)))
        self.assertEqual(cm.exception.code, 'HelpFailed')
        self.assertLess(time.monotonic() - t0, 10)

    def test_m9_spec_top_level_fields(self):
        self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--help-file', FIX / 'weird_free.txt', '--name', 'dd',
                   code=0)
        good = json.loads((self.d / 'dd' / 'wrapcli.json').read_text())
        for key, value, why in (('command', None, 'command'), ('description', 5, 'description'),
                                ('description', 'a\x1bb', 'description'), ('timeout', None, 'timeout'),
                                ('timeout', '9', 'timeout'), ('timeout', 0, 'timeout'), ('timeout', 10 ** 6, 'timeout'),
                                ('timeout', True, 'timeout'), ('params', {}, 'params'), ('mode', 'x', 'mode'),
                                ('help_sha256', 1, 'help_sha256'), ('help_file', 3, 'help_file')):
            with self.subTest(key=key, value=value):
                bad = dict(good, **{key: value})
                (self.d / 'bad.json').write_text(json.dumps(bad))
                r = self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--spec', self.d / 'bad.json', '--name', 'x',
                               code=1)
                self.assertIn('SpecInvalid', r.stderr)
                self.assertIn(why, r.stderr)
                self.assertNotIn('Traceback', r.stderr + r.stdout)

    def test_s1_control_characters(self):
        text = 'usage: t [--a]\n  --a   x\n'
        for bad in ('ok\x1b[31m', 'nul\x00', 'c1\x9b'):
            with self.subTest(bad=bad):
                _, dropped = w.check_params([{'name': 'a', 'flags': ['--a'], 'kind': 'flag', 'help': bad}], text)
                self.assertIn('控制字元', dropped[0][1])
        _, dropped = w.check_params([{'name': 'a', 'flags': ['--a'], 'kind': 'option', 'type': 'string',
                                      'choices': ['x\x1b']}], text)
        self.assertIn('控制字元', dropped[0][1])
        result = dev.analyze(OPAQUE.read_text(encoding='utf-8'), str(OPAQUE))
        ok, dropped = dev.check_describe({'proc': {'description': 'Count\x1b]0;pwn\x07 lines',
                                                   'params': {'path': 'file\x00'}}}, result)
        self.assertEqual(ok, {})
        self.assertEqual([d[1] for d in dropped], ['描述含控制字元（ESC、NUL…）', '說明含控制字元（ESC、NUL…）'])
        desc, _, dropped, _ = w.llm_table('t', 'help', text, ask=fake_ask({'description': 'bad\x1b', 'params': []}))
        self.assertIsNone(desc)
        self.assertEqual(dropped[0][0], 'description')

    def test_s5_apply_line_quoted(self):
        spaced = self.d / 'my dir'
        spaced.mkdir()
        shutil.copy(FIX / 'echoargs.py', spaced / 'echo args.py')
        _, out = self.quiet(w.wrap_cli, str(spaced / 'echo args.py'), name='ea', out=str(spaced),
                            help_file=str(FIX / 'weird_free.txt'), describe_with_llm=True, ask=fake_ask(FREE_REPLY))
        line = out.strip().splitlines()[-1]
        self.assertIn("wrap-cli '%s' --spec" % (spaced / 'echo args.py'), line)
        self.assertIn('--name ea', line)
        self.assertIn("--out '%s'" % spaced, line)
        r = self.agent('tools', '-h', code=0)
        self.assertIn('只有這一步要 AOS_LLM_CONFIG', r.stdout)


# ------------------------------------------------------------------ CLI：用法與假端點 ----

class FakeEndpoint:
    """本機假 OpenAI 相容端點：每次回同一段 content。"""

    def __init__(self, content):
        body = json.dumps({'choices': [{'message': {'role': 'assistant', 'content': content}}],
                           'usage': {'prompt_tokens': 3, 'completion_tokens': 4, 'total_tokens': 7}}).encode()
        self.hits = 0
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                outer.hits += 1
                self.rfile.read(int(self.headers.get('Content-Length') or 0))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def config(self, folder):
        path = Path(folder) / 'llm.json'
        path.write_text(json.dumps({'_metainfo': {'_type': 'llm_config', '_version': 1}, 'models': {
            'default': {'endpoint': 'http://127.0.0.1:%d/v1' % self.server.server_port, 'model': 'fake'}}}))
        return str(path)

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class CliTests(Temp):
    def test_usage_errors(self):
        cases = [('wrap-cli', 'wc', '--model', 'x'),
                 ('wrap-cli', 'wc', '--describe-with-llm', '--spec', 'f'),
                 ('wrap-py', 'f.py', '--describe-with-llm', '--describe', 'f'),
                 ('wrap-cli', 'wc', '--describe', 'f'),
                 ('wrap-py', 'f.py', '--spec', 'f'),
                 ('wrap-py', 'f.py', '--help-file', 'f'),
                 ('wrap-cli', 'wc', '--only', 'a'),
                 ('wrap-cli', 'wc', '--target', '.'),
                 ('wrap-cli', 'wc', '--spec', ''),
                 ('test', 'x', '--describe-with-llm'),
                 ('wrap-cli',)]
        for c in cases:
            with self.subTest(c):
                self.agent('tools', *c, code=2)

    def test_help_mentions_wrap_cli(self):
        r = self.agent('tools', '-h', code=0)
        self.assertIn('aos-agent tools wrap-cli CMD', r.stdout)
        self.assertIn('--describe-with-llm', r.stdout)
        self.assertIn('wrap-cli', self.agent('-h', code=0).stdout)

    def test_end_to_end_with_fake_endpoint(self):
        ep = FakeEndpoint('```json\n' + json.dumps(FREE_REPLY) + '\n```')
        self.addCleanup(ep.close)
        cfg = ep.config(self.d)
        r = self.agent('tools', 'wrap-cli', FIX / 'echoargs.py', '--help-file', FIX / 'weird_free.txt', '--name', 'dd',
                       '--describe-with-llm', code=0, AOS_LLM_CONFIG=cfg)
        self.assertIn('prompt 3、completion 4 token', r.stderr)
        self.assertTrue((self.d / 'dd.wrapcli.json').exists())
        ep2 = FakeEndpoint(json.dumps(OPAQUE_REPLY))
        self.addCleanup(ep2.close)
        r = self.agent('tools', 'wrap-py', OPAQUE, '--describe-with-llm', code=0, AOS_LLM_CONFIG=ep2.config(self.d))
        self.assertTrue((self.d / 'opaque_funcs.describe.json').exists())
        self.assertEqual((ep.hits, ep2.hits), (1, 1))

    def test_no_llm_config(self):
        e = {k: v for k, v in os.environ.items() if k != 'AOS_LLM_CONFIG'}
        r = subprocess.run([sys.executable, str(CLI), 'tools', 'wrap-py', str(OPAQUE), '--describe-with-llm'],
                           cwd=self.d, env=dict(e, PYTHONDONTWRITEBYTECODE='1'), stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn('ConfigInvalid', r.stderr)
        self.assertFalse((self.d / 'opaque_funcs.describe.json').exists())


if __name__ == '__main__':
    unittest.main()
