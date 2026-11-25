#!/usr/bin/env python3
# run.py: run every tests/test_*.py of proto9 aos-exec against build/bin (make first), print each test and the totals.
"""Usage: python3 tests/run.py [-q] [NAME ...]   (NAME = a module like test_cli, or test_cli.Cli.test_help; none = all)"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import BIN, CHECK  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if a != '-q']
    quiet = '-q' in sys.argv[1:]
    for b in (BIN, CHECK):
        if not os.access(b, os.X_OK):
            print('missing %s: run make test (or make all build/bin/resolve-check) first' % b)
            return 2
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(args) if args else loader.discover(HERE, pattern='test_*.py', top_level_dir=HERE)
    result = unittest.TextTestRunner(verbosity=1 if quiet else 2, stream=sys.stdout).run(suite)
    failed = len(result.failures) + len(result.errors)
    print('aos-exec tests: %d run, %d passed, %d failed, %d skipped'
          % (result.testsRun, result.testsRun - failed - len(result.skipped), failed, len(result.skipped)))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
