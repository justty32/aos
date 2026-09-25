"""任務單（交接書）與狀態機（spec/team/tasks.md）。

只有郵差寫任務單：郵差收到申請或信，叫這裡的處理函式；函式改好單子（暫存檔＋rename）、回「後續動作」清單，
郵差照清單一件一件做（寄信、提交驗收、開審查子單、推另一張單），做完一件勾一件。

冪等：每個事件帶 src（觸發它的信／申請／工作的 id）。同一個 src 再來一次＝不改單子、回當初那份後續動作，
所以郵差崩在「改了單、還沒記下後續動作」之間，重跑也不會多做或漏做。
這個檔留開單、取消／改派、審查、信件對單子與期限（各 kind 的處理函式）；
底與狀態機分在 aos_team_task_base／machine，這裡匯出外部用到的名字。
"""
import copy
import datetime
from pathlib import Path

from aos_team_format import BEAT, HUMAN, POST, TASK_ID, TASK_TYPE, TERMINAL, TeamError, check_name, members_by_template, next_number, now_iso, parse_iso

from aos_team_task_base import (
    all_tickets, DEFAULT_ATTEMPTS, describe_item, dispatch, find_by_request, JUDGE, letter, load,
    render_handoff, render_review, save
)
from aos_team_task_machine import step


# ---------------------------------------------------------------- 開單 ----

def _new_ticket(tid, req, sender, assignee, now, **extra):
    t = {'_metainfo': {'_type': TASK_TYPE, '_version': 1}, 'id': tid, 'parent': None,
         'request': req['id'], 'opened_by': sender, 'assignee': assignee, 'rev': 1, 'attempt': 1,
         'max_attempts': req.get('max_attempts') or DEFAULT_ATTEMPTS, 'workflow': req['workflow'],
         'goal': req['goal'], 'facts': req.get('facts'), 'done_when': copy.deepcopy(req['done_when']),
         'status': 'queued', 'waiting_on': None, 'created_at': now, 'updated_at': now, 'deadline': None,
         'review_of': None, 'verify': [], 'review': [], 'history': []}
    t.update(extra)
    if req.get('deadline_minutes'):
        start = parse_iso(now) or datetime.datetime.now(datetime.timezone.utc)
        t['deadline'] = (start + datetime.timedelta(minutes=req['deadline_minutes'])).isoformat(timespec='seconds')
    return t


def on_handoff(lay, roster, req):
    """申請 kind=handoff → 建 t-NNNN（queued）＋派給負責人的 REQUEST。重跑同一份申請回同一張單的同一份動作。"""
    sender, assignee = req['from'], req['assignee']
    old = find_by_request(lay, req['id'])
    if old is not None:
        return copy.deepcopy(old['history'][0].get('effects', []))
    if assignee not in roster['members']:
        raise TeamError('BadAssignee', '%s 不在名冊裡' % assignee)
    if assignee == sender:
        raise TeamError('BadAssignee', '不能派給自己')
    if sender not in (HUMAN, BEAT) and assignee not in roster['members'][sender]['mail_to']:
        raise TeamError('BadAssignee', '%s 不在 %s 的 mail_to 裡' % (assignee, sender))
    now = req.get('at') or now_iso(roster.get('tz'))
    lay.tasks.mkdir(parents=True, exist_ok=True)
    t = _new_ticket(next_number(lay.tasks, 't-'), req, sender, assignee, now)
    effects = [dispatch(t, render_handoff(t))]
    t['history'].append({'at': now, 'event': 'opened', 'src': req['id'], 'by': sender, 'from': None,
                         'to': 'queued', 'effects': copy.deepcopy(effects)})
    save(lay, t)
    return effects


def _opener_or_human(t, sender, what):
    if sender not in (HUMAN, t['opened_by']):
        raise TeamError('NotAllowed', '只有人或開單人（%s）能%s %s' % (t['opened_by'], what, t['id']))


def on_cancel(lay, roster, req):
    t = load(lay, req['task'])
    _opener_or_human(t, req['from'], '取消')
    return step(lay, t['id'], {'type': 'cancel', 'src': req['id'], 'by': req['from'], 'reason': req.get('reason'),
                               'at': req.get('at')})


def on_reassign(lay, roster, req):
    t = load(lay, req['task'])
    _opener_or_human(t, req['from'], '改派')
    if req['assignee'] not in roster['members']:
        raise TeamError('BadAssignee', '%s 不在名冊裡' % req['assignee'])
    if t['parent']:
        raise TeamError('NotAllowed', '%s 是審查子單，不能改派' % t['id'])
    return step(lay, t['id'], {'type': 'reassign', 'src': req['id'], 'by': req['from'],
                               'assignee': req['assignee'], 'at': req.get('at')})


# ---------------------------------------------------------------- 審查 ----

def open_review(lay, roster, tid, src, rev, attempt, now=None):
    """效果 {"do": "open_review", "task", "rev", "attempt"} 的做法：替那一次（rev／attempt）開審查子單。

    冪等：同一個 src 開過的子單＝回它的派送動作；父單已經不是那一次的 reviewing（改派、取消…）＝
    在父單記一筆 ignored（同 src 重播也回空）；沒有 reviewer＝父單 blocked。
    """
    for t in all_tickets(lay):
        if t.get('parent') == tid and t['history'] and t['history'][0].get('src') == src:
            return copy.deepcopy(t['history'][0].get('effects', []))
    parent = load(lay, tid)
    for h in parent['history']:
        if h.get('src') == src:
            return copy.deepcopy(h.get('effects', []))
    if parent['status'] != 'reviewing' or parent['rev'] != rev or parent['attempt'] != attempt:
        return step(lay, tid, {'type': 'stale_review', 'src': src, 'rev': rev, 'attempt': attempt}, now)
    for t in all_tickets(lay):
        ro = t.get('review_of') or {}
        if t.get('parent') == tid and ro.get('rev') == rev and ro.get('attempt') == attempt:
            return copy.deepcopy(t['history'][0].get('effects', []))
    reviewers = members_by_template(roster, 'reviewer')
    if not reviewers:
        return step(lay, tid, {'type': 'no_reviewer', 'src': src}, now)
    judges = [(i, it) for i, it in enumerate(parent['done_when']) if it['kind'] == JUDGE]
    k = 1 + sum(1 for p in Path(lay.tasks).glob(tid + '.r*.json'))
    now = now or now_iso(roster.get('tz'))
    req = {'id': src, 'workflow': '審查', 'goal': parent['goal'], 'done_when': [it for _, it in judges],
           'max_attempts': 1}
    sub = _new_ticket('%s.r%d' % (tid, k), req, POST, reviewers[0], now, parent=tid,
                      review_of={'task': tid, 'rev': rev, 'attempt': attempt, 'indices': [i for i, _ in judges]})
    effects = [dispatch(sub, render_review(sub, parent))]
    sub['history'].append({'at': now, 'event': 'opened', 'src': src, 'by': POST, 'from': None, 'to': 'queued',
                           'effects': copy.deepcopy(effects)})
    save(lay, sub)
    return effects


def on_review_result(lay, roster, req):
    """審查員交回逐條結果：子單 done，父單收到 reviewed（全 PASS 才過）。"""
    sub = load(lay, req['task'])
    if not sub.get('parent') or not sub.get('review_of'):
        raise TeamError('NotAReview', '%s 不是審查子單' % sub['id'])
    old = [h for h in sub['history'] if h.get('src') == req['id']]
    if old:
        return copy.deepcopy(old[0].get('effects', []))
    if req['from'] != sub['assignee']:
        raise TeamError('NotAllowed', '%s 的審查員是 %s，不是 %s' % (sub['id'], sub['assignee'], req['from']))
    if sub['status'] in TERMINAL:
        raise TeamError('Closed', '%s 已經 %s' % (sub['id'], sub['status']))
    ro = sub['review_of']
    # （09-24 W2C 修）i 用父單的原編號，不是子單裡 0..n 的位置——跟 render_review、task show 顯示的一致。
    want = set(ro['indices'])
    got = {it['i'] for it in req['items']}
    if got != want:
        raise TeamError('BadItems', '%s 要逐條回第 %s 條（收到 %s）'
                        % (sub['id'], '、'.join(map(str, sorted(want))), '、'.join(map(str, sorted(got))) or '無'))
    ok = all(it['pass'] for it in req['items'])
    items = sorted(req['items'], key=lambda x: x['i'])
    now = req.get('at') or now_iso(roster.get('tz'))
    effects = [{'do': 'step', 'task': ro['task'],
                'event': {'type': 'reviewed', 'src': req['id'], 'by': req['from'], 'rev': ro['rev'],
                          'attempt': ro['attempt'], 'pass': ok, 'items': items, 'at': now}}]
    sub['history'].append({'at': now, 'event': 'review_result', 'src': req['id'], 'by': req['from'],
                           'from': sub['status'], 'to': 'done', 'effects': copy.deepcopy(effects)})
    sub['status'], sub['updated_at'] = 'done', now
    sub['review'] = [{'rev': 1, 'attempt': 1, 'pass': ok, 'items': req['items'], 'at': now, 'by': req['from']}]
    save(lay, sub)
    return effects


# ---------------------------------------------------------- 信件對單子 ----

def on_letter(lay, roster, ltr):
    """郵差每處理一封成員或人的信都叫一次：reply_to 是單號才有事。

    負責人寄的＝回報（DONE／BLOCKED／NEEDS-USER／FAILED／PROGRESS）；
    開單人或人寄給負責人的 REQUEST＝恢復（blocked／waiting_user → working）。
    """
    tid = ltr.get('reply_to')
    if not isinstance(tid, str) or not TASK_ID.match(tid) or not lay.task(tid).exists():
        return []
    t = load(lay, tid)
    base = {'src': ltr['id'], 'by': ltr['from'], 'at': ltr.get('at')}
    if ltr['from'] == t['assignee'] or ltr['from'] not in (HUMAN, t['opened_by']):   # 別人冒回報＝記下、不改
        return step(lay, tid, dict(base, type='report', status=ltr['status'], rev=ltr.get('rev'),
                                   to=ltr['to'], note=ltr['text'][:200]))
    if ltr['from'] in (HUMAN, t['opened_by']) and ltr['to'] == t['assignee'] and ltr['status'] == 'REQUEST':
        return step(lay, tid, dict(base, type='resume', note=ltr['text'][:200]))
    return []


def letter_delivered(lay, ltr, dispatch_info):
    """派工信（後續動作帶 dispatch 的那封）投進負責人 input/ 之後叫：queued → sent。"""
    return _mail_event(lay, ltr, dispatch_info, 'delivered')


def letter_picked_up(lay, ltr, dispatch_info):
    """那封派工信從負責人 input/ 消失（被收走）之後叫：sent → working。"""
    return _mail_event(lay, ltr, dispatch_info, 'picked_up')


def _mail_event(lay, ltr, info, typ):
    """只認派工信：dispatch 的 task／rev／attempt 要對得上目前那一次、收件人是負責人；其他信一律不推狀態。"""
    if not isinstance(info, dict) or info.get('task') != ltr.get('reply_to'):
        return []
    tid = info['task']
    if not isinstance(tid, str) or not TASK_ID.match(tid) or not lay.task(tid).exists():
        return []
    t = load(lay, tid)
    if ltr.get('to') != t['assignee']:
        return []
    return step(lay, tid, {'type': typ, 'src': '%s:%s' % (typ, ltr['id']), 'rev': info.get('rev'),
                           'attempt': info.get('attempt')})


def due_deadlines(lay, now=None):
    """過了期限還沒結束的單：回 [(單號, expire 事件)]，**不寫檔**。

    郵差的做法：先把事件記進自己的紀錄，再 step(lay, 單號, 事件)、做回來的動作；崩了重跑同一個事件
    （同 src）會回同一份動作——單子已經 failed 也一樣，所以通知不會丟。
    """
    now_s = now or now_iso()
    now_t = parse_iso(now_s)
    out = []
    for t in all_tickets(lay):
        dl = parse_iso(t.get('deadline')) if t.get('deadline') else None
        if dl is not None and now_t is not None and t['status'] not in TERMINAL and now_t > dl:
            out.append((t['id'], {'type': 'expire', 'src': 'expire:%s:%d:%s' % (t['id'], t['rev'], t['deadline']),
                                  'at': now_s}))
    return out


def check_deadlines(lay, now=None):
    """due_deadlines＋馬上 step（測試與人用；郵差照 due_deadlines 的做法）。回 [(單號, 後續動作)]。"""
    return [(tid, step(lay, tid, ev, ev['at'])) for tid, ev in due_deadlines(lay, now)]


def check_member(roster, name):
    check_name(name, 'assignee')
    if name not in roster['members']:
        raise TeamError('BadAssignee', '%s 不在名冊裡' % name)
    return name


__all__ = ['Layout', 'apply', 'step', 'load', 'save', 'all_tickets', 'on_handoff', 'on_cancel', 'on_reassign',
           'on_review_result', 'open_review', 'on_letter', 'letter_delivered', 'letter_picked_up',
           'due_deadlines', 'check_deadlines', 'render_handoff', 'dispatch']
