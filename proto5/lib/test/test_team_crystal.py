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
        # zz 的例句（看 z）不會被候選吃到，所以整份例句仍全過；但 log 裡被 zz 接住的那句會被搶
        obj['routes'].append({'name': 'zz', 'pattern': '把 z\\.md 改名成 zz\\.md|看 z', 'do': 'tool', 'run': ['task', 'ls'],
                              'tests': {'hit': ['看 z'], 'miss': ['把 z.md 改名成 z2.md']}})
        fmt.write_json(self.lay.routes, obj)
        self.three_renames()
        self.log_tool('把 z.md 改名成 zz.md', 'zz')
        res = crystal.crystal(str(self.team), out=str(self.root / 'p.json'))
        # 候選自己的例句仍全過（不含 z 那句），但回測標出它搶了 zz 的句子
        c = res['candidates'][0]
        self.assertEqual([(e['text'], e['misfire']) for e in c['backtest']['eats']], [('把 z.md 改名成 zz.md', True)])

    def test_candidate_breaking_existing_rule_examples_dropped(self):
        # 審查 M3：舊規則 zz 的 hit「把 z.md 改名成 zz.md」會被候選一起吃到＝命中兩條＝舊規則例句不過 → 候選不收
        obj = json.loads(EXAMPLE_ROUTES.read_text(encoding='utf-8'))
        obj['routes'].append({'name': 'zz', 'pattern': '把 z\\.md 改名成 zz\\.md', 'do': 'tool', 'run': ['task', 'ls'],
                              'tests': {'hit': ['把 z.md 改名成 zz.md'], 'miss': ['把 z.md 改名成 z2.md']}})
        fmt.write_json(self.lay.routes, obj)
        self.three_renames()
        res = crystal.crystal(str(self.team), out=str(self.root / 'p.json'))
        self.assertEqual(res['candidates'], [])
        self.assertIn('加了它之後 zz 的例句不過', res['dropped'][0]['why'])
        self.assertIsNone(res['proposal'])

    def test_existing_rules_already_failing_blocks_all(self):
        obj = json.loads(EXAMPLE_ROUTES.read_text(encoding='utf-8'))
        obj['routes'].append({'name': 'bad', 'pattern': 'x', 'do': 'tool', 'run': ['task', 'ls'],
                              'tests': {'hit': ['y'], 'miss': ['z']}})
        fmt.write_json(self.lay.routes, obj)
        self.three_renames()
        res = crystal.crystal(str(self.team), out=str(self.root / 'p.json'))
        self.assertEqual(res['candidates'], [])
        self.assertIn('本來就沒全過', res['dropped'][0]['why'])

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


class OutPathTests(Base):
    """審查 M2：提案不准寫到生效中的 routes.json；預設不覆蓋、預設檔名唯一。"""
    def test_refuses_routes_json_and_aliases(self):
        self.three_renames()
        before = self.lay.routes.read_bytes()
        link = self.root / 'alias.json'
        link.symlink_to(self.lay.routes)
        hard = self.root / 'hard.json'
        import os
        os.link(self.lay.routes, hard)
        for out in (self.lay.routes, self.team / 'team' / '.' / 'routes.json', self.team / 'x' / '..' / 'team' / 'routes.json',
                    link, hard):
            with self.assertRaises(fmt.TeamError) as e:
                crystal.crystal(str(self.team), out=str(out), force=True)
            self.assertEqual(e.exception.code, 'Refused', out)
        self.assertEqual(self.lay.routes.read_bytes(), before)

    def test_no_overwrite_without_force(self):
        self.three_renames()
        out = self.root / 'p.json'
        out.write_text('{}', encoding='utf-8')
        with self.assertRaises(fmt.TeamError) as e:
            crystal.crystal(str(self.team), out=str(out))
        self.assertEqual(e.exception.code, 'AlreadyExists')
        self.assertEqual(out.read_text(encoding='utf-8'), '{}')
        code, _, _ = self.call('--out', str(out), '--force')
        self.assertEqual(code, 0)
        self.assertIn('crystal', json.loads(out.read_text(encoding='utf-8'))['_metainfo'])

    def test_default_names_unique(self):
        self.three_renames()
        a = crystal.crystal(str(self.team))['proposal']
        b = crystal.crystal(str(self.team))['proposal']
        self.assertNotEqual(a, b)
        self.assertEqual(len(list((self.lay.team / 'crystal').glob('proposal-*.json'))), 2)


class AmbiguityTests(Base):
    """審查 S3：配信有歧義的只列、不拿來產候選，可信度標出來。"""
    def test_old_log_same_text_twice_in_window_is_low(self):
        # 同一句說兩次、舊 log 沒 letter、兩封信都在 120 秒內 → 兩行都配不準
        self.minute = 5
        for sec in (0, 30):
            lid = '17900000000%08d-1-human' % (90 + sec)
            with open(self.lay.route_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'at': self.at(sec), 'text': RENAME[0], 'result': 'lead', 'route': None,
                                    'why': '沒有規則命中'}, ensure_ascii=False) + '\n')
            fmt.write_json(self.lay.post_sent / (lid + '.json'),
                           {'id': lid, 'kind': 'letter', 'recorded_at': self.at(sec), 'from': 'human', 'to': 'lead',
                            'status': 'REQUEST', 'text': RENAME[0], 'at': self.at(sec)})
        res = crystal.crystal(str(self.team))
        self.assertEqual([f['confidence'] for f in res['fallthrough']], ['low', 'low'])
        self.assertIn('配不準', res['fallthrough'][0]['doubt'])
        self.assertEqual(res['classes'][0]['doubtful'], 2)
        self.assertEqual(res['candidates'], [])
        self.assertIn('歧義', res['skipped'][0]['why'])

    def test_queued_letters_ticket_attribution_is_low(self):
        # 兩封信排在一起（第一封還沒被收走、第二封就寄了），之後只開一張單 → 分不清哪封開的
        self.rename(RENAME[0], 'a.md', 'alpha.md')
        self.minute += 1
        first = '17900000000%08d-1-human' % 77
        second = '17900000000%08d-1-human' % 78
        for lid, text, sec in ((first, '專案裡有哪些檔？', 0), (second, RENAME[1], 5)):
            with open(self.lay.route_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'at': self.at(sec), 'text': text, 'result': 'lead', 'route': None,
                                    'why': '沒有規則命中', 'letter': lid}, ensure_ascii=False) + '\n')
            fmt.write_json(self.lay.post_sent / (lid + '.json'),
                           {'id': lid, 'kind': 'letter', 'recorded_at': self.at(sec), 'from': 'human', 'to': 'lead',
                            'status': 'REQUEST', 'text': text, 'at': self.at(sec), 'picked_up_at': self.at(10)})
        t = json.loads(EXAMPLE_TASK.read_text(encoding='utf-8'))
        t.update(id='t-0077', request='x-2-lead', opened_by='lead', assignee='worker-1', workflow='無',
                 goal='把專案裡的 b.md 改名成 beta.md，內容不動', status='sent',
                 done_when=[{'kind': 'file_exists', 'path': 'beta.md'},
                            {'kind': 'check', 'name': 'contains', 'args': {'path': 'beta.md', 'text': '#'}}],
                 created_at=self.at(20), updated_at=self.at(20), deadline=self.at(50))
        t['history'] = [dict(t['history'][0], at=self.at(20), src='x-2-lead')]
        fmt.write_json(self.lay.tasks / 't-0077.json', t)
        res = crystal.crystal(str(self.team))
        conf = {f['text']: f['confidence'] for f in res['fallthrough']}
        self.assertEqual(conf[RENAME[0]], 'high')
        self.assertEqual(conf[RENAME[1]], 'low')
        self.assertEqual(res['candidates'], [])      # 能用的只剩 1 句 < --min 2

    def test_sequential_letters_not_ambiguous(self):
        self.three_renames()
        res = crystal.crystal(str(self.team), out=str(self.root / 'p.json'))
        self.assertEqual({f['confidence'] for f in res['fallthrough']}, {'high'})


class ProbeTests(unittest.TestCase):
    """審查 M5：內建反例。"""
    def rule(self, pattern, hits, path='{b}'):
        return {'name': 'r', 'pattern': pattern, 'do': 'handoff',
                'handoff': {'assignee': 'worker-1', 'workflow': '無', 'goal': 'g',
                            'done_when': [{'kind': 'file_exists', 'path': path}]},
                'tests': {'hit': hits, 'miss': ['x']}}

    def test_loose_model_patterns_eaten(self):
        loose = self.rule('把 (?P<a>\\S+\\.md) 改名成 (?P<b>\\S+\\.md)', ['把 a.md 改名成 b.md'])
        whys = [w for _, w in crystal.probe_rule(loose)]
        self.assertTrue(any('../x.md' in w for w in whys))
        self.assertTrue(any('/etc/passwd' in w for w in whys) is False)   # \.md 結尾擋掉了 /etc/passwd
        self.assertTrue(any('-rf.md' in w for w in whys))
        self.assertTrue(any('然後刪掉' in w for w in whys))
        noext = self.rule('數 (?P<a>\\S+\\.md) 有幾行，寫進 (?P<b>\\S+)', ['數 a.md 有幾行，寫進 n.txt'])
        whys = [w for _, w in crystal.probe_rule(noext)]
        self.assertIn('群組 b 換成 noext', whys)
        self.assertIn('群組 b 換成 /etc/passwd', whys)

    def test_mechanical_patterns_pass(self):
        for text in RENAME + ['數 poem.md 有幾行，寫進 poem-lines.txt', '把 e.md 的第 2 行刪掉']:
            r = self.rule(crystal.make_pattern(text), [text], path='x')
            self.assertEqual(crystal.probe_rule(r), [], text)

    def test_quote_group_used_as_path_is_probed(self):
        text = '在專案建一個 x.md，內容寫「你好」'
        pat = crystal.make_pattern(text)
        self.assertEqual(crystal.probe_rule(self.rule(pat, [text], path='{f1}')), [])     # 引號當內文：不測
        eaten = crystal.probe_rule(self.rule(pat, [text], path='{q1}'))                  # 引號群組當路徑用：吃到反例
        self.assertTrue(any('/etc/passwd' in t for t, _ in eaten))
        eaten = crystal.probe_rule(self.rule(pat, ['在專案建一個 x.md，內容寫「docs/a.md」'], path='{f1}'))
        self.assertTrue(eaten)                                                           # 值像路徑也測



class QuotePathTests(Base):
    def test_mechanical_quote_group_used_as_path_dropped(self):
        # 領隊把引號裡的值當檔名用（done_when 的 path）→ 機械候選的 q 群組變成路徑用途 → 吃得到 /etc/passwd → 丟
        for name in ('docs/a.md', 'docs/b.md'):
            self.say('建一個「%s」' % name, goal='建 %s' % name, done=[{'kind': 'file_exists', 'path': name}])
        res = crystal.crystal(str(self.team))
        self.assertEqual(res['candidates'], [])
        self.assertIn('吃到內建反例', res['dropped'][0]['why'])


def fake_asker(rules, text=None):
    calls = []

    def ask(system, user, alias=None, **kw):
        calls.append({'system': system, 'user': user, 'alias': alias})
        return {'text': text if text is not None else json.dumps({'routes': rules}, ensure_ascii=False),
                'usage': {'prompt_tokens': 100, 'completion_tokens': 50}, 'ms': 12, 'alias': alias or 'default',
                'model': 'fake'}
    ask.calls = calls
    return ask


SAFE = '[A-Za-z0-9_][A-Za-z0-9_.-]*\\.md'
GOOD = {'name': 'rename', 'pattern': '把\\s*(?P<a>%s)\\s*改名成\\s*(?P<b>%s)' % (SAFE, SAFE), 'do': 'handoff',
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
        self.assertIn('例句沒全過', why['llm-fake'])      # 跟 rename 同一個 pattern：歷史次數夠，但兩條互搶
        self.assertIn('{zzz}', why['llm-badh'])
        self.assertIn('不一致', why['llm-wide'])      # (.+) 也吃到沒開單的「專案裡有哪些檔？」
        self.assertEqual(res['llm']['usage'], {'prompt_tokens': 100, 'completion_tokens': 50})
        self.assertEqual(res['source'], 'llm')
        obj = json.loads((self.root / 'llm.json').read_text(encoding='utf-8'))
        self.assertEqual(obj['_metainfo']['crystal']['source'], 'llm')

    def test_misfire_in_backtest_dropped(self):
        self.three_renames()
        self.log_tool('把 x.md 複製成 y.md', 'tasks')        # 原本別條規則接住的句子，被它搶走
        loose = copy.deepcopy(GOOD)
        loose['pattern'] = '把\\s*(?P<a>%s)\\s*(改名|複製)成\\s*(?P<b>%s)' % (SAFE, SAFE)
        loose['tests']['miss'] = ['把 a.md 刪掉']
        res, _ = self.run_llm([loose])
        self.assertEqual(res['candidates'], [])
        self.assertIn('回測誤觸別類', res['dropped'][0]['why'])
        self.assertIsNone(res['proposal'])

    def test_count_from_history_not_model_hits(self):
        # 審查 M4：歷史只有一句（沒單），模型把它重複兩次當 hit → 不收
        self.say(RENAME[0], ticket=False)
        r = copy.deepcopy(GOOD)
        r['tests']['hit'] = [RENAME[0], RENAME[0]]
        res, _ = self.run_llm([r])
        self.assertEqual(res['candidates'], [])
        self.assertIn('只有 1 句', res['dropped'][0]['why'])

    def test_needs_tickets_and_same_kind(self):
        self.rename(RENAME[0], 'a.md', 'alpha.md')
        self.say(RENAME[1], ticket=False)
        res, _ = self.run_llm([GOOD])
        self.assertIn('不一致', res['dropped'][0]['why'])

    def test_assignee_workflow_must_match_history(self):
        self.three_renames()
        for key, val in (('assignee', 'lead'), ('workflow', 'IMPORT.md')):
            r = copy.deepcopy(GOOD)
            r['handoff'][key] = val
            res, _ = self.run_llm([r])
            self.assertEqual(res['candidates'], [], key)
            self.assertIn('負責人／工作流', res['dropped'][0]['why'])

    def test_group_needs_distinct_sentences(self):
        for _ in range(2):
            self.rename(RENAME[0], 'a.md', 'alpha.md')
        res, _ = self.run_llm([GOOD])
        self.assertIn('只有 1 種寫法', res['dropped'][0]['why'])

    def test_loose_model_rule_dropped_by_probes(self):
        self.three_renames()
        loose = copy.deepcopy(GOOD)
        loose['pattern'] = '把\\s*(?P<a>\\S+\\.md)\\s*改名成\\s*(?P<b>\\S+\\.md)'
        res, _ = self.run_llm([loose])
        self.assertEqual(res['candidates'], [])
        self.assertIn('吃到內建反例', res['dropped'][0]['why'])

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

    def test_words_and_fence_ok(self):
        # 09-25 收尾 S4：前後多字＋``` 圍欄照樣讀得懂
        self.three_renames()
        text = '好的，我歸納出一條：\n```json\n%s\n```\n以上。' % json.dumps({'routes': [GOOD]}, ensure_ascii=False)
        res, _ = self.run_llm(None, text=text)
        self.assertEqual([c['rule']['name'] for c in res['candidates']], ['llm-rename'])

    def test_duplicate_key_reported(self):
        # 外層 routes 出現兩次：整份不收（不撿裡面那一條），印讀不懂、退 0
        self.three_renames()
        text = '{"routes": [%s], "routes": []}' % json.dumps(GOOD, ensure_ascii=False)
        res, _ = self.run_llm(None, text=text)
        self.assertEqual(res['candidates'], [])
        self.assertIn('出現兩次', res['llm']['error'])
        self.assertIn('讀不懂', crystal.render(res))

    def test_rules_missing_fields_dropped(self):
        # 少 pattern、少 handoff、handoff 不是物件、routes 不是陣列：逐條丟，不炸
        self.three_renames()
        no_pattern = {k: v for k, v in GOOD.items() if k != 'pattern'}
        no_handoff = {k: v for k, v in GOOD.items() if k != 'handoff'}
        str_handoff = dict(GOOD, name='strh', handoff='worker-1')
        res, _ = self.run_llm([no_pattern, no_handoff, str_handoff, {}])
        self.assertEqual(res['candidates'], [])
        self.assertEqual(len(res['dropped']), 4)
        res, _ = self.run_llm(None, text='{"routes": {"name": "x"}}')
        self.assertEqual(res['candidates'], [])
        self.assertIn('routes 陣列', res['llm']['error'])


if __name__ == '__main__':
    unittest.main()
