"""心跳的例行表 team/routines.json：讀、申請 routine 的驗與處理（on_routine）、這一列有沒有被批准。"""
import aos_team_ask
import aos_team_format as fmt
from aos_team_format import HUMAN, TeamError

from aos_team_beat_schedule import APPROVE, check_tz, FIELDS, ROUTINE_COLUMNS, Schedule


# ------------------------------------------------------------- 資料檔 ----

def load_routines(lay):
    if not lay.routines.exists():
        return {'contract': 'wf-table/1', 'source': None, 'columns': list(ROUTINE_COLUMNS), 'rows': [],
                'removed_requests': []}
    data = fmt.read_json(lay.routines)
    if not isinstance(data, dict) or data.get('contract') != 'wf-table/1' or not isinstance(data.get('rows'), list):
        raise TeamError('FormatInvalid', '%s 要是 wf-table/1（{"contract": "wf-table/1", "rows": […]}）' % lay.routines)
    data.setdefault('removed_requests', [])
    return data


def check_routine(req, roster):
    """驗 routine 申請（或 aos-team routine add 要寄的）的欄位；回整理好的列（字串值，照 wf-table/1）。"""
    where = 'routine'
    extra = sorted(set(req) - set(FIELDS) - set(fmt.REQUEST_COMMON))
    if extra:
        fmt.bad(where, '不認得的欄位 %s（可用：%s）' % ('、'.join(extra), '、'.join(FIELDS)))
    op = req.get('op')
    if op not in ('add', 'rm'):
        fmt.bad(where + '.op', '要是 add 或 rm')
    fmt.check_name(req.get('name'), where + '.name', member=False)
    if req.get('tz') is not None:
        check_tz(req['tz'])
    if op == 'rm':
        return {'name': req['name']}
    when = [k for k in ('every', 'daily', 'once') if req.get(k)]
    if len(when) != 1:
        fmt.bad(where, 'every／daily／once（一次性時刻）要恰好給一個')
    if req.get('to') not in roster['members']:
        fmt.bad(where + '.to', '%r 不在名冊裡' % (req.get('to'),), 'BadAssignee')
    fmt._str(req.get('goal'), where + '.goal', limit=4000)
    fmt.validate_done_when(req.get('done_when'), where + '.done_when')
    row = {c: '' for c in ROUTINE_COLUMNS}
    row.update(name=req['name'], to=req['to'], goal=req['goal'], done_when=req['done_when'],
               workflow=req.get('workflow') or '無', tz=req.get('tz') or '')
    row[when[0]] = str(req[when[0]])
    for key, lo, hi in (('timeout_minutes', 1, 7 * 24 * 60), ('retries', 0, 5)):
        if req.get(key) is not None:
            row[key] = str(fmt._int(req[key], '%s.%s' % (where, key), lo, hi))
    Schedule(dict(row, added_at=fmt.now_iso()), roster.get('tz'))      # 時間表寫法不對就在這裡擋
    return row


def on_routine(lay, roster, req):
    """申請 kind=routine（郵差叫）：op=add 加一列、op=rm 拿掉一列。人加的直接生效；成員提的開一題問人。

    冪等：同一份申請（看列的 request、removed_requests）再來＝不多做。
    """
    row = check_routine(req, roster)
    data = load_routines(lay)
    rows = data['rows']
    if req['op'] == 'rm':
        if req['id'] in data['removed_requests']:
            return []
        hit = [r for r in rows if r.get('name') == row['name']]
        if not hit:
            raise TeamError('NoSuchRoutine', '沒有例行 %s' % row['name'])
        if req['from'] not in (HUMAN, hit[0].get('added_by')):
            raise TeamError('NotAllowed', '只有人或提出的 %s 能拿掉 %s' % (hit[0].get('added_by'), row['name']))
        data['rows'] = [r for r in rows if r.get('name') != row['name']]
        data['removed_requests'] = (data['removed_requests'] + [req['id']])[-200:]
        fmt.write_json(lay.routines, data, indent=2)
        return []
    if any(r.get('request') == req['id'] for r in rows):
        return []
    if any(r.get('name') == row['name'] for r in rows):
        raise TeamError('NameTaken', '例行 %s 已經有了（先 aos-team routine rm）' % row['name'])
    row.update(added_by=req['from'], added_at=req.get('at') or fmt.now_iso(roster.get('tz')), request=req['id'])
    effects = []
    if req['from'] != HUMAN:
        ask = {'id': req['id'] + '.q', 'from': req['from'], 'kind': 'ask', 'at': row['added_at'],
               'question': '%s 提議加一條例行「%s」：%s 叫 %s 做：%s。要讓心跳自動跑嗎？'
                           % (req['from'], row['name'], Schedule(row, roster.get('tz')).describe(), row['to'],
                              row['goal']),
               'options': ['批准', '不要'], 'reply_to': None}
        effects = aos_team_ask.on_ask(lay, roster, ask)
        row['q'] = next(q['id'] for q in aos_team_ask.all_questions(lay) if q.get('request') == ask['id'])
    lay.routines.parent.mkdir(parents=True, exist_ok=True)
    data['rows'] = rows + [row]
    fmt.write_json(lay.routines, data, indent=2)
    return effects


def authorized(lay, row):
    """(會不會自動跑, 白話)：人加的會；成員提的要那一題被人答「批准」。"""
    if row.get('added_by') == HUMAN:
        return True, '人登記的'
    q = row.get('q')
    if not q:
        return False, '成員提的、沒有問人'
    try:
        question = aos_team_ask.load(lay, q)
    except TeamError:
        return False, '問題 %s 不見了' % q
    if question['status'] != 'answered':
        return False, '等人批准（aos-team answer %s 批准）' % q
    answer = str(question.get('answer') or '').strip().lower()
    if answer in APPROVE:
        return True, '人批准了（%s）' % q
    return False, '人沒批准（%s 答：%s）' % (q, question.get('answer'))
