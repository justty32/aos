"""Swap stopped definitions with retained versions after checking public daemon listings."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from tool_io import Error

VERSION = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}\.[0-9]{3}Z')


def _root(value, name):
    if not isinstance(value, str) or not value or '\0' in value:
        raise Error('ArgumentsBad', '%s must be a nonempty path string' % name)
    path = Path(value)
    if not path.is_absolute():
        raise Error('PathBad', '%s must be an absolute path' % name)
    return path.resolve()


def _inside(root, path):
    if not path.resolve().is_relative_to(root):
        raise Error('PathBad', 'path resolves outside its definition root: %s' % path)
    return path


def _paths(args):
    root = _root(args.get('defs'), 'defs')
    target = args.get('target')
    if not isinstance(target, str) or not target:
        raise Error('ArgumentsBad', 'target must be a nonempty relative path')
    if '\0' in target or Path(target).is_absolute() or any(
            not part or part.startswith('.') for part in target.split('/')):
        raise Error('PathBad', 'target must be relative with no empty or dot-prefixed segments')
    current = _inside(root, root / target)
    if current.is_symlink():
        raise Error('PathBad', 'target must name a directory, not a symbolic link')
    previous = _inside(root, root / '.prev' / target)
    return root, target, current, previous


def _idle(current, args):
    daemons = args.get('daemons')
    if daemons is None:
        daemon = os.environ.get('AOS_DAEMON')
        daemons = [daemon] if daemon else []
    if not isinstance(daemons, list) or any(
            not isinstance(d, str) or not d or '\0' in d for d in daemons):
        raise Error('ArgumentsBad', 'daemons must be an array of nonempty path strings')
    for daemon in daemons:
        try:
            result = subprocess.run(['aos-daemon-ctl', '--daemon', daemon, 'ls', '--json'],
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True)
        except OSError as error:
            raise Error('DaemonFailed', 'cannot run aos-daemon-ctl: %s' % error) from None
        if result.stderr:
            sys.stderr.write(result.stderr)
        if result.returncode:
            lines = result.stderr.strip().splitlines()
            reason = lines[-1] if lines else 'aos-daemon-ctl exited %d' % result.returncode
            raise Error('DaemonFailed', reason)
        try:
            rows = json.loads(result.stdout)['procs']
            if not isinstance(rows, dict) or any(not isinstance(row, dict) for row in rows.values()):
                raise ValueError('procs must be an object of proc rows')
        except (ValueError, KeyError, TypeError) as error:
            raise Error('DaemonFailed', 'invalid aos-daemon-ctl listing: %s' % error) from None
        for row in rows.values():
            definition = row.get('def')
            if row.get('phase') != 'stopped' and isinstance(definition, str) and definition:
                resolved = Path(definition).resolve()
                if resolved.is_relative_to(current.resolve()):
                    raise Error('DefBusy', 'a proc is using %s' % definition)


def _stamp(root, previous):
    instant = datetime.now(timezone.utc)
    while True:
        promoted_at = instant.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        stamp = promoted_at.replace(':', '-')
        temporary = root / '.prev' / ('.tmp-' + stamp)
        if not (previous / stamp).exists() and not temporary.exists():
            return promoted_at, stamp, temporary
        instant += timedelta(milliseconds=1)


def _prune(previous):
    if previous.is_dir() and not any(previous.iterdir()):
        previous.rmdir()


def promote(args):
    root, target, current, previous = _paths(args)
    source_root = _root(args.get('from'), 'from')
    source = _inside(source_root, source_root / target)
    if not current.is_dir() or not source.is_dir():
        raise Error('DefMissing', 'both current and candidate definitions must exist as directories')
    _idle(current, args)
    promoted_at, stamp, temporary = _stamp(root, previous)
    backup = previous / stamp
    moved = False
    try:
        previous.mkdir(parents=True, exist_ok=True)
        os.rename(current, backup)
        moved = True
        shutil.copytree(source, temporary, symlinks=True)
        os.rename(temporary, current)
    except OSError as error:
        recovery = []
        if moved:
            try:
                os.rename(backup, current)
            except OSError as restore_error:
                recovery.append('previous version retained at %s: %s' % (backup, restore_error))
        try:
            if temporary.exists():
                shutil.rmtree(temporary)
            _prune(previous)
        except OSError as cleanup_error:
            recovery.append('cleanup failed: %s' % cleanup_error)
        raise Error('SwapFailed', '; '.join([str(error)] + recovery)) from None
    return {'target': target, 'promoted_at': promoted_at, 'prev': str(backup)}


def rollback(args):
    root, target, current, previous = _paths(args)
    _idle(current, args)
    versions = sorted(p for p in previous.iterdir() if VERSION.fullmatch(p.name) and p.is_dir()) if previous.is_dir() else []
    if not versions:
        raise Error('PrevMissing', 'no previous version exists for %s' % target)
    if any(VERSION.fullmatch(child.name) and child.is_dir()
           for version in versions for child in version.iterdir()):
        raise Error('SwapFailed', 'history contains ambiguous timestamp-named directories; no files changed')
    if not current.is_dir():
        raise Error('DefMissing', 'current definition must exist as a directory')
    latest = _inside(root, versions[-1])
    _, _, temporary = _stamp(root, previous)
    moved = False
    try:
        os.rename(current, temporary)
        moved = True
        try:
            os.rename(latest, current)
        except OSError:
            os.rename(temporary, current)
            moved = False
            raise
        shutil.rmtree(temporary)
        _prune(previous)
    except OSError as error:
        suffix = '; replaced version retained at %s' % temporary if moved and temporary.exists() else ''
        raise Error('SwapFailed', str(error) + suffix) from None
    return {'target': target, 'restored': latest.name}
