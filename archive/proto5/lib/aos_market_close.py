"""市場的倒閉與裁撤：花光或被裁的公司停機、回收額度與名額、崩在半路的收尾重跑。"""
from pathlib import Path
import shutil
import time
import uuid

import aos_company as co
import aos_team_cost as cost
from aos_team_format import TeamError

from aos_market_book import _event, cost_base, load, market_lock, MarketError, now, operating, save


# ------------------------------------------------------------------ 倒閉 ----

def _close_row(mdir, m, bal, name, reason):
    """收掉一家要記的東西（試算也用）：餘額、要收回的、名額、放出的名字、封存到哪。"""
    c = m['companies'][name]
    cdir = Path(c['dir'])
    left = (bal.get(name) or {}).get('balance') or {}
    try:
        cfg = co.load(cdir)
        freed = co.all_member_names(cdir, cfg)
        slots = dict(cfg['limits'])
    except TeamError:
        freed, slots = [], {}
    dest = Path(mdir) / 'archive' / ('%s-%s-%s' % (name, reason, time.strftime('%Y%m%d-%H%M%S')))
    return {'name': name, 'reason': reason, 'balance': left,
            'recycled': {k: v for k, v in left.items() if v is not None and v > 0}, 'slots': slots, 'freed': freed,
            'archive': str(dest)}


def _stop(cdir, stop):
    """停一家；停不乾淨＝StopFailed（不封存、不收回、不放名額，astra 必修 4）。"""
    cdir = Path(cdir)
    if stop and (cdir / 'company.json').is_file() and (cdir / 'K').is_dir():
        if co.down(cdir, out=lambda *_: None) != 0:
            raise MarketError('StopFailed', '%s 沒停乾淨（company.py down -C %s 看哪裡），先不封存、名額不放；'
                              '停好再跑一次同一個指令' % (cdir, cdir))


def _shutdown(mdir, m, base, name, reason, stop=True):
    """收掉一家，分兩段、每段先記再做（astra 必修 2、4）：
    1. 標 closing（記下封存目的地、操作 ID、名額）並存檔——這時還占著名額與錢；
    2. 停（失敗＝停在 closing，重跑同一個指令接著做）→ 停好後才讀餘額、收回（操作 ID 去重）→ 搬進 archive → 標結案。"""
    c = m['companies'][name]
    if c['status'] != 'closing':
        row = _close_row(mdir, m, cost.balances(base), name, reason)
        c['closing'] = {'reason': reason, 'archive': row['archive'], 'slots': row['slots'], 'freed': row['freed'],
                        'op': '%s-%s-%s' % (reason, name, uuid.uuid4().hex[:8]), 'recycled': None}
        c['status'] = 'closing'
        save(mdir, m)
    return _finish_close(mdir, m, base, name, stop)


def _finish_close(mdir, m, base, name, stop=True):
    c = m['companies'][name]
    cl = c['closing']
    cdir, dest = Path(c['dir']), Path(cl['archive'])
    if cdir.is_dir():
        _stop(cdir, stop)
    b = cost.balances(base).get(name) or {}
    left = b.get('balance') or {}
    if cl.get('recycled') is None:                   # 停好後才算：還在跑的單記的帳都進來了
        cl['recycled'] = {k: v for k, v in left.items() if v is not None and v > 0}
        cl['balance'] = left
        save(mdir, m)
    rec = cl['recycled']
    if rec:
        cost.account_grant(base, name, usd=-rec['usd'] if 'usd' in rec else None,
                           tokens=-rec['tokens'] if 'tokens' in rec else None, op=cl['op'] + ':recycle',
                           note='%s：沒花完的配額收回總池' % ('倒閉' if cl['reason'] == 'bankrupt' else '裁撤'))
    if cdir.is_dir() and not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(cdir), str(dest))
    reason = cl['reason']
    c.update(status='bankrupt' if reason == 'bankrupt' else 'closed', closed_at=now(), archive=str(dest),
             freed=cl['freed'])
    c.pop('closing', None)
    _event(m, kind=reason, company=name, recycled=rec, slots=cl['slots'], freed=cl['freed'])
    save(mdir, m)
    return {'name': name, 'reason': reason, 'balance': cl.get('balance', left), 'recycled': rec,
            'slots': cl['slots'], 'freed': cl['freed'], 'archive': str(dest)}


def _recover_closing(mdir, m, base, stop=True):
    """上次收到一半（closing）的先收完。"""
    return [_finish_close(mdir, m, base, n, stop) for n, c in list(m['companies'].items()) if c['status'] == 'closing']


def bankrupt(mdir, dry_run=False, env=None, stop=True):
    """餘額 ≤ 0（有撥過的那一種）的營業中公司倒閉：另一種還有剩的收回總池；名額回總池；停、封存（前綴可以再用）。
    上次收到一半的（closing）先收完。"""
    base = cost_base(env)
    if dry_run:
        m, bal = load(mdir), cost.balances(base)
        return [_close_row(mdir, m, bal, n, 'bankrupt') for n in operating(m) if (bal.get(n) or {}).get('broke')]
    with market_lock(mdir):
        m = load(mdir)
        out = [r for r in _recover_closing(mdir, m, base, stop) if r['reason'] == 'bankrupt']
        bal = cost.balances(base)
        for n in [n for n in operating(m) if (bal.get(n) or {}).get('broke')]:
            out.append(_shutdown(mdir, m, base, n, 'bankrupt', stop))
        return out


def close(mdir, name, dry_run=False, env=None, stop=True):
    """經理人裁撤一家（還沒花光）：沒花完的配額全部收回總池，其餘同倒閉。"""
    base = cost_base(env)
    if dry_run:
        m = load(mdir)
        if name not in operating(m):
            raise MarketError('NotFound', '%s 不在營業' % name)
        return _close_row(mdir, m, cost.balances(base), name, 'closed')
    with market_lock(mdir):
        m = load(mdir)
        c = m['companies'].get(name)
        if c is not None and c['status'] == 'closing':
            return _finish_close(mdir, m, base, name, stop)
        if name not in operating(m):
            raise MarketError('NotFound', '%s 不在營業' % name)
        return _shutdown(mdir, m, base, name, 'closed', stop)
