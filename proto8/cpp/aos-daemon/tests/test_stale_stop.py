# Check stop → sleep → start keeps the restarted loop running instead of replaying the old stop.
import json
import time
import unittest

from support import Fixture, read, until


class StaleStop(unittest.TestCase):
    def test_start_after_stop_then_sleep_keeps_running(self):
        f = Fixture('stale_stop').start()
        self.addCleanup(f.close)
        f.add(f.body('loop_array', 'stop', seconds=30))   # 一次跑 30 秒：stop 寫進 ctl 後子 loop 來不及回應
        f.ctl('stop', 'job')
        f.phase('stopping')
        self.assertEqual(read(f.cell / 'ctl.json')['cmd'], 'stop')
        f.ctl('sleep', 'job')
        f.phase('stopped')
        (f.cell / 'ready').unlink()
        f.ctl('start', 'job')
        until(lambda: (f.cell / 'ready').exists())
        ctl = read(f.cell / 'ctl.json')
        self.assertNotIn('cmd', ctl)            # 舊的 stop 拿掉了、seq 照留
        self.assertIn('seq', ctl)
        time.sleep(1)
        self.assertEqual(f.row()['phase'], 'running')
        f.ctl('stop', 'job')                    # 之後照常 stop 得掉（新的 seq）
        self.assertEqual(until(lambda: read(f.cell / 'ctl.json').get('cmd')), 'stop')


if __name__ == '__main__':
    unittest.main()
