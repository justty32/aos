"""壓縮記憶的封存檔：sha、原子寫檔、封存資料夾，以及人用的 `aos-agent history --archive`。"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

import aos_agent_info
import aos_home
from aos_agent_context import brief
from aos_agent_home import AgentError
from aos_agent_listen_render import call_names

from aos_agent_compact_plan import ARCHIVE


# ---- 寫 --------------------------------------------------------------------

def sha_of(raw):
    return hashlib.sha256(raw).hexdigest()[:16]


def _write_bytes(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def archive_dir(info):
    return Path(info['history_path']).parent / ARCHIVE


# ---- 人：aos-agent history --archive -------------------------------------------

def _load_archive(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, list):
        raise AgentError('NotAnArray', '%s 不是記憶陣列' % path)
    return value


def archive_main(agent_dir, *, sha=None, grep=None, as_json=False, env=None):
    """列 archive、印一份、或在 archive 裡找字。唯讀、不拿鎖。"""
    env = os.environ if env is None else env
    try:
        info = aos_agent_info.load(agent_dir, env=env)
        folder = archive_dir(info)
        paths = sorted(folder.glob('*.json'), key=lambda p: (p.stat().st_mtime, p.name)) if folder.is_dir() else []
        if sha is not None:
            paths = [p for p in paths if p.stem.startswith(sha)]
            if not paths:
                raise AgentError('NotFound', '%s 裡沒有 %s 開頭的 archive' % (folder, sha))
            if len(paths) > 1 and grep is None:
                raise AgentError('NotUnique', '%s 開頭的有 %d 份：%s' % (sha, len(paths), '、'.join(p.stem for p in paths)))
        if grep is not None:
            needle = grep.lower()
            hits = []
            for p in paths:
                history = _load_archive(p)
                names = call_names(history, len(history))
                for i, m in enumerate(history, 1):
                    text = (m.get('content') or '') + ''.join(c['function']['arguments'] for c in m.get('tool_calls') or [])
                    if needle in text.lower() or any(needle in c['function']['name'].lower()
                                                      for c in m.get('tool_calls') or []):
                        hits.append({'archive': p.stem, 'index': i, 'role': m.get('role'),
                                     'line': brief(m, names)})
            if as_json:
                print(json.dumps(hits, ensure_ascii=False))
            elif not hits:
                print('（archive 裡沒有「%s」）' % grep)
            for h in hits if not as_json else []:
                print('%s 第 %d 則  %s' % (h['archive'], h['index'], h['line'][:200]))
            return 0
        if sha is not None:
            history = _load_archive(paths[0])
            if as_json:
                print(json.dumps(history, ensure_ascii=False))
                return 0
            names = call_names(history, len(history))
            for i, m in enumerate(history, 1):
                print('第 %d 則  %s' % (i, brief(m, names, full=True)))
            return 0
        rows = []
        for p in paths:
            try:
                count = len(_load_archive(p))
            except (OSError, ValueError, AgentError):
                count = None
            rows.append({'archive': p.stem, 'path': str(p), 'count': count, 'bytes': p.stat().st_size,
                         'at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(p.stat().st_mtime))})
        if as_json:
            print(json.dumps(rows, ensure_ascii=False))
        elif not rows:
            print('（沒有 archive：%s）' % folder)
        for r in rows if not as_json else []:
            print('%s  %s  %s 則  %d bytes' % (r['archive'], r['at'], '?' if r['count'] is None else r['count'],
                                            r['bytes']))
        return 0
    except (AgentError, aos_home.HomeError, OSError, ValueError) as exc:
        from aos_agent import _error
        if isinstance(exc, ValueError) and not isinstance(exc, AgentError):
            exc = AgentError('JsonSyntax', str(exc))
        return _error(exc)
