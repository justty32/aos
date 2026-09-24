"""任務單（交接書）與狀態機（spec/team/tasks.md）。

只有郵差寫任務單：郵差收到申請或信，叫這裡的處理函式；函式改好單子（暫存檔＋rename）、回「後續動作」清單，
郵差照清單一件一件做（寄信、提交驗收、開審查子單、推另一張單），做完一件勾一件。

冪等：每個事件帶 src（觸發它的信／申請／工作的 id）。同一個 src 再來一次＝不改單子、回當初那份後續動作，
所以郵差崩在「改了單、還沒記下後續動作」之間，重跑也不會多做或漏做。
"""
import copy
import datetime
from pathlib import Path

from aos_team_format import (HUMAN, POST, TASK_ID, TASK_TYPE, TERMINAL, TeamError, Layout, check_name,
                             json_files, members_by_template, next_number, now_iso, parse_iso, read_json,
                             validate_ticket, write_json)

JUDGE = 'judge'
DEFAULT_ATTEMPTS = 3
NO_FLOW = ('無', '-', 'none', '（無）')


# ------------------------------------------------------------------ 讀寫 ----

def load(lay, tid):
    if not isinstance(tid, str) or not TASK_ID.match(tid):
        raise TeamError('BadTask', '%r 不是任務單號' % (tid,))
    path = lay.task(tid)
    if not path.exists():
        raise TeamError('NoSuchTask', '沒有任務單 %s（%s）' % (tid, path))
    return validate_ticket(read_json(path), str(path))


def save(lay, ticket):
    write_json(lay.task(ticket['id']), ticket, indent=2)


def all_tickets(lay):
    """(單號排序) 全部任務單；壞檔略過（aos-team task ls 另外報）。"""
    out = []
    for p in json_files(lay.tasks):
        try:
            out.append(validate_ticket(read_json(p), str(p)))
        except TeamError:
            continue
    return out


def find_by_request(lay, request_id):
    for t in all_tickets(lay):
        if t.get('request') == request_id:
            return t
    return None


# ------------------------------------------------------------------ 文字 ----

def describe_item(it):
    kind = it['kind']
    if kind == 'file_exists':
        return '檔案在：%s' % it['path']
    if kind == 'table_filled':
        extra = {k: v for k, v in it.items() if k not in ('kind', 'path')}
        return '表格填滿：%s%s' % (it['path'], ' %s' % extra if extra else '')
    if kind == 'check':
        return '檢查器 %s%s' % (it['name'], ' %s' % it['args'] if it.get('args') else '')
    return '（審查員判）%s' % it['text']


def render_handoff(t):
    """派給負責人的那封 REQUEST 的內文。"""
    reply = t['opened_by'] if t['opened_by'] not in (POST,) else HUMAN
    flow = t['workflow'].strip()
    lines = ['任務 %s（rev%d，第 %d/%d 次）：%s' % (t['id'], t['rev'], t['attempt'], t['max_attempts'], t['goal']),
             '沒有指定工作流，照目標與事實做' if flow in NO_FLOW else '照這份工作流做：%s' % flow,
             '事實：%s' % (t.get('facts') or '無')]
    lines.append('驗收（你回 DONE 之後自動跑，機械的不用你自己宣稱）：')
    lines += ['  %d. %s' % (i, describe_item(it)) for i, it in enumerate(t['done_when'])]
    lines.append('做完用 team_say 回 DONE 給 %s，reply_to "%s"、rev %d；卡住回 BLOCKED 說原因；'
                 '要人決定用 ask_human。回完這一輪就結束，不用等。' % (reply, t['id'], t['rev']))
    return '\n'.join(lines)


def render_review(sub, parent):
    lines = ['審查單 %s：替 %s（rev%d，第 %d 次）判下面幾條；機械檢查已經過了。'
             % (sub['id'], parent['id'], sub['review_of']['rev'], sub['review_of']['attempt']),
             '任務目標：%s' % parent['goal']]
    lines += ['  %d. %s' % (i, it['text']) for i, it in enumerate(sub['done_when'])]
    lines.append('用 review_result 逐條回：{"task": "%s", "items": [{"i": 0, "pass": true, "why": "一句理由"}, …]}；'
                 '每一條都要回。回完這一輪就結束。' % sub['id'])
    return '\n'.join(lines)


def _results_text(results):
    """驗收或審查的逐條結果 → 給負責人看的幾行。results：[{i, pass|result, why|message}]。"""
    lines = []
    for r in results or []:
        ok = r.get('pass')
        if ok is None:
            ok = r.get('result') == 'pass'
        lines.append('  %s %s. %s' % ('過' if ok else '不過', r.get('i', '?'), r.get('why') or r.get('message') or ''))
    return '\n'.join(lines)


# ------------------------------------------------------------------ 效果 ----

def letter(to, status, t, text):
    return {'do': 'letter', 'to': to, 'status': status, 'reply_to': t['id'], 'rev': t['rev'], 'text': text}


def _notify(t, status, text, skip=()):
    """通知開單人與人（去掉重複、去掉 skip 裡的）。"""
    out = []
    for who in (t['opened_by'], HUMAN):
        who = HUMAN if who == POST else who
        if who in skip or any(e['to'] == who for e in out):
            continue
        out.append(letter(who, status, t, text))
    return out


# ---------------------------------------------------------------- 狀態機 ----

def apply(t, ev, now=None):
    """把一個事件套到單子上（原地改 t）。回 (有沒有改, 後續動作)。

    ev：{"type", "src", "by"?, "at"?, …}。同一個 src 已在 history＝回當初的後續動作、不改。
    """
    for h in t['history']:
        if h.get('src') == ev['src']:
            return False, copy.deepcopy(h.get('effects', []))
    now = now or ev.get('at') or now_iso()
    typ, st = ev['type'], t['status']
    entry = {'at': now, 'event': typ, 'src': ev['src'], 'by': ev.get('by'), 'from': st, 'to': st}
    effects = []

    def move(new, note=None, **changes):
        t.update(changes)
        entry['to'] = t['status'] = new
        if note:
            entry['note'] = note

    def ignore(why):
        entry['event'] = 'ignored:' + typ
        entry['note'] = why

    rev_ok = ev.get('rev') in (None, t['rev'])
    if typ == 'reassign':
        if st in ('done', 'cancelled'):
            ignore('已經 %s，不能改派' % st)
        else:
            old = t['assignee']
            t['rev'] += 1
            move('queued', '改派 %s → %s' % (old, ev['assignee']), assignee=ev['assignee'], attempt=1,
                 waiting_on=None)
            if old != ev['assignee'] and st not in ('queued', 'failed'):
                effects.append(letter(old, 'REQUEST', t, '%s 改派給 %s 了，停下這件，不用再回報。' % (t['id'], ev['assignee'])))
            effects.append(letter(t['assignee'], 'REQUEST', t, render_handoff(t)))
    elif st in TERMINAL:
        ignore('單子已經 %s' % st)
    elif typ == 'delivered':
        if st == 'queued' and rev_ok and ev.get('attempt') in (None, t['attempt']):
            move('sent')
        else:
            ignore('狀態 %s／rev 對不上，不改' % st)
    elif typ == 'picked_up':
        if st == 'sent' and rev_ok:
            move('working')
        else:
            ignore('狀態 %s，不改' % st)
    elif typ == 'report':
        status = ev.get('status')
        if ev.get('by') != t['assignee']:
            ignore('%s 不是負責人（%s），只記下' % (ev.get('by'), t['assignee']))
        elif not rev_ok or ev.get('rev') is None:
            ignore('rev %s 對不上目前的 rev%d，只記下' % (ev.get('rev'), t['rev']))
        elif status == 'DONE' and t.get('parent'):
            ignore('審查子單要用 review_result 逐條回，DONE 信只記下')
        elif status == 'DONE' and st in ('sent', 'working', 'blocked', 'waiting_user'):
            mech = [it for it in t['done_when'] if it['kind'] != JUDGE]
            if mech:
                move('verifying', waiting_on=None)
                effects.append({'do': 'verify', 'task': t['id'], 'rev': t['rev'], 'attempt': t['attempt']})
            elif any(it['kind'] == JUDGE for it in t['done_when']):
                move('reviewing', waiting_on=None)
                effects.append({'do': 'open_review', 'task': t['id'], 'rev': t['rev'], 'attempt': t['attempt']})
            else:
                move('done', waiting_on=None)
                effects += _notify(t, 'DONE', '%s 完成：%s' % (t['id'], t['goal']))
        elif status == 'BLOCKED' and st in ('sent', 'working', 'waiting_user'):
            move('blocked', ev.get('note'), waiting_on=t['opened_by'] if t['opened_by'] != POST else HUMAN)
        elif status == 'NEEDS-USER' and st in ('sent', 'working', 'blocked'):
            move('waiting_user', ev.get('note'), waiting_on=HUMAN)
        elif status == 'FAILED':
            move('failed', ev.get('note'), waiting_on=None)
            effects += _notify(t, 'FAILED', '%s 負責人 %s 回報 FAILED：%s' % (t['id'], t['assignee'], ev.get('note') or ''),
                               skip=(ev.get('to'),))
        elif status in ('PROGRESS', 'REQUEST'):
            entry['event'] = 'progress'
            entry['note'] = ev.get('note')
        else:
            ignore('%s 在狀態 %s 不改' % (status, st))
    elif typ == 'needs_user':
        if ev.get('by') == t['assignee'] and st in ('sent', 'working', 'blocked'):
            move('waiting_user', '等 %s' % ev.get('q'), waiting_on=ev.get('q') or HUMAN)
        else:
            ignore('不是負責人或狀態 %s' % st)
    elif typ == 'resume':
        if st in ('blocked', 'waiting_user'):
            move('working', ev.get('note'), waiting_on=None)
        else:
            ignore('狀態 %s 不用恢復' % st)
    elif typ == 'verified':
        if st != 'verifying' or not rev_ok or ev.get('attempt') not in (None, t['attempt']):
            ignore('不是這一次的驗收（狀態 %s）' % st)
        else:
            t.setdefault('verify', []).append({'rev': t['rev'], 'attempt': t['attempt'], 'pass': bool(ev['pass']),
                                               'results': ev.get('results', []), 'at': now})
            if not ev['pass']:
                effects += _retry(t, move, '機械驗收沒過', ev.get('results'))
            elif any(it['kind'] == JUDGE for it in t['done_when']):
                move('reviewing')
                effects.append({'do': 'open_review', 'task': t['id'], 'rev': t['rev'], 'attempt': t['attempt']})
            else:
                move('done')
                effects += _notify(t, 'DONE', '%s 完成：%s' % (t['id'], t['goal']))
    elif typ == 'reviewed':
        if st != 'reviewing' or not rev_ok or ev.get('attempt') not in (None, t['attempt']):
            ignore('不是這一次的審查（狀態 %s）' % st)
        else:
            t.setdefault('review', []).append({'rev': t['rev'], 'attempt': t['attempt'], 'pass': bool(ev['pass']),
                                               'items': ev.get('items', []), 'at': now, 'by': ev.get('by')})
            if ev['pass']:
                move('done')
                effects += _notify(t, 'DONE', '%s 完成（審查通過）：%s' % (t['id'], t['goal']))
            else:
                effects += _retry(t, move, '審查沒過', ev.get('items'))
    elif typ == 'no_reviewer':
        move('blocked', '有 judge 條目，但隊裡沒有 reviewer', waiting_on=HUMAN)
        effects += _notify(t, 'BLOCKED', '%s 有要審查員判的條目，但名冊裡沒有 template=reviewer 的成員' % t['id'])
    elif typ == 'cancel':
        move('cancelled', ev.get('reason'), waiting_on=None)
        if st != 'queued':
            effects.append(letter(t['assignee'], 'REQUEST', t, '取消 %s%s：停下這件，不用再回報。'
                                  % (t['id'], '（%s）' % ev['reason'] if ev.get('reason') else '')))
    elif typ == 'expire':
        move('failed', '超過期限 %s' % t.get('deadline'), waiting_on=None)
        effects += _notify(t, 'FAILED', '%s 超過期限（%s）還沒完成，停了。' % (t['id'], t.get('deadline')))
    else:
        raise TeamError('BadEvent', '不認得的事件 %r' % typ)
    entry['effects'] = copy.deepcopy(effects)
    t['history'].append(entry)
    t['updated_at'] = now
    return True, effects


def _retry(t, move, why, results):
    """驗收或審查沒過：還有次數＝attempt+1、回 queued、寄修正；沒次數＝failed、通知開單人與人。"""
    detail = _results_text(results)
    if t['attempt'] < t['max_attempts']:
        move('queued', why, attempt=t['attempt'] + 1)
        text = ('REQUEST 修正 %s（第 %d/%d 次）：%s\n%s\n改好再用 team_say 回 DONE（reply_to "%s"、rev %d）。'
                % (t['id'], t['attempt'], t['max_attempts'], why, detail, t['id'], t['rev']))
        return [letter(t['assignee'], 'REQUEST', t, text)]
    move('failed', '%s，次數用完（%d 次）' % (why, t['max_attempts']))
    return _notify(t, 'FAILED', '%s %s，%d 次都沒過，停了。\n%s' % (t['id'], why, t['max_attempts'], detail))


def step(lay, tid, ev, now=None):
    """讀單、套事件、有改就寫回；回後續動作。"""
    t = load(lay, tid)
    before = copy.deepcopy(t)
    _, effects = apply(t, ev, now)
    if t != before:
        save(lay, t)
    return effects


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
    if sender != HUMAN and assignee not in roster['members'][sender]['mail_to']:
        raise TeamError('BadAssignee', '%s 不在 %s 的 mail_to 裡' % (assignee, sender))
    now = req.get('at') or now_iso(roster.get('tz'))
    lay.tasks.mkdir(parents=True, exist_ok=True)
    t = _new_ticket(next_number(lay.tasks, 't-'), req, sender, assignee, now)
    effects = [letter(assignee, 'REQUEST', t, render_handoff(t))]
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

def open_review(lay, roster, tid, src, now=None):
    """效果 open_review 的做法：替 tid 目前的 rev／attempt 開審查子單（沒有 reviewer＝單子 blocked）。

    冪等：同一個 rev／attempt 已經開過＝回那張子單的派送動作。
    """
    parent = load(lay, tid)
    rev, attempt = parent['rev'], parent['attempt']
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
    effects = [letter(sub['assignee'], 'REQUEST', sub, render_review(sub, parent))]
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
    want = set(range(len(sub['done_when'])))
    got = {it['i'] for it in req['items']}
    if got != want:
        raise TeamError('BadItems', '%s 要逐條回第 %s 條（收到 %s）'
                        % (sub['id'], '、'.join(map(str, sorted(want))), '、'.join(map(str, sorted(got))) or '無'))
    ok = all(it['pass'] for it in req['items'])
    ro = sub['review_of']
    items = [dict(it, i=ro['indices'][it['i']]) for it in sorted(req['items'], key=lambda x: x['i'])]
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


def letter_delivered(lay, ltr):
    """信投進收件人 input/ 之後叫：給負責人的 REQUEST 投到了＝queued → sent。"""
    return _mail_event(lay, ltr, 'delivered')


def letter_picked_up(lay, ltr):
    """收件人把信收走（信從 input/ 消失）之後叫：sent → working。"""
    return _mail_event(lay, ltr, 'picked_up')


def _mail_event(lay, ltr, typ):
    tid = ltr.get('reply_to')
    if not isinstance(tid, str) or not TASK_ID.match(tid) or not lay.task(tid).exists():
        return []
    t = load(lay, tid)
    if ltr.get('to') != t['assignee']:
        return []
    return step(lay, tid, {'type': typ, 'src': '%s:%s' % (typ, ltr['id']), 'rev': ltr.get('rev'), 'at': None})


def check_deadlines(lay, now=None):
    """過了期限還沒結束的單 → failed。回 [(單號, 後續動作)]。"""
    now_s = now or now_iso()
    now_t = parse_iso(now_s)
    out = []
    for t in all_tickets(lay):
        dl = parse_iso(t.get('deadline')) if t.get('deadline') else None
        if dl is not None and now_t is not None and t['status'] not in TERMINAL and now_t > dl:
            out.append((t['id'], step(lay, t['id'], {'type': 'expire', 'src': 'expire:%s:%d' % (t['id'], t['rev'])},
                                      now_s)))
    return out


def check_member(roster, name):
    check_name(name, 'assignee')
    if name not in roster['members']:
        raise TeamError('BadAssignee', '%s 不在名冊裡' % name)
    return name


__all__ = ['Layout', 'apply', 'step', 'load', 'save', 'all_tickets', 'on_handoff', 'on_cancel', 'on_reassign',
           'on_review_result', 'open_review', 'on_letter', 'letter_delivered', 'letter_picked_up',
           'check_deadlines', 'render_handoff']
