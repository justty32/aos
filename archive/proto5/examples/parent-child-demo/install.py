#!/usr/bin/env python3
"""Add fixed host bridge tools to an existing parent; do not reset its memory."""
import argparse
import json
from pathlib import Path
import shutil
import sys

from bridge import check_paths, cli, write_json


def tool(home, role, name, key, description):
    return {'type': 'function', 'function': {
        'name': name, 'description': description,
        'parameters': {'type': 'object', 'properties': {key: {'type': 'string',
            'minLength': 1, 'maxLength': 12000}}, 'required': [key], 'additionalProperties': False}},
        '_jail': False, '_timeout_ms': 180000, '_meta': {'argv': [sys.executable, str(home / 'bridge.py'),
                                           str(home / 'bridge-config.json'), role, name]}}


def install(root):
    root = root.absolute()
    cfg = {'root': str(root), 'cli': str(Path(__file__).resolve().parents[2] / 'cli' / 'aos-agent')}
    check_paths(cfg)
    for item in ('parent/info.json', 'K/info.json', 'project', 'reference'):
        if not (root / item).exists():
            raise ValueError('missing prerequisite: ' + str(root / item))
    child = root / 'child'
    home = root / 'parent-child-demo'
    expected = {'root': str(root), 'owner': 'parent-child-demo-v1'}
    if child.exists():
        from bridge import check_owned
        check_owned(root)
    if home.exists():
        if not (home / 'owner.json').is_file() or json.loads((home / 'owner.json').read_text()) != expected:
            raise ValueError('refusing to overwrite an unrelated parent-child-demo folder')
        if not (home / '.installed').is_file():
            raise ValueError('previous install incomplete; inspect parent tools registration on host')
        # Repeat install is read-only: do not replace a bridge while tools run.
        print('Already installed; parent memory, tools and bridge unchanged.')
        return
    home.mkdir(mode=0o700)
    write_json(home / 'owner.json', expected)
    shutil.copyfile(Path(__file__).with_name('bridge.py'), home / 'bridge.py')
    write_json(home / 'bridge-config.json', cfg)
    desc = 'Send one message to your fixed peer (parent/child). Returns immediately; do not acknowledge acknowledgements.'
    write_json(home / 'parent-link.json', [
        tool(home, 'parent', 'spawn_child', 'task',
             'Create or reuse your only child and queue a task. Child shares /work/ws (rw) and /work/ref (ro). '
             'Returns before completion: end your turn and wait for its send_peer message. Cannot create grandchildren.'),
        tool(home, 'parent', 'send_peer', 'message', desc)])
    write_json(home / 'child-link.json', [tool(home, 'child', 'send_peer', 'message', desc)])
    cli(cfg, 'tools', 'add', home / 'parent-link.json', '--target', root / 'parent')
    (home / '.installed').write_text('installed\n')
    print('Installed spawn_child and send_peer into the existing parent.')
    print('Only these management tools use _jail:false. Child shares project rw, reference ro; network off.')
    print('Parent prompts, history and existing tools are preserved. Child is created by the first spawn_child call.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        install(args.root)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, str(exc) + '\n')
