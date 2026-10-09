"""LLM 來源用本地 HTTP 走真 llmcall，不打真網路。"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from unittest import mock

PACK = Path(__file__).resolve().parents[1]
TOP = PACK.parents[1]
sys.path[:0] = [str(TOP / 'tests'), str(PACK)]
from base import DaemonCase
import _proc
import aos7_author as author
from aos7_author_llm import propose_llm, prompt_request
from aos7_fs import write_json

EXAMPLE = PACK / 'examples/csv-request'
AUTHOR = PACK / 'bin/aos7-author'
BUDGET = TOP / 'packs/budget/bin/aos7-budget'
MODEL = 'test/model'


class TestAuthorLLM(DaemonCase):
    """〔author〕本地 LiteLLM、原文驗證、回條重印、提示預覽與 CLI 契約。"""

    def setUp(self):
        super().setUp()
        self.node = self.mknode('work')
        shutil.copyfile(TOP / 'packs/step/examples/csv/data.csv', Path(self.node, 'data.csv'))
        self.assertTrue(author.register_request(self.node, str(EXAMPLE / 'request.json'))['ok'])
        self.llmnode = Path(self.root, 'llm')
        self.bd = self.llmnode / 'budget/llm'
        write_json(str(self.llmnode / '.aos/round.json'), {'round': 5, 'open': False})
        write_json(str(self.bd / 'grant.json'), {'v': 1, 'grant': 'g1', 'budget': 'llm',
                   'holder': 'author', 'resource': 'llm.tokens', 'gateway': 'llm.litellm',
                   'amount': 100000000, 'clock': 'completed_tock', 'from': 0,
                   'until': 1000000, 'delegate': False})
        p = subprocess.run([sys.executable, str(BUDGET), 'init', 'budget/llm'],
                           cwd=self.llmnode, capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = subprocess.Popen([sys.executable, str(BUDGET), 'ledger', 'budget/llm'],
                             cwd=self.llmnode, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=True)
        _proc.track(self, p, group=True)
        self.wait_for(lambda: (self.bd / 'ledger.lock').exists())
        self.bodies = []
        self.code = 200
        self.content = (EXAMPLE / 'valid.json').read_text()
        self.usage = {'prompt_tokens': 100, 'completion_tokens': 120, 'total_tokens': 220}
        case = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                case.bodies.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                reply = ({'choices': [{'message': {'content': case.content}, 'finish_reason': 'stop'}],
                          'usage': case.usage} if case.code in (200, 500) else {'error': 'bad request'})
                raw = json.dumps(reply).encode()
                self.send_response(case.code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .02})
        self.worker.start()
        self.addCleanup(self.stop_server)
        self.env = dict(os.environ, AOS7_LITELLM_URL='http://127.0.0.1:%d/v1' % self.server.server_port,
                        AOS7_LITELLM_KEY='')

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(2)

    def invoke(self, **kw):
        return propose_llm(self.node, 'csv1', model=MODEL, budget='../llm/budget/llm', env=self.env, **kw)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(AUTHOR), *map(str, args)], cwd=self.node,
                              env=self.env, capture_output=True, text=True, timeout=15)

    def stored_raw(self, r):
        doc = json.loads(Path(self.node, 'author/req/csv1/candidate.json').read_bytes())
        return author.candidate_raw(doc['versions'][r['candidate_sha']])

    def test_valid_replay_and_prompt(self):
        p = self.cli('propose', 'csv1', '--llm', MODEL, '--budget', '../llm/budget/llm')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        first = json.loads(p.stdout)
        raw = self.content.encode()
        self.assertEqual(first['job'], 'csv1_' + hashlib.sha256(raw).hexdigest()[:8])
        self.assertEqual(first['llm']['usage'], self.usage)
        self.assertEqual(first['llm']['used'], 220)
        self.assertTrue(Path(first['llm']['receipt_path']).is_file())
        self.assertTrue(str(first['llm']['receipt_path']).startswith(str(self.llmnode)))
        body = self.bodies[0]
        self.assertEqual(body['model'], MODEL)
        self.assertNotIn('max_tokens', body)
        self.assertNotIn('temperature', body)
        self.assertEqual([m['role'] for m in body['messages']], ['system', 'user'])
        user = body['messages'][1]['content']
        self.assertIn('部門統計：每個部門的筆數、總額、平均', user)
        self.assertIn('csv.convert', user)
        self.assertIn('csv.stats', user)
        self.assertNotIn(self.content, user)
        self.assertNotIn('轉檔後統計', user)
        again = self.cli('propose', 'csv1', '--llm', MODEL, '--budget', '../llm/budget/llm')
        self.assertEqual(again.returncode, 0, again.stderr)
        second = json.loads(again.stdout)
        self.assertEqual(len(self.bodies), 1)
        for key in ('candidate_sha', 'job', 'issues', 'llm'):
            self.assertEqual(first[key], second[key])
        self.assertEqual(self.stored_raw(first), raw)

    def test_fences_are_not_repaired(self):
        self.content = '```json\n' + self.content + '\n```'
        r = self.invoke()
        self.assertEqual(r['why'], 'invalid', r)
        self.assertIn('json', {i['rule'] for i in r['issues']})
        self.assertEqual(self.stored_raw(r), self.content.encode())

    def test_bad_path(self):
        self.content = (EXAMPLE / 'bad-path.json').read_text()
        r = self.invoke()
        self.assertEqual(r['why'], 'invalid', r)
        self.assertIn('path', {i['rule'] for i in r['issues']})

    def test_http_rejected_no_candidate(self):
        self.code = 400
        r = self.invoke()
        self.assertEqual((r['why'], r['llm']['outcome'], r['llm']['exit']), ('invalid', 'rejected', 1))
        self.assertFalse(Path(self.node, 'author/req/csv1/candidate.json').exists())

    def test_prompt_out_deterministic(self):
        for name in ('one.json', 'two.json'):
            p = self.cli('propose', 'csv1', '--llm', MODEL, '--budget', '../llm/budget/llm',
                         '--prompt-out', name)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        raw = Path(self.node, 'one.json').read_bytes()
        self.assertEqual(raw, Path(self.node, 'two.json').read_bytes())
        self.assertEqual(raw, prompt_request(author.Node(self.node), 'csv1', MODEL))
        self.assertEqual(self.bodies, [])
        self.assertFalse(Path(self.node, 'author/req/csv1/candidate.json').exists())

    def test_cli_argparse_errors(self):
        for args in (('--llm', MODEL), ('--llm', MODEL, '--budget', str(self.bd),
                                      '--candidate', str(EXAMPLE / 'valid.json'))):
            p = self.cli('propose', 'csv1', *args)
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            self.assertIn('error:', p.stderr)
        self.assertEqual(self.bodies, [])

    def test_failed_reply_with_text_is_not_a_candidate(self):
        self.code, self.usage = 500, None
        r = self.invoke()
        self.assertEqual((r['why'], r['llm']['outcome'], r['llm']['exit'], r['llm']['billing']),
                         ('invalid', 'failed', 4, 'pending'), r)
        self.assertEqual(len(self.bodies), 1)
        self.assertFalse(Path(self.node, 'author/req/csv1/candidate.json').exists())

    def test_long_model_call_id_keeps_hash(self):
        ids = []
        for tail in ('A', 'B'):
            model = 'm' * 80 + tail
            r = propose_llm(self.node, 'csv1', model=model, budget='../llm/budget/llm', env=self.env,
                            prompt_out='p-%s.json' % tail)
            raw = Path(self.node, 'p-%s.json' % tail).read_bytes()
            self.assertLessEqual(len(r['llm']['call_id']), 64)
            self.assertTrue(r['llm']['call_id'].endswith('-' + hashlib.sha256(raw).hexdigest()[:8]))
            ids.append(r['llm']['call_id'])
        self.assertNotEqual(ids[0], ids[1])

    def test_delivered_pending_and_missing_receipt(self):
        self.usage = None
        r = self.invoke()
        self.assertTrue(r['ok'], r)
        self.assertEqual((r['llm']['exit'], r['llm']['billing'], r['llm']['receipt_path']), (4, 'pending', None))

    def test_no_delivery_does_not_write_candidate(self):
        for rc, stdout, why in ((3, '{}', 'unknown'), (2, '{}', 'invalid'),
                                (0, 'broken', 'invalid'), (4, '{"text":null}', 'invalid')):
            with self.subTest(rc=rc, stdout=stdout), mock.patch('aos7_author_llm.subprocess.run',
                    return_value=subprocess.CompletedProcess([], rc, stdout, '')):
                r = self.invoke()
                self.assertEqual(r['why'], why)
                self.assertFalse(Path(self.node, 'author/req/csv1/candidate.json').exists())

    def test_explicit_call_auto_and_three_layers(self):
        r = self.invoke(call='human-new-call', auto=True)
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['llm']['call_id'], 'human-new-call')
        self.start_daemon(register=['work'])
        job = Path(self.node, 'jobs', r['job'])
        self.wait_for(lambda: (json.loads((job / 'frame.json').read_bytes()).get('phase') == 'ended')
                      if (job / 'frame.json').exists() else False, timeout=30)
        self.assertTrue(author.answer(self.node, 'csv1')['ok'])
