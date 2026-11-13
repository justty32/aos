# Check the $ref path rule (11-13 ref-path-rules): left of # is the file system (from the folder of the file), right of # is
# inside JSON (#/ root, #./ the object the $ref is in, #../ one level up; # and #/ the whole file). The table
# lib/tests/ref_path_cases.json is shared with lib/aos_refpath.py (index paths use the same rule and parser).
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
BIN = HERE.parent / 'bin' / 'aos-directive'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
CASES = json.loads((HERE.parent.parent.parent / 'lib' / 'tests' / 'ref_path_cases.json').read_text())['cases']


def nest(toks, leaf):
    for t in reversed(toks):
        leaf = {t.replace('~1', '/').replace('~0', '~'): leaf}
    return leaf


class RefSpot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-directive-spot-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name)) / 'w'
        self.d.mkdir()

    def put(self, name, doc):
        p = self.d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc))
        return p

    def run_file(self, name, *more, stdin=None):
        flags = ['--file', str(self.d / name)] if name else []
        text = stdin if stdin is not None else (self.d / (name or 'm.json')).read_text()
        p = subprocess.run([str(BIN), *flags, *more], input=text, cwd=self.d, env=ENV, capture_output=True, text=True, timeout=10)
        return p.returncode, json.loads(p.stdout) if p.returncode == 0 else None, p.stderr.strip()

    def test_shared_table(self):
        # stdin is the {"$ref": …} itself, sitting at HERE/r of the file (--at), so the object it is in is HERE
        for n, c in enumerate(CASES):
            with self.subTest(rule=c['rule'], text=c['text']):
                root = self.d / str(n)
                root.mkdir()
                ref = json.dumps({'$ref': c['text']})
                if c.get('err') == 'unknown':                       # which file / where is not known: left as it is
                    p = subprocess.run([str(BIN)], input=ref, cwd=root, env=ENV, capture_output=True, text=True, timeout=10)
                    self.assertEqual((p.returncode, json.loads(p.stdout) if p.returncode == 0 else p.stderr), (0, {'$ref': c['text']}))
                    continue
                argv = [str(BIN)]
                if c['file'] is not None:
                    argv += ['--file', c['file'], '--at', ''.join('/' + t for t in c['here'] + ['r'])]
                want = 'HIT'
                if 'to' in c:
                    f, _, ptr = c['to'].partition('#')
                    if f.startswith('/') or c['text'].rstrip('#/').endswith('/') or c['text'].endswith('sub/'):
                        want = None                                  # a folder or a file outside: cannot be read
                        (root / f.lstrip('/')).mkdir(parents=True, exist_ok=True)
                    else:
                        (root / f).parent.mkdir(parents=True, exist_ok=True)
                        (root / f).write_text(json.dumps(nest(ptr.split('/')[1:] if ptr else [], 'HIT')))
                else:
                    want = None
                p = subprocess.run(argv, input=ref, cwd=root, env=ENV, capture_output=True, text=True, timeout=10)
                if want is None:
                    self.assertEqual(p.returncode, 1, p.stdout)
                    self.assertIn('DirectiveBad', p.stderr)
                else:
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertEqual(json.loads(p.stdout), want)

    def test_the_object_it_is_in(self):
        self.put('m.json', {'defs': {'cmd': ['echo', 'hi'], 'd': 'bin'},
                            'a': {'x': 1, 'r': {'$ref': '#./x'}, 'up': {'$ref': '#../defs/d'}, 'me': {'$ref': '#.'}},
                            'argv': [{'$ref': '#../defs/cmd/0'}, {'$ref': '#./0'}, {'$ref': '#../defs/d', '$path': 'x', '$prefix': '--d='}]})
        code, out, err = self.run_file('m.json')
        self.assertEqual(code, 1)                                    # a/me points at a, which holds me itself
        self.assertIn('DirectiveBad $ref loop', err)
        doc = json.loads((self.d / 'm.json').read_text())
        del doc['a']['me']
        self.put('m.json', doc)
        code, out, err = self.run_file('m.json')
        self.assertEqual(code, 0, err)
        self.assertEqual(out['a'], {'x': 1, 'r': 1, 'up': 'bin'})
        self.assertEqual(out['argv'], ['echo', 'echo', '--d=bin/x'])   # argv/1 takes argv/0 as written, then resolves it from its own place

    def test_inside_a_reffed_file_counts_from_its_place_there(self):
        self.put('sub/inc.json', {'a': {'x': {'$ref': '#../y'}, 'side': {'$ref': 'side.json#/v'}}, 'y': 'inc-y'})
        self.put('sub/side.json', {'v': 'sub-side'})
        self.put('m.json', {'part': {'$ref': 'sub/inc.json#/a'}, 'y': 'm-y'})
        code, out, err = self.run_file('m.json')
        self.assertEqual((code, out), (0, {'part': {'x': 'inc-y', 'side': 'sub-side'}, 'y': 'm-y'}), err)

    def test_whole_file_is_the_ref(self):
        self.put('x.json', {'k': 1})
        code, out, _ = self.run_file('m.json', stdin=json.dumps({'$ref': 'x.json#/k'}))
        self.assertEqual((code, out), (0, 1))
        code, _, err = self.run_file('m.json', stdin=json.dumps({'$ref': '#./k'}))
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad', err)
        self.assertIn('sits in no object', err)

    def test_array_of_refs_counts_from_the_same_place(self):
        self.put('o.json', {'p': {'y': 2}})
        self.put('m.json', {'p': {'x': 1}, 'g': {'m': {'$ref': ['#../p', 'o.json#/p']}}})
        code, out, err = self.run_file('m.json')
        self.assertEqual((code, out['g'] if out else err), (0, {'m': {'x': 1, 'y': 2}}))

    def test_without_file_is_left_as_is(self):
        self.put('other.json', {'k': 1})
        doc = {'a': {'$ref': '#/k'}, 'b': {'$ref': ['other.json', '#./k']}, 'c': {'$ref': 'other.json#/k'}}
        self.put('m.json', doc)
        code, out, _ = self.run_file(None)
        self.assertEqual((code, out), (0, {'a': {'$ref': '#/k'}, 'b': {'$ref': ['other.json', '#./k']}, 'c': 1}))

    def test_bad_paths_are_errors(self):
        self.put('x.json', {'a': 1})
        for text in ('#a', 'x.json#a', 'x.json#./a', 'x.json#../a', '#../../../a', '', '#.x'):
            with self.subTest(text=text):
                self.put('m.json', {'o': {'r': {'$ref': text}}})
                code, _, err = self.run_file('m.json')
                self.assertEqual(code, 1, text)
                self.assertIn('DirectiveBad $ref', err)

    def test_dot_dot_after_hash_slash_is_a_key(self):
        self.put('m.json', {'a': {'..': {'b': 'dots'}}, 'r': {'$ref': '#/a/../b'}, 's': {'$ref': '#/x/../r'}})
        code, out, err = self.run_file('m.json', stdin=json.dumps({'a': {'..': {'b': 'dots'}}, 'r': {'$ref': '#/a/../b'}}))
        self.assertEqual((code, out['r'] if out else err), (0, 'dots'))
        code, _, err = self.run_file('m.json', stdin=json.dumps({'s': {'$ref': '#/x/../r'}}))
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad $ref pointer not found', err)

    def test_loops_folders_and_missing(self):
        self.put('m.json', {'r': {'$ref': 'm.json#/r'}})
        code, _, err = self.run_file('m.json')
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad $ref loop:', err)
        self.put('a.json', {'x': {'$ref': 'b.json#/y'}})
        self.put('b.json', {'y': {'$ref': 'a.json#/x'}})
        code, _, err = self.run_file('a.json')
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad $ref loop:', err)
        self.put('sub/x.json', {})
        for text, want in (('sub', 'DirectiveBad $ref cannot read'), ('../w', 'DirectiveBad $ref cannot read'),
                           ('nope.json', 'DirectiveBad $ref cannot read'), ('sub/x.json#/k', 'DirectiveBad $ref pointer not found'),
                           ('#', 'DirectiveBad $ref loop')):
            with self.subTest(text=text):
                self.put('m.json', {'r': {'$ref': text}})
                code, _, err = self.run_file('m.json')
                self.assertEqual(code, 1, text)
                self.assertIn(want, err)

    def test_at_flag(self):
        self.put('m.json', {'o': {'k': 'ok'}})
        code, out, err = self.run_file('m.json', '--at', '/o/r', stdin=json.dumps({'$ref': '#./k'}))
        self.assertEqual((code, out), (0, 'ok'), err)
        code, _, err = self.run_file(None, '--at', '/o', stdin='{}')
        self.assertEqual(code, 1)
        self.assertIn('ArgumentsBad', err)
        code, _, err = self.run_file('m.json', '--at', 'o', stdin='{}')
        self.assertEqual(code, 1)
        self.assertIn('ArgumentsBad', err)


if __name__ == '__main__':
    unittest.main()
