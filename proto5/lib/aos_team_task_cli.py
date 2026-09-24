"""aos-team task ls／show／cancel／reassign（spec/team/cli.md、tasks.md）。

只讀任務單；取消、改派都是往 team/outbox/human/ 放申請，郵差才改單子。
"""
import argparse
import json

import aos_team_task as task
from aos_team_format import (HUMAN, TERMINAL, Layout, TeamError, load_roster, new_id, now_iso,
                             validate_request, write_new)
from aos_team_task import describe_item


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TeamError('Usage', '%s\n%s' % (message, self.format_usage().strip()))


def _cut(text, n=40):
    text = ' '.join(str(text).split())
    return text if len(text) <= n else text[:n] + '…'


def line(t):
    return '%s  %-12s %-10s rev%d 第%d/%d次  %s' % (t['id'], t['status'], t['assignee'], t['rev'], t['attempt'],
                                                  t['max_attempts'], _cut(t['goal']))


def show(t):
    out = ['%s  %s' % (t['id'], t['status']),
           '負責人：%s（開單：%s）  rev%d  第 %d/%d 次' % (t['assignee'], t['opened_by'], t['rev'], t['attempt'],
                                                       t['max_attempts']),
           '目標：%s' % t['goal'], '工作流：%s' % t['workflow'], '事實：%s' % (t.get('facts') or '無')]
    if t.get('parent'):
        out.append('審查的是：%s' % t['parent'])
    if t.get('waiting_on'):
        out.append('在等：%s' % t['waiting_on'])
    if t.get('deadline'):
        out.append('期限：%s' % t['deadline'])
    out.append('驗收：')
    # 審查子單保留父單原編號，不是這裡從 0 重編（09-24 astra 審查 M5：aos-team task show 這條之前漏改）
    indices = (t.get('review_of') or {}).get('indices')
    out += ['  %d. %s' % (indices[i] if indices else i, describe_item(it)) for i, it in enumerate(t['done_when'])]
    for v in t.get('verify') or []:
        out.append('驗收結果 rev%s 第%s次：%s' % (v.get('rev'), v.get('attempt'), '過' if v.get('pass') else '不過'))
        for r in v.get('results') or []:
            out.append('  %s %s' % (r.get('i', '?'), r.get('why') or r.get('message') or r.get('result') or ''))
    for v in t.get('review') or []:
        out.append('審查結果 rev%s 第%s次：%s' % (v.get('rev'), v.get('attempt'), '過' if v.get('pass') else '不過'))
        for r in v.get('items') or []:
            out.append('  %s %s %s' % (r.get('i', '?'), 'PASS' if r.get('pass') else 'FAIL', r.get('why', '')))
    out.append('經過：')
    for h in t['history']:
        out.append('  %s  %s  %s→%s%s%s' % (h.get('at'), h.get('event'), h.get('from') or '-', h.get('to') or '-',
                                           '  by %s' % h['by'] if h.get('by') else '',
                                           '  %s' % _cut(h['note'], 80) if h.get('note') else ''))
    return '\n'.join(out)


def _submit(lay, roster, req, what):
    validate_request(req)
    folder = lay.outbox(HUMAN)
    folder.mkdir(parents=True, exist_ok=True)
    write_new(folder / (req['id'] + '.json'), req)
    print('已交給郵差：%s（%s）' % (what, req['id']))
    return 0


def _open_ticket(lay, tid):
    t = task.load(lay, tid)
    if t['status'] in TERMINAL:
        raise TeamError('Closed', '%s 已經 %s' % (tid, t['status']))
    return t


def cmd_task(team_dir, argv):
    ap = _Parser(prog='aos-team task', description='看任務表；取消、改派（寄申請給郵差）')
    sub = ap.add_subparsers(dest='action', required=True, parser_class=_Parser)
    p = sub.add_parser('ls')
    p.add_argument('--all', action='store_true', help='連 done／cancelled 一起列')
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('show')
    p.add_argument('id')
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('cancel')
    p.add_argument('id')
    p.add_argument('--reason')
    p = sub.add_parser('reassign')
    p.add_argument('id')
    p.add_argument('name')
    args = ap.parse_args(argv)
    lay = Layout(team_dir)
    if args.action == 'ls':
        tickets = [t for t in task.all_tickets(lay) if args.all or t['status'] not in ('done', 'cancelled')]
        if args.json:
            print(json.dumps(tickets, ensure_ascii=False, indent=2))
        elif not tickets:
            print('沒有任務單' if args.all else '沒有進行中的任務單（--all 連結束的一起看）')
        else:
            for t in tickets:
                print(line(t))
        return 0
    if args.action == 'show':
        t = task.load(lay, args.id)
        print(json.dumps(t, ensure_ascii=False, indent=2) if args.json else show(t))
        return 0
    roster = load_roster(team_dir)
    t = _open_ticket(lay, args.id) if args.action == 'cancel' else task.load(lay, args.id)
    req = {'id': new_id(HUMAN), 'from': HUMAN, 'kind': args.action, 'at': now_iso(roster.get('tz')),
           'task': t['id']}
    if args.action == 'cancel':
        if args.reason:
            req['reason'] = args.reason
        return _submit(lay, roster, req, '取消 %s' % t['id'])
    if t['status'] in ('done', 'cancelled'):
        raise TeamError('Closed', '%s 已經 %s，不能改派' % (t['id'], t['status']))
    if args.name not in roster['members']:
        raise TeamError('BadAssignee', '%s 不在名冊裡（有：%s）' % (args.name, '、'.join(roster['members'])))
    if t.get('parent'):
        raise TeamError('NotAllowed', '%s 是審查子單，不能改派' % t['id'])
    req['assignee'] = args.name
    return _submit(lay, roster, req, '%s 改派給 %s' % (t['id'], args.name))
