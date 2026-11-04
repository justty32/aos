"""Stage using the group's baseline ignore rules, not the task's new rules."""
import os
import subprocess
import tempfile
from pathlib import Path


def git_bytes(node, *args, data=None, allowed=(0,)):
    env = dict(os.environ, GIT_LITERAL_PATHSPECS='1' if args[0] in ('add', 'ls-tree') else '0')
    result = subprocess.run(['git', '-C', str(node), *args], input=data, capture_output=True, env=env)
    if result.returncode not in allowed:
        raise OSError(result.stderr.decode('utf-8', 'replace'))
    return result.stdout


def stage_baseline(node, gitdir, head):
    baseline = git_bytes(node, 'ls-tree', '-r', '--name-only', '-z', head).split(b'\0')[:-1]
    candidates = set(git_bytes(node, 'ls-files', '--cached', '--others', '-z').split(b'\0')[:-1])
    candidates.update(baseline)
    with tempfile.TemporaryDirectory(dir=gitdir / 'aos', prefix='ignore-') as directory:
        # check-ignore accepts non-existent names, reading rules from this mirror.
        mirror = Path(directory)
        for name in baseline:
            if name.split(b'/')[-1] != b'.gitignore':
                continue
            mode = git_bytes(node, 'ls-tree', head, '--', os.fsdecode(name)).split(b' ', 1)[0]
            if mode == b'120000':  # Git does not follow symlink .gitignore files.
                continue
            target = mirror / os.fsdecode(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git_bytes(node, 'show', head + ':' + os.fsdecode(name)))
        # Prefix ./ so check-ignore cannot interpret a leading : as pathspec magic.
        names = b'\0'.join(b'./' + name for name in sorted(candidates)) + (b'\0' if candidates else b'')
        ignored_raw = git_bytes(node, '--work-tree=' + str(mirror), 'check-ignore', '--no-index',
                                '-z', '--stdin', data=names, allowed=(0, 1)).split(b'\0')[:-1]
        ignored = {name[2:] if name.startswith(b'./') else name for name in ignored_raw}
    managed = (candidates - ignored) | set(baseline)
    # Throw away task-written index entries, retaining working-tree changes.
    git_bytes(node, 'reset', '-q', head)
    if managed:
        # -f applies only to the explicitly selected baseline-managed paths.
        names = b'\0'.join(sorted(managed)) + b'\0'
        git_bytes(node, 'add', '-A', '-f', '--pathspec-from-file=-', '--pathspec-file-nul', data=names)
