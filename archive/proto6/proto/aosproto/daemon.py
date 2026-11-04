import fcntl
import hashlib
import os
import re
import selectors
import signal
import socket
import stat
import struct
import sys
import time
import uuid
from pathlib import Path
from .common import Fault, ID_RE, MAX_LINE, encode, loads, now_ms, publish_new, read_inst, uid
from .config import load_config, self_check
from .cgroup import FakeCgroup, RealCgroup, drain, old_frames
from .launch import spawn, trusted_report
from .registry import authorize, new_entry, validate_params
from .process import subreaper

METHODS = {'daemon.info', 'node.register', 'node.unregister', 'node.wake', 'node.pause',
           'node.resume', 'node.show', 'node.ls'}
REG_FIELDS = ('node_id', 'parent_id', 'identity_grant', 'owner_uid', 'once', 'registered',
              'paused', 'running', 'pending', 'stopping', 'last_tick', 'interval_ms', 'provision')


class Daemon:
    def __init__(self, config, backend):
        self.config, self.backend = config, backend
        self.boot_id = str(uuid.uuid4())
        self.registry = {}
        self.common_uid = uid(config.get('common_user'))
        self.root = None
        self.stop = False
        self.sequence = 0
        self.selector = selectors.DefaultSelector()
        self.clients = {}
        self.socket = None
        self.lock_fd = None
        self.bound = False
        self.pid_files = False
        for params in config['roots']:
            try:
                entry = new_entry(params, self.common_uid, self.registry, top=True)
            except Fault as exc:
                raise Fault('invalid_config', str(exc), 2)
            self.registry[entry['node_id']] = entry

    def initialize(self):
        path = Path(self.config['socket_path'])
        parent_existed = path.parent.exists()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        if not parent_existed:
            path.parent.chmod(0o750)
        self.lock_fd = os.open(path.parent / 'daemon.lock', os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Fault('daemon_busy', '另一個 daemon 持有 daemon.lock')
        self.root = self.backend.prepare(self.config.get('cgroup_root'), self.config.get('create_cgroup', False))
        leaf = self.root / 'daemon'
        self.backend.create(leaf)
        self.backend.move(leaf, os.getpid())
        # G-3（第十六批）＋第十七批：不管有沒有寫 cgroup_root，原層剩下的程序都搬進 daemon 葉框。
        self.backend.evacuate(self.root, leaf)
        if not drain(self.backend, old_frames(self.root), self.config.get('shutdown_grace_ms', 2000)):
            raise Fault('cleanup_failed', '舊 cgroup 無法清空')
        if path.exists() or path.is_symlink():
            if not stat.S_ISSOCK(path.lstat().st_mode):
                raise Fault('socket_failed', 'socket_path 已存在且不是 socket')
            path.unlink()
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(path))
        self.bound = True
        os.chmod(path, 0o660)
        self.socket.listen(32)
        self.socket.setblocking(False)
        self.selector.register(self.socket, selectors.EVENT_READ, None)
        state = Path(self.config['state_dir'])
        state.mkdir(parents=True, exist_ok=True)
        self.pid_files = True
        (state / 'daemon.pid').write_text(str(os.getpid()) + '\n')
        (state / 'helper.pid').write_text('none\n')
        print('helper_pid=none', flush=True)

    def frame(self, entry):
        if entry['_frame'] is None:
            parent = self.registry.get(entry['parent_id'])
            base = self.root if parent is None else self.frame(parent)
            name = ('once-' if entry['once'] else 'n-') + hashlib.sha256(entry['node_id'].encode()).hexdigest()[:16]
            entry['_frame'] = base / name
        return entry['_frame']

    def ensure_frame(self, entry):
        parent = self.registry.get(entry['parent_id'])
        if parent is not None:
            self.ensure_frame(parent)
        frame = self.frame(entry)
        self.backend.create(frame)
        leaf = frame if entry['once'] else frame / 'tick'
        self.backend.create(leaf)
        entry['_leaf'] = leaf
        return leaf

    def show(self, entry):
        result = {k: entry[k] for k in REG_FIELDS if k in entry}
        result['boot_id'] = self.boot_id
        frame = entry['_frame']
        result['cgroup'] = None
        if entry['registered'] and frame is not None:
            if not frame.is_dir():
                raise Fault('resource_observation_failed', '已配置的 cgroup 不見了')
            try:
                (frame / 'cgroup.procs').read_text()
            except OSError as exc:
                raise Fault('resource_observation_failed', str(exc))
            result['cgroup'] = {'path': str(frame), 'limits': {}}
        return result

    def issue(self, entry, message):
        self.sequence += 1
        try:
            path = Path(entry['node_id']) / '.aos/attention'
            path.mkdir(parents=True, exist_ok=True)
            publish_new(path / ('daemon-%s-%d.json' % (self.boot_id, self.sequence)),
                        {'version': 1, 'node_id': entry['node_id'], 'reason': message,
                         'last_tick': entry['last_tick']})
        except OSError as exc:
            print('warning: attention 寫入失敗: ' + str(exc), flush=True)

    def finish(self, entry, report):
        tick = entry['last_tick']
        tick['ended_at_ms'] = now_ms()
        if report is None or report.get('error', {}).get('code') == 'FinalizeFailed':
            tick.update(outcome='unknown', exit_code=None, started=True if report and report['started'] else None)
        else:
            tick.update(outcome='completed' if report['started'] else 'launch_failed',
                        exit_code=report['exit_code'], started=report['started'], signal=report.get('signal'))
        entry.update(running=False, _process=None, _due=time.monotonic() + entry.get('interval_ms', 0) / 1000)
        if entry['once']:
            if report and not report['started']:
                code = {'UserInvalid': 'user_invalid', 'UserNotGranted': 'user_not_granted',
                        'UserMismatch': 'user_mismatch', 'SourceChanged': 'source_changed'}.get(report['error']['code'], 'start_failed')
                error = {'code': -32000, 'message': report['error']['message'],
                         'data': {'code': code, 'retryable': False}}
                try:
                    publish_new(Path(entry['_source'] + '.err'),
                                {'version': 1, 'node_id': entry['node_id'], 'error': error})
                except OSError as exc:
                    print('warning: once .err 寫入失敗: ' + str(exc), flush=True)
            entry.update(registered=False, paused=False, pending=False, stopping=False)
        elif tick['outcome'] != 'completed' or tick['exit_code'] in (3, 125):
            entry['paused'] = True
            self.issue(entry, 'tick_failed')

    def start(self, entry):
        entry.update(running=True, pending=False,
                     last_tick={'started_at_ms': now_ms(), 'ended_at_ms': None, 'exit_code': None,
                                'started': None, 'signal': None, 'outcome': 'running'})
        try:
            raw, source, _ = read_inst(entry['node_id'])
            entry['_source'] = str(source)
            obj = loads(raw)
            if not isinstance(obj, dict):
                raise Fault('NotAnObject', 'inst 必須為物件')
            parent = self.registry.get(entry['parent_id'])
            if 'user' in obj and obj['user'] is None:
                raise Fault('UserInvalid', 'user 不接受 null')
            owner = uid(obj.get('user'), self.common_uid if parent is None else parent['owner_uid'])
            if owner not in entry['_grant'] or owner != self.common_uid:
                raise Fault('UserNotGranted', '無 helper 或身分超出額度')
            entry['owner_uid'] = owner
            leaf = self.ensure_frame(entry)
            if not self.backend.empty(leaf):
                raise Fault('CleanupFailed', '開格前 cgroup 並非全空')
            pid, status_fd = spawn(raw, entry['node_id'], owner, leaf, isinstance(self.backend, FakeCgroup))
            entry.update(_process=pid, _status=status_fd, _report_bytes=b'')
        except (Fault, OSError, ValueError) as exc:
            code = getattr(exc, 'code', 'ReadFailed')
            if code == 'CleanupFailed':
                entry.update(stopping=True, paused=True)
                self.issue(entry, 'cleanup_failed')
                return
            self.finish(entry, {'started': False, 'exit_code': 125,
                                'error': {'code': code, 'message': str(exc)}})

    def reap_orphans(self):
        # A dead runner's descendants become daemon children (subreaper).
        # Never steal wait status from a still-tracked runner.
        tracked = {e['_process'] for e in self.registry.values() if e['_process'] is not None}
        children_file = Path('/proc/self/task/%d/children' % os.getpid())
        for value in children_file.read_text().split():
            pid = int(value)
            if pid not in tracked:
                try:
                    os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    pass

    def poll(self):
        self.reap_orphans()
        for entry in list(self.registry.values()):
            pid = entry['_process']
            if pid is None:
                continue
            if isinstance(self.backend, FakeCgroup):
                self.backend.remember(entry['_leaf'])
            try:
                chunk = os.read(entry['_status'], MAX_LINE + 1)
                if len(entry['_report_bytes']) <= MAX_LINE:
                    entry['_report_bytes'] += chunk
            except BlockingIOError:
                pass
            done, status = os.waitpid(pid, os.WNOHANG)
            if not done:
                continue
            try:
                while True:
                    chunk = os.read(entry['_status'], MAX_LINE + 1)
                    if not chunk:
                        break
                    if len(entry['_report_bytes']) <= MAX_LINE:
                        entry['_report_bytes'] += chunk
            except BlockingIOError:
                pass
            os.close(entry['_status'])
            entry['_status'] = None
            entry['_process'] = None
            report = trusted_report(entry['_report_bytes'], status)
            leaf = entry['_leaf']
            if not self.backend.empty(leaf):
                self.backend.kill(leaf)
                if not drain(self.backend, [leaf], 0):
                    entry.update(stopping=True, paused=True)
                    self.issue(entry, 'cleanup_failed')
                    continue
            self.reap_orphans()
            self.finish(entry, report)

    def dispatch(self, peer, method, params):
        if method not in METHODS:
            raise Fault('method_not_found', '原型未實作', 1, -32601)
        validate_params(method, params)
        if method == 'daemon.info':
            return {'boot_id': self.boot_id}
        if method == 'node.ls':
            entries = [e for e in self.registry.values()
                       if authorize(peer, 'node.show', e['node_id'], self.registry)]
            entries.sort(key=lambda e: e['node_id'].encode('utf-8'))
            after = params.get('after_node_id', '').encode('utf-8')
            entries = [e for e in entries if e['node_id'].encode('utf-8') > after]
            page = entries[:params.get('limit', 64)]
            return {'boot_id': self.boot_id, 'nodes': [self.show(e) for e in page],
                    'next_after_node_id': page[-1]['node_id'] if len(entries) > len(page) else None}
        node = params['node_id']
        entry = self.registry.get(node)
        target = params['parent_id'] if method == 'node.register' and entry is None else node
        if target not in self.registry:
            raise Fault('not_registered', '目標或父 node 未登記')
        if not authorize(peer, method, target, self.registry):
            raise Fault('forbidden', 'peer UID 不是 owner 或祖先 owner')
        if method == 'node.register':
            if entry is not None:
                keys = ('node_id', 'parent_id', 'identity_grant', 'interval_ms', 'once', 'provision')
                same = all(entry.get(k, False if k == 'once' else None) ==
                           params.get(k, False if k == 'once' else None) for k in keys)
                if not entry['registered'] or not same:
                    raise Fault('registration_conflict', '登記不同或 once 已解除，不盲目重跑')
            else:
                entry = new_entry(params, self.common_uid, self.registry)
                self.registry[node] = entry
            return {'node_id': node}
        if method == 'node.show':
            return self.show(entry)
        if not entry['registered']:
            raise Fault('not_registered', 'once 已解除')
        if entry['stopping']:
            raise Fault('stopping', 'node 正在停止')
        if method == 'node.wake':
            if not entry['once'] or not entry['running']:
                entry['pending'] = True
        elif method == 'node.pause':
            entry['paused'] = True
        elif method == 'node.resume':
            entry['paused'] = False
        elif method == 'node.unregister':
            descendants = {node}
            while True:
                more = {k for k, v in self.registry.items() if v['parent_id'] in descendants}
                if more <= descendants:
                    break
                descendants |= more
            for key in descendants:
                self.registry[key]['stopping'] = True
            paths = [self.registry[k]['_frame'] for k in descendants if self.registry[k]['_frame'] is not None]
            if not drain(self.backend, paths, self.config.get('shutdown_grace_ms', 2000), self.poll):
                raise Fault('cleanup_failed', '解除前無法清空子樹')
            self.poll()
            for key in descendants:
                del self.registry[key]
        return {'node_id': node}

    def response(self, raw, peer):
        request_id = None
        try:
            try:
                request = loads(raw)
            except (ValueError, UnicodeError) as exc:
                raise Fault('parse_error', str(exc), 1, -32700)
            if isinstance(request, dict) and isinstance(request.get('id'), str) and ID_RE.fullmatch(request['id']):
                request_id = request['id']
            if (not isinstance(request, dict) or set(request) != {'jsonrpc', 'id', 'method', 'params'}
                    or request.get('jsonrpc') != '2.0' or request_id is None
                    or not isinstance(request.get('method'), str) or not isinstance(request.get('params'), dict)
                    or not re.fullmatch(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:_[a-z0-9]+)*)+', request['method'])):
                raise Fault('invalid_request', '需要完整 JSON-RPC 請求與字串 ID', 1, -32600)
            result = self.dispatch(peer, request['method'], request['params'])
            response = {'jsonrpc': '2.0', 'id': request_id, 'result': result}
        except Fault as exc:
            response = rpc_error(request_id, exc.code, str(exc), exc.rpc_code)
        except (OSError, ValueError) as exc:
            response = rpc_error(request_id, 'internal_error', str(exc), -32603)
        data = encode(response)
        if len(data) > MAX_LINE and 'result' in response and 'nodes' in response['result']:
            page = response['result']
            while len(data) > MAX_LINE and len(page['nodes']) > 1:
                page['nodes'].pop()
                page['next_after_node_id'] = page['nodes'][-1]['node_id']
                data = encode(response)
        if len(data) > MAX_LINE:
            data = encode(rpc_error(request_id, 'response_too_large', '查詢結果超過單行上限'))
        return data

    def close_client(self, connection):
        self.selector.unregister(connection)
        self.clients.pop(connection, None)
        connection.close()

    def fill_output(self, state):
        while b'\n' in state['input'] and len(state['output']) < MAX_LINE:
            raw, state['input'] = state['input'].split(b'\n', 1)
            if len(raw) + 1 > MAX_LINE:
                state['output'] += encode(rpc_error(None, 'invalid_request', '單行超長', -32600))
                state['close'], state['input'] = True, b''
                break
            state['output'] += self.response(raw, state['peer'])
        if len(state['input']) >= MAX_LINE and b'\n' not in state['input']:
            state['output'] += encode(rpc_error(None, 'invalid_request', '單行超長', -32600))
            state['close'], state['input'] = True, b''

    def io(self, key, mask):
        connection = key.fileobj
        if connection is self.socket:
            connection, _ = self.socket.accept()
            connection.setblocking(False)
            _, peer, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            self.clients[connection] = {'peer': peer, 'input': b'', 'output': b'', 'close': False}
            self.selector.register(connection, selectors.EVENT_READ, True)
            return
        state = self.clients[connection]
        try:
            if mask & selectors.EVENT_READ:
                chunk = connection.recv(16384)
                if not chunk:
                    self.close_client(connection)
                    return
                state['input'] += chunk
                self.fill_output(state)
            if mask & selectors.EVENT_WRITE and state['output']:
                count = connection.send(state['output'])
                state['output'] = state['output'][count:]
                self.fill_output(state)
            if state['close'] and not state['output']:
                self.close_client(connection)
            else:
                events = selectors.EVENT_WRITE if state['output'] else selectors.EVENT_READ
                self.selector.modify(connection, events, True)
        except BlockingIOError:
            return
        except (BrokenPipeError, ConnectionResetError):
            self.close_client(connection)

    def loop(self):
        while not self.stop:
            self.poll()
            for entry in list(self.registry.values()):
                if (entry['registered'] and not entry['paused'] and not entry['running'] and not entry['stopping']
                        and (entry['pending'] or 'interval_ms' in entry and time.monotonic() >= entry['_due'])):
                    self.start(entry)
            for key, mask in self.selector.select(0.01):
                self.io(key, mask)

    def shutdown(self):
        for entry in self.registry.values():
            entry['stopping'] = True
        paths = [e['_leaf'] for e in self.registry.values() if e['_leaf'] is not None]
        return drain(self.backend, paths, self.config.get('shutdown_grace_ms', 2000), self.poll)

    def close(self):
        for connection in list(self.clients):
            self.close_client(connection)
        self.selector.close()
        if self.socket:
            self.socket.close()
        if self.bound:
            Path(self.config['socket_path']).unlink(missing_ok=True)
        if self.pid_files:
            for name in ('daemon.pid', 'helper.pid'):
                (Path(self.config['state_dir']) / name).unlink(missing_ok=True)
        if self.lock_fd is not None:
            os.close(self.lock_fd)


def rpc_error(request_id, code, message, number=-32000):
    return {'jsonrpc': '2.0', 'id': request_id,
            'error': {'code': number, 'message': message, 'data': {'code': code, 'retryable': code == 'busy'}}}


def run(config_path, create=False, fake=None):
    daemon = None
    handlers = {}
    result = 0
    try:
        config = load_config(config_path, create)
        self_check(fake is not None)
        backend = FakeCgroup(fake) if fake else RealCgroup()
        daemon = Daemon(config, backend)
        subreaper()
        def stop(sig, frame):
            daemon.stop = True
        for sig in (signal.SIGTERM, signal.SIGINT):
            handlers[sig] = signal.signal(sig, stop)
        daemon.initialize()
        daemon.loop()
    except (Fault, OSError) as exc:
        print('%s: %s' % (getattr(exc, 'code', 'daemon_failed'), exc), file=sys.stderr)
        result = getattr(exc, 'exit_code', 125)
    finally:
        if daemon is not None:
            try:
                if not daemon.shutdown():
                    print('cleanup_failed: 停機無法清空程序', file=sys.stderr)
                    result = 125
            except (OSError, Fault) as exc:
                print('cleanup_failed: ' + str(exc), file=sys.stderr)
                result = 125
            finally:
                daemon.close()
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    return result
