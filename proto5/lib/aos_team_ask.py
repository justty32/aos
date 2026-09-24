"""問人（spec/team/ask.md）：成員用 ask_human 寄 kind=ask 申請 → 郵差建 team/wait-user/q-NNNN.json；
人用 aos-team answer 寄 kind=answer → 郵差把答案投回發問者、問題標成 answered。

問題檔只有郵差寫（這裡的 on_ask／on_answer 就是郵差叫的）；人的指令只讀、只往 team/outbox/human/ 放申請。
"""
import copy

from aos_team_format import (HUMAN, QUESTION_TYPE, TASK_ID, TERMINAL, TeamError, json_files, next_number, now_iso,
                             read_json, validate_question, write_json)


def load(lay, qid):
    path = lay.question(qid)
    if not path.exists():
        raise TeamError('NoSuchQuestion', '沒有問題 %s（%s）' % (qid, path))
    return validate_question(read_json(path), str(path))


def all_questions(lay):
    out = []
    for p in json_files(lay.wait_user):
        try:
            out.append(validate_question(read_json(p), str(p)))
        except TeamError:
            continue
    return out


def open_questions(lay):
    return [q for q in all_questions(lay) if q['status'] == 'open']


def on_ask(lay, roster, req):
    """kind=ask → q-NNNN（open）。reply_to 是發問者手上的單＝那張單轉 waiting_user。冪等：同一份申請回同一題。"""
    for q in all_questions(lay):
        if q.get('request') == req['id']:
            return copy.deepcopy(q.get('effects', []))
    now = req.get('at') or now_iso(roster.get('tz'))
    lay.wait_user.mkdir(parents=True, exist_ok=True)
    qid = next_number(lay.wait_user, 'q-')
    effects = []
    reply = req.get('reply_to')
    task_rev = None
    if isinstance(reply, str) and TASK_ID.match(reply) and lay.task(reply).exists():
        import aos_team_task
        t = aos_team_task.load(lay, reply)
        if t['assignee'] == req['from'] and t['status'] not in TERMINAL:   # 只有負責人問、單還沒結束才綁到單上
            task_rev = t['rev']
            effects.append({'do': 'step', 'task': reply,
                            'event': {'type': 'needs_user', 'src': req['id'], 'by': req['from'], 'q': qid,
                                      'rev': task_rev, 'at': now}})
    q = {'_metainfo': {'_type': QUESTION_TYPE, '_version': 1}, 'id': qid, 'request': req['id'],
         'from': req['from'], 'question': req['question'], 'options': req.get('options'),
         'default': req.get('default'), 'reply_to': reply, 'task_rev': task_rev, 'asked_at': now, 'status': 'open',
         'tag': req.get('tag'), 'answer': None, 'answered_at': None, 'answer_request': None, 'effects': effects}
    write_json(lay.question(qid), q, indent=2)
    return copy.deepcopy(effects)


def on_answer(lay, roster, req):
    """kind=answer（只有 human）→ 投一封「人 → 發問者 · 回覆 q-NNNN」、問題標成 answered。

    同一份答覆申請再來一次＝回同一份動作；問題已經被別份答覆答過＝Closed（郵差退信給人）。
    """
    if req['from'] != HUMAN:
        raise TeamError('NotAllowed', '只有人能回答問題（%s 不行）' % req['from'])
    q = load(lay, req['q'])
    if q['status'] == 'answered' and q.get('answer_request') == req['id']:
        return copy.deepcopy(q.get('answer_effects', []))
    if q['status'] != 'open':
        raise TeamError('Closed', '%s 已經 %s（答案：%s）' % (q['id'], q['status'], q.get('answer')))
    now = req.get('at') or now_iso(roster.get('tz'))
    text = req['text']
    effects = [{'do': 'letter', 'from': HUMAN, 'to': q['from'], 'status': 'DONE', 'reply_to': q['id'], 'rev': None,
                'text': '問：%s\n答：%s' % (q['question'], text)}]
    reply = q.get('reply_to')
    if q.get('task_rev') is not None and isinstance(reply, str) and lay.task(reply).exists():
        # 只恢復「還在等這一題、還是同一個 rev」的單（狀態機再核一次 waiting_on 與 rev）
        effects.append({'do': 'step', 'task': reply,
                        'event': {'type': 'resume', 'src': req['id'], 'by': HUMAN, 'at': now, 'q': q['id'],
                                  'rev': q['task_rev'], 'note': '%s 已回答' % q['id']}})
    q.update(status='answered', answer=text, answered_at=now, answer_request=req['id'],
             answer_effects=copy.deepcopy(effects))
    write_json(lay.question(q['id']), q, indent=2)
    return effects


# 借用 kind=ask 的申請種類 → aos-team wait ls 的固定前綴（09-24 W2C 待拍題，2026-09-24 已裁決要加）：
# 從申請的 tag 欄位判斷，不猜問句字串；一般問題（沒有 tag）不加前綴。
TAG_LABEL = {'access': '權限', 'persona': '人格'}


def describe(q):
    opts = ''
    if q.get('options'):
        opts = '  選項：%s' % ' / '.join(q['options'])
        if q.get('default'):
            opts += '（預設 %s）' % q['default']
    ref = '  [%s]' % q['reply_to'] if q.get('reply_to') else ''
    label = TAG_LABEL.get(q.get('tag'))
    prefix = '[%s] ' % label if label else ''
    return '%s%s  %s 問：%s%s%s' % (prefix, q['id'], q['from'], q['question'], opts, ref)
