"""proto5/tools/base/ 與 aos-agent tools add：對 2026-09-24 astra 唯讀審查
（proto5/notes/2026-09-24-tools-base-review-astra.md）修過的地方逐條補測試。

共用底：ToolCase（假 agent 家、run_tool）在 test_tools_base.py；
tools add 用 test_agent_tools.py 的 run_agent／PACKAGE。
"""
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from test_tools_base import ToolCase
from test_agent_tools import run_agent, PACKAGE
from _kernel_util import CLI, PY, read_json


# =========================================================== 1. 暫存檔 ====

class TestTmpFileFixes(ToolCase):
    """write／edit 的暫存檔：不留殘留、新檔權限跟 umask、不能經符號連結覆寫根目錄外檔案。"""

    def test_no_leftover_tmp_after_write(self):
        self.assertOk(self.run_tool('write', {'path': 'f.txt', 'content': 'x'}))
        self.assertEqual(self.no_leftover_tmp(), [])

    def test_no_leftover_tmp_after_edit(self):
        self.wwrite('f.txt', 'hi\n')
        self.assertOk(self.run_tool('edit', {'path': 'f.txt', 'old_string': 'hi', 'new_string': 'bye'}))
        self.assertEqual(self.no_leftover_tmp(), [])

    def test_new_file_permission_matches_umask(self):
        old = os.umask(0o022)
        self.addCleanup(os.umask, old)
        self.assertOk(self.run_tool('write', {'path': 'new.txt', 'content': 'x'}))
        mode = stat.S_IMODE(os.stat(self.wpath('new.txt')).st_mode)
        self.assertEqual(oct(mode), oct(0o644))

    def test_write_through_symlink_to_outside_file_is_outside_root(self):
        outer_dir = tempfile.mkdtemp(prefix='aos-tools-outerfile-')
        self.addCleanup(shutil.rmtree, outer_dir, ignore_errors=True)
        outer_file = os.path.join(outer_dir, 'secret.txt')
        with open(outer_file, 'w') as f:
            f.write('original\n')
        os.symlink(outer_file, self.wpath('link.txt'))
        self.assertErr(self.run_tool('write', {'path': 'link.txt', 'content': 'evil'}), 'OutsideRoot')
        with open(outer_file) as f:
            self.assertEqual(f.read(), 'original\n')

    def test_edit_through_symlink_to_outside_file_is_outside_root(self):
        outer_dir = tempfile.mkdtemp(prefix='aos-tools-outerfile2-')
        self.addCleanup(shutil.rmtree, outer_dir, ignore_errors=True)
        outer_file = os.path.join(outer_dir, 'secret.txt')
        with open(outer_file, 'w') as f:
            f.write('original\n')
        os.symlink(outer_file, self.wpath('link2.txt'))
        self.assertErr(self.run_tool('edit', {'path': 'link2.txt', 'old_string': 'original',
                                              'new_string': 'evil'}), 'OutsideRoot')
        with open(outer_file) as f:
            self.assertEqual(f.read(), 'original\n')


# ========================================================== 2. arg() ====

class TestArgFixes(ToolCase):
    """arg() 對 NUL、孤立 surrogate 的參數要回 BadArguments，不是漏 Traceback 出來。"""

    def test_bash_command_with_nul_is_bad_arguments_no_traceback(self):
        code, out, j = self.run_tool('bash', {'command': 'echo\x00hi'})
        self.assertEqual(code, 1)
        self.assertNotIn('Traceback', out)
        self.assertIsNotNone(j, 'stdout 最後一行不是 JSON: %r' % out)
        self.assertFalse(j.get('ok'))
        self.assertEqual(j.get('error'), 'BadArguments')

    def test_read_path_with_lone_surrogate_is_bad_arguments_no_traceback(self):
        # 用原始 JSON 文字直接送 \ud800（json.dumps(ensure_ascii=False) 在 Python 端就會先炸，
        # 所以不能走 run_tool；要跟 TestCommonArguments._raw 一樣自己組 stdin）。
        exe = os.path.join(self.home, 'tools', 'base', 'read')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        raw = '{"path": "\\ud800"}'
        p = subprocess.run([exe], input=raw, cwd=self.home, capture_output=True,
                           text=True, encoding='utf-8', env=env, timeout=10)
        self.assertEqual(p.returncode, 1)
        self.assertNotIn('Traceback', p.stdout)
        stripped = p.stdout.rstrip('\n')
        self.assertTrue(stripped)
        j = json.loads(stripped.rsplit('\n', 1)[-1])
        self.assertFalse(j.get('ok'))
        self.assertEqual(j.get('error'), 'BadArguments')


# ============================================================ 3. read ====

class TestReadFixes(ToolCase):

    def test_limit_2001_is_bad_arguments(self):
        self.wwrite('f.txt', 'a\n')
        self.assertErr(self.run_tool('read', {'path': 'f.txt', 'limit': 2001}), 'BadArguments')

    def test_huge_single_line_file_limit_1_is_bounded(self):
        self.wwrite('huge.txt', 'a' * (5 * 1024 * 1024))
        code, out, j = self.run_tool('read', {'path': 'huge.txt', 'limit': 1}, timeout=30)
        self.assertEqual(code, 0, out[:200])
        self.assertLess(len(out.encode('utf-8')), 10 * 1024)
        self.assertIn('line truncated', out)

    def test_read_on_fifo_is_not_a_regular_file_and_returns_quickly(self):
        os.mkfifo(self.wpath('myfifo'))
        start = time.monotonic()
        self.assertErr(self.run_tool('read', {'path': 'myfifo'}, timeout=5), 'NotARegularFile')
        self.assertLess(time.monotonic() - start, 5)

    def test_offset_near_end_of_200k_line_file(self):
        n = 200000
        self.wwrite('lines.txt', ''.join('l%d\n' % i for i in range(1, n + 1)))
        out = self.assertOk(self.run_tool('read', {'path': 'lines.txt', 'offset': 199999, 'limit': 2},
                                          timeout=20))
        self.assertIn('l199999\n', out)
        self.assertIn('l200000\n', out)
        self.assertNotIn('l199998\n', out)


# ============================================================ 4. edit ====

class TestEditFixes(ToolCase):

    def test_file_over_10mb_is_file_too_large(self):
        self.wwrite('big.bin', 'a' * (10 * 1024 * 1024 + 1))
        self.assertErr(self.run_tool('edit', {'path': 'big.bin', 'old_string': 'a', 'new_string': 'b'},
                                     timeout=20), 'FileTooLarge')

    def test_crlf_file_lf_multiline_old_string_hints_crlf(self):
        self.wwrite('crlf2.txt', 'line1\r\nline2\r\nline3\r\n')
        j = self.assertErr(self.run_tool('edit', {'path': 'crlf2.txt', 'old_string': 'line1\nline2',
                                                  'new_string': 'X'}), 'NoMatch')
        self.assertIn('CRLF', j['message'])


# ============================================================ 5. grep ====

class TestGrepFixes(ToolCase):

    def setUp(self):
        super().setUp()
        self.wwrite('a.txt', 'hit\n')

    def _fake_rg_py(self, code):
        d = tempfile.mkdtemp(prefix='aos-tools-fakerg-')
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        path = os.path.join(d, 'rg')
        with open(path, 'w') as f:
            f.write('#!/usr/bin/env python3\n' + code)
        os.chmod(path, 0o755)
        return path

    @unittest.skipUnless(shutil.which('rg'), 'ripgrep 沒裝，跳過（本測試專門驗證真 rg 的行為）')
    def test_ignores_ripgrep_config_path_follow_symlink(self):
        outer = tempfile.mkdtemp(prefix='aos-tools-grep-outer-')
        self.addCleanup(shutil.rmtree, outer, ignore_errors=True)
        with open(os.path.join(outer, 'outside.txt'), 'w') as f:
            f.write('needle-outside\n')
        os.symlink(outer, self.wpath('linkdir'))
        fd, cfg = tempfile.mkstemp(prefix='aos-tools-rgrc-', suffix='.rgrc')
        self.addCleanup(os.unlink, cfg)
        with os.fdopen(fd, 'w') as f:
            f.write('--follow\n--hidden\n')
        out = self.assertOk(self.run_tool('grep', {'pattern': 'needle-outside'},
                                          env={'RIPGREP_CONFIG_PATH': cfg}))
        self.assertNotIn('outside.txt', out)
        self.assertIn('No matches found', out)

    def test_fake_rg_silent_hang_times_out_and_kills_process(self):
        pidfile = self.wpath('rg.pid')
        fake = self._fake_rg_py(
            "import os, time\n"
            "open(%r, 'w').write(str(os.getpid()))\n"
            "time.sleep(60)\n" % pidfile)
        start = time.monotonic()
        code, out, j = self.run_tool('grep', {'pattern': 'hit'},
                                     env={'AOS_TOOLS_RG': fake, 'AOS_TOOLS_GREP_TIMEOUT': '2'}, timeout=10)
        elapsed = time.monotonic() - start
        self.assertEqual(code, 1, out)
        self.assertEqual(j['error'], 'Timeout')
        self.assertLess(elapsed, 8, '逾時後該在幾秒內回，實際花了 %.1fs' % elapsed)
        deadline = time.monotonic() + 3
        while not os.path.exists(pidfile) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(os.path.exists(pidfile), '假 rg 沒來得及寫 pid 檔')
        with open(pidfile) as f:
            pid = int(f.read().strip())
        time.sleep(0.3)
        with self.assertRaises(OSError, msg='假 rg 的行程 %d 在逾時收掉之後應該已經不在了' % pid):
            os.kill(pid, 0)

    def test_fake_rg_stderr_flood_does_not_deadlock(self):
        fake = self._fake_rg_py(
            "import sys\n"
            "sys.stderr.write('e' * (1024 * 1024))\n"
            "sys.stderr.flush()\n"
            "sys.stdout.write('a.py:1:hit\\n')\n"
            "sys.stdout.flush()\n")
        out = self.assertOk(self.run_tool('grep', {'pattern': 'hit'}, env={'AOS_TOOLS_RG': fake}, timeout=10))
        self.assertIn('a.py:1:hit', out)

    def test_fake_rg_huge_single_line_no_newline_is_bounded(self):
        fake = self._fake_rg_py(
            "import sys\n"
            "sys.stdout.write('a.py:1:' + ('x' * 5000000))\n"
            "sys.stdout.flush()\n")
        code, out, j = self.run_tool('grep', {'pattern': 'x'}, env={'AOS_TOOLS_RG': fake}, timeout=20)
        self.assertEqual(code, 0, out[:200])
        self.assertLess(len(out.encode('utf-8')), 10 * 1024)
        self.assertIn('line truncated', out)

    def test_fake_rg_delayed_output_past_timeout_is_timeout_not_no_matches(self):
        fake = self._fake_rg_py(
            "import time, sys\n"
            "time.sleep(3)\n"
            "sys.stdout.write('a.py:1:hit\\n')\n"
            "sys.stdout.flush()\n")
        code, out, j = self.run_tool('grep', {'pattern': 'hit'},
                                     env={'AOS_TOOLS_RG': fake, 'AOS_TOOLS_GREP_TIMEOUT': '1'}, timeout=10)
        self.assertEqual(code, 1, out)
        self.assertEqual(j['error'], 'Timeout')
        self.assertNotIn('No matches found', out)


# ============================================================ 6. find ====

class TestFindFixes(ToolCase):

    @unittest.skipIf(hasattr(os, 'geteuid') and os.geteuid() == 0,
                     'root 不受檔案權限限制，chmod 000 攔不住，這條測試沒意義')
    def test_unreadable_subdirectory_is_reported_as_warning_not_silently_dropped(self):
        forbidden = self.wpath('forbidden')
        os.makedirs(os.path.join(forbidden, 'nested'))
        self.wwrite('forbidden/nested/x.py', '')
        self.wwrite('ok.py', '')
        os.chmod(forbidden, 0o000)
        self.addCleanup(os.chmod, forbidden, 0o755)
        out = self.assertOk(self.run_tool('find', {'pattern': '*.py'}))
        self.assertIn('ok.py', out)
        self.assertIn('warning:', out)
        self.assertIn('skipped', out)


# ============================================================ 7. bash ====

class TestBashSigtermFixes(ToolCase):

    def test_wrapper_sigterm_reaps_child_process_group(self):
        exe = os.path.join(self.home, 'tools', 'base', 'bash')
        pidfile = self.wpath('shell.pid')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, cwd=self.home, env=env, text=True)
        self.addCleanup(lambda: (p.poll() is None and (p.kill(), p.wait(timeout=5))))
        self.addCleanup(lambda: p.stdout and p.stdout.close())
        try:
            payload = json.dumps({'command': 'echo $$ > shell.pid; sleep 30'})
            p.stdin.write(payload)
            p.stdin.close()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not os.path.exists(pidfile):
                time.sleep(0.05)
            self.assertTrue(os.path.exists(pidfile), 'pid 檔沒在時間內出現')
            time.sleep(0.2)  # 讓 shell 真的跑到 sleep 30
            with open(pidfile) as f:
                pid = int(f.read().strip())
            p.send_signal(signal.SIGTERM)
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)
                self.fail('bash wrapper 收到 SIGTERM 後沒有在時間內退出')
            deadline2 = time.monotonic() + 5
            gone = False
            while time.monotonic() < deadline2:
                try:
                    os.kill(pid, 0)
                except OSError:
                    gone = True
                    break
                time.sleep(0.1)
            self.assertTrue(gone, 'shell 行程 %d 在 wrapper 退出後幾秒內仍在' % pid)
        finally:
            if p.poll() is None:
                p.kill()
                p.wait(timeout=5)


# ==================================================== 8. aos-agent tools add ====

def make_home(path, tools=()):
    """不跑 aos-agent init、直接寫最小合法 info.json（省一次 subprocess）。"""
    path.mkdir(parents=True, exist_ok=True)
    doc = {'_metainfo': {'_type': 'llm_agent', '_version': 1}, 'llm': {'model': 'm'},
           'tools': list(tools)}
    (path / 'info.json').write_text(json.dumps(doc), encoding='utf-8')
    return path


def make_pkg(base_dir, name, tool_name):
    """自製最小工具包：<name>/<name>.json + 一支可執行的 run。"""
    pkg = base_dir / name
    pkg.mkdir(parents=True)
    (pkg / (name + '.json')).write_text(json.dumps([
        {'type': 'function', 'function': {'name': tool_name}, '_meta': {'argv': ['tools/%s/run' % name]}}]),
        encoding='utf-8')
    prog = pkg / 'run'
    prog.write_text('#!/bin/sh\necho %s\n' % tool_name, encoding='utf-8')
    prog.chmod(0o755)
    return pkg


class ToolsAddFixCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-tools-add-fix-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.bob = make_home(self.root / 'bob', tools=[])

    def add(self, *extra, target=None, code=0):
        result = run_agent('tools', 'add', *extra, '--target', target or self.bob)
        if code is not None:
            self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def info(self, base=None):
        return read_json((base or self.bob) / 'info.json')


class TestToolsAddSymlinkAndForce(ToolsAddFixCase):
    """symlink 命名、--force 換連結刪舊版本、殘渣清理（只清自己版本，別包不動）。"""

    def test_symlink_target_matches_dot_name_dash_number_pattern(self):
        self.add('base')
        target = os.readlink(self.bob / 'tools/base')
        self.assertRegex(target, r'^\.base-\d+$')

    def test_force_reinstall_swaps_symlink_and_deletes_old_version_dir(self):
        self.add('base')
        old_target = os.readlink(self.bob / 'tools/base')
        old_version_dir = self.bob / 'tools' / old_target
        self.assertTrue(old_version_dir.is_dir())
        self.add('base', '--force')
        new_target = os.readlink(self.bob / 'tools/base')
        self.assertNotEqual(old_target, new_target)
        self.assertFalse(old_version_dir.exists(), '舊版本資料夾該被刪掉')
        self.assertTrue((self.bob / 'tools' / new_target).is_dir())

    def test_force_reinstall_keeps_config_json(self):
        self.add('base')
        (self.bob / 'tools/base/config.json').write_text(json.dumps({'root': 'elsewhere'}))
        self.add('base', '--force')
        self.assertEqual(read_json(self.bob / 'tools/base/config.json'), {'root': 'elsewhere'})

    def test_stale_leftovers_from_our_versions_cleaned_other_packages_kept(self):
        self.add('base')
        (self.bob / 'tools/.base-123.tmp').mkdir()
        (self.bob / 'tools/.base-456').mkdir()
        (self.bob / 'tools/.base-extra-789').mkdir()
        self.add('base', '--force')
        self.assertFalse((self.bob / 'tools/.base-123.tmp').exists())
        self.assertFalse((self.bob / 'tools/.base-456').exists())
        self.assertTrue((self.bob / 'tools/.base-extra-789').exists(),
                        '別的包的殘渣（名字不是 .base-<純數字>）不該被清掉')

    def test_legacy_real_directory_install_force_becomes_symlink(self):
        # 模擬舊式安裝：tools/base 是真資料夾，不是連結。
        shutil.copytree(PACKAGE, self.bob / 'tools' / 'base',
                        ignore=shutil.ignore_patterns('base.json', '__pycache__', '*.pyc'))
        self.assertFalse((self.bob / 'tools' / 'base').is_symlink())
        shutil.copy2(PACKAGE / 'base.json', self.bob / 'tools' / 'base.json')
        self.add('base', '--force')
        self.assertTrue((self.bob / 'tools' / 'base').is_symlink())


class TestToolsAddRepairAndBadName(ToolsAddFixCase):

    def test_repairs_missing_info_entry_without_force(self):
        amy = make_home(self.root / 'amy', tools=['other.json'])
        (amy / 'other.json').write_text('[]')
        (amy / 'tools').mkdir()
        (amy / 'tools/base.json').write_text(json.dumps(read_json(PACKAGE / 'base.json')))
        out = self.add('base', target=amy).stdout   # 不帶 --force
        self.assertIn('installed base', out)
        self.assertIn('補了 "tools/base.json"', out)
        self.assertIn('tools/base.json', self.info(amy)['tools'])

    def test_bad_package_name_dotted_or_hidden(self):
        err1 = self.add(str(self.root / 'pkgs' / 'foo.json'), code=1).stderr
        self.assertIn('BadName', err1)
        err2 = self.add(str(self.root / 'pkgs' / '.hidden'), code=1).stderr
        self.assertIn('BadName', err2)


class TestToolsAddConcurrentAndRootAlias(ToolsAddFixCase):

    def test_concurrent_installs_of_different_packages_both_succeed(self):
        amy = make_home(self.root / 'amy', tools=[])
        pkg1 = make_pkg(self.root / 'pkgs', 'pkg1', 'tool_one')
        pkg2 = make_pkg(self.root / 'pkgs', 'pkg2', 'tool_two')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        p1 = subprocess.Popen([PY, str(CLI / 'aos-agent'), 'tools', 'add', str(pkg1), '--target', str(amy)],
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p2 = subprocess.Popen([PY, str(CLI / 'aos-agent'), 'tools', 'add', str(pkg2), '--target', str(amy)],
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out1, err1 = p1.communicate(timeout=20)
        out2, err2 = p2.communicate(timeout=20)
        self.assertEqual(p1.returncode, 0, out1 + err1)
        self.assertEqual(p2.returncode, 0, out2 + err2)
        tools = read_json(amy / 'info.json')['tools']
        self.assertIn('tools/pkg1.json', tools)
        self.assertIn('tools/pkg2.json', tools)
        self.assertTrue((amy / 'tools/pkg1').is_symlink())
        self.assertTrue((amy / 'tools/pkg2').is_symlink())

    def test_root_symlink_alias_to_home_parent_warns(self):
        parent = self.root / 'parent'
        bob2 = make_home(parent / 'agent2', tools=[])
        alias = self.root / 'alias-to-parent'
        os.symlink(parent, alias)
        result = self.add('base', '--root', str(alias), target=bob2)
        self.assertIn('包含 agent 家', result.stderr)


if __name__ == '__main__':
    unittest.main()
