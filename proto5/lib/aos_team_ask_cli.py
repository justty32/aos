"""aos-team wait ls／answer（spec/team/ask.md）：人看等他回答的問題、回答一題。

只讀問題檔；回答是往 team/outbox/human/ 放一份 kind=answer 申請，郵差投回發問者。
"""
import argparse
import json

import aos_team_ask as ask
from aos_team_format import (HUMAN, Layout, TeamError, load_roster, new_id, now_iso, validate_request,
                             write_new)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TeamError('Usage', '%s\n%s' % (message, self.format_usage().strip()))


def cmd_wait(team_dir, argv):
    ap = _Parser(prog='aos-team wait', description='wait ls：列出等人回答的問題')
    ap.add_argument('action', choices=('ls',))
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    qs = ask.open_questions(Layout(team_dir))
    if args.json:
        print(json.dumps(qs, ensure_ascii=False, indent=2))
    elif not qs:
        print('沒有在等你回答的問題')
    else:
        for q in qs:
            print(ask.describe(q))
    return 0


def cmd_answer(team_dir, argv):
    ap = _Parser(prog='aos-team answer', description='answer q-0001 "文字"：回答一題（寄申請給郵差）')
    ap.add_argument('q')
    ap.add_argument('text', nargs='+')
    args = ap.parse_args(argv)
    lay = Layout(team_dir)
    roster = load_roster(team_dir)
    text = ' '.join(args.text).strip()
    if not text:
        raise TeamError('Usage', '答案不能是空的')
    q = ask.load(lay, args.q)
    if q['status'] != 'open':
        raise TeamError('Closed', '%s 已經 %s（答案：%s）' % (q['id'], q['status'], q.get('answer')))
    req = {'id': new_id(HUMAN), 'from': HUMAN, 'kind': 'answer', 'at': now_iso(roster.get('tz')),
           'q': q['id'], 'text': text}
    validate_request(req)
    folder = lay.outbox(HUMAN)
    folder.mkdir(parents=True, exist_ok=True)
    write_new(folder / (req['id'] + '.json'), req)
    print('已交給郵差：回答 %s 給 %s（%s）' % (q['id'], q['from'], req['id']))
    if q.get('options') and text not in q['options']:
        print('提醒：「%s」不在選項（%s）裡，照樣送出' % (text, ' / '.join(q['options'])))
    return 0
