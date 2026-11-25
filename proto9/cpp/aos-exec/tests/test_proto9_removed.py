# Check the two proto9 removals: no AOS_STACK (flags rejected, never set or created, an inherited one passes through) and no inst sheets (EntryBad).
import json
import os

from common import TmpCase

SHOW = '#!/bin/sh\nif [ "${AOS_STACK+set}" = set ]; then echo "stack=[$AOS_STACK]"; else echo "stack unset"; fi\n'
USAGE = '(usage: aos-exec [--ws WS] [--dotenv-override] XXX [ARGS...])'


class NoStack(TmpCase):
    prefix = 'aos-exec-nostack-'

    def setUp(self):
        super().setUp()
        self.put('t', SHOW, True)
        self.put('p/_entry', ['sh', '-c', 'touch ran'])

    def test_removed_flags_are_flag_unknown(self):
        for flags, name in ((['--stack', 'x'], '--stack'), (['--stack=x'], '--stack'), (['--stack-lazy'], '--stack-lazy'),
                            (['--stack-lazy=1'], '--stack-lazy'), (['-s', 'x'], '-s'), (['--ws', '.', '--stack', 'x'], '--stack')):
            with self.subTest(flags=flags):
                code, out, err = self.run_(*flags, 'p')
                self.assertEqual((code, out), (1, ''))
                self.assertEqual(err, 'aos-exec: error: FlagUnknown unknown flag %s (proto9 has no AOS_STACK) %s' % (name, USAGE))
                self.assertFalse((self.d / 'p' / 'ran').exists())
                self.assertFalse((self.d / 'x').exists())

    def test_removed_flags_after_xxx_are_args(self):
        self.assertEqual(self.run_('/bin/echo', '--stack', 'x', '--stack-lazy'), (0, '--stack x --stack-lazy', ''))

    def test_not_set_when_caller_has_none(self):
        self.assertEqual(self.run_('./t'), (0, 'stack unset', ''))
        self.assertEqual(self.run_('./t', extra={'AOS_WS': str(self.d)}), (0, 'stack unset', ''))

    def test_no_stack_folder_appears(self):
        for argv, extra in ((['p'], {}), (['p'], {'AOS_WS': str(self.d)}), (['--ws', str(self.d), 'p'], {}),
                            (['p'], {'AOS_STACK': 'later/st'})):
            with self.subTest(argv=argv, extra=extra):
                code, _, err = self.run_(*argv, extra=extra)
                self.assertEqual(code, 0, err)
                self.assertTrue((self.d / 'p' / 'ran').exists())
                (self.d / 'p' / 'ran').unlink()
                self.assertEqual(sorted(os.listdir(self.d)), ['p', 't'])
                self.assertEqual(sorted(os.listdir(self.d / 'p')), ['_entry'])

    def test_no_stack_folder_on_error_either(self):
        self.put('bad.json', {'argv': ['true']})
        code, _, _ = self.run_('bad.json', extra={'AOS_WS': str(self.d)})
        self.assertEqual(code, 1)
        self.assertFalse((self.d / '.stack').exists())

    def test_inherited_passes_through_unchanged(self):
        for value in ('rel/st', '/abs/not/there', '/abs/no-slash/', '', 'a b/../c'):
            with self.subTest(value=value):
                self.assertEqual(self.run_('./t', extra={'AOS_STACK': value}), (0, 'stack=[%s]' % value, ''))
                self.assertFalse((self.d / 'rel').exists())
        self.assertEqual(sorted(os.listdir(self.d)), ['p', 't'])

    def test_inherited_survives_redirect_and_dotenv_without_override(self):
        self.put('d/.env', 'AOS_STACK=from-dotenv\n')
        self.put('d/_entry', '"../t"')
        self.assertEqual(self.run_('d', extra={'AOS_STACK': 'outer'}), (0, 'stack=[outer]', ''))
        self.assertEqual(self.run_('d'), (0, 'stack=[from-dotenv]', ''))   # just a variable in .env: no default, no special case
        self.assertEqual(self.run_('--dotenv-override', 'd', extra={'AOS_STACK': 'outer'}), (0, 'stack=[from-dotenv]', ''))


class NoInst(TmpCase):
    prefix = 'aos-exec-noinst-'
    WHY = 'is an inst sheet (a JSON object with argv); inst sheets are not supported in proto9'

    def assert_entry_bad(self, argv, where):
        code, out, err = self.run_(*argv)
        self.assertEqual((code, out), (1, ''))
        self.assertEqual(err, 'aos-exec: error: EntryBad bad entry: %s %s' % (where, self.WHY))

    def test_inst_file(self):
        self.put('i.json', {'argv': ['sh', '-c', 'touch ran']})
        self.assert_entry_bad(['i.json'], self.d / 'i.json')
        self.assertFalse((self.d / 'ran').exists())

    def test_inst_at_pointer_and_in_object_folder(self):
        self.put('c.json', {'tools': {'t': {'argv': ['echo', 'x'], 'timeout_ms': 5}}, '_entry': {'argv': ['echo']}})
        self.assert_entry_bad(['c.json#/tools/t'], '%s#/tools/t' % (self.d / 'c.json'))
        self.assert_entry_bad(['c.json'], '%s#/_entry' % (self.d / 'c.json'))

    def test_inst_as_folder_entry_and_after_redirect(self):
        self.put('f/_entry.json', {'argv': ['echo']})
        self.assert_entry_bad(['f'], self.d / 'f' / '_entry.json')
        self.put('r.json', '"f/_entry.json"')
        self.assert_entry_bad(['r.json'], self.d / 'f' / '_entry.json')

    def test_inst_reached_through_inserted_aos_exec(self):
        self.put('i.json', {'argv': ['echo']})
        self.put('a.json', ['./i.json'])   # argv[0] is not runnable: aos-exec is inserted, and that one refuses
        self.assert_entry_bad(['a.json'], self.d / 'i.json')

    def test_shebang_line_is_still_skipped_but_still_refused(self):
        self.put('s.json', '#!/usr/bin/env aos-exec\n' + json.dumps({'argv': ['echo']}))
        self.assert_entry_bad(['s.json'], self.d / 's.json')
