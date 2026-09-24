"""proto5/tools/notes/ 的 note 工具（op=add/find/get/rm，wf-table/1 存檔）與
proto5/lib/aos_agent_notes.py（人看 notes ls／show，不叫模型）：涵蓋 catalog.md 的 T-notes。

NoteToolCase：note 程式複製進假 agent 家、當子行程跑（跟 test_tools_base.py 的 ToolCase 同風格）。
AgentNotesLibCase：直接呼叫 aos_agent_notes.main，含 access.json 牢裡路徑換算。
ToolsAddNotesCase：跟真 aos-agent tools add notes 的往返。
"""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aos_agent_notes as notes_lib  # noqa: E402
from aos_agent_home import AgentError  # noqa: E402

from _kernel_util import CLI, PY, read_json  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO5 = os.path.dirname(os.path.dirname(HERE))
PACKAGE = os.path.join(PROTO5, 'tools', 'notes')


def run_agent(*args, cwd=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    return subprocess.run([PY, str(CLI / 'aos-agent'), *map(str, args)], cwd=cwd, env=env,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)


def make_home(path, extra=None):
    """不跑 aos-agent init、直接寫最小合法 info.json（省一次 subprocess）。"""
    path.mkdir(parents=True, exist_ok=True)
    doc = {'_metainfo': {'_type': 'llm_agent', '_version': 1}, 'llm': {'model': 'm'}, 'tools': []}
    doc.update(extra or {})
    (path / 'info.json').write_text(json.dumps(doc), encoding='utf-8')
    return path


# ======================================================= note 工具（直接跑） ====

class NoteToolCase(unittest.TestCase):
    """每個 test 一個假 agent 家：tools/notes 複製進去，note 當子行程跑，cwd＝agent 家。"""

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix='aos-tools-notes-')
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        shutil.copytree(PACKAGE, os.path.join(self.home, 'tools', 'notes'))

    def config_path(self):
        return os.path.join(self.home, 'tools', 'notes', 'config.json')

    def set_config(self, obj):
        with open(self.config_path(), 'w', encoding='utf-8') as f:
            json.dump(obj, f)

    def notes_path(self, rel='notes/notes.json'):
        return os.path.join(self.home, rel)

    def run_tool(self, args=None, env=None, timeout=10):
        """呼叫 tools/notes/note：stdin 給 args 的 JSON，cwd＝agent 家。
        回 (exit_code, stdout全文, 最後一行解析出的 JSON 或 None)。"""
        exe = os.path.join(self.home, 'tools', 'notes', 'note')
        full_env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        if env:
            full_env.update(env)
        payload = '' if args is None else json.dumps(args, ensure_ascii=False)
        p = subprocess.run([exe], input=payload, cwd=self.home, capture_output=True,
                           text=True, encoding='utf-8', env=full_env, timeout=timeout)
        last = None
        stripped = p.stdout.rstrip('\n')
        if stripped:
            try:
                last = json.loads(stripped.rsplit('\n', 1)[-1])
            except ValueError:
                pass
        return p.returncode, p.stdout, last

    def assertOk(self, res):
        code, out, j = res
        self.assertEqual(code, 0, out)
        return out

    def assertErr(self, res, error):
        code, out, j = res
        self.assertEqual(code, 1, out)
        self.assertIsNotNone(j, 'stdout 最後一行不是 JSON: %r' % out)
        self.assertFalse(j.get('ok'))
        self.assertEqual(j.get('error'), error, out)
        return j

    # ---- 四種 op 成功、更新 ----

    def test_add_find_get_rm_roundtrip(self):
        out = self.assertOk(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'hello world',
                                           'tags': ['a', 'b']}))
        self.assertIn('added k1', out)
        data = read_json(Path(self.notes_path()))
        self.assertEqual(data['contract'], 'wf-table/1')
        self.assertEqual(data['columns'], ['key', 'text', 'tags', 'at'])
        self.assertEqual(len(data['rows']), 1)
        self.assertEqual(data['rows'][0]['tags'], 'a,b')

        out = self.assertOk(self.run_tool({'op': 'find', 'query': 'hello'}))
        self.assertIn('k1 [a,b]: hello world', out)

        out = self.assertOk(self.run_tool({'op': 'get', 'key': 'k1'}))
        self.assertIn('k1 [a,b]', out.splitlines()[0])
        self.assertIn('hello world', out)

        out = self.assertOk(self.run_tool({'op': 'rm', 'key': 'k1'}))
        self.assertIn('removed k1', out)
        data = read_json(Path(self.notes_path()))
        self.assertEqual(data['rows'], [])

    def test_add_existing_key_updates_not_appends(self):
        self.assertOk(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'first'}))
        out = self.assertOk(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'second', 'tags': ['x']}))
        self.assertIn('updated k1', out)
        data = read_json(Path(self.notes_path()))
        self.assertEqual(len(data['rows']), 1)
        self.assertEqual(data['rows'][0]['text'], 'second')
        self.assertEqual(data['rows'][0]['tags'], 'x')

    def test_find_no_match_prints_message_exit_0(self):
        self.assertOk(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'hello'}))
        out = self.assertOk(self.run_tool({'op': 'find', 'query': 'zzz'}))
        self.assertEqual(out.strip(), 'No matching notes.')

    def test_find_by_tags_only(self):
        self.assertOk(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'a', 'tags': ['x', 'y']}))
        self.assertOk(self.run_tool({'op': 'add', 'key': 'k2', 'text': 'b', 'tags': ['y']}))
        out = self.assertOk(self.run_tool({'op': 'find', 'tags': ['x']}))
        self.assertIn('k1', out)
        self.assertNotIn('k2', out)

    def test_find_case_insensitive_query(self):
        self.assertOk(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'Hello World'}))
        out = self.assertOk(self.run_tool({'op': 'find', 'query': 'hello world'}))
        self.assertIn('k1', out)

    # ---- BadArguments ----

    def test_missing_op(self):
        self.assertErr(self.run_tool({}), 'BadArguments')

    def test_unknown_op(self):
        self.assertErr(self.run_tool({'op': 'delete'}), 'BadArguments')

    def test_add_missing_required(self):
        self.assertErr(self.run_tool({'op': 'add', 'key': 'k1'}), 'BadArguments')
        self.assertErr(self.run_tool({'op': 'add', 'text': 'hi'}), 'BadArguments')

    def test_add_key_too_long_or_newline(self):
        self.assertErr(self.run_tool({'op': 'add', 'key': 'x' * 81, 'text': 'hi'}), 'BadArguments')
        self.assertErr(self.run_tool({'op': 'add', 'key': 'a\nb', 'text': 'hi'}), 'BadArguments')
        self.assertErr(self.run_tool({'op': 'add', 'key': '', 'text': 'hi'}), 'BadArguments')

    def test_add_text_too_long_or_empty(self):
        self.assertErr(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'x' * 4001}), 'BadArguments')
        self.assertErr(self.run_tool({'op': 'add', 'key': 'k1', 'text': ''}), 'BadArguments')

    def test_add_bad_tags(self):
        self.assertErr(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'hi',
                                      'tags': ['a'] * 11}), 'BadArguments')
        self.assertErr(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'hi',
                                      'tags': ['x' * 33]}), 'BadArguments')
        self.assertErr(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'hi',
                                      'tags': ['a,b']}), 'BadArguments')
        self.assertErr(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'hi',
                                      'tags': 'not-a-list'}), 'BadArguments')

    def test_add_type_errors(self):
        self.assertErr(self.run_tool({'op': 'add', 'key': 5, 'text': 'hi'}), 'BadArguments')
        self.assertErr(self.run_tool({'op': 'add', 'key': 'k1', 'text': 5}), 'BadArguments')

    def test_extra_unknown_argument_rejected_per_op(self):
        self.assertErr(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'hi', 'query': 'x'}), 'BadArguments')
        self.assertErr(self.run_tool({'op': 'get', 'key': 'k1', 'text': 'hi'}), 'BadArguments')
        self.assertErr(self.run_tool({'op': 'rm', 'key': 'k1', 'tags': ['a']}), 'BadArguments')

    def test_find_requires_query_or_tags(self):
        self.assertErr(self.run_tool({'op': 'find'}), 'BadArguments')

    def test_find_limit_bounds(self):
        self.assertErr(self.run_tool({'op': 'find', 'query': 'x', 'limit': 0}), 'BadArguments')
        self.assertErr(self.run_tool({'op': 'find', 'query': 'x', 'limit': 101}), 'BadArguments')

    # ---- NotFound ----

    def test_get_not_found(self):
        self.assertErr(self.run_tool({'op': 'get', 'key': 'nope'}), 'NotFound')

    def test_rm_not_found(self):
        self.assertErr(self.run_tool({'op': 'rm', 'key': 'nope'}), 'NotFound')

    # ---- Full ----

    def test_full_row_limit(self):
        rows = [{'key': 'k%d' % i, 'text': 't', 'tags': '', 'at': 'x'} for i in range(500)]
        os.makedirs(os.path.dirname(self.notes_path()), exist_ok=True)
        with open(self.notes_path(), 'w', encoding='utf-8') as f:
            json.dump({'contract': 'wf-table/1', 'columns': ['key', 'text', 'tags', 'at'], 'rows': rows}, f)
        self.assertErr(self.run_tool({'op': 'add', 'key': 'new', 'text': 'hi'}), 'Full')
        out = self.assertOk(self.run_tool({'op': 'add', 'key': 'k0', 'text': 'updated'}))
        self.assertIn('updated k0', out)
        data = read_json(Path(self.notes_path()))
        self.assertEqual(len(data['rows']), 500)

    # ---- 壞檔 ConfigInvalid，不覆蓋 ----

    def test_config_invalid_not_json_not_overwritten(self):
        os.makedirs(os.path.dirname(self.notes_path()), exist_ok=True)
        with open(self.notes_path(), 'w', encoding='utf-8') as f:
            f.write('not json at all')
        self.assertErr(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'hi'}), 'ConfigInvalid')
        with open(self.notes_path(), encoding='utf-8') as f:
            self.assertEqual(f.read(), 'not json at all')

    def test_config_invalid_bad_shape_not_overwritten(self):
        os.makedirs(os.path.dirname(self.notes_path()), exist_ok=True)
        with open(self.notes_path(), 'w', encoding='utf-8') as f:
            json.dump({'contract': 'wf-table/1', 'rows': 'not-a-list'}, f)
        self.assertErr(self.run_tool({'op': 'find', 'query': 'x'}), 'ConfigInvalid')
        self.assertErr(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'hi'}), 'ConfigInvalid')

    # ---- 平行 20 個 add：flock 有效 ----

    def test_parallel_add_all_present(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        exe = os.path.join(self.home, 'tools', 'notes', 'note')
        procs = []
        for i in range(20):
            p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, cwd=self.home, env=env, text=True)
            procs.append((i, p))
        for i, p in procs:
            out, err = p.communicate(json.dumps({'op': 'add', 'key': 'p%d' % i, 'text': 'note %d' % i}),
                                     timeout=20)
            self.assertEqual(p.returncode, 0, out + err)
        data = read_json(Path(self.notes_path()))
        self.assertEqual(len(data['rows']), 20)
        self.assertEqual({r['key'] for r in data['rows']}, {'p%d' % i for i in range(20)})

    # ---- AOS_NOTES_FILE ----

    def test_env_var_overrides_config(self):
        self.set_config({'file': 'ignored/notes.json'})
        custom = os.path.join(self.home, 'custom', 'notes.json')
        self.assertOk(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'hi'},
                                    env={'AOS_NOTES_FILE': custom}))
        self.assertTrue(os.path.exists(custom))
        self.assertFalse(os.path.exists(os.path.join(self.home, 'ignored', 'notes.json')))

    # ---- config.json 的 file（相對／絕對） ----

    def test_config_json_relative_file(self):
        self.set_config({'file': 'mydir/mynotes.json'})
        self.assertOk(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'hi'}))
        self.assertTrue(os.path.exists(os.path.join(self.home, 'mydir', 'mynotes.json')))

    def test_config_json_absolute_file(self):
        outside = tempfile.mkdtemp(prefix='aos-notes-abs-')
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        target = os.path.join(outside, 'notes.json')
        self.set_config({'file': target})
        self.assertOk(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'hi'}))
        self.assertTrue(os.path.exists(target))

    def test_config_missing_defaults_to_notes_notes_json(self):
        self.assertFalse(os.path.exists(self.config_path()))  # 工具包沒帶 config.json
        self.assertOk(self.run_tool({'op': 'add', 'key': 'k1', 'text': 'hi'}))
        self.assertTrue(os.path.exists(self.notes_path()))


# ======================================================= aos_agent_notes（人看） ====

class AgentNotesLibCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-agent-notes-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = make_home(self.root / 'amy')

    def write_notes(self, rows, rel='notes/notes.json'):
        path = self.home / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'contract': 'wf-table/1', 'columns': ['key', 'text', 'tags', 'at'],
                                    'rows': rows}), encoding='utf-8')
        return path

    def capture(self, *call):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = notes_lib.main(*call)
        return code, buf.getvalue()

    def test_ls_empty_no_notes_file(self):
        code, out = self.capture(str(self.home), 'ls', [])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), '（沒有筆記）')

    def test_ls_lists_and_show_prints_full_text(self):
        self.write_notes([{'key': 'k1', 'text': 'hello there world', 'tags': 'a,b', 'at': '2026-01-01T00:00:00Z'}])
        code, out = self.capture(str(self.home), 'ls', [])
        self.assertEqual(code, 0)
        self.assertIn('k1', out)
        self.assertIn('[a,b]', out)
        self.assertIn('hello there world', out)

        code, out = self.capture(str(self.home), 'show', ['k1'])
        self.assertEqual(code, 0)
        self.assertIn('k1 [a,b] 2026-01-01T00:00:00Z', out.splitlines()[0])
        self.assertIn('hello there world', out)

    def test_ls_json(self):
        self.write_notes([{'key': 'k1', 'text': 't', 'tags': '', 'at': 'x'}])
        code, out = self.capture(str(self.home), 'ls', [], True)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [{'key': 'k1', 'text': 't', 'tags': '', 'at': 'x'}])

    def test_show_json(self):
        self.write_notes([{'key': 'k1', 'text': 't', 'tags': 'x', 'at': 'y'}])
        code, out = self.capture(str(self.home), 'show', ['k1'], True)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {'key': 'k1', 'text': 't', 'tags': 'x', 'at': 'y'})

    def test_show_not_found_raises_agent_error(self):
        self.write_notes([])
        with self.assertRaises(AgentError) as ctx:
            notes_lib.main(str(self.home), 'show', ['nope'])
        self.assertEqual(ctx.exception.code, 'NotFound')

    def test_notes_file_bad_shape_raises_config_invalid(self):
        (self.home / 'notes').mkdir(parents=True, exist_ok=True)
        (self.home / 'notes' / 'notes.json').write_text('not json', encoding='utf-8')
        with self.assertRaises(AgentError) as ctx:
            notes_lib.main(str(self.home), 'ls', [])
        self.assertEqual(ctx.exception.code, 'ConfigInvalid')

    def test_config_json_relative_file(self):
        (self.home / 'tools' / 'notes').mkdir(parents=True)
        (self.home / 'tools' / 'notes' / 'config.json').write_text(
            json.dumps({'file': 'custom/mine.json'}), encoding='utf-8')
        self.write_notes([{'key': 'k1', 'text': 't', 'tags': '', 'at': 'x'}], rel='custom/mine.json')
        self.assertEqual(notes_lib.notes_file(str(self.home)), str(self.home / 'custom' / 'mine.json'))
        code, out = self.capture(str(self.home), 'show', ['k1'])
        self.assertEqual(code, 0)

    def test_jail_path_mapped_via_access_json(self):
        mount_dir = self.root / 'mnt'
        mount_dir.mkdir()
        (self.home / 'tools' / 'notes').mkdir(parents=True)
        (self.home / 'tools' / 'notes' / 'config.json').write_text(
            json.dumps({'file': '/work/mnt/notes.json'}), encoding='utf-8')
        (self.home / 'access.json').write_text(
            json.dumps({'mounts': {'mnt': str(mount_dir)}}), encoding='utf-8')
        (mount_dir / 'notes.json').write_text(
            json.dumps({'contract': 'wf-table/1', 'rows': [{'key': 'jk', 'text': 'jailed', 'tags': '',
                                                             'at': 'x'}]}), encoding='utf-8')
        real = notes_lib.notes_file(str(self.home))
        self.assertEqual(real, str(mount_dir / 'notes.json'))
        code, out = self.capture(str(self.home), 'show', ['jk'])
        self.assertEqual(code, 0)
        self.assertIn('jailed', out)


# ======================================================= aos-agent tools add notes ====

class ToolsAddNotesCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-tools-add-notes-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.bob = self.root / 'bob'
        result = run_agent('init', '--target', self.bob)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_install_notes_package(self):
        before = read_json(self.bob / 'info.json')
        result = run_agent('tools', 'add', 'notes', '--target', self.bob)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('installed notes', result.stdout)
        self.assertIn('note', result.stdout)
        tools = read_json(self.bob / 'tools/notes.json')
        self.assertEqual([t['function']['name'] for t in tools], ['note'])
        self.assertTrue(os.access(self.bob / 'tools/notes/note', os.X_OK))
        # init 的家 tools 已經是整個 tools/ 資料夾（涵蓋 tools/notes.json），info.json 不必再改
        # （跟 test_agent_tools.py 的 test_install_into_init_home 一樣）。
        self.assertEqual(read_json(self.bob / 'info.json'), before)

    def test_installed_tool_runs_and_lib_reads_it(self):
        run_agent('tools', 'add', 'notes', '--target', self.bob)
        # init 生的家有 access.json（工具關牢）：筆記在牢裡的 /work/notes，要掛一個 notes 資料夾；
        # 這裡不真的進牢，用 AOS_NOTES_FILE 指到那個資料夾在主機上的真路徑，模擬牢裡看到的同一個檔。
        shelf = self.bob.parent / 'shelf'
        shelf.mkdir()
        run_agent('access', 'set', 'notes', str(shelf), '--rw', '--target', self.bob)
        exe = self.bob / 'tools' / 'notes' / 'note'
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', AOS_NOTES_FILE=str(shelf / 'notes.json'))
        p = subprocess.run([str(exe)], input=json.dumps({'op': 'add', 'key': 'k1', 'text': 'from installed tool'}),
                           cwd=self.bob, capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = notes_lib.main(str(self.bob), 'show', ['k1'])
        self.assertEqual(code, 0)
        self.assertIn('from installed tool', buf.getvalue())

    def test_jailed_default_needs_notes_mount(self):
        run_agent('tools', 'add', 'notes', '--target', self.bob)
        exe = self.bob / 'tools' / 'notes' / 'note'
        if os.path.isdir('/work/notes'):
            self.skipTest('這台機器真的有 /work/notes')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', AOS_TOOL_ROOT='/work/ws')
        env.pop('AOS_NOTES_FILE', None)
        p = subprocess.run([str(exe)], input=json.dumps({'op': 'find', 'query': 'x'}), cwd=self.bob,
                           capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(json.loads(p.stdout.strip().splitlines()[-1])['error'], 'ConfigInvalid')
        self.assertIn('access set notes', p.stdout)
        with self.assertRaises(AgentError) as cm:
            notes_lib.main(str(self.bob), 'ls', [])
        self.assertIn('access set notes', cm.exception.msg)


if __name__ == '__main__':
    unittest.main()
