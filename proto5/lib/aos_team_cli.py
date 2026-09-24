"""aos-team 的分派表（spec/team/cli.md）。

每個子命令＝(模組, 函式, 哪一隊做, 一句話)。函式簽名一律 fn(team_dir, argv) → 退出碼；
argv 是子命令之後、已拿掉 --target 的參數，各模組自己用 argparse 解。
模組或函式還不在＝印「還沒做（第 N 隊）」退 1。別隊只新增自己的模組，不改這張表以外的東西；
要加新子命令就在 COMMANDS 加一行（這一行的合併衝突由調度者處理）。
"""
import importlib
import os
import sys

from aos_team_format import TeamError

COMMANDS = {
    'init': ('aos_team', 'cmd_init', 1, '照 team.json 建團隊資料夾與每個成員的家'),
    'start': ('aos_team', 'cmd_start', 1, '全部成員（和郵差、心跳）向 kernel 登記'),
    'stop': ('aos_team', 'cmd_stop', 1, '全部撤銷登記'),
    'ls': ('aos_team', 'cmd_ls', 1, '一行一個成員：health、手上的單、最後一封信'),
    'rm': ('aos_team', 'cmd_rm', 1, '拿掉一個成員（家搬進 members/.removed/，不刪）'),
    'ask': ('aos_team_route', 'cmd_ask', 1, '交給門房：命中規則就直接做，沒命中投給領隊'),
    'route': ('aos_team_route', 'cmd_route', 1, 'route test／save：跑規則的例句，全過才存；route try "一句話"：看會怎麼判、不真的做'),
    'task': ('aos_team_task_cli', 'cmd_task', 1, 'task ls／show／cancel／reassign'),
    'wait': ('aos_team_ask_cli', 'cmd_wait', 1, 'wait ls：列出等人回答的問題'),
    'answer': ('aos_team_ask_cli', 'cmd_answer', 1, 'answer q-0001 "…"：回答一題'),
    'mail': ('aos_team_mail', 'cmd_mail', 2, '一封信一行（加等你回答的題目），照時間排'),
    'post': ('aos_team_post', 'cmd_post', 2, '郵差走一次（kernel 反覆叫它）'),
    'verify': ('aos_team_verify', 'cmd_verify', 2, '對一張單跑固定檢查器'),
    'routine': ('aos_team_beat', 'cmd_routine', 2, 'routine ls／add／rm：心跳排程'),
    'lock': ('aos_team_lock', 'cmd_lock', 3, 'lock ls／acquire／release：短期獨佔鎖（第二波 C 隊）'),
    'beat': ('aos_team_beat', 'cmd_beat', 2, '心跳走一次（kernel 反覆叫它）'),
    'score': ('aos_team_score', 'cmd_score', 5, '六軸能量的部分自動彙整'),
    'crystal': ('aos_team_crystal', 'cmd_crystal', 3, '固化建議：從 route.log 找常落穿的句型，產候選規則提案給人批（不自動生效）'),
}
ENV_HOME = 'AOS_TEAM_HOME'


def usage():
    lines = ['用法：aos-team <子命令> [參數…] [--target 團隊資料夾]',
             '團隊資料夾：--target；沒給看 %s；再沒有＝目前資料夾。' % ENV_HOME, '', '子命令：']
    width = max(len(k) for k in COMMANDS)
    for name, (_, _, team, text) in COMMANDS.items():
        lines.append('  %s  %s' % (name.ljust(width), text))
    lines.append('')
    lines.append('每個子命令加 -h 看自己的用法。')
    return '\n'.join(lines)


def split_target(argv):
    """把 --target X／--target=X 從任何位置拿出來；回 (target 或 None, 其餘)。"""
    rest, target, i = [], None, 0
    while i < len(argv):
        a = argv[i]
        if a == '--target':
            if i + 1 >= len(argv):
                raise TeamError('Usage', '--target 後面要接團隊資料夾')
            target, i = argv[i + 1], i + 2
            continue
        if a.startswith('--target='):
            target = a.split('=', 1)[1]
        else:
            rest.append(a)
        i += 1
    return target, rest


def resolve(name):
    """子命令 → 函式；還沒做就丟 TeamError('NotImplemented')。"""
    if name not in COMMANDS:
        raise TeamError('Usage', '不認得的子命令 %r\n\n%s' % (name, usage()))
    module, func, team, _ = COMMANDS[name]
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError as e:
        if e.name != module:
            raise
        raise TeamError('NotImplemented', 'aos-team %s 還沒做（第 %d 隊，模組 %s）' % (name, team, module))
    fn = getattr(mod, func, None)
    if fn is None:
        raise TeamError('NotImplemented', 'aos-team %s 還沒做（第 %d 隊，%s.%s）' % (name, team, module, func))
    return fn


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        target, rest = split_target(argv)
        if not rest or rest[0] in ('-h', '--help', 'help'):
            print(usage())
            return 0 if rest else 2
        fn = resolve(rest[0])
        team = target or os.environ.get(ENV_HOME) or os.getcwd()
        return fn(os.path.abspath(os.path.expanduser(team)), rest[1:])
    except TeamError as e:
        sys.stderr.write('aos-team: %s: %s\n' % (e.code, e.msg))
        return 2 if e.code == 'Usage' else 1
    except KeyboardInterrupt:
        return 130
