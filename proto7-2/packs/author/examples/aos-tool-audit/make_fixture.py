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
    mail = root / 'R'
    ids = []
    # 六個真 REQUEST；兩個 done 自動回 DONE、兩個 PROGRESS、兩個不回。
    for sender, to in [('alice','bob'), ('alice','bob'), ('carol','bob'), ('carol','bob'), ('bob','carol'), ('bob','alice')]:
        ids.append(json.loads(cli('mail', '--root', mail, 'send', sender, to, 'REQUEST', '請檢查樣本'))['id'])
    for person in ('alice', 'bob', 'carol'):
        cli('mail', '--root', mail, 'read', person)
    for id in ids[:2]:
        cli('mail', '--root', mail, 'done', 'bob', id, 'DONE', '已檢查')
    for id in ids[2:4]:
        cli('mail', '--root', mail, 'send', 'bob', 'carol', 'PROGRESS', '正在檢查', '--re', id)
    cli('mail', '--root', mail, 'read', 'alice')
    cli('mail', '--root', mail, 'read', 'carol')
    # 手加：bob/inbox/99990101T0000-no-frontmatter.md，無 frontmatter。
    (mail / 'bob/inbox/99990101T0000-no-frontmatter.md').write_text('# 手加：無 frontmatter\n')
    # 手加：bob/inbox/99990101T0001-dup.md，原樣複製一封既有信，重複 id。
    original = sorted((mail / 'bob/inbox').glob('*.md'))[0]
    shutil.copy2(original, mail / 'bob/inbox/99990101T0001-dup.md')
    source = mail
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
