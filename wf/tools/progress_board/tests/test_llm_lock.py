"""Verify cross-process model exclusion, bounded waiting and refreshed eligibility offline."""
import contextlib
import io
import json
import multiprocessing
import time
from unittest.mock import patch
from eli5_support import OfflineBoard, WORDS
import eli5
import dash
from llm_lock import llm_lock
import summarize

CTX = multiprocessing.get_context('fork')


def hold(board, ready, release):
    with llm_lock(board) as acquired:
        assert acquired
        ready.set()
        release.wait(5)


class LockTests(OfflineBoard):
    def process(self, target, *args):
        child = CTX.Process(target=target, args=args)
        child.start()
        self.addCleanup(lambda: child.is_alive() and child.terminate())
        return child

    def join(self, child):
        child.join(5)
        self.assertEqual(child.exitcode, 0)

    def generators(self):
        return (summarize.maybe_summarize, eli5.maybe_main, eli5.maybe_detail)

    def test_all_paths_skip_when_other_process_holds_lock_and_timeout_warns(self):
        ready, release = CTX.Event(), CTX.Event()
        child = self.process(hold, self.board, ready, release)
        self.assertTrue(ready.wait(3))
        for generate in self.generators():
            started = time.monotonic()
            self.assertEqual(generate(self.board, self.cfg, force=True), 'skipped-busy')
            self.assertLess(time.monotonic() - started, 0.5)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(generate(self.board, self.cfg, force=True,
                                          wait_timeout=0.03), 'skipped-busy')
            self.assertEqual(stderr.getvalue(), 'dash: warning: busy, skipped\n')
        self.assertEqual(self.calls, [])
        release.set()
        self.join(child)
        self.assertEqual(eli5.maybe_main(self.board, self.cfg), 'ok')
        self.assertTrue(self.stored('main')['generated_at'])

    def test_waiting_process_rechecks_change_and_interval_after_model_finishes(self):
        for kind, generate in zip(('summary', 'main', 'detail'), self.generators()):
            for interval in (0, 4):
                with self.subTest(kind=kind, interval=interval):
                    self.cfg['summary'].update(enabled=True, min_interval_min=interval,
                                               eli5_min_interval_min=interval)
                    self.events.append(self.event('alpha', f'New evidence {kind} {interval}'))
                    self.flush()
                    ready, release = CTX.Event(), CTX.Event()
                    calls = self.board / f'{kind}-{interval}-calls.txt'
                    original = self.endpoint

                    def endpoint(request, **kwargs):
                        with calls.open('a') as stream:
                            stream.write('called\n')
                        ready.set()
                        if not release.wait(4):
                            raise AssertionError('Timed out waiting for test release')
                        if kind == 'summary':
                            return io.BytesIO(json.dumps({'choices': [{'message': {
                                'content': WORDS}}]}).encode())
                        return original(request, **kwargs)

                    # Force the first invocation so each subcase has work even with an old cache.
                    with patch('urllib.request.urlopen', side_effect=endpoint):
                        first = self.process(generate, self.board, self.cfg, True)
                        self.assertTrue(ready.wait(3))
                        def wait_and_generate():
                            result = generate(self.board, self.cfg, wait_timeout=2)
                            assert result in ('skipped', 'skipped-nochange', 'skipped-interval'), result
                        second = self.process(wait_and_generate)
                        time.sleep(0.05)
                        release.set()
                        self.join(first)
                        self.join(second)
                    self.assertEqual(calls.read_text().splitlines(), ['called'])
                    path = 'summary/cursor.json' if kind == 'summary' else f'eli5/{kind}.json'
                    self.assertTrue(json.loads((self.board / path).read_text()))

    def test_eli5_reloads_evidence_after_waiting_and_preserves_force_all(self):
        stale = eli5.input_snapshot(self.board, self.cfg)
        self.write('summary/latest.md', 'New evidence after snapshot.')
        self.assertEqual(eli5.maybe_main(self.board, self.cfg, inputs=stale), 'ok')
        self.assertEqual(self.calls[-1]['summary'], 'New evidence after snapshot.')
        self.assertEqual(eli5.maybe_main(self.board, self.cfg, force=True), 'skipped')
        self.assertEqual(eli5.maybe_main(self.board, self.cfg, force=True, all_items=True), 'ok')

    def test_dash_cli_eli5_uses_one_wait_budget_and_stops_after_busy(self):
        for result, elapsed in (('skipped-busy', 120), ('ok', 45), ('ok', 150)):
            with self.subTest(main_result=result, elapsed=elapsed), \
                 patch('dash.sys.argv', ['dash.py', 'eli5']), \
                 patch('dash.board_path', return_value=self.board), \
                 patch('dash.load_config', return_value=self.cfg), \
                 patch('dash.input_snapshot', return_value={}), \
                 patch('dash.snapshot'), \
                 patch('dash.time.monotonic', side_effect=[100, 100+elapsed]), \
                 patch('dash.maybe_main', return_value=result) as main, \
                 patch('dash.maybe_detail', return_value='ok') as detail, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dash.main(), 0)
                self.assertEqual(main.call_args.kwargs['wait_timeout'], 120)
                if result == 'skipped-busy':
                    detail.assert_not_called()
                else:
                    self.assertEqual(detail.call_args.kwargs['wait_timeout'], max(0, 120-elapsed))
