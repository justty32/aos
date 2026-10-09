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
def _scan(path, overhead):
    root = Path(path).absolute()
    calls, authors, jobs, events, unreadable = {}, {}, {}, {}, []
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
            continue
        m = matches[index]
        if index == 0:
            base, budget, cid, kind = m.groups()
            call((base, budget, cid))[kind] = data
        elif index == 1:
            base, budget = m.groups()
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
    for key, c in sorted(calls.items()):
        cid = obj(c.get('request')).get('call_id')
        c['id'] = cid if isinstance(cid, str) else key[2]
        logical = obj(c.get('request')).get('logical')
        grouped.setdefault(logical if isinstance(logical, str) else 'call:' + c['id'], []).append(c)
    flows, all_windows = [], []
    for logical, group in sorted(grouped.items()):
        token = dict.fromkeys(('used', 'reserve', 'pending', 'pending_reserve', 'prompt', 'completion', 'reasoning', 'cached'), 0)
        windows, starts, ends, usage_count = [], [events.get(logical)], [], 0
        for c in group:
            req, raw, rec, gate, op = (obj(c.get(k)) for k in ('request', 'raw', 'receipt', 'gateway', 'ledger'))
            reply = obj(raw.get('reply'))
            done = gate.get('stage') == 'done'
            final = rec if rec else gate if done else {}
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
        retries = dict(reask=max(0, len(group)-1), resends=sum(number(v) for f in frames for v in obj(f.get('resends')).values()),
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
    return result, all_windows
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
    return (f"{s['scope']}：{count} 件、{s['calls']} 次呼叫｜每件 token {int(t['used']/count) if count else 0}"
            f"（prompt {t['prompt']}{own}、completion {t['completion']}、推理 {t['reasoning']}、cached {t['cached']}；"
            f"預留 {t['reserve']}、未結 {t['pending']}）｜並行最多 {s['max_parallel']}｜收到→做完 {duration}｜重試 {s['retries']['total']}")
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
  給資料夾（不是檔案）。工具會往下找所有子資料夾，所以指 node 資料夾或它的任何上層都行；
  裡面要有別的工具留下的紀錄（llmcall/、budget/、author/、events/、jobs/）。找不到就印「沒找到 AI 工作紀錄」。
  給多個 PATH 時每個印一行，最後多一行「合計」。

預設輸出（一行，每格白話）：
  名稱：N 件工作｜每件用 X token｜同時最多 P 個在問模型｜花 S 秒｜重試 R 次
  件＝一件 AI 工作（例如一張需求）。

--detail 把 token 拆開：prompt（送出）、completion（回答）、推理、cached（命中快取）、
  預留（呼叫前先保留的 token 上限，不是真的用掉）、未結（還沒算完帳的呼叫數，正常 0）。
--overhead N 每次呼叫被代理（例如 LiteLLM）自動加進 prompt 的 token 數；只影響 --detail 和 --json，
  不知道就不用給（預設 0）。量法：經代理送一個空 prompt，--detail 看到的 prompt 數就是 N。
--json 印一行 JSON：{v, overhead, scopes:[每個 PATH], total:合計}；每個 scope 有
  scope、flows（每件明細）、calls、tokens、max_parallel、window_unknown、seconds{mean,max,open}、retries、unreadable。

退出碼：0 成功（有讀不了的檔也算成功）；2 用法錯或 PATH 不是資料夾。
"""
def main(argv=None):
    parser = argparse.ArgumentParser(prog='aos7-metrics', description=HELP, epilog=EPILOG,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['job'], help='唯一的子指令：量資料夾')
    parser.add_argument('paths', nargs='+', metavar='PATH', help='要量的資料夾（可多個）')
    parser.add_argument('--detail', action='store_true', help='改印細節行（token 拆項、預留、未結）')
    parser.add_argument('--overhead', type=int, default=0, metavar='N', help='代理每次自動加的 prompt token 數，預設 0（見下）')
    parser.add_argument('--json', action='store_true', help='印給程式讀的一行 JSON')
    args = parser.parse_args(argv)
    if args.overhead < 0:
        parser.error('--overhead 必須非負')
    for path in args.paths:
        if not Path(path).is_dir():
            print(f'aos7-metrics：不是資料夾：{path}（PATH 要給資料夾，見 --help）', file=sys.stderr)
            return 2
    scanned = [_scan(p, args.overhead) for p in sorted(args.paths)]
    scopes = [s for s, _ in scanned]
    flows = [f for s in scopes for f in s['flows']]
    total = dict(scope='合計', flows=len(flows), **summary(flows, [w for _, windows in scanned for w in windows]))
    if not flows:
        total['tokens'] = scopes[0]['tokens'].copy()
    if args.json:
        print(json.dumps(dict(v=1, overhead=args.overhead, scopes=scopes, total=total), ensure_ascii=False, sort_keys=True))
    else:
        for s in scopes + ([total] if len(scopes) > 1 else []):
            print(line(s, args.overhead) if args.detail else plain(s))
    return 0
