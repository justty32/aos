"""aos-agent 的命令列（aos-agent.md §1）：家一律 --target DIR，省略＝目前資料夾。"""
import argparse
import os
from pathlib import Path
import re

import aos_home
from aos_agent_home import AgentError
from aos_agent_runtime import report

WAIT_SECONDS = 300
MAX_WAIT_SECONDS = 7 * 24 * 3600
HELPS = {'tick': '走一格（kernel 反覆叫它）', 'start': '向 kernel 登記這個 agent',
         'stop': '撤銷登記', 'init': '在資料夾生一個最小可跑的 agent 家',
         'say': '投一則 user 訊息（--wait 等回話）',
         'listen': '看回話：--last [N] 最後 N 則、--wait 等下一則、--follow 一直印（三選一，要給）',
         'talk': '來回對話：打一行送出、等回話印出、再打下一行；/help 看 slash 指令，Ctrl-C 離開',
         'status': '印 agent 現在的狀態、在等什麼、最近的錯',
         'pause': '手動暫停：還登記著，但每格什麼都不做',
         'continue': '解除手動暫停與連敗暫停',
         'check': '啟動前檢查：K 的設定＋這個 agent 家（--probe 真的打一次模型）',
         'tools': '工具管理：tools ls／add／rm／alias／unalias（內建包 base＝read／write／edit／bash／grep／find／ls）',
         'access': '權限牆：access ls／set／rm／cwd／net（工具關進牢裡看得到哪些資料夾）',
         # 第 4 隊（記憶與紀錄）：spec/aos-agent/cli-memory.md
         'context': '送給模型的東西多大：人格、記憶、工具的字數與 token 粗估（--by-round 每輪一行）',
         'compact': '機械壓縮記憶（不叫模型）：舊的輪只留原話與最後回話，原文存進 prompts/archive/',
         'events': '事件紀錄：每批起訖與成敗、收件、壓縮（--usage 看模型回報的 token 用量）',
         'history': '看壓縮前的原文：history --archive [SHA] [--grep 字]',
         'notes': '長期筆記：notes ls｜notes show KEY'}
TALK_WAIT_SECONDS = 120
ACCESS_EPILOG = ('用法：\n'
                 '  aos-agent access ls  [--target DIR] [--json]\n'
                 '  aos-agent access set NAME PATH [--ro | --rw] [--cwd] [--target DIR]\n'
                 '  aos-agent access rm  NAME [--target DIR]\n'
                 '  aos-agent access cwd NAME [--target DIR]\n'
                 '  aos-agent access net on|off [--target DIR]\n'
                 'PATH 照目前資料夾轉成絕對路徑寫進 access.json；工具在牢裡看到 /work/NAME。改完下一批工具生效，不用重 start。')
TOOLS_ARGS = {'ls': (), 'add': ('NAME|DIR|FILE.json',), 'rm': ('NAME',), 'alias': ('NAME', 'NEW'),
              'unalias': ('NEW',)}
TOOLS_EPILOG = ('用法：\n'
                '  aos-agent tools ls      [--target DIR] [--json]\n'
                '  aos-agent tools add     NAME|DIR|FILE.json [--target DIR] [--as NEW | --as OLD=NEW[,OLD=NEW…]]'
                ' [--only a,b] [--root DIR] [--force]\n'
                '  aos-agent tools rm      NAME [--target DIR]      # 只改 info.json，不刪檔\n'
                '  aos-agent tools alias   NAME NEW [--target DIR]\n'
                '  aos-agent tools unalias NEW [--target DIR]\n'
                'add 的對象：不含 / 的名字＝內建工具包；含 <資料夾名>.json 的資料夾＝工具包（複製進 tools/）；\n'
                '其他資料夾或 .json 檔＝原地引用（不複製，info.tools 加一條）。改完下一批工具生效，不用重 start。')
WAIT_HELP = '等幾秒；不帶數字＝%d 秒' % WAIT_SECONDS
FULL_LIMIT = 4000  # 跟 aos_agent_listen_render.FULL_LIMIT 一致（-h 不為了一個數字載入印法模組）
LISTEN_MODES = '--last [N]（最後 N 則）、--wait [秒]（等下一則）、--follow（一直印）'
LISTEN_EPILOG = ('三種看法選一種，都不給＝用法錯：\n'
                 '  aos-agent listen --last          最後一則回話\n'
                 '  aos-agent listen --last 5        最後五則，每輪前面一行「── 第 R 輪 · 收話 時間 ──」\n'
                 '  aos-agent listen --last 3 --show-calls   連同叫了哪些工具、結果第一行\n'
                 '  aos-agent listen --follow --show-calls-full   一直印，工具參數與回傳也印（各最多 %d 字）' % FULL_LIMIT)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        report('Usage', message)
        raise SystemExit(2)


def _parser():
    ap = Parser(prog='aos-agent', description='agent 家的日常指令；家用 --target DIR 指定，省略＝目前資料夾')
    commands = ap.add_subparsers(dest='command', required=True, parser_class=Parser)
    for name, help_text in HELPS.items():
        sub = commands.add_parser(name, help=help_text, description=help_text)
        sub.add_argument('--target', metavar='DIR', help='agent 家（省略＝目前資料夾）')
        if name == 'say':
            sub.formatter_class = argparse.RawDescriptionHelpFormatter
            sub.usage = 'aos-agent say TEXT [--target DIR] [--wait [秒]]'
            sub.description = '投一則 user 訊息到 --target 的家（省略＝目前資料夾）。'
            sub.epilog = ('例子：\n  cd 家 && aos-agent say "現在幾點？" --wait\n'
                          '  aos-agent say "現在幾點？" --target ~/agents/amy --wait 60\n'
                          '--wait 不帶數字＝等 %d 秒；暫停中照收，continue 後才處理。' % WAIT_SECONDS)
            sub.add_argument('text', nargs='*', metavar='TEXT')
            sub.add_argument('--wait', nargs='?', const='', metavar='秒', help=WAIT_HELP)
        elif name == 'listen':
            sub.formatter_class = argparse.RawDescriptionHelpFormatter
            sub.usage = ('aos-agent listen [--target DIR] (--last [N] | --wait [秒] | --follow)'
                         ' [--show-calls | --show-calls-full] [--json]')
            sub.epilog = LISTEN_EPILOG
            modes = sub.add_mutually_exclusive_group()
            modes.add_argument('--last', nargs='?', const='1', metavar='N',
                               help='印最後 N 則回話就退（不帶數字＝1）')
            modes.add_argument('--wait', nargs='?', const='', metavar='秒',
                               help='等下一則新回話，印出就退；' + WAIT_HELP)
            modes.add_argument('--follow', action='store_true', help='每一則新回話都印，直到 Ctrl-C')
            shows = sub.add_mutually_exclusive_group()
            shows.add_argument('--show-calls', action='store_true',
                               help='連同工具呼叫一起印：一個呼叫一行 [呼叫 名 參數]、結果一行 [結果 名：第一行]')
            shows.add_argument('--show-calls-full', action='store_true',
                               help='連同工具呼叫一起印完整參數 JSON 與工具回傳（各超過 %d 字截斷並註明）' % FULL_LIMIT)
        elif name == 'talk':
            from aos_agent_talk import HELP
            sub.formatter_class = argparse.RawDescriptionHelpFormatter
            sub.epilog = ('提示符打 / 開頭是指令，不送給模型：\n' +
                          '\n'.join('  %-14s %s' % pair for pair in HELP) +
                          '\n例子：cd 家 && aos-agent talk --show-calls')
            sub.add_argument('--wait', metavar='秒', default=None,
                             help='每句最多等幾秒（預設 %d；0＝不等，按 Enter 再看）' % TALK_WAIT_SECONDS)
            sub.add_argument('--show-calls', action='store_true',
                             help='印出工具呼叫與結果的簡化行，例如 [呼叫 date] [結果 ok 1 行]')
        if name == 'status':
            sub.add_argument('-v', '--verbose', action='store_true', help='顯示完整 touch 指令、舊錯原文與 stuck 原行')
        if name == 'init':
            sub.add_argument('--force', action='store_true', help='資料夾裡已有別的東西也照樣生（info.json 已在仍拒絕）')
            sub.add_argument('--template', metavar='NAME', help='照 proto5/templates/NAME/ 生（第 1 隊的 init_from_template）')
        if name == 'context':
            sub.add_argument('--by-round', action='store_true', help='每輪一行：則數、字數、token、最胖的工具結果')
            sub.add_argument('--json', action='store_true', help='印機器格式')
        if name == 'compact':
            sub.add_argument('--keep-rounds', metavar='N', help='最後 N 輪原樣留（預設 info.compact.keep_rounds，再沒有＝3）')
            sub.add_argument('--max-tokens', metavar='X', help='縮完還超過 X token 就把最舊的輪整輪封存（預設 info.compact.max_tokens）')
            sub.add_argument('--dry-run', action='store_true', help='只印會變成怎樣，不寫任何檔')
            sub.add_argument('--prune-archive', metavar='天數', help='改做清理：刪超過這麼多天、記憶裡沒提到的 archive')
            sub.add_argument('--json', action='store_true', help='印機器格式')
        if name == 'events':
            sub.add_argument('--last', metavar='N', default='20', help='最後幾則（預設 20；0＝全部）')
            sub.add_argument('--usage', action='store_true', help='改看 log/usage.jsonl（aos-llm call 記的 token 用量）')
            sub.add_argument('--json', action='store_true', help='印機器格式')
        if name == 'history':
            sub.add_argument('--archive', action='store_true', help='看 compact 存下的原文（現在只有這一種看法，要給）')
            sub.add_argument('sha', nargs='?', metavar='SHA', help='只看這一份（開頭幾個字就行）')
            sub.add_argument('--grep', metavar='字', help='在 archive 裡找這個字（不分大小寫）')
            sub.add_argument('--json', action='store_true', help='印機器格式')
        if name == 'notes':
            sub.add_argument('action', choices=['ls', 'show'], help='ls 列全部；show KEY 看一則')
            sub.add_argument('args', nargs='*', metavar='KEY')
            sub.add_argument('--json', action='store_true', help='ls：印機器格式')
        if name == 'tools':
            sub.formatter_class = argparse.RawDescriptionHelpFormatter
            sub.usage = 'aos-agent tools {ls,add,rm,alias,unalias} [ARG…] [--target DIR] [選項]'
            sub.epilog = TOOLS_EPILOG
            sub.add_argument('action', choices=list(TOOLS_ARGS), help='要做什麼（見下面用法）')
            sub.add_argument('args', nargs='*', metavar='ARG')
            sub.add_argument('--root', metavar='DIR', help='add 裝包：工作根目錄（寫進工具包的 config.json；base 沒給＝agent 家的 workspace/）')
            sub.add_argument('--force', action='store_true', help='add 裝包：已經裝過也重裝（保留原本的 config.json，除非給了 --root）')
            sub.add_argument('--as', dest='as_', metavar='NEW|OLD=NEW[,…]', help='add：改名（恰好一支時可只給新名）')
            sub.add_argument('--only', metavar='a,b', help='add：只挑這幾支（原名）')
            sub.add_argument('--json', action='store_true', help='ls：印穩定的機器格式')
        if name == 'access':
            sub.formatter_class = argparse.RawDescriptionHelpFormatter
            sub.usage = 'aos-agent access {ls,set,rm,cwd,net} [ARG…] [--target DIR] [選項]'
            sub.epilog = ACCESS_EPILOG
            sub.add_argument('action', choices=['ls', 'set', 'rm', 'cwd', 'net'], help='要做什麼（見下面用法）')
            sub.add_argument('args', nargs='*', metavar='ARG')
            sub.add_argument('--ro', action='store_true', help='set：唯讀掛')
            sub.add_argument('--rw', action='store_true', help='set：可寫掛（跟信任資料重疊會拒絕）')
            sub.add_argument('--cwd', action='store_true', help='set：同時把牢裡起點設成它')
            sub.add_argument('--json', action='store_true', help='ls：印機器格式')
        if name == 'continue':
            sub.add_argument('--all', action='store_true',
                             help='解開 AOS_KERNEL_HOME 帳本裡所有登記的 agent（不能跟 --target 一起給）')
        if name == 'check':
            sub.add_argument('--probe', action='store_true',
                             help='真的對 llm.json 的每個 endpoint 打一次最小請求')
        if name in ('listen', 'status'):
            sub.add_argument('--json', action='store_true')
    return ap


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
    if args.action != 'add':
        extra = [f for f, v in (('--root', args.root), ('--force', args.force), ('--as', args.as_),
                                ('--only', args.only)) if v is not None and v is not False]
        if extra:
            ap.error('%s 只給 tools add' % '、'.join(extra))
    if args.json and args.action != 'ls':
        ap.error('--json 只給 tools ls')
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


def _tools(target, args, opts):
    import aos_agent_tools_edit as edit
    a = args.args
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
        if days is not None and (keep is not None or limit is not None or args.dry_run or args.json):
            ap.error('--prune-archive 不跟別的選項一起給')
        if days is not None:
            from aos_agent_compact import prune
            return {cmd: lambda t, a: prune(t, days)}
        from aos_agent_compact import compact
        return {cmd: lambda t, a: compact(t, keep_rounds=keep, max_tokens=limit, dry_run=a.dry_run, as_json=a.json)}
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
    if cmd == 'init' and args.template is not None and not args.template:
        ap.error('--template 不可為空')
    return {}


def _is_number(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


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
        if args.command not in ('init', 'tick', 'stop'):
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
                # 第 1 隊寫 aos_agent_init.init_from_template()；還沒合進來就說還沒做
                import aos_agent_init
                fn = getattr(aos_agent_init, 'init_from_template', None)
                if fn is None:
                    raise AgentError('NotImplemented', 'init --template 還沒做（第 1 隊的 init_from_template）')
                return fn(target, args.template, force=args.force)
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
