"""`aos-agent` 解析後的參數再驗（用法錯退 2）：--wait 秒數、listen 看法、名字清單、tools 各動作的參數與選項、tools 分派、memory 類參數。"""
import re

from aos_agent_cli_parser import (
    LISTEN_MODES, MAX_WAIT_SECONDS, TOOLS_ARGS, TOOLS_DEV, TOOLS_OPTS, WAIT_SECONDS
)


def _seconds(ap, value):
    """--wait 的秒數：空＝預設；要是非負數字。回毫秒。"""
    if value == '':
        return WAIT_SECONDS * 1000
    try:
        seconds = float(value)
    except ValueError:
        ap.error('--wait 後面要是秒數（或不帶數字＝%d 秒）：%s' % (WAIT_SECONDS, value))
    if not 0 <= seconds <= MAX_WAIT_SECONDS:  # 也擋掉 nan、inf、1e309
        ap.error('--wait 的秒數要在 0～%d 之間：%s' % (MAX_WAIT_SECONDS, value))
    return int(seconds * 1000)


def _listen_count(ap, args):
    """listen 沒給看法＝用法錯（09-24 listen 微調：--last 不再是預設）；--last N 要是正整數。"""
    if args.last is None and args.wait is None and not args.follow:
        ap.error('listen 要選一種看法：' + LISTEN_MODES + '；例：aos-agent listen --last')
    if args.last is None:
        return 1
    digits = args.last.lstrip('0') if re.fullmatch(r'[0-9]+', args.last) else ''
    if not digits:
        ap.error('--last 後面要是正整數（不帶數字＝1）：%s' % args.last[:40])
    return int(digits) if len(digits) <= 9 else 10 ** 9  # 再大也只是「全部」，不必真的換算


def _names(ap, flag, value):
    names = value.split(',')
    if not all(names):
        ap.error('%s 的名字不可為空：%r' % (flag, value))
    if len(set(names)) != len(names):
        ap.error('%s 的名字重複了：%r' % (flag, value))
    return names


def _tools_usage(ap, args):
    """tools 子命令的用法驗（退 2）：參數個數、選項只給對的動作、--as／--only 的寫法。"""
    want = TOOLS_ARGS[args.action]
    if len(args.args) != len(want):
        ap.error('tools %s 要 %s' % (args.action, ' '.join(want) if want else '不帶參數'))
    if any(not a for a in args.args):
        ap.error('tools %s 的參數不可為空' % args.action)
    for flag, attr, actions in TOOLS_OPTS:
        value = getattr(args, attr)
        if value is not None and value is not False and args.action not in actions:
            ap.error('%s 只給 tools %s' % (flag, '／'.join(actions)))
        if isinstance(value, str) and not value and attr in ('out', 'name', 'tool_args', 'case', 'tool', 'model',
                                                             'describe', 'spec', 'help_file'):
            ap.error('%s 不可為空' % flag)
    if args.action in TOOLS_DEV:
        _tools_dev_usage(ap, args)
    as_arg = only = None
    if args.as_ is not None:
        if '=' not in args.as_:
            if not args.as_ or ',' in args.as_:
                ap.error('--as 要是一個新名字，或 OLD=NEW[,OLD=NEW…]：%r' % args.as_)
            as_arg = ('one', args.as_)
        else:
            pairs = [p.split('=', 1) for p in args.as_.split(',')]
            if any(len(p) != 2 or not p[0] or not p[1] for p in pairs):
                ap.error('--as 的每一段都要是 OLD=NEW：%r' % args.as_)
            _names(ap, '--as', ','.join(p[0] for p in pairs))
            as_arg = ('map', dict(pairs))
    if args.only is not None:
        only = _names(ap, '--only', args.only)
    return as_arg, only


def _tools_dev_usage(ap, args):
    """new／test／wrap-py 多的用法驗：不收 --target；--args 要是 JSON、不跟 --case 一起給。"""
    if args.target is not None:
        ap.error('tools %s 不需要 agent 家，不收 --target' % args.action)
    if args.model is not None and not args.describe_with_llm:
        ap.error('--model 只跟 --describe-with-llm 一起給')
    if args.describe_with_llm and (args.describe is not None or args.spec is not None):
        ap.error('--describe-with-llm 只寫提案檔；照提案產包（--describe／--spec）是另一次、不叫模型')
    if args.tool_args is not None:
        if args.case is not None:
            ap.error('--args 只跑一次、不跑案例，不跟 --case 一起給')
        try:
            import json
            json.loads(args.tool_args)
        except ValueError as exc:
            ap.error('--args 要是 JSON：%s' % exc)


def _tools(target, args, opts):
    import aos_agent_tools_edit as edit
    a = args.args
    if args.action in TOOLS_DEV:
        import aos_agent_tools_dev as dev
        if args.action == 'new':
            return dev.new(a[0], out=args.out, force=args.force)
        if args.action == 'wrap-py':
            if args.describe_with_llm:
                return dev.describe_with_llm(a[0], only=opts[1], name=args.name, out=args.out, force=args.force,
                                             model=args.model)
            return dev.wrap_py(a[0], only=opts[1], name=args.name, out=args.out, force=args.force,
                               describe=args.describe)
        if args.action == 'wrap-cli':
            from aos_agent_tools_wrapcli import wrap_cli
            return wrap_cli(a[0], name=args.name, out=args.out, force=args.force, help_file=args.help_file,
                            describe_with_llm=args.describe_with_llm, model=args.model, spec=args.spec)
        return dev.test(a[0], args=args.tool_args, case_file=args.case, no_jail=args.no_jail,
                        as_json=args.json, tool=args.tool)
    if args.action == 'add':
        from aos_agent_tools import add
        return add(target, a[0], root=args.root, force=args.force, as_arg=opts[0], only=opts[1])
    if args.action == 'ls':
        return edit.ls(target, as_json=args.json)
    return {'rm': edit.rm, 'alias': edit.alias, 'unalias': edit.unalias}[args.action](target, *a)


def _count(ap, flag, value, lo=0):
    if value is None:
        return None
    if not re.fullmatch(r'[0-9]{1,9}', value) or int(value) < lo:
        ap.error('%s 要是 %d 以上的整數：%s' % (flag, lo, value[:40]))
    return int(value)


def _memory_usage(ap, args):
    """第 4 隊的五個子命令：先驗用法（退 2），回 {子命令: fn(target, args)}。"""
    cmd = args.command
    if cmd == 'compact':
        keep, limit = _count(ap, '--keep-rounds', args.keep_rounds), _count(ap, '--max-tokens', args.max_tokens, 100)
        days = _count(ap, '--prune-archive', args.prune_archive)
        if days is not None and (keep is not None or limit is not None or args.dry_run or args.json
                                 or args.summarize or args.model is not None):
            ap.error('--prune-archive 不跟別的選項一起給')
        if args.model is not None and not args.summarize:
            ap.error('--model 只跟 --summarize 一起給')
        if days is not None:
            from aos_agent_compact import prune
            return {cmd: lambda t, a: prune(t, days)}
        from aos_agent_compact import compact
        return {cmd: lambda t, a: compact(t, keep_rounds=keep, max_tokens=limit, dry_run=a.dry_run, as_json=a.json,
                                          summarize=a.summarize, model=a.model)}
    if cmd == 'events':
        last = _count(ap, '--last', args.last)
        from aos_agent_events import show
        return {cmd: lambda t, a: show(t, last=last, as_json=a.json, usage=a.usage)}
    if cmd == 'history':
        if not args.archive:
            ap.error('history 現在只有 --archive 一種看法（對話記憶用 aos-agent listen --last N 或 talk 的 /history）')
        from aos_agent_compact import archive_main
        return {cmd: lambda t, a: archive_main(t, sha=a.sha, grep=a.grep, as_json=a.json)}
    if cmd == 'context':
        from aos_agent_context import main as context_main
        return {cmd: lambda t, a: context_main(t, as_json=a.json, by_rounds=a.by_round)}
    if cmd == 'notes':
        want = 1 if args.action == 'show' else 0
        if len(args.args) != want:
            ap.error('notes %s %s' % (args.action, '要一個 KEY' if want else '不帶參數'))
        if args.json and args.action != 'ls':
            ap.error('--json 只給 notes ls')

        def notes(t, a):
            from aos_agent_notes import main as notes_main
            return notes_main(t, a.action, a.args, as_json=a.json)
        return {cmd: notes}
    if cmd == 'persona':
        def persona(t, a):
            from aos_agent_persona import main as persona_main
            return persona_main(t, a.action, a.text, as_json=a.json)
        return {cmd: persona}
    if cmd == 'init' and args.template is not None and not args.template:
        ap.error('--template 不可為空')
    return {}


def _is_number(value):
    try:
        float(value)
        return True
    except ValueError:
        return False
