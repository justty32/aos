# aos/apps/kit/add.py - lay a kit over an agent-fsm definition: system.txt (assembled) and tools.json (copied); old files are kept as *.before-kit.
import os

from .recipe import Fail

FILES = ('system.txt', 'tools.json')


def read_bytes(path):
    try:
        with open(path, 'rb') as fh:
            return fh.read()
    except OSError as e:
        raise Fail('ReadFailed', 'cannot read %s: %s' % (path, e.strerror or e))


def stock_dir(env=None):
    """$AOS_HOME/templates/agent-fsm, or None when AOS_HOME is not set."""
    env = os.environ if env is None else env
    home = env.get('AOS_HOME')
    return os.path.join(home, 'templates', 'agent-fsm') if home else None


def backup_name(path):
    """path.before-kit, or path.before-kit.2, .3 ... when that is taken (a backup is never overwritten)."""
    name = path + '.before-kit'
    n = 1
    while os.path.lexists(name):
        n += 1
        name = '%s.before-kit.%d' % (path, n)
    return name


def write_new(path, data):
    """Create path; fail if it is there."""
    try:
        with open(path, 'xb') as fh:
            fh.write(data)
    except OSError as e:
        raise Fail('WriteFailed', 'cannot write %s: %s' % (path, e.strerror or e))


def write_over(path, data):
    """Write a temporary file next to path, then rename it over path."""
    tmp = '%s.tmp.%d' % (path, os.getpid())
    try:
        with open(tmp, 'xb') as fh:
            fh.write(data)
        os.replace(tmp, path)
    except OSError as e:
        raise Fail('WriteFailed', 'cannot write %s: %s' % (path, e.strerror or e))


def plan(defdir, new, force=False, stock=None):
    """Decide per file before writing anything. new = {name: bytes}. -> [(name, action)], action in
    create, replace, unchanged. A file that is there and differs from the stock agent-fsm one is refused
    (FileChanged) unless force; without a stock copy to compare with it is refused too (StockMissing)."""
    if not os.path.isdir(defdir):
        raise Fail('DefMissing', '%s is not a folder' % defdir)
    if not os.path.isfile(os.path.join(defdir, 'interfaces.json')):
        raise Fail('DefMissing', '%s has no interfaces.json (not an agent definition; make one from the agent-fsm template first)' % defdir)
    steps = []
    for name in FILES:
        path = os.path.join(defdir, name)
        if not os.path.lexists(path):
            steps.append((name, 'create'))
            continue
        if os.path.isdir(path):
            raise Fail('WriteFailed', '%s is a folder' % path)
        cur = read_bytes(path)
        if cur == new[name]:
            steps.append((name, 'unchanged'))
            continue
        if not force:
            ref = os.path.join(stock, name) if stock else None
            if ref is None or not os.path.isfile(ref):
                raise Fail('StockMissing', 'cannot tell whether %s is the stock agent-fsm file (%s); give --force to replace it anyway'
                           % (path, 'AOS_HOME is not set' if stock is None else 'no ' + ref))
            if cur != read_bytes(ref):
                raise Fail('FileChanged', '%s is not the stock agent-fsm %s (someone edited it); give --force to replace it '
                           '(the old one is kept as %s)' % (path, name, os.path.basename(backup_name(path))))
        steps.append((name, 'replace'))
    return steps


def apply(defdir, new, steps):
    """Back up, then write. -> lines saying what was done."""
    out = []
    for name, action in steps:
        if action == 'replace':
            path = os.path.join(defdir, name)
            bak = backup_name(path)
            write_new(bak, read_bytes(path))
            out.append('saved %s (the old %s)' % (bak, name))
    for name, action in steps:
        path = os.path.join(defdir, name)
        if action == 'unchanged':
            out.append('unchanged %s (already the kit\'s)' % path)
        else:
            write_over(path, new[name])
            out.append('wrote %s (%d bytes)' % (path, len(new[name])))
    return out
