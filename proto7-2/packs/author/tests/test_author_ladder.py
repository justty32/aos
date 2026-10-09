"""--llm 不給模型＝先便宜後升級：被拒才換下一級，每級模型記進回覆的 rounds。本地 HTTP 走真 llmcall。"""
import json
from pathlib import Path
import sys

PACK = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACK.parents[1] / 'tests'), str(PACK), str(PACK / 'tests')]
import test_author_llm as csv_case
import test_author_aos_cli as aos_case
from aos7_author_llm import LADDER

CSV = PACK / 'examples/csv-request'
USAGE = PACK / 'examples/aos-tool-usage'


class Replies:
    """依請求的模型給回覆；沒列的模型回預設（合法候選）。"""
    replies = {}

    @property
    def content(self):
        return self.replies.get(self.bodies[-1]['model'], self.default) if self.bodies else self.default

    @content.setter
    def content(self, value):
        self.default = value

    def models(self):
        return [b['model'] for b in self.bodies]


def own_tests_only(cls):
    """借用既有案的 setUp（本地 HTTP＋budget），不重跑它的測試。"""
    for name in dir(cls):
        if name.startswith('test') and name not in cls.__dict__:
            setattr(cls, name, None)
    return cls


@own_tests_only
class TestLadderCSV(Replies, csv_case.TestAuthorLLM):
    """〔author 升級鏈〕CSV：luna-nothink 先答，被拒才 sol-high、再 astra-high。"""

    def propose(self, *extra, code=0):
        p = self.cli('propose', 'csv1', '--llm', '--budget', '../llm/budget/llm', *extra)
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        return json.loads(p.stdout)

    def test_cheap_model_first(self):
        out = self.propose()
        self.assertTrue(out['ok'])
        self.assertEqual(self.models(), [LADDER[0]])
        self.assertEqual([r['model'] for r in out['rounds']], [LADDER[0]])
        self.assertEqual(out['rounds'][0]['usage'], self.usage)
        self.assertEqual(out['llm']['model'], LADDER[0])

    def test_rejected_climbs_in_order(self):
        bad = (CSV / 'bad-params.json').read_text()
        self.replies = {LADDER[0]: bad, LADDER[1]: (CSV / 'bad-path.json').read_text()}
        out = self.propose('--call', 'c1')
        self.assertTrue(out['ok'], out)
        self.assertEqual(self.models(), list(LADDER))
        self.assertEqual([(r['model'], r['why']) for r in out['rounds']],
                         [(LADDER[0], 'invalid'), (LADDER[1], 'invalid'), (LADDER[2], None)])
        self.assertEqual([r['call_id'] for r in out['rounds']], ['c1', 'c1-r1', 'c1-r2'])

    def test_all_rejected_stops_at_top(self):
        self.content = (CSV / 'bad-params.json').read_text()
        out = self.propose(code=1)
        self.assertEqual(out['why'], 'invalid')
        self.assertEqual(self.models(), list(LADDER))
        self.assertEqual(len(out['rounds']), 3)

    def test_failed_delivery_does_not_climb(self):
        self.code = 400
        out = self.propose(code=2)
        self.assertEqual(self.models(), [LADDER[0]])
        self.assertEqual(len(out['rounds']), 1)

    def test_named_model_unchanged(self):
        self.content = (CSV / 'bad-params.json').read_text()
        p = self.cli('propose', 'csv1', '--llm', 'test/model', '--budget', '../llm/budget/llm')
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertNotIn('rounds', json.loads(p.stdout))
        self.assertEqual(self.models(), ['test/model'])


@own_tests_only
class TestLadderAos(Replies, aos_case.TestAuthorAosCLI):
    """〔author 升級鏈〕aos 學徒：被三關退回才升級，上一級的候選與檢查結果當重問交下一級。"""

    def test_gate_reject_climbs_with_feedback(self):
        self.content = (USAGE / 'valid.json').read_text()
        self.replies = {LADDER[0]: (USAGE / 'bad-link.json').read_text()}
        out = self.checked(self.aos('--budget', self.bd, '--llm'))
        self.assertTrue(out['ok'], out)
        self.assertEqual(self.models(), list(LADDER[:2]))
        self.assertEqual([(r['model'], r['why']) for r in out['rounds']],
                         [(LADDER[0], 'invalid'), (LADDER[1], None)])
        user = json.loads(self.bodies[1]['messages'][1]['content'])
        self.assertEqual(user['previous_candidate'], (USAGE / 'bad-link.json').read_text())
        self.assertEqual(user['feedback']['failed_gate'], 1)
        self.assertNotIn('previous_candidate', json.loads(self.bodies[0]['messages'][1]['content']))
