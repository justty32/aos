"""第 2 隊驗收員（aos_team_verify.py）：固定檢查器（file_exists／table_filled／check）、judge 排除、CLI。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import aos_team_format as fmt
import aos_team_task as task
import aos_team_verify as verify

PROTO = Path(__file__).resolve().parents[2]
EXAMPLES = PROTO / 'spec' / 'team' / 'examples'
ROSTER = json.loads((EXAMPLES / 'team.json').read_text(encoding='utf-8'))   # lead／worker-1／reviewer，project=../p


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-team-verify-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.team = self.root / 'team'
        self.team.mkdir()
        self.project = self.root / 'p'
        self.project.mkdir()
        (self.team / 'team.json').write_text(json.dumps(ROSTER, ensure_ascii=False), encoding='utf-8')
        self.lay = fmt.Layout(self.team)
        for d in self.lay.skeleton(ROSTER['members']):
            d.mkdir(parents=True, exist_ok=True)
        self.roster = fmt.load_roster(self.team)

    def write(self, rel, content):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def open_task(self, done_when, **over):
        """建一張單（照 request-handoff.json 改 done_when）；回單號（新資料夾一律 t-0001）。"""
        req = json.loads((EXAMPLES / 'request-handoff.json').read_text(encoding='utf-8'))
        req['id'] = fmt.new_id('lead')
        req['done_when'] = done_when
        req.update(over)
        task.on_handoff(self.lay, self.roster, req)
        return 't-0001'


# --------------------------------------------------------------- file_exists ----

class FileExistsTests(Base):
    def test_pass_when_exists(self):
        self.write('a.txt', 'x')
        ok, why = verify.check_file_exists(self.project, {'path': 'a.txt'})
        self.assertTrue(ok)
        self.assertIn('a.txt', why)

    def test_fail_when_missing(self):
        ok, why = verify.check_file_exists(self.project, {'path': 'missing.txt'})
        self.assertFalse(ok)
        self.assertIn('missing.txt', why)

    def test_relative_escape_is_fail_not_broken(self):
        with self.assertRaises(verify.NotMet):
            verify.check_file_exists(self.project, {'path': '../x'})

    def test_absolute_outside_is_error_not_fail(self):
        outside = self.root / 'outside.txt'
        outside.write_text('secret', encoding='utf-8')
        with self.assertRaises(verify.CheckError):
            verify.check_file_exists(self.project, {'path': str(outside)})

    def test_symlink_to_outside_is_fail_not_broken(self):
        outside = self.root / 'secret.txt'
        outside.write_text('secret', encoding='utf-8')
        link = self.project / 'link.txt'
        os.symlink(outside, link)
        with self.assertRaises(verify.NotMet):
            verify.check_file_exists(self.project, {'path': 'link.txt'})


# --------------------------------------------------------------- table_filled ----

class TableFilledJsonTests(Base):
    def test_all_filled_pass(self):
        data = {'contract': 'wf-table/1', 'columns': ['a', 'b'],
                'rows': [{'a': '1', 'b': '2'}, {'a': '3', 'b': '4'}]}
        self.write('table.json', json.dumps(data, ensure_ascii=False))
        ok, why = verify.check_table_filled(self.project, {'path': 'table.json'})
        self.assertTrue(ok, why)
        self.assertIn('2 列', why)
        self.assertIn('2 欄', why)

    def test_empty_cell_fails_with_row_and_column(self):
        data = {'contract': 'wf-table/1', 'columns': ['a', 'b'],
                'rows': [{'a': '1', 'b': '2'}, {'a': '', 'b': '4'}]}
        self.write('table.json', json.dumps(data, ensure_ascii=False))
        ok, why = verify.check_table_filled(self.project, {'path': 'table.json'})
        self.assertFalse(ok)
        self.assertIn('第 2 列', why)
        self.assertIn('a', why)

    def test_column_filter_only_checks_given_column(self):
        data = {'contract': 'wf-table/1', 'columns': ['a', 'b'],
                'rows': [{'a': '', 'b': '2'}, {'a': '', 'b': '4'}]}
        self.write('table.json', json.dumps(data, ensure_ascii=False))
        ok, _ = verify.check_table_filled(self.project, {'path': 'table.json', 'column': 'b'})
        self.assertTrue(ok)
        ok, why = verify.check_table_filled(self.project, {'path': 'table.json', 'column': 'a'})
        self.assertFalse(ok)
        self.assertIn('a', why)

    def test_unknown_column_is_fail(self):
        data = {'contract': 'wf-table/1', 'columns': ['a', 'b'], 'rows': [{'a': '1', 'b': '2'}]}
        self.write('table.json', json.dumps(data, ensure_ascii=False))
        with self.assertRaises(verify.NotMet) as cm:
            verify.check_table_filled(self.project, {'path': 'table.json', 'column': 'c'})
        self.assertIn('c', str(cm.exception))
        self.assertIn('a', str(cm.exception))
        self.assertIn('b', str(cm.exception))

    def test_zero_rows_is_fail(self):
        data = {'contract': 'wf-table/1', 'columns': ['a', 'b'], 'rows': []}
        self.write('table.json', json.dumps(data, ensure_ascii=False))
        ok, why = verify.check_table_filled(self.project, {'path': 'table.json'})
        self.assertFalse(ok)
        self.assertIn('0 列', why)


class TableFilledCsvTests(Base):
    def test_all_filled_pass(self):
        self.write('table.csv', 'a,b\n1,2\n3,4\n')
        ok, why = verify.check_table_filled(self.project, {'path': 'table.csv'})
        self.assertTrue(ok, why)

    def test_empty_cell_fails_with_row_and_column(self):
        self.write('table.csv', 'a,b\n1,2\n,4\n')
        ok, why = verify.check_table_filled(self.project, {'path': 'table.csv'})
        self.assertFalse(ok)
        self.assertIn('第 2 列', why)
        self.assertIn('a', why)


class TableFilledMarkdownTests(Base):
    def test_all_filled_pass(self):
        self.write('t.md', '# T\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n')
        ok, why = verify.check_table_filled(self.project, {'path': 't.md'})
        self.assertTrue(ok, why)

    def test_empty_cell_fails(self):
        self.write('t.md', '# T\n\n| a | b |\n| --- | --- |\n|  | 2 |\n')
        ok, why = verify.check_table_filled(self.project, {'path': 't.md'})
        self.assertFalse(ok)
        self.assertIn('第 1 列', why)

    def test_heading_picks_the_right_table(self):
        text = ('# A\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n\n'
                '# B\n\n| a | b |\n| --- | --- |\n|  | 4 |\n')
        self.write('t.md', text)
        ok, _ = verify.check_table_filled(self.project, {'path': 't.md', 'heading': 'A'})
        self.assertTrue(ok)
        ok, why = verify.check_table_filled(self.project, {'path': 't.md', 'heading': 'B'})
        self.assertFalse(ok)

    def test_table_not_found_is_fail(self):
        text = '# A\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n'
        self.write('t.md', text)
        with self.assertRaises(verify.NotMet) as cm:
            verify.check_table_filled(self.project, {'path': 't.md', 'heading': 'Z'})
        self.assertIn('Z', str(cm.exception))


# --------------------------------------------------------------- check: contains ----

class ContainsTests(Base):
    def test_contains_pass_and_fail(self):
        self.write('msg.txt', 'hello world')
        ok, why = verify.check_contains(self.project, {'path': 'msg.txt', 'text': 'hello'})
        self.assertTrue(ok)
        self.assertIn('有', why)
        ok, why = verify.check_contains(self.project, {'path': 'msg.txt', 'text': 'goodbye'})
        self.assertFalse(ok)
        self.assertIn('沒有', why)

    def test_contains_missing_file_is_fail(self):
        with self.assertRaises(verify.NotMet):
            verify.check_contains(self.project, {'path': 'nope.txt', 'text': 'x'})

    def test_contains_missing_text_arg_is_error(self):
        self.write('msg.txt', 'hello world')
        with self.assertRaises(verify.CheckError):
            verify.check_contains(self.project, {'path': 'msg.txt'})

    def test_not_contains_pass_and_fail(self):
        self.write('msg.txt', 'hello world')
        ok, _ = verify.check_not_contains(self.project, {'path': 'msg.txt', 'text': 'goodbye'})
        self.assertTrue(ok)
        ok, _ = verify.check_not_contains(self.project, {'path': 'msg.txt', 'text': 'hello'})
        self.assertFalse(ok)


# --------------------------------------------------------------- check: wf_residue ----

class WfResidueTests(Base):
    def test_pass_when_clean(self):
        self.write('clean.md', '# 標題\n\n這是正常內容，沒有殘留記號。\n')
        ok, why = verify.check_wf_residue(self.project, {})
        self.assertTrue(ok, why)

    def test_fail_reports_file_and_line(self):
        self.write('dirty.md', '第一行\n第二行 {{ 佔位 }}\n第三行\n')
        ok, why = verify.check_wf_residue(self.project, {})
        self.assertFalse(ok)
        self.assertIn('dirty.md:2', why)


# --------------------------------------------------------------- check: wf_lint_strict ----

class WfLintStrictTests(Base):
    def test_result_is_one_of_pass_fail_error_and_does_not_raise(self):
        # 空專案跑真的 wf-lint.sh（走 subprocess），只斷言不丟例外、結果落在三種之一
        results = verify.run_items(self.project, [{'kind': 'check', 'name': 'wf_lint_strict'}])
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertIn(r['result'], (verify.PASS, verify.FAIL, verify.ERROR))
        self.assertTrue(r['why'])


# --------------------------------------------------------------- checker dispatch ----

class CheckerDispatchTests(Base):
    def test_unknown_checker_name_is_error_lists_known(self):
        with self.assertRaises(verify.CheckError) as cm:
            verify.checker('bogus')
        msg = str(cm.exception)
        for name in ('contains', 'not_contains', 'wf_residue', 'wf_lint_strict'):
            self.assertIn(name, msg)


# --------------------------------------------------------------- run_items／verify ----

class RunItemsTests(Base):
    def test_judge_excluded_and_index_preserved(self):
        self.write('a.txt', 'hi there')
        done_when = [{'kind': 'file_exists', 'path': 'a.txt'},
                     {'kind': 'judge', 'text': '寫得白話'},
                     {'kind': 'check', 'name': 'contains', 'args': {'path': 'a.txt', 'text': 'hi'}}]
        results = verify.run_items(self.project, done_when)
        self.assertEqual([r['i'] for r in results], [0, 2])
        self.assertTrue(all(r['pass'] for r in results))

    def test_verify_pass_requires_all_mechanical_pass_judge_excluded(self):
        self.write('a.txt', 'hi there')
        done_when = [{'kind': 'file_exists', 'path': 'a.txt'},
                     {'kind': 'check', 'name': 'contains', 'args': {'path': 'a.txt', 'text': 'hi'}},
                     {'kind': 'judge', 'text': '意思沒變'}]
        tid = self.open_task(done_when)
        res = verify.verify(self.team, tid)
        self.assertTrue(res['pass'])
        self.assertEqual(len(res['results']), 2)

    def test_verify_error_makes_overall_not_pass(self):
        self.write('a.txt', 'hi there')
        done_when = [{'kind': 'file_exists', 'path': 'a.txt'}, {'kind': 'check', 'name': 'bogus'}]
        tid = self.open_task(done_when)
        res = verify.verify(self.team, tid)
        self.assertFalse(res['pass'])
        self.assertEqual(res['results'][0]['result'], verify.PASS)
        self.assertEqual(res['results'][1]['result'], verify.ERROR)


# --------------------------------------------------------------- CLI ----

class CliTests(Base):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(PROTO / 'cli' / 'aos-team'), 'verify', *args,
                               '--target', str(self.team)], capture_output=True, text=True, timeout=60)

    def snapshot(self):
        out = {}
        for base in (self.team, self.project):
            for root, _dns, fns in os.walk(base):
                for fn in fns:
                    p = Path(root) / fn
                    st = p.stat()
                    out[str(p)] = (st.st_mtime_ns, st.st_size)
        return out

    def test_all_pass_exit_0_prints_word(self):
        self.write('a.txt', 'hi there')
        tid = self.open_task([{'kind': 'file_exists', 'path': 'a.txt'},
                              {'kind': 'check', 'name': 'contains', 'args': {'path': 'a.txt', 'text': 'hi'}}])
        r = self.run_cli(tid)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('過', r.stdout)

    def test_not_all_pass_exit_1_stderr_notpassed(self):
        tid = self.open_task([{'kind': 'file_exists', 'path': 'missing.txt'}])
        r = self.run_cli(tid)
        self.assertEqual(r.returncode, 1)
        self.assertIn('NotPassed', r.stderr)

    def test_json_flag_prints_one_line_json(self):
        self.write('a.txt', 'hi there')
        tid = self.open_task([{'kind': 'file_exists', 'path': 'a.txt'}])
        r = self.run_cli(tid, '--json')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(obj['task'], tid)
        self.assertTrue(obj['pass'])

    def test_out_flag_writes_file(self):
        self.write('a.txt', 'hi there')
        tid = self.open_task([{'kind': 'file_exists', 'path': 'a.txt'}])
        outfile = self.root / 'out.json'
        r = self.run_cli(tid, '--out', str(outfile))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        obj = json.loads(outfile.read_text(encoding='utf-8'))
        for key in ('task', 'rev', 'attempt', 'pass', 'results'):
            self.assertIn(key, obj)
        self.assertEqual(obj['task'], tid)

    def test_rev_attempt_flags_recorded(self):
        self.write('a.txt', 'hi there')
        tid = self.open_task([{'kind': 'file_exists', 'path': 'a.txt'}])
        r = self.run_cli(tid, '--rev', '2', '--attempt', '3', '--json')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        obj = json.loads(r.stdout.strip())
        self.assertEqual(obj['rev'], 2)
        self.assertEqual(obj['attempt'], 3)

    def test_no_such_task_exit_1_stderr_nosuchtask(self):
        r = self.run_cli('t-9999')
        self.assertEqual(r.returncode, 1)
        self.assertIn('NoSuchTask', r.stderr)

    def test_verify_does_not_modify_any_file(self):
        self.write('a.txt', 'hi there')
        tid = self.open_task([{'kind': 'file_exists', 'path': 'a.txt'}])
        before = self.snapshot()
        r = self.run_cli(tid)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        after = self.snapshot()
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
