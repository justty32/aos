"""agent 的檔案操作；所有持久化邊界集中呼叫注入的掛鉤。"""
import os
from pathlib import Path
import sys
import tempfile
import time

import aos_client
import aos_home
from aos_agent_home import AgentError
from aos_agent_info import write_state


PAUSED = 'paused'
LOCK = '.tick.lock'
KERNEL_ENV = 'AOS_KERNEL_HOME'


def report(code, message):
    sys.stderr.write('aos-agent: %s: %s\n' % (code, ' '.join(str(message).split())))


def manual_paused(base):
    """手動暫停＝家裡有 paused 檔（aos-agent.md §1.6）；回修改時間（epoch 秒）或 None。"""
    try:
        return os.stat(Path(base) / PAUSED).st_mtime
    except OSError:
        return None


def tick_lock(base):
    """拿 <家>/.tick.lock 的非阻塞獨占 flock（aos-agent.md §2.1）。

    拿到＝寫入自己的 pid、回 fd（持到行程結束）；被佔＝回持有者 pid 字串（讀不到＝None），不動檔。
    """
    import fcntl
    fd = os.open(Path(base) / LOCK, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            try:
                holder = os.read(fd, 64).decode('ascii', 'replace').strip() or None
            except OSError:
                holder = None
            os.close(fd)
            return False, holder
        os.ftruncate(fd, 0)
        os.write(fd, b'%d\n' % os.getpid())
    except BaseException:
        # 還沒把 fd 交出去的任何失敗都在這裡關，免得同一行程下一次 tick 被自己留下的鎖擋住。
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    return True, fd


def unique_id():
    return '%d-%d' % (time.time_ns(), os.getpid())


def files(base, value):
    path = Path(os.path.abspath(os.path.join(base, value)))
    if path.is_dir():
        return [str(p) for p in sorted(path.iterdir()) if p.name.endswith('.json') and p.is_file()]
    return [str(path)] if path.exists() else []


def ledger(kernel, *, missing=False):
    path = Path(kernel) / 'state.json'
    try:
        value = aos_home.read_json(path)
    except aos_home.HomeError as exc:
        if missing and isinstance(exc.__cause__, FileNotFoundError):
            return {'procs': {}, 'replies': []}
        raise
    if (not isinstance(value, dict) or not isinstance(value.get('procs'), dict)
            or not isinstance(value.get('replies'), list)
            or any(not isinstance(r, dict) or not isinstance(r.get('name'), str)
                   for r in value['replies'])):
        raise AgentError('ReadFailed', 'K/state.json 的 procs／replies 形狀不合')
    return value


def history_prefix(history, length, messages):
    if len(history) != length and (len(history) != length + len(messages) or history[length:] != messages):
        raise AgentError('HistoryChanged', '記憶長度或當批尾巴已改變')
    return history[:length] + messages


class Runtime:
    def __init__(self, info, state, env, hook):
        self.info, self.st, self.env, self.hook = info, state, env, hook
        self.base = Path(info['dir'])

    def save(self, step):
        write_state(self.base, self.st)
        self.hook(step)

    def write(self, path, value, step):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        aos_home.write_json(path, value)
        self.hook(step)

    def text(self, path, value):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                             prefix='.', suffix='.tmp', delete=False) as out:
                temp = Path(out.name)
                out.write(value)
            os.replace(temp, path)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        self.hook('work.input')

    def move(self, pairs):
        for pair in pairs:
            src, dst = Path(pair['src']), Path(pair['dst'])
            if not dst.exists() and src.exists():
                dst.parent.mkdir(exist_ok=True)
                os.rename(src, dst)
                self.hook('consume.move')

    def submit(self, kernel, name, method, params):
        try:
            aos_client.submit(kernel, method, params, name=name)
        except aos_home.RequestExists:
            pass
        self.hook('request.post')

    def ack(self, kernel, name, index):
        aos_home.validate_name(name)
        while True:
            ack_name = 'ack-%s-%d.json' % (unique_id(), index)
            try:
                aos_home.post_request(kernel, ack_name,
                                     {'jsonrpc': '2.0', 'method': 'ack', 'params': {'name': name}})
            except aos_home.RequestExists:
                continue
            self.hook('ack.post')
            return

    def history(self, length, messages):
        value = history_prefix(self.info['history'], length, messages)
        self.write(self.info['history_path'], value, 'history.write')

    def sweep(self):
        remaining = []
        for item in self.st['sweep']:
            kernel, name = Path(item['kernel']), item['name']
            if (kernel / 'requests' / (name + '.json')).exists():
                remaining.append(item)
                continue
            try:
                state = ledger(kernel)
            except (AgentError, aos_home.HomeError):
                remaining.append(item)
                continue
            if name in state['procs']:
                remaining.append(item)
                continue
            for suffix in ('.inst.json', '.in', '.out'):
                (self.base / 'work' / (name + suffix)).unlink(missing_ok=True)
                self.hook('work.delete')
        if remaining != self.st['sweep']:
            self.st['sweep'] = remaining
            self.save('state.sweep')
