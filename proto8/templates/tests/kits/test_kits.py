"""Check the public kits folder (templates/kits): English only, no site-specific wording, valid JSON with a description first, each kit folder holding system.txt and tools.json (for ctl --kit), and each kit's system.txt equal to its assembled layers."""
import json
import re
import unittest
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[2]
KITS = TEMPLATES / 'kits'
AGENT_SYSTEM = TEMPLATES / 'agent-fsm' / 'system.txt'

CJK = re.compile('[⺀-鿿豈-﫿＀-￯　-〿]')
FORBIDDEN = ['wf/', '/home/', 'aos-home', 'xiaosi', 'repo-aos', 'llm-gpt',
             '127.0.0.1', 'Traditional Chinese']
SYSTEM_MAX = 3000
AGENT_SYSTEM_MAX = 1800

STEP2_OLD = ('2. Read <KNOWLEDGE>/aos/_description.md; look up more only when '
             'needed (index_view <KNOWLEDGE>/aos).')
STEP2_NEW = ('2. Read the aos knowledge base: aos/_description.md in the knowledge '
             'folder your brief names (index_view it for more, only when needed).')
BOARD_NEW = ('BOARD: before you wait on someone, and when an answer is late, board_read them '
             '(who = their name, or "user" for the user\'s notice). A notice is information, not permission.')
OWN_BOARD_NEW = ('OWN BOARD: when you stop to wait for someone, board_wait {"who": ..., "what": ...}; '
                 'when the answer comes, board_wait {"who": ..., "done": true}.')


def assemble(general, role):
    """Product default: resolve the placeholders of general, then a blank line, then the role text."""
    out = []
    for line in general.rstrip('\n').split('\n'):
        if line == STEP2_OLD:
            out.append(STEP2_NEW)
        elif line.startswith('BOARD:'):
            out.append(BOARD_NEW)
        elif line.strip() == '<OWN_BOARD>':
            out.append(OWN_BOARD_NEW)
        else:
            out.append(line)
    return '\n'.join(out) + '\n\n' + role


def kit_files():
    return sorted(p for p in KITS.rglob('*') if p.is_file())


class TestKits(unittest.TestCase):

    def test_english_and_neutral(self):
        files = kit_files() + [AGENT_SYSTEM]
        self.assertTrue(len(files) > 5)
        for p in files:
            text = p.read_text(encoding='utf-8')
            m = CJK.search(text)
            self.assertIsNone(m, f'{p}: CJK char {m.group() if m else ""!r}')
            for word in FORBIDDEN:
                self.assertNotIn(word, text, f'{p}: {word!r}')

    def test_no_install_folder(self):
        for p in KITS.rglob('*'):
            if p.is_dir():
                self.assertNotEqual(p.name.lower(), 'install', str(p))

    def test_json_description_first(self):
        for p in kit_files():
            if p.suffix != '.json':
                continue
            data = json.loads(p.read_text(encoding='utf-8'))
            self.assertIsInstance(data, dict, str(p))
            self.assertEqual(next(iter(data)), 'description', str(p))
            self.assertTrue(data['description'].strip(), str(p))

    def test_kits_json_paths_exist(self):
        data = json.loads((KITS / 'kits.json').read_text(encoding='utf-8'))
        self.assertTrue(data['kits'])
        for name, kit in data['kits'].items():
            self.assertTrue((KITS / kit['dir']).is_dir(), name)
            for key in ('system', 'tools'):
                self.assertTrue((KITS / kit[key]).is_file(), f'{name}.{key}')
            for tier in kit['tiers']:
                self.assertIn(tier, data['tiers'], name)
                self.assertTrue((KITS / f'general.{tier}.txt').is_file(), tier)

    def test_kit_folders_hold_both_files(self):
        """aos-agent ctl add / set-def --kit takes a kit folder: system.txt and tools.json in it, named so in kits.json."""
        data = json.loads((KITS / 'kits.json').read_text(encoding='utf-8'))
        for name, kit in data['kits'].items():
            self.assertEqual(kit['system'], kit['dir'] + '/system.txt', name)
            self.assertEqual(kit['tools'], kit['dir'] + '/tools.json', name)
        self.assertEqual((KITS / 'review' / 'tools.json').read_bytes(), (KITS / 'gather' / 'tools.json').read_bytes())

    def test_tools_name_packs_by_env(self):
        """The tools file is copied into a stack, so it must not point relative to the kit folder."""
        for p in KITS.glob('*/tools.json'):
            data = json.loads(p.read_text(encoding='utf-8'))
            for item in data['$override']:
                self.assertIsInstance(item, dict, str(p))
                self.assertEqual(item.get('$env'), 'AOS_HOME', str(p))

    def test_systems_are_assembled(self):
        general = (KITS / 'general.A.txt').read_text(encoding='utf-8')
        self.assertIn(STEP2_OLD, general)
        for kit, role in (('gather', 'gather'), ('review', 'review')):
            role_text = (KITS / 'roles' / f'{role}.txt').read_text(encoding='utf-8')
            want = assemble(general, role_text)
            got = (KITS / kit / 'system.txt').read_text(encoding='utf-8')
            self.assertEqual(got, want, kit)
            self.assertNotIn('<', got.replace('<=', ''), kit)
            self.assertLessEqual(len(got), SYSTEM_MAX, kit)

    def test_agent_fsm_system(self):
        text = AGENT_SYSTEM.read_text(encoding='utf-8')
        self.assertLessEqual(len(text), AGENT_SYSTEM_MAX)
        self.assertIn('peek_now_time', text)


if __name__ == '__main__':
    unittest.main()
