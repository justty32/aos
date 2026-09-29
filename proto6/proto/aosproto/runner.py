import argparse
import os
from pathlib import Path
from .common import Fault, encode, loads, node_id, read_inst
from .process import execute, failed


def run_snapshot(raw, target, authorized_uid, stderr=None, timeout_ms=None):
    try:
        current, _, base = read_inst(target)
        if current != raw:
            raise Fault('SourceChanged', '授權後原來源內容與快照不同')  # G-8（第十七批）
        try:
            inst = loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise Fault('JsonSyntax', str(exc))
        return execute(inst, base, authorized_uid, stderr, timeout_ms)
    except (Fault, OSError) as exc:
        report = failed(exc)
        if isinstance(exc, Fault) and exc.exit_code == 2:
            report['exit_code'] = 2
        return report


def snapshot_fd(raw):
    """memfd_create + write + reopen O_RDONLY, immutable via F_ADD_SEALS."""
    import fcntl
    fd = os.memfd_create('aos-inst', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        offset = 0
        while offset < len(raw):
            offset += os.write(fd, raw[offset:])
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW |
                    fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
        return os.open('/proc/self/fd/%d' % fd, os.O_RDONLY)
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aos-runner')
    parser.add_argument('--inst-fd', required=True, type=int)
    parser.add_argument('--status-fd', required=True, type=int)
    parser.add_argument('--target', required=True)
    parser.add_argument('--authorized-uid', required=True, type=int)
    parser.add_argument('--stderr')
    parser.add_argument('--timeout-ms', type=int)
    args = parser.parse_args(argv)
    if (not node_id(args.target) or args.authorized_uid < 0 or args.inst_fd < 0 or args.status_fd < 0
            or args.stderr is not None and not node_id(args.stderr)
            or args.timeout_ms is not None and args.timeout_ms <= 0):
        parser.error('參數格式不合法')
    try:
        with os.fdopen(args.inst_fd, 'rb') as stream:
            raw = stream.read()
        report = run_snapshot(raw, args.target, args.authorized_uid, args.stderr, args.timeout_ms)
    except OSError as exc:
        report = failed(exc)
    try:
        data = encode(report)
        while data:
            data = data[os.write(args.status_fd, data):]
        os.close(args.status_fd)
    except OSError:
        return 125
    return report['exit_code']
