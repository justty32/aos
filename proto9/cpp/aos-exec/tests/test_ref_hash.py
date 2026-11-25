# Check {"$ref": "#/..."} in an entry (argv array, JSON .env) takes the entry file itself (ported from proto8 aos-exec tests/test_ref_hash.py).
# proto9 change: the two cases that used an inst sheet now use an argv array (inst sheets are EntryBad here); AOS_STACK is no longer given.
import json

from common import TmpCase


class RefHash(TmpCase):
    prefix = 'aos-exec-hash-'

    def run_ws(self, *argv):
        return self.run_(*argv, extra={'AOS_WS': str(self.d)})

    def test_argv_at_pointer_counts_from_file_root(self):
        self.put('e.json', {'cmds': {'sh': 'sh', 'say': 'echo "$0"'},
                            'tools': {'t': [{'$ref': '#/cmds/sh'}, '-c', {'$ref': '#/cmds/say'}, 'hi']}})
        self.assertEqual(self.run_ws('e.json#/tools/t'), (0, 'hi', ''))

    def test_argv_array_entry(self):
        self.put('a.json', [{'$ref': '#/2'}, 'x', 'echo'])
        self.assertEqual(self.run_ws('a.json'), (0, 'x echo', ''))

    def test_json_dotenv_takes_the_file_holding_it(self):
        self.put('e.json', {'tools': {'t': ['sh', '-c', 'echo "$GREET"']}})
        self.put('f.json', {'.env': {'GREET': {'$ref': '#/words/g'}}, 'words': {'g': 'hello'}, '_entry': 'e.json#/tools/t'})
        self.assertEqual(self.run_ws('f.json'), (0, 'hello', ''))

    def test_pointer_not_found_is_entry_bad_naming_the_pointer(self):
        self.put('e.json', [{'$ref': '#/nope'}])
        code, _, err = self.run_ws('e.json')
        self.assertEqual(code, 1)
        self.assertIn('EntryBad bad entry: cannot resolve directives in argv array: $ref pointer not found', err)
        self.assertIn('e.json#/nope', err)

    def test_resolved_argv_must_be_all_strings(self):
        self.put('n.json', {'k': 1, '_entry': ['echo', {'$ref': '#/k'}]})
        code, _, err = self.run_ws('n.json')
        self.assertEqual(code, 1)
        self.assertIn('EntryBad bad entry: resolved argv array must be all strings', err)

    def test_env_directive_and_path_prefix(self):
        self.put('p.json', ['echo', {'$env': 'X', '$path': 'y', '$prefix': '--d='}])
        self.assertEqual(self.run_('p.json', extra={'X': 'a/'}), (0, '--d=a/y', ''))
        code, _, err = self.run_('p.json')
        self.assertEqual(code, 1)
        self.assertIn('environment variable X is not set', err)
