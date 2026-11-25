# common.py: shared helpers for the aos-exec tests -- paths of this folder's binaries, a clean environment, a temp-folder test case.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
BINDIR = FOLDER / 'build' / 'bin'
BIN = str(BINDIR / 'aos-exec')
CHECK = str(BINDIR / 'resolve-check')
DATA = HERE / 'data'

# No AOS_* from the caller; this folder's bin first on PATH (argv arrays insert "aos-exec" and find it on PATH).
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
ENV['PATH'] = str(BINDIR) + ':' + ENV.get('PATH', '/bin:/usr/bin')


def run_exec(*argv, cwd, env=None, extra=None):
    """Run aos-exec ARGV in cwd; returns (code, stdout stripped, stderr stripped)."""
    e = dict(env if env is not None else ENV, **(extra or {}))
    p = subprocess.run([BIN, *argv], cwd=cwd, env=e, capture_output=True, text=True, timeout=10)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


class TmpCase(unittest.TestCase):
    """A test case with a fresh real-path temp folder self.d (TMPDIR decides where it goes)."""
    prefix = 'aos-exec-'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix=self.prefix)
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))

    def put(self, name, text, x=False):
        """Write text (a str, or anything else as JSON) to self.d/name; x = chmod 755."""
        p = self.d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if isinstance(text, str) else json.dumps(text))
        p.chmod(0o755 if x else 0o644)
        return p

    def run_(self, *argv, cwd=None, env=None, extra=None):
        return run_exec(*argv, cwd=cwd or self.d, env=env, extra=extra)
