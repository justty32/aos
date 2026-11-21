# Check the letter key reasoning_effort and the pack list reasoning_efforts: accepted ones go to request.json, others refused or ignored.
import json
import os
import shutil
import sys
import tempfile
import unittest

import test_ledger

for folder in ('py', 'py/tools/aos/kernel', 'py/tools/aos/kernel_llm'):
    sys.path.insert(0, str(test_ledger.PROTO / folder))
import packs  # noqa: E402
from aos.tool_io import Error  # noqa: E402

LEVELS = ['low', 'high', 'max']


def cfg(group):
    return {'endpoint': 'p', 'endpoints': {'p': group}, 'groups': {}, 'endpoints_base': ('/x', '/x/kernel.json'),
            'exec': '/x/llm_http', 'base': '/x', 'backends': {}}


def ask(group, **body):
    return packs.pick(cfg(group), dict({'request': {'messages': []}}, **body))


class Effort(unittest.TestCase):
    def test_offered_effort_is_kept_for_the_request_and_the_list_is_not_handed_on(self):
        group = {'url': 'u', 'model': 'm', 'api': 'responses', 'session_key': 'k', 'reasoning_efforts': LEVELS}
        name, pack, handed, target = ask(group, reasoning_effort='high')
        self.assertEqual(pack['reasoning_effort'], 'high')
        self.assertEqual(handed, {'url': 'u', 'model': 'm', 'api': 'responses'})
        self.assertEqual(pack['reasoning_efforts'], LEVELS)
        self.assertEqual(pack['attrs']['reasoning_efforts'], LEVELS)

    def test_no_effort_in_the_letter(self):
        name, pack, handed, target = ask({'model': 'm', 'reasoning_efforts': LEVELS})
        self.assertIsNone(pack['reasoning_effort'])
        self.assertEqual(handed, {'model': 'm'})

    def test_pack_without_the_list_ignores_the_key(self):
        name, pack, handed, target = ask({'url': 'u', 'model': 'm'}, reasoning_effort='high')
        self.assertIsNone(pack['reasoning_effort'])
        self.assertEqual(handed, {'url': 'u', 'model': 'm'})
        self.assertNotIn('reasoning_efforts', pack['attrs'])

    def test_forward_hands_any_name_on_unchecked(self):
        name, pack, handed, target = ask({'to': 'sol', 'kernel': '/k', 'reasoning_efforts': 'forward'},
                                         reasoning_effort='whatever')
        self.assertEqual(pack['reasoning_effort'], 'whatever')
        self.assertEqual(pack['attrs']['reasoning_efforts'], 'forward')

    def test_effort_the_pack_does_not_offer_is_refused_with_the_list(self):
        with self.assertRaises(Error) as caught:
            ask({'model': 'm', 'reasoning_efforts': LEVELS}, reasoning_effort='none')
        self.assertEqual(caught.exception.code, 'RequestBad')
        self.assertEqual(str(caught.exception),
                         'reasoning_effort "none" is not offered by endpoint p (it offers: low, high, max)')

    def test_effort_that_is_not_a_name_is_refused_even_without_the_list(self):
        for bad in ('', 3, None, ['high']):
            with self.subTest(bad=bad), self.assertRaises(Error) as caught:
                ask({'model': 'm'}, reasoning_effort=bad)
            self.assertEqual(caught.exception.code, 'RequestBad')

    def test_request_parameter_of_the_same_name_is_not_this_key(self):
        name, pack, handed, target = packs.pick(cfg({'model': 'm', 'reasoning_efforts': LEVELS}),
                                                {'request': {'messages': [], 'reasoning_effort': 'none'}})
        self.assertIsNone(pack['reasoning_effort'])

    def test_bad_lists_are_cfgbad(self):
        for bad in ([], {}, 'high', 'any', ['low', 'low'], ['low', ''], ['low', 3], {'low': '-low'}):
            with self.subTest(bad=bad), self.assertRaises(Error) as caught:
                ask({'model': 'm', 'reasoning_efforts': bad}, reasoning_effort='low')
            self.assertEqual(caught.exception.code, 'CfgBad')


@unittest.skipUnless(shutil.which('aos-directive'), 'needs aos-directive on PATH (an installed tree)')
class SharedList(unittest.TestCase):
    """Lists at the top of kernel.json, packs point at them with $ref (an array of $ref joins arrays)."""

    def test_ref_to_shared_lists(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        doc = {'exec': 'f', 'reasoning_effort_levels': {'gpt': ['low', 'high'], 'none': ['none']},
               'endpoints': {'sol': {'model': 'sol', 'reasoning_efforts': {'$ref': '#/reasoning_effort_levels/gpt'},
                                     'cost': 'high'},
                             'luna': {'model': 'luna', 'reasoning_efforts': {
                                 '$ref': ['#/reasoning_effort_levels/gpt', '#/reasoning_effort_levels/none']}},
                             'fake': {'exec': 'g'}}}
        path = os.path.join(folder, 'kernel.json')
        with open(path, 'w') as stream:
            json.dump(doc, stream)
        read = packs.read_cfg(path, folder)
        window = packs.window(read['packs'])
        self.assertEqual(window['sol'], {'speed': 'normal', 'cost': 'high', 'reasoning_efforts': ['low', 'high']})
        self.assertEqual(window['luna']['reasoning_efforts'], ['low', 'high', 'none'])
        self.assertNotIn('reasoning_efforts', window['fake'])
        name, pack, handed, target = packs.pick(read, {'endpoint': 'luna', 'request': {'messages': []},
                                                      'reasoning_effort': 'none'})
        self.assertEqual((pack['reasoning_effort'], handed), ('none', {'model': 'luna'}))


if __name__ == '__main__':
    unittest.main()
