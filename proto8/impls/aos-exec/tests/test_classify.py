# Check entry kinds are judged by content (#!, ELF, JSON), not by +x alone, in aos-exec and daemon_ctl.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[3]
BIN = PROTO / 'impls' / 'aos-exec' / 'bin'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
ENV['PATH'] = str(BIN) + ':' + ENV['PATH']
sys.path.insert(0, str(PROTO / 'py'))
import daemon_ctl as dc  # noqa: E402
from daemon_ctl.entry import is_program  # noqa: E402


def run(*argv, cwd):
    p = subprocess.run(['aos-exec', *argv], cwd=cwd, env=ENV, capture_output=True, text=True, timeout=10)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


class Classify(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-exec-classify-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def put(self, name, text, x):
        p = self.d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        p.chmod(0o755 if x else 0o644)
        return p

    def test_json_entry_with_x_is_read_as_json(self):
        # /mnt/c（drvfs 沒 metadata）每個檔都 0777：+x 的 JSON 入口照樣當 JSON
        for x in (True, False):
            with self.subTest(x=x):
                self.put('p/_entry', json.dumps(['echo', 'hi-json']), x)
                self.assertEqual(run('p', cwd=self.d), (0, 'hi-json', ''))
                self.put('j.json', json.dumps({'a': ['echo', 'ptr']}), x)
                self.assertEqual(run('j.json#/a', cwd=self.d), (0, 'ptr', ''))

    def test_programs_still_run(self):
        self.put('t', '#!/bin/sh\necho hi-shebang\n', True)
        self.assertEqual(run('./t', cwd=self.d), (0, 'hi-shebang', ''))
        self.put('s', 'echo hi-noshebang\n', True)   # +x、沒 #!、不是 JSON：照舊交 sh（ideas § 22「乙」）
        self.assertEqual(run('./s', cwd=self.d), (0, 'hi-noshebang', ''))
        code, _, err = run('./t#/a', cwd=self.d)
        self.assertEqual(code, 1)
        self.assertIn('EntryBad', err)

    def test_script_without_x_keeps_old_error(self):
        self.put('u', '#!/bin/sh\necho x\n', False)
        code, out, err = run('./u', cwd=self.d)
        self.assertEqual((code, out), (1, ''))
        self.assertIn('EntryBad bad entry: not executable (+x) and not JSON', err)

    def test_argv0_with_x_json_goes_through_aos_exec(self):
        # argv[0] 帶 / 又是 +x 的 JSON：前面插 aos-exec（原本直接 exec，kernel 交 sh 跑 JSON 失敗）
        self.put('p/_entry', json.dumps(['echo', 'via-aos-exec']), True)
        self.put('arr', json.dumps(['./p/_entry']), True)
        self.assertEqual(run('arr', cwd=self.d), (0, 'via-aos-exec', ''))
        self.put('inst.json', json.dumps({'argv': ['./p/_entry']}), True)
        self.assertEqual(run('inst.json', cwd=self.d), (0, 'via-aos-exec', ''))

    def test_daemon_ctl_same_rule(self):
        js = self.put('loop.json', json.dumps({'exec': ['echo', 'x'], 'interval_ms': 5}), True)
        sh = self.put('t', '#!/bin/sh\necho\n', True)
        elf = Path('/bin/true')
        self.assertFalse(is_program(str(js)))
        self.assertTrue(is_program(str(sh)))
        self.assertTrue(is_program(str(elf)))
        self.assertFalse(is_program(str(self.put('n', '#!/bin/sh\n', False))))
        self.assertIsNotNone(dc.find_loop(str(js)))   # +x 的 loop 設定照樣認成 loop 型
        self.assertIsNone(dc.find_loop(str(sh)))


if __name__ == '__main__':
    unittest.main()
