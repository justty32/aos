# Check {"$ref": "#/..."} in an entry (inst, argv array, JSON .env) takes the entry file itself (11-12).
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-exec'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


class RefHash(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-exec-hash-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        self.env = dict(ENV, AOS_WS=str(self.d), AOS_STACK=str(self.d / 'st') + '/')

    def put(self, name, doc):
        (self.d / name).write_text(json.dumps(doc))

    def run_exec(self, *argv):
        p = subprocess.run([str(BIN), *argv], cwd=self.d, env=self.env, capture_output=True, text=True, timeout=10)
        return p.returncode, p.stdout.strip(), p.stderr.strip()

    def test_inst_at_pointer_counts_from_file_root(self):
        self.put('e.json', {'cmds': {'echo': ['sh', '-c', 'echo "$0 $GREET"', 'hi']},
                            'tools': {'t': {'argv': {'$ref': '#/cmds/echo'}}}})
        self.assertEqual(self.run_exec('e.json#/tools/t'), (0, 'hi', ''))

    def test_argv_array_entry(self):
        (self.d / 'a.json').write_text(json.dumps([{'$ref': '#/2'}, 'x', 'echo']))
        self.assertEqual(self.run_exec('a.json'), (0, 'x echo', ''))

    def test_json_dotenv_takes_the_file_holding_it(self):
        self.put('e.json', {'tools': {'t': {'argv': ['sh', '-c', 'echo "$GREET"']}}})
        self.put('f.json', {'.env': {'GREET': {'$ref': '#/words/g'}}, 'words': {'g': 'hello'}, '_entry': 'e.json#/tools/t'})
        self.assertEqual(self.run_exec('f.json'), (0, 'hello', ''))

    def test_pointer_not_found_is_directive_bad(self):
        self.put('e.json', {'argv': {'$ref': '#/nope'}})
        code, _, err = self.run_exec('e.json')
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad', err)
        self.assertIn('e.json#/nope', err)


if __name__ == '__main__':
    unittest.main()
