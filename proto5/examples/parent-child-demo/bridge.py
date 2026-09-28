#!/usr/bin/env python3
"""Fixed parent/child host bridge. Model arguments cannot select paths or commands."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def check_paths(cfg):
    root = Path(cfg['root'])
    paths = [root, root / 'parent', root / 'child', root / 'project',
             root / 'reference', root / 'D', root / 'K', root / 'parent-child-demo']
    for path in paths:
        if path.resolve() != path.absolute():
            raise ValueError('fixed demo paths must not contain symlinks')
    return root


def cli(cfg, *args):
    env = dict(os.environ)
    env['AOS_DAEMON_HOME'] = cfg['root'] + '/D'
    env['AOS_KERNEL_HOME'] = cfg['root'] + '/K'
    env['PATH'] = str(Path(cfg['cli']).parent) + os.pathsep + os.defpath
    result = subprocess.run([cfg['cli'], *map(str, args)], env=env,
                            text=True, capture_output=True, timeout=35)
    if result.returncode:
        # No raw stderr: environment/config errors can contain credentials.
        raise RuntimeError('aos-agent %s failed (exit %d); inspect its status on the host'
                           % (' '.join(str(x) for x in args[:2]), result.returncode))
    return result.stdout


def check_owned(root):
    child = root / 'child'
    expected = {'root': str(root), 'owner': 'parent-child-demo-v1'}
    marker = child / '.parent-child-demo.json'
    if not marker.is_file() or marker.is_symlink() or json.loads(marker.read_text()) != expected:
        raise ValueError('refusing to use an existing child not created by this demo')


def spawn(cfg, task):
    root = check_paths(cfg)
    child = root / 'child'
    with (root / 'parent-child-demo' / 'spawn.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if child.exists():
            check_owned(root)
            if not (child / '.ready').is_file():
                raise ValueError('child creation was interrupted; inspect on host before retrying')
        else:
            child.mkdir()
            write_json(child / '.parent-child-demo.json',
                       {'root': str(root), 'owner': 'parent-child-demo-v1'})
            cli(cfg, 'init', '--target', child, '--force')
            cli(cfg, 'tools', 'add', 'base', '--target', child, '--root', root / 'project')
            cli(cfg, 'access', 'set', 'ws', root / 'project', '--rw', '--cwd', '--target', child)
            cli(cfg, 'access', 'set', 'ref', root / 'reference', '--ro', '--target', child)
            cli(cfg, 'access', 'net', 'off', '--target', child)
            cli(cfg, 'tools', 'add', root / 'parent-child-demo' / 'child-link.json', '--target', child)
            write_json(child / 'prompts/system.json', {'content':
                '你是 child，parent 的子 agent，使用繁體中文。每次收到任務請實際使用工具完成；'
                '/work/ws 是與 parent 共用的可寫工作目錄，/work/ref 唯讀。'
                '只改任務指定的檔案。完成或遇到阻塞時用 send_peer(message) 回報 parent 一次，'
                '含檔案位置、驗證結果，再結束本輪。不要對收件確認或客套話回信，避免無限互傳。'})
            (child / '.ready').write_text('ready\n')
        cli(cfg, 'start', '--target', child)
        cli(cfg, 'say', '[parent task]\n' + task, '--target', child)
    return {'ok': True, 'status': 'queued', 'child': 'child',
            'note': 'Task queued, not completed. End this turn; child will send a message when done.'}


def invoke(cfg, role, action, args):
    root = check_paths(cfg)
    if Path.cwd().resolve() != root / role:
        raise ValueError('bridge must run in its fixed agent home')
    key = 'task' if action == 'spawn_child' else 'message'
    if action not in ('spawn_child', 'send_peer') or (action == 'spawn_child' and role != 'parent'):
        raise ValueError('operation is not allowed for this agent')
    if not isinstance(args, dict) or set(args) != {key}:
        raise ValueError('exactly one argument is required: ' + key)
    value = args[key]
    if not isinstance(value, str) or not value.strip() or len(value) > 12000 or '\0' in value:
        raise ValueError(key + ' must be nonempty text, at most 12000 characters, without NUL')
    if action == 'spawn_child':
        return spawn(cfg, value)
    check_owned(root)
    peer = 'child' if role == 'parent' else 'parent'
    cli(cfg, 'say', '[from %s]\n%s' % (role, value), '--target', root / peer)
    return {'ok': True, 'status': 'queued', 'to': peer,
            'note': 'Message queued. Do not poll or send acknowledgement loops.'}


def main():
    try:
        if len(sys.argv) != 4 or sys.argv[2] not in ('parent', 'child'):
            raise ValueError('invalid fixed bridge invocation')
        cfg = json.loads(Path(sys.argv[1]).read_text())
        args = json.loads(sys.stdin.read(65537))
        result = invoke(cfg, sys.argv[2], sys.argv[3], args)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
