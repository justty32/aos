"""Verify actual collection and serialized browser state preserve the explanation contract offline."""
import json
import unittest
from eli5_support import OfflineBoard, WORDS, eli5
import collect


class CollectionTests(OfflineBoard):
    def test_real_collect_serializes_generated_and_provided_explanations(self):
        self.events += [
            self.event('alpha', 'Choose.', id='generated', status='ask', options=[], recommend=None),
            self.event('beta', 'Choose.', id='provided', status='ask', options=[], recommend=None,
                       eli5='A supplied everyday explanation.')]
        self.flush()
        self.assertEqual(self.generate(), ('ok', 'ok'))
        calls = len(self.calls)
        state = collect.collect(self.board, self.cfg)
        self.assertEqual(len(self.calls), calls, 'Collection must never call the endpoint')
        asks = {ask['id']:ask for ask in state['asks']}
        self.assertEqual(asks['generated']['eli5']['text'], WORDS)
        self.assertFalse(asks['generated']['eli5']['stale'])
        supplied = asks['provided']['eli5']
        self.assertEqual(supplied, {'text':'A supplied everyday explanation.', 'provided':True,
                                   'stale':False, 'updated_at':asks['provided']['ts']})
        self.assertFalse(state['eli5']['main']['lines']['alpha']['stale'])
        self.assertFalse(state['eli5']['detail']['lines']['alpha']['timeline']['stale'])
        self.assertEqual(state['summary']['cost']['runs_today'], 2)
        self.assertEqual(state['summary']['cost']['tokens_today'], 36)
        last = state['summary']['cost']['last']
        self.assertTrue({'kind','prompt_tokens','completion_tokens','total_tokens','error'} <= set(last))
        self.assertIsNone(last['error'])
        collect.write_state(self.board, state)
        self.assertEqual(json.loads((self.board/'data/state.json').read_text()), state)
        js = (self.board/'data/state.js').read_text()
        self.assertTrue(js.startswith('window.AOS_STATE = '))
        self.assertEqual(json.loads(js.removeprefix('window.AOS_STATE = ').strip()[:-1]), state)
        self.assertTrue((self.board/'index.html').is_file())
        self.events[0]['text'] += ' More recent evidence.'
        self.flush()
        changed = collect.collect(self.board, self.cfg)
        self.assertEqual(len(self.calls), calls)
        self.assertTrue(changed['eli5']['main']['lines']['alpha']['stale'])
        self.assertTrue(changed['eli5']['detail']['lines']['alpha']['timeline']['stale'])
        self.assertFalse(changed['eli5']['main']['lines']['beta']['stale'])
        collect.write_state(self.board, changed)
        self.assertTrue(json.loads((self.board/'data/state.json').read_text())
                        ['eli5']['main']['lines']['alpha']['stale'])


if __name__ == '__main__':
    unittest.main()
