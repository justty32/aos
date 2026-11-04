"""三連同形題：固定答案、五種壞候選、需求契約與真離線三關。"""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

A = Path(__file__).resolve().parents[1]
P = A.parents[1]
sys.path.insert(0, str(A / 'checkers'))
import aos_three_gates as gates

TASKS = [('gap', 'evgap'), ('runs', 'runs'), ('audit', 'mailtodo')]


def load_checker(folder):
    spec = importlib.util.spec_from_file_location('answer_' + folder.name.replace('-', '_'), folder / 'check_answer.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def materialize(top, candidate):
    for path, content in candidate['files'].items():
        dest = top / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)


class TestAuthorAos3x(unittest.TestCase):
    def test_requests_and_limits(self):
        for topic, name in TASKS:
            with self.subTest(topic=topic):
                folder = A / ('examples/aos-tool-' + topic)
                req, card = gates.request(folder / 'request.json')
                self.assertEqual(req['name'], name)
                self.assertLess((folder / 'request.json').stat().st_size, 4096)
                candidate = json.loads((folder / 'valid.json').read_text())
                self.assertLessEqual((folder / 'valid.json').stat().st_size, 65536)
                self.assertEqual(set(candidate), {'v','rid','kind','name','files','row','report'})
                self.assertEqual(len(candidate['files']), 4)
                for text in candidate['files'].values():
                    self.assertLessEqual(len(text.encode()), 8192)
                fixture_files = [p for p in (folder / 'fixture').rglob('*') if p.is_file()]
                self.assertLessEqual(len(fixture_files), 60)
                for file in fixture_files:
                    self.assertLessEqual(file.stat().st_size, 4096, str(file))
                    self.assertNotEqual(file.suffix, '.pyc')
                self.assertFalse([p for p in (folder / 'fixture').rglob('*') if p.is_dir() and not any(p.iterdir())])

    def test_valid_answers_and_candidate_tests(self):
        for topic, name in TASKS:
            with self.subTest(topic=topic), tempfile.TemporaryDirectory() as tmp:
                folder = A / ('examples/aos-tool-' + topic)
                top = Path(tmp) / 'proto'
                candidate = json.loads((folder / 'valid.json').read_text())
                materialize(top, candidate)
                fixture = Path(tmp) / 'fixture'
                shutil.copytree(folder / 'fixture', fixture)
                checker = load_checker(folder)
                self.assertEqual(checker.check_answer(top, fixture), {'ok': True, 'issues': []})
                p = subprocess.run([sys.executable, '-B', str(folder / 'check_answer.py'), str(top), str(fixture)], capture_output=True, text=True, timeout=90)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                self.assertEqual(json.loads(p.stdout), {'ok': True, 'issues': []})
                self.assertEqual(len(p.stdout.splitlines()), 1)
                tests = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(top / ('packs/' + name + '/tests'))], capture_output=True, text=True, timeout=30)
                self.assertEqual(tests.returncode, 0, tests.stdout + tests.stderr)
                self.assertIn('Ran 2 tests', tests.stderr)

    def test_five_mutations_per_task(self):
        for topic, name in TASKS:
            folder = A / ('examples/aos-tool-' + topic)
            checker = load_checker(folder)
            original = json.loads((folder / 'valid.json').read_text())
            module_path = 'packs/' + name + '/aos7_' + name + '.py'
            source = original['files'][module_path]
            print_line = 'print(json.dumps(summarize(a.node' + (')' if name == 'evgap' else ', now)') + '))'
            # Exercise framing, exact int-vs-bool, explicit sort order and read-only snapshot.
            mutations = {
                'blank_line': source.replace(print_line, print_line + "\n    print()"),
                'bool_version': source.replace('v=1', 'v=True'),
                'transient_lock': source.replace(print_line, "lock = a.node / 'temporary.lock'\n    lock.write_text('locked')\n    lock.unlink()\n    " + print_line),
                'lock_file': source.replace(print_line, "(a.node / 'candidate.lock').write_text('locked')\n    " + print_line),
            }
            if name == 'evgap':
                mutations['wrong_sort'] = source.replace('missing.append([a + 1, b - 1])', 'missing.insert(0, [a + 1, b - 1])')
            elif name == 'runs':
                mutations['wrong_sort'] = source.replace("out[table].sort(key=lambda x: x['name'])", "out[table].sort(key=lambda x: x['name'], reverse=True)")
            else:
                mutations['wrong_sort'] = source.replace("key=lambda x: (x['to'], x['id'])", "key=lambda x: (x['to'], x['id']), reverse=True")
            for mutation, changed in mutations.items():
                with self.subTest(topic=topic, mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                    self.assertNotEqual(changed, source)
                    top = Path(tmp) / 'proto'
                    candidate = dict(original, files=dict(original['files'], **{module_path: changed}))
                    materialize(top, candidate)
                    fixture = Path(tmp) / 'fixture'
                    shutil.copytree(folder / 'fixture', fixture)
                    result = checker.check_answer(top, fixture)
                    self.assertIs(result['ok'], False, (topic, mutation))
                    self.assertTrue(result['issues'])
                    if mutation in ('lock_file', 'transient_lock'):
                        self.assertTrue(any('readonly' in issue for issue in result['issues']), result)

    def test_snapshot_links_metadata_and_cache(self):
        for topic, _ in TASKS:
            checker = load_checker(A / ('examples/aos-tool-' + topic))
            with self.subTest(topic=topic), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                target = root / 'data'
                target.write_bytes(b'original')
                (root / 'broken').symlink_to(root / 'missing')
                before = checker.snapshot(root)
                cache = root / '__pycache__'
                cache.mkdir()
                (cache / 'cache.pyc').write_bytes(b'allowed')
                self.assertTrue(checker.same_snapshot(before, checker.snapshot(root)))
                stamp = target.stat().st_mtime_ns
                import os
                os.utime(target, ns=(target.stat().st_atime_ns, stamp + 1_000_000))
                self.assertFalse(checker.same_snapshot(before, checker.snapshot(root)))

    def test_real_offline_gates(self):
        for topic, name in TASKS:
            with self.subTest(topic=topic):
                folder = A / ('examples/aos-tool-' + topic)
                # check never publishes; rules reviewer makes no AI/network call.
                p = subprocess.run([sys.executable, '-B', str(A / 'bin/aos7-gates'), 'check', str(folder / 'request.json'), str(folder / 'valid.json'), '--reviewer', 'rules', '--no-scope'], capture_output=True, text=True, timeout=120)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                result = json.loads(p.stdout)
                self.assertIs(result['ok'], True, result)
                for gate in ('1', '2', '3'):
                    self.assertIs(result['gates'][gate]['ok'], True, result)


if __name__ == '__main__':
    unittest.main()
