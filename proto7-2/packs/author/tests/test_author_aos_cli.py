"""LLM 來源用本地 HTTP 走真 llmcall，不打真網路。"""
import argparse
import fcntl
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
from aos7_author_aos import prompt_request, main_aos, gates, learn
from aos7_fs import write_json

EXAMPLE = PACK / 'examples/csv-request'
AUTHOR = PACK / 'bin/aos7-author'
BUDGET = TOP / 'packs/budget/bin/aos7-budget'
MODEL = 'test/model'


USAGE = PACK / 'examples/aos-tool-usage'
DIAG = PACK / 'examples/aos-module-diag'
REQUEST = USAGE / 'request.json'


REPO = Path(subprocess.check_output(['git', '-C', str(PACK), 'rev-parse', '--show-toplevel']).decode().strip())
PREFIX = TOP.relative_to(REPO).as_posix()


def baseline_ref(root, repo=REPO):
    """以題目 root 首次加入前的版本，驗證新增包。"""
    path = '/'.join(part for part in (PREFIX, root) if part)
    git = ['git', '-C', str(repo)]
    if subprocess.run(git + ['cat-file', '-e', 'HEAD:' + path],
                      capture_output=True, check=False).returncode:
        return subprocess.check_output(git + ['rev-parse', 'HEAD']).decode().strip()
    commits = subprocess.check_output(git + ['log', '--diff-filter=A', '--format=%H',
                                              '--', path + '/README.md']).decode().splitlines()
    return subprocess.check_output(git + ['rev-parse', commits[-1] + '^']).decode().strip()


class TestAuthorAosCLI(DaemonCase):
    """〔author aos CLI〕本地 HTTP 真 llmcall、三關、重問與學習。"""
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
        self.review_content = '{"verdict":"accept","reasons":[]}'
        self.usage = {'prompt_tokens': 100, 'completion_tokens': 120, 'total_tokens': 220}
        case = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                case.bodies.append(body)
                content = case.review_content if '審查人' in body['messages'][0]['content'] else case.content
                reply = ({'choices': [{'message': {'content': content}, 'finish_reason': 'stop'}],
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

    def cli(self, *args):
        return subprocess.run([sys.executable, str(AUTHOR), *map(str, args)], cwd=self.node,
                              env=self.env, capture_output=True, text=True, timeout=120)

    def aos(self, *args, cmd='propose', req=REQUEST):
        return self.cli(cmd, req, '--ref',
                        baseline_ref('modules/llmdiag' if req == DIAG / 'request.json' else 'packs/usage'),
                        *args, '--no-scope')

    def checked(self, p, code=0):
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        return json.loads(p.stdout)

    def apprentice(self, *extra):
        self.content = (USAGE / 'valid.json').read_text()
        return self.aos('--llm', MODEL, '--budget', self.bd, *extra)

    def test_csv_unchanged_and_aos_flags_rejected(self):
        p = self.cli('propose', 'csv1', '--candidate', EXAMPLE / 'valid.json')
        out = self.checked(p)
        self.assertTrue(out['ok'])
        self.assertEqual(out['job'], 'csv1_32ac171d')
        self.assertNotIn('check', out)
        for flag, value in [('--review-llm', MODEL), ('--reviewer', 'rules'), ('--ref', 'HEAD')]:
            p = self.cli('propose', 'csv1', '--candidate', EXAMPLE / 'valid.json', flag, value)
            self.assertEqual(p.returncode, 2)
            self.assertTrue(p.stderr.startswith('aos7-author: '), p.stderr)

    def test_candidate_dispatch_and_bad_link(self):
        out = self.checked(self.aos('--candidate', USAGE / 'valid.json'))
        self.assertTrue(out['check']['ok'])
        self.assertIsNone(out['review'])
        self.checked(self.cli('--candidate', USAGE / 'valid.json', 'propose',
                              '--no-scope', '--ref', baseline_ref('packs/usage'), REQUEST))
        bad = self.checked(self.aos('--candidate', USAGE / 'bad-link.json'), 1)
        self.assertEqual(bad['why'], 'invalid')
        self.assertEqual(bad['check']['failed_gate'], 1)
        diag = self.checked(self.aos('--candidate', DIAG / 'valid.json', req=DIAG / 'request.json'))
        self.assertEqual(diag['kind'], 'aos-module')

    def test_apprentice_bytes_prompt_and_replay(self):
        out = self.checked(self.apprentice())
        info = out['llm']
        path = Path(self.node, 'author/aos/usage1', info['call_id'] + '.json')
        self.assertEqual(out['candidate_path'], str(path))
        self.assertEqual(path.read_bytes(), self.content.encode())
        self.assertEqual(out['candidate_sha'], hashlib.sha256(self.content.encode()).hexdigest())
        self.assertTrue(out['check']['ok'])
        self.assertEqual(info['used'], 220)
        self.assertTrue(Path(info['receipt_path']).is_file())
        self.assertEqual(json.loads(Path(info['receipt_path']).with_name('request.json').read_bytes())['logical'], 'author/usage1')
        body = self.bodies[0]
        self.assertNotIn('max_tokens', body)
        self.assertNotIn('temperature', body)
        user = json.loads(body['messages'][1]['content'])
        self.assertTrue(user['brief'].startswith('# 任務：'))
        self.assertEqual(user['context'], {})
        self.assert_no_answer_leak(body['messages'])
        self.assertEqual(user['toolcard']['root'], 'packs/usage')
        self.assertNotIn('request_fields', user['toolcard'])
        self.assertNotIn('note', user['toolcard'])
        again = self.checked(self.apprentice())
        self.assertEqual(len(self.bodies), 1)
        self.assertEqual(again, out)

    def test_review_llm_reject_and_accept(self):
        for verdict, code in [('reject', 1), ('accept', 0)]:
            self.review_content = json.dumps({'verdict': verdict, 'reasons': ['x']})
            # 明示新候選呼叫，審查模型也變更，讓每次審查是獨立請求。
            out = self.checked(self.apprentice('--call', verdict,
                               '--review-llm', 'review/' + verdict), code)
            self.assertTrue(out['rules_check']['ok'])
            self.assertEqual(out['check']['failed_gate'], 3 if code else None)
            path = Path(out['review']['path'])
            self.assertEqual(path.read_text(), self.review_content)
            self.assertTrue(out['review']['llm']['call_id'].startswith('rv-'))
            self.assertEqual(json.loads(Path(out['review']['llm']['receipt_path']).with_name('request.json').read_bytes())['logical'], 'author-review/usage1')
            body = self.bodies[-1]
            self.assertIn('審查人', body['messages'][0]['content'])
            user = json.loads(body['messages'][1]['content'])
            self.assertEqual(set(user['gates']), {'1', '2'})
            self.assertEqual(user['candidate'], self.content)

    def test_rules_stop_before_llm_review(self):
        out = self.checked(self.aos('--candidate', USAGE / 'bad-review.json',
                           '--review-llm', MODEL, '--budget', self.bd), 1)
        self.assertEqual(out['check']['failed_gate'], 3)
        self.assertEqual(self.bodies, [])

    def test_file_reviewer_and_astra_rejected(self):
        path = Path(self.node, 'review.json')
        path.write_text('{"verdict":"reject","reasons":["x"]}')
        out = self.checked(self.aos('--candidate', USAGE / 'valid.json', '--reviewer', 'file:' + str(path)), 1)
        self.assertTrue(out['rules_check']['ok'])
        self.assertEqual(out['check']['failed_gate'], 3)
        p = self.aos('--candidate', USAGE / 'valid.json', '--reviewer', 'astra')
        self.assertEqual(p.returncode, 2)
        self.assertTrue(p.stderr.startswith('aos7-author: '), p.stderr)

    def test_retry_gotchas_context_and_prompt_preview(self):
        gotchas = Path(self.node, 'GOTCHAS.md')
        gotchas.write_text('# 踩坑\n- 先看工具卡。\n')
        feedback = Path(self.node, 'feedback.json')
        failed = self.checked(self.aos('--candidate', USAGE / 'bad-link.json'), 1)
        feedback.write_text(json.dumps(failed))
        context = PACK / 'README.md'
        opts = ['--llm', MODEL, '--budget', self.bd, '--previous', USAGE / 'bad-link.json',
                '--feedback', feedback, '--gotchas', gotchas, '--context', context,
                '--context', gotchas]
        for name in ('one.json', 'two.json'):
            self.checked(self.aos(*opts, '--prompt-out', name))
        raw = Path(self.node, 'one.json').read_bytes()
        self.assertEqual(raw, Path(self.node, 'two.json').read_bytes())
        user = json.loads(json.loads(raw)['litellm']['messages'][1]['content'])
        self.assertEqual(user['previous_candidate'], (USAGE / 'bad-link.json').read_text())
        self.assertEqual(user['feedback'], {k: failed['check'][k] for k in ('failed_gate', 'gates')})
        self.assertEqual(user['gotchas'], gotchas.read_text())
        self.assertEqual(user['context']['packs/author/README.md'], context.read_text())
        self.assertEqual(user['context']['GOTCHAS.md'], gotchas.read_text())
        self.assertIn('上一份沒過', user['rules'])
        self.assertEqual(self.bodies, [])

    def test_publish_clone_head_unchanged(self):
        repo = Path(self.root, 'shared')
        source = subprocess.check_output(['git', '-C', str(PACK), 'rev-parse', '--show-toplevel']).decode().strip()
        subprocess.run(['git', 'clone', '-q', '--shared', '--no-checkout', source, str(repo)], check=True)
        head = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD']).decode().strip()
        opts = ['--candidate', USAGE / 'valid.json', '--reviewer', 'rules', '--repo', repo, '--ref', baseline_ref('packs/usage', repo)]
        out = self.checked(self.aos(*opts, cmd='publish'))
        self.assertTrue(out['branch'].startswith('apprentice/usage1_'))
        self.assertEqual(subprocess.check_output(['git', '-C', str(repo), 'rev-parse',
                                                out['branch'] + '^']).decode().strip(),
                         baseline_ref('packs/usage', repo))
        self.assertEqual(subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD']).decode().strip(), head)
        dup = self.checked(self.aos(*opts, cmd='publish'))
        self.assertTrue(dup['dup'])
        receipt = json.loads(Path(self.node, 'author/req/usage1/receipt.json').read_bytes())
        self.assertTrue(receipt['closed'])
        self.assertEqual(receipt['versions'][out['candidate_sha']]['commit'], out['commit'])
        subprocess.run(['git', '-C', str(repo), 'update-ref', 'refs/heads/' + out['branch'], head], check=True)
        self.assertEqual(self.checked(self.aos(*opts, cmd='publish'), 1)['why'], 'conflict')

    def test_learn_appends_and_rejects_bad_format(self):
        into = Path(self.node, 'GOTCHAS.md')
        initial = '# 踩坑\n- 原有條目。\n'
        into.write_text(initial)
        history = Path(self.node, 'history.json')
        failed = self.checked(self.aos('--candidate', USAGE / 'bad-link.json'), 1)
        history.write_text(json.dumps(failed))
        self.content = '- 相對連結從文件位置算。\n- 先跑測試再交付。'
        opts = ['--llm', MODEL, '--budget', self.bd, '--history', history, '--into', into]
        out = self.checked(self.aos(*opts, cmd='learn'))
        self.assertEqual(out['added'], self.content.splitlines())
        self.assertTrue(out['llm']['call_id'].startswith('ln-'))
        self.assertEqual(json.loads(Path(out['llm']['receipt_path']).with_name('request.json').read_bytes())['logical'], 'author-learn/usage1')
        self.assertEqual(into.read_text(), initial + '\n## usage1（test/model）\n' + self.content + '\n')
        user = json.loads(self.bodies[0]['messages'][1]['content'])
        self.assertEqual(user['existing'], initial)
        self.assertEqual(user['history'][0]['failed_gate'], 1)
        self.assertTrue(user['history'][0]['gates']['1']['issues'])
        before = into.read_bytes()
        self.content = '- 一條\n這行不合格'
        self.checked(self.aos(*opts, '--call', 'learn-bad', cmd='learn'), 1)
        self.assertEqual(into.read_bytes(), before)
        into_missing = Path(self.node, 'absent.md')
        self.checked(self.aos('--llm', MODEL, '--budget', self.bd, '--history', history,
                              '--into', into_missing, cmd='learn'), 2)
        self.assertFalse(into_missing.exists())

    def test_fences_and_failed_http_are_not_delivery(self):
        self.content = '```json\n' + (USAGE / 'valid.json').read_text() + '\n```'
        p = self.aos('--llm', MODEL, '--budget', self.bd, '--out', 'fenced.json')
        out = self.checked(p, 1)
        self.assertEqual(Path(out['candidate_path']).read_bytes(), self.content.encode())
        self.assertEqual(out['check']['failed_gate'], 1)
        self.code = 400
        out = self.checked(self.aos('--llm', MODEL, '--budget', self.bd, '--call', 'rejected', '--out', 'no.json'), 1)
        self.assertEqual(out['llm']['outcome'], 'rejected')
        self.assertFalse(Path(self.node, 'no.json').exists())

    def test_strict_dispatch_and_invalid_request(self):
        bad = Path(self.node, 'request.json')
        req = json.loads(REQUEST.read_bytes())
        req['work'] = []
        bad.write_text(json.dumps(req))
        out = self.checked(self.aos('--candidate', USAGE / 'valid.json', req=bad), 2)
        self.assertEqual(out['why'], 'invalid')
        bad.write_text('{"kind":"aos-tool","kind":"aos-tool"}')
        p = self.aos('--candidate', USAGE / 'valid.json', req=bad)
        self.assertEqual(p.returncode, 2)
        self.assertTrue(p.stderr.startswith('aos7-author: '), p.stderr)

    def assert_no_answer_leak(self, messages):
        source = (USAGE / 'check_answer.py').read_text()
        def check(value):
            if isinstance(value, str):
                self.assertNotIn(source, value)
            elif isinstance(value, dict):
                for item in value.values():
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)
        for message in messages:
            content = message['content']
            try:
                content = json.loads(content)
            except ValueError:
                pass
            check(content)

    def test_answer_leak_assertion_detects_context(self):
        raw = prompt_request(REQUEST, MODEL, [USAGE / 'check_answer.py'])
        messages = json.loads(raw)['litellm']['messages']
        with self.assertRaises(AssertionError):
            self.assert_no_answer_leak(messages)

    def test_csv_parser_abbreviations(self):
        preview = Path(self.node, 'csv-preview.json')
        out = self.checked(self.cli('propose', 'csv1', '--llm', MODEL,
                                   '--budget', self.bd, '--pr', preview))
        self.assertTrue(out['ok'])
        self.assertTrue(preview.is_file())
        self.assertEqual(self.cli('--h').returncode, 0)
        self.assertEqual(self.cli('learn', 'csv1').returncode, 2)

    def test_publish_review_llm_rejected(self):
        p = self.aos('--candidate', USAGE / 'bad-link.json', '--review-llm', MODEL,
                     '--budget', self.bd, cmd='publish')
        self.assertEqual(p.returncode, 2)
        self.assertTrue(p.stderr.startswith('aos7-author: '), p.stderr)
        self.assertEqual(self.bodies, [])

    def test_publish_file_accept_still_requires_rules(self):
        repo = Path(self.root, 'reject-repo')
        source = subprocess.check_output(['git', '-C', str(PACK), 'rev-parse', '--show-toplevel']).decode().strip()
        subprocess.run(['git', 'clone', '-q', '--shared', '--no-checkout', source, str(repo)], check=True)
        review = Path(self.node, 'accept.json')
        review.write_text(self.review_content)
        before = subprocess.check_output(['git', '-C', str(repo), 'show-ref'])
        out = self.checked(self.aos('--candidate', USAGE / 'bad-review.json',
                           '--reviewer', 'file:' + str(review), '--repo', repo, cmd='publish'), 1)
        self.assertEqual(out['failed_gate'], 3)
        self.assertEqual(out['why'], 'invalid')
        self.assertEqual(subprocess.check_output(['git', '-C', str(repo), 'show-ref']), before)

    def test_propose_snapshot_and_sha_mismatch(self):
        candidate = Path(self.node, 'mutable.json')
        data = (USAGE / 'valid.json').read_bytes()
        candidate.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        a = argparse.Namespace(arg=str(REQUEST), cmd='propose', candidate=str(candidate),
                               llm=None, reviewer='file:accept.json', review_llm=MODEL,
                               reserve=100, call=None)
        seen = []
        def checker(args, cmd, path, reviewer):
            seen.append(Path(path))
            self.assertEqual(Path(path).read_bytes(), data)
            candidate.write_bytes((USAGE / 'bad-review.json').read_bytes())
            return {'ok': True, 'candidate_sha': digest, 'gates': {'1': {}, '2': {}}}, None
        def review(*args, **kwargs):
            user = json.loads(json.loads(args[3])['litellm']['messages'][1]['content'])
            self.assertEqual(user['candidate'], data.decode())
            return self.review_content, {'call_id': 'rv-snapshot'}, None
        with mock.patch('aos7_author_aos.gates', side_effect=checker), mock.patch('aos7_author_aos.delivery', side_effect=review):
            out = main_aos(a)
        self.assertTrue(out['ok'], out)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0], seen[1])
        self.assertNotEqual(seen[0], candidate)
        self.assertFalse(seen[0].exists())
        a.review_llm = None
        for mismatch in (0, 1):
            results = [({'ok': True, 'candidate_sha': digest}, None) for _ in range(2)]
            results[mismatch] = ({'ok': True, 'candidate_sha': 'other'}, None)
            candidate.write_bytes(data)
            with mock.patch('aos7_author_aos.gates', side_effect=results):
                out = main_aos(a)
            self.assertFalse(out['ok'])
            self.assertEqual(out['why'], 'invalid')

    def test_learn_rechecks_under_lock_and_never_creates(self):
        into = Path(self.node, 'concurrent.md')
        a = argparse.Namespace(into=str(into), llm=MODEL, history=[])
        req = json.loads(REQUEST.read_bytes())
        for action in ('duplicate', 'delete'):
            into.write_text('# Original\n')
            def delivered(*args, **kwargs):
                if action == 'duplicate':
                    into.write_text('# Latest\n- 重複。\n')
                else:
                    into.unlink()
                return '- 重複。', {}, None
            locks = []
            real_lock = fcntl.flock
            def locked(fd, mode):
                locks.append(mode)
                return real_lock(fd, mode)
            with mock.patch('aos7_author_aos.delivery', side_effect=delivered), mock.patch('aos7_author_aos.fcntl.flock', side_effect=locked):
                out = learn(a, req, {'ok': False})
            self.assertEqual(out['why'], 'invalid')
            if action == 'duplicate':
                self.assertEqual(locks, [fcntl.LOCK_EX])
                self.assertEqual(into.read_text(), '# Latest\n- 重複。\n')
            else:
                self.assertFalse(into.exists())

    def test_checker_unknown_mapping(self):
        import argparse
        a = argparse.Namespace(arg=str(REQUEST), no_scope=True, repo=None, ref=baseline_ref('packs/usage'))
        with mock.patch('aos7_author_aos.subprocess.run', return_value=subprocess.CompletedProcess([], 4, b'{"ok":false,"unknown":"bwrap"}', b'')):
            out, why = gates(a, 'check', USAGE / 'valid.json', 'rules')
        self.assertEqual(why, 'unknown')
        self.assertFalse(out['ok'])
