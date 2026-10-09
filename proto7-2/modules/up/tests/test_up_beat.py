"""心跳節拍：--interval 秒、--early／--fixed 寫進 up.json 與 timeline.json，重跑沿用，壞值退 2。"""
import json
import subprocess
import sys

import test_up as cases


class UpBeat(cases.UpTests):
    def timeline(self):
        return self.data('.aos/timeline.json')

    def effective(self, ms, early):
        def ok():
            row = self.nstat('bob')
            return row.get('interval_ms') == ms and row.get('early_tock') is early
        self.wait_for(ok, 10, f'心跳沒換成 {ms} ms early={early}：{self.nstat("bob")}')

    def test_beat_applies(self):
        path = self.node / '.aos/timeline.json'
        path.write_text(json.dumps(dict(interval_ms=200, action_timeout_s=20)))
        self.invoke(self.node, '--interval', '0.3', '--early', '-d')
        config = self.data('.aos/up.json')
        self.assertEqual((config['interval_ms'], config['early_tock']), (300, True))
        self.assertEqual(self.timeline(), dict(interval_ms=300, action_timeout_s=20, early_tock=True))
        self.effective(300, True)

    def test_beat_kept_on_rerun(self):
        self.invoke(self.node, '--interval', '0.25', '--early', '-d')
        self.invoke('stop', self.node)
        (self.node / '.aos/timeline.json').write_text(json.dumps(dict(interval_ms=200)))
        self.invoke(self.node, '-d')          # 不給節拍：沿用 up.json，蓋回 timeline
        self.assertEqual((self.data('.aos/up.json')['interval_ms'], self.data('.aos/up.json')['early_tock']), (250, True))
        self.assertEqual(self.timeline(), dict(interval_ms=250, early_tock=True))
        self.effective(250, True)
        self.invoke(self.node, '--fixed', '-d')   # 心跳在跑時改：只改 early，間隔沿用，下一回合生效
        self.assertEqual(self.timeline(), dict(interval_ms=250, early_tock=False))
        self.effective(250, False)

    def test_default_leaves_timeline(self):
        before = (self.node / '.aos/timeline.json').read_bytes()
        self.invoke(self.node, '-d')
        self.invoke(self.node, '-d')
        self.assertNotIn('interval_ms', self.data('.aos/up.json'))
        self.assertNotIn('early_tock', self.data('.aos/up.json'))
        self.assertEqual(before, (self.node / '.aos/timeline.json').read_bytes())

    def test_bad_beat_exit_2(self):
        snapshot = lambda: sorted(str(p) for p in self.node.rglob('*'))
        before = snapshot()
        bad = (['--interval', '0'], ['--interval', 'abc'], ['--interval', 'nan'], ['--interval', '1e9'],
               ['--interval', '-1'], ['--early', '--fixed'], ['--interval'])
        for args in bad:
            result = subprocess.run([sys.executable, '-B', str(cases.UP), str(self.node), *args, '-d'],
                                    capture_output=True, text=True, timeout=40)
            self.assertEqual(result.returncode, 2, (args, result.stdout, result.stderr))
            self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
            self.assertTrue(result.stderr.startswith('aos7-up: '), result.stderr)
            self.assertIn('。', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertEqual(before, snapshot(), args)
        self.invoke('status', self.node, '--interval', '1', rc=2)
        # up.json 的節拍欄壞了也是退 2、不動檔
        self.invoke(self.node, '-d')
        path = self.node / '.aos/up.json'
        for key, value in (('interval_ms', 'x'), ('interval_ms', 0), ('interval_ms', 1.5), ('early_tock', 'yes')):
            config = json.loads(path.read_text())
            config.pop('interval_ms', None), config.pop('early_tock', None)
            path.write_text(json.dumps(dict(config, **{key: value})))
            raw = path.read_bytes()
            self.invoke(self.node, '-d', rc=2)
            self.assertEqual(raw, path.read_bytes())

    # Only the beat cases belong to this subclass.
    test_idempotent = None
    test_sigkill_reconnect = None
    test_foreground_interrupt = None
    test_status_and_stop = None
    test_invalid_and_missing = None
