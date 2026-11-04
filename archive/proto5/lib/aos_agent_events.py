"""事件紀錄（spec/agent/events.md）：agent 家 log/events.jsonl，一行一事件。

寫的人只有一個：持 .tick.lock 的那一方（tick 本身，或拿了同一把鎖的 aos-agent compact）。
追加一行＝一次 write（O_APPEND）；寫不進去只丟掉這一行，不讓 tick 失敗（量測不能拖垮主流程）。
**至少一次**：事件都在「提交那一步」之前寫，崩了重做會再寫一次同一行（同 ev＋id），讀的人用 dedupe() 去重；
所以行程崩潰不會「做了沒記」，只可能「記了兩次」。例外：寫檔本身失敗（log/ 不能寫、磁碟滿）那一行就丟了。
"""
import datetime
import json
import os
from pathlib import Path

EVENTS = 'log/events.jsonl'
USAGE = 'log/usage.jsonl'
ROTATE_MB = 10   # 滿 10 MB 輪換、留 3 份舊的（09-24 調度者代裁；info.json 的 logs 可改）
KEEP = 3


def limits(base):
    """info.json 的 logs：{"rotate_mb": 非負整數（0＝不輪換）, "keep": 0～20}；沒寫或壞了＝預設。回 (bytes 或 0, keep)。"""
    try:
        with open(Path(base) / 'info.json', encoding='utf-8') as f:
            value = json.load(f).get('logs')
    except (OSError, ValueError, AttributeError):
        value = None
    value = value if isinstance(value, dict) else {}
    mb, keep = value.get('rotate_mb', ROTATE_MB), value.get('keep', KEEP)
    mb = mb if type(mb) in (int, float) and mb >= 0 else ROTATE_MB
    keep = keep if type(keep) is int and 0 <= keep <= 20 else KEEP
    return int(mb * 1024 * 1024), keep


def rotated(path, i):
    """events.jsonl 的第 i 份舊檔：events.<i>.jsonl。"""
    path = Path(path)
    return path.with_name('%s.%d%s' % (path.stem, i, path.suffix))


def _rotate(path, max_bytes, keep):
    """滿了就 events.jsonl→events.1.jsonl→…→events.<keep>.jsonl，最舊的丟掉。呼叫的人持資料夾的 flock。"""
    try:
        if not max_bytes or os.stat(path).st_size < max_bytes:
            return
    except FileNotFoundError:
        return
    if keep == 0:
        os.unlink(path)
        return
    rotated(path, keep).unlink(missing_ok=True)
    for i in range(keep - 1, 0, -1):
        if rotated(path, i).exists():
            os.rename(rotated(path, i), rotated(path, i + 1))
    os.rename(path, rotated(path, 1))


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec='milliseconds')


def append_line(path, record, limit=(0, KEEP)):
    """追加一行 JSON；limit＝(滿幾 bytes 輪換, 留幾份)。失敗回 False（不丟例外）。

    輪換與追加都在 log/ 資料夾的 flock 裡做（usage.jsonl 可能有兩個 aos-llm call 同時寫）。
    """
    import fcntl
    lock = None
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        fcntl.flock(lock, fcntl.LOCK_EX)
        _rotate(path, *limit)
        data = (json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
        fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC, 0o644)
        try:
            end = os.lseek(fd, 0, os.SEEK_END)
            if end and os.pread(fd, 1, end - 1) != b'\n':
                data = b'\n' + data          # 上一行寫到一半（短寫、崩潰）：先換行，別把這行黏上去
            while data:
                data = data[os.write(fd, data):]
        finally:
            os.close(fd)
        return True
    except (OSError, ValueError, TypeError):
        return False
    finally:
        if lock is not None:
            os.close(lock)


def emit(base, ev, ident, **fields):
    """記一件事：{"at", "ev", "id", …}。ident 是去重用的身分（批 id、消費 id、壓縮前的 sha）。"""
    record = {'at': now_iso(), 'ev': ev, 'id': ident}
    record.update(fields)
    return append_line(Path(base) / EVENTS, record, limits(base))


def batch_id(batch):
    """一批的身分：建批時存的 batch.id；改版前的批沒有，就從工作名去掉最後的 -<序號>（都沒有＝None）。"""
    if isinstance(batch.get('id'), str):
        return batch['id']
    for call in batch['calls']:
        if call.get('name'):
            return call['name'].rsplit('-', 1)[0]
    return None


def read_all(path):
    """連輪換掉的舊檔一起讀，舊的在前（events.<N>.jsonl … events.1.jsonl、events.jsonl）。"""
    olds = []
    i = 1
    while rotated(path, i).exists() and i <= 20:
        olds.append(rotated(path, i))
        i += 1
    return [row for p in reversed(olds) for row in read(p)] + read(path)


def read(path):
    """讀 jsonl：壞行（寫到一半、手改壞）跳過；檔不在＝空。"""
    out = []
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for line in f:
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, dict):
                    out.append(value)
    except FileNotFoundError:
        pass
    return out


def dedupe(events):
    """同 ev＋id 只留第一筆（崩了重做寫的第二筆丟掉）；id 是 null 的不去重。"""
    seen, out = set(), []
    for e in events:
        key = (e.get('ev'), e.get('id'))
        if e.get('id') is not None:
            if key in seen:
                continue
            seen.add(key)
        out.append(e)
    return out


# ---- tick 的幾個點（aos_agent_batch／aos_agent_inputs 叫） --------------------

def batch_start(run):
    batch = run.st['batch']
    fields = {'base_len': batch['base_len']}
    if batch['kind'] == 'act':
        fields['tools'] = [c['tool'] for c in batch['calls']]
    emit(run.base, batch['kind'] + '_start', batch_id(batch), **fields)


def batch_end(run, messages):
    batch = run.st['batch']
    calls = batch['calls']
    if batch['kind'] == 'think':
        done = calls[0]['done']
        fields = {'ok': bool(done.get('ok')), 'ms': calls[0].get('ms')}
        if not done.get('ok'):
            fields.update(reason=done.get('fail'), count=done.get('count'))
        elif messages:
            fields['tool_calls'] = len(messages[0].get('tool_calls') or [])
    else:
        fields = {'calls': [{'tool': c['tool'], 'ok': bool(c.get('ok')), 'ms': c.get('ms')} for c in calls]}
        fields['ok'] = all(c['ok'] for c in fields['calls'])
    emit(run.base, batch['kind'] + '_end', batch_id(batch), **fields)


def intake(run, record, count):
    emit(run.base, 'intake', record['id'],
         files=[os.path.basename(p['src']) for p in record['files'] if Path(p['dst']).exists()],
         messages=count)


# ---- 人看的 aos-agent events ---------------------------------------------------

def _line(e):
    rest = {k: v for k, v in e.items() if k not in ('at', 'ev', 'id')}
    parts = ['%s=%s' % (k, v if isinstance(v, (str, int, float)) or v is None
                        else json.dumps(v, ensure_ascii=False)) for k, v in rest.items()]
    at = str(e.get('at', '?'))
    return '%s  %-12s %s  %s' % (at[:23].replace('T', ' '), e.get('ev', '?'), e.get('id') or '-',
                                ' '.join(parts))


def show(agent_dir, *, last=20, as_json=False, usage=False):
    """印最後 last 則（去重後）；usage＝改看 log/usage.jsonl。"""
    base = Path(os.path.abspath(agent_dir))
    rows = read_all(base / (USAGE if usage else EVENTS))
    if not usage:
        rows = dedupe(rows)
    rows = rows[-last:] if last else rows
    if as_json:
        print(json.dumps(rows, ensure_ascii=False))
        return 0
    if not rows:
        print('（還沒有%s）' % ('用量紀錄' if usage else '事件'))
        return 0
    for e in rows:
        if usage:
            u = e.get('usage') if isinstance(e.get('usage'), dict) else {}
            print('%s  %s  %s→%s  prompt %s  completion %s  total %s  %s ms' % (
                str(e.get('at', '?'))[:23].replace('T', ' '), e.get('batch') or '-', e.get('alias'),
                e.get('model'), u.get('prompt_tokens', '?'), u.get('completion_tokens', '?'),
                u.get('total_tokens', '?'), e.get('ms', '?')))
        else:
            print(_line(e))
    return 0
