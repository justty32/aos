#!/usr/bin/env python3
"""aos-agent tick／start／stop／last；按規範持久化，再執行可重做的副作用。"""
import argparse
import os
from pathlib import Path

import aos_agent_info
import aos_client
import aos_home
from aos_agent_batch import META, collect, make_batch, send
from aos_agent_home import AgentError, resolve_field
from aos_agent_inputs import finish_consuming, gate, intake
from aos_agent_runtime import Runtime, report, unique_id
from aos_directives import Context, Document, is_directive

WAIT_TIMEOUT_MS = 10000


def _hook(step_name):
    """持久化完成後的單一測試掛鉤；正式執行時不做任何事。"""


def _environment(env):
    env = os.environ if env is None else env
    kernel = env.get('AOS_K')
    if not isinstance(kernel, str) or not os.path.isabs(kernel):
        raise AgentError('Usage', 'AOS_K 必須設成 kernel 家的絕對路徑')
    return env, kernel


def _error(exc):
    code = 'io' if isinstance(exc, OSError) or getattr(exc, 'code', '') == 'WriteFailed' else exc.code
    report(code, getattr(exc, 'msg', str(exc)))
    return 2 if code == 'Usage' else 1


def tick(agent_dir, env=None):
    try:
        env, kernel = _environment(env)
        # 此段讀驗全部完成前不建立 work，不做任何寫入。
        info = aos_agent_info.load(agent_dir, env=env)
        st = aos_agent_info.load_state(agent_dir, env=env)
        run = Runtime(info, st, env, _hook)
        finish_consuming(run)
        run.sweep()
        if not gate(run):
            return 101
        if st['batch'] is not None:
            return collect(run)
        if st['state'] == 'idle':
            return intake(run)
        history = info['history']
        if st['state'] == 'act' and not (history and history[-1]['role'] == 'assistant'
                                        and history[-1].get('tool_calls')):
            st['state'] = 'think'
            run.save('state.act_empty')
            return 0
        make_batch(run, kernel)
        return send(run)
    except (AgentError, aos_home.HomeError, OSError) as exc:
        return _error(exc)


def _compatible(kernel, env):
    path = Path(kernel) / 'info.json'
    try:
        raw = aos_home.read_json(path)
    except aos_home.HomeError as exc:
        raise AgentError('NotAHome', exc.msg) from exc
    if not isinstance(raw, dict) or is_directive(raw):
        raise AgentError('NotAHome', 'K/info.json 頂層必須是字面物件')
    doc = Document(path, raw)
    ctx = Context(doc, base_dir=kernel, env=env)
    values = {}
    for key, default in [('done_exit', 100), ('bad_after', 10)]:
        value = resolve_field(doc, ctx, [key]) if key in raw else default
        if type(value) is not int or value < 0 or (key == 'done_exit' and value > 255):
            raise AgentError('FieldTypeMismatch', '%s 必須是規定範圍的整數' % key)
        values[key] = value
    if values['done_exit'] in (1, 101):
        raise AgentError('KernelIncompatible', 'kernel 的 done_exit 與 agent 退出碼衝突')


def _tick_inst(run, kernel):
    path = run.base / 'tick.json'
    if path.exists():
        try:
            raw = aos_home.read_json(path)
            value = raw.get('envs', {}).get('AOS_K') if isinstance(raw, dict) else None
        except (aos_home.HomeError, AttributeError):
            value = None
        if not isinstance(value, str) or value != kernel:
            raise AgentError('KernelMismatch', 'tick.json 綁在另一個 K，要換就刪掉 tick.json 再 start')
    else:
        run.write(path, {'_metainfo': dict(META), 'argv': ['aos-agent', 'tick', str(run.base)],
                         'cwd': str(run.base), 'envs': {'AOS_K': kernel},
                         'stderr': {'$opt': ['append', 'mkdir'],
                                    '$val': str(run.base / 'log' / 'agent.err')}}, 'tick.inst')
    return str(path)


def _register(agent_dir, env, starting):
    try:
        env = os.environ if env is None else env
        if not starting and not env.get('AOS_K'):
            from aos_agent_status import tick_kernel
            bound = tick_kernel(agent_dir)
            if bound is None:
                raise AgentError('Usage', '沒設 AOS_K，tick.json 也沒記')
            env = dict(env, AOS_K=bound)
        env, kernel = _environment(env)
        if starting:
            info = aos_agent_info.load(agent_dir, env=env)
        else:
            base = Path(os.path.abspath(agent_dir))
            if not base.is_dir():
                raise AgentError('NotAnAgent', '%s 不是存在的資料夾' % base)
            try:
                raw = aos_home.read_json(base / 'tick.json')
                bound = raw.get('envs', {}).get('AOS_K') if isinstance(raw, dict) else None
            except (aos_home.HomeError, AttributeError):
                bound = None
            if isinstance(bound, str) and bound != kernel:
                raise AgentError('KernelMismatch', '%s 綁在 %s' % (base / 'tick.json', bound))
            info = {'dir': str(base)}
        run = Runtime(info, None, env, _hook)
        params = {'name': 'agent-' + run.base.name}
        if starting:
            _compatible(kernel, env)
            params.update(target=_tick_inst(run, kernel), pool=info['tick']['pool'])
            if info['tick']['interval_ms'] is not None:
                params['interval_ms'] = info['tick']['interval_ms']
        name = 'aa-%s-%s.json' % (run.base.name, unique_id())
        run.submit(kernel, name, 'add' if starting else 'rm', params)
        try:
            response = aos_client.wait_response(kernel, name, timeout_ms=WAIT_TIMEOUT_MS)
        except aos_client.ClientError as exc:
            if exc.code != 'ReadFailed':
                raise
            raise AgentError('ReadFailed', '等回音逾時，回音會出現在 %s/responses/%s，讀完自己放 ack（cpu.md §3.3）'
                             % (kernel, name)) from exc
        run.ack(kernel, name, 0)
        if isinstance(response, dict) and isinstance(response.get('error'), dict):
            from aos_agent_results import error_code
            error = response['error']
            raise AgentError(str(error_code(error)), error.get('message', 'kernel 退件'))
        if (not isinstance(response, dict) or not isinstance(response.get('result'), dict)
                or not isinstance(response['result'].get('name'), str)):
            raise AgentError('ReadFailed', 'kernel 回音缺少 result.name')
        print(('started ' if starting else 'stopped ') + params['name'])
        return 0
    except (AgentError, aos_home.HomeError, OSError) as exc:
        return _error(exc)


def start(agent_dir, env=None):
    return _register(agent_dir, env, True)


def stop(agent_dir, env=None):
    return _register(agent_dir, env, False)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        report('Usage', message)
        raise SystemExit(2)


def main(argv=None):
    ap = Parser(prog='aos-agent')
    commands = ap.add_subparsers(dest='command', required=True)
    helps = {'tick': '走一格（kernel 反覆叫它）', 'start': '向 kernel 登記這個 agent',
             'stop': '撤銷登記', 'last': '印最後一則 assistant 回話',
             'init': '在資料夾生一個最小可跑的 agent 家',
             'say': '投一則 user 訊息（--wait 等回話）',
             'status': '印 agent 現在的狀態、在等什麼、最近的錯', 'continue': '解除連敗暫停'}
    for name, help_text in helps.items():
        sub = commands.add_parser(name, help=help_text)
        if name == 'say':
            sub.add_argument('values', nargs='+', metavar='[dir] TEXT')
            sub.add_argument('--wait', action='store_true')
            sub.add_argument('--timeout-ms', type=int)
        else:
            sub.add_argument('agent_dir', nargs='?', default='.')
        if name in ('last', 'status'):
            sub.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    try:
        if args.command == 'say':
            if len(args.values) not in (1, 2) or not args.values[-1]:
                ap.error('say 需要 TEXT，或 dir TEXT；TEXT 不可為空')
            if args.timeout_ms is not None and (not args.wait or args.timeout_ms < 0):
                ap.error('--timeout-ms 必須搭配 --wait，且不可為負數')
            from aos_agent_say import say
            return say(args.values[0] if len(args.values) == 2 else '.', args.values[-1],
                       wait=args.wait, timeout_ms=300000 if args.timeout_ms is None else args.timeout_ms)
        if args.command == 'last':
            from aos_agent_last import last
            return last(args.agent_dir, as_json=args.json)
        if args.command == 'status':
            from aos_agent_status import status
            return status(args.agent_dir, as_json=args.json)
        if args.command == 'continue':
            from aos_agent_status import resume
            return resume(args.agent_dir)
        if args.command == 'init':
            from aos_agent_init import init
            return init(args.agent_dir)
        return {'tick': tick, 'start': start, 'stop': stop}[args.command](args.agent_dir)
    except (AgentError, aos_home.HomeError, OSError) as exc:
        return _error(exc)


if __name__ == '__main__':
    raise SystemExit(main())
