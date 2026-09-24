"""第二波 C 隊：aos-agent persona show／set／append（catalog.md〈T-persona〉，spec/agent/persona.md）。
人格是信任資料，模型改不到——模型只能用 persona_propose 工具寄提案（tools/task，test_team_init.py 涵蓋）；
這裡測人用的那半：直接讀寫 prompts/system.json，不叫模型、不進牢。
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
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aos_agent_persona as persona  # noqa: E402
from aos_agent_home import AgentError  # noqa: E402

from _kernel_util import CLI, PY  # noqa: E402


def run_agent(*args, cwd=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    return subprocess.run([PY, str(CLI / 'aos-agent'), *map(str, args)], cwd=cwd, env=env,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)


def make_home(path, system_rel=None):
    path.mkdir(parents=True, exist_ok=True)
    doc = {'_metainfo': {'_type': 'llm_agent', '_version': 1}, 'llm': {'model': 'm'}, 'tools': []}
    if system_rel is not None:
        doc['system'] = system_rel
    (path / 'info.json').write_text(json.dumps(doc), encoding='utf-8')
    return path


class PersonaLibTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-persona-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = make_home(self.root / 'agent')

    def out(self, fn, *a, **kw):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = fn(*a, **kw)
        return code, buf.getvalue()

    def test_show_missing_file_is_empty(self):
        code, text = self.out(persona.show, str(self.home))
        self.assertEqual((code, text), (0, '\n'))

    def test_show_json(self):
        (self.home / 'prompts').mkdir()
        (self.home / 'prompts' / 'system.json').write_text(json.dumps({'content': '你好'}), encoding='utf-8')
        code, text = self.out(persona.show, str(self.home), as_json=True)
        self.assertEqual(json.loads(text), {'content': '你好'})

    def test_set_overwrites(self):
        self.out(persona.set_, str(self.home), '第一版')
        self.out(persona.set_, str(self.home), '第二版')
        _, text = self.out(persona.show, str(self.home))
        self.assertEqual(text, '第二版\n')

    def test_append_adds_a_line(self):
        self.out(persona.set_, str(self.home), '第一行')
        self.out(persona.append, str(self.home), '第二行')
        _, text = self.out(persona.show, str(self.home))
        self.assertEqual(text, '第一行\n第二行\n')

    def test_append_on_empty_file(self):
        code, _ = self.out(persona.append, str(self.home), '唯一一行')
        self.assertEqual(code, 0)
        _, text = self.out(persona.show, str(self.home))
        self.assertEqual(text, '唯一一行\n')

    def test_respects_custom_system_path(self):
        home = make_home(self.root / 'agent2', system_rel='prompts/persona.json')
        self.out(persona.set_, str(home), '自訂路徑')
        self.assertTrue((home / 'prompts' / 'persona.json').is_file())
        self.assertFalse((home / 'prompts' / 'system.json').exists())

    def test_resolves_directive_system_field(self):
        """astra 審查 M4：system 是 {"$env": …} 這種指示詞物件，要解到跟 runtime 一樣的檔，不能誤判成沒設定。"""
        home = make_home(self.root / 'agent3', system_rel={'$env': 'PERSONA_PATH'})
        with unittest.mock.patch.dict(os.environ, {'PERSONA_PATH': 'prompts/from-env.json'}):
            self.out(persona.set_, str(home), '解過指示詞')
        self.assertTrue((home / 'prompts' / 'from-env.json').is_file())
        self.assertFalse((home / 'prompts' / 'system.json').exists())

    def test_invalid_system_directive_errors_instead_of_silent_default(self):
        """astra 審查 M4：system 寫了但解不出非空字串，要報錯，不能默默退回預設檔。"""
        home = make_home(self.root / 'agent4', system_rel={'$env': 'MISSING_PERSONA_PATH'})
        with self.assertRaises(AgentError) as cm:
            persona.show(str(home))
        self.assertEqual(cm.exception.code, 'FieldTypeMismatch')

    def test_main_usage_errors(self):
        with self.assertRaises(AgentError) as cm:
            persona.main(str(self.home), 'show', text='多給了')
        self.assertEqual(cm.exception.code, 'Usage')
        with self.assertRaises(AgentError) as cm:
            persona.main(str(self.home), 'set', text=None)
        self.assertEqual(cm.exception.code, 'Usage')
        with self.assertRaises(AgentError) as cm:
            persona.main(str(self.home), 'bogus')
        self.assertEqual(cm.exception.code, 'Usage')

    def test_corrupt_file_message_invalid(self):
        (self.home / 'prompts').mkdir()
        (self.home / 'prompts' / 'system.json').write_text('[]', encoding='utf-8')
        with self.assertRaises(AgentError) as cm:
            persona.show(str(self.home))
        self.assertEqual(cm.exception.code, 'MessageInvalid')


class PersonaCliTests(unittest.TestCase):
    """真的跑 cli/aos-agent（薄薄一層，確認接線接對）。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-persona-cli-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = make_home(self.root / 'agent')

    def test_show_set_append_roundtrip(self):
        r = run_agent('persona', 'show', '--target', str(self.home))
        self.assertEqual((r.returncode, r.stdout), (0, '\n'))
        r = run_agent('persona', 'set', '你是助理', '--target', str(self.home))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run_agent('persona', 'append', '多加一句', '--target', str(self.home))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run_agent('persona', 'show', '--target', str(self.home))
        self.assertEqual(r.stdout, '你是助理\n多加一句\n')

    def test_show_rejects_extra_text(self):
        r = run_agent('persona', 'show', '多的', '--target', str(self.home))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('不收 TEXT', r.stderr)


if __name__ == '__main__':
    unittest.main()
