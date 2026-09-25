"""郵差的再驗一次：格式驗過的信與申請，再驗路徑（不准跳出專案）、工作流入口、cmd_ok 白名單與假冒信頭。"""
import json
import re

import aos_team_format as fmt
from aos_team_format import HUMAN, TeamError


# ---------------------------------------------------------- 再驗一次 ----
# 第二波 B 隊：工具在牢裡已經擋過一層（寫不到別人的 outbox、讀不到別人的家），郵差讀申請時照樣再驗：
# 身分（信在誰的 outbox＝誰寄的，read_outbox_file）、角色（模板的 may，aos_team_requests.handle）、
# 以及這裡的路徑與操作——條目路徑不准跳出專案、不准指到團隊資料夾或別人的家、cmd_ok 要在人寫的白名單裡、
# 成員寫的字不准假冒信頭（收件人看到的第一行【來信 …】只有郵差能寫）。

HEADER_LIKE = re.compile(r'^\s*【\s*(來信|人\s*→)', re.M)


def _bad_path(where, value, why):
    raise TeamError('BadPath', '%s 的路徑 %r %s；條目路徑一律寫成相對專案資料夾、不含 ..' % (where, value, why))


CONTROL = re.compile(r'[\x00-\x1f\x7f]')


def check_rel_path(where, value):
    """條目裡的檔案路徑：相對專案、不含 .. 段、不以 ~ 開頭、不含換行等控制字元、前後沒有空白。"""
    if not isinstance(value, str) or not value:
        _bad_path(where, value, '不是非空字串')
    if CONTROL.search(value) or value != value.strip():
        _bad_path(where, value, '有換行、控制字元或前後空白')
    if value.startswith(('/', '~')):
        _bad_path(where, value, '是絕對路徑或 ~ 開頭（在專案外，可能指到別人的家）')
    if '..' in value.replace('\\', '/').split('/'):
        _bad_path(where, value, '有 .. 段（可能跳出專案）')


def check_workflow(where, value):
    """工作流入口：可以是檔名、相對路徑、牢裡的 /work/… 或「無」；不准 .. 段、不准牢外的絕對路徑與 ~。
    派工信用的是 strip() 過的值，所以先用同一個規則正規化再驗（astra w2b M3）；有換行等控制字元一律不收。"""
    if CONTROL.search(value):
        _bad_path(where, value, '有換行或控制字元')
    value = value.strip()
    if value.startswith('~') or (value.startswith('/') and not value.startswith('/work/')):
        _bad_path(where, value, '指到牢外（成員只看得到 /work/…）')
    if '..' in value.replace('\\', '/').split('/'):
        _bad_path(where, value, '有 .. 段（可能跳出專案）')


def check_text(where, value):
    if isinstance(value, str) and HEADER_LIKE.search(value):
        raise TeamError('ForgedHeader', '%s 裡有像信頭的一行（【來信 …】或【人 → …】）；信頭只有郵差能寫，'
                                        '引用別人的信請改寫成「lead 說：…」' % where)


def _all_text(where, value):
    """成員寫的每一段字（遞迴到物件、陣列裡）都不准有像信頭的行：申請裡的字可能被郵差原樣抄進派工信、
    審查信、修正信（goal、facts、judge 的 text、審查的 why、取消的 reason…；astra w2b M2）。"""
    if isinstance(value, str):
        check_text(where, value)
    elif isinstance(value, dict):
        for k, v in value.items():
            _all_text('%s.%s' % (where, k), v)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _all_text('%s[%d]' % (where, i), v)


def recheck(roster, sender, kind, obj):
    """成員／人寫進 outbox 的信與申請，格式驗過之後再驗一次路徑與操作（身分與 may 另有地方驗）。"""
    if sender != HUMAN:
        _all_text('信' if kind == 'letter' else '%s 申請' % obj.get('kind'), obj)
    if kind == 'letter' or obj.get('kind') != 'handoff':
        return
    check_workflow('handoff 的 workflow', obj['workflow'])
    for i, it in enumerate(obj['done_when']):
        w = 'done_when[%d]' % i
        if it['kind'] in ('file_exists', 'table_filled'):
            check_rel_path(w, it['path'])
        elif it['kind'] == 'check' and isinstance(it.get('args'), dict) and 'path' in it['args']:
            check_rel_path(w + '.args', it['args']['path'])
        elif it['kind'] == 'cmd_ok' and fmt.cmd_allowed(roster, it) is None:
            allowed = '；'.join('%s（≤%d 秒）' % (json.dumps(e['run'], ensure_ascii=False), e['timeout_s'])
                               for e in roster.get('cmd_ok', [])) or '（team.json 沒有 cmd_ok 白名單：這隊不跑指令）'
            raise TeamError('NotAllowed', '%s 的 cmd_ok %s 不在 team.json 的白名單（或 timeout_s 超過）；可用的：%s'
                            % (w, json.dumps(it.get('run'), ensure_ascii=False), allowed))
