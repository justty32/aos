# Verify registered_envs / add_letter for parent and notify_box (ok-devt-1114 05 修訂 1): only an add that carries envs records them; without envs the letter is unchanged.
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PROTO8 = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROTO8 / 'lib'))
import daemon_ctl as dc  # noqa: E402

P, N = dc.PARENT_ENV, dc.NOTIFY_ENV


class Registered(unittest.TestCase):
    def test_names(self):
        self.assertEqual((P, N), ('AOS_PARENT_STACK', 'AOS_NOTIFY_BOX'))

    def test_no_envs_adds_nothing(self):
        self.assertEqual(dc.registered_envs({}, found_parent='/x/mom'), {})
        self.assertEqual(dc.registered_envs(None, found_parent='/x/mom'), {})

    def test_envs_get_both_names(self):
        self.assertEqual(dc.registered_envs({'X': '1'}), {'X': '1', P: '', N: ''})
        self.assertEqual(dc.registered_envs({'X': '1'}, found_parent='/x/mom/'), {'X': '1', P: '/x/mom', N: ''})
        self.assertEqual(dc.registered_envs({'X': '1'}, found_parent='rel'), {'X': '1', P: '', N: ''})

    def test_explicit_wins_and_makes_envs(self):
        self.assertEqual(dc.registered_envs({}, parent='/p', found_parent='/x'), {P: '/p', N: ''})
        self.assertEqual(dc.registered_envs({}, notify_box='/b', found_parent='/x'), {P: '/x', N: '/b'})
        self.assertEqual(dc.registered_envs({}, parent=''), {P: '', N: ''})
        self.assertEqual(dc.registered_envs({P: '/p'}, parent='/p', found_parent='/x'), {P: '/p', N: ''})
        self.assertEqual(dc.registered_envs({P: '/e'}, found_parent='/x'), {P: '/e', N: ''})

    def test_disagreement_and_format(self):
        cases = (((({P: '/a'},), {'parent': '/b'}), '--parent'),
                 ((({N: '/a'},), {'notify_box': '/b'}), '--notify-box'),
                 ((({},), {'parent': 'rel'}), '--parent'),
                 ((({},), {'notify_box': '/a/../b'}), '--notify-box'),
                 ((({P: 'rel'},), {}), '--envs AOS_PARENT_STACK'),
                 ((({N: '/a/..'},), {}), '--envs AOS_NOTIFY_BOX'))
        for (args, kw), said in cases:
            with self.subTest(args=args, kw=kw):
                with self.assertRaises(dc.Fail) as e:
                    dc.registered_envs(*args, **kw)
                self.assertEqual(e.exception.code, 'ArgumentsBad')
                self.assertIn(said, str(e.exception))


    def test_not_a_string_is_arguments_bad(self):
        for args, kw, said in ((({P: 1},), {}, '--envs AOS_PARENT_STACK'), (({N: None},), {}, '--envs AOS_NOTIFY_BOX'),
                               (({},), {'parent': 3}, '--parent'), (({},), {'notify_box': ['/x']}, '--notify-box')):
            with self.subTest(args=args, kw=kw):
                with self.assertRaises(dc.Fail) as e:
                    dc.registered_envs(*args, **kw)
                self.assertEqual(e.exception.code, 'ArgumentsBad')
                self.assertIn(said, str(e.exception))

    def test_given_and_found_are_normalised_alike(self):
        self.assertEqual(dc.registered_envs({}, parent='/x//mom/', notify_box='/x/box/'), {P: '/x/mom', N: '/x/box'})
        self.assertEqual(dc.registered_envs({'X': '1'}, found_parent='/x//mom/'), {'X': '1', P: '/x/mom', N: ''})


class Letter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = os.path.join(os.path.realpath(self.tmp.name), 'def')
        os.mkdir(self.target)

    def test_without_envs_the_letter_is_unchanged(self):
        """guard rail: a found parent alone never wraps the exec (修訂 1)"""
        before = dc.add_letter(self.target, name='k')
        after = dc.add_letter(self.target, name='k', found_parent='/x/mom')
        self.assertEqual(before, after)
        self.assertIsInstance(after[1]['procs_added']['k']['exec'], str)

    def test_with_envs_both_names_are_in_the_single(self):
        spec = dc.add_letter(self.target, name='k', envs={'X': '1'}, found_parent='/x/mom')[1]['procs_added']['k']
        self.assertEqual(spec['exec']['envs'], {'X': '1', P: '/x/mom', N: ''})
        spec = dc.add_letter(self.target, name='k', notify_box='/x/box')[1]['procs_added']['k']
        self.assertEqual(spec['exec']['envs'], {P: '', N: '/x/box'})


if __name__ == '__main__':
    unittest.main()
