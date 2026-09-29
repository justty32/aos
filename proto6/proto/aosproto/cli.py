import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from .common import Fault, MAX_LINE, encode, loads, read_inst, read_json
from .config import load_config
from .runner import snapshot_fd
from .tick import git, tasks_validate

BIN = Path(__file__).resolve().parents[1] / 'bin'
ALIASES = {'ls', 'show', 'new', 'register', 'unregister', 'wake', 'pause', 'resume', 'tick'}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Fault('invalid_arguments', '原型未實作或參數不合法: ' + message, 2)


def rpc(path, method, params):
    request = {'jsonrpc': '2.0', 'id': 'cli1', 'method': method, 'params': params}
    data = encode(request)
    if len(data) > MAX_LINE:
        raise Fault('invalid_arguments', '請求過長', 2)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(10)
        try:
            client.connect(path)
        except OSError as exc:
            raise Fault('connection_failed', str(exc), 125)
        try:
            client.sendall(data)
            with client.makefile('rb') as stream:
                raw = stream.readline(MAX_LINE + 1)
            if not raw.endswith(b'\n') or len(raw) > MAX_LINE:
                raise ValueError('未取得完整有界回應')
            result = loads(raw)
            if (not isinstance(result, dict) or result.get('jsonrpc') != '2.0' or result.get('id') != 'cli1'
                    or ('result' in result) == ('error' in result)):
                raise ValueError('回應格式不合法')
            return result
        except (OSError, ValueError) as exc:
            raise Fault('result_unknown', str(exc), 1)


def checked(response, json_output=False):
    if json_output:
        sys.stdout.write(encode(response).decode())
    if 'error' in response:
        error = response['error']
        raise Fault(error['data']['code'], error['message'], 1)
    return response['result']


def confirm(yes):
    if yes:
        return
    if not sys.stdin.isatty():
        raise Fault('confirmation_required', 'stdin 不是 tty；請明示 --yes', 125)
    print('確認執行？[y/n] ', end='', file=sys.stderr, flush=True)
    if sys.stdin.readline().strip().lower() not in ('y', 'yes'):
        raise Fault('not_confirmed', '未確認', 125)


def create_node(target, task_file=None):
    node = Path(os.path.abspath(target))
    if node.exists():
        raise Fault('invalid_target', '目標已存在', 2)
    try:
        obj = read_json(task_file) if task_file else {'_metainfo': {'_type': 'aos-tasks', '_version': 1}, 'tasks': []}
        tasks = tasks_validate(obj)
    except (ValueError, OSError, Fault) as exc:
        raise Fault('invalid_tasks', str(exc), 2)
    try:
        node.mkdir(parents=True)
        (node / '.aos').mkdir()
        (node / '.aos/inst.json').write_bytes(encode({'argv': ['aos-tick']}))
        (node / '.aos/tasks.json').write_bytes(Path(task_file).read_bytes() if task_file else encode(obj))
        (node / '.gitignore').write_text('/requests/\n/responses/\n/work/\n/.aos/jobs/\n/.aos/attention/\n'
                                       '/.aos/alarms/\n/.aos/summary/published.json\n/.aos/runner-stderr.log\n')
        git(node, 'init', '-q')
        git(node, 'add', '-A')
        git(node, '-c', 'core.hooksPath=/dev/null', 'commit', '-q', '--no-verify', '-m', 'aos node initial')
        oid = git(node, 'rev-parse', 'HEAD').stdout.strip()
    except OSError as exc:
        raise Fault('create_failed', str(exc), 1)
    print('created %s; initial_commit=%s; tasks=%d' % (target, oid, len(tasks)))
    return 0


def run_inst(args):
    target = os.path.abspath(args.target)
    raw, _, _ = read_inst(target)
    if args.timeout_ms is not None and args.timeout_ms <= 0:
        raise Fault('invalid_arguments', 'timeout-ms 必須為正整數', 2)
    if args.json:
        try:
            inst = loads(raw)
            from .inst import validate
            try:
                spec = validate(inst, os.getuid())
            except Fault:
                spec = None  # Invalid inst belongs to runner's 125 report.
            if spec is not None and 'inherit' in spec['stdout'][0]:
                raise Fault('invalid_arguments', '--json 不能與 inherit stdout 混流', 2)
        except ValueError:
            pass  # Runner reports JsonSyntax through its status pipe.
    snapshot = snapshot_fd(raw)
    read_fd, status_fd = os.pipe()
    command = [str(BIN / 'aos-runner'), '--inst-fd', str(snapshot), '--target', target,
               '--authorized-uid', str(os.getuid()), '--status-fd', str(status_fd)]
    if args.stderr:
        command += ['--stderr', os.path.abspath(args.stderr)]
    if args.timeout_ms is not None:
        command += ['--timeout-ms', str(args.timeout_ms)]
    try:
        proc = subprocess.Popen(command, pass_fds=(snapshot, status_fd))
    finally:
        os.close(snapshot)
        os.close(status_fd)
    with os.fdopen(read_fd, 'rb') as stream:
        raw_report = stream.readline(MAX_LINE + 1)
    result = proc.wait()
    if args.json and raw_report:
        sys.stdout.buffer.write(raw_report)
        sys.stdout.flush()
    return result if result >= 0 else 128 - result


def human(entry):
    tick = entry['last_tick']
    state = ('未啟動' if tick is None else {'running': '還在跑', 'unknown': '結果不明',
             'completed': '已完成', 'launch_failed': '啟動失敗'}[tick['outcome']])
    if not entry['registered']:
        state = '已解除 once；' + state
    print('%s: %s; registered=%s paused=%s running=%s pending=%s; owner_uid=%s parent=%s; cgroup=%s; last_tick=%s'
          % (entry['node_id'], state, str(entry['registered']).lower(), str(entry['paused']).lower(),
             str(entry['running']).lower(), str(entry['pending']).lower(), entry['owner_uid'],
             entry['parent_id'], entry['cgroup'], tick))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv and argv[0] in ALIASES:
            argv.insert(0, 'node')
        if argv and argv[0] == 'run':
            argv[:1] = ['inst', 'run']
        if argv and argv[0] == 'daemon' and (len(argv) == 1 or argv[1].startswith('-')):
            argv.insert(1, 'start')
        if len(argv) < 2:
            raise Fault('invalid_arguments', '原型未實作；請指定 daemon/node/inst 動作', 2)
        family, action = argv[:2]
        parser = Parser(prog='aos ' + family + ' ' + action)
        if (family, action) == ('daemon', 'start'):
            parser.add_argument('--config', required=True)
            parser.add_argument('--create-cgroup', action='store_true')
            parser.add_argument('--x-fake-cgroup', help=argparse.SUPPRESS)
            args = parser.parse_args(argv[2:])
            from .daemon import run
            return run(args.config, args.create_cgroup, args.x_fake_cgroup)
        if (family, action) == ('node', 'new'):
            parser.add_argument('target')
            parser.add_argument('--tasks')
            args = parser.parse_args(argv[2:])
            return create_node(args.target, args.tasks)
        if (family, action) == ('node', 'tick'):
            parser.add_argument('target')
            args = parser.parse_args(argv[2:])
            os.execv(str(BIN / 'aos-tick'), [str(BIN / 'aos-tick'), '--node', os.path.abspath(args.target)])
        if (family, action) == ('inst', 'run'):
            parser.add_argument('target', nargs='?', default='.')
            parser.add_argument('--timeout-ms', type=int)
            parser.add_argument('--stderr')
            parser.add_argument('--json', action='store_true')
            return run_inst(parser.parse_args(argv[2:]))
        if not (family == 'daemon' and action == 'info' or family == 'node' and action in
                ('register', 'unregister', 'wake', 'pause', 'resume', 'show', 'ls')):
            raise Fault('not_implemented', '原型未實作', 2)
        connection = parser.add_mutually_exclusive_group(required=True)
        connection.add_argument('--socket')
        connection.add_argument('--daemon-config')
        parser.add_argument('--json', action='store_true')
        if family == 'node' and action != 'ls':
            parser.add_argument('target')
        if action == 'ls':
            parser.add_argument('--node', nargs='+', action='append', default=[])
        if action in ('register', 'unregister', 'resume'):
            parser.add_argument('--yes', action='store_true')
        if action == 'register':
            parser.add_argument('--parent', required=True)
            parser.add_argument('--identity-grant', required=True)
            period = parser.add_mutually_exclusive_group()
            period.add_argument('--interval-ms', type=int)
            period.add_argument('--once', action='store_true')
        args = parser.parse_args(argv[2:])
        path = os.path.abspath(args.socket) if args.socket else load_config(args.daemon_config)['socket_path']
        params = {}
        if family == 'node' and action != 'ls':
            params['node_id'] = os.path.abspath(args.target)
        if action == 'register':
            try:
                grant = read_json(args.identity_grant)
            except (OSError, ValueError) as exc:
                raise Fault('invalid_arguments', str(exc), 2)
            params.update(parent_id=os.path.abspath(args.parent), identity_grant=grant)
            if args.once:
                params['once'] = True
            if args.interval_ms is not None:
                params['interval_ms'] = args.interval_ms
            from .registry import validate_params
            validate_params('node.register', params)
        if action in ('unregister', 'resume'):
            confirm(args.yes)
        if action == 'ls':
            selected = [n for group in args.node for n in group]
            if selected:
                failures = 0
                for target in selected:
                    response = rpc(path, 'node.show', {'node_id': os.path.abspath(target)})
                    try:
                        result = checked(response, args.json)
                        if not args.json:
                            human(result)
                    except Fault as exc:
                        print(exc.code + ': ' + str(exc), file=sys.stderr)
                        failures = 1
                return failures
            boot = None
            while True:
                response = rpc(path, 'node.ls', params)
                result = checked(response, args.json)
                if boot is not None and boot != result['boot_id']:
                    raise Fault('daemon_restarted', '分頁期間 daemon 重開，請重列', 1)
                boot = result['boot_id']
                if not args.json:
                    for entry in result['nodes']:
                        human(entry)
                if result['next_after_node_id'] is None:
                    return 0
                params['after_node_id'] = result['next_after_node_id']
        response = rpc(path, family + '.' + action, params)
        result = checked(response, args.json and action != 'pause')
        if action == 'pause':
            while True:
                response = rpc(path, 'node.show', params)
                result = checked(response)
                if not result['running']:
                    if args.json:
                        checked(response, True)
                    break
                time.sleep(0.025)
        if not args.json:
            if action == 'show':
                human(result)
            elif action == 'info':
                print('boot_id=' + result['boot_id'])
            else:
                formats = {'register': 'registered %s (not woken)', 'unregister': 'unregistered %s',
                           'wake': 'wake accepted %s', 'pause': 'paused %s; running=false',
                           'resume': 'resume accepted %s'}
                print(formats[action] % args.target)
        return 0
    except Fault as exc:
        print(exc.code + ': ' + str(exc), file=sys.stderr)
        return exc.exit_code
    except (OSError, ValueError) as exc:
        print('precondition_failed: ' + str(exc), file=sys.stderr)
        return 125
    except KeyboardInterrupt:
        return 130
