import os
import signal
import time
from pathlib import Path
from .common import Fault, within


def live(pid):
    try:
        os.kill(pid, 0)
        # Zombies cannot execute; parent still owns responsibility for wait().
        return Path('/proc/%d/stat' % pid).read_text().rsplit(')', 1)[1].split()[0] != 'Z'
    except (ProcessLookupError, FileNotFoundError):
        return False
    except PermissionError:
        return True


def process_tree(seeds):
    parents = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            values = path.read_text().rsplit(')', 1)[1].split()
            parents[int(path.parent.name)] = int(values[1])
        except (OSError, ValueError):
            continue
    result = set(seeds)
    while True:
        children = {pid for pid, parent in parents.items() if parent in result}
        if children <= result:
            return result
        result.update(children)


class RealCgroup:
    def __init__(self, mount=None, own=None):
        if mount is None:
            with open('/proc/self/mounts') as stream:
                mount = next((line.split()[1].replace('\\040', ' ') for line in stream
                              if line.split()[2] == 'cgroup2'), None)
            if mount is None:
                raise Fault('cgroup_unavailable', '找不到 cgroup v2')
        self.mount = Path(mount)
        if own is None:
            with open('/proc/self/cgroup') as stream:
                group = next(line.strip()[3:] for line in stream if line.startswith('0::'))
            own = self.mount / group.lstrip('/')
        self.own = Path(own)

    def create(self, path):
        Path(path).mkdir(parents=True, exist_ok=True)

    def move(self, path, pid):
        (Path(path) / 'cgroup.procs').write_text(str(pid) + '\n')
        if pid == os.getpid():
            self.own = Path(path)

    def pids(self, path):
        result = set()
        for directory, _, _ in os.walk(path):
            try:
                result.update(int(p) for p in (Path(directory) / 'cgroup.procs').read_text().split())
            except FileNotFoundError:
                continue
        return result

    def direct_pids(self, path):
        try:
            return {int(p) for p in (Path(path) / 'cgroup.procs').read_text().split()}
        except FileNotFoundError:
            return set()

    def evacuate(self, root, leaf):
        """G-3（第十六批）：省略 cgroup_root 時，原層剩下的程序也搬進 daemon 葉框，原層只當分支。"""
        for _ in range(5):
            left = self.direct_pids(root)
            if not left:
                return
            for pid in left:
                try:
                    self.move(leaf, pid)
                except ProcessLookupError:
                    pass
                except OSError as exc:
                    raise Fault('cgroup_unavailable', '無法把原層程序搬進 daemon 葉框: ' + str(exc))
        raise Fault('cgroup_unavailable', '原 cgroup 層一直有新程序，無法只當分支')

    def empty(self, path):
        events = Path(path) / 'cgroup.events'
        if not Path(path).exists():
            return True
        return 'populated 0' in events.read_text().splitlines()

    def terminate(self, path):
        # pidfd prevents signalling a reused PID between observation and kill.
        for pid in self.pids(path):
            try:
                fd = os.pidfd_open(pid)
                try:
                    if pid in self.pids(path):
                        signal.pidfd_send_signal(fd, signal.SIGTERM)
                finally:
                    os.close(fd)
            except ProcessLookupError:
                pass

    def kill(self, path):
        (Path(path) / 'cgroup.kill').write_text('1\n')

    def prepare(self, root=None, create=False):
        root = Path(root) if root is not None else self.own
        try:
            if not within(root.resolve(), self.mount.resolve()):
                raise OSError('cgroup_root 不在 cgroup2 掛載點內')
            if not root.exists():
                if not create:
                    raise OSError('cgroup 子樹不存在且未開 create')
                self.create(root)
            if not within(self.own.resolve(), root.resolve()):
                if not create:
                    raise OSError('daemon 不在此子樹內；cgroup v2 搬移需對共同上層有寫權')
                try:
                    self.move(root, os.getpid())
                except OSError as exc:
                    raise OSError('cgroup v2 搬移需對共同上層有寫權: ' + str(exc))
            for item in [root] + [root / name for name in
                                     ('cgroup.procs', 'cgroup.subtree_control', 'cgroup.threads')]:
                if not item.exists() or not os.access(item, os.W_OK):
                    raise OSError('委派檔或資料夾不可寫: ' + str(item))
            return root
        except OSError as exc:
            raise Fault('cgroup_unavailable', str(exc))


class FakeCgroup(RealCgroup):
    def __init__(self, mount, own=None):
        super().__init__(mount, mount if own is None else own)

    def create(self, path):
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        for name in ('cgroup.procs', 'cgroup.subtree_control', 'cgroup.threads', 'cgroup.kill'):
            (path / name).touch(exist_ok=True)

    def move(self, path, pid):
        with (Path(path) / 'cgroup.procs').open('a') as stream:
            stream.write(str(pid) + '\n')
        if pid == os.getpid():
            self.own = Path(path)

    def direct_pids(self, path):
        return {pid for pid in super().direct_pids(path) if live(pid)}

    def evacuate(self, root, leaf):
        # 假後端沒有核心的「一個程序只在一個框」語意：搬完手動從原層清掉。
        for pid in self.direct_pids(root):
            self.move(leaf, pid)
        (Path(root) / 'cgroup.procs').write_text('')

    def pids(self, path):
        roots = super().pids(path)
        return {pid for pid in process_tree({p for p in roots if live(p)}) if live(pid)}

    def remember(self, path):
        known = super().pids(path)
        extra = self.pids(path) - known
        if extra:
            with (Path(path) / 'cgroup.procs').open('a') as stream:
                for pid in extra:
                    stream.write(str(pid) + '\n')

    def empty(self, path):
        return not self.pids(path)

    def kill(self, path):
        (Path(path) / 'cgroup.kill').write_text('1\n')
        for pid in self.pids(path):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def drain(backend, paths, grace_ms, reap=None):
    paths = [Path(p) for p in paths if Path(p).exists()]
    for path in paths:
        if not backend.empty(path):
            backend.terminate(path)
    deadline = time.monotonic() + grace_ms / 1000
    while True:
        if reap:
            reap()
        if all(backend.empty(p) for p in paths):
            return True
        if time.monotonic() >= deadline:
            break
        time.sleep(0.01)
    for path in paths:
        if not backend.empty(path):
            backend.kill(path)
    deadline = time.monotonic() + 3
    while True:
        if reap:
            reap()
        if all(backend.empty(p) for p in paths):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.01)


def old_frames(root):
    return [p for p in Path(root).iterdir() if p.is_dir() and
            (p.name.startswith(('n-', 'once-')) or p.name == 'tick')]
