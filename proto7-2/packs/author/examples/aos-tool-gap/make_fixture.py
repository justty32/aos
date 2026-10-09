#!/usr/bin/env python3
"""重現真樣本；時間與 id 每次不同，checker 的固定答案不隨重造更新。"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
P = HERE.parents[3]

def cli(module, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([str(P / 'modules' / module / ('aos7-' + module)), *map(str, args)], env=env, check=True, capture_output=True, text=True)
    return result.stdout

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    events = root / 'n1' / 'events'
    # 小段設定只在公開取樣器 CLI 提供；透過真 daemon 啟動一次初建。
    ctl = P / 'bin/aos7-ctl'
    subprocess.run([str(ctl), 'daemon', str(root), 'register', 'n1'], check=True, capture_output=True)
    task = {'name': 'events', 'mode': 'keep', 'argv': [str(P / 'modules/events/aos7-events'), '--src', 'absent', '--segment-bytes', '900', '--keep', '4']}
    subprocess.run([str(ctl), 'add', str(root / 'n1'), json.dumps(task)], check=True, capture_output=True)
    daemon = subprocess.Popen([str(P / 'bin/aos7-daemon'), str(root)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    try:
        for attempt in range(500):
            if (events / 'state.json').exists():
                break
            time.sleep(.02)
        else:
            raise RuntimeError('sampler 未初建 state')
    finally:
        subprocess.run([str(ctl), 'daemon', str(root), 'stop', '--kill'], check=True, capture_output=True)
        daemon.wait(timeout=15)
    for channel in ('obs', 'must'):
        for i in range(1, 13):
            cli('events', 'pub', '--events', events, '--create', '--kind', 'fixture.sample', '--payload', json.dumps({'n': i}), '--event-id', channel + '/' + str(i), *(['--must'] if channel == 'must' else []))
    cli('events', 'ack', '--events', events, '5')
    # 手加：從 obs 封存段刪 seq=2，形成一個缺號；其餘真紀錄不改。
    segment = sorted(events.glob('obs.[0-9]*.jsonl'))[0]
    segment.write_bytes(b''.join(line for line in segment.read_bytes().splitlines(keepends=True) if json.loads(line)['seq'] != 2))
    # 手加：obs.active.jsonl 尾端一行壞 JSON、一行半截。
    with (events / 'obs.active.jsonl').open('ab') as f:
        f.write(b'{bad json}\n{"seq":')
    source = events
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
