"""固定證據、唯讀與 R1 基線。"""
import csv, importlib.util, io, json, shutil, subprocess, sys, tempfile, unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
BASELINE = PACKAGE / 'baseline/r1'
_spec = importlib.util.spec_from_file_location('aos7_metrics', PACKAGE / 'aos7_metrics.py')
metrics = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(metrics)
class TestMetrics(unittest.TestCase):
    def output(self, *paths):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(metrics.main(['job', *map(str, paths), '--json']), 0)
        return out.getvalue().encode()
    def test_fixture(self):
        s = metrics.scan(HERE / 'fixture', 10)
        a, b = s['flows']
        self.assertEqual(a['call_ids'], ['a', 'b'])
        self.assertEqual(a['jobs'], ['r1_12345678'])
        self.assertEqual(a['calls'], 2)
        self.assertEqual(a['tokens'], dict(used=80, reserve=300, pending=0, pending_reserve=0, prompt=60, completion=20, reasoning=3, cached=4, prompt_own=40, overhead_total=20))
        self.assertEqual(a['max_parallel'], 2)
        self.assertEqual(a['seconds'], 10)
        self.assertEqual(a['start'], '2026-10-09T12:00:00')
        self.assertEqual(a['end'], '2026-10-09T12:00:10')
        self.assertFalse(a['open'])
        self.assertEqual(a['retries'], dict(reask=1, resends=1, extra_tries=1, adopted=1, total=4))
        self.assertEqual(b['tokens'], dict(used=0, reserve=300, pending=1, pending_reserve=300, prompt=0, completion=0, reasoning=0, cached=0, prompt_own=0, overhead_total=0))
        self.assertEqual((b['calls'], b['max_parallel'], b['seconds'], b['open']), (1, 1, None, True))
        self.assertEqual(b['retries'], dict(reask=0, resends=0, extra_tries=0, adopted=0, total=0))
        self.assertEqual((s['calls'], s['max_parallel'], s['window_unknown']), (3, 3, 0))
        self.assertEqual(s['seconds'], dict(mean=10, max=10, open=1))
        self.assertEqual(s['tokens'], dict(a['tokens'], reserve=600, pending=1, pending_reserve=300))
        self.assertEqual(s['retries'], a['retries'])
        self.assertEqual(s['unreadable'], ['jobs/r1_12345678/results/s/bad.json'])
    def test_readonly(self):
        def tree(root):
            return {(p.relative_to(root).as_posix(), p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob('*')}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'node'
            shutil.copytree(HERE / 'fixture', root)
            before = tree(root)
            metrics.scan(root)
            self.output(root)
            self.assertEqual(tree(root), before)
    def test_repeatable(self):
        for paths in [(HERE / 'fixture',), tuple(sorted(BASELINE.iterdir()))]:
            self.assertEqual(self.output(*paths), self.output(*paths))
        total = json.loads(self.output(HERE / 'fixture', HERE / 'fixture'))['total']
        self.assertEqual((total['flows'], total['calls'], total['max_parallel']), (4, 6, 6))
        self.assertEqual(total['tokens']['used'], 160)
    def test_baseline(self):
        evidence = PACKAGE.parents[1] / 'notes/play/2026-10-09-real-ai/evidence/calls.csv'
        with evidence.open() as f:
            rows = {r['run']: r for r in csv.DictReader(f)}
        nodes = sorted(BASELINE.iterdir())
        self.assertEqual(len(nodes), 13)
        used = 0
        for node in nodes:
            s = metrics.scan(node)
            self.assertEqual(s['unreadable'], [])
            if node.name == 'litellm-smoke':
                self.assertEqual(s['tokens']['prompt'], 1644)
                continue
            f = s['flows'][0]
            self.assertEqual((len(s['flows']), s['calls'], s['max_parallel'], s['retries']['total'], f['open']), (1, 1, 1, 0, False))
            self.assertGreater(f['seconds'], 0)
            for key, column in [('used','used'), ('prompt','prompt_tokens'), ('completion','completion_tokens'), ('reasoning','reasoning_tokens'), ('cached','cached_tokens')]:
                self.assertEqual(s['tokens'][key], int(rows[node.name][column]))
            used += s['tokens']['used']
        self.assertEqual(used, 30739)
    def test_cli(self):
        cli = [sys.executable, str(PACKAGE/'aos7-metrics'), 'job', str(BASELINE/'loop-gpt-6-sol')]
        p = subprocess.run(cli + ['--detail', '--overhead', '1644'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertIn('代理 1644＋自己 721', p.stdout)
        p = subprocess.run(cli, capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout), (0, 'loop-gpt-6-sol：1 件工作｜每件用 2590 token｜同時最多 1 個在問模型｜花 11.486 秒｜重試 0 次\n'))
        p = subprocess.run(cli[:2] + ['--help'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        for word in ('PATH', '--overhead', '--detail', '--json', 'max_parallel'):
            self.assertIn(word, p.stdout)
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(io.StringIO()) as err:
            self.assertEqual(metrics.main(['job', tmp+'/missing']), 2)
            self.assertEqual(len(err.getvalue().splitlines()), 1)
    def test_error_lines(self):
        """檔案 PATH 與 argparse 錯誤都只印一行接法。"""
        cli = [sys.executable, str(PACKAGE / 'aos7-metrics')]
        for args in (('job', __file__), ('job', HERE, '--overhead', '-1'),
                     ('job', HERE, '--unknown'), ('job',),
                     ('job', HERE, '--overhead', 'abc'), ('unknown', HERE)):
            with self.subTest(args=args):
                p = subprocess.run(cli + list(map(str, args)), capture_output=True, text=True)
                lines = p.stderr.splitlines()
                self.assertEqual(p.returncode, 2)
                self.assertEqual(p.stdout, '')
                self.assertEqual(len(lines), 1)
                prefix = 'aos7-metrics: 不是資料夾：' if args[1:] == (__file__,) else 'aos7-metrics: 參數不對：'
                self.assertTrue(lines[0].startswith(prefix), lines)
                self.assertIn('。', lines[0])
                self.assertIn('例：', lines[0])
                self.assertNotIn('aos7-metrics：', lines[0])
                self.assertNotIn('usage', lines[0])

    def test_plain(self):
        s = metrics.scan(HERE / 'fixture')
        self.assertEqual(metrics.plain(s), 'fixture：2 件工作｜平均每件用 40 token｜同時最多 3 個在問模型｜平均花 10.0 秒（最長 10.0 秒），另有 1 件還沒結束｜重試 4 次｜1 次還沒結帳｜1 個檔讀不了已跳過')
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn('沒找到 AI 工作紀錄', metrics.plain(metrics.scan(tmp)))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(metrics.main(['job', tmp, tmp]), 0)
            self.assertEqual(len(out.getvalue().splitlines()), 3)
    def evidence(self, root, files):
        for name, data in files.items():
            p = root / name; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(data if name.endswith('.jsonl') else json.dumps(data))
    def scan_files(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            self.evidence(Path(tmp), files)
            return metrics.scan(tmp)
    def test_nested_shapes(self):
        cases = [('budget/b/ledger.json', {'ops': x}) for x in (None, [], 1)]
        cases += [('budget/b/ledger.json', {'ops': {'bad': None, 'good': {'key': {'request': 'c'}, 'amount': 5}}}),
                  ('budget/b/ledger.json', {'ops': {'k': {'key': None}}}),
                  ('budget/b/ledger.json', {'ops': {'k': {'key': {'request': 'c'}, 'reserve': None, 'settle': None}}}),
                  ('llmcall/b/c/raw.json', {'reply': None}), ('llmcall/b/c/receipt.json', {'used': 3, 'settle': None}),
                  ('events/must.active.jsonl', '{"kind":"author.request","payload":null}'),
                  ('author/req/r/receipt.json', {'versions': {'x': None}}),
                  ('jobs/r_12345678/frame.json', {'tries': None, 'resends': []}),
                  ('llmcall/b/c/raw.json', {'reply': {'usage': {'prompt_tokens': 2, 'completion_tokens_details': None, 'prompt_tokens_details': None}}})]
        cases += [('llmcall/b/c/request.json', {'call_id': x, 'reserve': 5}) for x in (None, 7, [])]
        for name, data in cases:
            with self.subTest(name=name, data=data):
                s = self.scan_files( {'llmcall/b/c/request.json': {'reserve': 5}, 'author/req/r/receipt.json': {}, name: data})
                self.assertEqual((s['calls'], s['tokens']['reserve'], s['tokens']['used']), (1, 5, data.get('used', 0) if isinstance(data, dict) else 0))
                self.assertEqual((s['tokens']['reasoning'], s['tokens']['cached'], s['retries']['total']), (0, 0, 0))
                self.assertEqual(s['tokens']['prompt'], 2 if name.endswith('raw.json') and isinstance(data.get('reply'), dict) else 0)
                self.assertEqual([f['call_ids'] for f in s['flows'] if f['calls']], [['c']])
                if name.endswith('ledger.json') and isinstance(data['ops'], dict):
                    self.assertEqual(s['tokens']['pending'], int('good' in data['ops'] or data['ops'].get('k', {}).get('key') == {'request': 'c'}))
                self.assertEqual(s['unreadable'], [])
    def test_elapsed_overflow(self):
        for elapsed in (1e20, 1e12):
            with self.subTest(elapsed=elapsed):
                s = self.scan_files( {'llmcall/b/c/raw.json': {'at': '2026-10-09T00:00:02', 'reply': {'elapsed': elapsed}},
                                     'budget/b/ledger.json': {'ops': {'k': {'key': {'request': 'c'}, 'reserve': {'at': '2026-10-09T00:00:00'}}}},
                                     'llmcall/b/c/receipt.json': {'settle': {'at': '2026-10-09T00:00:02'}}})
                self.assertEqual((s['calls'], s['max_parallel'], s['window_unknown'], s['flows'][0]['seconds']), (1, 1, 0, 2))
    def test_gateway_done_pending(self):
        s = self.scan_files({'llmcall/b/c/request.json': {'reserve': 5},
                             'budget/b/gateway/k.json': {'call_id': 'c', 'stage': 'done', 'billing': 'pending', 'used': 2}})
        self.assertEqual((s['calls'], s['tokens']['used'], s['tokens']['pending'], s['tokens']['pending_reserve']), (1, 2, 1, 5))
    def test_subdirectory_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.evidence(root, {'llmcall/b/c/request.json': {'reserve': 5}, 'llmcall/b/c/raw.json': '{',
                                 'budget/b/ledger.json': {'ops': {'k': {'key': {'request': 'c'}}}},
                                 'budget/b/gateway/k.json': {'call_id': 'c', 'stage': 'done', 'used': 2}})
            for scope, calls, used, bad in [('llmcall/b/c', 1, 0, ['raw.json']), ('budget/b', 1, 2, []), ('budget/b/gateway', 1, 2, [])]:
                with self.subTest(scope=scope):
                    s = metrics.scan(root / scope)
                    self.assertEqual((s['calls'], s['tokens']['used'], s['unreadable']), (calls, used, bad))
    def test_jsonl_bad_lines(self):
        rows = [json.dumps({'kind': 'author.request', 'payload': {'rid': 'r'}, 'at': f'2026-10-09T00:00:0{n}'}) for n in (2, 1)]
        s = self.scan_files({'author/req/r/receipt.json': {'closed': True},
                             'jobs/r_12345678/frame.json': {'closed': True, 'at': '2026-10-09T00:00:03'},
                             'events/must.active.jsonl': rows[0] + '\n{bad\n[]\n' + rows[1] + '\n{'})
        self.assertEqual((s['calls'], s['flows'][0]['seconds'], s['seconds']['open']), (0, 2, 0))
        self.assertEqual(s['unreadable'], ['events/must.active.jsonl'])
    def run_metrics(self, *args):
        p = subprocess.run([sys.executable, '-B', str(PACKAGE / 'aos7-metrics'), *map(str, args)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout
    def test_by_baseline(self):
        node = BASELINE / 'loop-gpt-6-sol'
        s = json.loads(self.run_metrics('job', node, '--by', 'model', '--json'))['scopes'][0]
        self.assertEqual(s['by'], dict(field='model', groups=[dict(key='chatgpt-gpt-6-sol', calls=1, used=2590, overrun=0)]))
        self.assertEqual(s['ledger'], dict(used=2590, receipts=2590, diff=0, gaps=0, bad=0, unbooked=0, unbooked_used=0))
        data = json.loads(self.run_metrics('job', *sorted(BASELINE.iterdir()), '--by', 'model', '--json'))
        self.assertEqual(len(data['scopes']), 13)
        groups = data['total']['by']['groups']
        self.assertEqual(len(groups), 6)
        self.assertEqual(sum(g['calls'] for g in groups), sum(s['calls'] for s in data['scopes']))
        self.assertEqual(sum(g['used'] for g in groups), 32388)
        self.assertEqual(groups[4], dict(key='chatgpt-gpt-6-sol', calls=4, used=9449, overrun=0))
        for s in data['scopes']:
            # smoke 沒有 ledger；其他 12 個 scope 都已結帳、帳差為 0。
            self.assertEqual(s['ledger']['diff'], None if s['scope'] == 'litellm-smoke' else 0)
            self.assertEqual(s['ledger']['gaps'], 0)
        # 合計只比有帳的呼叫：smoke 的 1649 不算進回條，帳差仍 0。
        self.assertEqual(data['total']['ledger'], dict(used=30739, receipts=30739, diff=0, gaps=0, bad=0, unbooked=1, unbooked_used=1649))
        total_line = self.run_metrics('job', *sorted(BASELINE.iterdir()), '--by', 'model').splitlines()[-7]
        self.assertTrue(total_line.endswith('｜帳差 0（帳 30739－回條 30739；另 1 次呼叫沒帳、用 1649 token）、缺口 0'), total_line)
    def test_by_default_compatibility(self):
        nodes = sorted(BASELINE.iterdir())
        output = self.run_metrics('job', *nodes)
        readme = (PACKAGE / 'README.md').read_text()
        blocks = readme.split('```text\n')
        for before, text in zip(blocks, blocks[1:]):
            if '--by' in before.rsplit('```sh', 1)[-1]:
                continue  # --by 範例是細節行，不是預設行
            for line in text.split('```')[0].splitlines():
                if not line.startswith('…'):
                    self.assertIn(line + '\n', output)
        self.assertEqual(self.run_metrics('job', BASELINE / 'loop-gpt-6-sol'),
                         'loop-gpt-6-sol：1 件工作｜每件用 2590 token｜同時最多 1 個在問模型｜花 11.486 秒｜重試 0 次\n')
        times = [1.67, 8.739, 15.291, 9.167, 9.637, 6.918, 6.806, 7.328, 8.232, 11.486, 10.799, 10.157, 9.043]
        used = [1649, 2504, 2688, 2505, 2502, 2551, 2499, 2558, 2566, 2590, 2566, 2627, 2583]
        expected = ''.join(f'{n.name}：1 件工作｜每件用 {u} token｜同時最多 1 個在問模型｜花 {t} 秒｜重試 0 次\n' for n, u, t in zip(nodes, used, times))
        expected += '合計：13 件工作｜平均每件用 2491 token｜同時最多 6 個在問模型｜平均花 8.867 秒（最長 15.291 秒）｜重試 0 次\n'
        self.assertEqual(output.encode(), expected.encode())
        data = json.loads(self.run_metrics('job', *nodes, '--json'))
        for s in data['scopes'] + [data['total']]:
            self.assertNotIn('by', s)
            self.assertIn(s['ledger']['diff'], (0, None))
        self.assertEqual(data['total']['ledger']['diff'], 0)
    def test_by_usage_scenario(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'node'
            files = {'budget/b/ledger.json': {'used': 13}, 'llmcall/b/bad/request.json': '{'}
            for cid, model, holder, at, receipt in [
                ('a', 'm1', 'h1', '2026-10-09T23:20:00+08:00', {'used': 3}),
                ('b', 'm2', 'h2', '2026-10-10T00:20:00+08:00', {'used': 7, 'overrun': 2}),
                ('c', 'm1', 'h2', '2026-10-10T00:30:00+08:00', None)]:
                prefix = f'llmcall/b/{cid}/'
                files[prefix + 'request.json'] = {'request': {'litellm': {'model': model}}, 'holder': holder}
                files[prefix + 'raw.json'] = {'at': at}
                if receipt is not None:
                    files[prefix + 'receipt.json'] = receipt
            self.evidence(root, files)
            (root / 'llmcall/b/bad/request.json').write_text('{')
            (root / 'llmcall/b/a/request.json').chmod(0o440)
            def snapshot():
                return {p.relative_to(root).as_posix(): (p.stat().st_mode, p.read_bytes() if p.is_file() else None) for p in [root, *root.rglob('*')]}
            before = snapshot()
            expected = {
                'model': [('m1', 2, 3, 0), ('m2', 1, 7, 2)],
                'holder': [('h1', 1, 3, 0), ('h2', 2, 7, 2)],
                'day': [('2026-10-09', 1, 3, 0), ('2026-10-10', 2, 7, 2)],
                'hour': [('2026-10-09T23', 1, 3, 0), ('2026-10-10T00', 2, 7, 2)]}
            for field, rows in expected.items():
                with self.subTest(field=field):
                    data = json.loads(self.run_metrics('job', root, '--by', field, '--json'))
                    s = data['scopes'][0]
                    self.assertEqual(s['by'], dict(field=field, groups=[dict(zip(('key', 'calls', 'used', 'overrun'), row)) for row in rows]))
                    self.assertEqual(s['unreadable'], ['llmcall/b/bad/request.json'])
                    self.assertEqual(s['ledger'], dict(used=13, receipts=10, diff=3, gaps=2, bad=0, unbooked=0, unbooked_used=0))
                    self.assertEqual(data['total']['by'], s['by'])
                    self.assertEqual(data['total']['ledger'], s['ledger'])
            detail = self.run_metrics('job', root, '--detail')
            self.assertTrue(detail.rstrip().endswith('｜重試 0｜帳差 3（帳 13－回條 10）、缺口 2'))
            self.assertEqual(snapshot(), before)
    def test_by_fallbacks_and_ledgers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {'budget/b/ledger.json': {'used': 5, 'ops': {}}, 'budget/c/ledger.json': {'used': 8}}
            # raw → done → receipt.settle → op.settle → op.reserve → '-'，不把數字当日期。
            for i, at in enumerate(['2026-10-09T23:00:00-05:00'] * 5 + [None]):
                cid = str(i); prefix = f'llmcall/b/{cid}/'
                files[prefix + 'request.json'] = {'request': {'litellm': {'model': 7}, 'model': 'fallback'} if i == 0 else {}, 'endpoint': 'endpoint' if i == 1 else None}
                files[prefix + 'raw.json'] = {'at': at if i == 0 else 123}
                op = {'key': {'request': cid, 'holder': 'ledger-holder'}, 'settle': {'overrun': 2}}
                files['budget/b/ledger.json']['ops'][cid] = op
                if i == 1:
                    files[f'budget/b/gateway/{cid}.json'] = {'call_id': cid, 'stage': 'done', 'at': at, 'used': 4}
                else:
                    files[prefix + 'receipt.json'] = {'used': float('nan') if i == 5 else 1, 'overrun': float('inf') if i == 5 else 0,
                                                    'settle': {'at': at if i == 2 else None}}
                if i in (3, 4):
                    op['settle' if i == 3 else 'reserve'] = {'at': at, 'overrun': 2}
            # Receipt 優先於 gateway；無 request 的 ledger call 不加入分組。
            files['budget/b/gateway/0.json'] = {'call_id': '0', 'stage': 'done', 'used': 99, 'overrun': 99}
            files['budget/b/ledger.json']['ops']['orphan'] = {'key': {'request': 'orphan'}}
            self.evidence(root, files)
            for field, expected in [('model', [('?', 4, 3, 0), ('endpoint', 1, 4, 2), ('fallback', 1, 1, 0)]),
                                    ('holder', [('ledger-holder', 6, 8, 2)]),
                                    ('day', [('-', 1, 0, 0), ('2026-10-09', 5, 8, 2)]),
                                    ('hour', [('-', 1, 0, 0), ('2026-10-09T23', 5, 8, 2)])]:
                s = json.loads(self.run_metrics('job', root, '--by', field, '--json'))['scopes'][0]
                self.assertEqual(s['by']['groups'], [dict(zip(('key', 'calls', 'used', 'overrun'), row)) for row in expected])
                # 回條只算真 receipt（call 1 只有 gateway done → 不算回條、算缺口）；call 1 超支再算一個缺口。
                self.assertEqual(s['ledger'], dict(used=13, receipts=4, diff=9, gaps=2, bad=0, unbooked=0, unbooked_used=0))
            # 帳檔在卻壞（used 非整數或整檔壞）→ 帳差不明，不能當成沒帳而報 0。
            (root / 'budget/d').mkdir()
            (root / 'budget/d/ledger.json').write_text(json.dumps({'used': True}))
            (root / 'budget/e').mkdir()
            (root / 'budget/e/ledger.json').write_text('{')
            data = json.loads(self.run_metrics('job', root, root, '--json'))
            self.assertEqual(data['total']['ledger'], dict(used=None, receipts=8, diff=None, gaps=4, bad=4, unbooked=0, unbooked_used=0))
            self.assertIn('｜帳差 不明（2 個帳檔讀不了）、缺口 2', self.run_metrics('job', root, '--detail'))
            for b in ('b', 'c', 'd', 'e'):
                (root / f'budget/{b}/ledger.json').unlink()
            data = json.loads(self.run_metrics('job', root, root, '--json'))
            self.assertEqual(data['total']['ledger'], dict(used=None, receipts=0, diff=None, gaps=2, bad=0, unbooked=12, unbooked_used=8))  # 帳刪了，op 的超支也跟著不見
            self.assertIn('｜帳差 無帳、缺口 1', self.run_metrics('job', root, '--detail'))
    def test_by_cli(self):
        cli = [sys.executable, '-B', str(PACKAGE / 'aos7-metrics')]
        p = subprocess.run(cli + ['job', str(BASELINE), '--by', 'bogus'], capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout, len(p.stderr.splitlines())), (2, '', 1))
        self.assertTrue(p.stderr.startswith('aos7-metrics: '))
        text = self.run_metrics('job', BASELINE / 'loop-gpt-6-sol', '--by', 'model')
        self.assertEqual(text.splitlines()[1], '　　model chatgpt-gpt-6-sol：1 次呼叫、用 2590 token、超支 0')
        self.assertIn('｜帳差 0（帳 2590－回條 2590）、缺口 0', text.splitlines()[0])
        multi = self.run_metrics('job', BASELINE / 'loop-gpt-6-sol', BASELINE / 'loop-gpt-6-sol-r2', '--by', 'model')
        self.assertEqual(multi.splitlines()[-1], '　　model chatgpt-gpt-6-sol：2 次呼叫、用 5217 token、超支 0')
        help_text = self.run_metrics('--help')
        self.assertIn('FIELD 是 model／holder／day／hour', ' '.join(help_text.split()))
        self.assertIn('與帳差（帳上 used 減有帳呼叫的回條合計）、缺口', help_text)
        self.assertLessEqual(len(help_text.splitlines()), 30)
    def test_usage_stub_redirects(self):
        # 舊 aos7-usage 已封存到 archive/usage/，原處只留轉址：一行、退 1、不讀參數。
        stub = PACKAGE.parents[1] / 'packs/usage/bin/aos7-usage'
        p = subprocess.run([sys.executable, '-B', str(stub), str(BASELINE)], capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout), (1, ''))
        self.assertEqual(p.stderr, f'aos7-usage: 這個工具已停用，功能併進 aos7-metrics。看每個模型用多少，從 repo 根跑：python3 proto7-2/modules/metrics/aos7-metrics job {BASELINE} --by model（說明見 proto7-2/modules/metrics/README.md）\n')
        p = subprocess.run([sys.executable, '-B', str(stub)], capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout, len(p.stderr.splitlines())), (1, '', 1))
        self.assertIn('aos7-metrics job PATH --by model', p.stderr)
    def test_edges(self):
        a, b = metrics.stamp('2026-10-09T00:00:00+00:00'), metrics.stamp('2026-10-09T08:00:00+08:00')
        self.assertEqual(metrics.parallel([(a,b), (a,None)]), 1)
        c = metrics.stamp('2026-10-09T00:00:01+00:00')
        self.assertEqual(metrics.parallel([(a,c), (c,None)]), 1)
if __name__ == '__main__':
    unittest.main()
