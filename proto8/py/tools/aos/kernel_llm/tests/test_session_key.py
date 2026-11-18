# Check the endpoint pack switch session_key: off = the request object untouched; on = one fixed id per sender.
import hashlib
import sys
import unittest

import test_ledger

for folder in ('py', 'py/tools/aos/kernel', 'py/tools/aos/kernel_llm'):
    sys.path.insert(0, str(test_ledger.PROTO / folder))
import packs  # noqa: E402
import session  # noqa: E402
from aos.tool_io import Error  # noqa: E402

SENDER = '/tmp/tree/.stack/procs/bob'


class Tag(unittest.TestCase):
    def test_off_returns_the_same_object(self):
        request = {'messages': [], 'tools': []}
        for key in (None, '', 0, ['litellm_session_id']):
            with self.subTest(key=key):
                self.assertIs(session.tag(key, SENDER, request), request)
        self.assertEqual(request, {'messages': [], 'tools': []})

    def test_on_adds_one_fixed_id_per_sender_to_a_copy(self):
        request = {'messages': [{'role': 'user', 'content': 'hi'}]}
        out = session.tag('litellm_session_id', SENDER, request)
        self.assertIsNot(out, request)
        self.assertNotIn('litellm_session_id', request)
        want = hashlib.sha256(SENDER.encode('utf-8')).hexdigest()[:32]
        self.assertEqual(out, {'messages': request['messages'], 'litellm_session_id': want})
        self.assertEqual(session.tag('litellm_session_id', SENDER, {'messages': []})['litellm_session_id'], want)
        other = session.tag('litellm_session_id', SENDER + '2', request)['litellm_session_id']
        self.assertNotEqual(other, want)
        self.assertRegex(want, '^[0-9a-f]{32}$')
        self.assertNotIn('bob', want)

    def test_no_sender_or_key_already_in_the_request_leaves_it(self):
        request = {'messages': []}
        for sender in ('', None, 7):
            with self.subTest(sender=sender):
                self.assertIs(session.tag('litellm_session_id', sender, request), request)
        own = {'messages': [], 'litellm_session_id': 'mine'}
        self.assertIs(session.tag('litellm_session_id', SENDER, own), own)
        self.assertIs(session.tag('litellm_session_id', SENDER, 'not an object'), 'not an object')


class Pack(unittest.TestCase):
    def cfg(self, group):
        return {'endpoint': 'p', 'endpoints': {'p': group}, 'groups': {}, 'endpoints_base': ('/x', '/x/kernel.json'),
                'exec': '/x/llm_http', 'base': '/x', 'backends': {}}

    def test_default_is_off_and_the_group_is_unchanged(self):
        group = {'url': 'http://127.0.0.1:1/v1', 'model': 'm', 'slots': 2}
        name, pack, handed, target = packs.pick(self.cfg(group), {'request': {'messages': []}})
        self.assertIsNone(pack['session_key'])
        self.assertEqual(handed, {'url': 'http://127.0.0.1:1/v1', 'model': 'm'})

    def test_switch_is_read_and_not_handed_to_the_endpoint_function(self):
        group = {'url': 'http://127.0.0.1:1/v1', 'model': 'm', 'session_key': 'litellm_session_id'}
        name, pack, handed, target = packs.pick(self.cfg(group), {'request': {'messages': []}})
        self.assertEqual(pack['session_key'], 'litellm_session_id')
        self.assertEqual(handed, {'url': 'http://127.0.0.1:1/v1', 'model': 'm'})
        self.assertNotIn('session_key', pack['attrs'])

    def test_bad_value_is_cfg_bad(self):
        for bad in ('', 5, True, ['a'], {'a': 1}):
            with self.subTest(bad=bad):
                with self.assertRaises(Error) as caught:
                    packs.pick(self.cfg({'url': 'u', 'session_key': bad}), {'request': {'messages': []}})
                self.assertEqual(caught.exception.code, 'CfgBad')
                self.assertIn('session_key', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
