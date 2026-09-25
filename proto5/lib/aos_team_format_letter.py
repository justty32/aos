"""信、申請、任務單與問題的讀驗：信、done_when、各 kind 申請的欄位、outbox 檔、信頭與投遞去重、任務單與問題、下一個編號。"""
import json
import os
from pathlib import Path
import re

from aos_team_format_base import (
    _int, _metainfo, _obj, _opt_str, _str, _unknown, ANY_ID, bad, BEAT, check_name,
    CMD_TIMEOUT_MAX, DONE_KINDS, HUMAN, OUTBOX_ID, QUESTION_ID, QUESTION_TYPE, SENDER_LABEL,
    STATUSES, TASK_ID, TASK_TYPE, TEXT_LIMIT
)
from aos_team_format_io import read_json, short_time
from aos_team_format_cmd import validate_cmd


# ------------------------------------------------------------ 信與申請 ----

LETTER_KEYS = ('id', 'from', 'to', 'status', 'reply_to', 'rev', 'text', 'at')


def validate_letter(obj, where='letter'):
    _obj(obj, where)
    _unknown(obj, LETTER_KEYS, where)
    _str(obj.get('id'), where + '.id')
    if not ANY_ID.match(obj['id']):
        bad(where + '.id', 'id %r 只能用英數與 . _ ~ -' % obj['id'])
    _str(obj.get('from'), where + '.from')
    _str(obj.get('to'), where + '.to')
    if obj.get('status') not in STATUSES:
        bad(where + '.status', '%r 不是六個之一：%s' % (obj.get('status'), '、'.join(STATUSES)), 'BadStatus')
    _opt_str(obj.get('reply_to'), where + '.reply_to')
    if obj.get('rev') is not None:
        _int(obj['rev'], where + '.rev', 1)
    _str(obj.get('text'), where + '.text', limit=TEXT_LIMIT)
    _str(obj.get('at'), where + '.at')
    return obj


def validate_done_when(items, where='done_when'):
    if not isinstance(items, list) or not items:
        bad(where, '要是非空陣列')
    for i, it in enumerate(items):
        w = '%s[%d]' % (where, i)
        _obj(it, w)
        kind = it.get('kind')
        if kind not in DONE_KINDS:
            bad(w + '.kind', '%r 不是 %s 之一' % (kind, '、'.join(DONE_KINDS)))
        if kind in ('file_exists', 'table_filled'):
            _str(it.get('path'), w + '.path')
        elif kind == 'check':
            _str(it.get('name'), w + '.name')
            if 'args' in it:
                _obj(it['args'], w + '.args')
        elif kind == 'cmd_ok':
            _unknown(it, ('kind', 'run', 'timeout_s'), w)
            validate_cmd(it.get('run'), w + '.run')
            if 'timeout_s' in it:
                _int(it['timeout_s'], w + '.timeout_s', 1, CMD_TIMEOUT_MAX)
        else:
            _str(it.get('text'), w + '.text', limit=2000)
    return items


def _handoff_body(obj, where):
    check_name(obj.get('assignee'), where + '.assignee')
    _str(obj.get('workflow'), where + '.workflow')
    _str(obj.get('goal'), where + '.goal', limit=TEXT_LIMIT)
    _opt_str(obj.get('facts'), where + '.facts')
    validate_done_when(obj.get('done_when'), where + '.done_when')
    if obj.get('max_attempts') is not None:
        _int(obj['max_attempts'], where + '.max_attempts', 1, 10)
    if obj.get('deadline_minutes') is not None:
        _int(obj['deadline_minutes'], where + '.deadline_minutes', 1, 7 * 24 * 60)


ASK_TAGS = ('access', 'persona')   # 借用 kind=ask 的申請種類（09-24 W2C）：aos-team wait ls 靠它挑前綴，不猜字串


def _ask_body(obj, where):
    _str(obj.get('question'), where + '.question', limit=4000)
    opts = obj.get('options')
    if opts is not None:
        if not isinstance(opts, list) or not opts or not all(isinstance(o, str) and o.strip() for o in opts):
            bad(where + '.options', '要是非空字串的陣列')
    default = _opt_str(obj.get('default'), where + '.default')
    if default is not None and opts is not None and default not in opts:
        bad(where + '.default', '%r 不在 options 裡' % default)
    _opt_str(obj.get('reply_to'), where + '.reply_to')
    tag = obj.get('tag')
    if tag is not None and tag not in ASK_TAGS:
        bad(where + '.tag', '要是 %s 之一' % '／'.join(ASK_TAGS))


def _answer_body(obj, where):
    q = _str(obj.get('q'), where + '.q')
    if not QUESTION_ID.match(q):
        bad(where + '.q', '%r 不是問題編號（q-0001 這種）' % q)
    _str(obj.get('text'), where + '.text', limit=TEXT_LIMIT)


def _task_ref(obj, where, key='task'):
    t = _str(obj.get(key), '%s.%s' % (where, key))
    if not TASK_ID.match(t):
        bad('%s.%s' % (where, key), '%r 不是任務單號（t-0001 或審查子單 t-0001.r1）' % t)


def _cancel_body(obj, where):
    _task_ref(obj, where)
    _opt_str(obj.get('reason'), where + '.reason')


def _reassign_body(obj, where):
    _task_ref(obj, where)
    check_name(obj.get('assignee'), where + '.assignee')


def _review_body(obj, where):
    _task_ref(obj, where)
    items = obj.get('items')
    if not isinstance(items, list) or not items:
        bad(where + '.items', '要是非空陣列')
    seen = set()
    for k, it in enumerate(items):
        w = '%s.items[%d]' % (where, k)
        _obj(it, w)
        _int(it.get('i'), w + '.i', 0)
        if it['i'] in seen:
            bad(w + '.i', '第 %d 條重複' % it['i'])
        seen.add(it['i'])
        if not isinstance(it.get('pass'), bool):
            bad(w + '.pass', '要是 true／false')
        _str(it.get('why'), w + '.why', limit=2000)


# kind → (這個 kind 自己的欄位, 驗法)。第 2、4 隊的 kind 在自己的模組驗，這裡只列名字（body=None：只驗共同欄位）。
REQUEST_KINDS = {
    'handoff': (('assignee', 'workflow', 'goal', 'facts', 'done_when', 'max_attempts', 'deadline_minutes'),
                _handoff_body),
    'ask': (('question', 'options', 'default', 'reply_to', 'tag'), _ask_body),
    'answer': (('q', 'text'), _answer_body),
    'cancel': (('task', 'reason'), _cancel_body),
    'reassign': (('task', 'assignee'), _reassign_body),
    'review_result': (('task', 'items'), _review_body),
}
REQUEST_COMMON = ('id', 'from', 'kind', 'at')


def validate_request(obj, where='request'):
    _obj(obj, where)
    kind = obj.get('kind')
    if not isinstance(kind, str):
        bad(where + '.kind', '要是字串', 'UnknownKind')
    if kind not in REQUEST_KINDS:
        from aos_team_requests import KINDS   # 別隊登記的 kind 也認
        if kind not in KINDS:
            bad(where + '.kind', '不認得的申請種類 %r' % (kind,), 'UnknownKind')
        _str(obj.get('id'), where + '.id')
        _str(obj.get('from'), where + '.from')
        _str(obj.get('at'), where + '.at')
        return obj
    keys, body = REQUEST_KINDS[kind]
    _unknown(obj, REQUEST_COMMON + keys, where)
    _str(obj.get('id'), where + '.id')
    if not ANY_ID.match(obj['id']):
        bad(where + '.id', 'id %r 只能用英數與 . _ ~ -' % obj['id'])
    _str(obj.get('from'), where + '.from')
    _str(obj.get('at'), where + '.at')
    body(obj, where)
    return obj


def read_outbox_file(path, roster):
    """郵差讀 team/outbox/<寄件人>/<id>.json：回 ('letter'|'request', obj)。

    身分看檔在哪個 outbox（資料夾名），信裡的 from 只是抄寫、對不上就 NotSender；
    檔名要是 <id>.json 且 id 的寄件人段＝資料夾名；信的 to 要在寄件人的 mail_to（human 可寄給任何成員）。
    """
    path = Path(path)
    sender = path.parent.name
    # 退信會寄回給寄件人（在牢裡看不到主機路徑）：訊息裡只寫團隊資料夾裡的相對位置（wall-r1 試玩）
    where = 'outbox/%s/%s' % (sender, path.name)
    if sender not in (HUMAN, BEAT) and sender not in roster['members']:
        bad(where, '寄件人 %s 不在名冊裡' % sender, 'NotSender')
    stem = path.name[:-5] if path.name.endswith('.json') else path.name
    m = OUTBOX_ID.match(stem)
    if not m or m.group(1) != sender:
        bad(where, '檔名要是 <epoch ns>-<pid>-%s.json' % sender, 'BadId')
    obj = read_json(path, where)
    _obj(obj, where)
    if obj.get('id') != stem:
        bad(where + '.id', 'id 要跟檔名一樣（%s）' % stem, 'BadId')
    if obj.get('from') != sender:
        bad(where + '.from', '信在 %s 的 outbox，from 卻寫 %r' % (sender, obj.get('from')), 'NotSender')
    if 'kind' in obj:
        validate_request(obj, where)
        return 'request', obj
    validate_letter(obj, where)
    to = obj['to']
    if to == BEAT and sender in roster['members']:
        pass                              # 誰都能回信給心跳（它派的例行單回報 DONE 用；郵差只記下、不投）
    elif sender == BEAT:
        if to != HUMAN and to not in roster['members']:
            bad(where + '.to', '%s 不在名冊裡' % to, 'BadRecipient')
    elif sender == HUMAN:
        if to not in roster['members']:
            bad(where + '.to', '%s 不在名冊裡' % to, 'BadRecipient')
    elif to not in roster['members'][sender]['mail_to']:
        bad(where + '.to', '%s 不能寄給 %s（mail_to：%s）'
            % (sender, to, '、'.join(roster['members'][sender]['mail_to']) or '（空）'), 'BadRecipient')
    return 'letter', obj


# ------------------------------------------------------------------ 信頭 ----

def render_header(letter, tz=None):
    """收件人看到的第一行：【來信 lead → worker-1 · REQUEST · t-0007 rev1 · 09-25 10:03】。
    人回答問題：【人 → worker-1 · 回覆 q-0003 · 09-25 10:03】。"""
    when = short_time(letter.get('at'), tz)
    reply = letter.get('reply_to')
    if letter.get('from') == HUMAN and isinstance(reply, str) and QUESTION_ID.match(reply):
        return '【人 → %s · 回覆 %s · %s】' % (letter['to'], reply, when)
    ref = ''
    if reply:
        ref = ' · %s%s' % (reply, ' rev%d' % letter['rev'] if letter.get('rev') else '')
    sender = SENDER_LABEL.get(letter.get('from'), letter.get('from'))
    return '【來信 %s → %s · %s%s · %s】' % (sender, letter['to'], letter['status'], ref, when)


def mail_message(letter, tz=None):
    """投進收件人 input/mail-<id>.json 的內容：一則 user 訊息，第一行是信頭。"""
    return {'role': 'user', 'content': render_header(letter, tz) + '\n' + letter['text']}


def mail_filename(letter_id):
    return 'mail-%s.json' % letter_id


def already_delivered(member_home, filename):
    """投之前查「這封是不是其實已經投過」（spec/team/mail.md〈去重〉）：回 None（沒投過）或說明在哪。

    三處都算投過：還在 input/<檔名>；已被收走、封存在 input/done/<檔名>.<消費 id>.done；
    收件人正在收（state.json 的 intake.files 或 consuming 的 src 是它）。
    """
    inbox = Path(member_home) / 'input'
    if (inbox / filename).exists():
        return 'input'
    done = inbox / 'done'
    try:
        if any(p.name.startswith(filename + '.') and p.name.endswith('.done') for p in done.iterdir()):
            return 'done'
    except FileNotFoundError:
        pass
    try:
        st = json.loads((Path(member_home) / 'state.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        st = {}
    pairs = []
    if isinstance(st, dict):
        if isinstance(st.get('intake'), dict) and isinstance(st['intake'].get('files'), list):
            pairs += st['intake']['files']
        if isinstance(st.get('consuming'), list):
            pairs += st['consuming']
    for pair in pairs:
        if isinstance(pair, dict) and isinstance(pair.get('src'), str) and os.path.basename(pair['src']) == filename:
            return 'intake'
    return None


# -------------------------------------------------------------- 任務與問題 ----

TICKET_STATUSES = ('queued', 'sent', 'working', 'verifying', 'reviewing', 'done',
                   'blocked', 'waiting_user', 'failed', 'cancelled')
TERMINAL = ('done', 'failed', 'cancelled')
TICKET_KEYS = ('_metainfo', 'id', 'parent', 'request', 'opened_by', 'assignee', 'rev', 'attempt',
               'max_attempts', 'workflow', 'goal', 'facts', 'done_when', 'status', 'waiting_on',
               'created_at', 'updated_at', 'deadline', 'review_of', 'verify', 'review', 'history')


def validate_ticket(obj, where='task'):
    _obj(obj, where)
    _unknown(obj, TICKET_KEYS, where)
    _metainfo(obj, TASK_TYPE, where)
    tid = _str(obj.get('id'), where + '.id')
    if not TASK_ID.match(tid):
        bad(where + '.id', '%r 不是任務單號' % tid)
    if obj.get('status') not in TICKET_STATUSES:
        bad(where + '.status', '%r 不是 %s 之一' % (obj.get('status'), '、'.join(TICKET_STATUSES)))
    check_name(obj.get('assignee'), where + '.assignee')
    for k in ('rev', 'attempt', 'max_attempts'):
        _int(obj.get(k), '%s.%s' % (where, k), 1)
    validate_done_when(obj.get('done_when'), where + '.done_when')
    if not isinstance(obj.get('history'), list):
        bad(where + '.history', '要是陣列')
    return obj


def validate_question(obj, where='question'):
    _obj(obj, where)
    _metainfo(obj, QUESTION_TYPE, where)
    qid = _str(obj.get('id'), where + '.id')
    if not QUESTION_ID.match(qid):
        bad(where + '.id', '%r 不是問題編號' % qid)
    if obj.get('status') not in ('open', 'answered', 'cancelled'):
        bad(where + '.status', '要是 open／answered／cancelled')
    _str(obj.get('from'), where + '.from')
    _str(obj.get('question'), where + '.question')
    return obj


def next_number(folder, prefix):
    """資料夾裡 <prefix>NNNN.json 的下一號（只有一個寫的人：郵差）。"""
    top = 0
    pat = re.compile(re.escape(prefix) + r'([0-9]+)\.json\Z')
    try:
        for p in Path(folder).iterdir():
            m = pat.match(p.name)
            if m:
                top = max(top, int(m.group(1)))
    except FileNotFoundError:
        pass
    return '%s%04d' % (prefix, top + 1)
