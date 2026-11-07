"""Verify bounded evidence, independent fingerprints and filtered commit cache behavior offline."""
import json
import os
import unittest
from unittest.mock import patch
from eli5_support import OfflineBoard, eli5
import details_api
import eli5_inputs


class EvidenceTests(OfflineBoard):
    def inputs(self):
        return eli5.input_snapshot(self.board, self.cfg)

    def test_event_content_not_just_timestamp_changes_fingerprint(self):
        before = self.inputs()
        self.events[0]['text'] += ' Different content.'
        self.flush()
        after = self.inputs()
        for kind, expected in [('main', {'lines.alpha'}),
                               ('detail', {'lines.alpha.timeline'})]:
            old, new = before[kind][0], after[kind][0]
            self.assertEqual({key for key in old if old[key] != new[key]}, expected)

    def test_handoff_mtime_and_stat_are_fingerprint_sources(self):
        before = self.inputs()
        handoff = self.board/'handoff.md'
        st = handoff.stat()
        os.utime(handoff, (st.st_atime, st.st_mtime+5))
        changed = self.inputs()
        self.assertNotEqual(before['main'][0]['lines.alpha'], changed['main'][0]['lines.alpha'])
        self.assertNotEqual(before['detail'][0]['lines.alpha.handoff'],
                            changed['detail'][0]['lines.alpha.handoff'])
        # Detail uses mtime+size, so size changes invalidate even with preserved mtime.
        self.write('handoff.md', 'A much longer handoff body than the original fixture text.')
        os.utime(handoff, (st.st_atime, st.st_mtime+5))
        self.assertNotEqual(changed['detail'][0]['lines.alpha.handoff'],
                            self.inputs()['detail'][0]['lines.alpha.handoff'])

    def test_no_handoff_does_not_request_or_store_handoff(self):
        values = self.inputs()['detail']
        self.assertNotIn('lines.beta.handoff', values[0])
        self.assertNotIn('lines.beta.handoff', values[1])
        self.assertEqual(self.generate(), ('ok', 'ok'))
        self.assertNotIn('handoff', self.stored('detail')['lines']['beta'])

    def test_filtered_commits_and_cache_not_global_head(self):
        cfg = {**self.cfg, 'repos': [{'name':'local', 'path':str(self.board)}]}
        line = {'id':'alpha', 'commit_filters': [{'repo':'local','grep':'Target'},
                                                {'repo':'local','grep':'fix'},
                                                {'repo':'local','path':'scope/'}]}
        stamp = '2026-11-07T12:00:00+08:00'
        rows = '\n'.join([f'aaaaaaa\t{stamp}\tTarget change',
                          f'bbbbbbb\t{stamp}\tunrelated global head',
                          f'ccccccc\t{stamp}\tFIX update'])
        def git(path, args):
            return f'ddddddd\t{stamp}\tpath-only change' if '--' in args else rows
        cache = {}
        with patch('details_api._git', side_effect=git) as run:
            commits = details_api.line_commits(cfg, line, cache)
            again = details_api.line_commits(cfg, line, cache)
            self.assertEqual(run.call_count, 2)
        self.assertEqual(commits, again)
        self.assertEqual({x['hash'] for x in commits}, {'aaaaaaa','ccccccc','ddddddd'})
        self.assertNotIn('bbbbbbb', [x['hash'] for x in commits])
        cfg['lines'] = [line]
        with patch('details_api._git', return_value=rows):
            before = eli5.input_snapshot(self.board, cfg)['main'][0]['lines.alpha']
        with patch('details_api._git', return_value=rows+'\neeeeeee\t'+stamp+'\tglobal other'):
            self.assertEqual(before, eli5.input_snapshot(self.board,cfg)['main'][0]['lines.alpha'])
        with patch('details_api._git', return_value='fffffff\t2026-11-07T13:00:00+08:00\tTarget newer'):
            self.assertNotEqual(before, eli5.input_snapshot(self.board,cfg)['main'][0]['lines.alpha'])

    def test_codex_bucket_goal_pid_and_last_40_lines(self):
        self.write('worker.log', 'x'*16300)
        process = {'pid': 42, 'goal': 'Finish the work.', 'log_file':str(self.board/'worker.log')}
        with patch('eli5_inputs.codex_processes', return_value=[process]):
            before = self.inputs()['detail']
            self.write('worker.log', 'y'*16320)
            self.assertEqual(before[0]['codex'], self.inputs()['detail'][0]['codex'])
            self.write('worker.log', '\n'.join(f'row {i}' for i in range(100))+'z'*17000)
            after = self.inputs()['detail']
            self.assertNotEqual(before[0]['codex'], after[0]['codex'])
            self.assertLessEqual(len(after[1]['codex'][0]['log'].splitlines()), 40)
            process['goal'] = 'A changed goal.'
            self.assertNotEqual(after[0]['codex'], self.inputs()['detail'][0]['codex'])
            after = self.inputs()['detail']
            process['pid'] = 43
            self.assertNotEqual(after[0]['codex'], self.inputs()['detail'][0]['codex'])

    def test_reports_mtime_fingerprint_and_newest_five_bounded_text(self):
        self.cfg['report_globs'] = [str(self.board/'report*.md')]
        for i in range(7):
            self.write(f'report{i}.md', str(i)*1800)
            os.utime(self.board/f'report{i}.md', (1800000000+i,1800000000+i))
        before = self.inputs()['detail']
        reports = before[1]['reports']
        self.assertEqual([x['name'] for x in reports], [f'report{i}.md' for i in range(6,1,-1)])
        self.assertTrue(all(len(x['text']) <= 1500 for x in reports))
        os.utime(self.board/'report0.md', (1800000010,1800000010))
        self.assertNotEqual(before[0]['reports'], self.inputs()['detail'][0]['reports'])

    def test_main_last_ten_and_detail_last_thirty_event_windows(self):
        self.events = [self.event('alpha', f'Evidence {i}') for i in range(45)]
        self.flush()
        before = self.inputs()
        self.assertEqual(len(before['main'][1]['lines.alpha']['events']), 10)
        self.assertEqual(len(before['detail'][1]['lines.alpha.timeline']['events']), 30)
        self.events[0]['text'] = 'Outside both windows.'
        self.flush()
        outside = self.inputs()
        self.assertEqual(before['main'][0]['lines.alpha'], outside['main'][0]['lines.alpha'])
        self.assertEqual(before['detail'][0]['lines.alpha.timeline'],
                         outside['detail'][0]['lines.alpha.timeline'])
        self.events[20]['text'] = 'Inside detail window only.'
        self.flush()
        detail_only = self.inputs()
        self.assertEqual(outside['main'][0]['lines.alpha'], detail_only['main'][0]['lines.alpha'])
        self.assertNotEqual(outside['detail'][0]['lines.alpha.timeline'],
                            detail_only['detail'][0]['lines.alpha.timeline'])
        self.events[-1]['text'] = 'Inside both windows.'
        self.flush()
        both = self.inputs()
        self.assertNotEqual(detail_only['main'][0]['lines.alpha'], both['main'][0]['lines.alpha'])
        self.assertNotEqual(detail_only['detail'][0]['lines.alpha.timeline'],
                            both['detail'][0]['lines.alpha.timeline'])

    def test_question_text_options_recommend_individually_change_ask_fingerprint(self):
        ask = self.event('alpha', 'Choose.', id='question', status='ask',
                         options=[{'key':'a','text':'First'}, {'key':'b','text':'Second'}], recommend='a')
        self.events.append(ask)
        self.flush()
        for field, value in [('text','Changed question.'),
                             ('options',[{'key':'a','text':'Changed choice'},
                                         {'key':'b','text':'Second'}]), ('recommend','b')]:
            with self.subTest(field=field):
                before = self.inputs()['main'][0]
                ask[field] = value
                self.flush()
                after = self.inputs()['main'][0]
                self.assertNotEqual(before['asks.question'], after['asks.question'])
                self.assertEqual(before['summary'], after['summary'])
                self.assertEqual(before['lines.beta'], after['lines.beta'])

    def test_supplied_question_explanation_is_not_requested(self):
        self.events.append(self.event('alpha', 'Choose.', id='supplied', status='ask',
                            options=[], recommend=None, eli5='This is already explained.'))
        self.flush()
        self.assertNotIn('asks.supplied', self.inputs()['main'][0])
        self.assertEqual(self.generate(), ('ok', 'ok'))
        self.assertTrue(all('asks.supplied' not in payload for payload in self.calls))


if __name__ == '__main__':
    unittest.main()
