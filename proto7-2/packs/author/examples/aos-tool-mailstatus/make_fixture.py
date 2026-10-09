#!/usr/bin/env python3
"""用真郵局重現資料；重造後時間與 id 會變，固定答案須另行更新。"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
P = HERE.parents[3]

def cli(*args):
    result = subprocess.run([str(P / 'modules/mail/aos7-mail'), *map(str, args)], env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), check=True, capture_output=True, text=True)
    return result.stdout

with tempfile.TemporaryDirectory() as tmp:
    mail = Path(tmp) / 'R'
    cli('--root', mail, 'team', 'dev', 'dave', 'bob', 'carol')
    ids = []
    for sender, to in [('alice','bob'), ('alice','carol'), ('carol','bob'), ('bob','alice'), ('dave','carol'), ('bob','dave')]:
        ids.append(json.loads(cli('--root', mail, 'send', sender, to, 'REQUEST', '請檢查樣本'))['id'])
    for person in ('alice','bob','carol','dave'):
        cli('--root', mail, 'read', person)
    for person, ident, status in [('bob',ids[0],'DONE'), ('carol',ids[1],'DONE'), ('bob',ids[2],'BLOCKED')]:
        cli('--root', mail, 'done', person, ident, status, '已檢查樣本')
    # 寄件人把其中一封自動回信也辦結。
    reply = next(p for p in (mail / 'alice/inbox').glob('*.md') if 're-' + ids[0] in p.read_text())
    cli('--root', mail, 'done', 'alice', reply.name)
    cli('--root', mail, 'send', 'carol', 'dave', 'PROGRESS', '正在檢查', '--re', ids[4])
    for person in ('bob','carol'):
        cli('--root', mail, 'send', person, 'team:dev', 'PROGRESS', '全隊進度')
    for person in ('alice','bob','carol','dave'):
        cli('--root', mail, 'read', person)
    # 請求仍在頂層，唯一結案回信已辦結：漏讀已辦區會誤列未結。
    extra = json.loads(cli('--root', mail, 'send', 'dave', 'alice', 'REQUEST', '請確認尾項'))['id']
    reply = json.loads(cli('--root', mail, 'send', 'alice', 'dave', 'DONE', '尾項已確認', '--re', extra))['id']
    cli('--root', mail, 'done', 'dave', reply)
    # 真投遞使用 NamedTemporaryFile 的 tmp… 名稱；信頭已寫完，正文只寫一半。
    partial = '---\nfrom: carol\nto: dave\nstatus: DONE\nat: 2026-10-09T00:00:00+08:00\nreply-to: ' + str(mail / 'carol/inbox') + '\nid: interrupted-reply\nre: ' + ids[4] + '\n---\n# 已檢'
    tmpdir = mail / 'dave/inbox/.tmp'
    tmpdir.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=tmpdir, delete=False) as stream:
        stream.write(partial.encode())
    target = HERE / 'fixture'
    if target.exists():
        raise SystemExit('fixture 已存在；請先保留舊資料，再自行移開才重造')
    shutil.copytree(mail, target, copy_function=shutil.copy2)
    for directory in sorted(target.rglob('*'), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    files = [p for p in target.rglob('*') if p.is_file()]
    assert all(p.stat().st_size <= 4096 and p.suffix != '.pyc' for p in files)
    print(f'{target}: {len(files)} 檔')
