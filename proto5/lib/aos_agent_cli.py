"""aos-agent 的命令列（aos-agent.md §1）：家一律 --target DIR，省略＝目前資料夾。

這個檔留 main（先驗用法、再照子命令分派）；parser 與參數再驗分在 aos_agent_cli_parser／args。
"""
import os
from pathlib import Path

import aos_home
from aos_agent_home import AgentError

from aos_agent_cli_parser import _parser, TALK_WAIT_SECONDS, TOOLS_DEV, WAIT_SECONDS
from aos_agent_cli_args import (
    _is_number, _listen_count, _memory_usage, _seconds, _tools, _tools_usage
)


def main(argv=None):
    ap = _parser()
    args = ap.parse_args(argv)
    if args.target == '':
        ap.error('--target 不可為空')
    target = args.target or '.'
    source = '--target' if args.target else aos_home.SOURCE_CWD
    # 用法先驗完（退 2），才看家在不在（退 1）。
    if args.command == 'say':
        text = list(args.text)
        if args.wait and not text and not _is_number(args.wait):
            text, args.wait = [args.wait], ''  # say --wait "你好"：那個字是 TEXT
        if len(text) > 1:
            ap.error('say 只收一段 TEXT；要指定家用 --target DIR（舊的 say dir TEXT 不再支援）')
        if not text or not text[0]:
            ap.error('say 需要 TEXT，且不可為空')
    if args.command == 'continue' and args.all:
        if args.target is not None:
            ap.error('continue --all 不能跟 --target 一起給')
        if not os.path.isabs(os.environ.get('AOS_KERNEL_HOME') or ''):
            ap.error('continue --all 要 AOS_KERNEL_HOME（kernel 家的絕對路徑）')
    if args.command == 'listen':
        count = _listen_count(ap, args)
    if args.command == 'tools':
        tools_opts = _tools_usage(ap, args)
    if args.command == 'access':
        from aos_agent_access_cli import usage_problem
        problem = usage_problem(args.action, args.args, ro=args.ro, rw=args.rw, cwd=args.cwd, as_json=args.json)
        if problem:
            ap.error(problem)
    memory = _memory_usage(ap, args)
    wait = getattr(args, 'wait', None)
    timeout = _seconds(ap, wait) if wait is not None else WAIT_SECONDS * 1000
    if args.command == 'talk':
        if wait == '':
            ap.error('talk --wait 後面要是秒數')
        timeout = _seconds(ap, wait) if wait is not None else TALK_WAIT_SECONDS * 1000
    try:
        base = os.path.abspath(target)
        if args.command == 'stop' and not os.path.isdir(base):
            raise AgentError('NotAnAgent', '%s 不是存在的資料夾' % base)
        if args.command == 'continue' and args.all:
            from aos_agent_pause import resume_all
            return resume_all()
        dev = args.command == 'tools' and args.action in TOOLS_DEV
        if args.command not in ('init', 'tick', 'stop') and not dev:
            from aos_agent import _other_home
            if not os.path.exists(os.path.join(base, 'info.json')):
                raise AgentError('NotAnAgent', '%s 沒有 info.json' % base)
            kind = _other_home(Path(base))
            if kind:
                raise AgentError('NotAnAgent', '%s 是 %s 家，不是 agent 家（_metainfo._type 是 %s）' % (base, kind, kind))
        if args.command == 'say':
            from aos_agent_say import say
            return say(target, text[0], wait=wait is not None, timeout_ms=timeout)
        if args.command == 'listen':
            from aos_agent_listen import listen
            mode = 'wait' if wait is not None else 'follow' if args.follow else 'last'
            calls = 'full' if args.show_calls_full else 'short' if args.show_calls else None
            return listen(target, mode, count=count, calls=calls, timeout_ms=timeout, as_json=args.json)
        if args.command == 'talk':
            from aos_agent_talk import talk
            return talk(target, timeout_ms=timeout, show_calls=args.show_calls)
        if args.command == 'status':
            from aos_agent_status import status
            return status(target, as_json=args.json, verbose=args.verbose)
        if args.command == 'check':
            from aos_agent_check import check
            return check(target, probe=args.probe)
        if args.command in ('pause', 'continue'):
            from aos_agent_pause import pause, resume
            return pause(target) if args.command == 'pause' else resume(target)
        if args.command == 'tools':
            return _tools(target, args, tools_opts)
        if args.command == 'access':
            from aos_agent_access_cli import main as access_main
            return access_main(target, args.action, args.args, ro=args.ro, rw=args.rw, cwd=args.cwd,
                               as_json=args.json)
        if args.command in memory:
            return memory[args.command](target, args)
        if args.command == 'init':
            if args.template is not None:
                # 第 1 隊的 init_from_template（spec/team/templates.md）；團隊專用的模板（team: true）它會拒絕
                from aos_agent_init import init_from_template
                for line in init_from_template(target, args.template, force=args.force):
                    print(line)
                return 0
            from aos_agent_init import init
            return init(target, force=args.force)
        import aos_agent
        return {'tick': aos_agent.tick, 'start': aos_agent.start,
                'stop': aos_agent.stop}[args.command](target, note=aos_home.target_note(
                    'agent 家', os.path.abspath(target), source))
    except (AgentError, aos_home.HomeError, OSError) as exc:
        if getattr(exc, 'code', None) == 'NotAnAgent':
            exc.msg = getattr(exc, 'msg', str(exc)) + aos_home.target_note(
                'agent 家', os.path.abspath(target), source)
        from aos_agent import _error
        return _error(exc)
