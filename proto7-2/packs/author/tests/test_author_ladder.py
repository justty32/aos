"""--llm 不給模型＝先便宜後升級：被拒才換下一級，每級模型記進回覆的 rounds。本地 HTTP 走真 llmcall。"""
import json
from pathlib import Path
import sys

PACK = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACK.parents[1] / 'tests'), str(PACK), str(PACK / 'tests')]
import test_author_llm as csv_case
import test_author_aos_cli as aos_case
from aos7_author_llm import APPRENTICE_LADDER, LADDER

CSV = PACK / 'examples/csv-request'
USAGE = PACK / 'examples/aos-tool-usage'


class Replies:
    """依請求的模型給回覆與 HTTP 碼；沒列的模型回預設（合法候選、setUp 的碼）。"""
    replies = {}

    @property
    def content(self):
        return self.replies.get(self.bodies[-1]['model'], self.default) if self.bodies else self.default

    @content.setter
    def content(self, value):
        self.default = value

    codes = {}

    @property
    def code(self):
        return self.codes.get(self.bodies[-1]['model'], self.default_code) if self.bodies else self.default_code

    @code.setter
    def code(self, value):
        self.default_code = value

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

    def test_failed_reply_with_text_does_not_climb(self):
        self.code, self.usage = 500, None
        out = self.propose(code=2)
        self.assertEqual((out['llm']['exit'], out['llm']['outcome']), (4, 'failed'))
        self.assertEqual(self.models(), [LADDER[0]])

    def test_flag_before_rid_and_long_call(self):
        self.replies = {LADDER[0]: (CSV / 'bad-params.json').read_text()}
        call = 'x' * 64
        p = self.cli('propose', '--llm', 'csv1', '--budget', '../llm/budget/llm', '--call', call)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        out = json.loads(p.stdout)
        self.assertEqual(self.models(), list(LADDER[:2]))
        self.assertEqual(out['rounds'][0]['call_id'], call)
        self.assertLessEqual(len(out['rounds'][1]['call_id']), 64)
        self.assertTrue(out['rounds'][1]['call_id'].endswith('-r1'))

    def test_flag_before_command(self):
        out = self.propose_argv('--llm', 'propose', 'csv1', '--budget', '../llm/budget/llm')
        self.assertEqual([r['model'] for r in out['rounds']], [LADDER[0]])

    def propose_argv(self, *argv):
        p = self.cli(*argv)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return json.loads(p.stdout)

    def test_literal_auto_is_a_model_name(self):
        p = self.cli('propose', 'csv1', '--llm', 'auto', '--budget', '../llm/budget/llm')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn('rounds', json.loads(p.stdout))
        self.assertEqual(self.models(), ['auto'])

    def test_named_model_unchanged(self):
        self.content = (CSV / 'bad-params.json').read_text()
        p = self.cli('propose', 'csv1', '--llm', 'test/model', '--budget', '../llm/budget/llm')
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertNotIn('rounds', json.loads(p.stdout))
        self.assertEqual(self.models(), ['test/model'])


@own_tests_only
class TestLadderAos(Replies, aos_case.TestAuthorAosCLI):
    """〔author 升級鏈〕aos 學徒：從 sol-high 起（不用 luna-nothink），被三關退回才升級，上一級的候選與檢查結果當重問交下一級。"""

    def test_gate_reject_climbs_with_feedback(self):
        self.content = (USAGE / 'valid.json').read_text()
        self.replies = {APPRENTICE_LADDER[0]: (USAGE / 'bad-link.json').read_text()}
        node, book = self.skill_node()
        out = self.checked(self.aos('--budget', self.bd, '--skills', node, '--llm'))
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['skill']['picked'], 'apprentice')
        for body in self.bodies:
            self.assertEqual(json.loads(body['messages'][1]['content'])['skill'],
                             {'name': 'apprentice', 'text': book.read_text()})
        self.assertEqual(self.models(), list(APPRENTICE_LADDER))
        self.assertEqual([(r['model'], r['why']) for r in out['rounds']],
                         [(APPRENTICE_LADDER[0], 'invalid'), (APPRENTICE_LADDER[1], None)])
        user = json.loads(self.bodies[1]['messages'][1]['content'])
        self.assertEqual(user['previous_candidate'], (USAGE / 'bad-link.json').read_text())
        self.assertEqual(user['feedback']['failed_gate'], 1)
        self.assertNotIn('previous_candidate', json.loads(self.bodies[0]['messages'][1]['content']))

    def test_out_per_rung_and_unanswered_review_does_not_climb(self):
        self.replies = {APPRENTICE_LADDER[0]: (USAGE / 'bad-link.json').read_text()}
        self.content = (USAGE / 'valid.json').read_text()
        self.codes = {'test/review': 400}
        out = self.checked(self.aos('--budget', self.bd, '--out', 'cand.json', '--review-llm', 'test/review', '--llm'), 1)
        self.assertEqual(Path(self.node, 'cand.json').read_text(), (USAGE / 'bad-link.json').read_text())
        self.assertEqual(Path(self.node, 'cand-r1.json').read_text(), self.content)
        self.assertEqual(out['candidate_path'], str(Path(self.node, 'cand-r1.json').resolve()))
        self.assertEqual(self.models(), [APPRENTICE_LADDER[0], APPRENTICE_LADDER[1], 'test/review'])
        self.assertEqual([r['model'] for r in out['rounds']], list(APPRENTICE_LADDER))

    def test_checker_usage_error_does_not_climb(self):
        self.content = (USAGE / 'valid.json').read_text()
        out = self.checked(self.aos('--budget', self.bd, '--reviewer', 'file:' + str(Path(self.node, 'missing.json')), '--llm'), 1)
        self.assertEqual(self.models(), [APPRENTICE_LADDER[0]])
        self.assertEqual(len(out['rounds']), 1)

    def test_rung_exception_keeps_its_round(self):
        self.replies = {APPRENTICE_LADDER[0]: (USAGE / 'bad-link.json').read_text()}
        Path(self.node, 'cand-r1.json').mkdir()
        out = self.checked(self.aos('--budget', self.bd, '--out', 'cand.json', '--llm'), 3)
        self.assertEqual(out['why'], 'unknown')
        self.assertEqual(self.models(), list(APPRENTICE_LADDER))
        self.assertEqual(out['rounds'][1]['usage'], self.usage)
        self.assertTrue(out['rounds'][1]['call_id'])

    def test_apprentice_starts_at_sol_high(self):
        self.content = (USAGE / 'valid.json').read_text()
        out = self.checked(self.aos('--budget', self.bd, '--llm'))
        self.assertEqual(self.models(), ['chatgpt-gpt-6-sol-high'])
        self.assertEqual([r['model'] for r in out['rounds']], ['chatgpt-gpt-6-sol-high'])
