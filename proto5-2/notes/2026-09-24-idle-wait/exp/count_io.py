"""用 Python audit hook＋包 os.stat 數一支 CLI 碰了哪些檔（機器上沒有 strace 時用）。

用法：python3 count_io.py OUT.json -- /path/to/cli/aos-agent tick --target X
分兩類：`:python`＝Python 安裝目錄、proto5/lib、__pycache__ 底下（import 自己讀 .py／.pyc 的噪音）；`:data`＝其他（家、K）。
"""
import atexit
import json
import os
import runpy
import sys

out, rest = sys.argv[1], sys.argv[sys.argv.index('--') + 1:]
lib = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(rest[0]))), 'lib')
prefixes = tuple(os.path.realpath(p) for p in {sys.prefix, sys.base_prefix, lib}) + tuple(os.path.abspath(p) for p in {sys.prefix, sys.base_prefix, lib})
counts, paths = {}, {}


def note(kind, path):
    try:
        path = os.fsdecode(path) if isinstance(path, (bytes, str, os.PathLike)) else str(path)
    except Exception:
        path = str(path)
    real = os.path.abspath(path) if path and not path.isdigit() else path
    python = real.startswith(prefixes) or '__pycache__' in real or real.endswith(('.py', '.pyc', '.so'))
    key = kind + (':python' if python else ':data')
    counts[key] = counts.get(key, 0) + 1
    if not python:
        paths.setdefault(kind, []).append(path)


def hook(event, args):
    if event == 'open':
        mode = args[1] if len(args) > 1 else 'r'
        if isinstance(mode, int):
            kind = 'open_w' if mode & (os.O_WRONLY | os.O_RDWR | os.O_CREAT) else 'open_r'
        else:
            kind = 'open_w' if isinstance(mode, str) and any(c in mode for c in 'wax+') else 'open_r'
        note(kind, args[0])
    elif event in ('os.listdir', 'os.scandir'):
        note('listdir', args[0])
    elif event in ('os.rename', 'os.replace', 'os.link', 'os.remove', 'os.unlink', 'os.mkdir'):
        note(event.split('.')[1], args[0])
    elif event == 'subprocess.Popen':
        note('spawn', args[0])


for fn in ('stat', 'lstat'):
    orig = getattr(os, fn)

    def wrap(p, *a, _orig=orig, _fn=fn, **k):
        note(_fn, p)
        return _orig(p, *a, **k)
    setattr(os, fn, wrap)

sys.addaudithook(hook)


@atexit.register
def dump():
    with open(out, 'w') as f:
        json.dump({'counts': counts, 'data_paths': paths}, f, ensure_ascii=False, indent=1)


sys.argv = rest
sys.path.insert(0, lib)
runpy.run_path(rest[0], run_name='__main__')
