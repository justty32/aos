#!/usr/bin/env python3
"""Summarize measured git image costs and explicit one-week extrapolation models."""
import argparse
import collections
import datetime
import json
import math
from pathlib import Path
import platform
import re
import statistics

HERE = Path(__file__).resolve().parent
MIB = 1024 ** 2
METRICS = [
    ('git_before_bytes', 'Git before gc'), ('git_after_bytes', 'Git after gc'),
    ('object_count', 'Loose objects'), ('status_s', 'status'), ('add_s', 'add'),
    ('commit_s', 'commit'), ('gc_s', 'gc'), ('clone_s', 'clone time'),
    ('clone_bytes', 'clone total (raw fit)'), ('clone_git_bytes', 'clone .git'),
    ('clone_checkout_bytes', 'clone checkout'),
    ('squash_bytes', 'single-image orphan pack'),
    ('depth1_s', 'depth-1 clone time'), ('squash_gc_s', 'orphan squash gc time'),
]


def slope(points):
    groups = collections.defaultdict(list)
    for x, y in points:
        if x > 0 and y > 0:
            groups[x].append(y)
    if len(groups) < 2:
        return None
    xs = [math.log(x) for x in groups]
    ys = [statistics.mean(math.log(y) for y in groups[x]) for x in groups]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    return sum((x-mx)*(y-my) for x, y in zip(xs, ys)) / sum((x-mx)**2 for x in xs)


def linear_quadratic(points):
    """Fit nonnegative E(N)=a*N+b*N*N to per-round excess, equal weight per N."""
    groups = collections.defaultdict(list)
    for n,y in points:
        groups[n].append(y)
    if len(groups)<2:
        return None
    xs=list(groups)
    ys=[math.exp(statistics.mean(math.log(v) for v in groups[n]))/n for n in xs]
    mx,my=statistics.mean(xs),statistics.mean(ys)
    b=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sum((x-mx)**2 for x in xs)
    a=my-b*mx
    if b<0:
        a,b=my,0.0
    elif a<0:
        a,b=0.0,sum(x*y for x,y in zip(xs,ys))/sum(x*x for x in xs)
    return a,b


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---']*len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(str, r)) + ' |' for r in rows])


def mb(n):
    return f'{n/MIB:,.2f}'


def sec(n):
    return f'{n:.4f}'


def label(r):
    return r['mode'] + ('+archive' if r['archive'] else '')


def load(paths):
    current, completed, attempts = {}, {}, collections.defaultdict(list)
    executions, total_time = collections.defaultdict(int), collections.defaultdict(float)
    for path in paths:
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r.get('agents') != 50:
                continue
            if r['kind'] == 'start' and r['attempt'] == 1:
                executions[r['scenario']] += 1
            r['execution'] = executions[r['scenario']]
            key = r['scenario'], r['execution'], r['attempt']
            if r['kind'] == 'start':
                current[key] = dict(start=r, commits=[], phases={})
            elif r['kind'] == 'commit':
                start = current[key]['start']
                r['pack_threads'] = start.get('configured_pack_threads',int(re.search(r'pack threads (\d+)',start['note']).group(1)))
                current[key]['commits'].append(r)
            elif r['kind'] == 'phase':
                if 'clone_bytes' in r:
                    r['clone_checkout_bytes'] = r['clone_bytes'] - r['clone_git_bytes']
                current[key]['phases'].update({k:v for k,v in r.items() if k not in ['kind','phase']})
            elif r['kind'] == 'result':
                d = dict(r)
                d.update(current[key]['commits'][-1])
                d.update(r)
                d['object_count'] = r['loose_before']['count']
                d['clone_checkout_bytes'] = r['clone_bytes'] - r['clone_git_bytes']
                d['start'] = current[key]['start']
                d['pack_threads'] = d['start'].get('configured_pack_threads', int(re.search(r'pack threads (\d+)',d['start']['note']).group(1)))
                d['commit_records'] = current[key]['commits']
                eligible = [c for c in d['commit_records'] if c['auto_sample_17'] > 27 or c['objects']['packs'] > 50]
                first = eligible[0] if eligible else None
                d['auto_first_trigger'] = dict(commit=first['commit_index'],round=first['round'],sample_17=first['auto_sample_17'],loose=first['objects']['count'],packs=first['objects']['packs']) if first else None
                completed[r['scenario']] = d
            elif r['kind'] == 'attempt_end':
                r['commit_records'] = current[key]['commits']
                r['phase_metrics'] = current[key]['phases']
                attempts[r['scenario']].append(r)
            elif r['kind'] == 'cleanup':
                total_time[r['scenario']] += r['total_attempt_s']
                for failure in attempts[r['scenario']]:
                    if failure['attempt'] == r['attempt'] and failure['execution'] == r['execution']:
                        failure['cleanup_s'] = r['cleanup_s']
                        failure['total_attempt_s'] = r['total_attempt_s']
                if r['scenario'] in completed and completed[r['scenario']]['attempt'] == r['attempt'] and completed[r['scenario']]['execution'] == r['execution']:
                    completed[r['scenario']]['cleanup_s'] = r['cleanup_s']
                    completed[r['scenario']]['total_attempt_s'] = r['total_attempt_s']
    for scenario, result in completed.items():
        result['all_attempts_elapsed_s'] = total_time[scenario]
    rows = sorted(completed.values(), key=lambda r: ('ABCDEF'.index(r['mode']), r['archive'], r['commit_every'] != 10, r['requested_rounds'], r['commit_every']))
    return rows, attempts


def model(rows, metric):
    rows = [r for r in rows if metric in r]
    baseline = [r for r in rows if r['commit_every'] == 10]
    p = slope([(r['rounds'], r[metric]) for r in baseline])
    if p is None:
        return None
    # The largest actual baseline gives the shortest extrapolation distance.
    anchor = max(baseline, key=lambda r: (r['rounds'], -r['requested_rounds']))
    p_used = max(0, p) if metric.endswith('_s') else p
    # Fit K after removing measured N growth; all successfully completed K variants count.
    q = slope([(r['commit_every'], r[metric]/r['rounds']**p_used) for r in rows])
    if q is None:
        q = 0.0
    value = anchor[metric] * (10080/anchor['rounds'])**p_used * (60/anchor['commit_every'])**q
    return dict(p=p, p_used=p_used, q=q, value=value, anchor_rounds=anchor['rounds'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('results', nargs='*', type=Path, default=[HERE/'results.jsonl'])
    p.add_argument('--out', type=Path, default=HERE/'summary.md')
    p.add_argument('--report', type=Path, default=HERE.parent/'out.md')
    a = p.parse_args()
    rows, attempts = load(a.results)
    if not rows:
        p.error('No completed M=50 scenarios found.')
    groups = collections.defaultdict(list)
    for r in rows:
        groups[label(r)].append(r)
    fit_groups = {name:[r for r in rs if r['pack_threads']==2] for name,rs in groups.items()}
    partials = []
    for failures in attempts.values():
        for f in failures:
            records = f.get('commit_records', [])
            if records:
                last = records[-1]
                partials.append((f,last))
                if last['round'] == f['rounds'] and last['pack_threads'] == 2:
                    partial = dict(last, **{k:v for k,v in f.get('phase_metrics',{}).items() if k not in last}, git_before_bytes=last['git_bytes'],
                                   object_count=last['objects']['count'])
                    fit_groups.setdefault(label(last), []).append(partial)
    models = {name: {metric: model(rs, metric) for metric, _ in METRICS}
              for name, rs in fit_groups.items()}
    storage_components = []
    for name in 'ABCD':
        rs = fit_groups.get(name, [])
        mm = models.get(name, {})
        if not mm.get('squash_bytes'):
            continue
        # Final image content and checkout do not depend on freeze frequency.
        for fixed_metric in ['squash_bytes','clone_checkout_bytes']:
            fm = mm.get(fixed_metric)
            base = [r for r in rs if r['commit_every']==10 and fixed_metric in r]
            if fm and base:
                anchor = max(base,key=lambda r:r['rounds'])
                fm['raw_q'] = fm['q']
                fm['q'] = 0.0
                fm['value'] = anchor[fixed_metric]*(10080/anchor['rounds'])**fm['p_used']
                fm['weekly_method'] = 'final content depends on N only; q=0'
        final_model = mm['squash_bytes']
        base = [r for r in rs if r['commit_every']==10 and 'squash_bytes' in r]
        anchor = max(base,key=lambda r:r['rounds'])
        for metric in ['git_before_bytes','git_after_bytes','clone_git_bytes']:
            if not mm.get(metric):
                continue
            residual_rows = []
            for r in rs:
                if metric not in r:
                    continue
                single = r.get('squash_bytes',anchor['squash_bytes']*(r['rounds']/anchor['rounds'])**final_model['p_used'])
                residual_rows.append(dict(r, overhead=max(r[metric]-single,r[metric]*.001)))
            hm = model(residual_rows,'overhead')
            if hm is None:
                continue
            mm[metric]['raw_power_value'] = mm[metric]['value']
            mm[metric]['historical_overhead_model'] = hm
            mm[metric]['single_image_model'] = dict(final_model)
            mm[metric]['weekly_method'] = 'single image N-only + history overhead N,K power fit'
            mm[metric]['value'] = final_model['value'] + hm['value']
            storage_components.append([name,metric,f"{final_model['p_used']:.3f}",f"{hm['p_used']:.3f}",
                                       f"{hm['q']:.3f}",str(hm['anchor_rounds']),
                                       f"{final_model['value']/1024**3:.3f}",f"{hm['value']/1024**3:.3f}"])
    # Archive storage adds retained letters independent of freeze frequency. Calibrate
    # its excess over A at matching N; extrapolate that excess and add A's K=60 model.
    archive_diagnostics = []
    if 'A+archive' in groups and 'A' in groups:
        arch_all = [r for r in fit_groups['A+archive'] if r['commit_every'] == 10]
        normal = [r for r in groups['A'] if r['commit_every'] == 10]
        for metric, title in METRICS:
            am = models['A'][metric]
            if am is None:
                continue
            points = []
            for r in [r for r in arch_all if metric in r]:
                # Interpolate A with its measured baseline exponent, at K=10.
                base = max(normal, key=lambda x:x['rounds'])
                expected = base[metric] * (r['rounds']/base['rounds'])**am['p_used']
                points.append((r['rounds'], max(r[metric]-expected, r[metric]*.001)))
            pp = slope(points)
            assumed = pp is None
            if pp is None:
                pp = 2.0 if metric in ['git_before_bytes', 'add_s'] else 1.0
            pp_used = max(0, pp)
            n, excess = max(points)
            value = am['value'] + excess*(10080/n)**pp_used
            polynomial = linear_quadratic(points) if metric.endswith('_bytes') and metric!='clone_bytes' else None
            if polynomial:
                aa,bb=polynomial
                value=am['value']+aa*10080+bb*10080**2
            models['A+archive'][metric] = dict(p=pp, p_used=pp_used, q=0, value=value,
                                               anchor_rounds=n, assumed=assumed, excess=True)
            if polynomial:
                models['A+archive'][metric]['archive_linear_coefficient']=aa
                models['A+archive'][metric]['archive_quadratic_coefficient']=bb
                models['A+archive'][metric]['weekly_method']='A weekly model + a*N + b*N^2; a,b nonnegative'
            archive_diagnostics.append([title, f'{pp:.3f}' + (' (assumed)' if assumed else ''),
                                        str(n), 'clone total = Git + checkout' if metric=='clone_bytes' else f'Aweek + aN+bN²; a={aa:.6g}, b={bb:.6g}; bytes' if polynomial else 'Aweek + power excess; q=0'])

    # Total clone size must include its own .git; extrapolate additive components.
    for name, mm in models.items():
        if all(mm.get(k) is not None for k in ['clone_bytes','clone_git_bytes','clone_checkout_bytes']):
            mm['clone_bytes']['raw_power_value'] = mm['clone_bytes']['value']
            mm['clone_bytes']['value'] = mm['clone_git_bytes']['value'] + mm['clone_checkout_bytes']['value']
            mm['clone_bytes']['weekly_method'] = 'clone_git_bytes + clone_checkout_bytes'
    main_rows = []
    for r in rows:
        main_rows.append([label(r), f"{r['requested_rounds']}→{r['rounds']} / {r['commit_every']}", str(r['pack_threads']),
                          f"{mb(r['worktree_bytes'])} / {r['worktree_files']:,}",
                          f"{mb(r['git_before_bytes'])} / {mb(r['git_after_bytes'])}",
                          f"{r['object_count']:,}", mb(r['packed_after']['size-pack']*1024),
                          f"{sec(r['status_s'])} / {sec(r['add_s'])} / {sec(r['commit_s'])}",
                          sec(r['gc_s']), sec(r['clone_s']),
                          f"{mb(r['clone_bytes'])} / {mb(r['clone_git_bytes'])}",
                          f"{mb(r['depth1_bytes'])} / {mb(r['depth1_git_bytes'])}", mb(r['squash_bytes'])])
    main_table = table(['模式', '要求→實際 N / K', 'pack threads', '工作樹 MiB / 檔數', 'Git gc前/後 MiB',
                        'loose 物件數', 'pack MiB', 'status/add/commit s', 'gc s', 'clone s',
                        'clone 總量/.git MiB', 'depth1 總量/.git MiB', 'squash .git MiB'], main_rows)
    fit_rows = []
    for name in ['A','A+archive','B','C','D']:
        baseline_all = [r for r in fit_groups.get(name, []) if r['commit_every'] == 10]
        for metric, title in METRICS:
            baseline = [r for r in baseline_all if metric in r]
            pp = slope([(r['rounds'], r[metric]) for r in baseline])
            mm = models.get(name, {}).get(metric)
            fit_rows.append([name, title, ','.join(map(str, sorted(set(r['rounds'] for r in baseline)))),
                             '沒量' if pp is None else f'{pp:.3f}',
                             '沒量' if pp is None else ('下降／雜訊' if pp<-.35 else '近常數' if pp<.35 else '近線性' if pp<1.5 else '近平方' if pp<2.5 else '快於平方'),
                             'archive 增量模型' if name=='A+archive' else f"{mm.get('raw_q',mm['q']):.3f}" if mm else '沒量'])
    fit_table = table(['模式','量測項目','擬合實際 N','log-log p(N)','成長判讀','總量 q(K)（診斷）'], fit_rows)
    weekly_rows = []
    for name in ['A','A+archive','B','C','D']:
        mm = models.get(name, {})
        if not mm or any(v is None for v in mm.values()):
            weekly_rows.append([name] + ['沒量']*7)
            continue
        v = {k:m['value'] for k,m in mm.items()}
        weekly_rows.append([name, f"{v['git_before_bytes']/1024**3:,.2f} / {v['git_after_bytes']/1024**3:,.2f}",
                            f"{v['object_count']:,.0f}",
                            f"{v['status_s']:.3f} / {v['add_s']:.3f} / {v['commit_s']:.3f}",
                            f"{v['gc_s']:.2f}", f"{v['clone_s']:.2f}",
                            f"{v['clone_bytes']/1024**3:,.2f} / {v['clone_git_bytes']/1024**3:,.2f}", '外推'])
    weekly_table = table(['模式','Git gc前/後 GiB','loose 物件數','status/add/commit s',
                          'gc s','clone s','clone 總量/.git GiB','性質'], weekly_rows)
    runtime_rows = []
    problems = []
    for r in rows:
        failed = attempts[r['scenario']]
        elapsed = r['all_attempts_elapsed_s']
        retry = '; '.join(f"N={f['rounds']}: {f['reason']} ({f['elapsed_s']:.2f}s), retry N={f.get('retry_rounds','?')}" for f in failed)
        runtime_rows.append([label(r),f"{r['requested_rounds']}→{r['rounds']} / {r['commit_every']}",
                             f"{r['elapsed_s']:.2f}", f"{r.get('cleanup_s',0):.2f}",f'{elapsed:.2f}',retry or 'none'])
        if retry:
            problems.append(f"- {r['scenario']}: {retry}.")
    runtime_table = table(['模式','要求→實際 N / K','成功嘗試秒','成功清理秒','累計實跑秒*','砍規模原因'], runtime_rows)
    auto_rows = [[label(r),f"{r['requested_rounds']}→{r['rounds']} / {r['commit_every']}",
                  json.dumps(r['auto_first_trigger'],separators=(',',':')) if r['auto_first_trigger'] else '未達門檻'] for r in rows]
    partial_table = table(['模式','嘗試 N / 最後量到輪數','Git gc前/後 MiB','gc s','status/add/commit s','停止原因'],
                          [[label(f),f"{f['rounds']} / {last['round']}",mb(last['git_bytes'])+' / '+(mb(f['phase_metrics']['git_after_bytes']) if 'git_after_bytes' in f.get('phase_metrics',{}) else '沒量'),
                            sec(f['phase_metrics']['gc_s']) if 'gc_s' in f.get('phase_metrics',{}) else '沒量',
                            f"{sec(last['status_s'])} / {sec(last['add_s'])} / {sec(last['commit_s'])}",f['reason']]
                           for f,last in partials])
    auto_table = table(['模式','N / K','首次預設 auto-gc 候選'], auto_rows)
    expected = {(m,False,n,k) for m in 'ABCD' for n,k in [(100,10),(200,10),(400,10),(200,1),(200,50)]}
    expected |= {('A',True,n,10) for n in [100,200]}
    covered = {(r['mode'],r['archive'],r['requested_rounds'],r['commit_every']) for r in rows}
    missing = sorted(expected-covered)
    comparison = []
    for mode in 'ABCD':
        candidates = [r for r in groups.get(mode,[]) if r['rounds']==200 and r['commit_every']==10]
        if candidates:
            r=min(candidates,key=lambda r:r['requested_rounds'])
            comparison.append(f"{mode}={mb(r['git_before_bytes'])}/{mb(r['git_after_bytes'])} MiB")
        else:
            comparison.append(f'{mode}=沒量')
    conclusion = ('50 隻 agent、N=200、K=10 的 .git（gc 前／後）為：'+'；'.join(comparison)+'。'
                  'A 保留全部增長中的 history、request 與 live，反覆快照的膨脹明顯；B 排除暫存檔，'
                  'C 只留最後 64 行 history，D 封存 64 KiB 分段以保留完整 history 並減少重寫。'
                  '完整 clone 仍攜帶版本歷史；depth-1 與 orphan squash 才接近單一 image 的成本。'
                  f'任務書矩陣已完成或註明砍規模 {len(expected & covered)}/{len(expected)} 個情境。'
                  '一週數字是模型外推，並非實跑；不能當作容量或延遲保證。')
    method = '''單位一律用二進位 MiB/GiB。工作樹大小是所有一般檔案長度總和，包含 ignore 的檔案；`.git` 與 clone 總大小用 `du -sb`，含目錄的 apparent size。clone「總量」含 checkout，旁邊的 `.git` 欄獨立列出 Git 資料量；這不是網路傳輸封包的精確大小。`count-objects` 的 size/size-pack 原始單位是 KiB。每個來源 repo 都重新建立、關閉 auto-gc，最後只做一次明確的 gc；完整 `--no-local` clone 與 `--depth 1 file://` clone 依序量完即刪。squash 用無 parent 的 `commit-tree`，移動唯一分支、清空 reflog，最後 `gc --prune=now`。status/add/commit 是最後一次凍住的各自耗時，commit 不含 add；gc 包含 repack 與 prune。這是本機暖快取、file transport，不是 WAN 效能。所有重指令均用 `nice -n 15`，實際優先值因繼承而至少為 15；Git pack threads 設 2。

詞表來自本機 Python 標準庫文字，固定抽出 4,096 個詞、隨機填入多種句型；詞表 SHA256 與 seed 存在 JSONL。純 prose 的 zlib 比約 3.78 倍。每輪四行有效 JSON history 共 3,072 B；20% agent 另外 append 20,480 B live event；request 放入完整 history 與約 6 KiB system/tools。C 的 64 行在此等於 16 輪；舊行仍真的寫進 ignore 的 history.old，request/live 也照常生成。D 在下一行會跨過 65,536 B 前封存目前分段，不拆 JSON 行。stderr／thought／trash 的機率按每 agent 每輪計算，各情境用相同 seed。thought 是不再活動的 kept 小格，用一行有效 JSON 摘要表達 3～10 輪、長度按輪數產生，沒有遞迴模擬活的子 agent。任務書的 ignore 清單原樣保留，再補 `ws/.trash/`，因根目錄 `.trash/` 無法匹配真正位置。暫存檔是真的一般檔案；`.sock` 是同名一般檔案，沒有啟動 socket 服務。

**N 斜率：** 每個量各自取 K=10 的實際 N，以 log(V) 對 log(N) 做最小平方法。砍規模造成相同 N 時，先平均 log(V)，避免重複 N 權重失衡。p≈0 是近常數，p≈1 線性，p≈2 平方。若一次嘗試已完成全部凍住、卻在後續 gc/clone 被砍，已量到的 gc 前大小、物件數、最後 status/add/commit 仍進入其擬合；已寫下的 gc/clone 階段也進各自擬合，缺的階段寫「沒量」。因此 A 的 gc 前可以含 N=400，gc 後可能只有 N=100/200。毫秒級耗時容易受雜訊影響；表列原始 p，只有外推耗時時把負 p 改用 0，沒有替空間量偷偷截斷斜率。

**K 換算：** A/B/C/D 各量先得到 p，再用所有成功 K=1/10/50 情境（及有完整階段量測的砍規模嘗試），對 log(V/N^p) 與 log(K) 擬合 q；使用的是實際 N。對耗時、物件數，以最大的實際 K=10 樣本作 V0、N0，計算 **Vweek = V0 × (10080/N0)^p × (60/10)^q**。一週每分鐘一輪是 N=10080、每 60 輪 commit，共 168 次；不能直接按 N 放大而沿用 K=10。常數 metadata、state 物件與 Git 打包行為讓這個冪次模型只能是近似。**空間量採可加的分量模型**：先以 orphan squash 的 N 斜率估單一 image S(N)，令 q=0；每筆 .git gc 前／gc 後／clone .git 扣去同筆 squash 大小（缺 squash 的完整凍住用 S(N) 內插），得到歷史開銷 H，再分別擬合 H 的 pH、qH。最後 **Gitweek = Sweek + H0 × (10080/N0)^pH × (60/10)^qH**。這避免把 D 的不可消失的封存段也按 commit 次數一起縮小；原始總量 p 仍在 N 斜率表展示，真正用於空間外推的分量斜率另表列出。H 最低取觀察量的 0.1% 供 log 擬合。**clone 總量另外拆成 .git 與 checkout（實測總量減 .git），分別擬合後相加，checkout 與 K 無關、固定 q=0**；直接用總量的單一斜率跨尺度外推可能反而小於其 .git，故 raw total 斜率只展示、不用作最後總量預測。外推「物件數」指 auto-gc 關閉、最後一次 gc 前的 loose objects，並非檔案數；gc 後這些實測的 loose 都是 0。

**archive 換算：** 信件每輪留下，與 commit 頻率無關，但 archive 沒有 K 的實測變體。每個量先用 A 的 N 斜率算出 A(N,K=10)，從 A+archive 實測扣掉它，得到信件增量 E(N)，再用不同實際 N 擬合 pE。外推為 **Aweek + E(N0) × (10080/N0)^max(0,pE)**，信件增量假設 q=0，只有 A 的部分套用 K 修正。若不滿兩個 archive 規模，gc 前大小／add 的 pE 假設為 2，其餘假設為 1；表格明列 assumed，不冒稱實測。小於 archive 觀察量 0.1% 的 residual 以 0.1% 為下限，才能取 log。pack delta 共用與效能並非可加，此模型特別不確定。**archive 的空間量改用非負 aN+bN² 擬合增量**：因 request body 每輪隨 history 增長，留下的全部信件自然包含線性 metadata 與平方的 body；只有 N=25/50 等小規模時，局部 log-log p 會低估漸近平方項。以各 N 的 E/N 對 N 擬合 a、b，若係數為負則用 a=0 或 b=0 的邊界最小平方模型；最後空間為 Aweek+a×10080+b×10080²，增量仍令 q=0。空間的 pE 表列為局部診斷，真正用的 a、b 另列；耗時與物件數仍用 pE。clone 總量照前述兩分量相加。完整參數另存 model.json。

沒有跑一週。從 N=400 放大 25 倍以上（archive 可能更遠），delta chain、壓縮率、物件量、目錄結構、快取與 commit 間隔都可能改變成長率；耗時只測一個 seed、沒有重複樣本，不提供假精確的信賴區間。報表上的秒數保留小數是為了保留資料，不代表預測有這種精度；超過 2 GiB 的預測只是一個數學估值。

**預設 auto-gc：** 依實際 `.git/objects/17` 抽樣桶計數，預設 6700 的門檻是超過 ceil(6700/256)=27，也就是第 28 個抽樣物件；pack 則要超過 50 個。邊界已對照 [Git 2.43.0 原始碼](https://github.com/git/git/blob/v2.43.0/builtin/gc.c#L181-L210)。表列是「關閉 gc 的這條歷史，首次何時符合候選條件」，沒有真的執行 auto-gc，也沒有模擬前一次 gc 改變後的下一次觸發。所有實測 gc 前 pack 都是 0。

**資源與清理：** 用 allocated `du -s -B1`、逐筆檔案 block 估值、64 MiB headroom，加上打包／checkout 的額外預留控制磁碟。早期 A 的 clone 曾預留兩份 pack，比實際所需保守，因此有一次過早砍規模；已修正並在問題表保留紀錄。保守預留被擋也算砍規模，不代表真的用滿 2 GiB。每次嘗試的工作期限為 600 秒，超時只終止自己開的 child process group；之後清理另外計時。每次嘗試都刪掉 source tree、.git 與 clone，只留紀錄。
'''
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    parts = ['# Git image 壓測彙整', '', conclusion, '',
             f'Generated {stamp}; Python {platform.python_version()}; {rows[0]["start"]["git_version"]}.', '',
             f'Required matrix coverage: {len(expected & covered)}/{len(expected)}; missing: {missing or "none"}.', '',
             '## 實測主表', '', main_table, '', '## N 成長斜率與 K 敏感度', '', fit_table, '',
             '## 一週極限外推：M=50、N=10080、K=60、168 次凍住', '', weekly_table, '',
             '### 空間外推的單一 image 與版本歷史分量', '', table(['模式','量','p(image)','p(history)','q(history)','history anchor N','image GiB','history GiB'],storage_components), '',
             '### archive 增量參數', '', table(['Metric','pE','anchor N','method'],archive_diagnostics), '',
             '## 每情境耗時與砍規模', '', runtime_table, '',
             '*累計實跑包含同情境所有重跑、砍規模嘗試與清理；主表採最後一次完成的結果。', '',
             '## 被砍嘗試仍保留的量測', '', partial_table, '',
             '## 預設 auto-gc 首次候選', '', auto_table, '',
             '## 方法與限制', '', method, '',
             '## 問題與沒量的項目', '', '\n'.join(problems) if problems else '- 沒有砍規模或執行錯誤。', '',
             '- 磁碟上限由預留控制，沒有連續取樣；不能把每次凍住的樣本當成精確最高水位。',
             '- auto-gc 最初的推導邊界已按 Git 2.43 原始碼改正為桶內 28 個物件；原始抽樣桶計數與耗時未變。',
             '- 主表列出每次成功情境的 pack threads；擬合僅使用 2 threads，外部暫改為 1 thread 的紀錄不混入。',
             '- 網路傳輸、實際 aos 與醒來正確性沒量。', '']
    a.out.write_text('\n'.join(parts))
    report = ['# I 隊壓測結果', '', conclusion, '', '## 實測主表', '', main_table, '',
              '## 一週極限外推', '', weekly_table, '',
              '一週各數字均為外推：N 成長與 K 間隔分別擬合，archive 另算留下信件的增量；方法與斜率見 [summary.md](sim/summary.md)。', '',
              '## 每情境實際耗時', '', runtime_table, '',
              '## 遇到的問題', '', '\n'.join(problems) if problems else '- 沒有砍規模。', '',
              '- 一週沒實跑；毫秒級延遲斜率與 archive 打包外推尤其不確定。',
              '- 根目錄 `.trash/` 無法匹配 `ws/.trash/`，已補正確路徑。',
              '- repo 全程唯讀；每次嘗試的工作樹、clone 與 `.git` 均在結束後清掉。', '',
              f'Required matrix coverage: {len(expected & covered)}/{len(expected)}. Missing: {missing or "none"}.', '']
    a.report.write_text('\n'.join(report))
    (HERE/'model.json').write_text(json.dumps(models,indent=2)+'\n')
    print(f'Wrote {a.out} and {a.report}; {len(rows)} successful scenarios; {len(missing)} required cases missing.')
    from task2_summary import report as report_task2
    report_task2(a.out, rows, models)


if __name__ == '__main__':
    main()
