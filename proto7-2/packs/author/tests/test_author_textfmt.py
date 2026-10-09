"""學徒文字候選：原文拆段、舊 JSON 相容與真正三關／CLI。"""
from argparse import Namespace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

PACK = Path(__file__).resolve().parents[1]
TOP = PACK.parents[1]
sys.path[:0] = [str(TOP / 'tests'), str(PACK)]
from base import CoreCase
from checkers import aos_three_gates as checker
import aos7_author_aos as apprentice
from aos7_author_aos import prompt_request

USAGE = PACK / 'examples/aos-tool-usage'
REQUEST = USAGE / 'request.json'
AUTHOR = PACK / 'bin/aos7-author'
GATES = PACK / 'bin/aos7-gates'
REF = '3c18d378064e39b9fdcc8f4b14be2aa9a47b1fe7'
MODEL = 'test/model'


def example_candidate():
    candidate = json.loads((USAGE / 'valid.json').read_bytes())
    # 原範例 report 沒有最後換行；先按文字格式契約補齊，再比較兩種格式。
    candidate['report'] = candidate['report'].rstrip('\n') + '\n'
    return candidate


def text_candidate(candidate):
    parts = [f'=== {path} ===\n{content}' for path, content in candidate['files'].items()]
    return (''.join(parts) + '=== row ===\n' + candidate['row'] + '\n' +
            '=== report ===\n' + candidate['report']).encode('utf-8')


class TestCandidateTextParse(unittest.TestCase):
    """拆段不改檔案全文，保留段才做規定的空白整理。"""
    def setUp(self):
        self.req, self.card = checker.request(REQUEST)

    def test_json_with_leading_whitespace_and_same_candidate(self):
        original = json.loads((USAGE / 'valid.json').read_bytes())
        parsed_original, _ = checker.parse_candidate((USAGE / 'valid.json').read_bytes(), self.req)
        self.assertEqual(parsed_original, original)
        parsed_text, _ = checker.parse_candidate(text_candidate(original), self.req)
        self.assertEqual(parsed_text['report'], original['report'] + '\n')
        candidate = example_candidate()
        json_value, json_fmt = checker.parse_candidate(
            b' \t\r\n' + json.dumps(candidate, ensure_ascii=False).encode(), self.req)
        text_value, text_fmt = checker.parse_candidate(text_candidate(candidate), self.req)
        self.assertEqual((json_fmt, text_fmt), ('json', 'text'))
        self.assertEqual(json_value, text_value)
        for field in ('files', 'row', 'report'):
            self.assertEqual(json_value[field], candidate[field])

    def test_files_keep_exact_text_and_reserved_sections_trim(self):
        content = '  首行\r\n\n不是段頭 === x ===\n=== 含 空白 ===\n末行\n\n'
        data = (' \t\n=== packs/usage/README.md ===\n' + content +
                '=== row ===\n \t| 索引 | \n\n=== report ===\n# REPORT\n正文  \n \t\n\n').encode()
        candidate, fmt = checker.parse_candidate(data, self.req)
        self.assertEqual(fmt, 'text')
        self.assertEqual(candidate['files'], {'packs/usage/README.md': content})
        self.assertEqual(candidate['row'], '| 索引 |')
        self.assertEqual(candidate['report'], '# REPORT\n正文  \n')
        self.assertEqual({k: candidate[k] for k in ('v', 'rid', 'kind', 'name')},
                         {k: self.req[k] for k in ('v', 'rid', 'kind', 'name')})

    def test_last_file_without_newline_stays_without_newline(self):
        data = b'=== row ===\nrow\n=== report ===\nreport\n=== packs/usage/end ===\nlast'
        candidate, _ = checker.parse_candidate(data, self.req)
        self.assertEqual(candidate['files']['packs/usage/end'], 'last')
        self.assertEqual(candidate['report'], 'report\n')

    def test_preamble_rejected_with_opening_and_hint(self):
        for opening in ('先說明一下', '```text'):
            with self.subTest(opening=opening), self.assertRaises(ValueError) as caught:
                checker.parse_candidate((opening + '\n=== row ===\nx\n').encode(), self.req)
            self.assertIn(opening, str(caught.exception))
            self.assertIn('文字候選要從 `=== 路徑 ===` 開始，不加說明、不加 Markdown 圍欄',
                          str(caught.exception))

    def test_duplicate_names_rejected_including_reserved(self):
        for name in ('packs/usage/README.md', 'row', 'report'):
            with self.subTest(name=name), self.assertRaises(ValueError) as caught:
                checker.parse_candidate(f'=== {name} ===\na\n=== {name} ===\nb\n'.encode(), self.req)
            self.assertIn(name, str(caught.exception))

    def test_no_header_rejected(self):
        for data in (b'', b' \t\r\n', b'=== bad name ===\nx', b'plain text'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                checker.parse_candidate(data, self.req)

    def test_missing_reserved_sections_use_text_schema(self):
        candidate = example_candidate()
        for field in ('row', 'report'):
            # 刪除保留段，仍由第一關 schema 呈現缺段；不需要 materialize。
            text = text_candidate(candidate).decode()
            start = text.index('=== ' + field + ' ===\n')
            end = text.find('=== ', start + 1)
            text = text[:start] + (text[end:] if end >= 0 else '')
            parsed, fmt = checker.parse_candidate(text.encode(), self.req)
            out = checker.gate_static({'candidate': parsed, 'card': self.card,
                                       'request': self.req, 'fmt': fmt})
            self.assertFalse(out['ok'])
            issue = out['issues'][0]
            self.assertEqual(issue['rule'], 'schema')
            self.assertIn(f'缺 `=== {field} ===` 段', issue['why'])
            self.assertNotIn('欄', issue['why'])
            self.assertNotIn('頂層 report 字串', issue['why'])

    def test_text_prompt_and_default_json_bytes(self):
        original = prompt_request(REQUEST, MODEL)
        self.assertEqual(original, prompt_request(REQUEST, MODEL, fmt='json'))
        self.assertEqual(hashlib.sha256(original).hexdigest(),
                         'd09ce34ba8cf7a86c9979cdddecc85da111ff2dad1c35c14dc82e52aa257e359')
        messages = json.loads(prompt_request(REQUEST, MODEL, fmt='text'))['litellm']['messages']
        self.assertIn('多檔文字', messages[0]['content'])
        self.assertIn('不加 Markdown 圍欄', messages[0]['content'])
        user = json.loads(messages[1]['content'])
        self.assertNotIn('candidate_schema', user)
        self.assertIsInstance(user['candidate_format'], str)
        for text in ('=== packs/usage/README.md ===', '=== row ===', '=== report ==='):
            self.assertIn(text, user['candidate_format'])
        self.assertIn('全份候選 ≤65536 bytes', user['rules'])
        self.assertNotIn('全份候選 JSON ≤65536 bytes', user['rules'])


class TestCandidateTextGates(unittest.TestCase):
    """用原範例轉成文字，三關實跑一次。"""
    def test_text_candidate_passes_all_gates_with_raw_sha(self):
        data = text_candidate(example_candidate())
        with tempfile.TemporaryDirectory(prefix='author-text-') as tmp:
            path = Path(tmp, 'candidate.txt')
            path.write_bytes(data)
            p = subprocess.run([sys.executable, str(GATES), 'check', str(REQUEST), str(path),
                                '--reviewer', 'rules', '--no-scope', '--ref', REF],
                               capture_output=True, text=True, timeout=180)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        out = json.loads(p.stdout)
        self.assertTrue(out['ok'], out)
        self.assertIsNone(out['failed_gate'])
        self.assertEqual(out['candidate_sha'], hashlib.sha256(data).hexdigest())
        for gate in ('1', '2', '3'):
            self.assertTrue(out['gates'][gate]['ok'], out)

    def test_parse_errors_keep_json_exit_code_and_text_rule(self):
        with tempfile.TemporaryDirectory(prefix='author-text-bad-') as tmp:
            path = Path(tmp, 'candidate.txt')
            for data, rule in ((b'{broken', 'json'), (b'```text\n=== row ===\nx\n', 'text'),
                               (b'=== row ===\nx\n=== row ===\ny', 'text')):
                path.write_bytes(data)
                p = subprocess.run([sys.executable, str(GATES), 'check', str(REQUEST), str(path),
                                    '--reviewer', 'rules', '--no-scope', '--ref', REF],
                                   capture_output=True, text=True, timeout=15)
                with self.subTest(data=data):
                    self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                    self.assertEqual(json.loads(p.stdout)['gates']['1']['issues'][0]['rule'], rule)


class TestAuthorTextCLI(CoreCase):
    """只交本機候選，免起 HTTP 與 LLM 帳本。"""
    def setUp(self):
        super().setUp()
        self.node = self.mknode('work')
        self.candidate = Path(self.node, 'candidate.txt')
        self.candidate.write_bytes(text_candidate(example_candidate()))

    def cli(self, *args):
        return subprocess.run([sys.executable, str(AUTHOR), *map(str, args)], cwd=self.node,
                              capture_output=True, text=True, timeout=180)

    def test_propose_accepts_text_candidate(self):
        p = self.cli('propose', REQUEST, '--format', 'text', '--candidate', self.candidate,
                     '--reviewer', 'rules', '--no-scope', '--ref', REF)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        out = json.loads(p.stdout)
        self.assertTrue(out['ok'], out)
        self.assertTrue(out['check']['ok'], out)
        self.assertEqual(out['candidate_sha'], hashlib.sha256(self.candidate.read_bytes()).hexdigest())

    def test_format_is_rejected_outside_propose_even_for_json(self):
        for cmd in ('publish', 'learn'):
            for fmt in ('text', 'json'):
                with self.subTest(cmd=cmd, fmt=fmt):
                    p = self.cli(cmd, REQUEST, '--format', fmt)
                    self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                    self.assertIn('--format', p.stderr)

    def test_llm_text_uses_txt_and_keeps_previous_original(self):
        a = Namespace(arg=str(REQUEST), cmd='propose', llm=MODEL, format='text',
                      candidate=None, context=(), gotchas=None, previous=str(self.candidate),
                      feedback={'failed_gate': 1, 'gates': {}}, call='text-test', reserve=1000000, prompt_out=None,
                      out=None, reviewer='rules', review_llm=None)
        req, _ = checker.request(REQUEST)
        data = self.candidate.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        info = {'call_id': 'text-test', 'outcome': 'answered'}
        check = {'ok': True, 'candidate_sha': digest}
        with mock.patch.object(apprentice, 'delivery', return_value=(data.decode(), info, None)) as delivery, \
                mock.patch.object(apprentice, 'gates', return_value=(check, None)), \
                mock.patch.object(Path, 'cwd', return_value=Path(self.node)):
            out = apprentice.propose_one(a, req, {'ok': False, 'why': None})
        self.assertTrue(out['ok'], out)
        path = Path(self.node, 'author/aos/usage1/text-test.txt')
        self.assertEqual(out['candidate_path'], str(path))
        self.assertEqual(path.read_bytes(), data)
        raw = delivery.call_args.args[3]
        user = json.loads(json.loads(raw)['litellm']['messages'][1]['content'])
        self.assertEqual(user['previous_candidate'], data.decode())
        self.assertIn('candidate_format', user)

    def test_upgrade_ladder_keeps_text_format(self):
        a = Namespace(arg=str(REQUEST), cmd='propose', llm=apprentice.AUTO, format='text',
                      previous=None, feedback=None, out=None, call=None)
        attempts = []
        def proposed(options, req, out):
            attempts.append(options.format)
            if len(attempts) == 1:
                return dict(out, why='invalid', llm={'outcome': 'answered'},
                            check={'_rejected': True})
            return dict(out, ok=True, why=None, llm={'outcome': 'answered'}, check={'ok': True})
        with mock.patch.object(apprentice, 'propose_one', side_effect=proposed):
            out = apprentice.main_aos(a)
        self.assertTrue(out['ok'], out)
        self.assertEqual(attempts, ['text', 'text'])
