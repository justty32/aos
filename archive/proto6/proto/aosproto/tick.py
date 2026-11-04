import argparse
import fcntl
import os
import subprocess
import sys
from pathlib import Path
from .common import Fault, ID_RE, fields, read_json
from .inst import validate
from .process import execute
from .git_scope import stage_baseline


def tasks_validate(obj):
    fields(obj, ('_metainfo', 'tasks'), ('_metainfo', 'tasks'))
    fields(obj['_metainfo'], ('_type', '_version'), ('_type', '_version'))
    meta = obj['_metainfo']
    if meta['_type'] != 'aos-tasks' or type(meta['_version']) is not int or meta['_version'] != 1:
        raise ValueError('不支援 tasks 的種類／版本')
    if not isinstance(obj['tasks'], list):
        raise ValueError('tasks 必須為陣列')
    seen, groups, previous, rank = set(), set(), None, 0
    for task in obj['tasks']:
        if not isinstance(task, dict) or 'user' in task:
            raise ValueError('任務必须是物件且不可有 user')
        validate(task)
        name, kind = task.get('id'), task.get('kind')
        if not isinstance(name, str) or not ID_RE.fullmatch(name) or name in seen:
            raise ValueError('task id 不合法或重複')
        if kind not in ('system', 'kernel', 'agent', 'custom'):
            raise ValueError('kind 不合法')
        current = {'system': 0, 'kernel': 1, 'agent': 1, 'custom': 2}[kind]
        if current < rank:
            raise ValueError('kind 必須 system → kernel/agent → custom')
        rank = current
        group = task.get('group')
        if 'group' in task and (not isinstance(group, str) or not ID_RE.fullmatch(group)):
            raise ValueError('group 不合法')
        if group is not None and group != previous and group in groups:
            raise ValueError('同 group 必須連續')
        if group is not None:
            groups.add(group)
        previous = group
        needs = task.get('needs', [])
        if (not isinstance(needs, list) or not all(isinstance(n, str) for n in needs)
                or len(set(needs)) != len(needs) or not set(needs) <= seen):
            raise ValueError('needs 必須是不重複的前項 ID')
        seen.add(name)
    return obj['tasks']


def git(node, *args, check=True):
    result = subprocess.run(['git', '-C', str(node), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    if check and result.returncode:
        raise OSError('git ' + ' '.join(args) + ': ' + result.stderr.strip())
    return result


def restore(node, head, gitdir):
    # Index managed new files under baseline rules before reset removes them.
    # Otherwise a newly created nested .gitignore can hide failed output from clean.
    stage_baseline(node, gitdir, head)
    git(node, 'reset', '--hard', '-q', head)
    git(node, 'clean', '-fdq')


def block(gitdir, message):
    print('tick_blocked: ' + message, file=sys.stderr)
    try:
        (gitdir / 'aos/tick-blocked').write_text(message + '\n')
    except OSError as exc:
        print('tick_blocked_write_failed: ' + str(exc), file=sys.stderr)
    return 3


def run(node):
    node = Path(node).absolute()
    lock_fd = None
    gitdir = None
    processing = False
    try:
        top = git(node, 'rev-parse', '--show-toplevel').stdout.strip()
        if Path(top) != node:
            raise OSError('node 必須是 git repo 根目錄')
        gitdir = Path(git(node, 'rev-parse', '--absolute-git-dir').stdout.strip())
        (gitdir / 'aos').mkdir(exist_ok=True)
        lock_fd = os.open(gitdir / 'aos/tick.lock', os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 75
        if (gitdir / 'aos/tick-blocked').exists():
            raise OSError('aos/tick-blocked 存在，請先修復')
        head = git(node, 'rev-parse', '--verify', 'HEAD').stdout.strip()
        try:
            restore(node, head, gitdir)
        except OSError as exc:
            return block(gitdir, str(exc))
        try:
            tasks = tasks_validate(read_json(node / '.aos/tasks.json'))
        except (OSError, ValueError, Fault) as exc:
            print('invalid_tasks: ' + str(exc), file=sys.stderr)
            return 2
        processing = True
        batches = []
        for task in tasks:
            if batches and 'group' in task and batches[-1][-1].get('group') == task['group']:
                batches[-1].append(task)
            else:
                batches.append([task])
        success, failed_any = set(), False
        env = dict(os.environ, AOS_NODE_DIR=str(node), AOS_TICK_LOCK_FD=str(lock_fd))
        for batch in batches:
            head = git(node, 'rev-parse', 'HEAD').stdout.strip()
            branch = git(node, 'symbolic-ref', '-q', 'HEAD', check=False).stdout.strip()
            local = set()
            ok = True
            for task in batch:
                if not set(task.get('needs', [])) <= (success | local):
                    ok = False
                    break
                report = execute(task, node, os.getuid(), environment=env, pass_fds=(lock_fd,))
                if report.get('error', {}).get('code') == 'FinalizeFailed':
                    return block(gitdir, '任務後代／收尾失敗；保留現場')
                if report['exit_code'] != 0 or not report['started']:
                    ok = False
                    break
                local.add(task['id'])
            if (git(node, 'rev-parse', 'HEAD').stdout.strip() != head or
                    git(node, 'symbolic-ref', '-q', 'HEAD', check=False).stdout.strip() != branch):
                return block(gitdir, '任務改變 HEAD／分支；保留現場')
            try:
                if ok:
                    stage_baseline(node, gitdir, head)
                    diff = git(node, 'diff', '--cached', '--quiet', check=False)
                    if diff.returncode == 1:
                        git(node, '-c', 'core.hooksPath=/dev/null', 'commit', '-q', '--no-verify',
                            '-m', 'aos-tick group %s..%s' % (batch[0]['id'], batch[-1]['id']))
                    elif diff.returncode != 0:
                        raise OSError(diff.stderr)
                    success.update(local)
                else:
                    restore(node, head, gitdir)
                    failed_any = True
            except OSError as exc:
                return block(gitdir, str(exc))
        return 1 if failed_any else 0
    except OSError as exc:
        if processing and gitdir is not None:
            return block(gitdir, str(exc))
        print('tick_start_failed: ' + str(exc), file=sys.stderr)
        return 125
    finally:
        if lock_fd is not None:
            os.close(lock_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aos-tick')
    parser.add_argument('--node', default=os.getcwd())
    args = parser.parse_args(argv)
    return run(os.path.abspath(args.node))
