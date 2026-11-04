"""Daemon's explicit fork/exec boundary and trusted runner report validation."""
import os
import re
from pathlib import Path
from .common import encode, integer, loads
from .runner import snapshot_fd

RUNNER = str(Path(__file__).resolve().parents[1] / 'bin/aos-runner')


def spawn(raw, target, owner_uid, leaf, fake=False):
    snapshot = snapshot_fd(raw)
    read_fd, status_fd = os.pipe2(os.O_CLOEXEC)
    cg_fd = null_fd = diag_fd = None
    try:
        os.set_blocking(read_fd, False)
        cg_fd = os.open(Path(leaf) / 'cgroup.procs', os.O_WRONLY | (os.O_APPEND if fake else 0))
        null_fd = os.open('/dev/null', os.O_RDWR)
        if Path(target).is_dir():
            diagnostic = Path(target) / '.aos/runner-stderr.log'
            diagnostic.parent.mkdir(exist_ok=True)
            diag_fd = os.open(diagnostic, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        else:
            diag_fd = os.dup(null_fd)
        argv = [RUNNER, '--inst-fd', str(snapshot), '--target', target,
                '--authorized-uid', str(owner_uid), '--status-fd', str(status_fd)]
        # Enumerate before fork. No threads exist in this process.
        close_fds = [int(p.name) for p in Path('/proc/self/fd').iterdir()
                     if p.name.isdigit() and int(p.name) > 2 and int(p.name) not in (snapshot, status_fd)]
        pid = os.fork()
        if pid == 0:
            try:
                # Move BEFORE exec: all runner descendants inherit the cgroup.
                os.write(cg_fd, ('%d\n' % os.getpid()).encode())
                os.dup2(null_fd, 0)
                os.dup2(null_fd, 1)
                os.dup2(diag_fd, 2)
                os.set_inheritable(snapshot, True)
                os.set_inheritable(status_fd, True)
                for fd in close_fds:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                os.execv(RUNNER, argv)
            except BaseException as exc:
                try:
                    os.write(status_fd, encode({'started': False, 'exit_code': 125,
                             'error': {'code': 'ReadFailed', 'message': str(exc)}}))
                finally:
                    os._exit(125)
        return pid, read_fd
    except BaseException:
        os.close(read_fd)
        raise
    finally:
        for fd in (snapshot, status_fd, cg_fd, null_fd, diag_fd):
            if fd is not None:
                os.close(fd)


def trusted_report(raw, wait_code):
    try:
        if not raw.endswith(b'\n') or raw.count(b'\n') != 1:
            return None
        report = loads(raw)
        if not isinstance(report, dict) or set(report) - {'started', 'exit_code', 'error', 'signal'}:
            return None
        if type(report.get('started')) is not bool or not integer(report.get('exit_code'), 0, 255):
            return None
        if not os.WIFEXITED(wait_code) or os.WEXITSTATUS(wait_code) != report['exit_code']:
            return None
        error = report.get('error')
        if error is not None:
            if (not isinstance(error, dict) or set(error) != {'code', 'message'} or
                    not isinstance(error['code'], str) or not re.fullmatch('[A-Z][A-Za-z0-9]*', error['code']) or
                    not isinstance(error['message'], str)):
                return None
        if not report['started']:
            if report['exit_code'] not in (2, 125) or error is None or 'signal' in report:
                return None
        elif error is not None:
            if error['code'] != 'FinalizeFailed' or report['exit_code'] != 125 or 'signal' in report:
                return None
        if 'signal' in report and (not integer(report['signal'], 1, 64) or
                                    report['exit_code'] != 128 + report['signal']):
            return None
        return report
    except (ValueError, UnicodeError, TypeError):
        return None
