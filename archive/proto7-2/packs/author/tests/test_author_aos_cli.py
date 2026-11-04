"""LLM 來源用本地 HTTP 走真 llmcall，不打真網路。"""
import argparse
from contextlib import redirect_stderr, redirect_stdout
import fcntl
import hashlib
import io
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
            self.assertIn('不是退件理由', user['rules'])   # 極端邊角只當建議（S3b）

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

    def skill_book(self, trigger='aos-tool'):
        return ('---\nname: apprentice\ndescription: 寫工具前用\ntriggers: ' + trigger +
                '\n---\n## 踩過的坑\n- 匯入失敗→先設定路徑。\n## 驗過的骨架\n```python\nimport sys\n```\n')

    def skill_node(self, text=None):
        node = Path(self.root, 'books')
        book = node / 'skills/apprentice/SKILL.md'
        book.parent.mkdir(parents=True, exist_ok=True)
        book.write_text(self.skill_book() if text is None else text, encoding='utf-8')
        return node, book

    def skill_learn(self, node, *extra):
        history = Path(self.node, 'skill-history.json')
        history.write_text('{"failed_gate":1,"gates":{"1":{"issues":["缺必要檔"]}}}')
        return self.aos('--llm', MODEL, '--budget', self.bd, '--history', history,
                        '--skill-into', node, '--skill', 'apprentice', *extra, cmd='learn')

    def test_skills_picked_and_prompt_preview(self):
        node, book = self.skill_node()
        out = self.checked(self.apprentice('--skills', node))
        self.assertEqual(out['skill']['picked'], 'apprentice')
        user = json.loads(self.bodies[0]['messages'][1]['content'])
        self.assertEqual(user['skill'], {'name': 'apprentice', 'text': book.read_text()})
        self.assertIn('與需求衝突時以需求為準', user['rules'])
        self.checked(self.apprentice('--skills', node, '--prompt-out', 'skill-preview.json'))
        raw = Path(self.node, 'skill-preview.json').read_bytes()
        self.assertEqual(json.loads(json.loads(raw)['litellm']['messages'][1]['content']), user)

    def test_skills_none_preserves_prompt_bytes(self):
        node, _ = self.skill_node(self.skill_book('不會命中'))
        out = self.checked(self.apprentice('--skills', node, '--prompt-out', 'none.json'))
        self.assertIsNone(out['skill']['picked'])
        self.assertNotIn('skill', self.checked(self.apprentice('--prompt-out', 'plain.json')))
        self.assertEqual(Path(self.node, 'none.json').read_bytes(), Path(self.node, 'plain.json').read_bytes())
        self.assertEqual(Path(self.node, 'plain.json').read_bytes(), prompt_request(REQUEST, MODEL))

    def test_prompt_bytes_match_before_skills_commit(self):
        # git show 0800082f^:proto7-2/packs/author/aos7_author_aos.py
        # 的 prompt_request(REQUEST, MODEL)：5203 bytes。
        self.assertEqual(hashlib.sha256(prompt_request(REQUEST, MODEL)).hexdigest(),
                         'd09ce34ba8cf7a86c9979cdddecc85da111ff2dad1c35c14dc82e52aa257e359')

    def test_skills_bad_node_stops_before_writes(self):
        out = self.checked(self.apprentice('--skills', Path(self.root, 'absent'),
                           '--prompt-out', 'must-not-exist.json'), 2)
        self.assertEqual(out['why'], 'invalid')
        self.assertFalse(Path(self.node, 'must-not-exist.json').exists())
        self.assertEqual(self.bodies, [])
        self.assertEqual(self.cli('propose', 'csv1', '--candidate', EXAMPLE / 'valid.json',
                                  '--skills', self.root).returncode, 2)

    def test_skills_exit_mapping_and_question(self):
        a = argparse.Namespace(arg=str(REQUEST), cmd='propose', llm=MODEL, skills='bad-node')
        req = json.loads(REQUEST.read_bytes())
        for code, why in ((2, 'invalid'), (3, 'unknown'), (9, 'unknown')):
            with mock.patch('aos7_author_aos.subprocess.run', return_value=
                            subprocess.CompletedProcess([], code, '', '挑選失敗')) as run:
                out = main_aos(a)
            self.assertEqual(out['why'], why)
            self.assertFalse(out['ok'])
            self.assertEqual(run.call_args.args[0], ['python3', str(TOP / 'modules/skills/aos7-skills'),
                             'pick', 'bad-node', ' '.join(req[k] for k in ('kind', 'name', 'task', 'goal'))])
            self.assertEqual(run.call_count, 1)

    def test_skills_oversize_preserves_prompt(self):
        node, _ = self.skill_node(self.skill_book() + '大' * 3000)
        out = self.checked(self.apprentice('--skills', node, '--prompt-out', 'large.json'))
        self.assertIsNone(out['skill']['picked'])
        self.assertIn('8192', out['skill']['why'])
        self.assertEqual(Path(self.node, 'large.json').read_bytes(), prompt_request(REQUEST, MODEL))

    def test_skill_learn_replaces_and_includes_candidate(self):
        node, book = self.skill_node()
        existing = book.read_text()
        candidate = Path(self.node, 'source.txt')
        candidate.write_text('骨' * 25000)
        self.content = self.skill_book() + '\n改寫後的內容\n'
        out = self.checked(self.skill_learn(node, '--candidate', candidate))
        self.assertEqual((out['skill'], out['into'], out['bytes']),
                         ('apprentice', str(book), len(self.content.encode())))
        self.assertEqual(book.read_text(), self.content)
        self.assertEqual(out['why'], None)
        self.assertTrue(out['llm']['call_id'].startswith('ln-'))
        receipt = Path(out['llm']['receipt_path']).with_name('request.json')
        self.assertEqual(json.loads(receipt.read_bytes())['logical'], 'author-learn/usage1')
        user = json.loads(self.bodies[0]['messages'][1]['content'])
        self.assertEqual(user['existing'], existing)
        self.assertEqual(user['candidate'], '骨' * 24000)
        self.assertEqual(user['history'][0]['failed_gate'], 1)
        self.assertIn('整本 SKILL.md', self.bodies[0]['messages'][0]['content'])
        self.assertTrue((book.parent / '.lock').is_file())
        self.assertEqual(list(book.parent.glob('.SKILL-*')), [])

    def test_skill_learn_creates_missing_book(self):
        node = Path(self.root, 'new-books')
        node.mkdir()
        self.content = self.skill_book()
        self.checked(self.skill_learn(node))
        self.assertEqual((node / 'skills/apprentice/SKILL.md').read_text(), self.content)
        user = json.loads(self.bodies[0]['messages'][1]['content'])
        self.assertEqual(user['existing'], '')
        self.assertNotIn('candidate', user)

    def skill_learn_in_process(self, node, *extra):
        history = Path(self.node, 'skill-history.json')
        history.write_text('{"gates":{}}')
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = author.main(['learn', str(REQUEST), '--llm', MODEL,
                                '--budget', str(self.bd), '--history', str(history),
                                '--skill-into', str(node), '--skill', 'apprentice', *map(str, extra)])
        return self.checked(subprocess.CompletedProcess([], code, stdout.getvalue(), stderr.getvalue()), code), code

    def test_skill_learn_index_exit_mapping_preserves_receipt(self):
        node, book = self.skill_node()
        before = book.read_bytes()
        info = {'call_id': 'ln-test', 'exit': 0, 'outcome': 'answered', 'used': 220}
        for status, why, code in ((1, 'invalid', 1), (3, 'unknown', 3),
                                  (-9, 'unknown', 3), (2, 'unknown', 3), (9, 'unknown', 3)):
            with self.subTest(status=status), mock.patch('aos7_author_aos.delivery',
                    return_value=(self.skill_book(), info, None)), mock.patch(
                    'aos7_author_aos.subprocess.run', return_value=
                    subprocess.CompletedProcess([], status, b'', b'index failed')):
                out, actual = self.skill_learn_in_process(node)
            self.assertEqual(actual, code)
            self.assertEqual(out['why'], why)
            self.assertEqual(out['llm'], info)
            self.assertIn('index failed', out['error'])
            self.assertEqual(book.read_bytes(), before)

    def test_skill_learn_candidate_path_invalid_before_model(self):
        node, book = self.skill_node()
        before = book.read_bytes()
        for candidate in (Path(self.node, 'missing.json'), Path(self.node)):
            out = self.checked(self.skill_learn(node, '--candidate', candidate), 2)
            self.assertEqual(out['why'], 'invalid')
            self.assertEqual(book.read_bytes(), before)
        self.assertEqual(self.bodies, [])

    def test_skill_learn_candidate_io_fault_before_model(self):
        node, book = self.skill_node()
        candidate = Path(self.node, 'unreadable.json')
        candidate.write_text('{}')
        before = book.read_bytes()
        read_text = Path.read_text
        def read(path, *args, **kwargs):
            if path == candidate:
                raise PermissionError('candidate read denied')
            return read_text(path, *args, **kwargs)
        with mock.patch.object(Path, 'read_text', read), mock.patch('aos7_author_aos.delivery') as delivery:
            out, code = self.skill_learn_in_process(node, '--candidate', candidate)
        self.assertEqual(code, 3)
        self.assertEqual(out['why'], 'unknown')
        self.assertIn('candidate read denied', out['error'])
        delivery.assert_not_called()
        self.assertEqual(book.read_bytes(), before)
        self.assertEqual(self.bodies, [])

    def test_old_learn_candidate_rejected_before_model(self):
        into = Path(self.node, 'GOTCHAS.md')
        into.write_text('# 踩坑\n')
        history = Path(self.node, 'history.json')
        history.write_text('{"gates":{}}')
        p = self.aos('--llm', MODEL, '--budget', self.bd, '--history', history,
                     '--into', into, '--candidate', USAGE / 'valid.json', cmd='learn')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual(into.read_text(), '# 踩坑\n')
        self.assertEqual(self.bodies, [])

    def test_skill_learn_interleaved_writers_conflict(self):
        for initially_present in (True, False):
            with self.subTest(initially_present=initially_present):
                node, book = self.skill_node()
                if not initially_present:
                    book.unlink()
                started, release = threading.Event(), threading.Event()
                results = {}
                winner = self.skill_book() + '\n第二個寫者的新知\n'
                def deliver(*args, **kwargs):
                    user = json.loads(json.loads(args[3])['litellm']['messages'][1]['content'])
                    self.assertEqual(user['existing'], self.skill_book() if initially_present else '')
                    if threading.current_thread().name == 'first-learner':
                        started.set()
                        if not release.wait(10):
                            raise RuntimeError('second writer did not finish')
                        return self.skill_book() + '\n第一個寫者的新知\n', {'call_id': 'first'}, None
                    return winner, {'call_id': 'second'}, None
                a = argparse.Namespace(arg=str(REQUEST), cmd='learn', llm=MODEL,
                                       skill_into=str(node), skill='apprentice', history=[], candidate=None)
                def first():
                    results['first'] = main_aos(a)
                with mock.patch('aos7_author_aos.delivery', side_effect=deliver):
                    thread = threading.Thread(target=first, name='first-learner')
                    thread.start()
                    try:
                        self.assertTrue(started.wait(10))
                        results['second'] = main_aos(a)
                    finally:
                        release.set()
                        thread.join(10)
                self.assertFalse(thread.is_alive())
                self.assertTrue(results['second']['ok'], results)
                out = results['first']
                self.assertFalse(out['ok'])
                self.assertEqual(out['why'], 'conflict')
                self.assertEqual(out['error'], '技能書在學習期間被改過，重跑 learn')
                self.assertEqual(out['llm'], {'call_id': 'first'})
                self.assertEqual(book.read_text(), winner)
                with mock.patch('aos7_author_aos.main_aos', return_value=out):
                    result, code = self.skill_learn_in_process(node)
                self.assertEqual(code, 1)
                self.assertEqual(result['why'], 'conflict')
                self.assertEqual(list(book.parent.glob('.SKILL-*')), [])

    def test_skill_learn_invalid_never_replaces(self):
        node, book = self.skill_node()
        before = book.read_bytes()
        for i, text in enumerate(['沒有 frontmatter', self.skill_book('aos-module'),
                                  self.skill_book() + '大' * 3000]):
            self.content = text
            out = self.checked(self.skill_learn(node, '--call', 'bad-skill-' + str(i)), 1)
            self.assertEqual(out['why'], 'invalid')
            self.assertEqual(book.read_bytes(), before)
        self.content = self.skill_book('aos-module')
        self.assertIn('triggers', json.loads(self.skill_learn(node, '--call', 'bad-trigger').stdout)['error'])

    def test_skill_learn_argument_exclusion_and_bad_node(self):
        node, book = self.skill_node()
        self.assertEqual(self.skill_learn(node, '--into', book).returncode, 2)
        self.assertEqual(self.skill_learn(node, '--skill', 'Bad_Name').returncode, 2)
        for bad in (Path(self.root, 'absent'), book):
            out = self.checked(self.skill_learn(bad), 2)
            self.assertEqual(out['why'], 'invalid')
        self.assertEqual(self.bodies, [])

    def test_gate_schema_explains_all_fields(self):
        c = json.loads((USAGE / 'valid.json').read_bytes())
        c['files']['REPORT.md'] = c.pop('report')
        c.update(v=True, rid='bad', kind='bad', name='bad', row=0, extra=1)
        candidate = Path(self.node, 'bad-schema.json')
        candidate.write_text(json.dumps(c))
        out = self.checked(self.aos('--candidate', candidate), 1)
        issue = out['check']['gates']['1']['issues'][0]
        self.assertEqual(issue['rule'], 'schema')
        for phrase in ('缺 report 欄', 'REPORT 要寫在頂層 report 字串', '多 extra 欄',
                       'v 必須是整數 1', 'rid 應為 usage1', 'kind 應為 aos-tool', 'name 應為 usage', 'row 必須是字串'):
            self.assertIn(phrase, issue['why'])
        c.update(files=[], report='無章節', row='')
        candidate.write_text(json.dumps(c))
        out = self.checked(self.aos('--candidate', candidate), 1)
        why = out['check']['gates']['1']['issues'][0]['why']
        self.assertIn('files 必須是「路徑→字串」物件', why)
        self.assertIn('report 缺「以後交接書該點名的工具」一節', why)

    def test_gate_extra_data_and_index_hint(self):
        candidate = Path(self.node, 'extra.json')
        raw = (USAGE / 'valid.json').read_text() + '\n' + '{"extra":true}'
        candidate.write_text(raw)
        out = self.checked(self.aos('--candidate', candidate), 2)
        why = out['check']['gates']['1']['issues'][0]['why']
        self.assertIn('候選必須恰好是一個 JSON 物件', why)
        self.assertIn(f'第 {raw.index(chr(123) + chr(34) + "extra") + 1} 字元', why)
        self.assertIn('『{"extra":true}』', why)
        c = json.loads((USAGE / 'valid.json').read_bytes())
        c['files']['INDEX.md'] = '| 索引 |'
        candidate.write_text(json.dumps(c))
        out = self.checked(self.aos('--candidate', candidate), 1)
        issues = out['check']['gates']['1']['issues']
        self.assertTrue(any(i['rule'] == 'territory' and '索引列寫在頂層 row 欄，不放 files' in i['why'] for i in issues))

    def test_gate_layout_tests_readme_name_the_file(self):
        c = json.loads((USAGE / 'valid.json').read_bytes())
        c['files'] = {k: v for k, v in c['files'].items() if '/tests/' not in k and not k.endswith('aos7_usage.py')}
        c['files']['packs/usage/README.md'] = '# usage\n'
        c['files']['packs/usage/bin/aos7-usage'] += '\n' * 20
        candidate = Path(self.node, 'layout.json')
        candidate.write_text(json.dumps(c))
        out = self.checked(self.aos('--candidate', candidate), 1)
        whys = {i['rule']: i['why'] for i in out['check']['gates']['1']['issues'] if i['rule'] != 'layout'}
        layout = [i['why'] for i in out['check']['gates']['1']['issues'] if i['rule'] == 'layout']
        self.assertIn('缺必要檔：packs/usage/aos7_usage.py', layout[0])
        self.assertIn('入口 packs/usage/bin/aos7-usage 超過 12 行', layout[1])
        self.assertIn('缺測試（要有 packs/usage/tests/test_*.py）', whys['tests'])
        self.assertIn('packs/usage/README.md 缺指定章節', whys['readme'])

    def test_checker_unknown_mapping(self):
        import argparse
        a = argparse.Namespace(arg=str(REQUEST), no_scope=True, repo=None, ref=baseline_ref('packs/usage'))
        with mock.patch('aos7_author_aos.subprocess.run', return_value=subprocess.CompletedProcess([], 4, b'{"ok":false,"unknown":"bwrap"}', b'')):
            out, why = gates(a, 'check', USAGE / 'valid.json', 'rules')
        self.assertEqual(why, 'unknown')
        self.assertFalse(out['ok'])
