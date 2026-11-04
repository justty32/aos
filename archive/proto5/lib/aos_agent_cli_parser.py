"""`aos-agent` 的 argparse：各子命令的一句話、秒數上限、tools／access／listen 的用法說明與選項表、建 parser。"""
import argparse

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
         'tools': '工具管理：tools ls／add／rm／alias／unalias；造工具：new／test／wrap-py／wrap-cli（內建包 base＝read／write／edit／bash／grep／find／ls）',
         'access': '權限牆：access ls／set／rm／cwd／net（工具關進牢裡看得到哪些資料夾）',
         # 第 4 隊（記憶與紀錄）：spec/aos-agent/cli-memory.md
         'context': '送給模型的東西多大：人格、記憶、工具的字數與 token 粗估（--by-round 每輪一行）',
         'compact': '機械壓縮記憶（預設不叫模型）：舊的輪只留原話與最後回話，原文存進 prompts/archive/；--summarize 讓模型濃縮封存摘要',
         'events': '事件紀錄：每批起訖與成敗、收件、壓縮（--usage 看模型回報的 token 用量）',
         'history': '看壓縮前的原文：history --archive [SHA] [--grep 字]',
         'notes': '長期筆記：notes ls｜notes show KEY',
         # 第二波 C 隊（申請類）：spec/agent/persona.md
         'persona': '人格是信任資料，模型改不到：persona show｜persona set TEXT｜persona append TEXT'}
TALK_WAIT_SECONDS = 120
ACCESS_EPILOG = ('用法：\n'
                 '  aos-agent access ls  [--target DIR] [--json]\n'
                 '  aos-agent access set NAME PATH [--ro | --rw] [--cwd] [--target DIR]\n'
                 '  aos-agent access rm  NAME [--target DIR]\n'
                 '  aos-agent access cwd NAME [--target DIR]\n'
                 '  aos-agent access net on|off [--target DIR]\n'
                 'PATH 照目前資料夾轉成絕對路徑寫進 access.json；工具在牢裡看到 /work/NAME。改完下一批工具生效，不用重 start。')
TOOLS_ARGS = {'ls': (), 'add': ('NAME|DIR|FILE.json',), 'rm': ('NAME',), 'alias': ('NAME', 'NEW'),
              'unalias': ('NEW',), 'new': ('NAME',), 'test': ('NAME|DIR',), 'wrap-py': ('FILE.py',),
              'wrap-cli': ('CMD',)}
TOOLS_DEV = ('new', 'test', 'wrap-py', 'wrap-cli')   # 造工具的（spec/aos-agent/tools-dev.md、tools-llm.md）：不需要 agent 家
# 選項 → 給哪幾個動作（其他動作給了＝用法錯 2）
TOOLS_OPTS = (('--root', 'root', ('add',)), ('--force', 'force', ('add', 'new', 'wrap-py', 'wrap-cli')),
              ('--as', 'as_', ('add',)), ('--only', 'only', ('add', 'wrap-py')), ('--json', 'json', ('ls', 'test')),
              ('--out', 'out', ('new', 'wrap-py', 'wrap-cli')), ('--name', 'name', ('wrap-py', 'wrap-cli')),
              ('--args', 'tool_args', ('test',)),
              ('--case', 'case', ('test',)), ('--no-jail', 'no_jail', ('test',)), ('--tool', 'tool', ('test',)),
              # 第三波 W3-2（spec/aos-agent/tools-llm.md）
              ('--describe-with-llm', 'describe_with_llm', ('wrap-py', 'wrap-cli')),
              ('--model', 'model', ('wrap-py', 'wrap-cli')), ('--describe', 'describe', ('wrap-py',)),
              ('--spec', 'spec', ('wrap-cli',)), ('--help-file', 'help_file', ('wrap-cli',)))
TOOLS_EPILOG = ('用法：\n'
                '  aos-agent tools ls      [--target DIR] [--json]\n'
                '  aos-agent tools add     NAME|DIR|FILE.json [--target DIR] [--as NEW | --as OLD=NEW[,OLD=NEW…]]'
                ' [--only a,b] [--root DIR] [--force]\n'
                '  aos-agent tools rm      NAME [--target DIR]      # 只改 info.json，不刪檔\n'
                '  aos-agent tools alias   NAME NEW [--target DIR]\n'
                '  aos-agent tools unalias NEW [--target DIR]\n'
                '  aos-agent tools new     NAME [--out DIR] [--force]          # 生工具包骨架\n'
                '  aos-agent tools test    NAME|DIR [--tool T] [--args JSON] [--case FILE] [--no-jail] [--json]\n'
                '  aos-agent tools wrap-py FILE.py [--only f,g] [--name PACK] [--out DIR] [--force]\n'
                '                          [--describe-with-llm [--model ALIAS] | --describe FILE]\n'
                '  aos-agent tools wrap-cli CMD [--name PACK] [--out DIR] [--force] [--help-file F]\n'
                '                          [--describe-with-llm [--model ALIAS] | --spec FILE]   # 把一支指令包成工具\n'
                'new／test／wrap-py／wrap-cli 不需要 agent 家（不收 --target）；test 預設關在牢裡跑（有 bwrap 時）。\n'
                '--describe-with-llm 叫模型一次（只有這一步要 AOS_LLM_CONFIG），只寫提案檔、不產包；\n'
                '人看過再用 --describe／--spec 產包（不叫模型、不需要 AOS_LLM_CONFIG）。\n'
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
            sub.add_argument('--summarize', action='store_true',
                             help='封存摘要的中間那段再叫模型濃縮（要 AOS_LLM_CONFIG；過不了機械檢查就用機械摘要）')
            sub.add_argument('--model', metavar='ALIAS', help='--summarize 用哪個模型代號（預設這個 agent 的 llm.model）')
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
        if name == 'persona':
            sub.add_argument('action', choices=['show', 'set', 'append'], help='show 印目前人格；set 整份換掉；append 加一行')
            sub.add_argument('text', nargs='?', metavar='TEXT', help='set／append 要給；show 不收')
            sub.add_argument('--json', action='store_true', help='show：印機器格式')
        if name == 'tools':
            sub.formatter_class = argparse.RawDescriptionHelpFormatter
            sub.usage = 'aos-agent tools {ls,add,rm,alias,unalias,new,test,wrap-py,wrap-cli} [ARG…] [--target DIR] [選項]'
            sub.epilog = TOOLS_EPILOG
            sub.add_argument('action', choices=list(TOOLS_ARGS), help='要做什麼（見下面用法）')
            sub.add_argument('args', nargs='*', metavar='ARG')
            sub.add_argument('--out', metavar='DIR', help='new／wrap-py／wrap-cli：生在哪個資料夾底下（省略＝目前資料夾）')
            sub.add_argument('--name', metavar='PACK', help='wrap-py／wrap-cli：工具包名字（省略＝檔名去掉 .py／指令名）')
            sub.add_argument('--help-file', metavar='F', help='wrap-cli：help 文字從這個檔讀（省略＝跑 CMD --help）')
            sub.add_argument('--describe-with-llm', action='store_true',
                             help='wrap-py：請模型補沒 docstring 的描述；wrap-cli：請模型讀 help 出參數表。只寫提案檔，不產包（要 AOS_LLM_CONFIG）')
            sub.add_argument('--model', metavar='ALIAS', help='--describe-with-llm 用 llm.json 的哪個代號（省略＝default）')
            sub.add_argument('--describe', metavar='FILE', help='wrap-py：照人看過的描述提案檔補描述再產包')
            sub.add_argument('--spec', metavar='FILE', help='wrap-cli：照人看過的參數表產包（不叫模型）')
            sub.add_argument('--args', dest='tool_args', metavar='JSON', help='test：只用這組 arguments 跑一次，原樣印輸出')
            sub.add_argument('--case', metavar='FILE', help='test：固定案例檔（省略＝包裡的 cases.json）')
            sub.add_argument('--no-jail', action='store_true', help='test：不關牢，直接在這台機器上跑')
            sub.add_argument('--tool', metavar='T', help='test：只測包裡這一支')
            sub.add_argument('--root', metavar='DIR', help='add 裝包：工作根目錄（寫進工具包的 config.json；base 沒給＝agent 家的 workspace/）')
            sub.add_argument('--force', action='store_true', help='add 裝包：已經裝過也重裝（保留原本的 config.json，除非給了 --root）；'
                             'new／wrap-py：資料夾已在也蓋掉')
            sub.add_argument('--as', dest='as_', metavar='NEW|OLD=NEW[,…]', help='add：改名（恰好一支時可只給新名）')
            sub.add_argument('--only', metavar='a,b', help='add：只挑這幾支（原名）；wrap-py：只包這幾個函式')
            sub.add_argument('--json', action='store_true', help='ls／test：印穩定的機器格式')
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
