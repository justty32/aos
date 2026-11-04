#!/usr/bin/env python3
"""重現真樣本；時間與 id 每次不同，checker 的固定答案不隨重造更新。"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
P = HERE.parents[3]

def cli(module, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([str(P / 'modules' / module / ('aos7-' + module)), *map(str, args)], env=env, check=True, capture_output=True, text=True)
    return result.stdout

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    node = root / 'n1'
    node.mkdir()
    (node / 'ok.sh').write_text('#!/bin/sh\nexit 0\n')
    (node / 'fail.sh').write_text('#!/bin/sh\nexit 7\n')
    (node / 'ok.sh').chmod(0o755)
    (node / 'fail.sh').chmod(0o755)
    for name, every, inst in [('a-ok', '1h', 'ok.sh'), ('b-failed', '2m', 'fail.sh'), ('c-round', '3r', 'ok.sh'), ('d-day', '1d', 'ok.sh'), ('e-seconds', '30s', 'ok.sh'), ('f-minutes', '5m', 'ok.sh')]:
        cli('routines', 'add', node, name, '--every', every, inst)
    cli('routines', 'ls', node, '--run')
    for name in ('g-never', 'h-never', 'i-never'):
        cli('routines', 'add', node, name, '--every', '1h', 'ok.sh')
    for name, at in [('a-due', '2020-01-01T00:00:00'), ('b-pending', '2099-01-01T00:00:00+08:00'), ('c-local', '2099-01-02T00:00:00')]:
        cli('routines', 'add', node, name, '--at', at, 'ok.sh')
    # 手加：wf/routines.json 尾端一列 every 壞、一列重名，共 2 列。
    path = node / 'wf' / 'routines.json'
    data = json.loads(path.read_text())
    data['rows'].extend([dict(name='z-bad', every='wrong', inst='ok.sh', last_time='', last_code=''), dict(data['rows'][0])])
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    source = node
    target = HERE / 'fixture'
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, copy_function=shutil.copy2)
    # git 不保存空目錄；它們未含任何紀錄，不納入題目。
    for directory in sorted(target.rglob('*'), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    files = [p for p in target.rglob('*') if p.is_file()]
    assert len(files) <= 60
    assert all(p.stat().st_size <= 4096 for p in files)
    print(f'{target}: {len(files)} files')
