"""aos-team score（spec/team/score.md）：手造一支小團隊的紀錄，驗六軸計數、門檻、範圍、去重、輪換、--runs、--json、壞行。"""
import contextlib
import datetime
import io
import json
import unittest

import aos_team_score as score
from _team_util import TeamCase, TZ

T0 = datetime.datetime(2026, 9, 25, 10, 0, 0, tzinfo=TZ)


def at(sec):
    return (T0 + datetime.timedelta(seconds=sec)).isoformat(timespec='milliseconds')


def hist(sec, event, frm, to):
    return {'at': at(sec), 'event': event, 'src': '%s:%s' % (event, sec), 'by': None, 'from': frm, 'to': to,
            'effects': []}


class ScoreCase(TeamCase):

    # ---- 寫假紀錄
    def ev(self, name, rows, file='events.jsonl'):
        log = self.lay.member(name) / 'log'
        log.mkdir(exist_ok=True)
        with open(log / file, 'a', encoding='utf-8') as f:
            for r in rows:
                f.write((r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)) + '\n')

    def think(self, name, sec, bid, ok=True, ms=1000, file='events.jsonl'):
        self.ev(name, [{'at': at(sec), 'ev': 'think_end', 'id': bid, 'ok': ok, 'ms': ms}], file)

    def usage(self, name, sec, tokens):
        self.ev(name, [{'at': at(sec), 'batch': 'b', 'alias': 'default', 'model': 'm', 'ms': 10,
                        'usage': {'total_tokens': tokens} if tokens is not None else None}], 'usage.jsonl')

    def sent(self, rid, **fields):
        rec = dict({'id': rid, 'kind': 'letter', 'recorded_at': fields.get('at')}, **fields)
        (self.lay.post_sent / (rid + '.json')).write_text(json.dumps(rec, ensure_ascii=False), encoding='utf-8')

    def task(self, tid, status, history, opened_by='lead', created=0, **over):
        t = {'_metainfo': {'_type': 'aos_team_task', '_version': 1}, 'id': tid, 'parent': None,
             'request': 'req-' + tid, 'opened_by': opened_by, 'assignee': 'worker-1', 'rev': 1, 'attempt': 1,
             'max_attempts': 3, 'workflow': 'IMPORT.md', 'goal': '導入',
             'done_when': [{'kind': 'file_exists', 'path': 'A'}, {'kind': 'judge', 'text': '原意沒變'}],
             'status': status, 'waiting_on': None, 'created_at': at(created), 'updated_at': at(created),
             'deadline': None, 'review_of': None, 'verify': [], 'review': [], 'history': history}
        t.update(over)
        (self.lay.tasks / (tid + '.json')).write_text(json.dumps(t, ensure_ascii=False), encoding='utf-8')

    def run_score(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = score.cmd_score(str(self.team), list(argv))
        return code, buf.getvalue()

    def js(self, *argv):
        code, out = self.run_score('--json', *argv)
        self.assertEqual(code, 0)
        return json.loads(out)

    # ---- 一支做完 t-0001 的團隊（另有一張還在做的 t-0002）
    def build(self):
        self.sent('h1', **{'from': 'human', 'to': 'lead', 'status': 'REQUEST', 'text': '導入', 'at': at(-30)})
        self.sent('h0', **{'from': 'human', 'to': 'lead', 'status': 'REQUEST', 'text': '更早的', 'at': at(-500)})
        self.sent('w1', **{'from': 'worker-1', 'to': 'lead', 'status': 'DONE', 'reply_to': 't-0001',
                           'at': at(55)})
        self.sent('p1', **{'from': 'post', 'to': 'worker-1', 'status': 'REQUEST', 'at': at(1)})
        self.sent('x1', kind='rejected', **{'from': 'worker-1', 'at': at(20), 'code': 'BadStatus'})
        self.task('t-0001', 'done', [hist(0, 'opened', None, 'queued'), hist(2, 'delivered', 'queued', 'sent'),
                                      hist(10, 'picked_up', 'sent', 'working'),
                                      hist(12, 'ignored:report', 'working', 'working'),
                                      hist(60, 'report', 'working', 'verifying'),
                                      hist(70, 'verified', 'verifying', 'reviewing'),
                                      hist(100, 'reviewed', 'reviewing', 'done')],
                  verify=[{'rev': 1, 'attempt': 1, 'pass': True, 'at': at(70),
                           'results': [{'i': 0, 'kind': 'file_exists', 'result': 'pass', 'pass': True}]}],
                  review=[{'rev': 1, 'attempt': 1, 'pass': True, 'at': at(100),
                           'items': [{'i': 1, 'pass': True, 'why': '好'}]}])
        self.task('t-0001.r1', 'done', [hist(70, 'opened', None, 'queued'), hist(95, 'review_result', 'working',
                                                                                  'done')],
                  opened_by='post', created=70, parent='t-0001', assignee='reviewer',
                  done_when=[{'kind': 'judge', 'text': '原意沒變'}])
        self.task('t-0002', 'working', [hist(1000, 'opened', None, 'queued'),
                                        hist(1001, 'delivered', 'queued', 'sent'),
                                        hist(1005, 'picked_up', 'sent', 'working')], created=1000)
        # lead 2 次（在窗內）、worker 3 次（1 次失敗、1 行重複、1 次在輪換舊檔）、reviewer 1 次；t-0002 那段 worker 2 次
        self.think('lead', -20, 'bl1', ms=2000)
        self.think('lead', -5, 'bl2', ms=2000)
        self.think('worker-1', 15, 'bw1', ms=3000, file='events.1.jsonl')
        self.think('worker-1', 20, 'bw2', ok=False, ms=500)
        self.think('worker-1', 20, 'bw2', ok=False, ms=500)        # 崩了重做寫的第二行
        self.think('worker-1', 40, 'bw3', ms=1500)
        self.ev('worker-1', [{'at': at(45), 'ev': 'act_end', 'id': 'bw3', 'ok': True,
                              'calls': [{'tool': 'bash', 'ok': True, 'ms': 4000},
                                        {'tool': 'nope', 'ok': False, 'ms': None}]}])
        self.think('reviewer', 90, 'br1', ms=1000)
        self.think('worker-1', 1010, 'bw9')
        self.think('worker-1', 1020, 'bw10')
        self.usage('lead', -20, 5000)
        self.usage('lead', -5, 6000)
        self.usage('worker-1', 15, 4000)
        self.usage('worker-1', 40, 3000)
        self.usage('worker-1', 41, None)
        self.usage('reviewer', 90, 1000)
        self.usage('worker-1', 1010, 50000)


class ThresholdTest(unittest.TestCase):
    def test_think(self):
        for n, s in ((0, 5), (1, 5), (2, 4), (5, 4), (6, 3), (15, 3), (16, 2), (40, 2), (41, 1)):
            self.assertEqual(score.score_think(n), s, n)

    def test_tokens(self):
        for n, s in ((0, 5), (19999, 5), (20000, 4), (59999, 4), (60000, 3), (149999, 3), (150000, 2),
                     (399999, 2), (400000, 1)):
            self.assertEqual(score.score_tokens(n), s, n)

    def test_wall(self):
        for n, s in ((0, 5), (59.9, 5), (60, 4), (179, 4), (180, 3), (599, 3), (600, 2), (1799, 2), (1800, 1)):
            self.assertEqual(score.score_wall(n), s, n)

    def test_runs(self):
        self.assertIsNone(score.score_runs(9, 9))
        for ok, total, s in ((10, 10, 4), (20, 20, 4), (9, 10, 3), (8, 10, 3), (7, 10, 2), (5, 10, 2),
                             (4, 10, 1), (0, 10, 1)):
            self.assertEqual(score.score_runs(ok, total), s, (ok, total))


class TaskScopeTest(ScoreCase):
    def setUp(self):
        super().setUp()
        self.build()

    def test_think_dedupe_rotation_window(self):
        r = self.js('--task', 't-0001')
        L = r['axes']['L']
        self.assertEqual(L['by_member'], {'lead': 2, 'worker-1': 3, 'reviewer': 1})
        self.assertEqual((L['think'], L['failed'], L['score']), (6, 1, 3))
        self.assertIn('lead（領隊）2', L['why'])

    def test_tokens(self):
        R = self.js('--task', 't-0001')['axes']['R']
        self.assertEqual(R['by_member'], {'lead': 11000, 'worker-1': 7000, 'reviewer': 1000})
        self.assertEqual((R['tokens'], R['score'], R['no_usage'], R['cpu_s'], R['mem_mb']), (19000, 5, 1, None, None))

    def test_fast_start_from_human_letter(self):
        F = self.js('--task', 't-0001')['axes']['F']
        self.assertEqual(F['wall_s'], 130)
        self.assertEqual(F['score'], 4)
        self.assertEqual(F['start'], at(-30).replace('.000', ''))
        self.assertIn('人寄給 lead', F['start_from'])
        p = F['parts']
        self.assertEqual((p['model_s'], p['tools_s'], p['pickup_s'], p['verify_s'], p['human_s']),
                         (10.0, 4.0, 8.0, 10.0, 0.0))
        self.assertEqual(p['other_s'], 130 - 32)

    def test_stability_single_run(self):
        S = self.js('--task', 't-0001')['axes']['S']
        self.assertIsNone(S['score'])
        self.assertEqual(S['this_run'], 'ok')
        self.assertIn('1/1 次過', S['why'])

    def test_tasks_and_letters(self):
        r = self.js('--task', 't-0001')
        self.assertEqual([t['id'] for t in r['tasks']], ['t-0001', 't-0001.r1'])
        self.assertEqual(r['tasks'][0]['done_when'], {'total': 2, 'checked': 2, 'passed': 2})
        self.assertEqual(r['letters'], {'total': 3, 'by_sender': {'human': 1, 'post': 1, 'worker-1': 1},
                                        'rejected': 1})

    def test_done_letters_after_end_counted(self):
        """T5 試玩：單子結束那一刻之後才記的完成信（post → lead／人）也算這張單的信。"""
        self.sent('p9', **{'from': 'post', 'to': 'human', 'status': 'DONE', 'reply_to': 't-0001', 'at': at(5000)})
        self.sent('p8', **{'from': 'post', 'to': 'lead', 'status': 'DONE', 'reply_to': 't-0001.r1', 'at': at(5000)})
        r = self.js('--task', 't-0001')
        self.assertEqual(r['letters']['by_sender']['post'], 3)

    def test_later_non_terminal_letter_not_counted(self):
        """astra M5：結束很久後回這張單的一般信（追問、補充）照時間窗，不算；只有郵差的終局通知例外。"""
        self.sent('w9', **{'from': 'worker-1', 'to': 'lead', 'status': 'PROGRESS', 'reply_to': 't-0001', 'at': at(9000)})
        self.sent('p7', **{'from': 'post', 'to': 'lead', 'status': 'REQUEST', 'reply_to': 't-0001', 'at': at(9000)})
        r = self.js('--task', 't-0001')
        self.assertEqual(r['letters']['by_sender'], {'human': 1, 'post': 1, 'worker-1': 1})

    def test_bad_shapes_skipped_not_traceback(self):
        """astra M2：id 不是字串的事件、verify.results 不是陣列的單，跳過計數，不丟例外。"""
        self.ev('lead', [{'at': at(3), 'ev': 'think_end', 'id': [], 'ok': True, 'ms': 1}])
        self.task('t-0003', 'done', [hist(0, 'opened', None, 'queued'), hist(5, 'verified', 'verifying', 'done')],
                  created=0, verify=[{'results': 1}], review=[{'items': 'x'}])
        code, out = self.run_score()
        self.assertEqual(code, 0)
        self.assertIn('跳過', out)
        r = self.js('--task', 't-0003')
        self.assertEqual(r['tasks'][0]['done_when']['checked'], 0)

    def test_rotation_gap_still_read(self):
        """.1 不在、.2 還在：照樣讀（astra S2）。"""
        self.think('reviewer', 2, 'gap-b', file='events.2.jsonl')
        r = self.js('--task', 't-0001')
        self.assertEqual(r['axes']['L']['by_member']['reviewer'], 2)

    def test_json_keys(self):
        r = self.js('--task', 't-0001')
        self.assertEqual(set(r), {'scope', 'task', 'summary', 'axes', 'tasks', 'letters', 'skipped'})
        self.assertEqual(set(r['axes']), set('LSRFHB'))
        self.assertEqual(set(r['axes']['L']), {'score', 'think', 'failed', 'by_member', 'model_steps', 'why'})
        self.assertEqual(set(r['axes']['S']), {'score', 'this_run', 'runs', 'why'})
        self.assertEqual(set(r['axes']['R']), {'score', 'tokens', 'by_member', 'calls', 'no_usage', 'cpu_s',
                                               'mem_mb', 'why'})
        self.assertEqual(set(r['axes']['F']), {'score', 'wall_s', 'start', 'end', 'start_from', 'parts',
                                               'think_ms_missing', 'why'})
        self.assertEqual(set(r['axes']['F']['parts']), {'model_s', 'tools_s', 'pickup_s', 'verify_s', 'human_s',
                                                        'other_s'})
        self.assertEqual(r['axes']['H'], {'score': None, 'why': '給人填'})
        self.assertEqual(set(r['tasks'][0]), {'id', 'status', 'assignee', 'rev', 'attempt', 'max_attempts',
                                              'done_when', 'opened_at', 'ended_at'})
        self.assertEqual((r['scope'], r['task']), ('task', 't-0001'))

    def test_text_output(self):
        code, out = self.run_score('--task', 't-0001')
        self.assertEqual(code, 0)
        first = out.splitlines()[0]
        self.assertTrue(first.startswith('t-0001，這次成了，問模型 6 次'), first)
        self.assertIn('| L LLM 參與 | 3 |', out)
        self.assertIn('| S 穩定 | — |', out)
        self.assertIn('| H 人易懂 | — | 給人填 |', out)
        self.assertIn('t-0001.r1  done  reviewer', out)
        self.assertNotIn('跳過', out)

    def test_unfinished_task(self):
        r = self.js('--task', 't-0002')
        self.assertIsNone(r['axes']['F']['score'])
        self.assertIn('還沒結束', r['axes']['F']['why'])
        self.assertEqual(r['axes']['F']['start_from'], '開單')    # 人那封信屬於 t-0001，不算到 t-0002
        self.assertEqual(r['axes']['S']['this_run'], 'unfinished')
        self.assertEqual(r['axes']['L']['think'], 2)          # 開單到現在
        self.assertEqual(r['axes']['R']['tokens'], 50000)

    def test_letter_between_tasks_is_start(self):
        self.sent('h2', **{'from': 'human', 'to': 'lead', 'status': 'REQUEST', 'text': '再一件', 'at': at(990)})
        self.sent('h3', **{'from': 'human', 'to': 'lead', 'status': 'PROGRESS', 'text': '不算', 'at': at(995)})
        F = self.js('--task', 't-0002')['axes']['F']
        self.assertEqual(F['start'], at(990).replace('.000', ''))

    def test_team_scope(self):
        r = self.js()
        self.assertEqual(r['scope'], 'team')
        self.assertEqual(r['axes']['L']['think'], 8)
        self.assertEqual(r['axes']['R']['tokens'], 69000)
        self.assertIsNone(r['axes']['F']['wall_s'])           # t-0002 還沒結束
        self.assertEqual(r['axes']['F']['start'], at(-500).replace('.000', ''))
        self.assertEqual(len(r['tasks']), 3)
        self.assertEqual(r['letters']['by_sender']['human'], 2)

    def test_team_scope_all_done(self):
        (self.lay.tasks / 't-0002.json').unlink()
        F = self.js()['axes']['F']
        self.assertEqual(F['wall_s'], 600)
        self.assertEqual(F['score'], 2)


class RunsTest(ScoreCase):
    def setUp(self):
        super().setUp()
        self.build()

    def runs_file(self, content):
        p = self.tmp / 'runs.json'
        p.write_text(content, encoding='utf-8')
        return str(p)

    def test_under_ten(self):
        S = self.js('--runs', self.runs_file(json.dumps([{'ok': True}] * 9)))['axes']['S']
        self.assertIsNone(S['score'])
        self.assertEqual(S['runs'], {'ok': 9, 'total': 9})
        self.assertIn('9/9 次過', S['why'])

    def test_ten_all_ok(self):
        S = self.js('--runs', self.runs_file(json.dumps([{'ok': True}] * 10)))['axes']['S']
        self.assertEqual(S['score'], 4)
        self.assertIn('崩潰恢復', S['why'])

    def test_jsonl_and_bad_items(self):
        lines = ['{"ok": true}'] * 8 + ['{"ok": false}', 'false', 'not json', '{"ok": "yes"}']
        r = self.js('--runs', self.runs_file('\n'.join(lines)))
        self.assertEqual(r['axes']['S']['runs'], {'ok': 8, 'total': 10})
        self.assertEqual(r['axes']['S']['score'], 3)
        self.assertEqual(r['skipped']['lines'], 2)

    def test_missing_runs_file(self):
        with self.assertRaises(score.TeamError) as e:
            self.run_score('--runs', str(self.tmp / 'nope.json'))
        self.assertEqual(e.exception.code, 'NotFound')


class EdgeTest(ScoreCase):
    def test_empty_team(self):
        code, out = self.run_score()
        self.assertEqual(code, 0)
        r = self.js()
        self.assertEqual((r['axes']['L']['think'], r['axes']['L']['score']), (0, 5))
        self.assertEqual((r['axes']['R']['tokens'], r['axes']['R']['score']), (0, 5))
        self.assertIsNone(r['axes']['F']['score'])
        self.assertEqual(r['axes']['S']['this_run'], 'none')
        self.assertIn('（沒有）', out)
        self.assertIn('信：共 0 封', out)

    def test_bad_lines_and_files(self):
        self.think('lead', 1, 'a')
        self.ev('lead', ['{"at": "2026-09-25T10:00', '[1, 2]', '{"ev": "think_end", "id": "z", "at": "昨天"}'])
        self.ev('lead', ['garbage'], 'usage.jsonl')
        (self.lay.tasks / 't-0009.json').write_text('{壞', encoding='utf-8')
        (self.lay.post_sent / 'x.json').write_text('[]', encoding='utf-8')
        r = self.js()
        self.assertEqual(r['axes']['L']['think'], 1)
        self.assertEqual(r['skipped'], {'lines': 4, 'files': 2})
        code, out = self.run_score()
        self.assertIn('跳過 4 行、2 個檔', out)

    def test_think_without_usage(self):
        self.think('lead', 1, 'a')
        R = self.js()['axes']['R']
        self.assertIsNone(R['score'])
        self.assertIn('量不到', R['why'])

    def test_opened_by_human_uses_request_time(self):
        self.sent('rq', kind='request', request_kind='handoff', at=at(-7), **{'from': 'human'})
        self.task('t-0001', 'failed', [hist(0, 'opened', None, 'queued'), hist(10, 'expire', 'queued', 'failed')],
                  opened_by='human', request='rq')
        r = self.js('--task', 't-0001')
        self.assertEqual(r['axes']['F']['wall_s'], 17)
        self.assertEqual(r['axes']['F']['score'], 5)
        self.assertEqual(r['axes']['S']['this_run'], 'fail')
        self.assertIn('0/1 次過', r['axes']['S']['why'])

    def test_waiting_user_and_retry_segments(self):
        self.task('t-0001', 'done', [hist(0, 'opened', None, 'queued'), hist(5, 'report', 'queued', 'waiting_user'),
                                      hist(65, 'resume', 'waiting_user', 'working'),
                                      hist(70, 'report', 'working', 'verifying'),
                                      hist(80, 'verified', 'verifying', 'queued'),
                                      hist(90, 'report', 'queued', 'verifying'),
                                      hist(95, 'verified', 'verifying', 'done')])
        p = self.js('--task', 't-0001')['axes']['F']['parts']
        self.assertEqual((p['human_s'], p['verify_s'], p['other_s']), (60.0, 15.0, 20.0))

    def test_unknown_task(self):
        with self.assertRaises(score.TeamError) as e:
            self.run_score('--task', 't-0404')
        self.assertEqual(e.exception.code, 'NotFound')

    def test_cli_errors(self):
        p = self.cli('score', '--task', 'nope')
        self.assertEqual(p.returncode, 2)
        self.assertIn('aos-team: Usage:', p.stderr)
        p = self.cli('score', '--task', 't-0404')
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stderr.count('\n'), 1)
        self.assertIn('aos-team: NotFound:', p.stderr)
        (self.team / 'team.json').write_text('{壞', encoding='utf-8')
        p = self.cli('score')
        self.assertEqual(p.returncode, 1)
        self.assertNotIn('Traceback', p.stderr)
        p = self.cli('score', '--json')
        self.assertEqual(p.returncode, 1)

    def test_cli_missing_team(self):
        import subprocess, sys, os
        from _team_util import CLI_TEAM
        p = subprocess.run([sys.executable, str(CLI_TEAM), 'score', '--target', str(self.tmp / 'none')],
                           capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(p.returncode, 1)
        self.assertIn('aos-team: NotFound:', p.stderr)

    def test_cli_ok(self):
        self.think('lead', 1, 'a')
        self.usage('lead', 1, 100)
        p = self.cli('score', '--json')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)['axes']['L']['think'], 1)


if __name__ == '__main__':
    unittest.main()
