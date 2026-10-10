"""審查 1–4：安全寫檔、無歧義 call 名與工具失敗回條。"""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from menucase import simple
import aos7_menu_io as mio
from aos7_menu import MenuError


class MenuIOReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.node = Path(self.temp.name)
        self.directory = self.node / 'menu/run'
        self.directory.mkdir(parents=True)
        self.tools = {'tools': {'check': {'argv': ['true'], 'out': 'code'}}}

    def write(self, path='out/reply.txt'):
        return mio.action(self.node, self.directory, {'write': path, 'text': 'safe'}, self.tools)

    def test_01_out_and_every_path_segment_symlinks_rejected(self):
        outside = self.node / 'outside'
        outside.mkdir()
        for segment in ('out', 'out/nested', 'out/nested/reply.txt'):
            with self.subTest(segment=segment):
                run = self.directory / segment.replace('/', '-')
                run.mkdir()
                link = run / segment
                link.parent.mkdir(parents=True, exist_ok=True)
                target = outside / 'victim' if segment.endswith('.txt') else outside
                if target.name == 'victim':
                    target.write_text('secret')
                link.symlink_to(target)
                with self.assertRaises(MenuError):
                    mio.action(self.node, run, {'write': 'out/nested/reply.txt', 'text': 'unsafe'}, self.tools)
                if target.name == 'victim':
                    self.assertEqual(target.read_text(), 'secret')
        actual = self.node / 'actual'
        actual.mkdir()
        alias = self.node / 'alias'
        alias.symlink_to(actual)
        with self.assertRaises(MenuError):
            mio.action(self.node, alias / 'run', {'write': 'out/reply.txt', 'text': 'unsafe'}, self.tools)
        self.assertFalse((actual / 'run/out/reply.txt').exists())

    def test_01_check_symlinks_rejected(self):
        for segment in ('.check', '.check/slot.txt'):
            with self.subTest(segment=segment):
                run = self.directory / segment.replace('/', '-')
                run.mkdir()
                link = run / segment
                link.parent.mkdir(parents=True, exist_ok=True)
                target = self.node / ('victim' if segment.endswith('.txt') else 'outside')
                if segment.endswith('.txt'):
                    target.write_text('secret')
                else:
                    target.mkdir(exist_ok=True)
                link.symlink_to(target)
                with self.assertRaises(MenuError):
                    mio.action(self.node, run, {'check': 'check', 'text': 'unsafe'}, self.tools)
                if segment.endswith('.txt'):
                    self.assertEqual(target.read_text(), 'secret')

    def test_02_exclusive_random_same_directory_temporary_files(self):
        out = self.directory / 'out'
        out.mkdir()
        victim = self.node / 'victim'
        victim.write_text('secret')
        (out / '.reply.txt.tmp').symlink_to(victim)
        check = self.directory / '.check'
        check.mkdir()
        (check / '.slot.txt.tmp').symlink_to(victim)
        opened = []
        renamed = []
        real_open, real_replace = os.open, os.replace
        def spy_open(path, flags, *args, **kw):
            if flags & os.O_CREAT:
                opened.append((path, flags, kw.get('dir_fd')))
            return real_open(path, flags, *args, **kw)
        def spy_replace(src, dst, *args, **kw):
            renamed.append((src, dst, kw))
            return real_replace(src, dst, *args, **kw)
        with patch.object(mio.os, 'open', side_effect=spy_open), patch.object(mio.os, 'replace', side_effect=spy_replace):
            self.write()
            self.write()
            mio.action(self.node, self.directory, {'check': 'check', 'text': 'checked'}, self.tools)
        self.assertEqual(len(opened), 3)
        self.assertEqual(len({p for p, _, _ in opened}), 3)
        for path, flags, directory_fd in opened:
            self.assertTrue(all(flags & bit for bit in (os.O_CREAT, os.O_EXCL, os.O_NOFOLLOW)))
            self.assertNotIn('/', str(path))
            self.assertIsNotNone(directory_fd)
        for _, _, kw in renamed:
            self.assertEqual(kw['src_dir_fd'], kw['dst_dir_fd'])
        self.assertEqual(victim.read_text(), 'secret')
        self.assertEqual((out / 'reply.txt').read_text(), 'safe')
        self.assertEqual((check / 'slot.txt').read_text(), 'checked')
        self.assertEqual([p.name for p in out.iterdir() if p.name.endswith('.tmp')], ['.reply.txt.tmp'])

    def test_02_temporary_name_collision_retries_without_following(self):
        out = self.directory / 'out'
        out.mkdir()
        victim = self.node / 'victim'
        victim.write_text('secret')
        collision = out / '.reply.txt.fixed.tmp'
        collision.symlink_to(victim)
        with patch.object(mio.secrets, 'token_hex', side_effect=['fixed', 'fresh']):
            self.write()
        self.assertTrue(collision.is_symlink())
        self.assertEqual(victim.read_text(), 'secret')
        self.assertEqual((out / 'reply.txt').read_text(), 'safe')

    def ai_call(self, call_id, rc=0):
        grant = {'holder': 'menu', 'gateway': 'llm.litellm'}
        state = {'run': 'run', 'nonce': '0123456789abcdef', 'calls': [], 'pending': {'call_id': call_id}}
        receipt = {'text': '選：1', 'used': 3, 'outcome': 'answered'}
        result = subprocess.CompletedProcess([], rc, json.dumps(receipt), '帳沒清\n詳細\n')
        with patch.object(mio.aos7_budget, 'ledger_running', return_value=True), patch.object(mio, 'read', return_value=grant), patch.object(mio.subprocess, 'run', return_value=result) as called:
            answer = mio.ai(self.node, self.directory, self.node / 'menu.json', state, 'prompt', 'model')
        return called.call_args.args[0], answer

    def test_03_call_identifier_is_always_sha256_32_and_logical_unchanged(self):
        identifiers = ['menu/a-b/c/1', 'menu/a/b-c/1', 'menu/' + 'long' * 20 + '/layer/1']
        names = []
        for call_id in identifiers:
            argv, _ = self.ai_call(call_id)
            call = argv[argv.index('--call') + 1]
            self.assertEqual(call, 'menu-' + hashlib.sha256(('0123456789abcdef\n' + call_id).encode()).hexdigest()[:32])
            self.assertEqual(argv[argv.index('--logical') + 1], 'menu/run')
            names.append(call)
        self.assertEqual(len(set(names)), len(names))

    def test_04_code_one_json_line_and_empty_output(self):
        tool = {'tools': {'result': {'argv': [sys.executable, '-B', '-c', 'pass'], 'out': 'json-line'}}}
        for rc, stdout, expected in [(0, '{"issues":"none"}\n', {'issues': 'none'}), (1, 'progress\n{"issues":"bad"}\n', {'issues': 'bad'}), (1, '', {}), (1, '\n  \n', {})]:
            with self.subTest(rc=rc, stdout=stdout):
                result = subprocess.CompletedProcess([], rc, stdout, '')
                with patch.object(mio.subprocess, 'run', return_value=result):
                    got = mio.action(self.node, self.directory, {'tool': 'result'}, tool)
                self.assertEqual(got['out'], expected)
                self.assertEqual(got['rc'], rc)
        for rc in (0, 1):
            with self.subTest(invalid_json_rc=rc):
                with patch.object(mio.subprocess, 'run', return_value=subprocess.CompletedProcess([], rc, 'bad', '')):
                    with self.assertRaises(mio.Stop) as stopped:
                        mio.action(self.node, self.directory, {'tool': 'result'}, tool)
                self.assertEqual(stopped.exception.code, 3)

    def test_11_ai_unsettled_does_not_print_before_command_finishes(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            _, reply = self.ai_call('menu/run/one/1', rc=4)
        self.assertEqual(reply[2], 4)
        self.assertEqual(stderr.getvalue(), '')

    def test_01_cli_symlink_rejected_code_two_single_line(self):
        fixture = self.node / 'fixture'
        fixture.mkdir()
        menu = fixture / 'menu.json'
        menu.write_text(json.dumps(simple({'max_lines': 1}), ensure_ascii=False))
        (fixture / 'practice.json').write_text(json.dumps({'v': 1, 'replies': ['選：1\n格：safe']}))
        run = self.node / 'menu/test'
        run.mkdir()
        outside = self.node / 'outside'
        outside.mkdir()
        victim = outside / 'reply.txt'
        victim.write_text('secret')
        (run / 'out').symlink_to(outside)
        result = subprocess.run([sys.executable, '-B', str(mio.PACK / 'bin/aos7-menu'),
                                 'run', str(self.node), str(menu)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        self.assertIn('符號連結', result.stderr)
        self.assertEqual(victim.read_text(), 'secret')
