"""T-spawn（第三波 W3-1，catalog D 節；spec/team/spawn.md）：成員申請生一個新成員。

09-25 使用者翻案（WAIT_USER 39）：**預設開、預設不用人批**，每個成員都能在名冊上各自設。
一律平的：新成員就是名冊多一列，跟人手寫的成員一模一樣（沒有父子樹、沒有「小孩」資料夾），交流一律經郵差。
- 郵差端 on_spawn（kind: spawn）：照名冊檢查 → 記 team/spawns/s-NNNN.json →
  - 不用人批（預設）：當場生——改名冊（新成員一列＋申請者 mail_to 多這個名字）→ aos-team init → aos-agent start
    （有 AOS_KERNEL_HOME 才做）→ 回信給申請者，另寄一封給人知會。
  - 要人批（名冊 spawn.approve: true，團隊層或成員層）：開一題「[成員] …」問人；人 aos-team spawn approve q-NNNN 才生。
- 檢查（要全過才生／開題；approve 時再驗一次，名冊可能這中間被人改過）：
  申請者能生（format.spawn_policy：成員層 spawn 蓋過團隊層 spawn 蓋過模板 may）；模板在它能生的清單；
  人數（名冊＋還沒生完的）不超過 limits.max_members；新成員的 mail_to 只能是申請者自己或申請者 mail_to 裡的；
  新成員模板的 may 不能超過申請者的 may（加上 SAFE_MAY）；新成員生成員的設定不比申請者寬（inherit_spawn）。
不叫模型。team/spawns/ 只有郵差寫；名冊只有人、人的指令、和郵差這條（不用人批時）寫。
這個檔留真的生（realize）、郵差端 on_spawn（測試換掉這裡的 _auto_finish）、開題與人端指令；
紀錄與檢查分在 aos_team_spawn_check。
"""
import argparse
import contextlib
import copy
import io
import json
import os

import aos_team_ask
from aos_team_format import HUMAN, Layout, TeamError, json_files, load_roster, new_id, next_number, now_iso, read_json, roster_lock, spawn_policy, validate_roster, write_json, write_new

from aos_team_spawn_check import (
    _approves, check, check_body, FIELDS, folder, inherit_spawn, PREFIX, records, SPAWN_TYPE,
    state
)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TeamError('Usage', '%s\n%s' % (message, self.format_usage().strip()))


def realize(lay, rec, env, out=print):
    """真的生：改名冊（沒有才加）→ aos-team init → aos-agent start（有 AOS_KERNEL_HOME 才做）。每步都能重跑。
    回 (登記了沒：True／False／None＝沒 kernel, 名冊)。out＝印一行的函式（郵差裡叫時收進清單，不印到郵差的輸出）。"""
    import aos_agent
    import aos_team
    team_dir = str(lay.root)
    name = rec['name']
    with roster_lock(lay):                            # 讀→檢查→改→寫一口氣做完，不被 rm／另一份 approve 插隊
        roster = load_roster(team_dir)
        if name not in roster['members']:
            mail_to, policy = check(lay, roster, rec['from'], rec['template'], name, rec['mail_to'], ignore=rec['id'])
            raw = read_json(lay.roster)
            row = {'template': rec['template'], 'mail_to': mail_to, 'employment': 'temp'}   # HR：生出來的預設臨時工
            inherit = inherit_spawn(roster, rec['template'], policy)
            if inherit is not None:
                row['spawn'] = inherit
            raw['members'][name] = row
            mine = raw['members'][rec['from']].setdefault('mail_to', [])
            if name not in mine:
                mine.append(name)
            validate_roster(raw, str(lay.roster))
            write_json(lay.roster, raw, indent=2)
            out('team.json 加了 %s（模板 %s，mail_to：%s）；%s 的 mail_to 多了 %s'
                % (name, rec['template'], '、'.join(mail_to), rec['from'], name))
            roster = load_roster(team_dir)
    if roster['members'][name]['template'] != rec['template']:
        raise TeamError('NameTaken', '名冊裡的 %s 是模板 %s，不是這份申請的 %s' % (name, roster['members'][name]['template'],
                                                                     rec['template']))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = aos_team.cmd_init(team_dir, [])          # 生家；別人工具裡的名冊快照（mail_to、members）一起更新
    for line in buf.getvalue().splitlines():
        out(line)
    if rc:
        raise TeamError('InitFailed', 'aos-team init 沒全過；修好再跑一次 aos-team spawn approve %s'
                        % (rec.get('q') or rec['id']))
    kernel = env.get('AOS_KERNEL_HOME')
    if kernel and os.path.isabs(kernel):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            started = aos_agent.start(str(lay.member(name)), env=env) == 0
        out('%s: %s' % (name, buf.getvalue().strip()))
        return started, roster
    out('沒設 AOS_KERNEL_HOME：%s 還沒登記，之後 aos-team start' % name)
    return None, roster


def done_text(rec, started):
    how = {True: '、登記了', False: '，但登記失敗（等人 aos-team start）', None: '（還沒登記，等人 aos-team start）'}
    return ('新成員 %s（模板 %s）已經生好%s；你的 mail_to 多了 %s，可以 handoff／team_say 給它'
            % (rec['name'], rec['template'], how[started], rec['name']))


def on_spawn(lay, roster, req):
    """kind=spawn（郵差叫）：檢查 → 記紀錄 → 不用人批就當場生並回信；要人批就開一題問人。
    冪等：同一份申請回同一份動作。生到一半崩了（紀錄在、effects 還是 null）：名冊還沒這個人而申請者現在被設成
    要人批＝改開題問人（astra 09-25：不能靠崩一次繞過剛設的人批）；否則再生一次，每步都能重跑。"""
    for rec in records(lay):
        if rec.get('request') == req['id']:
            if rec.get('effects') is None and rec.get('status') == 'done':   # 人已經 approve 補做、寄過 DONE
                write_json(folder(lay) / (rec['id'] + '.json'), dict(rec, effects=[]), indent=2)
                return []
            if rec.get('effects') is None:
                policy = spawn_policy(roster, rec['from'])
                if rec['name'] not in roster['members'] and policy is not None and policy['approve']:
                    return _open_question(lay, roster, rec)
                return _auto_finish(lay, roster, rec)
            return copy.deepcopy(rec['effects'])
    check_body(req)
    mail_to, policy = check(lay, roster, req['from'], req['template'], req['name'], req.get('mail_to'))
    now = now_iso(roster.get('tz'))
    d = folder(lay)
    d.mkdir(parents=True, exist_ok=True)
    sid = next_number(d, 's-')
    rec = {'_metainfo': {'_type': SPAWN_TYPE, '_version': 1}, 'id': sid, 'request': req['id'], 'from': req['from'],
           'template': req['template'], 'name': req['name'], 'mail_to': mail_to, 'reason': req['reason'].strip(),
           'q': None, 'at': now, 'effects': None, 'status': None}
    write_json(d / (sid + '.json'), rec, indent=2)      # 先記（effects: null＝辦到一半），崩了重來補做
    if not policy['approve']:
        return _auto_finish(lay, roster, rec)
    return _open_question(lay, roster, rec)


def _open_question(lay, roster, rec):
    """要人批：開一題「[成員]」（tag member），題號記回紀錄。on_ask 冪等（看申請 id），重跑回同一題。"""
    ask = {'id': rec['request'] + '.q', 'from': rec['from'], 'kind': 'ask', 'at': rec['at'], 'reply_to': None,
           'options': ['批准', '不要'], 'tag': 'member',
           'question': '%s 想生一個新成員 %s（模板 %s，mail_to：%s）。理由：%s。'
                       '批准就跑 aos-team spawn approve %s（生家、登記、改名冊、回覆它）；不要就 aos-team answer %s 不要'
                       % (rec['from'], rec['name'], rec['template'], '、'.join(rec['mail_to']), rec['reason'],
                          '{q}', '{q}')}
    old = next((x['id'] for x in aos_team_ask.all_questions(lay) if x.get('request') == ask['id']), None)
    ask['question'] = ask['question'].replace('{q}', old or next_number(lay.wait_user, 'q-'))
    effects = aos_team_ask.on_ask(lay, roster, ask)
    q = next(x['id'] for x in aos_team_ask.all_questions(lay) if x.get('request') == ask['id'])
    rec = dict(rec, q=q, effects=effects)
    write_json(folder(lay) / (rec['id'] + '.json'), rec, indent=2)
    return copy.deepcopy(effects)


def _auto_finish(lay, roster, rec):
    """不用人批：當場生，回兩封信（申請者 DONE／FAILED、人一封知會）。動作與結果（status done／failed）記回紀錄。"""
    lines = []
    try:
        started, _ = realize(lay, rec, os.environ, out=lines.append)
        status, text = 'DONE', done_text(rec, started)
        human = ('%s 生了新成員 %s（模板 %s，不用人批）。理由：%s。不要它：aos-agent stop --target %s 再 aos-team rm %s'
                 % (rec['from'], rec['name'], rec['template'], rec['reason'], lay.member(rec['name']), rec['name']))
    except TeamError as e:
        status, text = 'FAILED', '生 %s 沒成功（%s：%s）' % (rec['name'], e.code, e.msg)
        human = ('%s 申請生 %s（不用人批），郵差生到一半失敗（%s：%s）。修好後 aos-team spawn approve %s 補做'
                 % (rec['from'], rec['name'], e.code, e.msg, rec['id']))
    effects = [{'do': 'letter', 'to': rec['from'], 'status': status, 'reply_to': rec['request'], 'rev': None,
                'text': text},
               {'do': 'letter', 'to': HUMAN, 'status': status, 'reply_to': rec['request'], 'rev': None,
                'text': human}]
    rec = dict(rec, effects=effects, log=lines, status='done' if status == 'DONE' else 'failed')
    write_json(folder(lay) / (rec['id'] + '.json'), rec, indent=2)
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
    """人批（要人批的那種），或補做郵差生到一半的（不用人批的那種，s-NNNN）。"""
    env = os.environ if env is None else env
    lay = Layout(team_dir)
    roster = load_roster(team_dir)
    rec = find(lay, ref, folder(lay), 's')
    st, q = state(lay, rec, roster)
    if st in ('denied', 'cancelled'):
        raise TeamError('Closed', '%s 已經%s（答案：%s）' % (rec['q'], '被你拒絕' if st == 'denied' else '取消',
                                                       (q or {}).get('answer')))
    was = rec.get('status')
    started, roster = realize(lay, rec, env)
    rec = dict(rec, status='done')
    if q is None and was != 'done' and not rec.get('recovered'):
        # 不用人批、郵差那次失敗（或崩了）而人補做成功：郵差之前寄的是 FAILED（或還沒寄），補一封 DONE（astra 09-25）
        box = lay.team / 'post' / 'outbox'
        box.mkdir(parents=True, exist_ok=True)
        lid = new_id('post')
        write_new(box / (lid + '.json'), {'id': lid, 'from': 'post', 'to': rec['from'], 'status': 'DONE',
                                          'reply_to': rec['request'], 'rev': None, 'at': now_iso(roster.get('tz')),
                                          'text': '人補做好了：' + done_text(rec, started)})
        rec['recovered'] = lid
        print('%s 補做完了；已交給郵差：DONE 信給 %s' % (rec['id'], rec['from']))
    elif q is None:
        print('%s 已經生好（郵差生的），沒事可做' % rec['id'])
    else:
        print(notify(lay, roster, rec, q, '批准：' + done_text(rec, started)))
    write_json(folder(lay) / (rec['id'] + '.json'), rec, indent=2)
    return 1 if started is False else 0


def describe(lay, rec, roster):
    st, _ = state(lay, rec, roster)
    words = {'pending': '等你批', 'approved': '還沒生完（aos-team spawn approve %s）' % (rec.get('q') or rec['id']),
             'done': '已生' + ('（不用人批）' if rec.get('q') is None else ''), 'denied': '你不要',
             'cancelled': '題目不見了'}
    return '%s  %s  %s 想生 %s（%s）  %s  理由：%s' % (rec['id'], rec.get('q') or '-', rec['from'], rec['name'],
                                                rec['template'], words[st], rec['reason'])


def cmd_spawn(team_dir, argv):
    ap = Parser(prog='aos-team spawn', description='spawn ls：成員申請生的新成員；'
                                 'spawn approve q-NNNN|s-NNNN：批准要人批的，或補做郵差生到一半的')
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
