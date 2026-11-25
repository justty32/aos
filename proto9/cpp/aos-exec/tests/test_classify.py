# Check entry kinds are judged by content (#!, ELF, JSON), not by +x alone (ported from proto8 aos-exec tests/test_classify.py).
# Not ported from that file: the inst-sheet timeout tests (no inst sheets in proto9) and test_daemon_ctl_same_rule (Python daemon_ctl is proto8 only).
import json

from common import TmpCase


class Classify(TmpCase):
    prefix = 'aos-exec-classify-'

    def test_json_entry_with_x_is_read_as_json(self):
        # /mnt/c（drvfs 沒 metadata）每個檔都 0777：+x 的 JSON 入口照樣當 JSON
        for x in (True, False):
            with self.subTest(x=x):
                self.put('p/_entry', json.dumps(['echo', 'hi-json']), x)
                self.assertEqual(self.run_('p'), (0, 'hi-json', ''))
                self.put('j.json', json.dumps({'a': ['echo', 'ptr']}), x)
                self.assertEqual(self.run_('j.json#/a'), (0, 'ptr', ''))

    def test_programs_still_run(self):
        self.put('t', '#!/bin/sh\necho hi-shebang\n', True)
        self.assertEqual(self.run_('./t'), (0, 'hi-shebang', ''))
        self.put('s', 'echo hi-noshebang\n', True)   # +x、沒 #!、不是 JSON：照舊交 sh（ideas § 22「乙」）
        self.assertEqual(self.run_('./s'), (0, 'hi-noshebang', ''))
        code, _, err = self.run_('./t#/a')
        self.assertEqual(code, 1)
        self.assertIn('EntryBad', err)

    def test_script_without_x_keeps_old_error(self):
        self.put('u', '#!/bin/sh\necho x\n', False)
        code, out, err = self.run_('./u')
        self.assertEqual((code, out), (1, ''))
        self.assertIn('EntryBad bad entry: not executable (+x) and not JSON', err)

    def test_argv0_with_x_json_goes_through_aos_exec(self):
        # argv[0] 帶 / 又是 +x 的 JSON：前面插 aos-exec（原本直接 exec，kernel 交 sh 跑 JSON 失敗）
        self.put('p/_entry', json.dumps(['echo', 'via-aos-exec']), True)
        self.put('arr', json.dumps(['./p/_entry']), True)
        self.assertEqual(self.run_('arr'), (0, 'via-aos-exec', ''))

    def test_elf_runs(self):
        self.assertEqual(self.run_('/bin/echo', 'elf')[:2], (0, 'elf'))

    def test_other_json_values_are_entry_bad(self):
        for doc in (3, None, [], True):
            with self.subTest(doc=doc):
                self.put('v.json', json.dumps(doc))
                code, out, err = self.run_('v.json')
                self.assertEqual((code, out), (1, ''))
                self.assertIn('EntryBad bad entry:', err)
                self.assertIn('is not an argv array or a path', err)
