"""壓縮記憶的算法（純函式為主）：常數與設定、沒做完的任務、成對檢查、每一級每輪留多少、機械摘要、算出新記憶 plan。"""
import collections
import json
from pathlib import Path
import re

import aos_home
from aos_agent_context import history_tokens, rounds
from aos_agent_home import AgentError, check_message
from aos_agent_listen_render import call_names


DEFAULT_KEEP = 3
DEFAULT_MAX = 32000            # 自動壓縮預設上限（使用者 09-24 裁決；info.json 的 compact 可改）
MIN_TOKENS = 100
MAX_TOKENS = 10 ** 8
MAX_KEEP = 1000
ARCHIVE = 'archive'            # 相對記憶檔所在的資料夾
REQUESTS = 'compact-req'       # 郵差投進來的 compact 申請（agent 家裡）
SKIP = 'log/compact-skip'      # 自動壓縮「這份記憶縮不動」的記號，免得每格重算
FINISHED = ('done', 'cancelled')
TASK_RE = re.compile(r'(?<![A-Za-z0-9_-])t-\d{4,}(?:\.r\d+)?(?![A-Za-z0-9_])')
WIDE = 999999  # 算「值不值得換」時說明行裡的數字一律當 6 位（決定不能跟位置有關，astra M2）
COMPRESSED = '[aos 已壓縮'
SEALED = '[aos 已封存'


# ---- 設定 ------------------------------------------------------------------

def _int(value, where, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise AgentError('FieldTypeMismatch', '%s 要是 %d～%d 的整數' % (where, lo, hi))
    return value


def config(base):
    """info.json 的 compact（字面物件或 false，不解指示詞）：{"max_tokens", "keep_rounds", "auto"}。

    沒寫＝自動壓縮開、上限 32000 token（使用者 09-24 裁決）；false 或 max_tokens 0＝關（也沒上限）。
    """
    raw = aos_home.read_json(Path(base) / 'info.json')
    value = raw.get('compact') if isinstance(raw, dict) else None
    out = {'max_tokens': DEFAULT_MAX, 'keep_rounds': DEFAULT_KEEP, 'auto': True}
    if value is None:
        return out
    if value is False:
        return dict(out, max_tokens=None, auto=False)
    if not isinstance(value, dict) or any(k.startswith('$') for k in value):
        raise AgentError('FieldTypeMismatch', 'info.json 的 compact 要是字面物件或 false')
    if value.get('max_tokens') == 0 and type(value.get('max_tokens')) is int:
        out['max_tokens'] = None
    elif 'max_tokens' in value:
        out['max_tokens'] = _int(value['max_tokens'], 'compact.max_tokens（0＝關）', MIN_TOKENS, MAX_TOKENS)
    if 'keep_rounds' in value:
        out['keep_rounds'] = _int(value['keep_rounds'], 'compact.keep_rounds', 0, MAX_KEEP)
    auto = value.get('auto', True)
    if type(auto) is not bool:
        raise AgentError('FieldTypeMismatch', 'compact.auto 要是 true／false')
    out['auto'] = auto and out['max_tokens'] is not None
    return out


# ---- 沒做完的任務 -----------------------------------------------------------

def task_status(base):
    """成員的家在 <團隊>/members/<名>/ 時，回「單號 → 狀態（讀不到＝None）」；不在團隊裡回 None。"""
    base = Path(base)
    team = base.parent.parent
    if base.parent.name != 'members' or not (team / 'team.json').exists():
        return None
    tasks = team / 'team' / 'tasks'

    def status(tid):
        try:
            value = json.loads((tasks / (tid + '.json')).read_text(encoding='utf-8'))
            return value.get('status') if isinstance(value, dict) else None
        except (OSError, ValueError):
            return None
    return status


def mentioned_tasks(history):
    """記憶裡 user 訊息提到的單號（照出現順序、不重複）。"""
    found = []
    for m in history:
        if m['role'] == 'user':
            for tid in TASK_RE.findall(m.get('content') or ''):
                if tid not in found:
                    found.append(tid)
    return found


def task_snapshot(base, history):
    """這份記憶提到的單號 → 狀態，一次讀好（plan 只看這份快照；不在團隊裡＝None）。"""
    status = task_status(base)
    if status is None:
        return None
    return {tid: status(tid) for tid in mentioned_tasks(history)}


def open_tasks(history, span, status):
    """這一輪的 user 訊息提到、還沒結束的單號（讀不到的也算沒結束，寧可多留）。"""
    if status is None:
        return []
    s, e = span
    found = []
    for m in history[s:e]:
        if m['role'] == 'user':
            for tid in TASK_RE.findall(m.get('content') or ''):
                state = status.get(tid) if isinstance(status, dict) else status(tid)
                if tid not in found and state not in FINISHED:
                    found.append(tid)
    return found


# ---- 驗 --------------------------------------------------------------------

def check_pairs(history):
    """tool_calls 與 tool 結果成對：每則有 tool_calls 的 assistant 後面緊接著它每個 id 的結果，沒有落單的結果。"""
    waiting = set()
    for i, m in enumerate(history):
        check_message(m)
        if m['role'] == 'tool':
            if m['tool_call_id'] not in waiting:
                raise AgentError('HistoryInvalid', '第 %d 則是沒有對應呼叫的工具結果（tool_call_id %s）'
                                 % (i + 1, m['tool_call_id']))
            waiting.discard(m['tool_call_id'])
            continue
        if waiting:
            raise AgentError('HistoryInvalid', '第 %d 則之前，呼叫 %s 沒有結果' % (i + 1, '、'.join(sorted(waiting))))
        if m['role'] == 'assistant':
            waiting = {c['id'] for c in m.get('tool_calls') or []}
    if waiting:
        raise AgentError('HistoryInvalid', '最後一則的呼叫 %s 還沒有結果（這一輪還沒做完）' % '、'.join(sorted(waiting)))


# ---- 算新記憶（純函式） ------------------------------------------------------

def _counts(messages):
    names = collections.Counter(c['function']['name'] for m in messages if m['role'] == 'assistant'
                                for c in m.get('tool_calls') or [])
    return '、'.join('%s×%d' % (n, k) for n, k in sorted(names.items(), key=lambda x: (-x[1], x[0])))


def _sealed_marker(m):
    return m['role'] == 'user' and (m.get('content') or '').startswith(SEALED)


DIGEST_BYTES = 8192
BUDGETS = (DIGEST_BYTES, 4096, 2048, 1024, 512, 0)   # 摘要上限逐級降，挑放得下的最大一級（0＝只剩一行）
# 每一級每輪留多少：(使用者原話字數, 工具參數字數, 結果留幾行, 每行字數, 回話字數)；None＝工具只留「名字（幾行）」
LEVELS = ((300, 120, 3, 160, 400), (160, 60, 1, 100, 200), (80, None, 0, 0, 100), (40, None, 0, 0, 40),
          (30, None, 0, 0, 0))
FORGET = '這段細節你看不到了，問到就說不記得。'
FORGET_DIGEST = '摘要以外的細節你看不到了，問到就說不記得（摘要裡寫的可以照著回答）。'


def _cut(text, limit):
    text = ' '.join((text or '').split())
    return text if len(text) <= limit else text[:limit] + '…'


def _round_digest(n, messages, level):
    """一輪的機械摘要（幾行）：使用者原話、叫了什麼工具（參數摘要）、結果前幾行與行數、最後回話。"""
    user_n, arg_n, res_lines, res_n, reply_n = LEVELS[level]
    names = call_names(messages, len(messages))
    out = ['第 %d 輪' % n]
    said = [m.get('content') or '' for m in messages if m['role'] == 'user'
            and not (m.get('content') or '').startswith('[aos ')]
    if said:
        out.append('  使用者：' + _cut(' / '.join(said), user_n))
    if arg_n is None:
        # 短的幾級：每個結果只留「工具名（幾行）」——行數這種關鍵數字很便宜，最後才丟
        shown = ['%s（%d 行）' % (names.get(m.get('tool_call_id'), '?'),
                                  len([l for l in (m.get('content') or '').splitlines() if l.strip()]))
                 for m in messages if m['role'] == 'tool']
        if shown:
            out.append('  工具：' + '、'.join(shown))
    else:
        for m in messages:
            if m['role'] == 'assistant':
                for c in m.get('tool_calls') or []:
                    out.append('  呼叫 %s %s' % (c['function']['name'], _cut(c['function']['arguments'], arg_n)))
            elif m['role'] == 'tool':
                lines = [l for l in (m.get('content') or '').splitlines() if l.strip()]
                head = '  結果 %s（%d 行）' % (names.get(m.get('tool_call_id'), '?'), len(lines))
                out.append(head + ('：' if res_lines and lines else ''))
                out += ['    ' + _cut(l, res_n) for l in lines[:res_lines]]
    replies = [m.get('content') for m in messages if m['role'] == 'assistant' and m.get('content')]
    if replies and reply_n:
        out.append('  回話：' + _cut(replies[-1], reply_n))
    return out


def _digest(group, archive, budget, lo, hi):
    """相連封存的幾輪 → 一則 user。budget＝這段最多幾 bytes（UTF-8）；0＝只剩一行。"""
    count = hi - lo + 1
    head = '%s較早的 %d 輪（%d 則）' % (SEALED, len(group), count)
    tail = '%s原文 %s 第 %d～%d 則]' % (FORGET_DIGEST, archive, lo, hi)
    if budget:
        for level in range(len(LEVELS)):
            body = [line for p in group for line in _round_digest(p['round'], p['orig'], level)]
            text = '\n'.join([head + '，下面是機械摘要：'] + body + [tail])
            if len(text.encode('utf-8')) <= budget:
                return {'role': 'user', 'content': text}
        # 最短的一級還放不下：從最舊的輪丟，留得下幾輪算幾輪
        rows = [_round_digest(p['round'], p['orig'], len(LEVELS) - 1) for p in group]
        while rows:
            rows.pop(0)
            skipped = len(group) - len(rows)
            body = ['（更早的 %d 輪只剩原文位置）' % skipped] + [line for r in rows for line in r]
            text = '\n'.join([head + '，下面是機械摘要：'] + body + [tail])
            if len(text.encode('utf-8')) <= budget:
                return {'role': 'user', 'content': text}
    return {'role': 'user', 'content': '%s。%s原文 %s 第 %d～%d 則]' % (head, FORGET, archive, lo, hi)}


def _assemble(parts, archive, budget=0):
    """照每輪的 action 組出新記憶；相連要封存的幾輪併成一則摘要（每則最多 budget bytes）。"""
    out, k = [], 0
    while k < len(parts):
        p = parts[k]
        if p['action'] != 'seal':
            out.extend(p['messages'])
            k += 1
            continue
        j = k
        while j + 1 < len(parts) and parts[j + 1]['action'] == 'seal':
            j += 1
        out.append(_digest(parts[k:j + 1], archive, budget, p['from'], parts[j]['to']))
        k = j + 1
    return out


def plan(history, *, keep_rounds, max_tokens, archive, status=None):
    """回 {"history": 新記憶, "changed", "rounds": [每輪怎麼處理], "before"/"after": {count, tokens}, "over"}。

    archive＝寫進說明行的原文位置（相對 agent 家）。同樣的輸入一定算出同樣的結果（重跑靠這條）。
    """
    spans = rounds(history) if history else []
    last = len(spans) - keep_rounds
    parts = []
    for n, (s, e) in enumerate(spans):
        part = history[s:e]
        entry = {'round': n + 1, 'from': s + 1, 'to': e, 'action': 'keep', 'messages': part, 'orig': part}
        protect = open_tasks(history, (s, e), status)
        if n >= last:
            entry['why'] = 'recent'
        elif protect:
            entry.update(why='task', tasks=protect)
        else:
            k = s
            while k < e and history[k]['role'] == 'user':
                k += 1
            users, rest = history[s:k], history[k:e]
            final = rest[-1] if rest and rest[-1]['role'] == 'assistant' and not rest[-1].get('tool_calls') else None
            dropped = rest[:-1] if final is not None else rest
            if dropped:
                hi = e - 1 if final is not None else e
                called = _counts(dropped)
                text = '%s %d 則：%s；原文 %s 第 %d～%d 則]'
                note = {'role': 'user', 'content': text % (
                    COMPRESSED, len(dropped), called or '沒叫工具', archive, k + 1, hi)}
                worst = {'role': 'user', 'content': text % (
                    COMPRESSED, len(dropped), called or '沒叫工具', archive, WIDE, WIDE)}
                # 換掉的比說明行還短就不換（縮不能讓記憶變長）；說明行照最長的位數估，重跑判斷一樣
                if history_tokens([worst]) < history_tokens(dropped):
                    entry.update(action='compress', dropped=len(dropped),
                                 messages=users + [note] + ([final] if final is not None else []))
                else:
                    entry['why'] = 'small'
            entry['sealable'] = not (e - s == 1 and _sealed_marker(history[s]))
        parts.append(entry)
    out = _assemble(parts, archive)
    if max_tokens is not None:
        # 從最舊的一輪起封存到不超過。摘要上限從 8 KB 起逐級降：每一級找「最少要封幾輪」（二分），
        # 找得到就用這一級（所以放得下就留大摘要）；都不行就全封、只剩一行。封完反而比沒封大就全部不封
        # （封存不能讓記憶變長，astra M3）。
        plain = history_tokens(out)
        cands = [p for p in parts if p.get('sealable')]
        for p in cands:
            p['was'] = p['action']

        def trial(k, budget):
            for i, p in enumerate(cands):
                p['action'] = 'seal' if i < k else p['was']
            return _assemble(parts, archive, budget)

        if plain > max_tokens and cands:
            chosen = (len(cands), 0)
            for budget in BUDGETS:
                if history_tokens(trial(len(cands), budget)) > max_tokens:
                    continue
                lo, hi = 1, len(cands)
                while lo < hi:
                    mid = (lo + hi) // 2
                    if history_tokens(trial(mid, budget)) <= max_tokens:
                        hi = mid
                    else:
                        lo = mid + 1
                chosen = (lo, budget)
                break
            out = trial(*chosen)
            if history_tokens(out) >= plain:
                out = trial(0, 0)
    after = history_tokens(out)
    return {'history': out, 'changed': out != history,
            'rounds': [{x: p[x] for x in ('round', 'from', 'to', 'action', 'why', 'tasks', 'dropped') if x in p}
                       for p in parts],
            'before': {'count': len(history), 'tokens': history_tokens(history)},
            'after': {'count': len(out), 'tokens': after},
            'over': max_tokens is not None and after > max_tokens}
