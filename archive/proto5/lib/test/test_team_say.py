"""tools/team/team_say（spec/team/mail.md）：寫一封信進自己的 outbox；config.json 讀取與參數驗證。"""
import filecmp
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import aos_team_format as fmt

PROTO = Path(__file__).resolve().parents[2]
EXAMPLES = PROTO / 'spec' / 'team' / 'examples'
TOOL_SRC = PROTO / 'tools' / 'team'


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='aos-team-say-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tooldir = self.tmp / 'tool'
        shutil.copytree(TOOL_SRC, self.tooldir)
        self.outbox = self.tmp / 'team' / 'outbox' / 'worker-1'
        self.outbox.mkdir(parents=True)
        self.write_config()
        self.roster = fmt.validate_roster(json.loads((EXAMPLES / 'team.json').read_text(encoding='utf-8')))

    def write_config(self, **over):
        cfg = {'member': 'worker-1', 'mail_to': ['lead', 'human'], 'members': ['lead', 'worker-1', 'reviewer'],
               'outbox': str(self.outbox), 'tz': 'Asia/Taipei'}
        cfg.update(over)
        (self.tooldir / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8')
        return cfg

    def run_tool(self, arguments):
        """arguments：dict（照樣 dump 成 JSON）或字串（原樣當 stdin，塞爛資料用）。"""
        stdin = json.dumps(arguments, ensure_ascii=False) if isinstance(arguments, (dict, list)) else arguments
        return subprocess.run([sys.executable, str(self.tooldir / 'team_say')], input=stdin,
                              capture_output=True, text=True, timeout=30)

    def outbox_files(self):
        return sorted(p for p in self.outbox.iterdir() if not p.name.startswith('.'))

    def outbox_temp_files(self):
        return sorted(p.name for p in self.outbox.iterdir() if p.name.startswith('.'))

    def last_error(self, r):
        return json.loads(r.stdout.strip().splitlines()[-1])


# --------------------------------------------------------------- 成功 ----

class SuccessTests(Base):
    def test_prints_queued_line_and_writes_one_file(self):
        args = {'to': 'lead', 'status': 'DONE', 'text': '完成了', 'reply_to': 't-0001', 'rev': 1}
        r = self.run_tool(args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        line = r.stdout.strip()
        self.assertEqual(line.count('\n'), 0)
        m = re.match(r'^queued (\S+) DONE → lead$', line)
        self.assertIsNotNone(m, line)
        letter_id = m.group(1)
        self.assertRegex(letter_id, r'^\d+-\d+-worker-1$')
        files = self.outbox_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, letter_id + '.json')
        self.assertEqual(self.outbox_temp_files(), [])   # 沒有殘留暫存檔

    def test_letter_has_exact_fields_and_validates_via_read_outbox_file(self):
        r = self.run_tool({'to': 'lead', 'status': 'DONE', 'text': '完成了'})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        path = self.outbox_files()[0]
        obj = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(list(obj.keys()), ['id', 'from', 'to', 'status', 'reply_to', 'rev', 'text', 'at'])
        kind, letter = fmt.read_outbox_file(path, self.roster)
        self.assertEqual(kind, 'letter')
        self.assertEqual(letter['from'], 'worker-1')
        self.assertEqual(letter['to'], 'lead')
        self.assertEqual(letter['text'], '完成了')


# --------------------------------------------------------------- to ----

class RecipientTests(Base):
    def test_to_not_in_mail_to_is_bad_arguments(self):
        r = self.run_tool({'to': 'reviewer', 'status': 'DONE', 'text': 'x'})
        self.assertEqual(r.returncode, 1)
        err = self.last_error(r)
        self.assertFalse(err['ok'])
        self.assertEqual(err['error'], 'BadArguments')
        self.assertIn('lead', err['message'])
        self.assertIn('human', err['message'])
        self.assertEqual(self.outbox_files(), [])

    def test_to_outside_roster_is_bad_arguments(self):
        r = self.run_tool({'to': 'boss', 'status': 'DONE', 'text': 'x'})
        self.assertEqual(r.returncode, 1)
        err = self.last_error(r)
        self.assertEqual(err['error'], 'BadArguments')
        self.assertIn('lead', err['message'])
        self.assertEqual(self.outbox_files(), [])


# --------------------------------------------------------------- status ----

class StatusTests(Base):
    def test_status_not_in_whitelist_is_bad_arguments(self):
        for bad in ('OK', 'done'):
            r = self.run_tool({'to': 'lead', 'status': bad, 'text': 'x'})
            self.assertEqual(r.returncode, 1, bad)
            err = self.last_error(r)
            self.assertEqual(err['error'], 'BadArguments')
            for s in ('REQUEST', 'DONE', 'BLOCKED', 'NEEDS-USER', 'FAILED', 'PROGRESS'):
                self.assertIn(s, err['message'])
        self.assertEqual(self.outbox_files(), [])


# --------------------------------------------------------------- 其他參數 ----

class ArgumentValidationTests(Base):
    def test_text_empty_or_missing_is_bad_arguments(self):
        for args in ({'to': 'lead', 'status': 'DONE', 'text': ''}, {'to': 'lead', 'status': 'DONE'}):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 1, args)
            self.assertEqual(self.last_error(r)['error'], 'BadArguments')
        self.assertEqual(self.outbox_files(), [])

    def test_rev_zero_or_non_integer_is_bad_arguments(self):
        for rev in (0, 'one'):
            r = self.run_tool({'to': 'lead', 'status': 'DONE', 'text': 'x', 'rev': rev})
            self.assertEqual(r.returncode, 1, rev)
            self.assertEqual(self.last_error(r)['error'], 'BadArguments')
        self.assertEqual(self.outbox_files(), [])

    def test_unknown_key_is_bad_arguments(self):
        r = self.run_tool({'to': 'lead', 'status': 'DONE', 'text': 'x', 'nope': 1})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.last_error(r)['error'], 'BadArguments')
        self.assertEqual(self.outbox_files(), [])

    def test_arguments_not_json_is_bad_arguments(self):
        r = self.run_tool('not json at all')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.last_error(r)['error'], 'BadArguments')
        self.assertEqual(self.outbox_files(), [])

    def test_arguments_not_object_is_bad_arguments(self):
        r = self.run_tool('[1, 2, 3]')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.last_error(r)['error'], 'BadArguments')
        self.assertEqual(self.outbox_files(), [])


# --------------------------------------------------------------- config／outbox ----

class ConfigTests(Base):
    def test_missing_config_is_configinvalid(self):
        (self.tooldir / 'config.json').unlink()
        r = self.run_tool({'to': 'lead', 'status': 'DONE', 'text': 'x'})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.last_error(r)['error'], 'ConfigInvalid')
        self.assertEqual(self.outbox_files(), [])

    def test_bad_json_config_is_configinvalid(self):
        (self.tooldir / 'config.json').write_text('{not valid json', encoding='utf-8')
        r = self.run_tool({'to': 'lead', 'status': 'DONE', 'text': 'x'})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.last_error(r)['error'], 'ConfigInvalid')
        self.assertEqual(self.outbox_files(), [])

    def test_missing_outbox_dir_is_writefailed(self):
        shutil.rmtree(self.outbox)
        r = self.run_tool({'to': 'lead', 'status': 'DONE', 'text': 'x'})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.last_error(r)['error'], 'WriteFailed')


# --------------------------------------------------------------- _common.py／team.json ----

class SharedFilesTests(Base):
    def test_common_py_is_byte_identical_to_base(self):
        self.assertTrue(filecmp.cmp(str(PROTO / 'tools' / 'base' / '_common.py'),
                                    str(PROTO / 'tools' / 'team' / '_common.py'), shallow=False))


class ToolJsonTests(unittest.TestCase):
    def test_team_json_has_one_tool_with_right_shape(self):
        data = json.loads((TOOL_SRC / 'team.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data), 1)
        entry = data[0]
        self.assertEqual(entry['function']['name'], 'team_say')
        self.assertEqual(entry['_meta']['argv'], ['tools/team/team_say'])
        size = len(json.dumps(entry['function'], ensure_ascii=False))
        self.assertLess(size, 1200, size)


# --------------------------------------------------------------- 穩定度 ----

class StabilityTests(Base):
    def test_ten_runs_all_succeed_with_distinct_ids(self):
        ids = []
        for _ in range(10):
            r = self.run_tool({'to': 'lead', 'status': 'DONE', 'text': 'x'})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            ids.append(r.stdout.strip().split()[1])
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(set(ids)), 10)
        self.assertEqual(len(self.outbox_files()), 10)


if __name__ == '__main__':
    unittest.main()
