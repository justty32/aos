"""唯讀狀態、公開指令呼叫與觀看用的小函式。"""
import fcntl
import json
import os
import tempfile
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

P = Path(__file__).resolve().parents[2]


def read(path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def text(path):
    try:
        return path.read_text()
    except OSError:
        return ''


class UpError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def config(node):
    path = node / '.aos/up.json'
    if not path.exists():
        return {}
    try:
        data = read(path)
        strings = ('node', 'house', 'name', 'you', 'mail_root', 'litellm_url',
                   'budget', 'holder', 'gateway')
        if (not isinstance(data, dict) or data.get('v') != 1 or
            any(not isinstance(data.get(k), str) for k in strings) or
            'model' not in data or
            (data['model'] is not None and not isinstance(data['model'], str))):
            raise ValueError()
        return data
    except (ValueError, TypeError):
        raise UpError(2, f'{path} 壞了。刪掉它再跑 aos7-up {node}') from None


def call(path, *args, cwd=None):
    argv = ['python3', '-B', str(P / path), *map(str, args)]
    child = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = child.communicate()
        return subprocess.CompletedProcess(argv, child.returncode, out, err)
    except BaseException:
        try:
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        except ProcessLookupError:
            child.wait()
        # The leader may exit before its grandchildren: kill any remaining group.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        raise


def alive(house):
    # 不建立檔案：status 完全唯讀。
    try:
        with (house / '.aosd/daemon.lock').open('r') as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(stream, fcntl.LOCK_UN)
    except FileNotFoundError:
        pass
    return False


def number(node):
    try:
        data = read(node / '.aos/round.json', {})
        if isinstance(data, dict) and isinstance(data.get('round'), int):
            return data['round']
        daemon = read(node.parent / '.aosd/status.json', {})
        return daemon.get('nodes', {}).get(node.name, {}).get('round', 0)
    except (ValueError, OSError, AttributeError):
        return 0


def letters(box):
    result = {}
    for path in box.glob('*.md'):
        if not path.is_file():
            continue
        parts = re.split(r'^---\r?$', text(path), maxsplit=2, flags=re.M)
        fields = dict(line.split(': ', 1) for line in parts[1].strip().splitlines()
                      if ': ' in line) if len(parts) == 3 else {}
        result[path.name] = fields
    return result


def skill_count(node):
    return sum(p.is_file() for p in (node / 'skills').glob('*/SKILL.md'))


def state(node):
    pointer = node / 'wf/handoffs/NEXT-SESSION.md'
    for link in re.findall(r'\]\(([^)]+STATE\.md)\)', text(pointer)):
        lines = [s for s in text(pointer.parent / link).splitlines() if s.strip()]
        if lines:
            return lines[-1]
    return '（還沒記）'


def status(node):
    if not node.is_dir() or not (node / '.aos/up.json').is_file():
        print(f'aos7-up: 這裡還沒有 node。先跑 aos7-up {node}', file=sys.stderr)
        return 2
    settings = config(node)
    n = number(node)
    print(f'心跳：活著，第 {n} 下' if alive(node.parent) else
          f'心跳：停了（最後第 {n} 下）；起它：aos7-up {node}')
    inbox = letters(node / 'inbox')
    waiting = sum(v.get('status') == 'REQUEST' for v in inbox.values())
    print(f'信：未讀 {len(inbox)} 封（要回 {waiting} 封）；你的信箱有 '
          f'{len(letters(node.parent / "you/inbox"))} 封回信')
    count = sum(s.startswith('- ') for rel in ('SESSION-LOG.md', 'WAIT_USER.md')
                for s in text(node / 'wf' / rel).splitlines())
    check = call('modules/wfnode/aos7-wfnode', 'check', node)
    health = 'OK' if check.returncode == 0 else '有問題'
    print(f'工作簿：還有 {count} 件事沒做完；停在：{state(node)}；體檢 {health}' +
          (f'（看細節：aos7-wfnode check {node}）' if check.returncode else ''))
    print(f'技能：{skill_count(node)} 本')
    calls = sum(p.is_file() for p in (node / 'llmcall/llm').glob('*/raw.json'))
    budget = call('packs/budget/bin/aos7-budget', 'status', 'budget/llm', cwd=node)
    try:
        used = json.loads(budget.stdout).get('used', '—') if budget.returncode == 0 else '—'
    except ValueError:
        used = '—'
    print(f'AI：{settings.get("model") or "假 AI"}；問過 {calls} 次，用了 {used} token')
    print(f'檔案：{node}、{node.parent}/you（全清：先停心跳，再刪這兩個資料夾）')
    return 0


def watch(node, daemon):
    last = None
    seen = set(letters(node / 'inbox'))
    done = set(letters(node / 'inbox/done'))
    pending = []
    while True:
        incoming = letters(node / 'inbox')
        completed = letters(node / 'inbox/done')
        fresh = sum(v.get('status') == 'REQUEST' for k, v in incoming.items() if k not in seen)
        if fresh:
            pending.append(f'收到 {fresh} 封信')
        replies = {**letters(node.parent / 'you/inbox/done'), **letters(node.parent / 'you/inbox')}
        for key, value in completed.items():
            if key in done or value.get('status') != 'REQUEST':
                continue
            reply = next((r for r in replies.values() if r.get('re') == value.get('id')), {})
            outcome = reply.get('status')
            pending.append('→ 問 AI → 已回信' if outcome == 'DONE' else
                           '→ AI 沒回成，已回 BLOCKED' if outcome in ('BLOCKED', 'FAILED') else '→ 已回信')
        seen.update(incoming)
        done.update(completed)
        n = number(node)
        if n != last and n:
            print(' '.join([f'心跳 {n}', *pending]), flush=True)
            pending.clear()
            last = n
        if daemon is not None and daemon.poll() is not None:
            raise UpError(1, f'心跳沒跑起來。請看 {node.parent}/.aosd/up-daemon.log 後重跑')
        time.sleep(.2)



def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, ensure_ascii=False)
            stream.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

