"""POSIX execution: prepare fds, Popen fork/exec + setsid, wait, drain, fsync."""
import ctypes
import errno
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from .common import Fault, sync_dir
from .inst import validate
from .cgroup import live, process_tree


def subreaper():
    # Linux prctl(PR_SET_CHILD_SUBREAPER): adopt detached double-fork descendants.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'PR_SET_CHILD_SUBREAPER')


def signal_pids(pids, sig):
    for pid in pids:
        try:
            fd = os.pidfd_open(pid)
            try:
                signal.pidfd_send_signal(fd, sig)
            finally:
                os.close(fd)
        except ProcessLookupError:
            pass


def cleanup_children(grace=2):
    descendants = process_tree({os.getpid()}) - {os.getpid()}
    signal_pids(descendants, signal.SIGTERM)
    deadline = time.monotonic() + grace
    killed = False
    while True:
        while True:
            try:
                if os.waitpid(-1, os.WNOHANG)[0] == 0:
                    break
            except ChildProcessError:
                break
        descendants = process_tree({os.getpid()}) - {os.getpid()}
        if not descendants:
            return True
        if time.monotonic() >= deadline:
            if killed:
                return False
            signal_pids(descendants, signal.SIGKILL)
            killed, deadline = True, time.monotonic() + 2
        time.sleep(0.01)


def failed(exc, started=False):
    code = 'FinalizeFailed' if started else getattr(exc, 'code', 'ReadFailed')
    print('%s: %s' % (code, exc), file=sys.stderr)
    return {'started': started, 'exit_code': 125, 'error': {'code': code, 'message': str(exc)}}


def execute(inst, base, authorized_uid=None, stderr_override=None, timeout_ms=None,
            environment=None, pass_fds=()):
    """Used directly by tick. No UID switching; explicit inherited fds only."""
    opened = []
    started = False
    old_handlers = {}
    proc = None
    try:
        spec = validate(inst, authorized_uid)
        expected = os.getuid() if authorized_uid is None else authorized_uid
        if spec['user'] != expected or expected != os.getuid():
            raise Fault('UserNotGranted', '無 helper；執行身分必須等於授權及目前 UID')
        opts, value = spec['cwd']
        cwd = Path(base) / value if value else Path(base)
        if 'mkdir' in opts:
            cwd.mkdir(parents=True, exist_ok=True)
        if not cwd.is_dir():
            raise Fault('ReadFailed', 'cwd 不是資料夾: ' + str(cwd))
        cwd = cwd.resolve()
        opts, additions = spec['envs']
        env = {} if 'clear' in opts else dict(os.environ if environment is None else environment)
        env.update(additions)
        streams = {}
        exit_path, exit_file = None, None
        for field in ('stdin', 'stdout', 'stderr', 'exit'):
            opts, value = spec[field]
            if field == 'stderr' and stderr_override is not None:
                opts, value = set(), stderr_override
            if 'inherit' in opts:
                streams[field] = None
                continue
            if 'merge' in opts:
                streams[field] = subprocess.STDOUT
                continue
            if field == 'exit' and not value:
                continue
            path = cwd / value if value else Path('/dev/null')
            if 'mkdir' in opts:
                path.parent.mkdir(parents=True, exist_ok=True)
            # Opening exit is preflight; it stays empty on preflight failure.
            mode = 'rb' if field == 'stdin' else ('ab' if 'append' in opts else 'wb')
            stream = open(path, mode)
            opened.append(stream)
            if field == 'exit':
                exit_path, exit_file = path, stream
            else:
                streams[field] = stream
        subreaper()
        interrupted = [None]
        def interrupt(sig, frame):
            interrupted[0] = sig
            if proc is not None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for sig in (signal.SIGTERM, signal.SIGINT):
            old_handlers[sig] = signal.signal(sig, interrupt)
        started = True
        # Popen performs fork, dup2, closes all except pass_fds, setsid, execvpe.
        # No Python preexec_fn here; status-fd is NOT in pass_fds.
        try:
            proc = subprocess.Popen(spec['argv'], cwd=cwd, env=env,
                                    stdin=streams['stdin'], stdout=streams['stdout'], stderr=streams['stderr'],
                                    start_new_session=True, close_fds=True, pass_fds=pass_fds)
        except OSError as exc:
            result = 127 if exc.errno == errno.ENOENT else 126
            report = {'started': True, 'exit_code': result}
        else:
            deadline = None if timeout_ms is None else time.monotonic() + timeout_ms / 1000
            term_at = None
            while proc.poll() is None:
                now = time.monotonic()
                if term_at is None and (interrupted[0] is not None or deadline is not None and now >= deadline):
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    term_at = now
                if term_at is not None and now - term_at >= 2:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                time.sleep(0.01)
            status = proc.wait()
            report = {'started': True, 'exit_code': status if status >= 0 else 128 - status}
            if status < 0:
                report['signal'] = -status
        if not cleanup_children():
            raise Fault('FinalizeFailed', '無法清空任務後代')
        if exit_file is not None:
            exit_file.write(('%d\n' % report['exit_code']).encode())
            exit_file.flush()
            os.fsync(exit_file.fileno())
            sync_dir(exit_path.parent)
        return report
    except (Fault, OSError, ValueError) as exc:
        return failed(exc, started)
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        for stream in opened:
            stream.close()
