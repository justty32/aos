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
    def test_edges(self):
        a, b = metrics.stamp('2026-10-09T00:00:00+00:00'), metrics.stamp('2026-10-09T08:00:00+08:00')
        self.assertEqual(metrics.parallel([(a,b), (a,None)]), 1)
        c = metrics.stamp('2026-10-09T00:00:01+00:00')
        self.assertEqual(metrics.parallel([(a,c), (c,None)]), 1)
if __name__ == '__main__':
    unittest.main()
