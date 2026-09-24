"""機械壓縮記憶（spec/agent/compact.md）：aos-agent compact、tick idle 的自動壓縮、compact 申請、history --archive。

不叫模型。三個入口共用 apply()，**呼叫的人要已經持 .tick.lock**（人用的 compact 自己拿；tick 本來就持著，不再拿第二次）。
每步可重跑：先寫 archive/<舊 sha>.json（已在就略過）→ 記事件 → 用暫存檔＋rename 換掉記憶檔。
永遠不是「先搬走舊的」，所以崩在哪一步，記憶檔都是完整的舊版或新版；舊版重跑算出來的新版一樣。
"""
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time

import aos_agent_events as events
import aos_agent_info
import aos_home
from aos_agent_context import brief, history_tokens, message_size, rounds
from aos_agent_home import AgentError, check_message
from aos_agent_listen_render import call_names
from aos_agent_runtime import LOCK, files, report, tick_lock

DEFAULT_KEEP = 3
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


def _hook(step):
    """持久化邊界的測試掛鉤（compact.archive、compact.history、compact.request）；正式執行什麼都不做。"""


# ---- 設定 ------------------------------------------------------------------

def _int(value, where, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise AgentError('FieldTypeMismatch', '%s 要是 %d～%d 的整數' % (where, lo, hi))
    return value


def config(base):
    """info.json 的 compact（字面物件，不解指示詞）：{"max_tokens", "keep_rounds", "auto"}；沒寫＝都預設。"""
    raw = aos_home.read_json(Path(base) / 'info.json')
    value = raw.get('compact') if isinstance(raw, dict) else None
    out = {'max_tokens': None, 'keep_rounds': DEFAULT_KEEP, 'auto': False}
    if value is None:
        return out
    if not isinstance(value, dict) or any(k.startswith('$') for k in value):
        raise AgentError('FieldTypeMismatch', 'info.json 的 compact 要是字面物件')
    if value.get('max_tokens') is not None:
        out['max_tokens'] = _int(value['max_tokens'], 'compact.max_tokens', MIN_TOKENS, MAX_TOKENS)
    if 'keep_rounds' in value:
        out['keep_rounds'] = _int(value['keep_rounds'], 'compact.keep_rounds', 0, MAX_KEEP)
    auto = value.get('auto', out['max_tokens'] is not None)
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


def _assemble(parts, archive):
    """照每輪的 action 組出新記憶；相連要封存的幾輪併成一行。"""
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
        out.append(_marker(j - k + 1, parts[j]['to'] - p['from'] + 1, archive, p['from'], parts[j]['to']))
        k = j + 1
    return out


def _marker(n_rounds, count, archive, lo, hi):
    return {'role': 'user', 'content': '%s較早的 %d 輪（%d 則）；原文 %s 第 %d～%d 則]' % (
        SEALED, n_rounds, count, archive, lo, hi)}


def plan(history, *, keep_rounds, max_tokens, archive, status=None):
    """回 {"history": 新記憶, "changed", "rounds": [每輪怎麼處理], "before"/"after": {count, tokens}, "over"}。

    archive＝寫進說明行的原文位置（相對 agent 家）。同樣的輸入一定算出同樣的結果（重跑靠這條）。
    """
    spans = rounds(history) if history else []
    last = len(spans) - keep_rounds
    parts = []
    for n, (s, e) in enumerate(spans):
        part = history[s:e]
        entry = {'round': n + 1, 'from': s + 1, 'to': e, 'action': 'keep', 'messages': part}
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
        # 從最舊的一輪起逐輪封存，直到不超過。每封一輪先估值不值得：接在前一段封存後面＝併進同一行（多付 0），
        # 否則要多一行封存行（照最長位數估）；那輪本身比這個還小就不封（封存不能讓記憶變長，astra M3）
        marker = history_tokens([_marker(1, 1, archive, WIDE, WIDE)])
        prev_sealed = False
        for p in parts:
            if history_tokens(out) <= max_tokens:
                break
            cost = 0 if prev_sealed else marker
            if p.get('sealable') and history_tokens(p['messages']) > cost:
                p['action'] = 'seal'
                out = _assemble(parts, archive)
            prev_sealed = p['action'] == 'seal'
    after = history_tokens(out)
    return {'history': out, 'changed': out != history,
            'rounds': [{x: p[x] for x in ('round', 'from', 'to', 'action', 'why', 'tasks', 'dropped') if x in p}
                       for p in parts],
            'before': {'count': len(history), 'tokens': history_tokens(history)},
            'after': {'count': len(out), 'tokens': after},
            'over': max_tokens is not None and after > max_tokens}


# ---- 寫 --------------------------------------------------------------------

def sha_of(raw):
    return hashlib.sha256(raw).hexdigest()[:16]


def _write_bytes(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def archive_dir(info):
    return Path(info['history_path']).parent / ARCHIVE


def apply(info, *, keep_rounds, max_tokens, auto=False, reason=None, dry_run=False):
    """算好、（不是 dry_run 就）寫 archive、記事件、換記憶。**呼叫的人要持 tick 鎖、確定 idle 且沒 batch／intake。**"""
    base = Path(info['dir'])
    path = Path(info['history_path'])
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raw = None
    history = json.loads(raw) if raw else []
    if raw is not None and history != info['history']:
        raise AgentError('HistoryChanged', '讀記憶的中途檔被換了，下一次再縮')
    sha = sha_of(raw) if raw is not None else None
    target = archive_dir(info) / ('%s.json' % sha)
    result = plan(history, keep_rounds=keep_rounds, max_tokens=max_tokens,
                  archive=os.path.relpath(target, base), status=task_snapshot(base, history))
    result.update(sha=sha, archive=str(target), keep_rounds=keep_rounds, max_tokens=max_tokens)
    if not result['changed']:
        return result
    check_pairs(result['history'])   # dry-run 也驗：預覽過了正式就不會在這裡失敗
    if dry_run:
        return result
    if not target.exists() or sha_of(target.read_bytes()) != sha:
        _write_bytes(target, raw)
    _hook('compact.archive')
    events.emit(base, 'compact', sha, auto=auto, reason=reason, keep_rounds=keep_rounds, max_tokens=max_tokens,
                before=result['before'], after=result['after'], over=result['over'],
                archive=os.path.relpath(target, base))
    aos_home.write_json(path, result['history'])
    _hook('compact.history')
    return result


# ---- 人：aos-agent compact ---------------------------------------------------

def _peek_lock(base):
    """dry-run 不建檔：鎖檔在才試，被佔回持有者（字串），沒被佔回 None。"""
    import fcntl
    try:
        fd = os.open(Path(base) / LOCK, os.O_RDONLY | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return os.read(fd, 64).decode('ascii', 'replace').strip() or '不明'
        return None
    finally:
        os.close(fd)


def summary(result, dry_run):
    b, a = result['before'], result['after']
    if not result['changed']:
        lines = ['nothing to compact：記憶 %d 則、約 %d token，沒有可以縮的（最後 %d 輪原樣留、沒做完的任務不縮）'
                 % (b['count'], b['tokens'], result['keep_rounds'])]
    else:
        lines = ['%s記憶 %d 則、約 %d token → %d 則、約 %d token；原文 %s' % (
            '（dry-run，沒寫）' if dry_run else 'compacted：', b['count'], b['tokens'], a['count'], a['tokens'],
            result['archive'])]
        acts = collections.Counter(r['action'] for r in result['rounds'])
        lines.append('輪：壓縮 %d、封存 %d、原樣 %d（最近 %d、沒做完的任務 %d）' % (
            acts['compress'], acts['seal'], acts['keep'],
            sum(1 for r in result['rounds'] if r.get('why') == 'recent'),
            sum(1 for r in result['rounds'] if r.get('why') == 'task' and r['action'] == 'keep')))
    if result['over']:
        lines.append('還超過 --max-tokens %d：剩下的是最近 %d 輪與沒做完的任務（約 %d token），不再縮；要更小就減 --keep-rounds'
                     % (result['max_tokens'], result['keep_rounds'], a['tokens']))
    return lines


def compact(agent_dir, *, keep_rounds=None, max_tokens=None, dry_run=False, as_json=False, env=None):
    env = os.environ if env is None else env
    base = Path(os.path.abspath(agent_dir))
    lock = None
    try:
        if dry_run:
            holder = _peek_lock(base)
            if holder is not None:
                report('busy', '另一個 tick 正在跑（pid %s），這次不縮' % holder)
                return 101
        else:
            got, lock = tick_lock(base)
            if not got:
                report('busy', '另一個 tick 正在跑（pid %s），這次不縮、沒動檔' % (lock or '不明'))
                lock = None
                return 101
        info = aos_agent_info.load(base, env=env)
        st = aos_agent_info.load_state(base, env=env)
        if st['batch'] is not None or st['state'] != 'idle' or st['intake'] is not None:
            what = ('batch 還在（%s）' % st['batch']['kind'] if st['batch'] is not None
                    else 'intake 做到一半' if st['intake'] is not None else 'state 是 %s' % st['state'])
            raise AgentError('NotIdle', '%s；等這一輪做完回到 idle 再縮（aos-agent status 看）' % what)
        cfg = config(base)
        keep = cfg['keep_rounds'] if keep_rounds is None else keep_rounds
        limit = cfg['max_tokens'] if max_tokens is None else max_tokens
        result = apply(info, keep_rounds=keep, max_tokens=limit, reason='aos-agent compact', dry_run=dry_run)
        if as_json:
            print(json.dumps({k: v for k, v in result.items() if k != 'history'}, ensure_ascii=False))
        else:
            for line in summary(result, dry_run):
                print(line)
        return 0
    except (AgentError, aos_home.HomeError, OSError) as exc:
        from aos_agent import _error
        return _error(exc)
    finally:
        if lock is not None:
            os.close(lock)


def prune(agent_dir, days, env=None):
    """刪超過 days 天、而且現在的記憶沒有提到的 archive（記憶裡的說明行還指著的一律留）。"""
    env = os.environ if env is None else env
    base = Path(os.path.abspath(agent_dir))
    lock = None
    try:
        # 跟 compact 互斥（astra M1）：不然可能刪掉「archive 寫了、記憶還沒換」那一份
        got, lock = tick_lock(base)
        if not got:
            report('busy', '另一個 tick 正在跑（pid %s），這次不清、沒動檔' % (lock or '不明'))
            lock = None
            return 101
        info = aos_agent_info.load(base, env=env)
        folder = archive_dir(info)
        text = json.dumps(info['history'], ensure_ascii=False)
        cutoff = time.time() - days * 86400
        removed = kept = 0
        for p in sorted(folder.glob('*.json')) if folder.is_dir() else []:
            if p.stat().st_mtime < cutoff and p.name not in text:
                p.unlink()
                removed += 1
            else:
                kept += 1
        print('pruned %d 份 archive，留 %d 份（%s）' % (removed, kept, folder))
        return 0
    except (AgentError, aos_home.HomeError, OSError) as exc:
        from aos_agent import _error
        return _error(exc)
    finally:
        if lock is not None:
            os.close(lock)


# ---- tick idle：自動壓縮與申請 -------------------------------------------------

def _requests(base):
    """還沒處理的申請：compact-req/*.json 裡，done/ 沒有同名收據的。原檔永遠不搬（郵差看它在不在去重，astra M4）。"""
    folder = Path(base) / REQUESTS
    try:
        return sorted(p for p in folder.iterdir() if p.is_file() and p.name.endswith('.json')
                      and not p.name.startswith('.') and not (folder / 'done' / p.name).exists())
    except FileNotFoundError:
        return []


def _request_opts(paths, cfg):
    keep, limit, reasons = cfg['keep_rounds'], cfg['max_tokens'], []
    for p in paths:
        try:
            req = json.loads(p.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(req, dict):
            continue
        if type(req.get('keep_rounds')) is int and 0 <= req['keep_rounds'] <= MAX_KEEP:
            keep = req['keep_rounds']
        if type(req.get('max_tokens')) is int and MIN_TOKENS <= req['max_tokens'] <= MAX_TOKENS:
            limit = req['max_tokens']
        why = req.get('reason') if isinstance(req.get('reason'), str) else ''
        reasons.append('申請 %s（%s）%s' % (req.get('id', p.stem), req.get('from', '?'), '：' + why if why else ''))
    return keep, limit, reasons


def _skip_key(info, keep, limit):
    """記憶 sha＋選項＋提到的單號的狀態（任務做完了就該重新看，astra M5）。"""
    try:
        raw = Path(info['history_path']).read_bytes()
    except FileNotFoundError:
        raw = b''
    history = json.loads(raw) if raw else []
    tasks = task_snapshot(info['dir'], history) if isinstance(history, list) else None
    return '%s %s %s %s' % (sha_of(raw), keep, limit, sha_of(json.dumps(tasks, sort_keys=True).encode()))


def auto(run):
    """tick 在 idle、沒 batch／intake、持著鎖時叫（aos_agent.tick）。做了事（縮了或收了申請）回 True。

    - 有輸入等著收就先不縮（讓那句先進記憶；縮會讓 say --wait／talk 追的記憶長度變短）。
    - 觸發：compact-req/ 裡有申請，或 info.compact.auto 開著且記憶超過 max_tokens。
    - 縮不動（還是超過、或驗不過）就記在 log/compact-skip，同一份記憶不再每格重算。
    - 申請處理完搬進 compact-req/done/（縮失敗也搬，錯誤進事件與 agent.err）；先縮再搬，崩了重跑再縮一次是空轉。
    """
    base, info, st = run.base, run.info, run.st
    if any(files(base, value) for value in st['input']):
        return False
    requests = _requests(base)
    try:
        cfg = config(base)
    except (AgentError, aos_home.HomeError) as exc:
        if not requests:
            return False  # 設定壞了不自動縮；check 會看到（不在每格噴錯）
        cfg = {'max_tokens': None, 'keep_rounds': DEFAULT_KEEP, 'auto': False}
        report('compact', 'info.json 的 compact 讀不懂，照預設縮：%s' % getattr(exc, 'msg', exc))
    if not requests:
        if not cfg['auto'] or history_tokens(info['history']) <= cfg['max_tokens']:
            return False
        keep, limit, reason = cfg['keep_rounds'], cfg['max_tokens'], 'auto'
        key = _skip_key(info, keep, limit)
        try:
            if (base / SKIP).read_text(encoding='utf-8').strip() == key:
                return False
        except OSError:
            pass
    else:
        keep, limit, reasons = _request_opts(requests, cfg)
        reason = '；'.join(reasons) or 'request'
    changed = False
    try:
        result = apply(info, keep_rounds=keep, max_tokens=limit, auto=True, reason=reason)
        changed = result['changed']
        if not requests and (not changed or result['over']):
            _write_skip(base, _skip_key(info, keep, limit))  # 讀的是現在（縮過）的檔
    except (AgentError, aos_home.HomeError, OSError, ValueError) as exc:
        msg = getattr(exc, 'msg', str(exc))
        report('compact', '自動壓縮沒做：%s' % msg)
        events.emit(base, 'compact_fail', None, auto=True, reason=reason, error=msg)
        if not requests:
            _write_skip(base, _skip_key(info, keep, limit))
    for p in requests:
        (p.parent / 'done').mkdir(exist_ok=True)
        _write_bytes(p.parent / 'done' / p.name, p.read_bytes())   # 收據＝原申請的副本
        _hook('compact.request')
    return changed or bool(requests)


def _write_skip(base, key):
    try:
        path = Path(base) / SKIP
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_bytes(path, (key + '\n').encode('utf-8'))
    except OSError:
        pass


# ---- 申請（spec/team/mail.md〈申請〉，郵差叫） -----------------------------------

REQUEST_KEYS = ('id', 'from', 'kind', 'at', 'member', 'keep_rounds', 'max_tokens', 'reason')


def on_request(lay, roster, req):
    """compact 申請 → 投進那個成員家的 compact-req/<id>.json（不覆蓋；已投過、已處理過都不再投），回 []。

    欄位：member?（沒寫＝寄件人自己；只有 human 能替別人申請）、keep_rounds?（0～1000）、max_tokens?（100 以上）、reason?。
    郵差不持成員的 tick 鎖，所以這裡不縮；成員下一次閒著時 tick 在自己的鎖裡縮。
    """
    from aos_team_format import TeamError, bad, check_name
    from aos_agent_say import drop_new
    extra = [k for k in req if k not in REQUEST_KEYS]
    if extra:
        bad('request', '不認得的欄位 %s' % '、'.join(sorted(extra)))
    member = req.get('member', req['from'])
    check_name(member, 'request.member')
    if member != req['from'] and req['from'] != 'human':
        raise TeamError('NotAllowed', '%s 只能申請壓縮自己的記憶，不能替 %s 申請' % (req['from'], member))
    if member not in roster['members']:
        raise TeamError('BadRecipient', '名冊裡沒有 %s' % member)
    body = {'id': req['id'], 'from': req['from'], 'at': req['at']}
    for key, lo, hi in (('keep_rounds', 0, MAX_KEEP), ('max_tokens', MIN_TOKENS, MAX_TOKENS)):
        if key in req:
            if type(req[key]) is not int or not lo <= req[key] <= hi:
                bad('request.' + key, '要是 %d～%d 的整數' % (lo, hi))
            body[key] = req[key]
    if 'reason' in req:
        if not isinstance(req['reason'], str) or len(req['reason']) > 500:
            bad('request.reason', '要是 500 字以內的字串')
        body['reason'] = req['reason']
    # 原檔 tick 不搬、只在 done/ 放收據，所以「同名已在」就是投過了（drop_new 不覆蓋）；沒有先查再投的窗口
    drop_new(lay.member(member) / REQUESTS, req['id'] + '.json', body)
    return []


# ---- 人：aos-agent history --archive -------------------------------------------

def _load_archive(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, list):
        raise AgentError('NotAnArray', '%s 不是記憶陣列' % path)
    return value


def archive_main(agent_dir, *, sha=None, grep=None, as_json=False, env=None):
    """列 archive、印一份、或在 archive 裡找字。唯讀、不拿鎖。"""
    env = os.environ if env is None else env
    try:
        info = aos_agent_info.load(agent_dir, env=env)
        folder = archive_dir(info)
        paths = sorted(folder.glob('*.json'), key=lambda p: (p.stat().st_mtime, p.name)) if folder.is_dir() else []
        if sha is not None:
            paths = [p for p in paths if p.stem.startswith(sha)]
            if not paths:
                raise AgentError('NotFound', '%s 裡沒有 %s 開頭的 archive' % (folder, sha))
            if len(paths) > 1 and grep is None:
                raise AgentError('NotUnique', '%s 開頭的有 %d 份：%s' % (sha, len(paths), '、'.join(p.stem for p in paths)))
        if grep is not None:
            needle = grep.lower()
            hits = []
            for p in paths:
                history = _load_archive(p)
                names = call_names(history, len(history))
                for i, m in enumerate(history, 1):
                    text = (m.get('content') or '') + ''.join(c['function']['arguments'] for c in m.get('tool_calls') or [])
                    if needle in text.lower() or any(needle in c['function']['name'].lower()
                                                      for c in m.get('tool_calls') or []):
                        hits.append({'archive': p.stem, 'index': i, 'role': m.get('role'),
                                     'line': brief(m, names)})
            if as_json:
                print(json.dumps(hits, ensure_ascii=False))
            elif not hits:
                print('（archive 裡沒有「%s」）' % grep)
            for h in hits if not as_json else []:
                print('%s 第 %d 則  %s' % (h['archive'], h['index'], h['line'][:200]))
            return 0
        if sha is not None:
            history = _load_archive(paths[0])
            if as_json:
                print(json.dumps(history, ensure_ascii=False))
                return 0
            names = call_names(history, len(history))
            for i, m in enumerate(history, 1):
                print('第 %d 則  %s' % (i, brief(m, names, full=True)))
            return 0
        rows = []
        for p in paths:
            try:
                count = len(_load_archive(p))
            except (OSError, ValueError, AgentError):
                count = None
            rows.append({'archive': p.stem, 'path': str(p), 'count': count, 'bytes': p.stat().st_size,
                         'at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(p.stat().st_mtime))})
        if as_json:
            print(json.dumps(rows, ensure_ascii=False))
        elif not rows:
            print('（沒有 archive：%s）' % folder)
        for r in rows if not as_json else []:
            print('%s  %s  %s 則  %d bytes' % (r['archive'], r['at'], '?' if r['count'] is None else r['count'],
                                            r['bytes']))
        return 0
    except (AgentError, aos_home.HomeError, OSError, ValueError) as exc:
        from aos_agent import _error
        if isinstance(exc, ValueError) and not isinstance(exc, AgentError):
            exc = AgentError('JsonSyntax', str(exc))
        return _error(exc)
