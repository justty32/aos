# Check a proc that ended while the daemon was gone (killed, power loss, reboot) stays on the table as stopped with a reason (11-19 audit P18).
import os
import signal
import time
import unittest

from support import Fixture, read, until, write


class AdoptDead(unittest.TestCase):
    def crashed(self, name, declared=False):
        """Start a daemon with one running proc, kill -9 the daemon, then kill the proc while no daemon runs."""
        f = Fixture(name)
        target = f.body('script', 'stop', seconds=60)
        if declared:
            write(f.config, {'interval_ms': 20, 'procs': {'job': str(target)}})
        f.start()
        self.addCleanup(f.close)
        if not declared:
            f.ctl('add', '--name', 'job', str(target))
        pid = f.phase('running')['pid']
        f.proc.kill()
        f.proc.wait()
        f.close()
        os.kill(pid, signal.SIGKILL)
        until(lambda: not os.path.exists('/proc/%d' % pid) or open('/proc/%d/stat' % pid).read().split()[2] == 'Z')
        return f

    def test_dead_while_away_stays_stopped(self):
        f = self.crashed('dead_away')
        f.start()
        row = f.phase('stopped')
        self.assertEqual(row['reason'], 'ended while the daemon was not running (exit code unknown); start it to run it again')
        self.assertIn('aos-daemon: warning: job ended while the daemon was not running', (f.root / 'daemon.err').read_text())
        time.sleep(.2)
        self.assertEqual(f.row()['phase'], 'stopped')     # not started again on its own
        f.body('script', 'stop', seconds=4)
        f.ctl('start', 'job')
        self.assertIsNone(f.phase('running')['reason'])

    def test_reboot_says_the_machine_restarted(self):
        f = self.crashed('dead_reboot')
        table = read(f.stack / 'procs_state.json')
        table['boot_id'] = '00000000-0000-0000-0000-000000000000'   # as after a reboot
        write(f.stack / 'procs_state.json', table)
        f.start()
        self.assertTrue(f.phase('stopped')['reason'].startswith('the machine restarted while it was running (exit code unknown)'))

    def test_declared_proc_starts_again(self):
        f = self.crashed('dead_declared', declared=True)
        f.start()
        row = f.phase('running')
        self.assertIsNone(row['reason'])


if __name__ == '__main__':
    unittest.main()
