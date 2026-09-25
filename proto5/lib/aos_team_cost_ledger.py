"""財務部的帳本：帳本家、價格表與模型家族、記一筆（record 掛在每次叫模型）、讀帳與篩選、分組加總、從 usage.jsonl 回填。"""
import datetime
import glob
import hashlib
import json
import os


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
