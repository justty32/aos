"""依規格檢查 prompt 的黑箱行為。"""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
PACK = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACK), str(PACK.parents[1] / 'lib')]
from aos7_prompt import PromptError, expand_request, expand_text, located, render
def message(content, role='user'):
    return {'role': role, 'content': content}
class PromptTests(unittest.TestCase):
    """〔prompt〕隔離節點的渲染、折疊與命令列契約。"""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.node = Path(self.tmp.name) / 'node'
        shutil.copytree(PACK / 'examples/node', self.node)
    def write(self, name, value):
        path = self.node / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return path
    def prompt(self, content):
        return self.write('p.json', {'messages': [message(content)]})
    def cli(self, *args, env=None):
        return subprocess.run([str(PACK / 'bin/aos7-prompt'), *map(str, args)],
                              capture_output=True, timeout=30, env=env)
    def rendered(self, content, limit=0):
        return render(self.node, self.prompt(content), max_chars=limit)
    def test_examples(self):
        """四個範例成功、first 預設門檻就折疊週報，且 inbox 最後一則恰為檔名降序的最新五封。"""
        for name in ('first', 'entry', 'session', 'inbox'):
            with self.subTest(name=name):
                p = self.cli('render', self.node, 'prompts/' + name + '.json')
                self.assertEqual(p.returncode, 0, p.stderr)
                request = json.loads(p.stdout)
                self.assertEqual(set(request), {'litellm'})
                llm = request['litellm']
                self.assertEqual(set(llm), {'model', 'messages'})
                self.assertEqual(llm['model'], 'chatgpt-gpt-6-sol-high')
                self.assertIsInstance(llm['model'], str)
                self.assertTrue(llm['messages'])
                for msg in llm['messages']:
                    self.assertEqual(set(msg), {'role', 'content'})
                    self.assertIsInstance(msg['role'], str)
                    self.assertTrue(msg['role'])
                    self.assertIsInstance(msg['content'], str)
        _, receipt = render(self.node, 'prompts/first.json')
        self.assertEqual(len(receipt['folded']), 1)
        self.assertLess(receipt['tokens_est'] * 10, receipt['tokens_est_full'])
        llm = render(self.node, 'prompts/inbox.json')[0]['litellm']
        files = sorted((self.node / 'wf/inbox').glob('*.md'), reverse=True)[:5]
        self.assertEqual([f.stem.rsplit('-', 1)[1] for f in files],
                         ['note6', 'note5', 'note4', 'note3', 'note2'])
        expected = '最新 5 封信：\n\n' + '\n\n'.join(
            '### ' + f.name + '\n' + f.read_text(encoding='utf-8') for f in files)
        self.assertEqual(llm['messages'][-1]['content'], expected)
        self.assertNotIn('note1', llm['messages'][-1]['content'])
    def test_segments(self):
        """整檔、保留行尾的尾段與空信箱以雙換行相接。"""
        (self.node / 'lines').write_bytes(b'one\ntwo\nthree\n')
        (self.node / 'empty').mkdir()
        req, _ = self.rendered(['起', {'$opt': 'file', '$val': 'lines'},
                               {'$opt': 'tail', '$val': 'lines', 'n': 2},
                               {'$opt': 'latest', '$val': 'empty'}, '末'])
        self.assertEqual(req['litellm']['messages'][0]['content'],
                         '起\n\none\ntwo\nthree\n\n\ntwo\nthree\n\n\n\n\n末')
    def test_directives(self):
        """內容的三種取值指示詞與選項優先序有效。"""
        self.write('value.json', {'text': '引用'})
        (self.node / 'plain').write_text('選項', encoding='utf-8')
        with patch.dict(os.environ, {'AOS_PROMPT_TEST': '環境'}):
            req, _ = self.rendered([{'$fmt': {'$val': '${x}格式', 'x': '本地'}},
                                   {'$ref': 'value.json#/text'}, {'$env': 'AOS_PROMPT_TEST'},
                                   {'$opt': 'file', '$val': 'plain', '$ref': '不存在'}])
        self.assertEqual(req['litellm']['messages'][0]['content'],
                         '本地格式\n\n引用\n\n環境\n\n選項')
    def test_append(self):
        """另一文件的訊息接在原訊息後。"""
        self.write('other.json', [message('後')])
        path = self.write('p.json', {'messages': [message('前'),
                          {'$opt': 'append', '$val': {'$ref': 'other.json'}}]})
        req, _ = render(self.node, path)
        self.assertEqual(req['litellm']['messages'], [message('前'), message('後')])
    def test_clear(self):
        """清除選項丟掉所有先前訊息。"""
        path = self.write('p.json', {'messages': [message('前'), {'$opt': 'clear'}, message('後')]})
        self.assertEqual(render(self.node, path)[0]['litellm']['messages'], [message('後')])
    def test_cycles(self):
        """隔離取值器跨呼叫的循環保護，驗追加本身的鏈檢查。"""
        self.write('other.json', [{'$opt': 'append', '$val': {'$ref': 'p.json#/messages'}}])
        for msgs in ([{'$opt': 'append', '$val': {'$ref': 'other.json'}}],
                     [{'$opt': 'append', '$val': {'$ref': '#/messages'}}],
                     [message({'$ref': '#/messages/0/content'})]):
            with self.subTest(messages=msgs):
                path = self.write('p.json', {'messages': msgs})
                fresh = lambda v, ctx, pos: located(v, type(ctx)(ctx.doc, ctx.base_dir, ctx.env), pos)
                with patch("aos7_prompt.located", side_effect=fresh), self.assertRaises(PromptError) as caught:
                    render(self.node, path)
                self.assertEqual((caught.exception.outcome, caught.exception.code),
                                 ('unknown', 'ReferenceCycle'))
                self.assertIsInstance(caught.exception.why, str)
                self.assertTrue(caught.exception.why)
    def test_unknown_preserves_output(self):
        """讀檔、環境與 JSON 失敗不輸出請求也不覆寫檔案。"""
        env = dict(os.environ)
        env.pop('AOS_PROMPT_MISSING', None)
        self.write('broken.json', None).write_text('{', encoding='utf-8')
        cases = [{'messages': [message({'$opt': 'file', '$val': 'missing'})]},
                 {'messages': [message({'$env': 'AOS_PROMPT_MISSING'})]}, None]
        for value in cases:
            with self.subTest(value=value):
                path = self.write('p.json', value) if value is not None else self.node / 'broken.json'
                out = self.node / 'out.json'
                out.write_bytes(b'KEEP\n')
                p = self.cli('render', self.node, path, '--out', out, env=env)
                self.assertEqual(p.returncode, 3, p.stderr)
                self.assertEqual(out.read_bytes(), b'KEEP\n')
                self.assertEqual(p.stdout, b'')
                self.assertEqual(json.loads(p.stderr)['outcome'], 'unknown')
    def test_bad_inputs(self):
        """未知鍵、選項與錯誤訊息形狀退出二。"""
        cases = [{'messages': [message('好')], 'extra': 1},
                 {'messages': [message('好') | {'extra': 1}]},
                 {'messages': [message({'$opt': 'nope', '$val': 'x'})]},
                 {'messages': [message(42)]}, {'messages': [message('好', '')]},
                 {'messages': []}]
        for value in cases:
            with self.subTest(value=value):
                p = self.cli('render', self.node, self.write('p.json', value))
                self.assertEqual(p.returncode, 2, p.stderr)
                self.assertEqual(p.stdout, b'')
                self.assertEqual(json.loads(p.stderr)['outcome'], 'bad')
    def test_folding_receipt_and_reuse(self):
        """逐段折疊、完整回條與既有參照檔不重寫。"""
        text = '長文🙂\n' * 70
        req, receipt = self.rendered([text, '短', text], 50)
        sha = hashlib.sha256(text.encode()).hexdigest()
        folded = f'ref://{sha} 已折疊 {len(text)} 字，預覽：\n' + text[:200]
        content = folded + '\n\n短\n\n' + folded
        self.assertEqual(req['litellm']['messages'], [message(content)])
        ref = self.node / 'refs' / (sha + '.json')
        self.assertEqual(json.loads(ref.read_text(encoding='utf-8')),
                         {'v': 1, 'sha': sha, 'chars': len(text), 'text': text})
        full_chars = 2 * len(text) + 5
        expected = {'v': 1, 'outcome': 'rendered', 'messages': 1, 'chars': len(content),
                    'tokens_est': math.ceil(len(content) / 3), 'chars_full': full_chars,
                    'tokens_est_full': math.ceil(full_chars / 3), 'folded': [sha], 'out': None}
        self.assertEqual(receipt, expected)
        os.utime(ref, ns=(1234567890000000000, 1234567890000000000))
        stamp = ref.stat().st_mtime_ns
        self.assertEqual(self.rendered([text, '短', text], 50), (req, receipt))
        self.assertEqual(ref.stat().st_mtime_ns, stamp)
    def test_round_trip(self):
        """多訊息折疊可還原，CLI 原文位元組與請求展開相同。"""
        text = '繁體🙂\n' * 90
        path = self.write('p.json', {'messages': [message([text, '短']), message(text, 'system')]})
        req, receipt = render(self.node, path, max_chars=50)
        full = render(self.node, path, max_chars=0)[0]
        self.assertEqual(expand_request(self.node, req), full)
        self.assertEqual(expand_text(self.node, req['litellm']['messages'][0]['content']), text + '\n\n短')
        p = self.cli('expand', self.node, 'ref://' + receipt['folded'][0])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, text.encode('utf-8'))
        p = self.cli('expand', self.node, self.write('request.json', req))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout), full)
    def test_damaged_refs(self):
        """參照原文遭竄改或遺失都退出三；請求裡標頭的字數不符也是 unknown。"""
        req, receipt = self.rendered('原文' * 150, 50)
        sha = receipt['folded'][0]
        bad = req['litellm']['messages'][-1]['content'].replace(' 已折疊 300 字', ' 已折疊 301 字')
        with self.assertRaises(PromptError) as caught:
            expand_text(self.node, bad)
        self.assertEqual(caught.exception.outcome, 'unknown')
        ref = self.node / 'refs' / (sha + '.json')
        data = json.loads(ref.read_text(encoding='utf-8'))
        data['text'] = '竄改'
        ref.write_text(json.dumps(data), encoding='utf-8')
        for state in ('竄改', '遺失'):
            with self.subTest(state=state):
                if state == '遺失':
                    ref.unlink()
                p = self.cli('expand', self.node, 'ref://' + sha)
                self.assertEqual(p.returncode, 3, p.stderr)
                self.assertEqual(p.stdout, b'')
                self.assertEqual(json.loads(p.stderr)['outcome'], 'unknown')
    def test_no_recursive_expansion(self):
        """還原段內看似參照的文字保持原樣並繼續展開後段。"""
        text = '開頭 ref://' + 'a' * 64 + ' 已折疊 1 字，預覽：\nx' + '尾' * 250
        req, _ = self.rendered([text, '另' * 260], 50)
        full, _ = self.rendered([text, '另' * 260], 0)
        self.assertEqual(expand_request(self.node, req), full)
    def test_cli_streams(self):
        """請求與單行回條依輸出檔選項分流。"""
        path = self.prompt('你好')
        req, _ = render(self.node, path)
        p = self.cli('render', self.node, path)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, (json.dumps(req, ensure_ascii=False, indent=1) + '\n').encode())
        self.assertEqual(len(p.stderr.splitlines()), 1)
        self.assertEqual(json.loads(p.stderr)['out'], None)
        out = self.node / 'out.json'
        p = self.cli('render', self.node, path, '--out', out)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(out.read_text(encoding='utf-8')), req)
        self.assertEqual(len(p.stdout.splitlines()), 1)
        self.assertEqual(json.loads(p.stdout)['out'], str(out))
        self.assertEqual(p.stderr, b'')
    def test_ref_chars_and_preview(self):
        """原文正確仍須驗參照字數與請求中的完整預覽。"""
        req, receipt = self.rendered('原文🙂' * 150, 50)
        sha = receipt['folded'][0]
        ref = self.node / 'refs' / (sha + '.json')
        data = json.loads(ref.read_text(encoding='utf-8'))
        content = req['litellm']['messages'][0]['content']
        with self.assertRaises(PromptError) as caught:
            expand_text(self.node, content[:-1] + '改')
        self.assertEqual((caught.exception.outcome, caught.exception.code), ('unknown', 'RefMismatch'))
        data['chars'] += 1
        self.write('refs/' + ref.name, data)
        p = self.cli('expand', self.node, 'ref://' + sha)
        self.assertEqual(p.returncode, 3, p.stderr)
        self.assertEqual(json.loads(p.stderr)['code'], 'RefMismatch')
    def test_render_repairs_ref_metadata(self):
        """既有原文相同但字數壞掉或缺欄時必須重寫整份參照。"""
        text = '長文🙂' * 150
        req, receipt = self.rendered(text, 50)
        name = 'refs/' + receipt['folded'][0] + '.json'
        expected = json.loads((self.node / name).read_text(encoding='utf-8'))
        for chars in (1, None):
            with self.subTest(chars=chars):
                damaged = dict(expected)
                if chars is None:
                    del damaged['chars']
                else:
                    damaged['chars'] = chars
                self.write(name, damaged)
                self.assertEqual(self.rendered(text, 50), (req, receipt))
                self.assertEqual(json.loads((self.node / name).read_text(encoding='utf-8')), expected)
                self.assertEqual(expand_request(self.node, req)['litellm']['messages'], [message(text)])
    def test_out_inside_refs(self):
        """輸出不能佔用 refs；拒絕時不產檔。"""
        out = self.node / 'refs/x.json'
        p = self.cli('render', self.node, self.prompt('短'), '--out', out)
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertFalse(out.exists())
    def test_read_all_before_refs(self):
        """前段能折疊、後段讀取失敗時仍不產生 refs。"""
        (self.node / 'long').write_text('長' * 7000, encoding='utf-8')
        path = self.prompt([{'$opt': 'file', '$val': 'long'},
                            {'$opt': 'file', '$val': 'missing'}])
        p = self.cli('render', self.node, path)
        self.assertEqual(p.returncode, 3, p.stderr)
        self.assertFalse((self.node / 'refs').exists())
    def test_cli_value_invalid(self):
        """NUL 路徑與過長整數都給單行 bad/ValueInvalid 回條。"""
        path = self.prompt({'$opt': 'file', '$val': 'bad\x00path'})
        for value in ('nul', 'huge-int'):
            with self.subTest(value=value):
                if value == 'huge-int':
                    path.write_text('{"messages":[{"role":"user","content":"x"}],"max_chars":'
                                    + '9' * 5000 + '}', encoding='utf-8')
                p = self.cli('render', self.node, path)
                self.assertEqual(p.returncode, 2, p.stderr)
                self.assertEqual(len(p.stderr.splitlines()), 1)
                self.assertNotIn(b'Traceback', p.stderr)
                self.assertEqual((json.loads(p.stderr)['outcome'], json.loads(p.stderr)['code']),
                                 ('bad', 'ValueInvalid'))
    def test_expand_bad_shapes(self):
        """請求陣列、非字串模型與布林 role 都是 bad。"""
        for value in ([], {'litellm': {'model': 42, 'messages': [message('x')]}},
                      {'litellm': {'model': 'm', 'messages': [message('x', False)]}}):
            with self.subTest(value=value):
                p = self.cli('expand', self.node, self.write('request.json', value))
                self.assertEqual(p.returncode, 2, p.stderr)
                self.assertEqual(json.loads(p.stderr)['outcome'], 'bad')
