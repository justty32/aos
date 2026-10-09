"""用長回合與成長對照檢驗指示詞的內容預算。"""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
PACK = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACK), str(PACK.parents[1] / 'lib')]
from aos7_prompt import render
class PromptRoundsTests(unittest.TestCase):
    """〔prompt〕三百回合維持開放事項與頂層信件的有限視窗。"""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.node = Path(self.tmp.name) / 'node'
        shutil.copytree(PACK / 'examples/node', self.node)
    def curve(self, bounded):
        log = self.node / 'wf/SESSION-LOG.md'
        items = log.read_text(encoding='utf-8').splitlines()[2:]
        inbox = self.node / 'wf/inbox'
        (inbox / 'done').mkdir()
        prompt = self.node / 'prompts/session.json'
        if not bounded:
            data = json.loads(prompt.read_text(encoding='utf-8'))
            data['messages'][0]['content'][1] = {'$opt': 'file', '$val': 'wf/SESSION-LOG.md'}
            prompt.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            data = json.loads((self.node / 'prompts/inbox.json').read_text(encoding='utf-8'))
            data['max_chars'] = 0
            (self.node / 'prompts/inbox.json').write_text(json.dumps(data), encoding='utf-8')
        tokens = []
        for i in range(300):
            items.append(f'- [ ] 回合 {i:04d}：檢查待辦與回覆進度')
            if bounded:
                items = items[-4:]
            log.write_text('# SESSION-LOG（只列 open）\n\n' + '\n'.join(items) + '\n', encoding='utf-8')
            (inbox / f'2026-10-10-{i:06d}-note.md').write_text(
                f'寄件：worker\n主旨：回合 {i:04d}\n\n進度回報：照計畫進行，沒有卡點。\n', encoding='utf-8')
            for old in sorted(inbox.glob('*.md'))[:-8]:
                old.rename(inbox / 'done' / old.name)
            request, receipt = render(self.node, 'prompts/inbox.json')
            messages = request['litellm']['messages']
            self.assertEqual(receipt['chars'], sum(len(m['content']) for m in messages))
            if bounded:
                for recent in range(max(0, i - 4), i + 1):
                    self.assertIn(f'主旨：回合 {recent:04d}', messages[-1]['content'])
                if i >= 5:
                    self.assertNotIn(f'主旨：回合 {i - 5:04d}', messages[-1]['content'])
                self.assertIn(f'- [ ] 回合 {i:04d}：檢查待辦與回覆進度', messages[0]['content'])
            tokens.append(receipt['tokens_est'])
        return tokens
    def test_bounded_curve(self):
        """開放事項刪舊、信件歸檔後三百回合估值保持平坦。"""
        values = self.curve(True)
        self.assertLessEqual(max(values[-100:]), max(values[:100]) * 1.1)
        self.assertLessEqual(max(values) - min(values), sum(values[:20]) / 20 * 0.3)
    def test_growing_control(self):
        """整檔讀取只加不刪的日誌會持續增長超過兩倍。"""
        values = self.curve(False)
        self.assertTrue(all(b > a for a, b in zip(values, values[1:])), values)
        self.assertGreater(values[-1], values[0] * 2)
