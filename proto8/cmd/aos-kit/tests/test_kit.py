"""Test aos-kit ls / make / check / add against fixture kit folders (a copy of templates/kits with make blocks) and a scratch copy of the agent-fsm template."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
KIT_CMD = PROTO / 'cmd' / 'aos-kit'
BIN = KIT_CMD / 'bin' / 'aos-kit'
SHIPPED = PROTO / 'templates' / 'kits'
AGENT_FSM = PROTO / 'templates' / 'agent-fsm'
FIX = Path(__file__).resolve().parent / 'fixtures'
KITS = FIX / 'kits'
STALE = FIX / 'kits-stale'
CJK = re.compile('[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef\u3000-\u303f]')


class Kit(unittest.TestCase):
    def setUp(self):
        # temporary folders are kept (nothing is deleted); point TMPDIR where they should go
        self.tmp = Path(tempfile.mkdtemp(prefix='aos-kit-'))
        self.home = self.tmp / 'aoshome'
        shutil.copytree(AGENT_FSM, self.home / 'templates' / 'agent-fsm')
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        self.env.update(PYTHONDONTWRITEBYTECODE='1', AOS_HOME=str(self.home))

    def run_k(self, *args, env=None):
        return subprocess.run([sys.executable, str(BIN)] + [str(a) for a in args], stdin=subprocess.DEVNULL,
                              capture_output=True, env=env or self.env, cwd=str(self.tmp), timeout=60)

    def ok(self, *args, **kw):
        r = self.run_k(*args, **kw)
        self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
        return r

    def fails(self, code, *args, **kw):
        r = self.run_k(*args, **kw)
        self.assertEqual(r.returncode, 1, (args, r.stdout, r.stderr))
        err = r.stderr.decode()
        self.assertTrue(err.startswith('aos-kit: error: %s ' % code), (args, err))
        self.assertEqual(err.count('\n'), 1, err)
        return r

    def kits_copy(self, src=KITS):
        dst = self.tmp / ('kits-%d' % len(list(self.tmp.glob('kits-*'))))
        shutil.copytree(src, dst)
        return dst

    def edit_kits(self, d, fn):
        p = d / 'kits.json'
        data = json.loads(p.read_text())
        fn(data)
        p.write_text(json.dumps(data))

    def new_def(self):
        d = self.tmp / ('def-%d' % len(list(self.tmp.glob('def-*'))))
        shutil.copytree(AGENT_FSM, d)
        return d

    # --- the fixture stays a faithful copy of the shipped kits -----------------------------------

    def test_fixture_matches_shipped(self):
        for p in sorted(SHIPPED.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.name != 'kits.json':
                rel = p.relative_to(SHIPPED)
                self.assertEqual((KITS / rel).read_bytes(), p.read_bytes(), str(rel))
        fix = json.loads((KITS / 'kits.json').read_text())
        for kit in fix['kits'].values():
            self.assertIn('make', kit)
            kit.pop('make')
        self.assertEqual(fix, json.loads((SHIPPED / 'kits.json').read_text()))

    # --- make ------------------------------------------------------------------------------------

    def test_make_reproduces_shipped_bytes(self):
        for kit in ('gather', 'review'):
            r = self.ok('make', kit, '--kits', KITS)
            self.assertEqual(r.stdout, (SHIPPED / kit / 'system.txt').read_bytes(), kit)
            self.assertEqual(r.stderr, b'', kit)

    def test_make_output_file(self):
        out = self.tmp / 'gather.txt'
        r = self.ok('--kits', KITS, 'make', 'gather', '-o', out)
        self.assertEqual(out.read_bytes(), (SHIPPED / 'gather' / 'system.txt').read_bytes())
        self.assertIn(b'wrote ', r.stdout)
        self.ok('make', 'review', '--kits', KITS, '--output', out)
        self.assertEqual(out.read_bytes(), (SHIPPED / 'review' / 'system.txt').read_bytes())

    def test_make_set_and_site(self):
        site = self.tmp / 'site.txt'
        site.write_text('SITE: write reports in English.\n\n\n')
        r = self.ok('make', 'gather', '--kits', KITS, '--site', site, '--set', 'KNOWLEDGE=/k',
                    '--set', 'BOARD_LINE=', '--set', 'OWN_BOARD_LINE=OWN: none.')
        text = r.stdout.decode()
        self.assertIn('2. Read /k/aos/_description.json; look up more only when needed (index_view /k/aos).\n', text)
        self.assertNotIn('BOARD:', text)
        self.assertIn('\nOWN: none.\nSTOP:', text)
        role = (KITS / 'roles' / 'gather.txt').read_text()
        self.assertTrue(text.endswith('goal done.\n\nSITE: write reports in English.\n\n' + role), text[-600:])
        self.assertNotIn('<', text.replace('<=', ''))

    def test_make_set_inline_beats_default_line(self):
        r = self.ok('make', 'gather', '--kits', KITS, '--set', 'BOARD=board_read {"who": "user"}')
        self.assertIn('check it at start and when an answer is late: board_read {"who": "user"}. A notice', r.stdout.decode())

    def test_make_drop_line_with_empty_inline(self):
        r = self.ok('make', 'gather', '--kits', KITS, '--set', 'OWN_BOARD=')
        text = r.stdout.decode()
        self.assertNotIn('OWN BOARD', text)
        self.assertIn('not permission.\nSTOP:', text)

    def test_make_warnings(self):
        d = self.kits_copy()

        def fn(data):
            mk = data['kits']['gather']['make']
            del mk['defaults']['BOARD_LINE']
            mk['limit'] = 100
        self.edit_kits(d, fn)
        r = self.ok('make', 'gather', '--kits', d, '--set', 'NOPE=1')
        err = r.stderr.decode()
        self.assertIn('aos-kit: warning: placeholder <BOARD> is left', err)
        self.assertIn('over the limit 100', err)
        self.assertIn('--set NOPE is not used', err)
        self.assertIn(b'<BOARD>', r.stdout)

    def test_make_errors(self):
        self.fails('ArgumentsBad', 'make', '--kits', KITS)
        self.fails('ArgumentsBad', 'make', 'gather', '--kits', KITS, '--set', 'lower=x')
        self.fails('ArgumentsBad', 'make', 'gather', '--kits', KITS, '--set', 'NOEQUALS')
        self.fails('KitUnknown', 'make', 'nope', '--kits', KITS)
        self.fails('MakeMissing', 'make', 'gather', '--kits', SHIPPED)
        self.fails('FileMissing', 'make', 'gather', '--kits', KITS, '--site', self.tmp / 'no-site.txt')
        self.fails('KitsMissing', 'make', 'gather', '--kits', self.tmp)
        env = dict(self.env)
        env.pop('AOS_HOME')
        self.fails('KitsMissing', 'make', 'gather', env=env)
        d = self.kits_copy()
        self.edit_kits(d, lambda data: data['kits']['gather']['make'].update(layers=['general.A.txt', '@other']))
        self.fails('RecipeBad', 'make', 'gather', '--kits', d)
        (d / 'kits.json').write_text('{not json')
        self.fails('JsonBad', 'make', 'gather', '--kits', d)

    def test_default_kits_dir_is_aos_home(self):
        shutil.copytree(KITS, self.home / 'templates' / 'kits')
        r = self.ok('make', 'gather')
        self.assertEqual(r.stdout, (SHIPPED / 'gather' / 'system.txt').read_bytes())

    # --- ls --------------------------------------------------------------------------------------

    def test_ls(self):
        r = self.ok('ls', '--kits', KITS)
        self.assertEqual(r.stdout.decode().splitlines(), [
            'gather\tgatherer\tA\tgather/system.txt\tgather/tools.json\tmake',
            'review\treviewer\tA\treview/system.txt\tgather/tools.json\tmake'])
        r = self.ok('--kits', SHIPPED, 'ls', '-j')
        data = json.loads(r.stdout)
        self.assertEqual([k['name'] for k in data['kits']], ['gather', 'review'])
        self.assertFalse(any(k['make'] for k in data['kits']))
        self.fails('ArgumentsBad', 'ls', 'extra', '--kits', KITS)

    # --- check -----------------------------------------------------------------------------------

    def test_check_clean(self):
        for kit in ('gather', 'review'):
            r = self.ok('check', kit, '--kits', KITS)
            self.assertTrue(r.stdout.startswith(b'ok %s (' % kit.encode()), r.stdout)
            self.assertIn(b'limit 3000', r.stdout)
        r = self.ok('check', 'gather', '--kits', KITS, '-j')
        self.assertEqual(json.loads(r.stdout), {'kit': 'gather', 'ok': True, 'problems': [], 'chars': 2156, 'limit': 3000})

    def test_check_stale_fixture(self):
        r = self.fails('CheckFailed', 'check', 'gather', '--kits', STALE)
        out = r.stdout.decode()
        self.assertIn('gather: stale: gather/system.txt differs from the assembled layers (first difference at line 19)', out)
        self.assertIn('gather: unresolved: <OWN_BOARD> is left in gather/system.txt', out)
        r = self.run_k('check', 'gather', '--kits', STALE, '--json')
        self.assertEqual(r.returncode, 1)
        self.assertFalse(json.loads(r.stdout)['ok'])

    def test_check_shipped_has_no_make_yet(self):
        r = self.fails('CheckFailed', 'check', 'gather', '--kits', SHIPPED)
        self.assertIn(b'no "make" block', r.stdout)

    def test_check_problems(self):
        d = self.kits_copy()

        def fn(data):
            mk = data['kits']['gather']['make']
            mk['limit'] = 1000
            del mk['defaults']['KNOWLEDGE_LINE']
        self.edit_kits(d, fn)
        r = self.fails('CheckFailed', 'check', 'gather', '--kits', d)
        out = r.stdout.decode()
        self.assertIn('unresolved: <KNOWLEDGE> is left in the assembled text', out)
        self.assertIn('too long: the assembled text is', out)
        self.assertIn('too long: gather/system.txt is 2156 chars, the limit is 1000', out)
        self.assertIn('stale:', out)

        d = self.kits_copy()
        os.rename(d / 'roles' / 'review.txt', d / 'roles' / 'review.moved')
        (d / 'gather' / 'tools.json').write_text('{bad')
        r = self.fails('CheckFailed', 'check', 'review', '--kits', d)
        out = r.stdout.decode()
        self.assertIn('review: missing: roles/review.txt (a layer)', out)
        self.assertIn('tools file gather/tools.json is not valid JSON', out)

        d = self.kits_copy()
        os.rename(d / 'review' / 'system.txt', d / 'review' / 'system.moved')
        r = self.fails('CheckFailed', 'check', 'review', '--kits', d)
        self.assertIn(b'missing: review/system.txt', r.stdout)
        self.fails('KitUnknown', 'check', 'nope', '--kits', KITS)

    # --- add -------------------------------------------------------------------------------------

    def test_add_over_stock(self):
        d = self.new_def()
        hooks, llm = (d / 'hooks.json').read_bytes(), (d / 'llm.json').read_bytes()
        r = self.ok('add', 'gather', d, '--kits', KITS)
        out = r.stdout.decode()
        self.assertEqual((d / 'system.txt').read_bytes(), (SHIPPED / 'gather' / 'system.txt').read_bytes())
        self.assertEqual((d / 'tools.json').read_bytes(), (SHIPPED / 'gather' / 'tools.json').read_bytes())
        self.assertEqual((d / 'system.txt.before-kit').read_bytes(), (AGENT_FSM / 'system.txt').read_bytes())
        self.assertEqual((d / 'tools.json.before-kit').read_bytes(), (AGENT_FSM / 'tools.json').read_bytes())
        self.assertIn('saved %s' % (d / 'system.txt.before-kit'), out)
        self.assertIn('wrote %s' % (d / 'tools.json'), out)
        self.assertIn('not touched: hooks.json, llm.json', out)
        self.assertEqual((d / 'hooks.json').read_bytes(), hooks)
        self.assertEqual((d / 'llm.json').read_bytes(), llm)
        self.assertEqual(sorted(p.name for p in d.iterdir() if '.tmp.' in p.name), [])

        # same kit again: nothing to do, no new backup
        r = self.ok('add', 'gather', d, '--kits', KITS)
        self.assertIn('unchanged %s' % (d / 'system.txt'), r.stdout.decode())
        self.assertFalse((d / 'system.txt.before-kit.2').exists())

        # another kit: system.txt is no longer stock -> refused, nothing written
        self.fails('FileChanged', 'add', 'review', d, '--kits', KITS)
        self.assertEqual((d / 'system.txt').read_bytes(), (SHIPPED / 'gather' / 'system.txt').read_bytes())
        r = self.ok('add', 'review', d, '--kits', KITS, '--force')
        self.assertEqual((d / 'system.txt').read_bytes(), (SHIPPED / 'review' / 'system.txt').read_bytes())
        self.assertEqual((d / 'system.txt.before-kit.2').read_bytes(), (SHIPPED / 'gather' / 'system.txt').read_bytes())
        self.assertEqual((d / 'system.txt.before-kit').read_bytes(), (AGENT_FSM / 'system.txt').read_bytes())
        self.assertIn('unchanged %s' % (d / 'tools.json'), r.stdout.decode())

    def test_add_refuses_edited_file(self):
        d = self.new_def()
        (d / 'system.txt').write_text('my own system text\n')
        r = self.fails('FileChanged', 'add', 'gather', d, '--kits', KITS)
        self.assertIn(b'is not the stock agent-fsm system.txt', r.stderr)
        self.assertEqual((d / 'tools.json').read_bytes(), (AGENT_FSM / 'tools.json').read_bytes())
        self.assertFalse((d / 'tools.json.before-kit').exists())
        self.assertFalse((d / 'system.txt.before-kit').exists())
        self.ok('add', 'gather', d, '--kits', KITS, '--force')
        self.assertEqual((d / 'system.txt.before-kit').read_text(), 'my own system text\n')

    def test_add_new_files_and_site(self):
        d = self.tmp / 'bare'
        d.mkdir()
        shutil.copyfile(AGENT_FSM / 'interfaces.json', d / 'interfaces.json')
        site = self.tmp / 'site.txt'
        site.write_text('SITE: local rules.\n')
        r = self.ok('add', 'gather', d, '--kits', KITS, '--site', site, '--set', 'KNOWLEDGE=/k')
        self.assertNotIn(b'saved', r.stdout)
        text = (d / 'system.txt').read_text()
        self.assertIn('SITE: local rules.', text)
        self.assertIn('/k/aos/_description.json', text)
        self.assertFalse((d / 'system.txt.before-kit').exists())

    def test_add_errors(self):
        self.fails('DefMissing', 'add', 'gather', self.tmp / 'nowhere', '--kits', KITS)
        empty = self.tmp / 'empty'
        empty.mkdir()
        self.fails('DefMissing', 'add', 'gather', empty, '--kits', KITS)
        self.assertEqual(list(empty.iterdir()), [])
        self.fails('ArgumentsBad', 'add', 'gather', '--kits', KITS)
        self.fails('MakeMissing', 'add', 'gather', self.new_def(), '--kits', SHIPPED)
        d = self.new_def()
        env = dict(self.env)
        env.pop('AOS_HOME')
        self.fails('StockMissing', 'add', 'gather', d, '--kits', KITS, env=env)
        self.assertEqual((d / 'system.txt').read_bytes(), (AGENT_FSM / 'system.txt').read_bytes())
        self.ok('add', 'gather', d, '--kits', KITS, '--force', env=env)
        self.assertTrue((d / 'system.txt.before-kit').exists())

    # --- the command line ------------------------------------------------------------------------

    def test_cli(self):
        r = self.ok('--help')
        self.assertIn(b'usage: aos-kit', r.stdout)
        for sub in ('ls', 'make', 'check', 'add'):
            r = self.ok(sub, '--help')
            self.assertIn(b'usage: aos-kit ' + sub.encode(), r.stdout)
        self.fails('ArgumentsBad')
        self.fails('CommandUnknown', 'nope')
        self.fails('FlagUnknown', 'ls', '--nope')

    def test_product_files_english(self):
        files = [p for p in KIT_CMD.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
        self.assertTrue(len(files) > 10)
        for p in files:
            text = p.read_text(encoding='utf-8')
            m = CJK.search(text)
            self.assertIsNone(m, '%s: CJK char %r' % (p, m.group() if m else ''))


if __name__ == '__main__':
    unittest.main()
