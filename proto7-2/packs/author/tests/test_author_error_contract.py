"""錯誤路徑、索引表格與 aos 結案標記。"""
import argparse
import contextlib
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

PACK = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACK), str(PACK / 'checkers')]
import aos_three_gates as gates
import aos7_author as author
import aos7_author_aos as aos
import aos7_author_llm as llm
from test_author_aos import baseline_ref, REPO

REQ = PACK / 'examples/aos-tool-usage/request.json'
CAND = REQ.parent / 'valid.json'


class TestAuthorErrorContract(unittest.TestCase):
    @contextlib.contextmanager
    def csv_node(self):
        with tempfile.TemporaryDirectory(prefix='fx1-b-author-') as tmp:
            path = Path(tmp, 'author/req/csv1/request.json')
            path.parent.mkdir(parents=True)
            path.write_bytes((PACK / 'examples/csv-request/request.json').read_bytes())
            old = os.getcwd()
            os.chdir(tmp)
            try:
                yield Path(tmp)
            finally:
                os.chdir(old)

    def captured_main(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = author.main(args)
        return code, json.loads(stdout.getvalue()), stderr.getvalue()

    def test_csv_propose_io_error_contract(self):
        for failure in ('lock', 'write'):
            with self.subTest(failure=failure), self.csv_node() as node:
                args = ['propose', 'csv1', '--candidate', str(PACK / 'examples/csv-request/valid.json')]
                if failure == 'lock':
                    (node / 'author/author.lock').mkdir()
                    p = self.run_cli('aos7-author', *args, cwd=node)
                    code, out, stderr = p.returncode, json.loads(p.stdout), p.stderr
                else:
                    with mock.patch.object(author, 'write_json', side_effect=OSError('write unavailable')):
                        code, out, stderr = self.captured_main(args)
                self.assertEqual((code, out['ok'], out['why']), (3, False, 'unknown'))
                self.assertNotIn('Traceback', stderr)
                self.assertEqual(len(stderr.splitlines()), 1)
                self.assertTrue(stderr.startswith('aos7-author: 不確定：'))
                self.assertIn('照原樣再跑一次會接續', stderr)
                self.assertTrue((node / 'author/req/csv1/request.json').exists())

    def test_csv_llm_terminal_failure_exit(self):
        for rc, outcome in [(1, 'failed'), (1, 'rejected'), (1, 'denied'), (1, 'cancelled'), (2, None)]:
            with self.subTest(rc=rc, outcome=outcome), self.csv_node() as node:
                before = sorted(p.relative_to(node) for p in node.rglob('*'))
                reply = dict(outcome=outcome, text=None, billing='final', used=0)
                proc = subprocess.CompletedProcess([], rc, json.dumps(reply), '')
                with mock.patch.object(llm.subprocess, 'run', return_value=proc):
                    code, out, stderr = self.captured_main(['propose', 'csv1', '--llm', 'demo', '--budget', 'budget/llm'])
                self.assertEqual((code, out['why'], out['llm']['exit']), (1, 'invalid', rc))
                self.assertEqual(len(stderr.splitlines()), 1)
                self.assertNotIn('給符合需求的檔案與選項', stderr)
                self.assertIn('模型這邊沒做成：', stderr)
                self.assertNotIn('issues／gates 改候選', stderr)
                self.assertNotIn('_rejected', out)
                self.assertEqual(sorted(p.relative_to(node) for p in node.rglob('*')), before)

    def test_aos_and_csv_llm_uncertain_receipt(self):
        for rc, stdout in [(3, '{}'), (99, '{}'), (-9, '{}'), (0, 'broken'), (4, 'broken')]:
            for kind, arg in [('csv', 'csv1'), ('aos', str(REQ))]:
                with self.subTest(rc=rc, kind=kind), self.csv_node() as node:
                    proc = subprocess.CompletedProcess([], rc, stdout, '')
                    with mock.patch.object(llm.subprocess, 'run', return_value=proc):
                        code, out, stderr = self.captured_main(['propose', arg, '--llm', 'demo', '--budget', 'budget/llm'])
                    self.assertEqual((code, out['why']), (3, 'unknown'))
                    self.assertEqual(len(stderr.splitlines()), 1)
                    self.assertTrue(stderr.startswith('aos7-author: 不確定：'))
                    self.assertFalse((node / 'author/req/csv1/candidate.json').exists())
                    self.assertFalse((node / 'author/aos').exists())

    def test_aos_llm_terminal_failure_exit(self):
        for rc in (1, 2):
            with self.subTest(rc=rc), self.csv_node() as node:
                proc = subprocess.CompletedProcess([], rc, json.dumps(dict(outcome='rejected', text=None)), '')
                with mock.patch.object(llm.subprocess, 'run', return_value=proc):
                    code, out, stderr = self.captured_main(['propose', str(REQ), '--llm', 'demo', '--budget', 'budget/llm'])
                self.assertEqual((code, out['why']), (1, 'invalid'))
                self.assertIn('模型' if rc == 1 else '作者產生', stderr)
                self.assertFalse((node / 'author/aos').exists())

    def run_cli(self, entry, *args, **kw):
        return subprocess.run([str(PACK / 'bin' / entry), *map(str, args)], capture_output=True,
                              text=True, timeout=30, **kw)

    def test_help_and_bad_do_not_write(self):
        for entry, limit in [('aos7-author', 20), ('aos7-gates', 15)]:
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as tmp:
                p = self.run_cli(entry, '--help', cwd=tmp)
                self.assertEqual(p.returncode, 0)
                self.assertEqual(p.stderr, '')
                self.assertLessEqual(len(p.stdout.splitlines()), limit)
                for args in [('--no-such-option',), ('publish',)]:
                    p = self.run_cli(entry, *args, cwd=tmp)
                    self.assertEqual(p.returncode, 2)
                    self.assertEqual(p.stdout, '')
                    self.assertEqual(len(p.stderr.splitlines()), 1)
                    self.assertTrue(p.stderr.startswith(entry + ': '))
                    self.assertIn('。', p.stderr)
                    self.assertIn('例如', p.stderr)
                    self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_row_inside_last_matching_table(self):
        for prefix in ['| `packs/{name}/`', '| [{name}]']:
            match = prefix.format(name='old') + ' | old |\n'
            text = '| header |\n|---|\n' + match + '| other |\n\n- 後面的條列\n'
            row = prefix.format(name='new') + ' | new |'
            self.assertEqual(gates.insert_row(text, row, prefix), text.replace('\n\n-', '\n' + row + '\n\n-'))
            self.assertEqual(gates.insert_row('intro', row, prefix), 'intro\n' + row + '\n')

    def test_default_rules_and_missing_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp, 'codex')
            called = Path(tmp, 'called')
            fake.write_text('#!/bin/sh\ntouch "' + str(called) + '"\nexit 99\n')
            fake.chmod(0o755)
            env = dict(os.environ, PATH=tmp + ':' + os.environ['PATH'])
            p = self.run_cli('aos7-gates', 'check', REQ, CAND, '--no-scope', '--ref', baseline_ref('packs/usage'), env=env)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertEqual(p.stderr, '')
            self.assertFalse(called.exists())
            refs = subprocess.check_output(['git', '-C', str(REPO), 'show-ref'])
            with mock.patch.object(gates, 'run_gates', side_effect=AssertionError('must not run')):
                with mock.patch('sys.stdout'), mock.patch('sys.stderr'):
                    self.assertEqual(gates.main(['publish', str(REQ), str(CAND)]), 2)
            p = self.run_cli('aos7-gates', 'publish', REQ, CAND)
            self.assertEqual(p.returncode, 2)
            out = json.loads(p.stdout)
            self.assertEqual(out['gates']['1']['issues'][0]['rule'], 'repo')
            self.assertEqual(len(p.stderr.splitlines()), 1)
            self.assertIn(str(REPO), p.stderr)
            self.assertIn('--repo', p.stderr)
            self.assertEqual(refs, subprocess.check_output(['git', '-C', str(REPO), 'show-ref']))
            p = self.run_cli('aos7-author', 'publish', REQ, '--candidate', CAND, cwd=tmp)
            self.assertEqual(p.returncode, 2)
            self.assertIn(str(REPO), p.stderr)
            self.assertIn('--repo', p.stderr)
            self.assertEqual(len(p.stderr.splitlines()), 1)

    def test_gate_code_mapping_and_stderr(self):
        for code, extra, why in [(0, {}, None), (1, {}, 'invalid'), (1, {'branch': 'x', 'failed_gate': None}, 'conflict'), (2, {}, 'invalid'), (3, {}, 'unknown'), (7, {}, 'unknown')]:
            proc = subprocess.CompletedProcess([], code, json.dumps(dict(ok=code == 0, **extra)).encode(), b'aos7-gates: detail\n')
            a = argparse.Namespace(arg='r', no_scope=True, repo=None, ref=None)
            with mock.patch.object(aos.subprocess, 'run', return_value=proc):
                out, actual = aos.gates(a, 'check', 'c', 'rules')
            self.assertEqual(actual, why)
            self.assertEqual(out['error'], 'detail')
        line = author.error_line({'why': 'unknown', 'error': 'x\ny' * 400})
        self.assertNotIn('\n', line)
        self.assertLessEqual(len(line), 300)
        self.assertTrue(line.startswith('aos7-author: 不確定：'))
        self.assertIn('照原樣再跑一次會接續', line)

    def test_close_merge_skip_and_lock_failure(self):
        req, _ = gates.request(REQ)
        out = dict(ok=True, why=None, job='usage1_12345678', branch='apprentice/usage1_12345678', commit='c', candidate_sha='a' * 64)
        a = argparse.Namespace(arg=str(REQ))
        with tempfile.TemporaryDirectory() as tmp:
            old = os.getcwd()
            os.chdir(tmp)
            self.addCleanup(os.chdir, old)
            path = Path('author/req/usage1/receipt.json')
            self.assertEqual(aos.close_aos(a, req, out), out)
            doc = json.loads(path.read_bytes())
            self.assertEqual(doc['request_sha'], hashlib.sha256(REQ.read_bytes()).hexdigest())
            self.assertTrue(doc['closed'])
            self.assertEqual(doc['kind'], 'aos-tool')
            first = doc['closed_at']
            aos.close_aos(a, req, dict(out, candidate_sha='b' * 64, dup=True))
            doc = json.loads(path.read_bytes())
            self.assertEqual(len(doc['versions']), 2)
            self.assertEqual(doc['closed_at'], first)
            path.write_text('{"v":1,"rid":"usage1","closed":true,"versions":{}}')
            before = path.read_bytes()
            self.assertIn('close_skipped', aos.close_aos(a, req, out))
            self.assertEqual(path.read_bytes(), before)
            with open('author/author.lock', 'a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                with mock.patch.object(author, 'LOCK_TIMEOUT', .02):
                    result = aos.close_aos(a, req, out)
            self.assertEqual(result['why'], 'unknown')
            self.assertFalse(result['ok'])
            self.assertIn('分支 apprentice/usage1_12345678 已建', result['error'])
            self.assertEqual(path.read_bytes(), before)
            # 讀不到的標記＝不確定（不當成別人的帳略過）
            path.unlink()
            path.mkdir()
            result = aos.close_aos(a, req, out)
            self.assertEqual((result['ok'], result['why']), (False, 'unknown'))
            path.rmdir()
            # 同 rid 已有 CSV 需求帳：不寫結案標記，免得 CSV close 被跳過
            Path('author/req/usage1/request.json').write_text('{"v":1}')
            self.assertIn('close_skipped', aos.close_aos(a, req, out))
            self.assertFalse(path.exists())
