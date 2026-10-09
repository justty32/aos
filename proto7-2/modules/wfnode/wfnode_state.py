"""鎖內追加 STATE 與更新 NEXT-SESSION。"""
import datetime as dt
import fcntl
import os
import re
import shlex
import sys
import tempfile


def fail(code, what, how):
    """錯誤一行：stderr 印「aos7-wfnode: 發生什麼。怎麼辦」，回傳退出碼。"""
    message = f'aos7-wfnode: {what}。{how}'
    print(message.replace('\r', '\\r').replace('\n', '\\n'), file=sys.stderr)
    return code


NEXT = '# NEXT-SESSION — 續行點\n\n下一次開場先讀最新一份 STATE；`aos7-wfnode state` 會更新本檔第一行連結\n\n（尚無）\n'
def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         delete=False) as stream:
            temp = stream.name
            stream.write(content)
        os.replace(temp, path)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def _after_open():
    """首次開檔窗口的測試 hook（呼叫時仍持有 handoffs 鎖）。"""


def show(node):
    text = (node / 'wf/handoffs/NEXT-SESSION.md').read_text(encoding='utf-8') \
        if (node / 'wf/handoffs/NEXT-SESSION.md').exists() else ''
    found = re.search(r'^> 最新：\[([^\]]+)\]', text, re.M)
    path = node / 'wf/handoffs' / found.group(1) if found else None
    if path is None or not path.is_file():
        print('還沒記過。用法：aos7-wfnode state <node> \'停在哪、下一步做什麼\'')
        return 0
    print(f'最新續行點（wf/handoffs/{found.group(1)}）：')
    print(path.read_text(encoding='utf-8'), end='')
    return 0


def state(node, line=None):
    if not (node / 'wf/tools/wf-lint.sh').is_file():
        return fail(2, f'{node} 還沒 init', f'先跑：aos7-wfnode init {shlex.quote(str(node))}')
    if line is None:
        return show(node)
    if not line.strip() or '\n' in line or '\r' in line:
        return fail(2, '進度要一行非空文字',
                    f"例：aos7-wfnode state {shlex.quote(str(node))} '寫完第一版，下一步跑測試'")
    override = os.environ.get('AOS7_WFNODE_NOW')
    try:
        if override and not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', override):
            raise ValueError('invalid timestamp')
        now = dt.datetime.fromisoformat(override) if override else dt.datetime.now()
    except ValueError:
        return fail(2, 'AOS7_WFNODE_NOW 格式不對', '用 YYYY-MM-DDTHH:MM，例：2026-10-09T15:30')
    day, time = now.strftime('%Y-%m-%d'), now.strftime('%H:%M')
    handoffs = node / 'wf/handoffs'
    handoffs.mkdir(parents=True, exist_ok=True)
    lock = os.open(handoffs / '.state.lock', os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = handoffs / day / 'STATE.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o666)
        try:
            _after_open()
            if os.fstat(fd).st_size == 0:
                os.write(fd, f'# 續行點 {day}\n\n## 進度\n'.encode('utf-8'))
            head = b'' if path.read_bytes().endswith(b'\n') else b'\n'
            os.write(fd, head + f'- {time} {line}\n'.encode('utf-8'))
        finally:
            os.close(fd)
        next_path = handoffs / 'NEXT-SESSION.md'
        text = next_path.read_text(encoding='utf-8') if next_path.exists() else NEXT
        lines = (text or NEXT).splitlines(keepends=True)
        link = f'> 最新：[{day}/STATE.md]({day}/STATE.md)\n'
        slot = next((i for i, value in enumerate(lines) if value.startswith('> 最新：')), None)
        if slot is None:
            slot = next((i for i, value in enumerate(lines) if value.strip() == '（尚無）'), None)
        if slot is not None:
            lines[slot] = link
        else:
            if not lines[0].endswith('\n'):
                lines[0] += '\n'
            lines.insert(1, link)
        atomic_write(next_path, ''.join(lines))
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        os.close(lock)
    print(f'已記到 wf/handoffs/{day}/STATE.md（AI 下次開場從這裡接）')
    return 0
