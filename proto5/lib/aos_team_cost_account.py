"""財務部的公司帳戶：accounts.json 開戶、撥款、轉帳、餘額（花到 0＝倒閉）、一個團隊資料夾屬於哪個帳戶。"""
import json
import os
import re

from aos_team_cost_ledger import _now, ACCOUNTS, CostError, load_prices, read_ledger, usd


# ------------------------------------------------------------------ 帳戶（一家公司一個） ----
# accounts.json：{"accounts": {名: {"root": 公司資料夾絕對路徑, "grants": [{"at", "usd", "tokens", "note"}…]}}}
# 已花＝帳本 team 欄落在 root 底下（或 team 欄就等於帳戶名，給 AOS_COST_TEAM 帶名字的呼叫）的全部紀錄，不分時段；
# 配額＝grants 加總；餘額＝配額 − 已花；有設的那一種（usd 或 tokens）餘額 ≤ 0＝倒閉（broke）。

ACCOUNT_NAME = re.compile(r'[a-z][a-z0-9_-]{0,31}\Z')


def load_accounts(base):
    path = os.path.join(base, ACCOUNTS)
    try:
        with open(path, encoding='utf-8') as f:
            obj = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise CostError('AccountsInvalid', '%s 讀不了：%s' % (path, e))
    acc = obj.get('accounts') if isinstance(obj, dict) else None
    if not isinstance(acc, dict):
        raise CostError('AccountsInvalid', '%s 要是 {"accounts": {…}}' % path)
    return acc


def _save_accounts(base, acc):
    path = os.path.join(base, ACCOUNTS)
    tmp = os.path.join(base, '.accounts.%d.tmp' % os.getpid())
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'accounts': acc}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _edit_accounts(base, fn):
    """在 flock 裡讀、改、寫 accounts.json（經理人和程式可能同時撥款）。"""
    import fcntl
    os.makedirs(base, exist_ok=True)
    with open(os.path.join(base, '.accounts.lock'), 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        acc = load_accounts(base)
        out = fn(acc)
        _save_accounts(base, acc)
        return out


def account_open(base, name, root):
    """開帳戶（已開就回原樣，root 不同＝錯）。root＝那家公司的資料夾，它的團隊都放在底下。"""
    if not ACCOUNT_NAME.match(name or ''):
        raise CostError('Usage', '帳戶名 %r 不合規（小寫英文開頭，a-z0-9_-，最長 32）' % name)
    root = os.path.realpath(os.path.expanduser(root))

    def fn(acc):
        if name in acc and acc[name].get('root') != root:
            raise CostError('Conflict', '帳戶 %s 已經綁 %s，不是 %s' % (name, acc[name].get('root'), root))
        acc.setdefault(name, {'root': root, 'grants': []})
        return acc[name]
    return _edit_accounts(base, fn)


def account_grant(base, name, usd=None, tokens=None, note='', op=None):
    """加配額（撥款）。usd／tokens 至少一個；可以是負的（收回）。回撥款後的那筆。
    op＝操作 ID（市場層用）：這個帳戶已經有同一個 op 的撥款＝不再撥、回原來那筆（崩了重跑不重撥）。"""
    if usd is None and tokens is None:
        raise CostError('Usage', '撥款要給 usd 或 tokens')
    grant = {'at': _now().isoformat(timespec='seconds'), 'usd': usd, 'tokens': tokens, 'note': note or ''}
    if op:
        grant['op'] = op

    def fn(acc):
        if name not in acc:
            raise CostError('NotFound', '沒有帳戶 %s（先 aos-team cost account open）' % name)
        grants = acc[name].setdefault('grants', [])
        if op:
            for g in grants:
                if g.get('op') == op:
                    return g
        grants.append(grant)
        return grant
    return _edit_accounts(base, fn)


def account_transfer(base, src, dst, usd=None, tokens=None, note='', op=None):
    """從 src 轉配額給 dst：同一次讀寫 accounts.json 裡 src 撥負的、dst 撥正的（不會只做一半）。
    op 必填：兩邊都已有這個 op＝已轉過，不再轉。回 (src 那筆, dst 那筆)。"""
    if usd is None and tokens is None:
        raise CostError('Usage', '轉帳要給 usd 或 tokens')
    if not op:
        raise CostError('Usage', '轉帳要給 op（去重用）')
    at = _now().isoformat(timespec='seconds')

    def fn(acc):
        for n in (src, dst):
            if n not in acc:
                raise CostError('NotFound', '沒有帳戶 %s' % n)
        out = []
        for n, sign in ((src, -1), (dst, 1)):
            grants = acc[n].setdefault('grants', [])
            hit = next((g for g in grants if g.get('op') == op), None)
            if hit is None:
                hit = {'at': at, 'usd': None if usd is None else sign * usd,
                       'tokens': None if tokens is None else sign * tokens, 'note': note or '', 'op': op}
                grants.append(hit)
            out.append(hit)
        return tuple(out)
    return _edit_accounts(base, fn)


def _in_account(row, name, root):
    team = row.get('team')
    return isinstance(team, str) and (team == name or team == root or team.startswith(root.rstrip('/') + '/'))


def balances(base, prices=None, rows=None):
    """{帳戶名: {"root", "quota": {"usd", "tokens"}, "spent": {...}, "balance": {...}, "broke": bool}}。
    quota 的某一種從沒撥過＝None（那一種不管，也不會因它倒閉）。"""
    prices = prices or load_prices(base)
    rows = read_ledger(base)[0] if rows is None else rows
    out = {}
    for name, a in load_accounts(base).items():
        root = a.get('root') or ''
        q = {'usd': None, 'tokens': None}
        for g in a.get('grants') or []:
            for k in q:
                if isinstance(g.get(k), (int, float)) and not isinstance(g.get(k), bool):
                    q[k] = (q[k] or 0) + g[k]
        mine = [r for r in rows if _in_account(r, name, root)]
        spent = {'tokens': sum(int(r.get('prompt_tokens') or 0) + int(r.get('completion_tokens') or 0) for r in mine),
                 'usd': round(sum(usd(r.get('model') or '', int(r.get('prompt_tokens') or 0),
                                      int(r.get('completion_tokens') or 0), prices) or 0 for r in mine), 6)}
        bal = {k: (None if q[k] is None else round(q[k] - spent[k], 6)) for k in q}
        out[name] = {'root': root, 'quota': q, 'spent': spent, 'balance': bal, 'calls': len(mine),
                     'broke': any(v is not None and v <= 0 for v in bal.values())}
    return out


def account_of(base, team_dir):
    """這個團隊資料夾歸哪個帳戶（root 最長的那個）；沒有＝None。"""
    team = os.path.realpath(team_dir)
    best = None
    for name, a in load_accounts(base).items():
        root = a.get('root') or ''
        if root and (team == root or team.startswith(root.rstrip('/') + '/')) and (best is None or len(root) > len(best[1])):
            best = (name, root)
    return best[0] if best else None
