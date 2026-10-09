"""四道郵局學徒題：需求藏坑、真資料、壞候選與離線三關。"""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

A = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(A / 'checkers'))
import aos_three_gates as gates

TASKS = ('mailcount', 'mailsent', 'mailopen', 'mailstatus')


def load_checker(folder):
    spec = importlib.util.spec_from_file_location(
        'answer_' + folder.name.replace('-', '_'), folder / 'check_answer.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def materialize(top, candidate):
    for path, content in candidate['files'].items():
        dest = top / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding='utf-8')


def header(path):
    """只讀信頭，讓測試另外核對真樣本的組成。"""
    lines = path.read_text(encoding='utf-8').splitlines()
    if not lines or lines[0] != '---':
        return {}
    fields = {}
    for line in lines[1:]:
        if line == '---':
            break
        if ': ' in line:
            key, value = line.split(': ', 1)
            fields[key] = value
    return fields


class TestAuthorAosMail(unittest.TestCase):
    def test_requests_limits_and_shared_fixture(self):
        shared = None
        for name in TASKS:
            with self.subTest(name=name):
                folder = A / ('examples/aos-tool-' + name)
                req, _ = gates.request(folder / 'request.json')
                self.assertEqual(req['name'], name)
                self.assertEqual(req['kind'], 'aos-tool')
                self.assertEqual(req['scope']['only'], ['packs/' + name + '/', 'INDEX.md 一列'])
                self.assertEqual(req['scope']['max_files'], 8)
                self.assertEqual(len(req['tools']), 2)
                self.assertEqual(len(req['accept']), 3)
                self.assertLess((folder / 'request.json').stat().st_size, 3072)
                full_request = json.dumps(req, ensure_ascii=False)
                # 小寫禁詞不擴成大寫：mailopen 必須能說明終局狀態 DONE。
                for forbidden in ('done', '.tmp', 'teams', 'team', '歸檔'):
                    self.assertNotIn(forbidden, full_request)
                candidate = json.loads((folder / 'valid.json').read_text())
                self.assertEqual(set(candidate), {'v', 'rid', 'kind', 'name', 'files', 'row', 'report'})
                self.assertEqual(len(candidate['files']), 4)
                for content in candidate['files'].values():
                    self.assertLessEqual(len(content.encode('utf-8')), 8192)
                self.assertIn('## 第一次跑', candidate['files']['packs/' + name + '/README.md'])
                self.assertLessEqual(len(candidate['files']['packs/' + name + '/bin/aos7-' + name].splitlines()), 12)
                self.assertIn('以後交接書該點名的工具', candidate['report'])
                fixture = folder / 'fixture'
                files = [p for p in fixture.rglob('*') if p.is_file()]
                self.assertTrue(files)
                for path in files:
                    self.assertLessEqual(path.stat().st_size, 4096, str(path))
                    self.assertNotEqual(path.suffix, '.pyc')
                self.assertFalse([p for p in fixture.rglob('*') if p.is_dir() and not any(p.iterdir())])
                content = {p.relative_to(fixture).as_posix(): p.read_bytes() for p in files}
                if shared is None:
                    shared = content
                else:
                    self.assertEqual(content, shared)

    def test_real_fixture_anatomy(self):
        fixture = A / 'examples/aos-tool-mailcount/fixture'
        people = ('alice', 'bob', 'carol', 'dave')
        records, archived = [], []
        counts = {}
        for person in people:
            inbox = fixture / person / 'inbox'
            self.assertTrue(inbox.is_dir())
            current = [header(p) for p in inbox.glob('*.md') if not p.name.startswith('.')]
            history = [header(p) for p in (inbox / 'done').glob('*.md') if not p.name.startswith('.')]
            records.extend(current)
            archived.extend(history)
            counts[person] = {'letters': len(current) + len(history),
                              'requests': sum(r.get('status') == 'REQUEST' for r in current + history)}
        records += archived
        self.assertTrue(any(r.get('status') == 'REQUEST' for r in archived))
        self.assertTrue(any(r.get('status') == 'DONE' for r in archived))
        self.assertTrue(any(r.get('status') == 'DONE' and r.get('id', '').startswith('re-') for r in records))
        self.assertTrue(any(r.get('status') == 'PROGRESS' and r.get('re') for r in records))
        self.assertTrue(any(r.get('status') == 'BLOCKED' and r.get('re') for r in records))
        closed = {r.get('re') for r in records if r.get('status') in ('DONE', 'BLOCKED', 'NEEDS-USER', 'FAILED')}
        pending = {r['id'] for r in records if r.get('status') == 'REQUEST' and r['id'] not in closed}
        self.assertGreaterEqual(len(pending), 2)
        replied = {r.get('re') for r in records if r.get('re')}
        self.assertGreaterEqual(len(pending - replied), 2)
        self.assertEqual((fixture / 'teams/dev/members').read_text().splitlines()[0], 'dave')
        self.assertGreaterEqual(len(list((fixture / 'teams/dev/inbox').glob('*.md'))), 2)
        partials = list(fixture.glob('*/inbox/.tmp/*'))
        self.assertTrue(partials)
        self.assertTrue(any(header(p).get('status') == 'DONE' and header(p).get('re') in pending for p in partials))
        self.assertTrue(list(fixture.glob('*/inbox/.seen')))
        self.assertTrue(list(fixture.rglob('*.lock')))
        senders, statuses = {}, {}
        for record in records:
            sender, status = record['from'], record['status']
            senders[sender] = senders.get(sender, 0) + 1
            statuses[status] = statuses.get(status, 0) + 1
        expected = {
            'mailcount': {'v': 1, 'people': counts},
            'mailsent': {'v': 1, 'senders': dict(sorted(senders.items()))},
            'mailopen': {'v': 1, 'open': sorted(pending)},
            'mailstatus': {'v': 1, 'statuses': dict(sorted(statuses.items()))},
        }
        for name in TASKS:
            with self.subTest(name=name):
                checker = load_checker(A / ('examples/aos-tool-' + name))
                self.assertEqual(checker.MAIN, expected[name])
                self.assertIs(type(checker.MAIN['v']), int)

    def test_valid_answers_and_candidate_tests(self):
        for name in TASKS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                folder = A / ('examples/aos-tool-' + name)
                top = Path(tmp) / 'proto'
                materialize(top, json.loads((folder / 'valid.json').read_text()))
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
        for name in TASKS:
            folder = A / ('examples/aos-tool-' + name)
            checker = load_checker(folder)
            original = json.loads((folder / 'valid.json').read_text())
            module_path = 'packs/' + name + '/aos7_' + name + '.py'
            source = original['files'][module_path]
            print_line = 'print(json.dumps(summarize(a.node), ensure_ascii=False))'
            # 每個突變只犯一種錯；錯誤標籤也要教得出對應慣例。
            mutations = {
                'ignore_done': (source.replace("for folder in (inbox, inbox / 'done'):", 'for folder in (inbox,):'), 'inbox/done/'),
                'include_hidden': (source.replace("folder.glob('*.md')", "folder.rglob('*.md')").replace("p.name.startswith('.') or ", ''), '. 開頭'),
                'include_teams': (source.replace('for box in sorted(root.iterdir()):', "for box in sorted(p.parent for p in root.rglob('inbox') if p.is_dir()):").replace("box.name == 'teams' or ", ''), 'teams/'),
                'blank_line': (source.replace(print_line, print_line + '\n    print()'), None),
                'lock_file': (source.replace(print_line, "(a.node / 'candidate.lock').write_text('locked')\n    " + print_line), 'readonly'),
            }
            for mutation, (changed, keyword) in mutations.items():
                with self.subTest(name=name, mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                    self.assertNotEqual(changed, source)
                    top = Path(tmp) / 'proto'
                    candidate = dict(original, files=dict(original['files'], **{module_path: changed}))
                    materialize(top, candidate)
                    fixture = Path(tmp) / 'fixture'
                    shutil.copytree(folder / 'fixture', fixture)
                    result = checker.check_answer(top, fixture)
                    self.assertIs(result['ok'], False, (name, mutation))
                    self.assertTrue(result['issues'])
                    if keyword:
                        self.assertTrue(any(keyword in issue for issue in result['issues']), result)

    def test_real_offline_gates(self):
        for name in TASKS:
            with self.subTest(name=name):
                folder = A / ('examples/aos-tool-' + name)
                # rules 審查不打 AI；check 不會發布候選。
                p = subprocess.run([sys.executable, '-B', str(A / 'bin/aos7-gates'), 'check', str(folder / 'request.json'), str(folder / 'valid.json'), '--reviewer', 'rules', '--no-scope'], capture_output=True, text=True, timeout=120)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                result = json.loads(p.stdout)
                self.assertIs(result['ok'], True, result)
                for gate in ('1', '2', '3'):
                    self.assertIs(result['gates'][gate]['ok'], True, result)


if __name__ == '__main__':
    unittest.main()
