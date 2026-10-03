#!/usr/bin/env python3
"""Run from any cwd. Actual aos7-tick starts every audited worker; no product edits."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
PROJECT = next(p for p in HERE.parents if (p / 'lib/aos7_mount.py').exists())
BASE = Path(tempfile.mkdtemp(prefix='astra3-reg-audit-'))
ROOT = BASE / 'space'
ROOT.mkdir()
ENV = dict(os.environ, AOS7_AUDIT='1')
worker = r'''
import json, os, pathlib, sys, time
P = pathlib.Path
node, root, task = map(P, (os.environ['AOS7_NODE'], os.environ['AOS7_ROOT'], os.environ['AOS7_TASK']))
mode = sys.argv[1]
if mode == 'baseline':
    (root/'b/absolute.txt').write_text('absolute')
    P('../b/dotdot.txt').write_text('dotdot')
    P('escape/symlink.txt').write_text('symlink')
    (root.parent/'outside/outside-python.txt').write_text('outside')
elif mode == 'dirfd':
    fd = os.open(root/'b', os.O_RDONLY | os.O_DIRECTORY)
    out = os.open('dirfd.txt', os.O_CREAT | os.O_WRONLY, 0o600, dir_fd=fd)
    os.write(out, b'dirfd actual b')
    os.close(out)
    os.mkdir('dirfd-dir', dir_fd=fd)
    os.rename('rename-src.txt', 'rename-dst.txt', src_dir_fd=fd, dst_dir_fd=fd)
    os.unlink('remove.txt', dir_fd=fd)
    os.close(fd)
elif mode == 'retarget':
    box = task/'mnt/box'
    (box/'before.txt').write_text('approved b')
    box.unlink()
    box.symlink_to(root/'c', target_is_directory=True)
    (box/'retarget.txt').write_text('unapproved c')
elif mode == 'request':
    req = task/'mount-req'
    req.mkdir()
    for name, path in [('inside','allowed/inside'), ('outside','allowed/outside/new-created-by-tick')]:
        (req/(name+'.json')).write_text(json.dumps({'name':name,'path':path,'why':'probe symlink allow'}))
    (task/'ready').write_text('ready')
    limit=time.monotonic()+10
    while not (task/'mount-done/outside.json').exists():
        if time.monotonic()>limit: raise RuntimeError('no tick response')
        time.sleep(.01)
    for name in ['inside','outside']:
        (task/'mnt'/name/'via-approved-link.txt').write_text(name)
'''

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')

def wait(pred):
    limit = time.monotonic()+15
    while not pred():
        if time.monotonic()>limit:
            raise RuntimeError('wait timeout')
        time.sleep(.02)

def tick():
    p = subprocess.run([sys.executable, str(PROJECT/'bin/aos7-tick'), str(ROOT), 'a'],
                       env=ENV, text=True, capture_output=True, timeout=20)
    ticks.append({'code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    if p.returncode: raise RuntimeError(p.stderr)

ticks=[]
try:
    for name in ['a','b','c']:
        dump(ROOT/name/'.aos/timeline.json', {'interval_ms':100})
        dump(ROOT/name/'.aos/tasks.json', {'tasks':[]})
    (BASE/'outside').mkdir()
    (ROOT/'allowed').mkdir()
    (ROOT/'allowed/inside').symlink_to(ROOT/'c', target_is_directory=True)
    (ROOT/'allowed/outside').symlink_to(BASE/'outside', target_is_directory=True)
    (ROOT/'a/escape').symlink_to(ROOT/'b', target_is_directory=True)
    (ROOT/'b/rename-src.txt').write_text('src')
    (ROOT/'b/remove.txt').write_text('remove')
    tasks=[]
    for mode in ['baseline','dirfd','retarget','request']:
        item={'name':mode,'argv':[sys.executable,'-c',worker,mode]}
        if mode=='retarget': item['mounts']={'box':'b'}
        tasks.append(item)
    tasks.append({'name':'shell','argv':['/bin/sh','-c','printf shell > "$AOS7_ROOT/b/shell.txt"']})
    dump(ROOT/'a/.aos/tasks.json', {'tasks':tasks, 'mount_allow':['allowed']})
    tick()
    td=ROOT/'a/.aos/tasks'
    wait(lambda:(td/'request-r1/ready').exists())
    dump(ROOT/'a/.aos/tasks.json', {'tasks':[], 'mount_allow':['allowed']})
    tick()
    wait(lambda:all((td/(t['name']+'-r1')/'exit.json').exists() for t in tasks))
    # Wait for runners to fully leave after exit.json; all payloads are bounded.
    pids=[]
    for p in td.glob('*/pid.json'):
        data=json.loads(p.read_text())
        pids.extend(data[k] for k in ['pid','runner_pid'] if k in data)
    def alive(pid):
        try: return Path('/proc',str(pid),'stat').read_text().split(') ')[1].split()[0] != 'Z'
        except FileNotFoundError: return False
    wait(lambda:not any(alive(p) for p in pids))
    files={}
    for p in sorted(BASE.rglob('*')):
        if p.is_file() and not p.is_symlink():
            files[str(p.relative_to(BASE))]=p.read_text()
    sys.path.insert(0,str(PROJECT/'lib'))
    import aos7_audit
    audit=aos7_audit.scan(str(ROOT))
    links={str(p.relative_to(BASE)):os.readlink(p) for p in BASE.rglob('*') if p.is_symlink()}
    summary={'base':str(BASE),'ticks':ticks,'audit':audit,'symlinks':links,
             'task_exits':{p.parent.name:json.loads(p.read_text()) for p in td.glob('*/exit.json')},
             'actual_files':{str(p.relative_to(BASE)):(p.read_text() if p.exists() else None) for p in [
                 ROOT/'b/absolute.txt',ROOT/'b/dotdot.txt',ROOT/'b/symlink.txt',ROOT/'b/shell.txt',
                 ROOT/'b/dirfd.txt',ROOT/'b/rename-dst.txt',ROOT/'c/retarget.txt',
                 ROOT/'c/via-approved-link.txt',BASE/'outside/outside-python.txt',
                 BASE/'outside/new-created-by-tick/via-approved-link.txt']},
             'dirfd_mkdir_actual':(ROOT/'b/dirfd-dir').is_dir(),
             'dirfd_remove_actual':not (ROOT/'b/remove.txt').exists(),
             'all_started_pids_gone_or_zombie':not any(alive(p) for p in pids)}
    dump(HERE/'results.json',summary)
    dump(HERE/'raw-files.json',files)
finally:
    # No daemon is used. On unexpected failure, terminate our identified task groups.
    for p in ROOT.glob('a/.aos/tasks/*/pid.json'):
        data=json.loads(p.read_text())
        try:
            stat=Path('/proc',str(data['pid']),'stat').read_text()
            if stat.split(') ')[1].split()[0]!='Z': os.killpg(data['pgid'],15)
        except (FileNotFoundError, ProcessLookupError): pass
    shutil.rmtree(BASE)
print(json.dumps({'evidence':str(HERE),'temporary_root_removed':not BASE.exists()},ensure_ascii=False))
