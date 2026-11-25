# Check aos-exec's command line: flags before XXX only, args after XXX stay raw, --help, and the usage errors (test_exec_args_stay_raw ported from proto8 aos-util tests/test_parse_cli.py).
from common import TmpCase

USAGE = '(usage: aos-exec [--ws WS] [--dotenv-override] XXX [ARGS...])'


class Cli(TmpCase):
    prefix = 'aos-exec-cli-'

    def test_exec_args_stay_raw(self):
        self.assertEqual(self.run_('/bin/echo', '-w', 'x', '--stack', 'y'), (0, '-w x --stack y', ''))
        self.assertEqual(self.run_('/bin/echo', '--', '--help', '-x'), (0, '-- --help -x', ''))

    def test_double_dash_ends_flags(self):
        self.put('-p', '#!/bin/sh\necho dash "$@"\n', True)
        self.assertEqual(self.run_('--', '-p', 'a'), (0, 'dash a', ''))

    def test_help(self):
        for flag in ('--help', '-h'):
            code, out, err = self.run_(flag)
            self.assertEqual((code, err), (0, ''))
            self.assertTrue(out.startswith('usage: aos-exec [FLAGS] XXX [ARGS...]'), out)
            self.assertIn('inst sheets are not supported in proto9', out)
            self.assertNotIn('--stack', out)

    def test_missing_and_empty_xxx(self):
        self.assertEqual(self.run_(), (1, '', 'aos-exec: error: ArgumentsBad missing XXX %s' % USAGE))
        self.assertEqual(self.run_(''), (1, '', 'aos-exec: error: ArgumentsBad XXX is an empty string %s' % USAGE))

    def test_flag_errors(self):
        self.assertEqual(self.run_('--bogus', 'x'), (1, '', 'aos-exec: error: FlagUnknown unknown flag --bogus %s' % USAGE))
        self.assertEqual(self.run_('--ws'), (1, '', 'aos-exec: error: ArgumentsBad --ws needs a value %s' % USAGE))
        self.assertEqual(self.run_('--dotenv-override=1', 'x'),
                         (1, '', 'aos-exec: error: ArgumentsBad --dotenv-override takes no value %s' % USAGE))

    def test_ws_flag(self):
        self.put('w/keep', '')
        self.put('t', '#!/bin/sh\necho "$AOS_WS"\n', True)
        self.assertEqual(self.run_('--ws', 'w', './t'), (0, str(self.d / 'w'), ''))
        self.assertEqual(self.run_('-w', 'w', './t'), (0, str(self.d / 'w'), ''))
        self.assertEqual(self.run_('--ws=-', './t', extra={'AOS_WS': str(self.d / 'w')}), (0, str(self.d / 'w'), ''))
        self.assertEqual(self.run_('./t'), (0, str(self.d), ''))
        code, _, err = self.run_('--ws', 'nope', './t')
        self.assertEqual((code, err), (1, 'aos-exec: error: WsMissing workspace does not exist: nope'))
