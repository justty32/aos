"""任務單的狀態機：apply 照事件改單子並回後續動作（純函式）、重試、step 讀單→apply→寫回。"""
import copy

from aos_team_format import BEAT, HUMAN, POST, TERMINAL, TeamError, now_iso, parse_iso

from aos_team_task_base import (
    _is_int, _notify, _results_text, _tell_human_for_beat, dispatch, JUDGE, letter, load,
    render_handoff, save
)


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
    exact = ev.get('rev') == t['rev'] and ev.get('attempt') == t['attempt']
    if typ in ('verified', 'reviewed', 'delivered', 'picked_up', 'review_failed') and not (
            _is_int(ev.get('rev')) and _is_int(ev.get('attempt'))):
        raise TeamError('BadEvent', '%s 事件要帶整數 rev 與 attempt' % typ)
    if typ == 'reassign':
        if st in ('done', 'cancelled'):
            ignore('已經 %s，不能改派' % st)
        else:
            old = t['assignee']
            t['rev'] += 1
            deadline = t.get('deadline')
            if deadline and parse_iso(deadline) and parse_iso(t['created_at']) and parse_iso(now):
                span = parse_iso(deadline) - parse_iso(t['created_at'])      # 改派＝重新起算同樣長的期限
                deadline = (parse_iso(now) + span).isoformat(timespec='seconds')
            move('queued', '改派 %s → %s' % (old, ev['assignee']), assignee=ev['assignee'], attempt=1,
                 waiting_on=None, deadline=deadline)
            if old != ev['assignee'] and st not in ('queued', 'failed'):
                effects.append(letter(old, 'REQUEST', t, '%s 改派給 %s 了，停下這件，不用再回報。' % (t['id'], ev['assignee'])))
            effects.append(dispatch(t, render_handoff(t)))
    elif st in TERMINAL:
        ignore('單子已經 %s' % st)
    elif typ == 'delivered':
        if st == 'queued' and exact:
            move('sent')
        else:
            ignore('狀態 %s／rev 對不上，不改' % st)
    elif typ == 'picked_up':
        if st == 'sent' and exact:
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
            move('blocked', ev.get('note'), waiting_on=t['opened_by'] if t['opened_by'] not in (POST, BEAT) else HUMAN)
            effects += _tell_human_for_beat(t, status, ev)
        elif status == 'NEEDS-USER' and st in ('sent', 'working', 'blocked'):
            move('waiting_user', ev.get('note'), waiting_on=HUMAN)
            effects += _tell_human_for_beat(t, status, ev)
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
        if ev.get('by') == t['assignee'] and st in ('sent', 'working', 'blocked') and rev_ok:
            move('waiting_user', '等 %s' % ev.get('q'), waiting_on=ev.get('q') or HUMAN)
        else:
            ignore('不是負責人或狀態 %s' % st)
    elif typ == 'resume':
        if st not in ('blocked', 'waiting_user'):
            ignore('狀態 %s 不用恢復' % st)
        elif ev.get('q') is not None and t.get('waiting_on') != ev['q']:
            ignore('%s 不是這張單在等的（在等 %s）' % (ev['q'], t.get('waiting_on')))
        elif not rev_ok:
            ignore('rev %s 對不上目前的 rev%d' % (ev.get('rev'), t['rev']))
        else:
            move('working', ev.get('note'), waiting_on=None)
    elif typ == 'verified':
        if st != 'verifying' or not exact:
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
        if st != 'reviewing' or not exact:
            ignore('不是這一次的審查（狀態 %s）' % st)
        else:
            t.setdefault('review', []).append({'rev': t['rev'], 'attempt': t['attempt'], 'pass': bool(ev['pass']),
                                               'items': ev.get('items', []), 'at': now, 'by': ev.get('by')})
            if ev['pass']:
                move('done')
                effects += _notify(t, 'DONE', '%s 完成（審查通過）：%s' % (t['id'], t['goal']))
            else:
                effects += _retry(t, move, '審查沒過', ev.get('items'))
    elif typ == 'stale_review':
        ignore('過期的開審查動作（rev%s 第 %s 次；目前 %s rev%d 第 %d 次）'
               % (ev.get('rev'), ev.get('attempt'), st, t['rev'], t['attempt']))
    elif typ == 'review_failed':
        if st == 'reviewing' and exact:
            move('blocked', '審查子單 %s 沒完成（%s）' % (ev.get('sub'), ev.get('why')), waiting_on=HUMAN)
            effects += _notify(t, 'BLOCKED', '%s 的審查子單 %s %s；要重審就 aos-team task reassign，或取消'
                               % (t['id'], ev.get('sub'), ev.get('why')))
        else:
            ignore('不是這一次的審查（狀態 %s）' % st)
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
    ro = t.get('review_of')
    if ro and entry['to'] in ('failed', 'cancelled') and entry['from'] not in TERMINAL:
        effects.append({'do': 'step', 'task': ro['task'],
                        'event': {'type': 'review_failed', 'src': 'review_failed:%s' % t['id'], 'sub': t['id'],
                                  'why': entry['to'], 'rev': ro['rev'], 'attempt': ro['attempt']}})
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
        return [dispatch(t, text)]
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
