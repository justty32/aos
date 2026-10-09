"""唯讀證據量測；不依賴其他 aos 包。"""
import argparse, json, math, re, sys
import datetime as dt
from pathlib import Path
def obj(value):
    return value if isinstance(value, dict) else {}
def stamp(value):
    try:
        return dt.datetime.fromisoformat(value).astimezone(), value
    except (TypeError, ValueError, OverflowError):
        return None
def extreme(values, largest=False):
    values = [v for v in values if v is not None]
    return (max if largest else min)(values) if values else None
def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else 0
def parallel(windows):
    points = []
    for start, end in windows:
        if start and (end is None or end[0] > start[0]):
            points.append((start[0], 1))
            if end:
                points.append((end[0], -1))
    active = peak = 0
    for _, delta in sorted(points):
        active += delta
        peak = max(peak, active)
    return peak
def summary(flows, windows):
    seconds = [f['seconds'] for f in flows if f['seconds'] is not None]
    return dict(calls=sum(f['calls'] for f in flows),
                tokens={k: sum(f['tokens'][k] for f in flows) for k in flows[0]['tokens']} if flows else {},
                max_parallel=parallel(windows), window_unknown=sum(f['calls'] for f in flows)-len(windows),
                seconds=dict(mean=round(sum(seconds)/len(seconds), 3) if seconds else None,
                             max=max(seconds) if seconds else None, open=sum(f['open'] for f in flows)),
                retries={k: sum(f['retries'][k] for f in flows) for k in ('reask', 'resends', 'extra_tries', 'adopted', 'total')})
def letter_key(call_id, known=None):
    """依 aos7_up_brain.call_id/cid_of 還原信件鍵；前 47 字相同的信會合併（已知限制）。
    known＝看到的 brain call id：給了就只在去尾後那個第 1 回合 id 確實存在時才去 `-s數字`，信 id 本身以 -s數字 結尾也不拆件。"""
    truncated = re.fullmatch(r'(.{47})-[0-9a-f]{16}', call_id)
    if truncated:
        return truncated[1]
    step = re.fullmatch(r'(.+)-s\d+', call_id)
    return (step[1] if step and (known is None or step[1] in known) else call_id)[:47]
def _scan(path, overhead):
    root = Path(path).absolute()
    calls, authors, jobs, events, unreadable = {}, {}, {}, {}, []
    books, ingredients, gaps = {}, [], 0
    def call(key):
        return calls.setdefault(key, {})
    # 只讀契約內的路徑；JSONL 壞行跳過，仍保留其他行。
    patterns = [r'(.*)/llmcall/([^/]+)/([^/]+)/(request|raw|receipt)\.json',
                r'(.*)/budget/([^/]+)/ledger\.json', r'(.*)/budget/([^/]+)/gateway/[^/]+\.json',
                r'.*/author/req/([^/]+)/(request|receipt)\.json',
                r'.*/jobs/([^/]+)/frame\.json', r'.*/jobs/([^/]+)/results/[^/]+/[^/]+\.json',
                r'.*/events/must\.[^/]+\.jsonl']
    for p in sorted(root.rglob('*')):
        rel = p.relative_to(root).as_posix()
        matches = [re.fullmatch(pattern, p.as_posix()) for pattern in patterns]
        index = next((i for i, m in enumerate(matches) if m), None)
        if index is None:
            continue
        try:
            text = p.read_text(encoding='utf-8')
            data = [] if index == 6 else json.loads(text)
            if index == 6:
                for row in text.splitlines():
                    try:
                        event = json.loads(row)
                        if not isinstance(event, dict):
                            raise ValueError('非物件')
                        data.append(event)
                    except ValueError:
                        if rel not in unreadable:
                            unreadable.append(rel)
            elif not isinstance(data, dict):
                raise ValueError('非物件')
        except (OSError, ValueError, UnicodeError):
            unreadable.append(rel)
            if index == 1:
                books[matches[1].groups()] = None  # 帳檔在卻讀不了：帳差不明，不當成沒帳
            continue
        m = matches[index]
        if index == 0:
            base, budget, cid, kind = m.groups()
            call((base, budget, cid))[kind] = data
        elif index == 1:
            base, budget = m.groups()
            if 'used' in data:  # 沒 used 欄（如重建的 smoke 帳）當沒帳；有欄但不是整數算壞帳
                used = data['used']
                books[(base, budget)] = used if isinstance(used, int) and not isinstance(used, bool) else None
            for op in obj(data.get('ops')).values():
                if not isinstance(op, dict):
                    continue
                cid = obj(op.get('key')).get('request')
                if isinstance(cid, str):
                    call((base, budget, cid))['ledger'] = op
        elif index == 2:
            cid = data.get('call_id')
            if isinstance(cid, str):
                call((*m.groups(), cid))['gateway'] = data
        elif index == 3:
            rid, kind = m.groups()
            authors.setdefault('author/' + rid, {})[kind] = data
        elif index in (4, 5):
            job = jobs.setdefault(m[1], {'frame': {}, 'results': []})
            if index == 4:
                job['frame'] = data
            else:
                job['results'].append(data.get('at'))
        else:
            for event in data:
                rid = obj(event.get('payload')).get('rid')
                if event.get('kind') == 'author.request' and isinstance(rid, str):
                    key = 'author/' + rid
                    events[key] = extreme([events.get(key), stamp(event.get('at'))])
    grouped = {key: [] for key in authors}
    for key, c in calls.items():
        cid = obj(c.get('request')).get('call_id')
        c['id'] = cid if isinstance(cid, str) else key[2]
    brain_ids = {c['id'] for c in calls.values() if obj(c.get('request')).get('logical') == 'up/brain'}
    for key, c in sorted(calls.items()):
        logical = obj(c.get('request')).get('logical')
        flow = logical if isinstance(logical, str) else 'call:' + c['id']
        c['slot'] = c['id'] if logical == 'up/brain' else flow
        if logical == 'up/brain':
            flow = 'up/brain/' + letter_key(c['id'], brain_ids)
        elif flow.startswith(('author-review/', 'author-learn/')):
            flow = 'author/' + flow.split('/', 1)[1]
        grouped.setdefault(flow, []).append(c)
    flows, all_windows = [], []
    for logical, group in sorted(grouped.items()):
        token = dict.fromkeys(('used', 'reserve', 'pending', 'pending_reserve', 'prompt', 'completion', 'reasoning', 'cached'), 0)
        windows, starts, ends, usage_count = [], [events.get(logical)], [], 0
        for c in group:
            req, raw, rec, gate, op = (obj(c.get(k)) for k in ('request', 'raw', 'receipt', 'gateway', 'ledger'))
            reply = obj(raw.get('reply'))
            done = gate.get('stage') == 'done'
            final = rec if rec else gate if done else {}
            overrun = number(final.get('overrun', obj(op.get('settle')).get('overrun')))
            gaps += int('request' in c and 'receipt' not in c) + int(overrun > 0)
            if 'request' in c:
                nested = obj(req.get('request'))
                model = next((v for v in (obj(nested.get('litellm')).get('model'), nested.get('model'), req.get('endpoint')) if isinstance(v, str)), '?')
                holder = next((v for v in (req.get('holder'), obj(op.get('key')).get('holder')) if isinstance(v, str)), '?')
                moment = None
                for at in (raw.get('at'), gate.get('at') if done else None, obj(rec.get('settle')).get('at'),
                           obj(op.get('settle')).get('at'), obj(op.get('reserve')).get('at')):
                    try:
                        moment = dt.datetime.fromisoformat(at)
                        break
                    except (TypeError, ValueError, OverflowError):
                        pass
                ingredients.append((model, holder, moment.strftime('%Y-%m-%d') if moment else '-',
                                    moment.strftime('%Y-%m-%dT%H') if moment else '-', number(final.get('used')), overrun))
            c['used'] = number(rec.get('used'))  # 帳差只比真回條，gateway done 不算回條
            reserve = number(req.get('reserve'))
            pending = final.get('billing') == 'pending' or gate.get('stage') == 'intent' or bool(op and op.get('stage') != 'settled')
            token['used'] += number(final.get('used'))
            token['reserve'] += reserve
            token['pending'] += int(pending)
            token['pending_reserve'] += reserve if pending else 0
            usage = rec.get('usage') or (gate.get('usage') if done else None) or reply.get('usage')
            if isinstance(usage, dict):
                usage_count += 1
                for name, value in [('prompt', usage.get('prompt_tokens')), ('completion', usage.get('completion_tokens')),
                                    ('reasoning', obj(usage.get('completion_tokens_details')).get('reasoning_tokens')),
                                    ('cached', obj(usage.get('prompt_tokens_details')).get('cached_tokens'))]:
                    token[name] += number(value)
            raw_at = stamp(raw.get('at'))
            reserve_at = stamp(obj(op.get('reserve')).get('at'))
            start = stamp(gate.get('at')) if gate.get('stage') == 'intent' else None
            elapsed = reply.get('elapsed')
            if start is None and raw_at and isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool) and math.isfinite(elapsed):
                try:
                    moment = raw_at[0] - dt.timedelta(seconds=elapsed)
                    start = moment, moment.isoformat()
                except OverflowError:
                    pass
            start = start or reserve_at
            end = (stamp(gate.get('at')) if done else None) or raw_at
            if start:
                windows.append((start, end))
            starts.extend([start, reserve_at])
            ends.extend([stamp(gate.get('at')) if done else None, stamp(obj(rec.get('settle')).get('at'))])
        if overhead:
            token.update(overhead_total=overhead*usage_count, prompt_own=token['prompt']-overhead*usage_count)
        author = obj(obj(authors.get(logical)).get('receipt'))
        owned = {v['job'] for v in obj(author.get('versions')).values() if isinstance(obj(v).get('job'), str)}
        if logical.startswith('author/'):
            rid = logical[7:]
            owned.update(j for j in jobs if re.fullmatch(re.escape(rid) + r'_[0-9a-fA-F]{8}', j))
        frames = [jobs[j]['frame'] for j in sorted(owned) if j in jobs]
        for j in sorted(owned):
            if j in jobs:
                ends.extend(stamp(v) for v in jobs[j]['results'])
                if jobs[j]['frame'].get('closed') is True:
                    ends.append(stamp(jobs[j]['frame'].get('at')))
        start = extreme(starts)
        end = extreme(ends, True) if not logical.startswith('author/') or author.get('closed') is True else None
        retries = dict(reask=len(group)-len({c['slot'] for c in group}), resends=sum(number(v) for f in frames for v in obj(f.get('resends')).values()),
                       extra_tries=sum(max(0, number(v)-1) for f in frames for v in obj(f.get('tries')).values()),
                       adopted=sum(obj(c.get('raw')).get('source') == 'adopted' for c in group))
        retries['total'] = sum(retries.values())
        flows.append(dict(flow=logical, calls=len(group), call_ids=sorted(c['id'] for c in group), jobs=sorted(owned), tokens=token,
                          max_parallel=parallel(windows), start=start[1] if start else None, end=end[1] if end else None,
                          seconds=round((end[0]-start[0]).total_seconds(), 3) if start and end else None, open=end is None, retries=retries))
        all_windows.extend(windows)
    result = dict(scope=root.absolute().name, flows=flows, unreadable=sorted(unreadable), **summary(flows, all_windows))
    if not flows:
        result['tokens'] = dict.fromkeys(('used', 'reserve', 'pending', 'pending_reserve', 'prompt', 'completion', 'reasoning', 'cached'), 0)
        if overhead:
            result['tokens'].update(prompt_own=0, overhead_total=0)
    # 帳差只比有帳的 budget：沒帳的呼叫（例如直連代理的 smoke）不拉低帳差。
    bad = sum(v is None for v in books.values())
    unbooked = [c.get('used', 0) for k, c in calls.items() if 'request' in c and k[:2] not in books]
    result['ledger'] = ledger(sum(books.values()) if books and not bad else None, sum(c['used'] for k, c in calls.items() if k[:2] in books and 'used' in c),
                              gaps, bad, len(unbooked), sum(unbooked))
    return result, all_windows, ingredients
def ledger(used, receipts, gaps, bad, unbooked, unbooked_used):
    return dict(used=used, receipts=receipts, diff=used-receipts if used is not None else None, gaps=gaps, bad=bad,
                unbooked=unbooked, unbooked_used=unbooked_used)
def by(field, ingredients):
    groups, index = {}, ('model', 'holder', 'day', 'hour').index(field)
    for row in ingredients:
        group = groups.setdefault(row[index], dict(key=row[index], calls=0, used=0, overrun=0))
        group['calls'] += 1
        group['used'] += row[4]
        group['overrun'] += row[5]
    return dict(field=field, groups=[groups[k] for k in sorted(groups)])
def scan(path, overhead=0):
    return _scan(path, overhead)[0]
def line(scope_dict, overhead):
    s, t = scope_dict, scope_dict['tokens']
    count = len(s['flows']) if isinstance(s['flows'], list) else s['flows']
    own = f"＝代理 {t['overhead_total']}＋自己 {t['prompt_own']}" if overhead else ''
    sec = s['seconds']
    duration = f"{sec['mean']} 秒" if count == 1 and sec['mean'] is not None else f"平均 {sec['mean']} 秒、最長 {sec['max']} 秒" if sec['mean'] is not None else '未結案'
    if sec['open']:
        duration += f"、未結案 {sec['open']}"
    book = s['ledger']
    extra = f"；另 {book['unbooked']} 次呼叫沒帳、用 {book['unbooked_used']} token" if book['unbooked'] else ''
    balance = f"{book['diff']}（帳 {book['used']}－回條 {book['receipts']}{extra}）" if book['used'] is not None else f"不明（{book['bad']} 個帳檔讀不了）" if book['bad'] else '無帳'
    return (f"{s['scope']}：{count} 件、{s['calls']} 次呼叫｜每件 token {int(t['used']/count) if count else 0}"
            f"（prompt {t['prompt']}{own}、completion {t['completion']}、推理 {t['reasoning']}、cached {t['cached']}；"
            f"預留 {t['reserve']}、未結 {t['pending']}）｜並行最多 {s['max_parallel']}｜收到→做完 {duration}｜重試 {s['retries']['total']}｜帳差 {balance}、缺口 {book['gaps']}")
def plain(scope_dict):
    """給人看的預設一行：每格都有白話標籤與單位。"""
    s, t = scope_dict, scope_dict['tokens']
    count = len(s['flows']) if isinstance(s['flows'], list) else s['flows']
    if not count:
        text = f"{s['scope']}：沒找到 AI 工作紀錄（要指到含 llmcall/、budget/、author/ 的資料夾或它的上層）"
    else:
        sec, avg = s['seconds'], '平均' if count > 1 else ''
        if sec['mean'] is None:
            took = '還沒結束'
        elif count > 1:
            took = f"平均花 {sec['mean']} 秒（最長 {sec['max']} 秒）"
        else:
            took = f"花 {sec['mean']} 秒"
        if sec['open'] and sec['mean'] is not None:
            took += f"，另有 {sec['open']} 件還沒結束"
        text = (f"{s['scope']}：{count} 件工作｜{avg}每件用 {int(t['used']/count)} token"
                f"｜同時最多 {s['max_parallel']} 個在問模型｜{took}｜重試 {s['retries']['total']} 次")
        if t['pending']:
            text += f"｜{t['pending']} 次還沒結帳"
    if s.get('unreadable'):
        text += f"｜{len(s['unreadable'])} 個檔讀不了已跳過"
    return text
HELP = """量一個資料夾裡 AI 工作用了多少：token、同時幾個呼叫、花幾秒、重試幾次。只讀不寫。

例：aos7-metrics job proto7-2/modules/metrics/baseline/r1/loop-gpt-6-sol
"""
EPILOG = """PATH 要量哪個資料夾：
  給資料夾（不是檔案）。工具會往下找所有子資料夾，所以指放紀錄的那層或它的任何上層都行；
  裡面要有別的工具留下的紀錄（llmcall/、budget/、author/、events/、jobs/）。找不到就印「沒找到 AI 工作紀錄」。
  給多個 PATH 時每個印一行，最後多一行「合計」。

預設輸出（一行，每格白話）：
  名稱：N 件工作｜每件用 X token｜同時最多 P 個在問模型｜花 S 秒｜重試 R 次
  件＝一件 AI 工作：按 logical 分，同一張需求的呼叫（含審查／學習）算一件；brain 一封信一件，同件多回合不算重試；沒標 logical 的單次呼叫自己算一件。

--detail 把 token 拆成 prompt／completion／推理／cached，另列預留（先保留的上限，不是真的用掉）與未結，與帳差（帳上 used 減有帳呼叫的回條合計）、缺口。
--json 欄位：{v, overhead, scopes, total}，scope 含 flows、tokens、max_parallel、seconds、retries 等；--overhead 量法與各欄算法見 ADVANCED.md。
退出碼：0 成功（有讀不了的檔也算）；2 參數不對或 PATH 不是資料夾。
"""
class ArgumentParser(argparse.ArgumentParser):
    """用法錯誤只印一行人話，不印 usage。"""
    def error(self, message):
        message = " ".join(message.splitlines()).rstrip("。")
        self.exit(2, f'aos7-metrics: 參數不對：{message}。例：aos7-metrics job proto7-2/modules/metrics/baseline/r1/loop-gpt-6-sol；全部選項看 --help\n')

def main(argv=None):
    parser = ArgumentParser(prog='aos7-metrics', description=HELP, epilog=EPILOG,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['job'], help='唯一的子指令：量資料夾')
    parser.add_argument('paths', nargs='+', metavar='PATH', help='要量的資料夾（可多個）')
    parser.add_argument('--detail', action='store_true', help='改印細節行（token 拆項、預留、未結）')
    parser.add_argument('--overhead', type=int, default=0, metavar='N', help='代理每次自動加的 prompt token 數，預設 0（見下）')
    parser.add_argument('--by', choices=['model', 'holder', 'day', 'hour'], metavar='FIELD', help='FIELD 是 model／holder／day／hour：按模型／呼叫者／日／時分組（含 --detail）')
    parser.add_argument('--json', action='store_true', help='印給程式讀的一行 JSON')
    args = parser.parse_args(argv)
    if args.overhead < 0:
        parser.error('--overhead 必須非負')
    for path in args.paths:
        if not Path(path).is_dir():
            shown = ' '.join(path.splitlines())
            print(f'aos7-metrics: 不是資料夾：{shown}。PATH 要給資料夾，例：aos7-metrics job proto7-2/modules/metrics/baseline/r1/loop-gpt-6-sol', file=sys.stderr)
            return 2
    scanned = [_scan(p, args.overhead) for p in sorted(args.paths)]
    scopes = [s for s, _, _ in scanned]
    flows = [f for s in scopes for f in s['flows']]
    total = dict(scope='合計', flows=len(flows), **summary(flows, [w for _, windows, _ in scanned for w in windows]))
    if not flows:
        total['tokens'] = scopes[0]['tokens'].copy()
    amounts = [s['ledger']['used'] for s in scopes if s['ledger']['used'] is not None]
    bad = sum(s['ledger']['bad'] for s in scopes)
    total['ledger'] = ledger(sum(amounts) if amounts and not bad else None, sum(s['ledger']['receipts'] for s in scopes), sum(s['ledger']['gaps'] for s in scopes), bad, *(sum(s['ledger'][k] for s in scopes) for k in ('unbooked', 'unbooked_used')))
    if args.by:
        for s, _, rows in scanned:
            s['by'] = by(args.by, rows)
        total['by'] = by(args.by, [row for _, _, rows in scanned for row in rows])
    if args.json:
        print(json.dumps(dict(v=1, overhead=args.overhead, scopes=scopes, total=total), ensure_ascii=False, sort_keys=True))
    else:
        for s in scopes + ([total] if len(scopes) > 1 else []):
            print(line(s, args.overhead) if args.detail or args.by else plain(s))
            if args.by:
                for g in s['by']['groups']:
                    print(f"　　{args.by} {g['key']}：{g['calls']} 次呼叫、用 {g['used']} token、超支 {g['overrun']}")
    return 0
