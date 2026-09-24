"""T-spawn（第三波 W3-1，catalog D 節；spec/team/spawn.md）：成員（領隊）申請生一個新成員，人批了才生。

一律平的：新成員就是名冊多一列，跟人手寫的成員一模一樣（沒有父子樹、沒有「小孩」資料夾），交流一律經郵差。
- 郵差端 on_spawn（kind: spawn）：照名冊檢查 → 記 team/spawns/s-NNNN.json → 開一題「[成員] …」問人。不建家、不改名冊。
- 人端 aos-team spawn approve q-NNNN：再驗一次 → 改名冊（新成員一列＋申請者的 mail_to 多這個名字）→
  aos-team init（生家、更新大家工具的名冊快照）→ aos-agent start（登記 kernel）→ 回覆申請者。
  不要就照舊 aos-team answer q-NNNN 不要。停掉／收掉：aos-agent stop ＋ aos-team rm（既有）。
- 檢查（要全過才開題；approve 時再驗一次，名冊可能這中間被人改過）：
  模板要在名冊 spawn.templates 白名單；人數（名冊＋還在等人批的）不超過 limits.max_members；
  新成員的 mail_to 只能是申請者自己或申請者 mail_to 裡的；新成員模板的 may 不能超過申請者的 may（加上 SAFE_MAY）。
不叫模型。team/spawns/ 只有郵差寫；名冊只有人（和人的指令）寫。
"""
import argparse
import copy
import json
import os
import sys

import aos_team_ask
from aos_team_format import (HUMAN, RESERVED, Layout, TeamError, bad, check_name, json_files, load_roster,
                             new_id, next_number, now_iso, read_json, template_dir, template_may,
                             validate_roster, write_json, write_new)

SPAWN_TYPE = 'aos_team_spawn'
FIELDS = ('template', 'name', 'reason', 'mail_to')
# 新成員的模板可以有、申請者自己卻沒有的申請種類：都只碰自己的東西，或本來就要人批
SAFE_MAY = ('ask', 'compact', 'lock', 'review_result', 'tool_draft')
APPROVE = ('批准', '同意', '好', '可以', 'yes', 'y', 'ok', 'approve')   # 跟 aos_team_beat.APPROVE 同一張
PREFIX = '[成員]'   # wait ls 由題目的 tag（member）印這個前綴；題目文字本身不帶


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TeamError('Usage', '%s\n%s' % (message, self.format_usage().strip()))


def folder(lay):
    return lay.team / 'spawns'


def check_body(req):
    where = 'spawn'
    extra = sorted(set(req) - set(FIELDS) - {'id', 'from', 'kind', 'at'})
    if extra:
        bad(where, '不認得的欄位 %s（可用：%s）' % ('、'.join(extra), '、'.join(FIELDS)), 'BadArguments')
    tpl = req.get('template')
    if not isinstance(tpl, str) or '/' in tpl or not tpl.strip():
        bad(where + '.template', '要是內建模板名（不含 /）', 'BadTemplate')
    check_name(req.get('name'), where + '.name')
    reason = req.get('reason')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        bad(where + '.reason', '要是 1～500 字的字串', 'BadArguments')
    mail_to = req.get('mail_to')
    if mail_to is not None and (not isinstance(mail_to, list) or not all(isinstance(x, str) for x in mail_to)):
        bad(where + '.mail_to', '要是名字的陣列', 'BadArguments')
    return req


def records(lay):
    out = []
    for p in json_files(folder(lay)):
        try:
            rec = read_json(p)
        except TeamError:
            continue
        if isinstance(rec, dict) and rec.get('id'):
            out.append(rec)
    return out


def state(lay, rec, roster=None):
    """('pending'|'approved'|'done'|'denied'|'cancelled', 題目)。done＝名冊已經有這個成員。"""
    try:
        q = aos_team_ask.load(lay, rec['q'])
    except TeamError:
        return 'cancelled', None
    if roster is not None and rec['name'] in roster['members']:
        return 'done', q
    if q['status'] == 'open':
        return 'pending', q
    if q['status'] == 'answered':
        return ('approved' if _approves(q.get('answer')) else 'denied'), q
    return 'cancelled', q


def _approves(answer):
    text = str(answer or '').strip().lower()
    return text in APPROVE or any(text.startswith(w) for w in APPROVE if not w.isascii())


def check(lay, roster, sender, template, name, mail_to, *, ignore=None):
    """照名冊檢查一份生成員申請；不過丟 TeamError。回新成員的 mail_to。ignore＝檢查人數時不算這筆紀錄（approve 自己）。"""
    allowed = roster.get('spawn', {}).get('templates', [])
    if template not in allowed:
        raise TeamError('BadTemplate', '模板 %r 不在 team.json 的 spawn.templates（可以生：%s）'
                        % (template, '、'.join(allowed) or '（沒有：這隊不准成員生新成員，要人在 team.json 加 spawn.templates）'))
    if not (template_dir(template) / 'template.json').is_file():
        raise TeamError('BadTemplate', '找不到模板 %s' % template)
    if sender not in roster['members']:
        raise TeamError('NotSender', '%s 不在名冊裡' % sender)
    if name in roster['members'] or name in RESERVED:
        raise TeamError('NameTaken', '名字 %s 已經有人用了' % name)
    pending = [r for r in records(lay) if r['id'] != ignore and state(lay, r, roster)[0] in ('pending', 'approved')]
    if any(r['name'] == name for r in pending):
        raise TeamError('NameTaken', '名字 %s 已經有一份生成員申請在等人批' % name)
    limit = roster['limits']['max_members']
    if len(roster['members']) + len(pending) + 1 > limit:
        raise TeamError('TooMany', '名冊 %d 人＋等人批 %d 人，再生就超過 limits.max_members=%d'
                        % (len(roster['members']), len(pending), limit))
    mine = roster['members'][sender]['mail_to']
    if mail_to is None:
        mail_to = [sender] + ([HUMAN] if HUMAN in mine else [])
    mail_to = list(dict.fromkeys(mail_to))
    over = [x for x in mail_to if x != sender and x not in mine]
    if over:
        raise TeamError('MailToExceeds', '新成員的 mail_to 只能是 %s 自己或它的 mail_to 裡的（%s）；多了：%s'
                        % (sender, '、'.join(mine) or '（空）', '、'.join(over)))
    if name in mail_to:
        raise TeamError('BadArguments', 'mail_to 不能寫新成員自己')
    have = set(template_may(roster['members'][sender]['template'])) | set(SAFE_MAY)
    extra = [k for k in template_may(template) if k not in have]
    if extra:
        raise TeamError('MayExceeds', '模板 %s 能寄 %s，%s 自己不能；新成員的權限不能比申請者大'
                        % (template, '、'.join(extra), sender))
    return mail_to


def on_spawn(lay, roster, req):
    """kind=spawn（郵差叫）：檢查 → 記紀錄 → 開一題問人。冪等：同一份申請回同一份動作。"""
    for rec in records(lay):
        if rec.get('request') == req['id']:
            return copy.deepcopy(rec.get('effects', []))
    check_body(req)
    mail_to = check(lay, roster, req['from'], req['template'], req['name'], req.get('mail_to'))
    now = now_iso(roster.get('tz'))
    d = folder(lay)
    d.mkdir(parents=True, exist_ok=True)
    sid = next_number(d, 's-')
    ask = {'id': req['id'] + '.q', 'from': req['from'], 'kind': 'ask', 'at': now, 'reply_to': None,
           'options': ['批准', '不要'], 'tag': 'member',
           'question': '%s 想生一個新成員 %s（模板 %s，mail_to：%s）。理由：%s。'
                       '批准就跑 aos-team spawn approve %s（生家、登記、改名冊、回覆它）；不要就 aos-team answer %s 不要'
                       % (req['from'], req['name'], req['template'], '、'.join(mail_to), req['reason'].strip(),
                          '{q}', '{q}')}
    qid = next_number(lay.wait_user, 'q-')
    ask['question'] = ask['question'].replace('{q}', qid)
    effects = aos_team_ask.on_ask(lay, roster, ask)
    q = next(x['id'] for x in aos_team_ask.all_questions(lay) if x.get('request') == ask['id'])
    rec = {'_metainfo': {'_type': SPAWN_TYPE, '_version': 1}, 'id': sid, 'request': req['id'], 'from': req['from'],
           'template': req['template'], 'name': req['name'], 'mail_to': mail_to, 'reason': req['reason'].strip(),
           'q': q, 'at': now, 'effects': effects}
    write_json(d / (sid + '.json'), rec, indent=2)
    return copy.deepcopy(effects)


# ------------------------------------------------------------------ 人端 ----

def find(lay, ref, kind_folder, prefix):
    """q-NNNN 或 s-NNNN（d-NNNN）→ 紀錄。"""
    for p in json_files(kind_folder):
        try:
            rec = read_json(p)
        except TeamError:
            continue
        if isinstance(rec, dict) and ref in (rec.get('id'), rec.get('q')):
            return rec
    raise TeamError('NotFound', '沒有 %s（用 %s-NNNN 或它的題號 q-NNNN）' % (ref, prefix))


def _human_items(lay):
    box = lay.outbox(HUMAN)
    for p in json_files(box) + json_files(box / 'done'):
        try:
            obj = read_json(p)
        except TeamError:
            continue
        if isinstance(obj, dict):
            yield obj


def notify(lay, roster, rec, q, text):
    """人批完回覆申請者：題目還開著＝寄 answer（題目關掉、答案投回）；人先用 answer 答過「批准」＝另寄一封信。
    重跑不重寄（看 human 的 outbox 與 done/ 裡有沒有同一題的回覆）。回印出來的一句。"""
    for obj in _human_items(lay):
        if obj.get('kind') == 'answer' and obj.get('q') == q['id']:
            return '已經回覆過 %s' % q['id']
        if 'kind' not in obj and obj.get('reply_to') == q['id'] and obj.get('to') == rec['from']:
            return '已經回覆過 %s' % q['id']
    box = lay.outbox(HUMAN)
    box.mkdir(parents=True, exist_ok=True)
    now = now_iso(roster.get('tz'))
    if q['status'] == 'open':
        obj = {'id': new_id(HUMAN), 'from': HUMAN, 'kind': 'answer', 'at': now, 'q': q['id'], 'text': text}
    else:
        obj = {'id': new_id(HUMAN), 'from': HUMAN, 'to': rec['from'], 'status': 'DONE', 'reply_to': q['id'],
               'rev': None, 'text': text, 'at': now}
    write_new(box / (obj['id'] + '.json'), obj)
    return '已交給郵差：回覆 %s 給 %s' % (q['id'], rec['from'])


def approve(team_dir, ref, env=None):
    import aos_agent
    import aos_team
    env = os.environ if env is None else env
    lay = Layout(team_dir)
    roster = load_roster(team_dir)
    rec = find(lay, ref, folder(lay), 's')
    st, q = state(lay, rec, roster)
    if st in ('denied', 'cancelled'):
        raise TeamError('Closed', '%s 已經%s（答案：%s）' % (rec['q'], '被你拒絕' if st == 'denied' else '取消',
                                                       (q or {}).get('answer')))
    name = rec['name']
    if st != 'done':
        mail_to = check(lay, roster, rec['from'], rec['template'], name, rec['mail_to'], ignore=rec['id'])
        raw = read_json(lay.roster)
        raw['members'][name] = {'template': rec['template'], 'mail_to': mail_to}
        mine = raw['members'][rec['from']].setdefault('mail_to', [])
        if name not in mine:
            mine.append(name)
        validate_roster(raw, str(lay.roster))
        write_json(lay.roster, raw, indent=2)
        print('team.json 加了 %s（模板 %s，mail_to：%s）；%s 的 mail_to 多了 %s'
              % (name, rec['template'], '、'.join(mail_to), rec['from'], name))
        roster = load_roster(team_dir)
    elif roster['members'][name]['template'] != rec['template']:
        raise TeamError('NameTaken', '名冊裡的 %s 是模板 %s，不是這份申請的 %s' % (name, roster['members'][name]['template'],
                                                                     rec['template']))
    rc = aos_team.cmd_init(team_dir, [])          # 生家；別人工具裡的名冊快照（mail_to、members）一起更新
    if rc:
        raise TeamError('InitFailed', 'aos-team init 沒全過（看上面）；修好再跑一次 aos-team spawn approve %s' % rec['q'])
    started = False
    kernel = env.get('AOS_KERNEL_HOME')
    if kernel and os.path.isabs(kernel):
        sys.stdout.write('%s: ' % name)
        sys.stdout.flush()
        started = aos_agent.start(str(lay.member(name)), env=env) == 0
    else:
        print('沒設 AOS_KERNEL_HOME：%s 還沒登記，之後 aos-team start' % name)
    text = ('批准：新成員 %s（模板 %s）已經生好%s；你的 mail_to 多了 %s，可以 handoff／team_say 給它'
            % (name, rec['template'], '、登記了' if started else '（還沒登記，等人 aos-team start）', name))
    print(notify(lay, roster, rec, q, text))
    return 0 if (started or not kernel) else 1


def describe(lay, rec, roster):
    st, _ = state(lay, rec, roster)
    words = {'pending': '等你批', 'approved': '你答了批准、還沒生（aos-team spawn approve %s）' % rec['q'],
             'done': '已生', 'denied': '你不要', 'cancelled': '題目不見了'}
    return '%s  %s  %s 想生 %s（%s）  %s  理由：%s' % (rec['id'], rec['q'], rec['from'], rec['name'], rec['template'],
                                                words[st], rec['reason'])


def cmd_spawn(team_dir, argv):
    ap = Parser(prog='aos-team spawn', description='spawn ls：成員申請生的新成員；'
                                 'spawn approve q-NNNN：批准（生家、登記、改名冊、回覆申請者）')
    sub = ap.add_subparsers(dest='op', required=True)
    ls = sub.add_parser('ls')
    ls.add_argument('--json', action='store_true')
    ok = sub.add_parser('approve')
    ok.add_argument('ref', help='q-NNNN 或 s-NNNN')
    args = ap.parse_args(argv)
    lay = Layout(team_dir)
    roster = load_roster(team_dir)
    if args.op == 'approve':
        return approve(team_dir, args.ref)
    rows = records(lay)
    if args.json:
        print(json.dumps([dict(r, state=state(lay, r, roster)[0]) for r in rows], ensure_ascii=False, indent=2))
    elif not rows:
        print('沒有生成員的申請')
    else:
        for r in rows:
            print(describe(lay, r, roster))
    return 0
