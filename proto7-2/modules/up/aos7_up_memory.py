"""把辦完的信存成全文和短目錄，讓下一封信能找回前件，也能請 AI 指名要看哪一件。"""
import hashlib
import os
from pathlib import Path
import re

from aos7_fs import test_point

DONE = 'notes/done'
INDEX = 'notes/done/INDEX.md'
OLD = 'notes/done/INDEX-old.md'
KEEP = 50
INDEX_MAX = 2000
FILE_MAX = 3000
PROMPT_MAX = 12000
HEADER = '# 做完的件（新的在下面）\n'
OLD_HEADER = '# 做完的件（舊）\n'
REFERENCES = ('前面', '你交的', '你寫的', '你給的', '上次', '之前', '前件', '上一封')
STOP = {'回合', '一節', '三句', '做完', '每回', '整理', '寫成', '先列', '給我', '分', '第'}


def fid(ident):
    safe = re.sub(r'[^A-Za-z0-9_-]', '-', ident)
    if safe in ('INDEX', 'INDEX-old'):
        safe = 'id-' + safe
    return safe if len(safe) <= 64 else safe[:47] + '-' + hashlib.sha1(ident.encode()).hexdigest()[:16]


def _read(path):
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return ''


def _write(path, text):
    tmp = path.with_name(path.name + '.memory-tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, path)


def _rows(node, name=INDEX):
    return [s for s in _read(Path(node) / name).splitlines() if s.startswith('- ')]


def _flat(text):
    return ' '.join(text.split()).replace('｜', '|')


def record(node, ident, ask, status, body):
    node = Path(node)
    ref = fid(ident)
    path = node / DONE / (ref + '.md')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _write(path, f'# {ask}\n\n狀態：{status}\n\n{body}\n')
    test_point('up-brain-after-done')
    rows, old = _rows(node), _rows(node, OLD)
    mark = '- ' + ref + '｜'
    if not any(s.startswith(mark) for s in rows + old):
        conclusion = next((re.sub(r'^[\s#>*_`\\-]+', '', s) for s in body.splitlines() if s.strip()), '')
        row = f'- {ref}｜{_flat(ask)[:30]}｜{status} {_flat(conclusion)[:40]}'
        _write(node / INDEX, (_read(node / INDEX) or HEADER).rstrip('\n') + '\n' + row + '\n')
        rows.append(row)
    if len(rows) > KEEP:
        overflow = rows[:-KEEP]
        known = {s.split('｜', 1)[0] for s in old}
        extra = [s for s in overflow if s.split('｜', 1)[0] not in known]
        if extra:
            _write(node / OLD, (_read(node / OLD) or OLD_HEADER).rstrip('\n') + '\n' + '\n'.join(extra) + '\n')
        _write(node / INDEX, HEADER + '\n'.join(rows[-KEEP:]) + '\n')
    test_point('up-brain-after-index')


def index_text(node):
    rows, size = [], 0
    for row in reversed(_rows(node)):
        extra = len(row) + bool(rows)
        if size + extra > INDEX_MAX:
            break
        rows.append(row)
        size += extra
    return '\n'.join(reversed(rows))


def _words(text):
    words = set(re.findall(r'[a-z0-9]{2,}', text.lower()))
    for run in re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff]+', text):
        words.update(run[i:i + 2] for i in range(len(run) - 1))
    return words - STOP


def pick(node, text):
    rows = [s[2:].split('｜', 2) for s in _rows(node)]
    for fields in reversed(rows):
        if len(fields) == 3 and fields[0] in text:
            return fields[0] if (Path(node) / DONE / (fields[0] + '.md')).is_file() else None
    if not any(word in text for word in REFERENCES):
        return None
    words, best, score = _words(text), None, 1
    for fields in rows:
        if len(fields) != 3:
            continue
        hits = len(words & _words(fields[1]))
        if hits >= 2 and hits >= score:
            best, score = fields[0], hits
    return best if best and (Path(node) / DONE / (best + '.md')).is_file() else None


def attach(node, ref):
    if not isinstance(ref, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', ref) or ref in ('INDEX', 'INDEX-old'):
        return None
    path = Path(node) / DONE / (ref + '.md')
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return None
    return text if len(text) <= FILE_MAX else text[:FILE_MAX] + f'\n（後面還有 {len(text) - FILE_MAX} 字沒附上）'


def want_of(text):
    head = text.lstrip()
    if not head.startswith('要檔案：'):
        return None
    line = head[len('要檔案：'):].split('\n', 1)[0].strip()
    if not line:
        return None
    ref = line.split()[0].strip('<>')
    return ref.removesuffix('.md').strip('<>')


def want_step(ref):
    return f'繼續：要看前件 {ref} 的全文\n停在哪：要檔案 {ref}'


def wanted(task):
    line = task.get('line', '')
    return line[len('要檔案 '):].strip() if line.startswith('要檔案 ') else None


def section(node, ref, got):
    index = index_text(node)
    text = ('做完的件（notes/done/INDEX.md；要看哪件全文而下面沒附，就只回「要檔案：<id>」）：\n' + index + '\n\n') if index else ''
    if ref is not None:
        text += (f'附上前件 {ref} 的全文：\n{got}\n\n' if got is not None else
                 f'要的前件 {ref} 沒有這個檔（只有目錄裡的 id 拿得到）。\n\n')
    return text


def fit(parts, size, limit):
    parts = dict(parts)
    for key in ('trail', 'skill'):
        if size <= limit:
            break
        size -= len(parts[key])
        parts[key] = ''
    if size > limit and parts['attach']:
        original = parts['attach']
        room = max(0, len(original) - (size - limit))
        kept = max(0, room - len(f'\n（太長，只附前 {room} 字）'))
        while kept and kept + len(f'\n（太長，只附前 {kept} 字）') > room:
            kept -= 1
        cut = original[:kept] + f'\n（太長，只附前 {kept} 字）' if kept else ''
        size -= len(original) - len(cut)
        parts['attach'] = cut
    return parts, size
