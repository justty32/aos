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
RESUMED = 'resumed'  # fix-r5：continue 解了連敗暫停、還沒等到一次成功（aos-agent.md §1.4）
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


def resumed_since(base):
    """continue 放的 resumed 檔的修改時間（epoch 秒）或 None（aos-agent.md §1.4）。"""
    try:
        return os.stat(Path(base) / RESUMED).st_mtime
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


def kernel_proc(kernel, name):
    """查一筆行程（one-boot：K/ledger.sqlite，aos-kernel proc 同一支 lib）：回 None 或 {name, proc, cpu, discard}。
    沒 boot 過回 None；帳本還是舊的 state.json、讀不懂＝HomeError（LedgerVersion／ReadFailed）。"""
    import aos_kernel_store
    found = aos_kernel_store.proc(kernel, name)
    if found is not None and not isinstance(found['proc'], dict):
        raise AgentError('ReadFailed', 'K 帳本裡 %s 的行程資料形狀不合' % name)
    return found


def kernel_knows(kernel, name):
    """kernel 還記得這張單嗎（帳本有這個行程，或出貨箱裡有它的回音）。"""
    import aos_kernel_store
    return aos_kernel_store.knows(kernel, name)


def kernel_procs(kernel):
    """{名: 行程紀錄}：要掃全部的才用（continue --all）。"""
    import aos_kernel_store
    return aos_kernel_store.procs(kernel)


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
                import aos_kernel_store
                # 沒 boot 過（沒帳本）就先留著，跟以前「帳本讀不到就留」一樣。
                known = not aos_kernel_store.exists(kernel) or kernel_proc(kernel, name) is not None
            except (AgentError, aos_home.HomeError, ValueError):
                remaining.append(item)
                continue
            if known:
                remaining.append(item)
                continue
            for suffix in ('.inst.json', '.in', '.out'):
                (self.base / 'work' / (name + suffix)).unlink(missing_ok=True)
                self.hook('work.delete')
        if remaining != self.st['sweep']:
            self.st['sweep'] = remaining
            self.save('state.sweep')
