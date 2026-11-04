"""aos-team mail（w2a 從 aos_team_post.cmd_mail 接手；信的讀法與一行印法仍用郵差那份）。

比郵差版多兩件（T5 §8 的建議，試玩兩輪都想要）：
- 等人回答的題目也一題一行：`lead → 人  ASK  q-0001  等你回答…  問：…`；答完了那行先顯示答案 `已答「…」`。
  題目檔（team/wait-user/）只讀，不改。
- `--task t-0001`：領隊開的單，把「落穿給這位領隊的那封人寫的信」也列進來（第一行），
  跟 aos-team score 的起點同一套挑法（spec/team/score.md〈起點〉）。
"""
import argparse
import datetime
import json
import time

import aos_team_ask
import aos_team_format as fmt
from aos_team_format import HUMAN, Layout
from aos_team_post import load_records, mail_line


def _at(rec):
    """排序用時間：跟 score 同一套正規化（沒時區的當本機；astra M12）。"""
    import aos_team_score
    t = aos_team_score.when(rec.get('recorded_at'))
    return t if t is not None else datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


def _key(rec):
    """--follow 看過沒：題目連狀態一起算，答完會再印一次（astra S3）。"""
    q = rec.get('q') or {}
    return rec['kind'], rec['id'], q.get('status'), q.get('answer')


def question_records(lay):
    """每一題 → 一筆 kind=ask 的紀錄（時間＝發問時間）。"""
    out = []
    for q in aos_team_ask.all_questions(lay):
        out.append({'kind': 'ask', 'id': q['id'], 'from': q['from'], 'to': HUMAN, 'status': 'ASK',
                    'reply_to': q.get('reply_to'), 'recorded_at': q.get('asked_at'), 'q': q})
    return out


def ask_line(rec, tz, full=False):
    q = rec['q']
    ask = q['question'] if full else _cut(q['question'], 60)
    if q.get('status') == 'answered':
        head = '已答「%s」' % (q.get('answer') if full else _cut(q.get('answer') or '', 30))
    elif q.get('status') == 'open':
        head = '等你回答（aos-team answer %s "…"）' % q['id']
    else:
        head = q.get('status') or '?'
    ref = '  [%s]' % q['reply_to'] if q.get('reply_to') else ''
    return '%s  %s → 人  ASK  %s%s  %s  問：%s' % (fmt.short_time(rec.get('recorded_at'), tz), q['from'], q['id'],
                                                 ref, head, ask)


def _cut(text, limit):
    text = ' '.join(str(text or '').split())
    return text[:limit] + ('…' if len(text) > limit else '')


def fallthrough_letter(lay, tid, letters):
    """領隊開的單：落穿給領隊、開出這張單的那封人寫的信（沒有＝None）。
    跟 aos-team score 的起點同一個函式（aos_team_score.lead_letter；astra M11）。"""
    import aos_team_score
    import aos_team_task
    try:
        tasks = {t['id']: t for t in aos_team_task.all_tickets(lay)}
        leads = fmt.members_by_template(fmt.load_roster(lay.root), 'lead')
    except Exception:
        return None
    t = tasks.get(tid)
    if not t or t.get('parent'):
        return None
    return aos_team_score.lead_letter(t, letters, leads, tasks)


def cmd_mail(team_dir, argv):
    p = argparse.ArgumentParser(prog='aos-team mail',
                                description='一封信一行（郵差的投遞紀錄）＋等你回答的題目，照時間排')
    p.add_argument('--last', type=int, default=30, help='只看最後幾行（預設 30；0＝全部）')
    p.add_argument('--to', help='只看寄給誰的（human＝人）')
    p.add_argument('--from', dest='sender', help='只看誰寄的')
    p.add_argument('--task', help='只看某張單的（t-0001；含它的審查子單、它的題目、落穿給領隊的那封）')
    p.add_argument('--full', action='store_true', help='印全文')
    p.add_argument('--json', action='store_true', help='一行一個 JSON 紀錄（題目是 kind=ask）')
    p.add_argument('--follow', action='store_true', help='印完繼續等新的（Ctrl-C 停）')
    args = p.parse_args(argv)
    lay = Layout(team_dir)
    tz = fmt.load_roster(team_dir).get('tz')

    def load():
        letters = load_records(lay)
        recs = letters + question_records(lay)
        first = fallthrough_letter(lay, args.task, letters) if args.task else None
        out = []
        for r in recs:
            if args.to and r.get('to') != args.to:
                continue
            if args.sender and r.get('from') != args.sender:
                continue
            if args.task and str(r.get('reply_to') or '').split('.r')[0] != args.task \
                    and not (first is not None and r['id'] == first['id']):
                continue
            out.append(r)
        return sorted(out, key=lambda r: (_at(r), r['id']))

    def show(recs):
        for r in recs:
            if args.json:
                obj = dict(r)
                q = obj.pop('q', None)
                if q is not None:
                    obj.update(question=q['question'], answer=q.get('answer'), state=q.get('status'))
                print(json.dumps(obj, ensure_ascii=False), flush=True)
            else:
                print(ask_line(r, tz, args.full) if r['kind'] == 'ask' else mail_line(r, tz, args.full), flush=True)

    recs = load()
    if not recs and not args.follow:
        print('還沒有信（郵差沒投過任何一封、也沒有人問你問題）')
        return 0
    show(recs[-args.last:] if args.last else recs)
    if not args.follow:
        return 0
    seen = {_key(r) for r in recs}
    try:
        while True:
            time.sleep(1)
            new = [r for r in load() if _key(r) not in seen]
            seen.update(_key(r) for r in new)
            show(new)
    except KeyboardInterrupt:
        return 0
