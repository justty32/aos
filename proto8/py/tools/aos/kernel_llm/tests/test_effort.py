# Check the letter key effort and the pack table efforts: suffix or overlay, unknown effort refused, no table = untouched.
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

LEVELS = {'low': '-low', 'high': '-high', 'max': '-max'}


def cfg(group):
    return {'endpoint': 'p', 'endpoints': {'p': group}, 'groups': {}, 'endpoints_base': ('/x', '/x/kernel.json'),
            'exec': '/x/llm_http', 'base': '/x', 'backends': {}}


def ask(group, **body):
    return packs.pick(cfg(group), dict({'request': {'messages': []}}, **body))


class Effort(unittest.TestCase):
    def test_suffix_goes_after_the_model_and_the_table_is_not_handed_on(self):
        group = {'url': 'u', 'model': 'm', 'fixed': {'temperature': 0.2}, 'session_key': 'k', 'efforts': LEVELS}
        name, pack, handed, target = ask(group, effort='high')
        self.assertEqual(handed, {'url': 'u', 'model': 'm-high', 'fixed': {'temperature': 0.2}})
        self.assertEqual(pack['efforts'], ['low', 'high', 'max'])
        self.assertEqual(pack['session_key'], 'k')
        self.assertEqual(group['model'], 'm')   # the table itself is not changed

    def test_no_effort_in_the_letter_keeps_the_pack_as_it_is(self):
        name, pack, handed, target = ask({'url': 'u', 'model': 'm', 'efforts': LEVELS})
        self.assertEqual(handed, {'url': 'u', 'model': 'm'})

    def test_pack_without_efforts_ignores_the_key(self):
        name, pack, handed, target = ask({'url': 'u', 'model': 'm'}, effort='high')
        self.assertEqual(handed, {'url': 'u', 'model': 'm'})
        self.assertNotIn('efforts', pack['attrs'])

    def test_object_is_laid_over_and_fixed_is_merged_key_by_key(self):
        group = {'url': 'u', 'model': 'm', 'fixed': {'temperature': 0.2},
                 'efforts': {'low': {'fixed': {'reasoning_effort': 'low'}}, 'big': {'model': 'm2', 'context': 9}}}
        self.assertEqual(ask(group, effort='low')[2],
                         {'url': 'u', 'model': 'm', 'fixed': {'temperature': 0.2, 'reasoning_effort': 'low'}})
        self.assertEqual(ask(group, effort='big')[2], {'url': 'u', 'model': 'm2', 'fixed': {'temperature': 0.2},
                                                       'context': 9})

    def test_fixed_from_an_effort_is_fixed_for_the_request_too(self):
        group = {'model': 'm', 'efforts': {'low': {'fixed': {'reasoning_effort': 'low'}}}}
        with self.assertRaises(Error) as caught:
            packs.pick(cfg(group), {'request': {'messages': [], 'reasoning_effort': 'high'}, 'effort': 'low'})
        self.assertEqual(caught.exception.code, 'RequestBad')

    def test_effort_the_pack_does_not_offer_is_refused_with_the_list(self):
        with self.assertRaises(Error) as caught:
            ask({'model': 'm', 'efforts': LEVELS}, effort='none')
        self.assertEqual(caught.exception.code, 'RequestBad')
        self.assertEqual(str(caught.exception), 'effort "none" is not offered by endpoint p (it offers: low, high, max)')

    def test_effort_that_is_not_a_name_is_refused(self):
        for bad in ('', 3, None, ['high']):
            with self.subTest(bad=bad), self.assertRaises(Error) as caught:
                ask({'model': 'm'}, effort=bad)
            self.assertEqual(caught.exception.code, 'RequestBad')

    def test_pack_default_effort_is_used_when_the_letter_names_none(self):
        group = {'url': 'u', 'model': 'm', 'efforts': LEVELS, 'effort': 'low'}
        name, pack, handed, target = ask(group)
        self.assertEqual(handed, {'url': 'u', 'model': 'm-low'})
        self.assertEqual(pack['attrs']['effort'], 'low')
        self.assertEqual(ask(group, effort='max')[2], {'url': 'u', 'model': 'm-max'})

    def test_pack_default_must_be_one_of_its_efforts(self):
        for group in ({'model': 'm', 'effort': 'low'}, {'model': 'm', 'efforts': LEVELS, 'effort': 'none'},
                      {'model': 'm', 'efforts': LEVELS, 'effort': 3}):
            with self.subTest(group=group), self.assertRaises(Error) as caught:
                ask(group)
            self.assertEqual(caught.exception.code, 'CfgBad')

    def test_bad_tables_are_cfgbad(self):
        for bad in ([], {}, 'high', {'': '-x'}, {'high': ''}, {'high': 3}, {'high': {}},
                    {'high': {'slots': 2}}, {'high': {'session_key': 'x'}}, {'high': {'fixed': 1}}):
            with self.subTest(bad=bad), self.assertRaises(Error) as caught:
                ask({'model': 'm', 'efforts': bad}, effort='high')
            self.assertEqual(caught.exception.code, 'CfgBad')
        with self.assertRaises(Error) as caught:
            ask({'url': 'u', 'efforts': LEVELS}, effort='high')
        self.assertEqual(caught.exception.code, 'CfgBad')
        self.assertIn('has no model', str(caught.exception))


@unittest.skipUnless(shutil.which('aos-directive'), 'needs aos-directive on PATH (an installed tree)')
class SharedTable(unittest.TestCase):
    """One table at the top of kernel.json, each pack points at it with $ref: the window and the request both see it."""

    def test_ref_to_a_shared_table(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        doc = {'exec': 'f', 'efforts': {'chatgpt': {'low': '-low', 'high': '-high'}},
               'endpoints': {'sol': {'model': 'sol', 'efforts': {'$ref': '#/efforts/chatgpt'}, 'cost': 'high'},
                             'luna': {'model': 'luna', 'efforts': {'$ref': ['#/efforts/chatgpt', '#/efforts/none']}},
                             'fake': {'exec': 'g'}}}
        doc['efforts']['none'] = {'none': '-nothink'}
        path = os.path.join(folder, 'kernel.json')
        with open(path, 'w') as stream:
            json.dump(doc, stream)
        read = packs.read_cfg(path, folder)
        window = packs.window(read['packs'])
        self.assertEqual(window['sol'], {'speed': 'normal', 'cost': 'high', 'efforts': ['low', 'high']})
        self.assertEqual(window['luna']['efforts'], ['low', 'high', 'none'])
        self.assertNotIn('efforts', window['fake'])
        name, pack, handed, target = packs.pick(read, {'endpoint': 'luna', 'request': {'messages': []},
                                                      'effort': 'none'})
        self.assertEqual(handed, {'model': 'luna-nothink'})


if __name__ == '__main__':
    unittest.main()
