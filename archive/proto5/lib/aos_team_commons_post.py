"""commons 的郵差兩端：投稿端（申請 contribute、收審查結果）與圖書館員端（審稿桌、申請 commons_write、每輪 post_round）。"""
import datetime
import hashlib
import os
import re
import shutil
from pathlib import Path

from aos_team_format import TeamError, bad, json_files, read_json, write_json

from aos_team_commons_base import Commons, commons_dir, librarians, LIMITS, member_on
from aos_team_commons_ingest import check_fields, check_files, content_sha, ingest, similar


# ------------------------------------------------------------ 郵差：投稿端 ----

def _team_name(lay):
    """給人看的隊名（條目的「來自」）：團隊資料夾名。"""
    return lay.root.name


def _team_tag(lay):
    """投稿號、判決用的隊代號：名字＋資料夾實際路徑的雜湊前 6 碼（astra 9：Team-A／team-a、不同上層的同名隊不撞）。"""
    name = re.sub(r'[^a-z0-9_-]', '-', lay.root.name.lower())[:24] or 'team'
    return '%s-%s' % (name, hashlib.sha1(os.path.realpath(str(lay.root)).encode()).hexdigest()[:6])


def _records(lay):
    return lay.team / 'commons'


def on_contribute(lay, roster, req):
    """kind: contribute（投稿者團隊的郵差叫）：驗欄位 → 附件從 outbox 抄進 commons/inbox/<號>/ → 回信「送到了」。
    冪等：紀錄 team/commons/<號>.json 在＝回同一份動作。"""
    sender = req['from']
    if not member_on(roster, sender):
        raise TeamError('NotAllowed', '%s 沒開 commons（名冊 commons: false）' % sender)
    sub = check_fields(req)
    cid = 'c-%s--%s' % (_team_tag(lay), req['id'])
    recs = _records(lay)
    rec_path = recs / (cid + '.json')
    if rec_path.exists():
        return read_json(rec_path).get('effects', [])
    c = Commons(commons_dir(lay.root, roster)).ensure()
    published = c.inbox / cid / 'submission.json'
    if published.exists():                               # astra 8：崩在發布之後、寫紀錄之前；照已發布的補紀錄，不再讀原附件
        if read_json(published).get('request') != req['id']:
            raise TeamError('AlreadyExists', '投稿號 %s 已被另一份投稿用了' % cid)
        return _contribute_done(recs, rec_path, cid, req, sub)
    outbox = Path(os.path.realpath(lay.outbox(sender)))
    staging = c.inbox / ('.%s.tmp' % cid)
    shutil.rmtree(staging, ignore_errors=True)
    (staging / 'files').mkdir(parents=True)
    total = 0
    try:
        for rel in sub['files']:
            src = outbox / rel
            real = os.path.realpath(src)
            if not real.startswith(str(outbox) + os.sep) or os.path.islink(src) or not os.path.isfile(src):
                raise TeamError('BadFile', '附件 %s 不在你的 outbox、或不是一般檔（符號連結不收）' % rel)
            size = os.path.getsize(src)
            total += size
            if size > LIMITS['file_bytes'] or total > LIMITS['total_bytes']:
                raise TeamError('TooLarge', '附件 %s 太大（一檔 %d、總共 %d bytes 為上限）'
                                % (rel, LIMITS['file_bytes'], LIMITS['total_bytes']))
            dst = staging / 'files' / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            if os.stat(src).st_mode & 0o111:
                os.chmod(dst, 0o755)
        meta = dict(sub, cid=cid, request=req['id'],
                    source={'team': _team_name(lay), 'member': sender, 'task': sub['task']}, at=req.get('at'))
        write_json(staging / 'submission.json', meta, indent=2)
        final = c.inbox / cid
        if not final.exists():
            os.replace(staging, final)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return _contribute_done(recs, rec_path, cid, req, sub)


def _contribute_done(recs, rec_path, cid, req, sub):
    effects = [{'do': 'letter', 'to': req['from'], 'status': 'DONE', 'reply_to': req['id'], 'rev': None,
                'text': '投稿 %s（%s）送到圖書館了；入庫或退回會另寄一封信。' % (cid, sub['title'])}]
    recs.mkdir(parents=True, exist_ok=True)
    write_json(rec_path, {'cid': cid, 'request': req['id'], 'from': req['from'], 'title': sub['title'],
                          'status': None, 'effects': effects}, indent=2)
    return effects


def pending_results(lay, roster):
    """投稿者團隊的郵差每輪看：自己送出去還沒回信的投稿，有結果了就回 [(notice id, 動作)]，並記下已處理。"""
    out = []
    recs = _records(lay)
    if not recs.is_dir():
        return out
    c = Commons(commons_dir(lay.root, roster))
    for p in json_files(recs):
        rec = read_json(p)
        if rec.get('status') is not None:
            continue
        rp = c.inbox / rec['cid'] / 'result.json'
        if not rp.exists():
            continue
        res = read_json(rp)
        if res.get('status') == 'accepted':
            text = '投稿 %s 入庫了：/work/commons/%s（%s；%s）' % (rec['cid'], res.get('path'), res.get('id'),
                                                            res.get('reason') or '機械檢查過')
            status = 'DONE'
        else:
            text = '投稿 %s 被退回（%s）：%s' % (rec['cid'], res.get('by'), res.get('reason'))
            status = 'FAILED'
        # astra 4：這裡不記「已寄」；post_round 開好 notice（郵差的紀錄）之後才記，崩在中間下一輪重給、notice 靠 id 去重
        out.append(('commons.result.%s' % rec['cid'],
                    [{'do': 'letter', 'to': rec['from'], 'status': status, 'reply_to': rec['request'], 'rev': None,
                      'text': text}], (p, res.get('status'))))
    return out


def _mark_sent(p, status):
    rec = read_json(p)
    rec['status'] = status
    write_json(p, rec, indent=2)


# ------------------------------------------------------------ 郵差：圖書館員端 ----

def _result(folder, status, by, reason, **extra):
    write_json(folder / 'result.json', dict({'status': status, 'by': by, 'reason': reason,
                                             'at': datetime.datetime.now().astimezone().isoformat(timespec='seconds')},
                                            **extra), indent=2)


def judge_one(c, folder):
    """一份投稿走機械檢查；回 ('rejected'|'accepted'|'ask', 細節)。呼叫者拿著 c.lock()。"""
    try:
        raw = read_json(folder / 'submission.json')
        sub = check_fields(raw, 'submission')
        sums = check_files(folder / 'files', sub['files'])
    except TeamError as e:
        _result(folder, 'rejected', 'machine', '%s：%s' % (e.code, e.msg))
        return 'rejected', e.code
    sha = content_sha(sub, sums)
    idx = c.load_index()
    same, like = similar(idx, sub, sha)
    if same:
        _result(folder, 'rejected', 'machine', 'Duplicate：跟既有條目 %s 內容完全一樣' % same)
        return 'rejected', 'Duplicate'
    if like:
        return 'ask', like
    eid = ingest(c, sub, raw.get('source') or {}, folder / 'files', sha=sha)
    _result(folder, 'accepted', 'machine', None, id=eid, path=idx_path(c, eid))
    return 'accepted', eid


def idx_path(c, eid):
    return c.load_index()['entries'][eid]['path']


def desk(lay, roster):
    """圖書館員團隊的郵差每輪叫：處理 inbox 裡還沒結果的投稿。回 [(notice id, 動作)]（叫模型判的信）。"""
    libs = librarians(roster)
    if not libs:
        return []
    c = Commons(commons_dir(lay.root, roster)).ensure()
    out = []
    with c.lock():
        for folder in sorted(p for p in c.inbox.iterdir() if p.is_dir() and not p.name.startswith('.')):
            if (folder / 'result.json').exists() or not (folder / 'submission.json').exists():
                continue
            if not (folder / 'judge.json').exists():
                try:
                    verdict, detail = judge_one(c, folder)
                except (OSError, ValueError, KeyError, TeamError):
                    continue                              # astra 7：一份出錯不擋後面的；它下一輪再試
                if verdict != 'ask':
                    continue
                sub = read_json(folder / 'submission.json')
                idx = c.load_index()
                lines = ['投稿 %s 跟既有條目很像，請判：入庫還是退回。' % folder.name,
                         '新投稿：%s（%s）適合：%s 標籤：%s' % (sub['title'], sub['type'], sub['fits'],
                                                        '、'.join(sub['tags'])),
                         '內容：read /work/commons/inbox/%s/submission.json（body 欄）' % folder.name, '像的：']
                for eid in detail:
                    e = idx['entries'][eid]
                    lines.append('- %s：%s → /work/commons/%s' % (eid, e.get('title'), e.get('path')))
                lines.append('用 commons_verdict {"submission": "%s", "verdict": "accept" 或 "reject", '
                             '"reason": "一句話"} 回。' % folder.name)
                write_json(folder / 'judge.json', {'team': _team_tag(lay), 'to': libs[0], 'similar': detail,
                                                   'text': '\n'.join(lines)}, indent=2)
            judge = read_json(folder / 'judge.json')
            if judge.get('team') != _team_tag(lay):
                continue                                  # 別的圖書館員團隊在判
            # 每輪都給；郵差的 notice 靠 id 去重（崩在寫 judge.json 與寄信之間，下一輪也會補寄）
            out.append(('commons.judge.%s' % folder.name,
                        [{'do': 'letter', 'to': judge['to'], 'status': 'REQUEST', 'reply_to': None, 'rev': None,
                          'text': judge['text']}]))
    return out


def on_commons_write(lay, roster, req):
    """kind: commons_write（圖書館員的判決）：{"submission", "verdict": accept|reject, "reason"}。"""
    extra = sorted(set(req) - {'id', 'from', 'kind', 'at', 'submission', 'verdict', 'reason'})
    if extra:
        bad('commons_write', '不認得的欄位 %s' % '、'.join(extra))
    cid, verdict, reason = req.get('submission'), req.get('verdict'), req.get('reason')
    if not isinstance(cid, str) or not re.match(r'c-[A-Za-z0-9_.~-]+\Z', cid):
        bad('commons_write.submission', '要是投稿號 c-…')
    if verdict not in ('accept', 'reject'):
        bad('commons_write.verdict', '要是 accept 或 reject')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        bad('commons_write.reason', '必填，一句話（≤ 500 字）')
    c = Commons(commons_dir(lay.root, roster)).ensure()
    folder = c.inbox / cid
    with c.lock():
        if not (folder / 'submission.json').exists():
            raise TeamError('NotFound', '沒有投稿 %s' % cid)
        res_path = folder / 'result.json'
        if res_path.exists():
            res = read_json(res_path)
            if res.get('request') == req['id']:
                return res.get('effects', [])
            raise TeamError('AlreadyDone', '投稿 %s 已經有結果（%s）' % (cid, res.get('status')))
        if not (folder / 'judge.json').exists():
            raise TeamError('NotAsked', '投稿 %s 沒有要你判（機械就能判的不用模型）' % cid)
        judge = read_json(folder / 'judge.json')           # astra 3：只有被指定的那一隊那一個圖書館員能判
        if judge.get('team') != _team_tag(lay) or judge.get('to') != req['from']:
            raise TeamError('NotAsked', '投稿 %s 是指定給 %s/%s 判的，不是你' % (cid, judge.get('team'), judge.get('to')))
        by = '%s/%s' % (_team_name(lay), req['from'])
        if verdict == 'reject':
            text = '退回 %s：%s' % (cid, reason)
            effects = [{'do': 'letter', 'to': req['from'], 'status': 'DONE', 'reply_to': req['id'], 'rev': None,
                        'text': text}]
            _result(folder, 'rejected', by, reason, request=req['id'], effects=effects)
            return effects
        raw = read_json(folder / 'submission.json')
        sub = check_fields(raw, 'submission')
        sums = check_files(folder / 'files', sub['files'])
        sha = content_sha(sub, sums)
        same, _ = similar(c.load_index(), sub, sha)          # astra 6：兩份一樣的都在等判，先收的那份進館後第二份要擋
        if same:
            reason2 = 'Duplicate：等判的時候，一樣內容的 %s 已經入庫' % same
            effects = [{'do': 'letter', 'to': req['from'], 'status': 'DONE', 'reply_to': req['id'], 'rev': None,
                        'text': '沒入庫 %s：%s' % (cid, reason2)}]
            _result(folder, 'rejected', 'machine', reason2, request=req['id'], effects=effects)
            return effects
        eid = ingest(c, sub, raw.get('source') or {}, folder / 'files', sha=sha)
        path = idx_path(c, eid)
        effects = [{'do': 'letter', 'to': req['from'], 'status': 'DONE', 'reply_to': req['id'], 'rev': None,
                    'text': '入庫 %s → %s（%s）' % (cid, path, eid)}]
        _result(folder, 'accepted', by, reason, id=eid, path=path, request=req['id'], effects=effects)
        return effects


def post_round(post):
    """郵差每輪（process_outboxes 之後）叫：圖書館員端 desk、投稿者端 pending_results；各開一份 notice（冪等）。"""
    roster = post.roster
    for what, fn in (('圖書館', desk), ('回信', pending_results)):     # 兩半各自出錯各自略過
        try:
            items = fn(post.lay, roster)
        except (TeamError, OSError, ValueError, KeyError) as e:
            post.warn('commons %s這輪做不下去：%s（下一輪再試）' % (what, e))
            continue
        for item in items:
            try:
                if post.notice(item[0], item[1]):
                    post.say('commons：%s' % item[0])
                if len(item) > 2:
                    _mark_sent(*item[2])          # notice 紀錄在了才記已寄
            except (TeamError, OSError, ValueError, KeyError) as e:
                post.warn('commons %s 這輪做不下去：%s（下一輪再試）' % (item[0], e))
