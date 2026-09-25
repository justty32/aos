"""財務部（2026-09-25）：記帳、查帳、擋預算。規格 spec/team/cost.md。

- 帳本放 $AOS_COST_HOME/ledger.jsonl（一台機器一本）；同一夾有 prices.json（價格表）、budget.json（全公司預算）。
  沒設 AOS_COST_HOME＝不記帳（跟 AOS_HOPS 一樣：一次 dict 查詢就回，測試不會寫進真帳本）。
- 記帳：aos_llm_call.call（agent 思考）與 aos_llm_ask.ask（工具、壓縮、結晶、評審…）拿到端點回的 usage 就叫 record()。
  **寫失敗絕不擋呼叫**：任何例外都吞掉。
- 查帳：`aos-team cost [--by team|member|model|family|task] [--since 今天|本週|全部|YYYY-MM-DD] [--team] [--json]`。
  金額用**現在的**價格表重算（改了價格表，舊帳的估值跟著改）；價格表沒有的模型只記 token、不算錢，另印警告。
- 預算：全公司 budget.json＋團隊 team.json 的 budget。超了：郵差把新的 handoff／spawn 申請退件（FAILED「財務擋單：超支」
  回寄件人；09-25 五家真跑前是留在 outbox），每天每種超額寄一封給 human；aos-team ls 第一行印超額。已在跑的單不砍。
- 回填：`aos-team cost import 資料夾…` 把找得到的 members/<名>/log/usage*.jsonl 撈進帳本（重跑不重記）。
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

ENV = 'AOS_COST_HOME'
LEDGER, PRICES, BUDGET, ACCOUNTS = 'ledger.jsonl', 'prices.json', 'budget.json', 'accounts.json'
HOLD_KINDS = ('handoff', 'spawn')          # 超預算時郵差退件的申請（開新單、生新成員）
BY = ('family', 'model', 'team', 'member', 'task', 'source')
LIMIT_KEYS = ('usd', 'tokens', 'since')

CPU_LIMITS = {'max': 20, 'llm_max': 5}   # 新創規模（董事 09-25）；擴張到 200／20 就在 budget.json 寫 "cpus"（名額歸 HR 管，這裡只印）
DEFAULT_FAMILIES = {'claude': ['claude-'], 'gpt': ['chatgpt-', 'gpt-'], 'deepseek': ['deepseek-'],
                    'local': ['ollama-', 'lm-']}


class CostError(Exception):
    def __init__(self, code, msg):
        super().__init__('%s: %s' % (code, msg))
        self.code, self.msg = code, msg


def home(env=None):
    env = os.environ if env is None else env
    path = env.get(ENV)
    if not path or not os.path.isabs(path):
        return None
    return path


# ------------------------------------------------------------------ 價格表 ----

def load_prices(base):
    """回 {"families": {家族: [前綴…]}, "models": {模型或前綴*: {"in": 美元/百萬, "out": …}}}。檔不在＝空價格表。"""
    path = os.path.join(base, PRICES)
    try:
        with open(path, encoding='utf-8') as f:
            obj = json.load(f)
    except FileNotFoundError:
        obj = {}
    except (OSError, ValueError) as e:
        raise CostError('PricesInvalid', '%s 讀不了：%s' % (path, e))
    if not isinstance(obj, dict):
        raise CostError('PricesInvalid', '%s 頂層要是物件' % path)
    fams = obj.get('families') or DEFAULT_FAMILIES
    models = obj.get('models') or {}
    if not isinstance(fams, dict) or not isinstance(models, dict):
        raise CostError('PricesInvalid', '%s：families、models 要是物件' % path)
    for k, v in models.items():
        if not (isinstance(v, dict) and all(isinstance(v.get(x), (int, float)) and v.get(x) >= 0 for x in ('in', 'out'))):
            raise CostError('PricesInvalid', '%s：models.%s 要是 {"in": 數字, "out": 數字}（美元／百萬 token）' % (path, k))
    return {'families': fams, 'models': models}


def family(model, prices):
    """模型名 → 家族（照 families 的前綴，最長的贏）；都不中＝other。"""
    best, hit = '', 'other'
    for fam, prefixes in prices['families'].items():
        for p in prefixes if isinstance(prefixes, list) else []:
            if isinstance(p, str) and model.startswith(p) and len(p) > len(best):
                best, hit = p, fam
    return hit


def price(model, prices):
    """(進價, 出價) 美元／百萬 token；完全相同的鍵優先，其次 `前綴*` 最長的；沒有＝None。"""
    table = prices['models']
    if model in table:
        return table[model]['in'], table[model]['out']
    best = None
    for k in table:
        if k.endswith('*') and model.startswith(k[:-1]) and (best is None or len(k) > len(best)):
            best = k
    return (table[best]['in'], table[best]['out']) if best else None


def usd(model, pt, ct, prices):
    p = price(model, prices)
    if p is None:
        return None
    return round((pt * p[0] + ct * p[1]) / 1e6, 6)


# ------------------------------------------------------------------ 記帳 ----

def _now():
    return datetime.datetime.now().astimezone()


def _team_of(agent_dir):
    """agent 家 → (團隊資料夾, 成員名)；家不在 <團隊>/members/<名>/ 底下＝(None, 家的資料夾名)。"""
    base = os.path.realpath(agent_dir)
    members = os.path.dirname(base)
    team = os.path.dirname(members)
    if os.path.basename(members) == 'members' and os.path.isfile(os.path.join(team, 'team.json')):
        return team, os.path.basename(base)
    return None, os.path.basename(base)


def _task_of(team, member):
    """這個成員手上沒結束的單（最近更新的那張）；找不到＝None。只讀 team/tasks/*.json，壞檔略過。"""
    best = None
    for p in glob.glob(os.path.join(team, 'team', 'tasks', '*.json')):
        try:
            with open(p, encoding='utf-8') as f:
                t = json.load(f)
        except (OSError, ValueError):
            continue
        if (isinstance(t, dict) and t.get('assignee') == member
                and t.get('status') not in ('done', 'failed', 'cancelled')):
            key = str(t.get('updated_at') or '')
            if best is None or key > best[0]:
                best = (key, t.get('id'))
    return best[1] if best else None


def _tokens(usage):
    u = usage if isinstance(usage, dict) else {}
    pt, ct = u.get('prompt_tokens'), u.get('completion_tokens')
    pt = pt if type(pt) is int and pt >= 0 else 0
    ct = ct if type(ct) is int and ct >= 0 else 0
    return pt, ct


def make_row(*, model, alias=None, usage=None, ms=None, source, team=None, member=None, task=None,
             batch=None, at=None, prices=None, extra=None):
    pt, ct = _tokens(usage)
    prices = prices or {'families': DEFAULT_FAMILIES, 'models': {}}
    row = {'at': at or _now().isoformat(timespec='milliseconds'), 'team': team, 'member': member, 'task': task,
           'model': model, 'alias': alias, 'family': family(model or '', prices),
           'prompt_tokens': pt, 'completion_tokens': ct, 'usage_missing': not isinstance(usage, dict),
           'usd': usd(model or '', pt, ct, prices), 'source': source, 'batch': batch, 'ms': ms}
    if extra:
        row.update(extra)
    return row


def append(base, rows):
    """一行一次 write（O_APPEND），多支程式同時寫不會交錯。"""
    data = ''.join(json.dumps(r, ensure_ascii=True, default=str) + '\n' for r in rows).encode('ascii')
    os.makedirs(base, exist_ok=True)
    fd = os.open(os.path.join(base, LEDGER), os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC, 0o644)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def record(env=None, *, model, alias=None, usage=None, ms=None, source='ask', agent_dir=None, batch=None):
    """記一筆。沒設 AOS_COST_HOME 立刻回；任何錯都吞掉（絕不擋呼叫）。回有沒有記。"""
    try:
        env = os.environ if env is None else env
        base = home(env)
        if base is None:
            return False
        team, member, task = env.get('AOS_COST_TEAM') or None, env.get('AOS_COST_MEMBER') or None, None
        if agent_dir:
            t, member = _team_of(agent_dir)
            team = t or team
        if team and member:
            task = _task_of(team, member)
        task = env.get('AOS_COST_TASK') or task
        try:
            prices = load_prices(base)
        except CostError:
            prices = None
        append(base, [make_row(model=model, alias=alias, usage=usage, ms=ms, source=env.get('AOS_COST_SOURCE') or source,
                               team=team, member=member, task=task, batch=batch or env.get('AOS_LLM_BATCH') or None,
                               prices=prices)])
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ 查帳 ----

def read_ledger(base):
    rows, bad = [], 0
    try:
        f = open(os.path.join(base, LEDGER), encoding='utf-8', errors='replace')
    except FileNotFoundError:
        return rows, 0
    with f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if isinstance(r, dict) and isinstance(r.get('at'), str):
                rows.append(r)
            else:
                bad += 1
    return rows, bad


def _at(row):
    try:
        t = datetime.datetime.fromisoformat(row['at'])
    except (ValueError, TypeError, KeyError):
        return None
    return t if t.tzinfo else t.astimezone()


def since_time(text, now=None):
    """今天／day、本週／week（週一 0 點）、全部／all、YYYY-MM-DD（本地時間 0 點）。回 aware datetime 或 None（＝全部）。"""
    now = now or _now()
    text = (text or 'week').strip()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if text in ('今天', 'today', 'day'):
        return midnight
    if text in ('本週', 'week'):
        return midnight - datetime.timedelta(days=midnight.weekday())
    if text in ('全部', 'all'):
        return None
    try:
        d = datetime.date.fromisoformat(text)
    except ValueError:
        raise CostError('Usage', '--since 看不懂 %r（今天、本週、全部、YYYY-MM-DD）' % text)
    return datetime.datetime(d.year, d.month, d.day, tzinfo=now.tzinfo)


def select(rows, since=None, team=None):
    out = []
    for r in rows:
        t = _at(r)
        if since is not None and (t is None or t < since):
            continue
        if team is not None and r.get('team') != team:
            continue
        out.append(r)
    return out


def summarize(rows, by, prices):
    """分組加總。金額用現在的價格表重算；價格表沒有的模型記進 unpriced。"""
    groups, unpriced = {}, {}
    for r in rows:
        model = r.get('model') or '?'
        key = model if by == 'model' else (family(model, prices) if by == 'family' else r.get(by))
        key = key if key is not None else '-'
        g = groups.setdefault(key, {'key': key, 'calls': 0, 'prompt_tokens': 0, 'completion_tokens': 0,
                                    'usd': 0.0, 'unpriced_tokens': 0, 'usage_missing': 0})
        pt, ct = int(r.get('prompt_tokens') or 0), int(r.get('completion_tokens') or 0)
        g['calls'] += 1
        g['prompt_tokens'] += pt
        g['completion_tokens'] += ct
        g['usage_missing'] += 1 if r.get('usage_missing') else 0
        cost = usd(model, pt, ct, prices)
        if cost is None:
            g['unpriced_tokens'] += pt + ct
            unpriced[model] = unpriced.get(model, 0) + pt + ct
        else:
            g['usd'] += cost
    out = sorted(groups.values(), key=lambda g: (-g['usd'], -(g['prompt_tokens'] + g['completion_tokens'])))
    for g in out:
        g['tokens'] = g['prompt_tokens'] + g['completion_tokens']
        g['usd'] = round(g['usd'], 4)
    return out, unpriced


# ------------------------------------------------------------------ 預算 ----

def check_budget(obj, where):
    """驗預算的形狀（team.json 的 budget 與 budget.json 共用）；回補好 since 的新物件。錯丟 ValueError(白話)。

    {"since": "week"|"day"|"all"|"YYYY-MM-DD", "<家族>|all": {"usd": 數字, "tokens": 整數}, …}"""
    if obj is None:
        return None
    if not isinstance(obj, dict):
        raise ValueError('%s 要是物件' % where)
    out = {'since': obj.get('since', 'week')}
    if not isinstance(out['since'], str):
        raise ValueError('%s.since 要是字串（week、day、all、YYYY-MM-DD）' % where)
    try:
        since_time(out['since'])
    except CostError as e:
        raise ValueError('%s.since：%s' % (where, e.msg))
    for fam, lim in obj.items():
        if fam in ('since', '_metainfo', '_note'):
            continue
        if fam == 'cpus':                  # 只給 cost 表的 cpu 行當上限顯示，不是花費預算
            if not isinstance(lim, dict) or set(lim) - set(CPU_LIMITS) or not all(
                    type(v) is int and v > 0 for v in lim.values()):
                raise ValueError('%s.cpus 要是 {"max": 正整數, "llm_max": 正整數}' % where)
            out['cpus'] = dict(lim)
            continue
        if not isinstance(lim, dict) or not (set(lim) - {'since'}) or set(lim) - set(LIMIT_KEYS):
            raise ValueError('%s.%s 要是 {"usd": 數字} 或 {"tokens": 整數}（可兩個都寫，可另加 since）' % (where, fam))
        if 'since' in lim:
            try:
                since_time(lim['since'] if isinstance(lim['since'], str) else '?')
            except CostError as e:
                raise ValueError('%s.%s.since：%s' % (where, fam, e.msg))
        for k, v in lim.items():
            if k == 'since':
                continue
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 or (k == 'tokens' and not isinstance(v, int)):
                raise ValueError('%s.%s.%s 要是 ≥ 0 的%s' % (where, fam, k, '整數' if k == 'tokens' else '數字'))
        out[fam] = dict(lim)
    return out


def load_company_budget(base):
    path = os.path.join(base, BUDGET)
    try:
        with open(path, encoding='utf-8') as f:
            obj = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        raise CostError('BudgetInvalid', '%s 讀不了：%s' % (path, e))
    try:
        return check_budget(obj, BUDGET)
    except ValueError as e:
        raise CostError('BudgetInvalid', str(e))


def load_team_budget(team_dir):
    path = os.path.join(team_dir, 'team.json')
    try:
        with open(path, encoding='utf-8') as f:
            obj = json.load(f)
    except (OSError, ValueError):
        return None
    try:
        return check_budget(obj.get('budget') if isinstance(obj, dict) else None, 'team.json.budget')
    except ValueError:
        return None       # 名冊壞了由 load_roster 報；這裡當沒預算


def usage_against(budget, rows, prices, scope, now=None):
    """一份預算 → [{scope, family, kind, used, limit, ratio, since}]。"""
    if not budget:
        return []
    out = []
    for fam, lim in budget.items():
        if fam in ('since', 'cpus'):
            continue
        start = lim.get('since', budget['since'])
        mine = [r for r in select(rows, since_time(start, now))
                if fam == 'all' or family(r.get('model') or '', prices) == fam]
        for kind, limit in lim.items():
            if kind == 'since':
                continue
            if kind == 'tokens':
                used = sum(int(r.get('prompt_tokens') or 0) + int(r.get('completion_tokens') or 0) for r in mine)
            else:
                used = round(sum(usd(r.get('model') or '', int(r.get('prompt_tokens') or 0),
                                     int(r.get('completion_tokens') or 0), prices) or 0 for r in mine), 4)
            out.append({'scope': scope, 'family': fam, 'kind': kind, 'used': used, 'limit': limit,
                        'ratio': (used / limit) if limit else (1.0 if used else 0.0), 'since': start})
    return out


def budget_status(env, team_dir=None, now=None):
    """回 (各條預算用了幾成, 超了的那幾條)。沒設 AOS_COST_HOME＝([], [])。預算檔壞了丟 CostError。"""
    base = home(env)
    if base is None:
        return [], []
    prices = load_prices(base)
    rows, _ = read_ledger(base)
    lines = usage_against(load_company_budget(base), rows, prices, 'company', now)
    if team_dir:
        team = os.path.realpath(team_dir)
        lines += usage_against(load_team_budget(team), [r for r in rows if r.get('team') == team], prices,
                               'team', now)
        acct = account_of(base, team)
        if acct:
            b = balances(base, prices, rows)[acct]
            for kind in ('usd', 'tokens'):
                if b['quota'][kind] is not None:
                    lines.append({'scope': 'account', 'family': acct, 'kind': kind, 'used': b['spent'][kind],
                                  'limit': b['quota'][kind], 'since': '開戶',
                                  'ratio': (b['spent'][kind] / b['quota'][kind]) if b['quota'][kind] else 1.0})
    return lines, [x for x in lines if x['used'] >= x['limit']]


def _fmt_amount(kind, v):
    return ('$%.4f' % v) if kind == 'usd' else ('%s token' % format(int(v), ','))


SCOPE_NAMES = {'company': '全公司', 'team': '本團隊', 'account': '帳戶'}


def over_text(over):
    return '、'.join('%s %s %s 用了 %s／上限 %s（%s 起）' % (
        SCOPE_NAMES[o['scope']], o['family'], '金額' if o['kind'] == 'usd' else 'token',
        _fmt_amount(o['kind'], o['used']), _fmt_amount(o['kind'], o['limit']), o['since']) for o in over)


def ls_line(env, team_dir):
    """aos-team ls 的第一行；沒設 AOS_COST_HOME＝None（不印）。"""
    if home(env) is None:
        return None
    try:
        _, over = budget_status(env, team_dir)
    except CostError as e:
        return '財務：預算檔壞了（%s）——郵差照常派工，修好再看' % e.msg
    if over:
        return '財務：超預算，郵差不派新單：%s' % over_text(over)
    return '財務：ok（預算內；aos-team cost budget 看幾成）'


def hold_reason(env, team_dir):
    """郵差派工前問：要不要擋。回 None（不擋）或 (白話原因, 簽名)。預算檔壞了不擋（只在 ls 報）。"""
    try:
        _, over = budget_status(env, team_dir)
    except CostError:
        return None
    if not over:
        return None
    sig = ';'.join(sorted('%s/%s/%s' % (o['scope'], o['family'], o['kind']) for o in over))
    return over_text(over), sig


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


# ------------------------------------------------------------------ 回填 ----

def import_usage(base, dirs, prices, dry_run=False):
    """把 dirs 底下所有 members/<名>/log/usage*.jsonl 撈進帳本。回 (新記幾筆, 略過幾筆, 找到的檔)。

    每筆帶 import_key（檔的真實路徑＋那一行的 sha1），帳上已有同 key 的不再記；
    帳上已有同 (team, member, batch, prompt, completion) 的即時紀錄也不記（避免同一次呼叫記兩次）。"""
    rows, _ = read_ledger(base)
    keys = {r.get('import_key') for r in rows if r.get('import_key')}
    live = {(r.get('team'), r.get('member'), r.get('batch'), r.get('prompt_tokens'), r.get('completion_tokens'))
            for r in rows if not r.get('import_key')}
    files = []
    for d in dirs:
        d = os.path.realpath(os.path.expanduser(d))
        files += glob.glob(os.path.join(d, '**', 'members', '*', 'log', 'usage*.jsonl'), recursive=True)
    new, skipped = [], 0
    for path in sorted(set(files)):
        member_dir = os.path.dirname(os.path.dirname(path))
        member = os.path.basename(member_dir)
        team = os.path.dirname(os.path.dirname(member_dir))
        with open(path, encoding='utf-8', errors='replace') as f:
            for line in f:
                key = hashlib.sha1((path + '\n' + line.strip()).encode()).hexdigest()[:20]
                try:
                    u = json.loads(line)
                except ValueError:
                    skipped += 1
                    continue
                if not isinstance(u, dict) or key in keys:
                    skipped += 1
                    continue
                row = make_row(model=u.get('model') or '?', alias=u.get('alias'), usage=u.get('usage'), ms=u.get('ms'),
                               source='import', team=team, member=member, batch=u.get('batch'),
                               at=u.get('at') if isinstance(u.get('at'), str) else None, prices=prices,
                               extra={'import_key': key, 'import_from': path})
                if (team, member, row['batch'], row['prompt_tokens'], row['completion_tokens']) in live:
                    skipped += 1
                    continue
                keys.add(key)
                new.append(row)
    if new and not dry_run:
        append(base, new)
    return new, skipped, sorted(set(files))


# ------------------------------------------------------------------ kernel 的 cpu 數 ----

def cpu_limits(env):
    """cpu 行印的上限：預設新創規模 20／5；budget.json 的 "cpus" 可改（例：擴張 {"max": 200, "llm_max": 20}）。"""
    out = dict(CPU_LIMITS)
    base = home(env)
    try:
        b = load_company_budget(base) if base else None
    except CostError:
        b = None
    out.update((b or {}).get('cpus') or {})
    return out


def cpu_line(env):
    """現在開著幾個 cpu／幾個 llm cpu（上限由 HR 管，這裡只印、超了標出來）。拿不到回白話原因。"""
    lim = cpu_limits(env)
    cap = '上限 %d／llm %d，由 HR 管' % (lim['max'], lim['llm_max'])
    k = env.get('AOS_KERNEL_HOME')
    if not k or not os.path.isabs(k):
        return 'cpu：沒設 AOS_KERNEL_HOME，看不到（%s）' % cap
    exe = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cli', 'aos-kernel')
    try:
        p = subprocess.run([exe, 'ls', '--json', '--target', k], capture_output=True, text=True, timeout=15)
        data = json.loads(p.stdout)
        total = data['counts']['pools']['want']
        llm = (data.get('pools') or {}).get('llm', {}).get('want', 0)
        busy = data['counts']['pools'].get('busy')
    except Exception as e:                       # noqa: BLE001 — 只少一行，不擋查帳
        return 'cpu：aos-kernel ls 讀不到（%s）' % (' '.join(str(e).split())[:120])
    over = '  ← 超過上限' if (total or 0) > lim['max'] or (llm or 0) > lim['llm_max'] else ''
    return 'cpu：開著 %s 個（忙 %s）、其中 llm cpu %s 個（%s）%s' % (total, busy, llm, cap, over)


# ------------------------------------------------------------------ 命令列 ----

def _table(groups, by):
    head = {'family': '家族', 'model': '模型', 'team': '團隊', 'member': '成員', 'task': '單號', 'source': '來源'}[by]
    lines = ['%-34s %6s %13s %11s %10s' % (head, '次', 'prompt', 'completion', '估美元')]
    for g in groups:
        key = str(g['key'])
        if by == 'team' and key.startswith('/'):
            key = os.path.join(*key.rstrip('/').split('/')[-2:])     # 末兩段（團隊資料夾常叫 team）
        money = ('$%.4f' % g['usd']) + ('＋?' if g['unpriced_tokens'] else '')
        lines.append('%-34s %6d %13s %11s %10s' % (key[:34], g['calls'], format(g['prompt_tokens'], ','),
                                                    format(g['completion_tokens'], ','), money))
    return lines


def _cmd_account(base, prices, args):
    from aos_team_format import TeamError
    act = args.dirs[0] if args.dirs else 'ls'
    if act == 'open' and len(args.dirs) == 3:
        a = account_open(base, args.dirs[1], args.dirs[2])
        print('帳戶 %s 綁 %s' % (args.dirs[1], a['root']))
        return 0
    if act == 'grant' and len(args.dirs) == 2:
        g = account_grant(base, args.dirs[1], usd=args.usd, tokens=args.tokens, note=args.note)
        print('撥給 %s：%s' % (args.dirs[1], json.dumps(g, ensure_ascii=False)))
        return 0
    if act != 'ls' or len(args.dirs) > 1:
        raise TeamError('Usage', 'aos-team cost account ls｜open 名 公司資料夾｜grant 名 [--usd X] [--tokens N] [--note …]')
    b = balances(base, prices)
    broke = 1 if any(x['broke'] for x in b.values()) else 0
    if args.json:
        print(json.dumps(b, ensure_ascii=False, indent=1))
        return broke
    if not b:
        print('還沒有帳戶（aos-team cost account open 名 公司資料夾）')
    for name, x in sorted(b.items()):
        def one(k):
            if x['quota'][k] is None:
                return '%s 已花 %s（沒配額）' % (k, _fmt_amount(k, x['spent'][k]))
            return '%s 餘 %s／配 %s' % (k, _fmt_amount(k, x['balance'][k]), _fmt_amount(k, x['quota'][k]))
        print('%-12s %s  %s；%s  %d 次%s' % (name, '倒閉' if x['broke'] else '營業', one('usd'), one('tokens'),
                                          x['calls'], '' if not x['broke'] else '  ← 餘額歸零，郵差不派新單'))
    return broke


def cmd_cost(team_dir, argv):
    from aos_team_format import TeamError
    ap = argparse.ArgumentParser(prog='aos-team cost', description='財務：模型用量與估算花費（帳本 $AOS_COST_HOME）')
    ap.add_argument('what', nargs='?', default='report', choices=('report', 'budget', 'import', 'account'),
                    help='report（預設）＝一張表；budget＝預算用了幾成；import 資料夾…＝回填舊的 usage.jsonl；'
                         'account ls／open 名 公司資料夾／grant 名 --usd X --tokens N＝一家公司一個帳戶')
    ap.add_argument('dirs', nargs='*', help='import 要掃的資料夾；account 的動作與參數')
    ap.add_argument('--usd', type=float)
    ap.add_argument('--tokens', type=int)
    ap.add_argument('--note', default='')
    ap.add_argument('--by', choices=BY, default='family')
    ap.add_argument('--since', default='今天', help='今天（預設）、本週、全部、YYYY-MM-DD')
    ap.add_argument('--team', action='store_true', help='只看這個團隊（--target 那個）的帳')
    ap.add_argument('--dry-run', action='store_true', help='import 只算不寫')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    env = os.environ
    base = home(env)
    if base is None:
        raise TeamError('NotConfigured', '沒設 %s（帳本資料夾的絕對路徑，例：export %s=~/.aos/cost 展開後的絕對路徑）'
                        % (ENV, ENV))
    try:
        prices = load_prices(base)
        if args.what == 'import':
            if not args.dirs:
                raise TeamError('Usage', 'aos-team cost import 資料夾…')
            new, skipped, files = import_usage(base, args.dirs, prices, dry_run=args.dry_run)
            out = {'files': files, 'imported': len(new), 'skipped': skipped, 'dry_run': args.dry_run}
            if args.json:
                print(json.dumps(out, ensure_ascii=False, indent=1))
            else:
                print('%s %d 筆、略過 %d 筆（已記過／壞行），來自 %d 個 usage 檔' % (
                    '會記' if args.dry_run else '記了', len(new), skipped, len(files)))
            return 0
        if args.what == 'account':
            return _cmd_account(base, prices, args)
        team = os.path.realpath(team_dir) if args.team else None
        if args.what == 'budget':
            lines, over = budget_status(env, team_dir)
            if args.json:
                print(json.dumps({'lines': lines, 'over': over}, ensure_ascii=False, indent=1))
                return 0
            if not lines:
                print('沒設預算（%s/%s，或 team.json 的 budget）' % (base, BUDGET))
            for x in lines:
                print('%-4s %-9s %-6s %5.0f%%  %s／%s（%s 起）%s' % (
                    SCOPE_NAMES[x['scope']], x['family'], x['kind'], x['ratio'] * 100,
                    _fmt_amount(x['kind'], x['used']), _fmt_amount(x['kind'], x['limit']), x['since'],
                    '  ← 超了' if x['used'] >= x['limit'] else ''))
            return 1 if over else 0
        since = since_time(args.since)
        rows, bad = read_ledger(base)
        rows = select(rows, since, team)
        groups, unpriced = summarize(rows, args.by, prices)
        if args.json:
            print(json.dumps({'since': since.isoformat() if since else None, 'by': args.by, 'groups': groups,
                              'unpriced': unpriced, 'bad_lines': bad}, ensure_ascii=False, indent=1))
            return 0
        tot_t = sum(g['tokens'] for g in groups)
        tot_u = sum(g['usd'] for g in groups)
        print('帳本 %s：%s %d 次呼叫、%s token、估 $%.4f%s' % (
            os.path.join(base, LEDGER), ('%s 起' % since.strftime('%Y-%m-%d %H:%M')) if since else '有帳以來',
            sum(g['calls'] for g in groups), format(tot_t, ','), tot_u, '（只看本團隊）' if team else ''))
        for line in _table(groups, args.by):
            print(line)
        if unpriced:
            print('警告：價格表 %s 沒有這些模型，只記 token、不算錢：%s' % (
                os.path.join(base, PRICES), '、'.join('%s（%s token）' % (m, format(n, ',')) for m, n in unpriced.items())))
        if bad:
            print('警告：帳本有 %d 行讀不了，略過' % bad)
        print(cpu_line(env))
        return 0
    except CostError as e:
        raise TeamError(e.code, e.msg)


if __name__ == '__main__':
    import aos_team_cli
    sys.exit(aos_team_cli.main(['cost'] + sys.argv[1:]))
