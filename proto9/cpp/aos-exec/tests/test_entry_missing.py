# Check EntryMissing says where a relative entry was counted from and what absolute path it became (ported as is from proto8 aos-exec tests/test_entry_missing.py).
import json

from common import TmpCase


class EntryMissing(TmpCase):
    prefix = 'aos-exec-missing-'

    def test_relative_from_cwd(self):
        code, _, err = self.run_('agents/../nope')
        self.assertEqual(code, 1)
        self.assertEqual(err, 'aos-exec: error: EntryMissing entry not found: agents/../nope (relative paths count from %s: %s/nope)'
                         % (self.d, self.d))

    def test_redirect_counts_from_the_file_that_holds_it(self):
        sub = self.d / 'another'
        sub.mkdir()
        (sub / 'x.json').write_text(json.dumps({'_entry': 'agents/a'}))
        code, _, err = self.run_('another/x.json')
        self.assertEqual(code, 1)
        self.assertIn('entry not found: agents/a (relative paths count from %s: %s/agents/a)' % (sub, sub), err)

    def test_absolute_is_printed_as_is(self):
        code, _, err = self.run_(str(self.d / 'gone'))
        self.assertEqual(code, 1)
        self.assertEqual(err, 'aos-exec: error: EntryMissing entry not found: %s' % (self.d / 'gone'))
