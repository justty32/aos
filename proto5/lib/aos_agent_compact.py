"""機械壓縮記憶（spec/agent/compact.md）：aos-agent compact、tick idle 的自動壓縮、compact 申請、history --archive。

機械版不叫模型。三個入口共用 apply()，**呼叫的人要已經持 .tick.lock**（人用的 compact 自己拿；tick 本來就持著，不再拿第二次）。
每步可重跑：先寫 archive/<舊 sha>.json（已在就略過）→ 記事件 → 用暫存檔＋rename 換掉記憶檔。
永遠不是「先搬走舊的」，所以崩在哪一步，記憶檔都是完整的舊版或新版；舊版重跑算出來的新版一樣。
只有人跑的 `compact --summarize`（第三波 W3-2，spec/agent/compact-summarize.md）會叫模型，而且只換封存摘要的中間那段。
這個檔留 apply 與三個入口（人用的 compact、tick idle 的 auto、申請 on_request），以及測試掛鉤 _hook
（測試換掉這裡的 _hook、plan）；實作分在 aos_agent_compact_plan／archive／summarize，這裡匯出外部用到的名字。
"""
import collections
import json
import os
from pathlib import Path
import time

import aos_agent_events as events
import aos_agent_info
import aos_home
from aos_agent_context import history_tokens
from aos_agent_home import AgentError
from aos_agent_runtime import LOCK, files, report, tick_lock

from aos_agent_compact_plan import (
    check_pairs, config, DEFAULT_KEEP, FORGET, FORGET_DIGEST, MAX_KEEP, MAX_TOKENS, MIN_TOKENS,
    plan, REQUESTS, SEALED, SKIP, TASK_RE, task_snapshot
)
from aos_agent_compact_archive import _write_bytes, archive_dir, archive_main, sha_of
from aos_agent_compact_summarize import (
    _clean, _event_summary, _has, _new_digests, check_model, check_summary, compose,
    CONDENSED_HEAD, KEPT_HEAD, keywords, make_summarizer, summary_lines
)


def _hook(step):
    """持久化邊界的測試掛鉤（compact.archive、compact.history、compact.request）；正式執行什麼都不做。"""


def apply(info, *, keep_rounds, max_tokens, auto=False, reason=None, dry_run=False, summarizer=None):
    """算好、（不是 dry_run 就）寫 archive、記事件、換記憶。**呼叫的人要持 tick 鎖、確定 idle 且沒 batch／intake。**

    summarizer（只有人跑的 compact --summarize 給）：fn(舊記憶, 機械版新記憶, sha) → (新記憶, 報告)，
    在寫任何檔之前叫；tick 自動壓縮與申請一律不給，所以不叫模型。dry_run 時不叫。
    """
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
    if summarizer is not None and not dry_run:
        # 第三波 W3-2：只換新記憶的內容；archive、事件、換檔的順序照舊，崩潰恢復規則不變
        result['history'], result['summarize'] = summarizer(history, result['history'], sha)
        result['after'] = {'count': len(result['history']), 'tokens': history_tokens(result['history'])}
        result['over'] = max_tokens is not None and result['after']['tokens'] > max_tokens
    check_pairs(result['history'])   # dry-run 也驗：預覽過了正式就不會在這裡失敗
    if dry_run:
        return result
    if not target.exists() or sha_of(target.read_bytes()) != sha:
        _write_bytes(target, raw)
    _hook('compact.archive')
    extra = {'summarize': _event_summary(result['summarize'])} if 'summarize' in result else {}
    events.emit(base, 'compact', sha, auto=auto, reason=reason, keep_rounds=keep_rounds, max_tokens=max_tokens,
                before=result['before'], after=result['after'], over=result['over'],
                archive=os.path.relpath(target, base), **extra)
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
    if result.get('summarize'):
        lines.extend(summary_lines(result['summarize']))
    if result['over']:
        lines.append('還超過 --max-tokens %d：剩下的是最近 %d 輪與沒做完的任務（約 %d token），不再縮；要更小就減 --keep-rounds'
                     % (result['max_tokens'], result['keep_rounds'], a['tokens']))
    return lines


def compact(agent_dir, *, keep_rounds=None, max_tokens=None, dry_run=False, as_json=False, env=None,
            summarize=False, model=None):
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
        summarizer = None
        if summarize:
            alias = check_model(env, model or info['model'])   # 設定錯＝先退、什麼都不動（dry-run 也查）
            if not dry_run:
                summarizer = make_summarizer(base, env, alias)
        result = apply(info, keep_rounds=keep, max_tokens=limit, reason='aos-agent compact', dry_run=dry_run,
                       summarizer=summarizer)
        if summarize and dry_run and result['changed']:
            result['summarize'] = {'dry_run': True, 'planned': len(_new_digests(info['history'], result['history']))}
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
