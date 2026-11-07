"""Verify the server uses one sequential summary and explanation worker without sockets."""
import signal
import threading
import unittest
from unittest.mock import patch
from eli5_support import OfflineBoard
import dash


class WorkerTests(OfflineBoard):
    def test_sequential_worker_with_disabled_and_enabled_regular_summary(self):
        for enabled in (False, True):
            with self.subTest(summary_enabled=enabled):
                self.cfg['summary']['enabled'] = enabled
                self.cfg['collect_interval_sec'] = 10
                self.write('summary/latest.md', 'Old summary.')
                finished = threading.Event()
                handlers, order, inputs_seen = {}, [], []
                active = 0
                max_active = 0

                class Server:
                    def __init__(server, *args, **kwargs):
                        pass
                    def handle_request(server):
                        if not finished.wait(2):
                            raise AssertionError('Explanation worker did not finish')
                        handlers[signal.SIGTERM](None, None)
                    def server_close(server):
                        pass

                def summary(board, cfg):
                    order.append('summary')
                    if enabled:
                        self.write('summary/latest.md', 'Fresh summary.')
                    return 'ok' if enabled else 'skipped'

                def generator(kind):
                    def run(board, cfg, inputs=None):
                        nonlocal active, max_active
                        active += 1
                        max_active = max(active, max_active)
                        order.append(kind)
                        inputs_seen.append(inputs)
                        self.assertEqual(inputs['main'][1]['summary'],
                                         'Fresh summary.' if enabled else 'Old summary.')
                        active -= 1
                        if kind == 'detail':
                            finished.set()
                        return 'ok'
                    return run

                state = lambda *a, **k: {'summary': {'running': False},
                                         'eli5': {'enabled': True, 'running': False}}
                with patch('dash.http.server.ThreadingHTTPServer', Server), \
                     patch('dash.signal.signal', side_effect=lambda sig, fn: handlers.update({sig:fn})), \
                     patch('dash.load_config', return_value=self.cfg), \
                     patch('dash.copy_assets'), patch('dash.write_state'), \
                     patch('dash.snapshot', side_effect=state), \
                     patch('dash.maybe_summarize', side_effect=summary), \
                     patch('dash.maybe_main', side_effect=generator('main')), \
                     patch('dash.maybe_detail', side_effect=generator('detail')):
                    self.assertEqual(dash.serve(self.board, 8765), 0)
                self.assertEqual(order, ['summary', 'main', 'detail'])
                self.assertEqual(max_active, 1)
                self.assertIs(inputs_seen[0], inputs_seen[1])


if __name__ == '__main__':
    unittest.main()
