"""aos-agent 的命令列（aos-agent.md §1）：家一律 --target DIR，省略＝目前資料夾。"""
import argparse
import os
from pathlib import Path

import aos_home
from aos_agent_home import AgentError
from aos_agent_runtime import report

WAIT_SECONDS = 300
MAX_WAIT_SECONDS = 7 * 24 * 3600
HELPS = {'tick': '走一格（kernel 反覆叫它）', 'start': '向 kernel 登記這個 agent',
         'stop': '撤銷登記', 'init': '在資料夾生一個最小可跑的 agent 家',
         'say': '投一則 user 訊息（--wait 等回話）',
         'listen': '看回話：--last 最後一則（預設）、--wait 等下一則、--follow 一直印',
         'status': '印 agent 現在的狀態、在等什麼、最近的錯',
         'pause': '手動暫停：還登記著，但每格什麼都不做',
         'continue': '解除手動暫停與連敗暫停',
         'check': '啟動前檢查：K 的設定＋這個 agent 家（--probe 真的打一次模型）',
         'tools': '裝工具包：tools add NAME|DIR（內建 base＝read／write／edit／bash／grep／find／ls）'}
WAIT_HELP = '等幾秒；不帶數字＝%d 秒' % WAIT_SECONDS


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
            modes = sub.add_mutually_exclusive_group()
            modes.add_argument('--last', action='store_true', help='印最後一則回話就退（預設）')
            modes.add_argument('--wait', nargs='?', const='', metavar='秒',
                               help='等下一則新回話，印出就退；' + WAIT_HELP)
            modes.add_argument('--follow', action='store_true', help='每一則新回話都印，直到 Ctrl-C')
        if name == 'status':
            sub.add_argument('-v', '--verbose', action='store_true', help='顯示完整 touch 指令、舊錯原文與 stuck 原行')
        if name == 'init':
            sub.add_argument('--force', action='store_true', help='資料夾裡已有別的東西也照樣生（info.json 已在仍拒絕）')
        if name == 'tools':
            sub.usage = 'aos-agent tools add NAME|DIR [--target DIR] [--root DIR] [--force]'
            sub.add_argument('action', choices=['add'], help='目前只有 add')
            sub.add_argument('package', metavar='NAME|DIR', help='內建工具包名字（proto5/tools/ 下），或工具包資料夾（含 /）')
            sub.add_argument('--root', metavar='DIR', help='工作根目錄（寫進工具包的 config.json；base 沒給＝agent 家的 workspace/）')
            sub.add_argument('--force', action='store_true', help='已經裝過也重裝（保留原本的 config.json，除非給了 --root）')
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
    wait = getattr(args, 'wait', None)
    timeout = _seconds(ap, wait) if wait is not None else WAIT_SECONDS * 1000
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
            return listen(target, mode, timeout_ms=timeout, as_json=args.json)
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
            from aos_agent_tools import add
            return add(target, args.package, root=args.root, force=args.force)
        if args.command == 'init':
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
