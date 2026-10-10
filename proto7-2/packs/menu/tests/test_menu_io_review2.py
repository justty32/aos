"""二次審查 5／7：I/O 故障分流與同名 run 重建隔離。"""
import contextlib
import errno
import io
import os
import shutil
from unittest.mock import patch

from menucase import MenuCase, read_json, simple
import aos7_menu_io as mio
import aos7_menu_run as mrun
from aos7_menu_check import MenuError


class MenuIOReview2(MenuCase):
    def test_05_directory_open_io_errors_keep_original_exception(self):
        directory = self.node / 'fault'
        directory.mkdir()
        path = directory / 'state.json'
        path.write_text('original')
        real_open = os.open
        for number in (errno.EIO, errno.EMFILE, errno.EACCES):
            with self.subTest(errno=number):
                failure = OSError(number, 'injected filesystem failure')
                def fail_open(part, flags, *args, **kw):
                    if part == 'fault' and flags & os.O_DIRECTORY:
                        raise failure
                    return real_open(part, flags, *args, **kw)
                with patch.object(mio.os, 'open', side_effect=fail_open):
                    with self.assertRaises(OSError) as caught:
                        mio.atomic_text(path, 'changed')
                self.assertIs(caught.exception, failure)
                self.assertEqual(path.read_text(), 'original')

    def test_05_directory_type_must_be_confirmed(self):
        ordinary = self.node / 'ordinary'
        ordinary.mkdir()
        link = self.node / 'link'
        link.symlink_to(ordinary, target_is_directory=True)
        file = self.node / 'file'
        file.write_text('original')
        for parent in (link, file):
            with self.subTest(parent=parent.name):
                with self.assertRaises(MenuError):
                    mio.atomic_text(parent / 'state.json', 'changed')
        failure = OSError(errno.EIO, 'open failed')
        real_open = os.open
        def fail_open(part, flags, *args, **kw):
            if part == 'ordinary' and flags & os.O_DIRECTORY:
                raise failure
            return real_open(part, flags, *args, **kw)
        with patch.object(mio.os, 'open', side_effect=fail_open), patch.object(
                mio.os, 'stat', side_effect=OSError(errno.EACCES, 'cannot inspect')):
            with self.assertRaises(OSError) as caught:
                mio.atomic_text(ordinary / 'state.json', 'changed')
        self.assertIs(caught.exception, failure)
        self.assertEqual(file.read_text(), 'original')

    def test_05_cli_state_write_io_errors_exit_three_single_line(self):
        menu = self.fixture(simple())
        reply = self.node / 'reply'
        reply.write_text('不像')
        self.run_menu('--reply', reply, menu=menu)
        run = self.node / 'menu/test'
        before = {name: (run / name).read_bytes() for name in ('state.json', 'log.jsonl')}
        real_open = os.open
        for number in (errno.EIO, errno.EMFILE, errno.EACCES):
            with self.subTest(errno=number):
                def fail_open(part, flags, *args, **kw):
                    if part == 'test' and flags & os.O_DIRECTORY:
                        raise OSError(number, 'injected filesystem failure')
                    return real_open(part, flags, *args, **kw)
                stderr = io.StringIO()
                with patch.object(mio.os, 'open', side_effect=fail_open), contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                    code = mrun.main(['run', str(self.node), str(menu), '--reply', str(reply)])
                self.assertEqual(code, 3, stderr.getvalue())
                self.assertEqual(len(stderr.getvalue().splitlines()), 1)
                self.assertIn('不確定', stderr.getvalue())
                self.assertNotIn('符號連結', stderr.getvalue())
                self.assertEqual({name: (run / name).read_bytes() for name in before}, before)

    def test_07_recreated_same_run_llm_never_reuses_or_conflicts(self):
        self.ledger()
        menu = self.fixture(simple({'max_lines': 1}), ['選：1\n格：first'])
        run = self.node / 'menu/test'
        states = []
        for i in range(3):
            with self.subTest(rebuild=i):
                if i:
                    shutil.rmtree(run)
                if i == 2:
                    obj = simple({'max_lines': 1})
                    obj['layers']['one']['ask'] = '另一份問題'
                    menu = self.fixture(obj, ['選：1\n格：second'])
                self.run_menu('--llm', 'fake', menu=menu)
                state = self.state('test')
                states.append(state)
                self.assertEqual(state['status'], 'done')
                self.assertRegex(state['nonce'], r'^[0-9a-f]{16}$')
                self.assertEqual((run / 'out/reply.txt').read_text().strip(), 'second' if i == 2 else 'first')
                sends = read_json(str(self.node / 'llmcall/fake-remote.json'))['sends']
                self.assertEqual(sum(sends.values()), i + 1)
                self.assertEqual(set(sends.values()), {1})
                self.assertEqual([row['call_id'] for row in self.logs('test') if row['kind'] == 'ask'],
                                 [call['call_id'] for call in state['calls']])
        self.assertEqual(len({state['nonce'] for state in states}), 3)
        self.assertEqual([call['call_id'] for call in states[0]['calls']],
                         [call['call_id'] for call in states[1]['calls']])
        self.assertEqual([call['call_id'] for call in states[1]['calls']],
                         [call['call_id'] for call in states[2]['calls']])
