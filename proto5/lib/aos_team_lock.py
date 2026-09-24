"""T-lock（09-24 W2C，catalog.md〈T-lock〉）：多工人同專案搶同一個檔／資料夾的短期獨佔鎖
（跟 T-pool「工具走哪個池」是兩回事，只是剛好都在 priority-and-shared-cpu 提案旁邊被提到）。

一個名字＝一把鎖，記在 `team/locks/<名>.json`；只有郵差寫（跟 wait-user 的問題檔一樣，模型碰不到）。
三種操作（acquire／release／ls）全部走申請（`kind: lock`），跟其他工具一樣是非同步的：
模型端沒有「同步等待」這種東西（工具送出這輪就結束，回信是下一輪的新輸入），所以不做 catalog 草案設想的
「acquire 立即回」，乾脆全部走 outbox → 郵差 → 回信，跟 ask_human／compact_me 同一套路。
**逾時自動放**：鎖記 `expires_at`，到期後誰都可以 acquire（覆蓋），不用人或原本的持有者特地去 release。
"""
import copy
import datetime
import re

from aos_team_format import HUMAN, Layout, TeamError, bad, json_files, load_roster, new_id, now_iso, \
    parse_iso, read_json, write_json, _int, _opt_str

DEFAULT_TTL, MIN_TTL, MAX_TTL = 1800, 60, 86400   # 秒：預設 30 分、最短 1 分、最長 24 小時
FIELDS = ('op', 'name', 'why', 'ttl_seconds')
OPS = ('acquire', 'release', 'ls')
# 鎖的名字是「檔或資料夾的名字」，不是成員名（跟 aos_team_format.check_name 的規則不一樣，
# 那個只准小寫英數＋底線／連字號，鎖名要能寫 docs/WORKFLOWS.md 這種相對路徑）：
# 英數、`. _ - /`，不以 / 開頭、不含 .. 段（防目錄穿越當成識別碼濫用）、上限 200 字，不准空白。
LOCK_NAME = re.compile(r'[\w.\-/]{1,200}\Z')


def _check_lock_name(name, where):
    if not isinstance(name, str) or not LOCK_NAME.match(name) or name.startswith('/') \
            or any(seg == '..' for seg in name.split('/')):
        bad(where, '名字 %r 只能用英數、. _ - /，不能以 / 開頭、不能含 .. 段、上限 200 字' % (name,))
    return name


def check_lock(req):
    """驗 lock 申請的欄位（給 on_lock、也給 cmd_lock 組申請前檢查用）。"""
    where = 'lock'
    extra = sorted(set(req) - set(FIELDS) - {'id', 'from', 'kind', 'at'})
    if extra:
        bad(where, '不認得的欄位 %s（可用：%s）' % ('、'.join(extra), '、'.join(FIELDS)))
    op = req.get('op')
    if op not in OPS:
        bad(where + '.op', '要是 %s 之一' % '／'.join(OPS))
    if op == 'ls':
        return op, None, None, None
    _check_lock_name(req.get('name'), where + '.name')
    why = _opt_str(req.get('why'), where + '.why')
    if why is not None and len(why) > 500:
        bad(where + '.why', '太長（上限 500 字）')
    ttl = DEFAULT_TTL
    if op == 'acquire' and req.get('ttl_seconds') is not None:
        ttl = _int(req['ttl_seconds'], where + '.ttl_seconds', MIN_TTL, MAX_TTL)
    return op, req['name'], why, ttl


def _add_seconds(iso, seconds):
    t = parse_iso(iso)
    return iso if t is None else (t + datetime.timedelta(seconds=seconds)).isoformat(timespec='seconds')


def _expired(rec, now):
    exp = parse_iso(rec.get('expires_at'))
    return exp is None or exp <= parse_iso(now)


def _free(rec, now):
    return rec is None or rec.get('owner') is None or _expired(rec, now)


def describe(rec):
    if rec.get('owner') is None:
        return '%s  沒人拿著' % rec['name']
    state = '已到期' if _expired(rec, now_iso()) else ('到期 %s' % rec.get('expires_at'))
    why = ('  ' + rec['why']) if rec.get('why') else ''
    return '%s  %s 拿著（%s）%s' % (rec['name'], rec['owner'], state, why)


def _letter(to, text, reply_to):
    return {'do': 'letter', 'to': to, 'status': 'DONE', 'reply_to': reply_to, 'rev': None, 'text': text}


def on_lock(lay, roster, req):
    """申請 kind=lock（郵差叫）：acquire／release／ls，全部回一封信（DONE）；拿不到／不是持有者丟 TeamError，
    郵差照共同規則退一封 FAILED 給寄件人（不用這裡自己組拒絕信）。

    冪等：acquire／release 各自記在鎖檔的 request／release_request；同一份申請重跑回同一份效果。
    """
    op, name, why, ttl = check_lock(req)
    lay.locks.mkdir(parents=True, exist_ok=True)
    now = req.get('at') or now_iso(roster.get('tz'))
    if op == 'ls':
        lines = [describe(read_json(p)) for p in json_files(lay.locks)]
        text = '\n'.join(lines) if lines else '沒有任何鎖'
        return [_letter(req['from'], text, req['id'])]
    path = lay.lock(name)
    rec = read_json(path) if path.exists() else None
    if op == 'acquire':
        if rec is not None and rec.get('request') == req['id']:
            return copy.deepcopy(rec.get('effects', []))
        # 同一個持有者可以續租（不算 Busy）；別人要等到期或它／人主動 release
        if not _free(rec, now) and rec.get('owner') != req['from']:
            raise TeamError('Busy', '鎖 %s 被 %s 拿著，到期 %s；等到期或請它／人 release'
                            % (name, rec['owner'], rec.get('expires_at')))
        expires = _add_seconds(now, ttl)
        effects = [_letter(req['from'], '取得鎖 %s（到期 %s，過了自動放）' % (name, expires), req['id'])]
        new = {'name': name, 'owner': req['from'], 'acquired_at': now, 'expires_at': expires, 'ttl_seconds': ttl,
               'why': why, 'request': req['id'], 'effects': copy.deepcopy(effects),
               'released_at': None, 'release_request': None, 'release_effects': []}
        write_json(path, new, indent=2)
        return effects
    # release
    if rec is None:
        raise TeamError('NoSuchLock', '沒有鎖 %s' % name)
    if rec.get('release_request') == req['id']:
        return copy.deepcopy(rec.get('release_effects', []))
    if rec.get('owner') is None:
        raise TeamError('NotOwner', '鎖 %s 本來就沒人拿著' % name)
    if rec['owner'] != req['from'] and not _expired(rec, now):
        raise TeamError('NotOwner', '鎖 %s 是 %s 拿著，不是 %s，放不了' % (name, rec['owner'], req['from']))
    effects = [_letter(req['from'], '放掉鎖 %s' % name, req['id'])]
    rec.update(owner=None, acquired_at=None, expires_at=None, released_at=now,
              release_request=req['id'], release_effects=copy.deepcopy(effects))
    write_json(path, rec, indent=2)
    return effects


def cmd_lock(team_dir, argv):
    """人用：ls 直接讀（唯讀、不用等郵差）；acquire／release 往 team/outbox/human/ 放申請（跟 routine add 同路）。"""
    import argparse
    import json as _json

    p = argparse.ArgumentParser(prog='aos-team lock', description='短期獨佔鎖：ls／acquire／release')
    sub = p.add_subparsers(dest='op', required=True)
    ls = sub.add_parser('ls', help='列出所有鎖（誰拿著、到期）')
    ls.add_argument('--json', action='store_true')
    acq = sub.add_parser('acquire', help='拿一把鎖（拿不到會收到退信說誰拿著）')
    acq.add_argument('name')
    acq.add_argument('--why', default=None)
    acq.add_argument('--ttl', type=int, default=None, metavar='秒', help='多久沒放自動失效（預設 %d）' % DEFAULT_TTL)
    rel = sub.add_parser('release', help='放掉一把鎖（不是自己拿的、沒過期會被拒）')
    rel.add_argument('name')
    args = p.parse_args(argv)
    lay = Layout(team_dir)
    load_roster(team_dir)   # 只是確認團隊存在
    if args.op == 'ls':
        lay.locks.mkdir(parents=True, exist_ok=True)
        rows = [read_json(f) for f in json_files(lay.locks)]
        if args.json:
            print(_json.dumps(rows, ensure_ascii=False))
        else:
            print('\n'.join(describe(r) for r in rows) if rows else '沒有任何鎖')
        return 0
    body = {'op': args.op, 'name': args.name}
    if args.op == 'acquire':
        if args.why:
            body['why'] = args.why
        if args.ttl is not None:
            body['ttl_seconds'] = args.ttl
    req = {'id': new_id(HUMAN), 'from': HUMAN, 'kind': 'lock', 'at': now_iso()}
    req.update(body)
    lay.outbox(HUMAN).mkdir(parents=True, exist_ok=True)
    write_json(lay.outbox(HUMAN) / (req['id'] + '.json'), req, indent=2)
    print('已交給郵差：%s %s' % (args.op, args.name))
    return 0
