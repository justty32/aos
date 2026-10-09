"""用真 brain 資料重播停滯、結案與未知區間。"""
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aos7_kernel_rules import RULES, noop, supervise_brain

FIX = Path(__file__).parent / 'fixtures/brain'


def load(name):
    return json.loads((FIX / name).read_text(encoding='utf-8'))


def item(task, run, ct, read=None):
    return dict(src=dict(node='bob', slot='brain', kind='brain'), file='brain/task.json',
                run=run, seq=None, completed_tock=ct, value=deepcopy(task),
                read=read or ('ok' if isinstance(task, dict) else 'absent' if task is None else 'bad'))


def config(**params):
    return dict(sources=[dict(node='bob', slot='brain', kind='brain')],
                targets=[dict(node='bob', slot='brain')],
                rules=[dict(name='supervise-brain', **params)])


class SuperviseBrainTest(unittest.TestCase):
    def setUp(self):
        self.task = load('longtask-run1/task.json')
        self.birth = load('longtask-run1/birth.json')
        self.run, self.ct = self.birth['run'], self.birth['round']

    def frames(self, start, end, run=None, task=None, read=None):
        return [[item(self.task if task is None else task, self.run if run is None else run, ct, read)]
                for ct in range(start, end + 1)]

    def replay(self, frames, cfg=None, state=None, rule=None):
        outputs = []
        for tock, snap in enumerate(frames):
            ctx = dict(v=1, tock=tock, config=config() if cfg is None else cfg)
            if rule is not None:
                ctx['rule'] = rule
            before = deepcopy((ctx, snap, state))
            result, actions = supervise_brain(ctx, snap, state)
            self.assertEqual((ctx, snap, state), before)
            self.assertEqual(json.loads(json.dumps(result)), result)
            self.assertEqual(json.loads(json.dumps(actions)), actions)
            self.assertEqual(supervise_brain(ctx, snap, state), (result, actions))
            state = result
            outputs.append(actions)
        return state, outputs

    def flat(self, outputs):
        return [a for actions in outputs for a in actions]

    def test_trigger_notify_then_kill_run1_01(self):
        state, out = self.replay(self.frames(self.ct, load('longtask-run1/exit.json')['round'] - 1))
        self.assertEqual([(i, a['op']) for i, actions in enumerate(out) for a in actions],
                         [(6, 'notify'), (12, 'kill')])
        kill = out[12][0]
        self.assertEqual(kill['run'], 25)
        self.assertEqual(kill['target'], dict(node='bob', slot='brain'))
        self.assertEqual(kill['basis'], dict(src='bob/brain', file='brain/task.json', run=self.run,
            completed_tock=self.ct + 12, id=self.task['id'], title=None, step=self.task['step'], since=self.ct, age=12))
        self.assertIn(self.task['line'], out[6][0]['body'])
        self.assertEqual(state['killed'], {'bob/brain': self.run})

    def test_new_run_rebuilds_02(self):
        state, _ = self.replay(self.frames(self.ct, self.ct + 79))
        _, out = self.replay(self.frames(self.ct + 80, self.ct + 104, run=26), state=state)
        self.assertEqual([(i, a['op']) for i, aa in enumerate(out) for a in aa], [(24, 'kill')])
        self.assertEqual(out[24][0]['run'], 26)

    def test_quiet_idle_run3_03(self):
        birth = load('longtask-run3/birth.json')
        self.assertFalse((FIX / 'longtask-run3/task.json').exists())
        state, out = self.replay([[item(None, birth['run'], ct)] for ct in
                                 range(birth['round'], load('longtask-run3/round.json')['round'] + 1)])
        self.assertEqual(self.flat(out), [])
        self.assertNotIn('bob/brain', state['brains'])

    def test_quiet_closed_task_vanishes_04(self):
        state, _ = self.replay(self.frames(self.ct, self.ct + 11))
        state, out = self.replay([[item(None, self.run, self.ct + 12)]], state=state)
        self.assertEqual(self.flat(out), [])
        self.assertNotIn('bob/brain', state['brains'])
        _, out = self.replay(self.frames(self.ct + 13, self.ct + 19), state=state)
        self.assertEqual(out[:6], [[]] * 6)
        self.assertEqual(out[6], [])

    def test_quiet_unknown_K09_05(self):
        for read in ('unknown', 'bad'):
            state, _ = self.replay(self.frames(self.ct, self.ct + 6))
            state, out = self.replay(self.frames(self.ct + 7, self.ct + 16, read=read), state=state)
            self.assertEqual(self.flat(out), [])
            self.assertEqual(state['brains']['bob/brain']['last'], self.ct + 6)
            _, out = self.replay(self.frames(self.ct + 17, self.ct + 29), state=state)
            self.assertEqual(out[:12], [[]] * 12)
            self.assertEqual([a['op'] for a in out[12]], ['kill'])
            # 還沒通知就進未知：未知那段不算，恢復後滿 6 才通知、滿 12 才殺
            state, _ = self.replay(self.frames(self.ct, self.ct + 4))
            state, _ = self.replay(self.frames(self.ct + 5, self.ct + 14, read=read), state=state)
            _, out = self.replay(self.frames(self.ct + 15, self.ct + 27), state=state)
            self.assertEqual([(i, a['op']) for i, aa in enumerate(out) for a in aa], [(6, 'notify'), (12, 'kill')])
            # 殺過這個 run 之後進未知再恢復：同 run 不再殺、也不再通知
            state, _ = self.replay(self.frames(self.ct, self.ct + 12))
            state, _ = self.replay(self.frames(self.ct + 13, self.ct + 17, read=read), state=state)
            _, out = self.replay(self.frames(self.ct + 18, self.ct + 50), state=state)
            self.assertEqual(self.flat(out), [])

    def test_K05_run_mismatch_06(self):
        state, _ = self.replay(self.frames(self.ct, self.ct + 11))
        _, out = self.replay([[item(self.task, self.run, self.ct + 12, 'unknown')],
                             [item(self.task, self.run + 1, self.ct + 13)]], state=state)
        self.assertEqual(out, [[], []])

    def test_K07_source_clock_07(self):
        state, out = self.replay(self.frames(self.ct, self.ct) * 50)
        self.assertEqual(self.flat(out), [])
        _, out = self.replay(self.frames(self.ct + 20, self.ct + 20), state=state)
        self.assertEqual([a['op'] for a in out[0]], ['notify', 'kill'])

    def test_K08_only_noise_08(self):
        noisy = dict(self.task, line='只是換一句話', stall=99, trail=['只是雜訊'])
        state, out = self.replay(self.frames(self.ct, self.ct) + self.frames(self.ct + 1, self.ct + 12, task=noisy))
        self.assertEqual([a['op'] for a in self.flat(out)], ['notify', 'kill'])
        for task in (dict(noisy, step=noisy['step'] + 1), dict(noisy, step=noisy['step'] - 1),
                     dict(noisy, id=noisy['id'] + '新信')):
            _, out = self.replay(self.frames(self.ct + 13, self.ct + 25, task=task), state=state)
            self.assertEqual(out[:6], [[]] * 6)
            self.assertEqual([a['op'] for a in self.flat(out)], ['notify'] if task['id'] != noisy['id'] else [])

    def test_capture_fake_replay_09(self):
        records = [json.loads(line) for line in (FIX / 'capture-fake.jsonl').read_text(encoding='utf-8').splitlines()]
        records = [r for r in records if 'event' not in r]
        frames = [[item(r['task'], r['run'], r['completed_tock'])] for r in records]
        first = next(r for r in records if isinstance(r['task'], dict))
        for cfg, ops in ((config(), ['notify']), (config(kill_after_rounds=7), ['notify', 'kill'])):
            _, out = self.replay(frames, cfg)
            actions = self.flat(out)
            self.assertEqual([a['op'] for a in actions], ops)
            self.assertTrue(all(a['basis']['id'] == first['task']['id'] and a['basis']['step'] == 2 for a in actions))
            self.assertTrue(all(a['run'] == first['run'] for a in actions if a['op'] == 'kill'))
            self.assertTrue(all(not aa for r, aa in zip(records, out) if r['completed_tock'] >= 11))

    def test_params_and_purity_10(self):
        frames = self.frames(self.ct, self.ct + 12)
        wrapped = frames
        _, out = self.replay(wrapped, config(no_progress_rounds=1, kill_after_rounds=2),
                             rule=dict(no_progress_rounds=3, kill_after_rounds=4, notify='管理者'))
        self.assertEqual([(i, a['op']) for i, aa in enumerate(out) for a in aa], [(3, 'notify'), (4, 'kill')])
        self.assertEqual(out[3][0]['target'], '管理者')
        for bad in (True, 0, -1, '3', None, 1.5, '', []):
            _, out = self.replay(wrapped, config(no_progress_rounds=bad, kill_after_rounds=bad, notify=bad))
            self.assertEqual([(i, a['op']) for i, aa in enumerate(out) for a in aa], [(6, 'notify'), (12, 'kill')])
            self.assertEqual(out[6][0]['target'], bad if isinstance(bad, str) and bad else 'you')
        cfg = config(); cfg['targets'] = []
        _, out = self.replay(frames, cfg, state={'brains': []})
        self.assertEqual([a['op'] for a in self.flat(out)], ['notify'])
        _, out = self.replay(frames, config(), rule='壞參數')
        self.assertEqual([a['op'] for a in self.flat(out)], ['notify', 'kill'])

    def test_backoff_limit_new_letter_and_old_state(self):
        state, out = self.replay(self.frames(0, 12))
        self.assertEqual([a['op'] for a in self.flat(out)], ['notify', 'kill'])
        state, out = self.replay(self.frames(13, 37, run=26), state=state)
        self.assertEqual([(i, a['op']) for i, aa in enumerate(out) for a in aa], [(24, 'kill')])
        state, out = self.replay(self.frames(38, 86, run=27), state=state)
        self.assertEqual([(i, a['op']) for i, aa in enumerate(out) for a in aa], [(48, 'kill')])
        state, out = self.replay(self.frames(87, 400, run=28), state=state)
        self.assertEqual(self.flat(out), [])
        new = dict(self.task, id='另一封信')
        fresh, out = self.replay(self.frames(401, 413, run=29, task=new), state=state)
        self.assertEqual([a['op'] for a in self.flat(out)], ['notify', 'kill'])
        self.assertEqual(fresh['retries']['bob/brain']['count'], 1)
        old = {k: state[k] for k in ('brains', 'killed')}
        _, out = self.replay(self.frames(401, 425, run=29), state=old)
        self.assertEqual([a['op'] for a in self.flat(out)], ['kill'])

    def test_custom_maximum_and_step_reset(self):
        state, _ = self.replay(self.frames(0, 12), config(max_kills=1))
        _, out = self.replay(self.frames(13, 100, run=26), config(max_kills=1), state=state)
        self.assertEqual(self.flat(out), [])
        task = dict(self.task, step=self.task['step'] + 1)
        _, out = self.replay(self.frames(101, 113, run=26, task=task), config(max_kills=1), state=state)
        self.assertEqual([a['op'] for a in self.flat(out)], ['kill'])
        for bad in (True, 0, -1, '3'):
            state, _ = self.replay(self.frames(0, 12), config(max_kills=bad))
            _, out = self.replay(self.frames(13, 37, run=26), config(max_kills=bad), state=state)
            self.assertEqual([a['op'] for a in self.flat(out)], ['kill'])

    def test_title_body_and_flattening(self):
        frames = self.frames(0, 6, task=dict(self.task, line='第一行\n第二行' + '長' * 100))
        for frame in frames:
            frame[0]['title'] = '做 5 回合的整理\n附註' + '長' * 100
        _, out = self.replay(frames)
        note = out[6][0]
        self.assertIn('做 5 回合的整理', note['text'])
        self.assertNotIn(self.task['id'], note['text'])
        self.assertNotIn('\n', note['text'])
        self.assertIn('第一行 第二行', note['body'])
        self.assertLess(len(note['basis']['title']), 61)
        self.assertEqual(note['body'].count('## '), 4)

    def test_noop_11(self):
        self.assertEqual(set(RULES), {'supervise-brain', 'noop'})
        self.assertIs(RULES['supervise-brain'], supervise_brain)
        self.assertIs(RULES['noop'], noop)
        for state in (None, {}, {'資料': [1]}):
            before = deepcopy(state)
            result, actions = noop(None, None, state)
            self.assertEqual(actions, [])
            self.assertEqual(result, state or {})
            self.assertEqual(state, before)

    def test_state_bounded_12(self):
        state = None
        for run in range(300):
            state, out = self.replay(self.frames(run * 13, run * 13 + 12, run=run), state=state)
            self.assertEqual([a['op'] for a in self.flat(out)], ['notify', 'kill'] if run == 0 else [])
            if run == 19:
                size = len(json.dumps(state))
        self.assertLess(abs(len(json.dumps(state)) - size), 50)
        state, _ = self.replay([[]], dict(sources=[], targets=[], rules=[]), state=state)
        self.assertEqual(state, {'brains': {}, 'killed': {}, 'notified': {}, 'retries': {}, 'gaps': {}})

    def test_invalid_observation_13(self):
        state, _ = self.replay(self.frames(self.ct, self.ct + 11))
        invalid = [[], [item('bad', self.run, self.ct + 12)]]
        for field, value in (('run', True), ('completed_tock', True), ('value', []), ('read', '錯誤')):
            sample = item(self.task, self.run, self.ct + 12); sample[field] = value
            invalid.append([sample])
        for field, value in (('id', 3), ('step', True)):
            invalid.append([item(dict(self.task, **{field: value}), self.run, self.ct + 12)])
        wrong = item(self.task, self.run, self.ct + 12); wrong['file'] = 'task.json.bak'
        invalid.extend([[wrong], self.frames(self.ct + 12, self.ct + 12)[0] * 2])
        for frame in invalid:
            result, out = self.replay([frame], state=state)
            self.assertEqual(out, [[]])
            self.assertTrue(result['brains']['bob/brain']['gap'])
        cfg = config(); cfg['sources'][0]['kind'] = '其他'
        result, out = self.replay(self.frames(self.ct, self.ct + 12), cfg)
        self.assertEqual(self.flat(out), [])
        self.assertEqual(result['brains'], {})

    def test_clock_rollback_and_kill_once_14(self):
        state, _ = self.replay(self.frames(self.ct, self.ct + 3))
        _, out = self.replay(self.frames(0, 6), state=state)   # 來源鐘倒退＝從倒退那回合重建基準
        self.assertEqual([(i, a['op']) for i, aa in enumerate(out) for a in aa], [(6, 'notify')])
        state, _ = self.replay(self.frames(self.ct, self.ct + 12))
        _, out = self.replay(self.frames(0, 12), state=state)
        self.assertEqual(self.flat(out), [])
        state, _ = self.replay([[item(None, self.run, self.ct + 13)]], state=state)
        _, out = self.replay(self.frames(self.ct + 14, self.ct + 26), state=state)
        self.assertEqual(self.flat(out), [])

    def test_multiple_sources_and_output_copies_15(self):
        cfg = config()
        cfg['sources'].append(dict(node='alice', slot='brain', kind='brain'))
        cfg['targets'].append(dict(node='alice', slot='brain', extra=['原物件']))
        frames = self.frames(self.ct, self.ct + 12)
        for frame in frames:
            other = deepcopy(frame[0]); other['src'] = dict(node='alice', slot='brain', kind='brain')
            frame.append(other)
        state, out = self.replay(frames, cfg)
        self.assertEqual(len(out[6]), 2)
        self.assertEqual(len(out[12]), 2)
        kill = next(a for a in out[12] if a['basis']['src'] == 'alice/brain')
        self.assertEqual(kill['target'], cfg['targets'][1])
        kill['target']['extra'].append('改輸出')
        self.assertEqual(cfg['targets'][1]['extra'], ['原物件'])
        self.assertEqual(set(state['brains']), {'alice/brain', 'bob/brain'})


if __name__ == '__main__':
    unittest.main()
