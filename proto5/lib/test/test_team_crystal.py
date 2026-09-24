"""第三波 W3-2 T-crystal：固化建議（aos_team_crystal）＋route.log 的 letter 格。
不打真模型：--suggest-with-llm 用注入的假 ask。"""
import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import aos_team_crystal as crystal
import aos_team_format as fmt
import aos_team_route as route

PROTO = Path(__file__).resolve().parents[2]
EXAMPLE_ROUTES = PROTO / 'spec' / 'team' / 'examples' / 'routes.json'
EXAMPLE_TASK = PROTO / 'spec' / 'team' / 'examples' / 'task.json'
ROSTER = {'project': '../p', 'tz': 'Asia/Taipei',
          'members': {'lead': {'template': 'lead', 'mail_to': ['worker-1', 'human']},
                      'worker-1': {'template': 'worker', 'mail_to': ['lead', 'human']}}}

RENAME = ['把 a.md 改名成 alpha.md', '把 b.md 改名成 beta.md', '把c.md改名成gamma.md']
DELLINE = ['把 e.md 的第 2 行刪掉', '把 f.md 的第 1 行刪掉']


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-team-crystal-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.team = self.root / 'team'
        self.team.mkdir()
        (self.root / 'p').mkdir()
        (self.team / 'team.json').write_text(json.dumps(ROSTER, ensure_ascii=False), encoding='utf-8')
        self.lay = fmt.Layout(self.team)
        for d in self.lay.skeleton(ROSTER['members']):
            d.mkdir(parents=True, exist_ok=True)
        for n in ROSTER['members']:
            (self.lay.member(n) / 'input').mkdir(parents=True, exist_ok=True)
        shutil.copy(EXAMPLE_ROUTES, self.lay.routes)
        self.n = 0
        self.minute = 0

    def at(self, sec=0):
        return '2026-09-25T10:%02d:%02d+08:00' % (self.minute, sec)

    def say(self, text, *, goal=None, assignee='worker-1', workflow='無', done=None, letter_in_log=True,
            ticket=True, why='沒有規則命中', result='lead'):
        """一句落穿：log 一行、投遞紀錄一封、（要的話）領隊開一張單。每句佔一分鐘，時間不重疊。"""
        self.minute += 1
        self.n += 1
        lid = '17900000000%08d-1-human' % self.n
        line = {'at': self.at(0), 'text': text, 'result': result, 'route': None, 'why': why}
        if letter_in_log:
            line['letter'] = lid
        with open(self.lay.route_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(line, ensure_ascii=False) + '\n')
        rec = {'_metainfo': {'_type': 'aos_team_post_record', '_version': 1}, 'id': lid, 'kind': 'letter',
               'recorded_at': self.at(1), 'from': 'human', 'to': 'lead', 'status': 'REQUEST', 'reply_to': None,
               'rev': None, 'text': text, 'at': self.at(0)}
        fmt.write_json(self.lay.post_sent / (lid + '.json'), rec)
        if ticket:
            t = json.loads(EXAMPLE_TASK.read_text(encoding='utf-8'))
            tid = 't-%04d' % self.n
            t.update(id=tid, request='17900000000%08d-2-lead' % self.n, opened_by='lead', assignee=assignee,
                     workflow=workflow, goal=goal or ('照人說的做：' + text), status='sent',
                     done_when=done or [{'kind': 'file_exists', 'path': 'x.md'}],
                     created_at=self.at(20), updated_at=self.at(20), deadline=self.at(50))
            t['history'] = [dict(t['history'][0], at=self.at(20), src=t['request'])]
            fmt.write_json(self.lay.tasks / (tid + '.json'), t)
        return lid

    def log_tool(self, text, name):
        self.minute += 1
        with open(self.lay.route_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'at': self.at(0), 'text': text, 'result': 'tool', 'route': name,
                                'why': '命中 ' + name}, ensure_ascii=False) + '\n')

    def rename(self, text, a, b):
        return self.say(text, goal='把專案裡的 %s 改名成 %s，內容不動' % (a, b),
                        done=[{'kind': 'file_exists', 'path': b},
                              {'kind': 'check', 'name': 'contains', 'args': {'path': b, 'text': '#'}}])

    def call(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = crystal.cmd_crystal(str(self.team), list(args))
        return code, out.getvalue(), err.getvalue()

    def three_renames(self, letter_in_log=True):
        for s, a, b in zip(RENAME, ('a.md', 'b.md', 'c.md'), ('alpha.md', 'beta.md', 'gamma.md')):
            self.rename(s, a, b) if letter_in_log else self.say(
                s, goal='把專案裡的 %s 改名成 %s，內容不動' % (a, b), letter_in_log=False,
                done=[{'kind': 'file_exists', 'path': b},
                      {'kind': 'check', 'name': 'contains', 'args': {'path': b, 'text': '#'}}])


class LogLetterTests(Base):
    def test_lead_line_has_letter_tool_line_does_not(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            route.ask(str(self.team), '把 a.md 改名成 b.md')
            route.ask(str(self.team), '看一下單子')
        lines = [json.loads(l) for l in self.lay.route_log.read_text(encoding='utf-8').splitlines()]
        sent = fmt.json_files(self.lay.outbox('human'))
        self.assertEqual(lines[0]['result'], 'lead')
        self.assertEqual(lines[0]['letter'], sent[0].stem)
        self.assertEqual(lines[1]['result'], 'tool')
        self.assertNotIn('letter', lines[1])


class SkeletonTests(unittest.TestCase):
    def test_same_class_despite_values_and_spaces(self):
        ks = {crystal.skeleton(s) for s in RENAME + ['把 docs/a.md 改名成 docs/b.md']}
        self.assertEqual(ks, {'把{檔名}改名成{檔名}'})
        self.assertEqual(crystal.skeleton('把 e.md 的第 12 行刪掉'), '把{檔名}的第{數字}行刪掉')
        self.assertEqual(crystal.skeleton('在專案建一個 x.md，內容寫「你 好」'), '在專案建一個{檔名}，內容寫「{引號內文}」')
        self.assertEqual(crystal.skeleton('把 workflows 導入 ~/p/q，照 facts.json'), '把workflows導入{路徑}，照{檔名}')
        self.assertNotEqual(crystal.skeleton('把 a.md 複製成 b.md'), crystal.skeleton(RENAME[0]))

    def test_pattern_is_deterministic_and_matches_class(self):
        p1 = crystal.make_pattern(RENAME[0])
        self.assertEqual(p1, crystal.make_pattern(RENAME[1]))
        import re
        rx = re.compile(p1)
        for s in RENAME + ['把 docs/x.md 改名成 docs/y.md']:
            self.assertIsNotNone(route._match(rx, s), s)
        for s in ['把 a.md 複製成 b.md', '把 a.md 改名成 b.md，然後刪掉 c.md', '把 -x.md 改名成 y.md', '把 a 改名成 b']:
            self.assertIsNone(route._match(rx, s), s)

    def test_templ_keeps_unrelated_digits(self):
        got = crystal._templ('交給 worker-1：刪第 1 行（1 從上數）', [('n1', '1')])
        self.assertEqual(got, '交給 worker-1：刪第 {n1} 行（{n1} 從上數）')
        self.assertEqual(crystal._templ('把 a.md 改成 alpha.md', [('f1', 'a.md'), ('f2', 'alpha.md')]),
                         '把 {f1} 改成 {f2}')


class SlotTests(unittest.TestCase):
    """候選規則的群組只收專案裡的相對路徑（W3-2 審查前補）。"""
    def test_file_slot(self):
        import re
        rx = re.compile(crystal.SLOT_PATTERN['f'] + r'\Z')
        for ok in ('a.md', 'docs/a.md', 'a.b.md', 'x_1/y-2.txt'):
            self.assertTrue(rx.match(ok), ok)
        for bad in ('../x.md', '/etc/a.md', '-rf.md', '~/a.md', 'x/../y.md', '.env.md'):
            self.assertIsNone(rx.match(bad), bad)

    def test_path_slot(self):
        import re
        rx = re.compile(crystal.SLOT_PATTERN['p'] + r'\Z')
        self.assertTrue(rx.match('src/lib'))
        for bad in ('/etc/x', '../up', '~/h/x', 'a/../b'):
            self.assertIsNone(rx.match(bad), bad)


class MechanicalTests(Base):
    def test_candidate_proposal_passes_route_test(self):
        self.three_renames()
        self.say('專案裡有哪些檔？', ticket=False)
        self.say('不要把 a.md 刪掉', why='含否定詞「不要」', ticket=False)
        self.log_tool('看一下單子', 'tasks')
        out = self.root / 'prop.json'
        res = crystal.crystal(str(self.team), out=str(out))
        st = res['stats']
        self.assertEqual((st['lines'], st['by_rule'], st['fallthrough']),
                         (6, {'tasks': 1}, {'nomatch': 4, 'negation': 1}))
        self.assertEqual(len(res['candidates']), 1)
        rule = res['candidates'][0]['rule']
        self.assertEqual(rule['name'], 'crystal-1')
        self.assertEqual(rule['do'], 'handoff')
        self.assertEqual(rule['tests']['hit'], RENAME)
        self.assertIn('不要' + RENAME[0], rule['tests']['miss'])
        self.assertIn('專案裡有哪些檔？', rule['tests']['miss'])
        h = rule['handoff']
        self.assertEqual(h['assignee'], 'worker-1')
        self.assertEqual(h['goal'], '把專案裡的 {f1} 改名成 {f2}，內容不動')
        self.assertEqual(h['done_when'][0], {'kind': 'file_exists', 'path': '{f2}'})
        self.assertNotIn('facts', h)
        obj = json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual(obj['_metainfo']['crystal']['candidates'], ['crystal-1'])
        self.assertEqual([r['name'] for r in obj['routes']][:5], ['tasks', 'waiting', 'routines', 'count-md', 'import'])
        neg, routes = fmt.validate_routes(obj)
        self.assertTrue(all(ok for _, ok, _ in route.run_tests(neg, routes)))
        result, got, groups, _ = route.decide('把 old.md 改名成 new.md', neg, routes)
        self.assertEqual((result, got['name'], groups), ('handoff', 'crystal-1', {'f1': 'old.md', 'f2': 'new.md'}))
        self.assertEqual(json.loads(self.lay.routes.read_text(encoding='utf-8')),
                         json.loads(EXAMPLE_ROUTES.read_text(encoding='utf-8')))     # 不自動生效

    def test_default_out_and_cli_text(self):
        self.three_renames()
        code, out, _ = self.call()
        self.assertEqual(code, 0)
        props = list((self.lay.team / 'crystal').glob('proposal-*.json'))
        self.assertEqual(len(props), 1)
        self.assertIn('aos-team route test --file %s' % props[0], out)
        self.assertIn('aos-team route save %s' % props[0], out)
        self.assertIn('領隊每次開同一種單', out)
        code, out, _ = self.call('--json', '--out', str(self.root / 'x.json'))
        self.assertEqual(json.loads(out)['candidates'][0]['rule']['name'], 'crystal-1')

    def test_old_log_without_letter_matched_by_text_and_time(self):
        self.three_renames(letter_in_log=False)
        res = crystal.crystal(str(self.team), out=str(self.root / 'p.json'))
        self.assertEqual([f['linked'] for f in res['fallthrough']], ['matched'] * 3)
        self.assertEqual(len(res['candidates']), 1)

    def test_unmatched_old_line_lists_sentence_only(self):
        self.three_renames(letter_in_log=False)
        for p in self.lay.post_sent.glob('*.json'):
            p.unlink()
        res = crystal.crystal(str(self.team))
        self.assertEqual([f['linked'] for f in res['fallthrough']], [None] * 3)
        self.assertEqual(res['candidates'], [])
        self.assertIsNone(res['proposal'])
        self.assertFalse((self.lay.team / 'crystal').exists())

    def test_inconsistent_tickets_not_proposed(self):
        self.rename(RENAME[0], 'a.md', 'alpha.md')
        self.say(RENAME[1], assignee='lead')
        res = crystal.crystal(str(self.team))
        self.assertEqual(res['candidates'], [])
        self.assertIn('不一致', res['skipped'][0]['why'])
        self.assertFalse(res['classes'][0]['same_kind'])

    def test_min_threshold(self):
        for s in DELLINE:
            self.say(s, goal='刪掉 %s' % s)
        self.assertEqual(len(crystal.crystal(str(self.team), min_count=3)['candidates']), 0)
        self.assertEqual(len(crystal.crystal(str(self.team), min_count=2, out=str(self.root / 'o.json'))['candidates']), 1)

    def test_same_sentence_repeated_gives_literal_rule(self):
        for _ in range(2):
            self.say('在專案建一個 hello.md，內容寫「你好」', goal='建 hello.md，寫「你好」',
                     done=[{'kind': 'file_exists', 'path': 'hello.md'}])
        res = crystal.crystal(str(self.team), out=str(self.root / 'p.json'))
        self.assertEqual(res['classes'][0]['count'], 2)
        rule = res['candidates'][0]['rule']
        self.assertEqual(rule['tests']['hit'], ['在專案建一個 hello.md，內容寫「你好」'])
        import re
        self.assertEqual(re.compile(rule['pattern']).groupindex, {})
        self.assertEqual(rule['handoff']['goal'], '建 hello.md，寫「你好」')
        self.assertEqual(rule['handoff']['done_when'], [{'kind': 'file_exists', 'path': 'hello.md'}])
        self.assertIn('整句照抄', crystal.render(res))
        neg, routes = fmt.validate_routes(json.loads((self.root / 'p.json').read_text(encoding='utf-8')))
        self.assertEqual(route.decide('在專案建一個 x.md，內容寫「你好」', neg, routes)[0], 'lead')

    def test_backtest_flags_stealing_from_existing_rule(self):
        # 有一條舊規則接住「把 z.md 改名成 zz.md」；新候選也吃得到它＝命中兩條、改落穿＝疑似誤觸
        obj = json.loads(EXAMPLE_ROUTES.read_text(encoding='utf-8'))
        obj['routes'].append({'name': 'zz', 'pattern': '把 z\\.md 改名成 zz\\.md', 'do': 'tool', 'run': ['task', 'ls'],
                              'tests': {'hit': ['把 z.md 改名成 zz.md'], 'miss': ['把 z.md 改名成 z2.md']}})
        fmt.write_json(self.lay.routes, obj)
        self.three_renames()
        self.log_tool('把 z.md 改名成 zz.md', 'zz')
        res = crystal.crystal(str(self.team), out=str(self.root / 'p.json'))
        # 候選自己的例句仍全過（不含 z 那句），但回測標出它搶了 zz 的句子
        c = res['candidates'][0]
        self.assertEqual([(e['text'], e['misfire']) for e in c['backtest']['eats']], [('把 z.md 改名成 zz.md', True)])

    def test_candidate_dropped_when_examples_fail(self):
        # 現有規則已經吃「把 X 改名成 Y」→ 候選的 hit 會命中兩條 → 例句不過 → 不寫進提案
        obj = json.loads(EXAMPLE_ROUTES.read_text(encoding='utf-8'))
        obj['routes'].append({'name': 'wide', 'pattern': '把 (?P<a>\\S+) 改名成 (?P<b>\\S+)', 'do': 'tool',
                              'run': ['task', 'ls'], 'tests': {'hit': ['把 q 改名成 r'], 'miss': ['q']}})
        fmt.write_json(self.lay.routes, obj)
        for s, a, b in zip(RENAME[:2], ('a.md', 'b.md'), ('alpha.md', 'beta.md')):
            self.rename(s, a, b)
        res = crystal.crystal(str(self.team))
        self.assertEqual(res['stats']['fallthrough'], {'nomatch': 2})
        self.assertEqual(res['candidates'], [])
        self.assertIn('例句沒全過', res['dropped'][0]['why'])
        self.assertIsNone(res['proposal'])

    def test_bad_log_lines_counted(self):
        self.three_renames()
        with open(self.lay.route_log, 'a', encoding='utf-8') as f:
            f.write('not json\n{"x": 1}\n')
        res = crystal.crystal(str(self.team), out=str(self.root / 'p.json'))
        self.assertEqual(res['stats']['bad_lines'], 2)

    def test_usage_errors(self):
        with self.assertRaises(fmt.TeamError) as e:
            self.call('--model', 'x')
        self.assertEqual(e.exception.code, 'Usage')
        with self.assertRaises(fmt.TeamError):
            self.call('--min', '0')

    def test_no_log(self):
        code, out, _ = self.call()
        self.assertEqual(code, 0)
        self.assertIn('route.log：0 句', out)
        self.assertIn('沒有候選規則', out)


def fake_asker(rules, text=None):
    calls = []

    def ask(system, user, alias=None, **kw):
        calls.append({'system': system, 'user': user, 'alias': alias})
        return {'text': text if text is not None else json.dumps({'routes': rules}, ensure_ascii=False),
                'usage': {'prompt_tokens': 100, 'completion_tokens': 50}, 'ms': 12, 'alias': alias or 'default',
                'model': 'fake'}
    ask.calls = calls
    return ask


GOOD = {'name': 'rename', 'pattern': '把\\s*(?P<a>[\\w.-]+\\.md)\\s*改名成\\s*(?P<b>[\\w.-]+\\.md)', 'do': 'handoff',
        'handoff': {'assignee': 'worker-1', 'workflow': '無', 'goal': '把 {a} 改名成 {b}',
                    'done_when': [{'kind': 'file_exists', 'path': '{b}'}]},
        'tests': {'hit': RENAME, 'miss': ['把 a.md 複製成 b.md']}}


class LlmTests(Base):
    def run_llm(self, rules, text=None):
        ask = fake_asker(rules, text)
        res = crystal.crystal(str(self.team), out=str(self.root / 'llm.json'), use_llm=True, model='m', asker=ask)
        return res, ask

    def test_good_rule_kept_bad_ones_dropped_with_reasons(self):
        self.three_renames()
        self.say('專案裡有哪些檔？', ticket=False)
        wide = copy.deepcopy(GOOD)
        wide.update(name='wide', pattern='(?P<x>.+)', tests={'hit': RENAME, 'miss': ['x']})   # 會被自己吃到＝例句不過
        wide['handoff'] = dict(GOOD['handoff'], goal='{x}', done_when=[{'kind': 'file_exists', 'path': 'x'}])
        broken = dict(GOOD, name='broken', pattern='(?P<a>[')
        tool = dict(GOOD, name='tool', do='tool', run=['task', 'ls'])
        fake = copy.deepcopy(GOOD)
        fake.update(name='fake', tests={'hit': ['把 q.md 改名成 r.md', '把 s.md 改名成 t.md'], 'miss': ['x']})
        badh = copy.deepcopy(GOOD)
        badh.update(name='badh', pattern='把\\s*(?P<a>[\\w.-]+\\.md)\\s*改名成\\s*(?P<b>[\\w.-]+\\.md)\\s*吧?')
        badh['handoff']['goal'] = '{zzz}'
        res, ask = self.run_llm([GOOD, wide, broken, tool, fake, badh, 'x'])
        self.assertEqual(len(ask.calls), 1)
        self.assertEqual(ask.calls[0]['alias'], 'm')
        self.assertIn('把 a.md 改名成 alpha.md', ask.calls[0]['user'])
        self.assertEqual([c['rule']['name'] for c in res['candidates']], ['llm-rename'])
        why = {d['name']: d['why'] for d in res['dropped']}
        self.assertIn('編不過', why['llm-broken'])
        self.assertIn('do=handoff', why['tool'])
        self.assertIn('真的落穿過的不到', why['llm-fake'])
        self.assertIn('{zzz}', why['llm-badh'])
        self.assertIn('例句沒全過', why['llm-wide'])
        self.assertEqual(res['llm']['usage'], {'prompt_tokens': 100, 'completion_tokens': 50})
        self.assertEqual(res['source'], 'llm')
        obj = json.loads((self.root / 'llm.json').read_text(encoding='utf-8'))
        self.assertEqual(obj['_metainfo']['crystal']['source'], 'llm')

    def test_misfire_in_backtest_dropped(self):
        self.three_renames()
        self.say('把 x.md 複製成 y.md', ticket=False)
        loose = copy.deepcopy(GOOD)
        loose['pattern'] = '把\\s*(?P<a>[\\w.-]+\\.md)\\s*(改名|複製)成\\s*(?P<b>[\\w.-]+\\.md)'
        loose['tests']['miss'] = ['把 a.md 刪掉']
        res, _ = self.run_llm([loose])
        self.assertEqual(res['candidates'], [])
        self.assertIn('回測誤觸別類', res['dropped'][0]['why'])
        self.assertIsNone(res['proposal'])

    def test_llm_failure_is_team_error(self):
        self.three_renames()
        import aos_agent_home
        import aos_llm_ask
        orig = aos_llm_ask.ask

        def boom(*a, **k):
            raise aos_agent_home.AgentError('EngineFailed', '端點不通')
        aos_llm_ask.ask = boom
        self.addCleanup(setattr, aos_llm_ask, 'ask', orig)
        with self.assertRaises(fmt.TeamError) as e:
            self.call('--suggest-with-llm')
        self.assertEqual(e.exception.code, 'EngineFailed')

    def test_bad_json_reported(self):
        self.three_renames()
        res, _ = self.run_llm(None, text='我覺得不用加規則')
        self.assertEqual(res['candidates'], [])
        self.assertIn('不是 JSON', res['llm']['error'])
        self.assertIn('讀不懂', crystal.render(res))


if __name__ == '__main__':
    unittest.main()
