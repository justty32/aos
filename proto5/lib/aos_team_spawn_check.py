"""生新成員（spawn）的紀錄與檢查：常數、紀錄資料夾與讀取、問題的狀態與批准字、申請欄位驗、能不能生（名冊、模板、may、人頭）、新成員的 spawn 設定。"""
import aos_team_ask
from aos_team_format import HUMAN, RESERVED, TeamError, bad, check_name, json_files, member_may, read_json, spawn_policy, template_dir, template_may


SPAWN_TYPE = 'aos_team_spawn'
FIELDS = ('template', 'name', 'reason', 'mail_to')
# 新成員的模板可以有、申請者自己卻沒有的申請種類：都只碰自己的東西，或本來就要人批
SAFE_MAY = ('ask', 'compact', 'lock', 'review_result', 'tool_draft')
APPROVE = ('批准', '同意', '好', '可以', 'yes', 'y', 'ok', 'approve')   # 跟 aos_team_beat.APPROVE 同一張
PREFIX = '[成員]'   # wait ls 由題目的 tag（member）印這個前綴；題目文字本身不帶


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


def _load_q(lay, qid):
    try:
        return aos_team_ask.load(lay, qid)
    except TeamError:
        return None


def state(lay, rec, roster=None):
    """('pending'|'approved'|'done'|'denied'|'cancelled', 題目)。
    done 看紀錄自己記的 status（生完、init 過了才記）——不看名冊有沒有這個名字：生完又被 rm 掉的不會變回
    「還沒生」再佔名額，名冊寫了但 init 沒過的也不會被當成已生（astra 09-25）。
    approved＝該生、還沒生完（不用人批的郵差生到一半／失敗，或人答了批准還沒跑 approve）；人可以 spawn approve 補做。
    roster 參數留著給舊的呼叫法，不再用。"""
    q = None if rec.get('q') is None else _load_q(lay, rec['q'])
    if rec.get('status') == 'done':
        return 'done', q
    if rec.get('q') is None:
        return 'approved', None
    if q is None:
        return 'cancelled', None
    if q['status'] == 'open':
        return 'pending', q
    if q['status'] == 'answered':
        return ('approved' if _approves(q.get('answer')) else 'denied'), q
    return 'cancelled', q


def _approves(answer):
    text = str(answer or '').strip().lower()
    return text in APPROVE or any(text.startswith(w) for w in APPROVE if not w.isascii())


def check(lay, roster, sender, template, name, mail_to, *, ignore=None):
    """照名冊檢查一份生成員申請；不過丟 TeamError。回 (新成員的 mail_to, 申請者的 spawn_policy)。
    ignore＝檢查人數時不算這筆紀錄（approve 自己）。"""
    if sender not in roster['members']:
        raise TeamError('NotSender', '%s 不在名冊裡' % sender)
    policy = spawn_policy(roster, sender)
    if policy is None:
        raise TeamError('NotAllowed', '%s 不能生新成員（team.json 的 members.%s.spawn 或它模板的 may 關掉了）'
                        % (sender, sender))
    allowed = policy['templates']
    if template not in allowed:
        raise TeamError('BadTemplate', '模板 %r 不在 %s 能生的清單（可以生：%s）'
                        % (template, sender, '、'.join(allowed) or
                           '（沒有：team.json 的 spawn.templates 或 members.%s.spawn.templates 是空的）' % sender))
    if not (template_dir(template) / 'template.json').is_file():
        raise TeamError('BadTemplate', '找不到模板 %s' % template)
    if name in roster['members'] or name in RESERVED:
        raise TeamError('NameTaken', '名字 %s 已經有人用了' % name)
    # 還沒辦完的（不算已經寫進名冊的：那些已經算在名冊人數裡）
    pending = [r for r in records(lay) if r['id'] != ignore and r['name'] not in roster['members']
               and state(lay, r)[0] in ('pending', 'approved')]
    if any(r['name'] == name for r in pending):
        raise TeamError('NameTaken', '名字 %s 已經有一份生成員申請還沒辦完' % name)
    limit = roster['limits']['max_members']
    if len(roster['members']) + len(pending) + 1 > limit:
        raise TeamError('TooMany', '名冊 %d 人＋還沒辦完的 %d 人，再生就超過 limits.max_members=%d'
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
    have = set(member_may(roster, sender)) | set(SAFE_MAY)
    extra = [k for k in template_may(template) if k not in have]
    if extra:
        raise TeamError('MayExceeds', '模板 %s 能寄 %s，%s 自己不能；新成員的權限不能比申請者大'
                        % (template, '、'.join(extra), sender))
    import aos_team
    hr = aos_team._hr_home(cpu_only=True)             # HR 09-25：生之前數全公司 cpu（試用副本也管）
    if hr is not None:
        import aos_team_hr
        aos_team_hr.check_cpus(hr)
    return mail_to, policy


def inherit_spawn(roster, template, policy):
    """新成員那一列要不要寫 spawn：模板本來就不能生＝不寫（關著）；申請者的設定跟「一個沒寫 spawn 的這種模板」
    算出來一樣＝不寫（跟著團隊層）；不一樣＝照抄申請者的——新成員不會比申請者寬（例：申請者被設成要人批，
    它生的也要人批；申請者只能生 importer，它生的 lead 也只能生 importer）。"""
    if 'spawn' not in template_may(template):
        return None
    probe = dict(roster, members={'_': {'template': template, 'spawn': None}})
    if spawn_policy(probe, '_') == policy:
        return None
    return {'templates': list(policy['templates']), 'approve': policy['approve']}
