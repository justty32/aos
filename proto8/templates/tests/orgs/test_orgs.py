"""Check the org templates (templates/orgs): English only, no site-specific names, each file at most 8 KB, every .md starting with a describing line, relative links that resolve (the skeleton's inside the skeleton, the extras' from the place they are moved to), capital placeholders matching the table in orgs/README.md, and CHOICE n marks matching the nine choices."""
import re
import unittest
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[2]
ORGS = TEMPLATES / 'orgs'
BASIC = ORGS / 'basic'
EXTRAS = BASIC / 'extras'

CJK = re.compile('[⺀-鿿豈-﫿＀-￯　-〿]')
# Names of real sites, machines and projects: the template must read the same everywhere.
FORBIDDEN = ['/home/', '/mnt/', 'aos-home', 'xiaosi', 'repo-aos', 'eca-aos', 'eca_main', 'arena',
             'paper_readings', 'mecha', 'llm-gpt', '127.0.0.1', 'localhost', 'Traditional Chinese']
MAX_BYTES = 8 * 1024
LINK = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')
CAPS = re.compile(r'<([A-Z][A-Z_]*)>')
CHOICE = re.compile(r'CHOICE (\d+)')
# extras that are moved into wf/org (= BASIC) before use; their links are written for that place
MOVED = {
    EXTRAS / 'helper' / 'README.md': BASIC / 'helper' / 'README.md',
    EXTRAS / 'improvements.md': BASIC / 'seat' / 'improvements.md',   # wf/org/<SEAT>/, next to the card
    EXTRAS / 'gates.md': BASIC / 'gates.md',
}
TXT = {EXTRAS / 'system.seat.txt', EXTRAS / 'site.txt'}   # sent to the model whole: no describing line (as in kits)


def org_files():
    return sorted(p for p in ORGS.rglob('*') if p.is_file() and '__pycache__' not in p.parts)


def table_placeholders():
    """The capital placeholders listed in the tables of orgs/README.md (rows like | `<NAME>` | ...)."""
    text = (ORGS / 'README.md').read_text(encoding='utf-8')
    return set(re.findall(r'^\s*\| `<([A-Z][A-Z_]*)>` \|', text, re.M))


class TestOrgs(unittest.TestCase):

    def test_files(self):
        files = org_files()
        self.assertGreaterEqual(len(files), 13)
        for p in files:
            self.assertIn(p.suffix, {'.md', '.txt'}, str(p))
        self.assertEqual({p for p in files if p.suffix == '.txt'}, TXT)
        for rel in ['README.md', 'CHOICES.md', 'places.md', 'letters.md', 'lead/README.md',
                    'seat/README.md', 'extras/README.md']:
            self.assertTrue((BASIC / rel).is_file(), rel)

    def test_english_and_neutral(self):
        for p in org_files():
            text = p.read_text(encoding='utf-8')
            m = CJK.search(text)
            self.assertIsNone(m, f'{p}: CJK char {m.group() if m else ""!r}')
            for word in FORBIDDEN:
                self.assertNotIn(word, text, f'{p}: {word!r}')

    def test_size(self):
        for p in org_files():
            self.assertLessEqual(p.stat().st_size, MAX_BYTES, str(p))

    def test_describing_first_line(self):
        for p in org_files():
            first = p.read_text(encoding='utf-8').split('\n', 1)[0]
            if p in TXT:
                continue
            self.assertTrue(first.strip(), f'{p}: empty first line')
            self.assertFalse(first.startswith('#'), f'{p}: first line must be a sentence, not a heading')

    def test_links(self):
        """Relative links resolve; a file of the skeleton links only inside the skeleton (it is copied alone)."""
        for p in org_files():
            place = MOVED.get(p, p)
            for target in LINK.findall(p.read_text(encoding='utf-8')):
                if '://' in target or target.startswith('#') or '<' in target:
                    continue
                path = target.split('#', 1)[0]
                dest = (place.parent / path).resolve()
                if p in MOVED:
                    # after the move the extras folder is gone: the target must be a skeleton file
                    self.assertTrue(dest.exists() and EXTRAS not in dest.parents,
                                    f'{p} (moved to {place.relative_to(BASIC)}): {target}')
                else:
                    self.assertTrue(dest.exists(), f'{p}: {target}')
                if BASIC in p.parents:
                    self.assertTrue(dest == BASIC or BASIC in dest.parents, f'{p}: {target} leaves the skeleton')

    def test_placeholders_match_table(self):
        listed = table_placeholders()
        used = set()
        for p in org_files():
            if p == ORGS / 'README.md':
                continue
            used |= set(CAPS.findall(p.read_text(encoding='utf-8')))
        self.assertEqual(used - listed, set(), 'used but not in the table of orgs/README.md')
        self.assertEqual(listed - used, set(), 'in the table but used nowhere')

    def test_choice_marks(self):
        heads = re.findall(r'^## (\d+)\. ', (BASIC / 'CHOICES.md').read_text(encoding='utf-8'), re.M)
        self.assertEqual(heads, [str(n) for n in range(1, 10)])
        self.assertEqual(len(re.findall(r'^\*\*Ours:\*\*', (BASIC / 'CHOICES.md').read_text(encoding='utf-8'), re.M)), 9)
        for p in org_files():
            for n in CHOICE.findall(p.read_text(encoding='utf-8')):
                self.assertIn(int(n), range(1, 10), f'{p}: CHOICE {n}')


if __name__ == '__main__':
    unittest.main()
