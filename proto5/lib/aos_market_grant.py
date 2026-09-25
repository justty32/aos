"""市場的開戶與撥款：開一家的帳戶、照品質／快／省加權排名、照名次撥額度、撥名額。"""
import json
import os
from pathlib import Path
import uuid

import aos_company as co
import aos_team_cost as cost
import aos_team_format as fmt

from aos_market_book import (
    _event, _finite, _overlap, cost_base, load, market_lock, MarketError, now, operating,
    pool_status, save, usd_floor
)


# ------------------------------------------------------------------ 開戶 ----

def open_company(mdir, name, cdir, usd=None, tokens=None, env=None):
    with market_lock(mdir):
        return _open_company(mdir, name, cdir, usd, tokens, env)


def _open_company(mdir, name, cdir, usd, tokens, env):
    base = cost_base(env)
    m = load(mdir)
    cdir = Path(os.path.abspath(os.path.expanduser(str(cdir))))
    co.load(cdir)                                    # 要是一家公司（company.json 驗得過）
    if name in m['companies']:
        # 收掉的名字不再用：舊帳戶還帶著它的撥款與花費，重用會把舊帳算進新公司（astra 必修 5）
        raise MarketError('AlreadyExists', '%s 已經在市場裡（%s）；換一個名字' % (name, m['companies'][name]['status']))
    real = os.path.realpath(str(cdir))
    for other, a in cost.load_accounts(base).items():
        root = a.get('root') or ''
        if other != name and root and _overlap(real, root):
            raise MarketError('Conflict', '%s 跟帳戶 %s 的資料夾 %s 重疊（同一個、或包著／被包著）：帳會重複算；換一個資料夾'
                              % (cdir, other, root))
    for other, c in m['companies'].items():
        if _overlap(real, os.path.realpath(c['dir'])):
            raise MarketError('Conflict', '%s 跟 %s（%s）用過的資料夾 %s 重疊' % (cdir, other, c['status'], c['dir']))
    seed = m['params']['seed']
    usd = seed.get('usd') if usd is None else usd
    tokens = seed.get('tokens') if tokens is None else tokens
    _finite(usd, 'usd', 0)
    _finite(tokens, 'tokens', 0)
    pool = pool_status(m, cost.balances(base))
    for k, v in (('usd', usd), ('tokens', tokens)):
        if k in pool['money'] and (v or 0) > pool['money'][k]:
            raise MarketError('PoolEmpty', '總池的 %s 只剩 %s，開辦費要 %s' % (k, pool['money'][k], v))
    lim = co.load(cdir)['limits']
    short = [k for k in pool['slots'] if lim.get(k, 0) > pool['slots'][k]]
    if short:
        raise MarketError('NoSlots', '機器名額不夠：%s（剩 %s，這家要 %s）' % (
            '、'.join(short), json.dumps(pool['slots']), json.dumps(lim)))
    cost.account_open(base, name, str(cdir))
    cost.account_grant(base, name, usd=usd, tokens=tokens, note='開辦費', op='open-%s' % name)
    m['companies'][name] = {'dir': str(cdir), 'status': 'operating', 'opened_at': now(), 'closed_at': None,
                            'note': ''}
    _event(m, kind='open', company=name, grant={'usd': usd, 'tokens': tokens}, slots=lim)
    save(mdir, m)
    return m['companies'][name]


# ------------------------------------------------------------------ 排名 ----

def rank(m, bal):
    """回一列一家（照排名分高到低）：quality、speed、cost 三項各 0～100，再加權。

    - **這輪沒有成功結案（done＝0）的：品質、快、省、排名分全 0**（真跑 09-25：做壞的單照樣拿滿分品質）。
    - 品質＝記下的分數（原始品質 raw_quality，沒記＝0）× 成功率 × 審查係數（第 74、75 題，經理人 09-25 晚）：
      成功率＝成功張數 ÷ 董事下單張數（成功＋失敗，失敗含逾時）；審查係數＝score 記的 review_factor
      （成功那幾張第幾次審查才過，照 params.review_factors 換算再平均；沒記＝1.0，那列 note 寫出來——
      整份沒記〔review_factor 沒有〕、或 review_rounds 裡有幾張 None 都寫）。係數在 score 時算好存下，
      改 review_factors 之後要重新 score 才生效。
    - 快：**只在成功張數最多的幾家之間比**董事等的秒數，最快那家 ÷ 自己 ×100；成功張數比較少的「快」＝0（第 74 題）。
    - 省：這一輪花的 token（這輪已花 − 上輪記下的已花），**只在成功的幾家之間比**，最省那家 ÷ 自己 ×100；成功但沒花＝100。
    - 只有一家成功：快、省都是滿分，那一列 note 寫「無對照」。
    - 同分同名次（名次跳號，例 1、1、3）；列的順序同分再照品質、名字排，只為了印得穩定。
    """
    w = m['params']['weights']
    last_spent = (m['history'][-1].get('spent') if m['history'] else None) or {}
    cur = len(m['history']) + 1
    rows = []
    for name in operating(m):
        s = m['scores'].get(name) or {}
        if s.get('round') != cur:           # 上一輪（或沒記輪次）的分數不算：這輪沒做事就沒分（astra 必修 9）
            s = {}
        b = bal.get(name) or {}
        spent_now = (b.get('spent') or {}).get('tokens') or 0
        spent = max(0, spent_now - (last_spent.get(name) or 0))
        done = s.get('done') or 0
        asked = done + (s.get('failed') or 0)
        rate = round(done / asked, 4) if asked else 0.0
        rf = s.get('review_factor')
        rows.append({'name': name, 'quality': round(float(s.get('quality') or 0) * rate * (1.0 if rf is None else rf), 2)
                     if done else 0.0, 'success_rate': rate, 'review_factor': rf, 'review_rounds': s.get('review_rounds'),
                     'raw_quality': s.get('quality'), 'seconds': s.get('seconds'),
                     'hops': s.get('hops'), 'done': done, 'failed': s.get('failed') or 0, 'spent_tokens': spent,
                     'spent_total': spent_now, 'balance': b.get('balance'), 'broke': b.get('broke', False),
                     'scored': bool(s), 'note': None})
    ok = [r for r in rows if r['done']]
    top = max((r['done'] for r in ok), default=0)
    fast = [r['seconds'] for r in ok if r['seconds'] is not None and r['done'] == top]   # 0 秒也算（astra 審查必修 3）
    cheap = [r['spent_tokens'] for r in ok if r['spent_tokens']]
    for r in rows:
        notes = []
        rr = r['review_rounds'] if isinstance(r['review_rounds'], list) else []
        if r['done'] and r['review_factor'] is None:
            notes.append('沒有審查紀錄：審查係數當 1.0')
        elif r['done'] and None in rr:                # score 時已當 1.0 平均進去；這裡要看得到（astra 審查建議 2）
            notes.append('沒有審查紀錄：成功的 %d 張裡有 %d 張審查係數當 1.0' % (len(rr), rr.count(None)))
        if r['done'] and r['done'] < top:
            notes.append('快：成功 %d 張少於最多的 %d 張，不比快（0）' % (r['done'], top))
        if not (r['done'] == top and top and fast and r['seconds'] is not None):
            r['speed'] = 0.0
        elif r['seconds'] == 0:
            r['speed'] = 100.0                 # 0 秒＝最快（以前當成沒秒數、快＝0）
        else:
            r['speed'] = round(100 * min(fast) / r['seconds'], 2)
        if not r['done']:
            r['cost'] = 0.0
        elif not r['spent_tokens']:
            r['cost'] = 100.0                  # 成功、這輪沒花 token＝最省（試玩 09-25：三家都 0 不該全拿 0）
        else:
            r['cost'] = round(100 * min(cheap) / r['spent_tokens'], 2)
        if r['done'] and len(ok) == 1:
            notes.insert(0, '省、快：無對照（這輪只有它成功）')
        r['note'] = '；'.join(notes) or None
        r['score'] = round(w['quality'] * r['quality'] + w['speed'] * r['speed'] + w['cost'] * r['cost'], 2)
    rows.sort(key=lambda r: (-r['score'], -r['quality'], r['name']))
    for i, r in enumerate(rows, 1):
        r['rank'] = i if i == 1 or r['score'] != rows[i - 2]['score'] else rows[i - 2]['rank']
    return rows


def plan_grants(m, rows, usd_over=None, tok_over=None):
    """照排名分這一輪的總額：shares 取前 n 個按比例放大到 1；**同分的把那幾個名次的 shares 平均分**（不照名字破平）；
    這輪沒成功結案的、品質低於 min_quality 的、已經花光（broke）的拿 0；
    覆寫的照覆寫（花光的不准覆寫：先 bankrupt，astra 必修 11）。美元往下取到 0.0001。"""
    usd_over, tok_over = usd_over or {}, tok_over or {}
    for over in (usd_over, tok_over):
        for n, v in over.items():
            _finite(v, '%s 的覆寫' % n, 0)
            r = next((r for r in rows if r['name'] == n), None)
            if r is None:
                raise MarketError('NotFound', '%s 不在營業，不能覆寫' % n)
            if r['broke']:
                raise MarketError('Broke', '%s 已經花光，要先 bankrupt，不能撥款救活' % n)
    pool = m['params']['round_pool']
    shares = list(m['params']['shares'])[:len(rows)]
    shares += [0.0] * (len(rows) - len(shares))
    for sc in {r['score'] for r in rows}:                   # 同分均分
        idx = [i for i, r in enumerate(rows) if r['score'] == sc]
        avg = sum(shares[i] for i in idx) / len(idx)
        for i in idx:
            shares[i] = avg
    eligible = [r['done'] > 0 and r['quality'] >= m['params']['min_quality'] and not r['broke'] for r in rows]
    tot = sum(s for s, ok in zip(shares, eligible) if ok) or 1.0
    out = {}
    for r, s, ok in zip(rows, shares, eligible):
        frac = s / tot if ok else 0.0
        g = {'usd': usd_floor(pool.get('usd', 0) * frac) if pool.get('usd') is not None else None,
             'tokens': int(pool.get('tokens', 0) * frac) if pool.get('tokens') is not None else None,
             'share': round(frac, 4), 'override': False}
        if r['name'] in usd_over:
            g['usd'], g['override'] = usd_over[r['name']], True
        if r['name'] in tok_over:
            g['tokens'], g['override'] = tok_over[r['name']], True
        out[r['name']] = g
    return out


def do_grant(mdir, usd_over=None, tok_over=None, dry_run=False, env=None):
    """一輪撥款。順序（astra 必修 1、11）：先確定這輪要撥什麼（排名、縮額）→ 存進 market.json 的 pending
    （含操作 ID）→ 逐家撥（帳戶照操作 ID 去重）→ 記 history、清 pending。崩在中間重跑＝接著同一份計畫撥，不重撥。
    花光的公司不撥：先跑 bankrupt 再 grant。"""
    if dry_run:
        return _plan_grant(mdir, load(mdir), cost.balances(cost_base(env)), usd_over, tok_over)[:3]
    with market_lock(mdir):
        base = cost_base(env)
        m = load(mdir)
        pend = m.get('pending')
        if pend and pend.get('kind') == 'grant':
            rnd, rows, grants, capped, op = pend['round'], pend['ranking'], pend['grants'], pend['capped'], pend['op']
        else:
            if pend:
                raise MarketError('Pending', '還有沒做完的 %s（再跑一次那個指令接著做）' % pend.get('kind'))
            rnd, rows, grants, capped = _plan_grant(mdir, m, cost.balances(base), usd_over, tok_over)
            op = 'grant-r%d-%s' % (rnd, uuid.uuid4().hex[:8])
            m['pending'] = {'kind': 'grant', 'round': rnd, 'op': op, 'ranking': rows, 'grants': grants, 'capped': capped}
            save(mdir, m)
        for name, g in grants.items():
            if (g['usd'] or 0) == 0 and (g['tokens'] or 0) == 0:
                continue
            cost.account_grant(base, name, usd=g['usd'], tokens=g['tokens'], op='%s:%s' % (op, name),
                               note='第 %d 輪 第 %d 名%s' % (rnd, next(r['rank'] for r in rows if r['name'] == name),
                                                          '（經理人覆寫）' if g['override'] else ''))
        m['history'].append({'round': rnd, 'at': now(), 'ranking': rows, 'grants': grants, 'capped': capped,
                             'spent': {r['name']: r['spent_total'] for r in rows}, 'op': op})
        _event(m, kind='grant', round=rnd, grants={n: {'usd': g['usd'], 'tokens': g['tokens']} for n, g in grants.items()},
               capped=capped)
        m.pop('pending', None)
        save(mdir, m)
        return rnd, rows, grants


def _plan_grant(mdir, m, bal, usd_over, tok_over):
    rows = rank(m, bal)
    grants = plan_grants(m, rows, usd_over, tok_over)
    if not any(r['scored'] for r in rows):
        # 真跑 09-25：撥完一輪什麼都沒做再 grant，第 2 輪照樣整份發出去。這輪一家都沒 score＝拒絕、什麼都不發
        raise MarketError('NoScores', '本輪無分數（第 %d 輪還沒有任何一家 score）：什麼都沒發；先 score 再 grant'
                          % (len(m['history']) + 1))
    pool = pool_status(m, bal)
    capped = {}
    for k, left in pool['money'].items():
        want = sum((g[k] or 0) for g in grants.values() if (g[k] or 0) > 0)
        if want > left:                                  # 總池不夠：照比例往下縮（不會超過剩的）
            f = max(0.0, left) / want if want else 0.0
            for g in grants.values():
                if (g[k] or 0) > 0:
                    g[k] = usd_floor(g[k] * f) if k == 'usd' else int(g[k] * f)
            got = sum((g[k] or 0) for g in grants.values() if (g[k] or 0) > 0)
            assert got <= max(0.0, left) + 1e-9, (k, got, left)
            capped[k] = {'want': want, 'pool': left}
    return len(m['history']) + 1, rows, grants, capped


def grant_slots(mdir, name, regular=0, cpu=0, llm_cpu=0, env=None):
    """從總池撥名額給一家：llm cpu＝limits.llm_cpu、pools.llm +1；cpu（不含 llm，同 HR 的算法）＝limits.cpu、
    pools.default +1；人頭＝limits.regular +1。不能超過那家的 limits_max 與總池。
    kernel 開著的話池要 aos-kernel cpu add 才真的多開（這裡只改 company.json；下次 up 對齊 K 的池）。
    只收 ≥ 0：收回名額不走這裡（名額只在公司收掉、確定停好時回總池，astra 必修 12）。"""
    with market_lock(mdir):
        return _grant_slots(mdir, name, regular, cpu, llm_cpu, env)


def _grant_slots(mdir, name, regular, cpu, llm_cpu, env):
    m = load(mdir)
    if name not in operating(m):
        raise MarketError('NotFound', '%s 不在營業' % name)
    want = {'regular': regular, 'cpu': cpu, 'llm_cpu': llm_cpu}
    for k, v in want.items():
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise MarketError('Usage', 'slots 的 %s 要是 ≥ 0 的整數（收回名額不走這裡）：%r' % (k, v))
    pool = pool_status(m, cost.balances(cost_base(env)))
    short = [k for k, v in want.items() if v > pool['slots'][k]]
    if short:
        raise MarketError('NoSlots', '總池名額不夠：%s（剩 %s）' % ('、'.join(short), json.dumps(pool['slots'])))
    cdir = Path(m['companies'][name]['dir'])
    raw = fmt.read_json(cdir / 'company.json')
    cfg = co.load(cdir)
    lim = dict(cfg['limits'])
    for k, v in want.items():
        lim[k] += v
    pools = dict(cfg['pools'])
    pools['llm'] += llm_cpu
    pools['default'] += cpu
    raw['limits'], raw['pools'] = lim, pools
    co.validate(raw, str(cdir / 'company.json'))          # 超過 limits_max＝擋
    fmt.write_json(cdir / 'company.json', raw, indent=2)
    _event(m, kind='slots', company=name, slots=want)
    save(mdir, m)
    return lim
