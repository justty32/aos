"""第 1 隊 T-route：門房（aos_team_route）——整句句型、落穿、例句全過才准存、tool 命中不寫成員 input。"""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import aos_team_format as fmt
import aos_team_route as route

PROTO = Path(__file__).resolve().parents[2]
EXAMPLE_ROUTES = PROTO / 'spec' / 'team' / 'examples' / 'routes.json'
ROSTER = {'project': '../p', 'tz': 'Asia/Taipei',
          'members': {'lead': {'template': 'lead', 'mail_to': ['worker-1', 'reviewer', 'human']},
                      'worker-1': {'template': 'worker', 'mail_to': ['lead', 'human']},
                      'reviewer': {'template': 'reviewer', 'mail_to': ['lead', 'human']}}}


def rule(name, pattern, hit, miss, **do):
    r = {'name': name, 'pattern': pattern, 'do': 'tool', 'run': ['task', 'ls'], 'tests': {'hit': hit, 'miss': miss}}
    r.update(do)
    return r


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-team-route-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.team = self.root / 'team'
        self.team.mkdir()
        (self.root / 'p').mkdir()
        self.write_roster(ROSTER)
        self.lay = fmt.Layout(self.team)
        for d in self.lay.skeleton(ROSTER['members']):
            d.mkdir(parents=True, exist_ok=True)
        for n in ROSTER['members']:
            (self.lay.member(n) / 'input').mkdir(parents=True)
        shutil.copy(EXAMPLE_ROUTES, self.lay.routes)

    def write_roster(self, obj):
        (self.team / 'team.json').write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')

    def routes(self, rules, neg=None):
        obj = {'routes': rules}
        if neg is not None:
            obj['negations'] = neg
        return obj

    def set_routes(self, rules, neg=None):
        self.lay.routes.write_text(json.dumps(self.routes(rules, neg), ensure_ascii=False), encoding='utf-8')

    def call(self, fn, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = fn(str(self.team), list(args))
        return code, out.getvalue(), err.getvalue()

    def human_outbox(self):
        return fmt.json_files(self.lay.outbox('human'))

    def inputs(self):
        return [p for n in ROSTER['members'] for p in (self.lay.member(n) / 'input').iterdir()]

    def log(self):
        return [json.loads(l) for l in self.lay.route_log.read_text(encoding='utf-8').splitlines()]


class DecideTests(Base):
    def test_example_rules(self):
        neg, routes = route.load_routes(self.lay.routes)
        self.assertEqual(route.decide('列任務', neg, routes)[:2][0], 'tool')
        self.assertEqual(route.decide('  看一下單子 ', neg, routes)[1]['name'], 'tasks')
        result, r, groups, _ = route.decide('把 workflows 導入 p，照 facts.json', neg, routes)
        self.assertEqual((result, r['name'], groups), ('handoff', 'import', {'project': 'p', 'facts': 'facts.json'}))
        self.assertEqual(route.decide('列任務給 bob 看', neg, routes)[0], 'lead')    # 整句，不是關鍵字
        self.assertEqual(route.decide('你好', neg, routes)[3], '沒有規則命中')

    def test_two_hits_and_negation_fall_through(self):
        neg, routes = fmt.validate_routes(self.routes([
            rule('a', '.*heartbeat.*', ['導入 heartbeat'], ['x']),
            rule('b', '導入 (?P<pack>\\w+)', ['導入 dev'], ['y'])]))
        result, r, _, why = route.decide('導入 heartbeat', neg, routes)
        self.assertEqual((result, r), ('lead', None))
        self.assertIn('命中兩條以上', why)
        result, _, _, why = route.decide('不要導入 heartbeat 包', neg, routes)
        self.assertEqual(result, 'lead')
        self.assertIn('否定詞', why)

    def test_empty_group_is_not_a_hit(self):
        neg, routes = fmt.validate_routes(self.routes([rule('a', '看(?P<x>\\w*)', ['看信'], ['聽'])]))
        self.assertEqual(route.decide('看', neg, routes)[0], 'lead')
        self.assertEqual(route.decide('看信', neg, routes)[0], 'tool')

    def test_fill(self):
        self.assertEqual(route.fill({'a': ['{x} 與 {y}', {'b': '{x}'}], 'n': 3}, {'x': '1'}),
                         {'a': ['1 與 {y}', {'b': '1'}], 'n': 3})

    def test_run_tests(self):
        neg, routes = route.load_routes(self.lay.routes)
        self.assertTrue(all(ok for _, ok, _ in route.run_tests(neg, routes)))
        neg, routes = fmt.validate_routes(self.routes([
            rule('a', '列任務', ['列任務', '列單子'], ['列任務吧']),
            rule('b', '列.*', ['列東西'], ['列任務'])]))
        res = dict((n, (ok, f)) for n, ok, f in route.run_tests(neg, routes))
        self.assertFalse(res['a'][0])          # 列任務 同時命中 b → 落穿；列單子 沒命中
        self.assertEqual(len(res['a'][1]), 2)
        self.assertFalse(res['b'][0])          # miss 列任務 卻命中 b


class AskTests(Base):
    def test_tool_hit_writes_no_input(self):
        code, out, _ = self.call(route.cmd_ask, '列任務')
        self.assertEqual(code, 0)
        self.assertIn('沒有進行中的任務單', out)
        self.assertEqual(self.inputs(), [])
        self.assertEqual(self.human_outbox(), [])
        self.assertEqual(self.log()[-1]['result'], 'tool')
        self.assertEqual(self.log()[-1]['route'], 'tasks')

    def test_tool_run_fills_groups(self):
        """T5：tool 規則的 run 也換 {群組名}：「每 2m 數一次 md 檔」＝寄一份 routine add 申請，--every 是 2m。"""
        code, out, _ = self.call(route.cmd_ask, '每 2m 數一次 md 檔')
        self.assertEqual(code, 0, out)
        files = self.human_outbox()
        self.assertEqual(len(files), 1)
        kind, req = fmt.read_outbox_file(files[0], fmt.load_roster(self.team))
        self.assertEqual((req['kind'], req['op'], req['name'], req['every'], req['to']),
                         ('routine', 'add', 'count-md', '2m', 'worker-1'))
        self.assertEqual(req['done_when'], [{'kind': 'file_exists', 'path': 'notes/md-count.txt'}])
        self.assertEqual(self.inputs(), [])
        self.assertEqual(self.log()[-1]['route'], 'count-md')

    def test_handoff_request_is_valid(self):
        code, out, _ = self.call(route.cmd_ask, '把', 'workflows', '導入', 'p，照', 'facts.json')
        self.assertEqual(code, 0, out)
        self.assertIn('開單申請已交給郵差', out)
        files = self.human_outbox()
        self.assertEqual(len(files), 1)
        kind, req = fmt.read_outbox_file(files[0], fmt.load_roster(self.team))
        self.assertEqual((kind, req['kind'], req['assignee'], req['facts']), ('request', 'handoff', 'worker-1', 'facts.json'))
        self.assertIn('人說的是 p）', req['goal'])
        self.assertEqual(self.inputs(), [])
        self.assertEqual(self.log()[-1]['result'], 'handoff')

    def test_fall_through_to_lead(self):
        code, out, _ = self.call(route.cmd_ask, '不要把 workflows 導入 p，照 facts.json')
        self.assertEqual(code, 0)
        self.assertIn('已交給領隊 lead', out)
        kind, ltr = fmt.read_outbox_file(self.human_outbox()[0], fmt.load_roster(self.team))
        self.assertEqual((kind, ltr['to'], ltr['status'], ltr['reply_to'], ltr['rev']),
                         ('letter', 'lead', 'REQUEST', None, None))
        self.assertEqual(self.log()[-1]['result'], 'lead')
        self.assertIn('否定詞', self.log()[-1]['why'])

    def test_no_routes_file_all_fall_through(self):
        self.lay.routes.unlink()
        code, out, _ = self.call(route.cmd_ask, '列任務')
        self.assertEqual(code, 0)
        self.assertIn('沒有規則命中', out)

    def test_no_lead(self):
        roster = json.loads(json.dumps(ROSTER))
        del roster['members']['lead']
        for m in roster['members'].values():
            m['mail_to'] = ['human']
        self.write_roster(roster)
        with self.assertRaises(fmt.TeamError) as cm:
            self.call(route.cmd_ask, '你好')
        self.assertEqual(cm.exception.code, 'NoLead')
        self.assertEqual(self.human_outbox(), [])

    def test_failing_examples_refuse_ask(self):
        self.set_routes([rule('a', '列任務', ['列單子'], ['x'])])
        with self.assertRaises(fmt.TeamError) as cm:
            self.call(route.cmd_ask, '列任務')
        self.assertEqual(cm.exception.code, 'RoutesFailed')
        self.assertIn('route test', cm.exception.msg)
        self.assertEqual(self.human_outbox(), [])

    def test_pack_tool(self):
        packs = self.root / 'packs'
        (packs / 'fake').mkdir(parents=True)
        (packs / 'fake' / 'fake.json').write_text(json.dumps([{
            'type': 'function', 'function': {'name': 'echo', 'parameters': {'type': 'object'}},
            '_meta': {'argv': ['tools/fake/run']}}]))
        run = packs / 'fake' / 'run'
        run.write_text('#!/bin/sh\necho "root=$AOS_TOOL_ROOT cwd=$(pwd)"\ncat\necho\nexit 3\n')
        run.chmod(0o755)
        old = route.PACKAGES
        route.PACKAGES = packs
        self.addCleanup(setattr, route, 'PACKAGES', old)
        r = rule('lint', 'lint', ['lint'], ['lint 一下'], tool='fake/echo', args={'strict': True})
        del r['run']
        self.set_routes([r])
        obj = json.loads(self.lay.routes.read_text())
        code, out, _ = self.call(route.cmd_ask, 'lint')
        self.assertEqual(code, 3)
        self.assertIn('root=%s' % (self.root / 'p').resolve(), out)
        self.assertIn('cwd=%s' % self.team, out)
        self.assertIn('{"strict": true}', out)
        self.assertEqual(self.inputs(), [])
        # 找不到那支
        obj['routes'][0]['tool'] = 'fake/nope'
        self.lay.routes.write_text(json.dumps(obj))
        with self.assertRaises(fmt.TeamError) as cm:
            self.call(route.cmd_ask, 'lint')
        self.assertEqual(cm.exception.code, 'NotFound')


class RouteCmdTests(Base):
    def test_test_and_save(self):
        code, out, _ = self.call(route.cmd_route, 'test')
        self.assertEqual(code, 0)
        self.assertIn('PASS import', out)
        bad = self.root / 'bad.json'
        bad.write_text(json.dumps(self.routes([rule('a', '列任務', ['列單子'], ['x'])])), encoding='utf-8')
        before = self.lay.routes.read_bytes()
        code, out, _ = self.call(route.cmd_route, 'save', str(bad))
        self.assertEqual(code, 1)
        self.assertIn('FAIL a', out)
        self.assertEqual(self.lay.routes.read_bytes(), before)
        code, _, _ = self.call(route.cmd_route, 'test', '--file', str(bad))
        self.assertEqual(code, 1)
        good = self.root / 'good.json'
        good.write_text(json.dumps(self.routes([rule('a', '列任務', ['列任務'], ['x'])])), encoding='utf-8')
        code, out, _ = self.call(route.cmd_route, 'save', str(good))
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(self.lay.routes.read_text())['routes'][0]['name'], 'a')
        self.assertTrue(self.lay.routes.read_text().startswith('{\n  '))

    def test_bad_regex_is_format_error(self):
        bad = self.root / 'bad.json'
        bad.write_text(json.dumps(self.routes([rule('a', '(', ['x'], ['y'])])), encoding='utf-8')
        with self.assertRaises(fmt.TeamError) as cm:
            self.call(route.cmd_route, 'save', str(bad))
        self.assertIn('正規式', cm.exception.msg)

    def test_cli_end_to_end(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        cli = str(PROTO / 'cli' / 'aos-team')
        r = subprocess.run([sys.executable, cli, 'ask', '你好', '--target', str(self.team)], capture_output=True,
                           text=True, timeout=30, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('已交給領隊 lead', r.stdout)
        r = subprocess.run([sys.executable, cli, 'route', 'test'], capture_output=True, text=True, timeout=30,
                           env=dict(env, AOS_TEAM_HOME=str(self.team)))
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run([sys.executable, cli, 'route', 'save', '--target', str(self.team)], capture_output=True,
                           text=True, timeout=30, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertIn('Usage', r.stderr)


if __name__ == '__main__':
    unittest.main()
