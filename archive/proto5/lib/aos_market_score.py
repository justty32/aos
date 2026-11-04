"""市場的表現：從評估結果與品管判決算品質、從公司的任務單與信算一家的成績板、記一筆成績。"""
import re
from pathlib import Path
import sys

import aos_company as co
import aos_team_format as fmt
from aos_team_format import TeamError

from aos_market_book import _finite, load, market_lock, MarketError, now, save
from aos_market_review import _review_rounds, review_factor

LIB = Path(__file__).resolve().parent      # 跟 aos_market.LIB 同一個資料夾（proto5/lib）


# ------------------------------------------------------------------ 表現 ----

ALIAS_DEF = re.compile(r'(?<![A-Za-z0-9])([A-Z])\s*檔\s*`([^`\s]+)`')


def expand_codes(text):
    """證據檔的「代號 L30」寫法展開成檔名（真跑 09-25：「行號依據 A 檔 `…奇石.md`」再寫「A L30-L37」，
    證據檢查器認不出檔名，整份算壞）。回 (展開後的文字, {代號: 檔名})；沒有代號定義＝原樣、空 dict。"""
    codes = dict(ALIAS_DEF.findall(text))
    if not codes:
        return text, {}
    rx = re.compile(r'(?<![A-Za-z0-9_./`-])(%s)(?=\s*L\d)' % '|'.join(map(re.escape, codes)))
    out = [rx.sub(lambda m: codes[m.group(1)], ln) if ln.lstrip().startswith('|') else ln
           for ln in text.split('\n')]
    return '\n'.join(out), codes


def _recheck_evidence(project, name, notes):
    """證據列有「無檔名」的：展開代號後用同一支 evidence_check 重跑（展開的是暫存副本，不動原檔）。
    回新的 summary；展開不了回 None（notes 寫原因）。"""
    import tempfile
    sys.path.insert(0, str(LIB.parent / 'examples' / 'arknights' / 'eval'))
    try:
        import evidence_check as evc
    except ImportError as e:
        notes.append('%s：證據列有「無檔名」，展開不了（載不到 evidence_check：%s），證據那一項算 0' % (name, e))
        return None
    files = evc.evidence_files_for(Path(project), name) if project else []
    if not files:
        notes.append('%s：證據列有「無檔名」，展開不了（在 %s 找不到證據檔），證據那一項算 0' % (name, project))
        return None
    with tempfile.TemporaryDirectory(prefix='market-ev-') as td:
        tmp, found = [], {}
        for i, f in enumerate(files):
            text, codes = expand_codes(f.read_text(encoding='utf-8'))
            found.update(codes)
            t = Path(td) / ('%d-%s' % (i, f.name))
            t.write_text(text, encoding='utf-8')
            tmp.append(t)
        if not found:
            notes.append('%s：證據列有「無檔名」，展開不了（證據檔裡沒有「X 檔 `檔名`」這種代號定義），證據那一項算 0' % name)
            return None
        summary = evc.run(Path(project), files=tmp, corpus=evc.Corpus(Path(project)))['summary']
    notes.append('%s：證據檔的代號 %s 展開成檔名後重跑證據檢查：%d/%d 列 ok（原本全算「無檔名」）' % (
        name, '、'.join('%s＝%s' % kv for kv in sorted(found.items())), summary['ok'], summary['checked_rows']))
    return summary


def quality_from_eval(result, project=None, notes=False):
    """arknights eval 的結果檔 → 0～100：每人 機械 40％＋證據列 40％＋評審 20％（沒評審就前兩項放大成 100）。
    證據列有「無檔名」的：先把證據檔（這人的 cand_root，沒有就用 project）裡的代號展開成檔名重跑證據檢查；
    展開不了＝證據那一項照原樣（通常是 0），notes 寫原因。notes=True 回 (分數, [說明…])。"""
    people = result.get('people') or []
    msgs = []
    if not people:
        return (None, msgs) if notes else None
    total = 0.0
    for p in people:
        mech = p.get('mech') or {}
        ev = p.get('evidence') or {}
        if (ev.get('by_status') or {}).get('無檔名'):
            root = p.get('cand_root') or project
            fixed = _recheck_evidence(root, p.get('name', '?'), msgs) if root else None
            if root is None:
                msgs.append('%s：證據列有 %d 列「無檔名」，展開不了（不知道證據檔在哪；給公司的專案），證據那一項算 0'
                            % (p.get('name', '?'), ev['by_status']['無檔名']))
            ev = fixed or {'checked_rows': ev.get('checked_rows'), 'ok': 0}
        m = (mech.get('passed', 0) / mech['total']) if mech.get('total') else 0.0
        e = (ev.get('ok', 0) / ev['checked_rows']) if ev.get('checked_rows') else 0.0
        j = None
        judge = p.get('judge') or {}
        scores = judge.get('scores') if isinstance(judge, dict) else None
        if isinstance(scores, dict) and scores:
            vals = [v for v in scores.values() if isinstance(v, (int, float))]
            j = sum(vals) / len(vals) / 5.0 if vals else None
        total += (40 * m + 40 * e + 20 * j) if j is not None else (50 * m + 50 * e)
    q = round(total / len(people), 2)
    return (q, msgs) if notes else q


def _aware(t):
    return t if t is None or t.tzinfo is not None else t.astimezone()


def _read_letters(folder):
    out = []
    for p in fmt.json_files(folder) if folder.is_dir() else []:
        try:
            out.append(fmt.read_json(p))
        except TeamError:
            continue
    return out


VERDICT = re.compile(r'結論[為是]?\s*[:：]\s*(不)?合格')


def _qa_verdict(teams, o):
    """品管總機單 o 的品管報告結論（五家真跑 §7 第 1 條長遠版：看報告檔本身，不看總裁的轉述）：
    照那張單子的 done_when 找 qa-reports/ 底下的檔，第一個「結論：合格／不合格」（容「結論為：」）。
    合格＝True、不合格＝False；找不到單子、檔或結論＝None（呼叫的人退回看結案信）。"""
    tdir = teams.get((o.get('to') or {}).get('team') or (o.get('to') or {}).get('dept'))
    if tdir is None or not o.get('task'):
        return None
    try:
        ticket = fmt.read_json(fmt.Layout(tdir).task(o['task']))
        proj = fmt.project_dir(tdir, fmt.load_roster(tdir))
    except (TeamError, OSError, ValueError):
        return None
    for it in ticket.get('done_when') or []:
        path = it.get('path') if isinstance(it, dict) and it.get('kind') == 'file_exists' else None
        if not isinstance(path, str) or not path.startswith('qa-reports/') or '..' in path.split('/'):
            continue
        try:
            text = (proj / path).read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        m = VERDICT.search(text)
        if m:
            return m.group(1) is None
    return None


def _mfg_for_asks(asks, pair, mfg, t):
    """董事的單 → 它的製造總機單（astra 審查第 74、75 題必修 1：兩張單時間重疊時，以前取「那段時間最後一張」，
    兩張單會配到同一張）。一張製造總機單只配一張董事的單：
    董事的單照下單時間排，每張先拿它那段時間（下單到結案；沒結案＝到下一張董事的單之前）裡最早一張還沒配走的；
    再把「下一張董事的單下之前」還沒配走的也收進來（同一張單總裁重發的），用收到的最後一張。
    沒有重疊時跟以前一樣＝那段時間最後一張。回 {董事單號: 製造總機單}，配不到的不在裡面。"""
    mfg = sorted(mfg, key=t)
    used, out = set(), {}
    for i, a in enumerate(asks):
        t0, c = t(a), pair.get(a['id'])
        t1 = t(c) if c is not None else None
        nxt = t(asks[i + 1]) if i + 1 < len(asks) else None
        mine = []
        for j, o in enumerate(mfg):
            if j in used or t(o) < t0 or (t1 is not None and t(o) > t1):
                continue
            if c is None and nxt is not None and t(o) >= nxt:
                break                                  # 沒結案的單（逾時）只拿下一張單之前的，不搶後面的
            if mine and nxt is not None and t(o) >= nxt:
                break
            mine.append(j)
            used.add(j)
        if mine:
            out[a['id']] = mfg[mine[-1]]
    return out


def board_from_company(cdir, since=None, skip=()):
    """董事的單（company.py order → 前台部門）這一輪的結果（真跑 09-25 修正：快＝董事等的時間，不是部門間跳的平均）。

    - 董事的單：前台部門 human 寄件格（含郵差收走的 done/）裡 human 寄出的 REQUEST、沒有 reply_to、不是總機寫的。
    - 結案信：前台部門 human 收件格裡狀態 DONE／FAILED、第一行不是〔給 …〕的信（總裁寫給董事的）。
    - 配對（五家真跑 §7 第 6 條）：結案信的 reply_to 若是總裁發某張總機單的那封信，就配給那張總機單之前最後一張
      董事的單；其他照時間先後，每張還沒配的單配它之後第一封還沒配走的結案信。一張單只配第一封。
    - **成功**＝結案信是 DONE，而且品管過了：優先看品管報告檔本身（_qa_verdict：總裁回的那張品管總機單、
      沒有就這段時間最後一張結案的品管總機單，報告第一個結論是「合格」、那張總機單 done）；找不到報告檔才退回看
      結案信寫了「結論：合格」＋這段時間有 done 的品管總機單。其他結案＝失敗。
    - **逾時＝失敗**：這一輪下的單（下單時間在 since 之後；沒 since＝全部）score 時還沒有結案信，算失敗一張
      （`timeout` 另記張數、`timeout_ids` 記單號）。skip：以前的輪已經算過逾時的單號，不再算（之後才來的結案信也不算）。
    - 「這一輪」看結案信的時間（上一輪 grant 之後）；跨輪完成的單算在結案那一輪。
    - **審查輪數**（第 75 題）：每張成功的單配一張有單號的製造總機單（_mfg_for_asks：一張製造總機單只配一張董事的單），
      看那張部門單子第幾次審查才過（_review_rounds）；照成功的順序記在 `reviews`（1、2、3…／'FAILED'／None＝沒紀錄）。
      配不到製造總機單的成功單記 None，`notes` 寫是哪張。
    回 {'done': 成功張數, 'failed': 失敗張數（含逾時）, 'timeout': 逾時張數, 'timeout_ids': [...],
        'seconds': 成功那幾張董事平均等幾秒（沒有＝None）, 'hops': 成功那幾張平均經過幾張總機單＋1（只記、不算分）,
        'reviews': 成功那幾張的審查輪數}。"""
    cdir = Path(cdir)
    cfg = co.load(cdir)
    front = co.host_dept(cfg, cfg['front'])
    teams = co.team_dirs(cdir, cfg)
    tdir = teams.get(front)
    t_since = _aware(fmt.parse_iso(since)) if since else None
    folder = cdir / 'switchboard' / 'orders'
    orders = [fmt.read_json(p) for p in fmt.json_files(folder)] if folder.is_dir() else []
    out_ids = {o.get('out_id') for o in orders}
    res = {'done': 0, 'failed': 0, 'timeout': 0, 'timeout_ids': [], 'seconds': None, 'hops': None, 'reviews': []}
    if tdir is None:
        return res
    lay = fmt.Layout(tdir)
    box = lay.outbox(fmt.HUMAN)
    skip = set(skip or ())
    asks = [x for x in _read_letters(box) + _read_letters(box / 'done')
            if x.get('from') == fmt.HUMAN and x.get('status') == 'REQUEST' and not x.get('reply_to')
            and 'kind' not in x and x.get('id') not in out_ids]
    closes = [x for x in _read_letters(lay.human_inbox)
              if x.get('status') in co.TERMINAL_STATUS and not co.MARK.match(x.get('text') or '')
              and x.get('from') not in (fmt.HUMAN, fmt.POST, fmt.BEAT)]

    def t(x):
        return _aware(fmt.parse_iso(x.get('at') or ''))
    asks = sorted((a for a in asks if t(a)), key=t)
    closes = sorted((c for c in closes if t(c)), key=t)
    orders = [o for o in orders if t(o)]
    by_letter = {(o.get('from') or {}).get('letter'): o for o in orders if (o.get('from') or {}).get('letter')}
    pair, used = {}, set()
    for c in closes:                                   # 先配 reply_to 指得到總機單的
        o = by_letter.get(c.get('reply_to'))
        if o is None:
            continue
        a = next((a for a in reversed(asks) if t(a) <= t(o)), None)
        if a is not None and a['id'] not in pair:
            pair[a['id']] = c
            used.add(c['id'])
    for a in asks:                                     # 其他照時間
        if a['id'] in pair:
            continue
        c = next((c for c in closes if c['id'] not in used and t(c) >= t(a)), None)
        if c is not None:
            pair[a['id']] = c
            used.add(c['id'])
    mfg_of = _mfg_for_asks(asks, pair, [o for o in orders if (o.get('to') or {}).get('dept') == 'mfg' and o.get('task')], t)
    secs, hops = [], []
    for a in asks:
        if a['id'] in skip:
            continue
        t0, c = t(a), pair.get(a['id'])
        if c is None:
            if t_since is None or t0 >= t_since:
                res['failed'] += 1
                res['timeout'] += 1
                res['timeout_ids'].append(a['id'])
            continue
        t1 = t(c)
        if t_since is not None and t1 < t_since:
            continue
        inside = [o for o in orders if t0 <= t(o) <= t1]
        qa = [o for o in inside if (o.get('to') or {}).get('dept') == 'qa']
        linked = by_letter.get(c.get('reply_to'))
        cand = [linked] if linked is not None and (linked.get('to') or {}).get('dept') == 'qa' else \
            sorted((o for o in qa if o.get('status') == 'done'), key=lambda o: o.get('closed_at') or o['at'], reverse=True)
        verdict, qa_order = None, None
        for o in cand:
            verdict = _qa_verdict(teams, o)
            if verdict is not None:
                qa_order = o
                break
        if verdict is not None:
            ok = c['status'] == 'DONE' and verdict and qa_order.get('status') == 'done'
        else:                                          # 沒有報告檔可看：退回看結案信（真跑 5 家：總裁寫「結論為：合格」）
            ok = (c['status'] == 'DONE' and bool(VERDICT.search(c.get('text') or ''))
                  and not VERDICT.search(c.get('text') or '').group(1)
                  and any(o.get('status') == 'done' for o in qa))
        if ok:
            res['done'] += 1
            secs.append(max(0.0, (t1 - t0).total_seconds()))
            hops.append(len(inside) + 1)
            o = mfg_of.get(a['id'])
            res['reviews'].append(_review_rounds(teams, o) if o is not None else None)
            if o is None:
                res.setdefault('notes', []).append(
                    '董事的單 %s：配不到製造總機單（這段時間沒有、或都被先下的單配走了），審查輪數記 None' % a['id'])
        else:
            res['failed'] += 1
    if secs:
        res['seconds'] = round(sum(secs) / len(secs), 1)
        res['hops'] = round(sum(hops) / len(hops), 2)
    return res


def record_score(mdir, name, quality=None, eval_path=None, seconds=None, hops=None, done=None):
    with market_lock(mdir):
        return _record_score(mdir, name, quality, eval_path, seconds, hops, done)


def _record_score(mdir, name, quality, eval_path, seconds, hops, done):
    m = load(mdir)
    if name not in m['companies']:
        raise MarketError('NotFound', '市場裡沒有 %s' % name)
    src, notes = 'manual', []
    cdir = m['companies'][name]['dir']
    if eval_path is not None:
        try:
            project = co.load(cdir).get('project')
        except TeamError:
            project = None
        quality, notes = quality_from_eval(fmt.read_json(eval_path), project=project, notes=True)
        src = 'eval:%s' % eval_path
    _finite(quality, 'quality', 0, 100)
    _finite(seconds, 'seconds', 0)
    _finite(hops, 'hops', 0)
    _finite(done, 'done', 0)
    since = m['history'][-1]['at'] if m['history'] else None
    cur = len(m['history']) + 1
    # 以前的輪算過逾時的單：不再算（market.json 的 timed_out：{公司: {單號: 輪次}}；同一輪重打分會重算這一輪的）
    timed = m.setdefault('timed_out', {}).setdefault(name, {})
    try:
        bd = board_from_company(cdir, since, skip=[k for k, r in timed.items() if r < cur])
    except TeamError:
        bd = {'done': 0, 'failed': 0, 'timeout': 0, 'timeout_ids': [], 'seconds': None, 'hops': None, 'reviews': []}
    for k in [k for k, r in timed.items() if r >= cur]:
        del timed[k]
    timed.update({k: cur for k in bd['timeout_ids']})
    if done is None:
        done = 1 if seconds is not None else bd['done']        # 經理人手給秒數＝他認定有一張成功
    notes.extend(bd.get('notes') or [])
    rounds = bd['reviews']
    facs = [review_factor(r, m['params']['review_factors']) for r in rounds]
    if not rounds or None in facs:                   # 舊資料／手給的成功：沒審查紀錄的那幾張當一次過
        notes.append('%s：%s沒有審查紀錄，審查係數當 1.0' % (
            name, '成功的單' if not rounds else '成功的 %d 張裡有 %d 張' % (len(rounds), facs.count(None))))
    rf = round(sum(1.0 if f is None else f for f in facs) / len(facs), 4) if facs else None
    s = {'quality': quality, 'seconds': seconds if seconds is not None else bd['seconds'],
         'hops': hops if hops is not None else bd['hops'], 'done': done, 'failed': bd['failed'],
         'timeout': bd['timeout'], 'review_rounds': rounds, 'review_factor': rf,
         'at': now(), 'source': src, 'round': cur}     # 分數綁輪次：grant 之後就不算了
    if notes:
        s['notes'] = notes
    m['scores'][name] = s
    save(mdir, m)
    return s
