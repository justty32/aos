# Check behavior kept from proto8 that later slimming passes may cut (.env, AOS_ENTRY walking, lookups, loops, AOS_CF/CD/CO), so a cut shows up as a failing test.
import json

from common import TmpCase

ECHO_ENV = '#!/bin/sh\necho "$@" "A=${A-}" "CF=$AOS_CF" "CD=$AOS_CD" "CO=$AOS_CO" "PWD=$(pwd -P)"\n'


class Dotenv(TmpCase):
    prefix = 'aos-exec-dotenv-'

    def setUp(self):
        super().setUp()
        self.put('p/_entry', ['sh', '-c', 'echo "$A|$B"'])

    def test_read_and_expand(self):
        self.put('p/.env', '# c\nexport A=1\nB = "x${A}y" # tail\n')
        self.assertEqual(self.run_('p'), (0, '1|x1y', ''))

    def test_no_override_by_default_and_flag_overrides(self):
        self.put('p/.env', 'A=dot\nB=b\n')
        self.assertEqual(self.run_('p', extra={'A': 'outer'}), (0, 'outer|b', ''))
        self.assertEqual(self.run_('--dotenv-override', 'p', extra={'A': 'outer'}), (0, 'dot|b', ''))

    def test_errors_never_print_values(self):
        for text, why in (('A=${NOPE}\n', 'variable referenced by ${...} is not set'), ('A\n', 'no ='),
                          ("A='se${cret}'\n", 'no ${ inside single quotes'), ('A="secret\n', 'unterminated quote'),
                          ('﻿A=secret\n', 'file starts with a BOM')):
            with self.subTest(text=text):
                self.put('p/.env', text)
                code, out, err = self.run_('p')
                self.assertEqual((code, out), (1, ''))
                self.assertIn('DotenvBad bad .env: %s line 1 (' % (self.d / 'p' / '.env'), err)
                self.assertIn(why, err)
                self.assertNotIn('secret', err)

    def test_unicode_whitespace_in_values(self):
        self.put('p/.env', 'A=　v  # c\nB=x　#y\n')
        self.assertEqual(self.run_('p'), (0, 'v|x', ''))

    def test_json_dotenv_key_and_object_as_folder(self):
        self.put('o.json', {'.env': {'A': 'ja', 'B': {'$env': 'HOME'}, 'N': 3}, '_entry': {'_entry': ['sh', '-c', 'echo "$A $N"']}})
        self.assertEqual(self.run_('o.json'), (0, 'ja', ''))

    def test_entry_dotenv_is_the_entry(self):
        self.put('q/.env', '["echo", "env-is-entry"]')
        self.assertEqual(self.run_('q', extra={'AOS_ENTRY': '.env'}), (0, 'env-is-entry', ''))


class Walk(TmpCase):
    prefix = 'aos-exec-walk-'

    def test_entry_name_and_segments(self):
        self.put('p/.env', 'AOS_ENTRY=sub/run\n')
        self.put('p/sub/.env', 'A=sub\n')
        self.put('p/sub/run', ECHO_ENV, True)
        code, out, err = self.run_('p', 'x')
        self.assertEqual(code, 0, err)
        sub = self.d / 'p' / 'sub'
        self.assertEqual(out, 'x A=sub CF=%s/run CD=%s CO= PWD=%s' % (sub, sub, sub))

    def test_folder_wins_and_json_fallback(self):
        self.put('a/_entry/_entry', ['echo', 'folder'])
        self.put('a/_entry.json', ['echo', 'json'])
        self.assertEqual(self.run_('a'), (0, 'folder', ''))
        self.put('b/_entry.json', ['echo', 'json'])
        self.assertEqual(self.run_('b'), (0, 'json', ''))
        self.put('c.json', ['echo', 'c'])
        self.assertEqual(self.run_('c'), (0, 'c', ''))
        code, _, err = self.run_('d')
        self.assertEqual(code, 1)
        self.assertIn('EntryMissing', err)

    def test_pointer_and_co(self):
        self.put('t', ECHO_ENV, True)
        self.put('j.json', {'a/b': {'_entry': [str(self.d / 't')]}})
        code, out, _ = self.run_('j.json#/a~1b')
        self.assertEqual(code, 0)
        self.assertIn('CO=/a~1b/_entry', out)
        self.assertIn('CF=%s/j.json' % self.d, out)
        for bad in ('j.json#a', 'p#/x'):
            self.put('p/_entry', ['true'])
            code, _, err = self.run_(bad)
            self.assertEqual(code, 1)
            self.assertIn('EntryBad', err)

    def test_loops(self):
        self.put('r1.json', '"r2.json"')
        self.put('r2.json', '"r1.json"')
        code, _, err = self.run_('r1.json')
        self.assertEqual(code, 1)
        self.assertIn('EntryBad bad entry: redirect loop: %s# → %s# → %s#' % (self.d / 'r1.json', self.d / 'r2.json', self.d / 'r1.json'), err)
        self.put('l/.env', 'AOS_ENTRY=.\n')
        code, _, err = self.run_('l')
        self.assertEqual(code, 1)
        self.assertIn('EntryBad bad entry: directory loop', err)

    def test_redirect_is_a_new_hop(self):
        self.put('w/keep', '')
        self.put('t', '#!/bin/sh\necho "$AOS_WS" "$@"\n', True)
        self.put('r.json', '"t"')
        self.assertEqual(self.run_('--ws', 'w', 'r.json', 'a'), (0, '%s a' % (self.d / 'w'), ''))


class Launch(TmpCase):
    prefix = 'aos-exec-launch-'

    def test_argv0_folder_gets_aos_exec_inserted(self):
        self.put('tools/stamp/_entry', ['echo', 'stamp'])
        self.put('a.json', ['tools/stamp', 'arg'])
        self.assertEqual(self.run_('a.json'), (0, 'stamp arg', ''))

    def test_path_lookup_and_launch_failed(self):
        self.put('a.json', ['no-such-command-xyz'])
        code, _, err = self.run_('a.json')
        self.assertEqual((code, err), (1, 'aos-exec: error: LaunchFailed cannot start: no-such-command-xyz (No such file or directory)'))

    def test_exit_code_is_the_entry_code(self):
        self.put('a.json', ['sh', '-c', 'exit 7'])
        self.assertEqual(self.run_('a.json'), (7, '', ''))

    def test_symlinked_entry_cds_to_real_folder(self):
        self.put('real/t', ECHO_ENV, True)
        (self.d / 'p').mkdir()
        (self.d / 'p' / '_entry').symlink_to(self.d / 'real' / 't')
        self.put('p/.env', 'A=p\n')
        self.put('real/.env', 'A=real\n')
        code, out, _ = self.run_('p')
        self.assertEqual(code, 0)
        self.assertIn('A=p CF=%s/real/t CD=%s/real' % (self.d, self.d), out)
        self.assertIn('PWD=%s/real' % self.d, out)

    def test_args_reach_argv_array(self):
        self.put('a.json', json.dumps(['echo', 'x']))
        self.assertEqual(self.run_('a.json', 'y', '--ws'), (0, 'x y --ws', ''))
