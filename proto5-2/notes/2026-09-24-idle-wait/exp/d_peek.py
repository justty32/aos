"""實驗 D：方案 (a)「一支喚醒員掃所有 agent」掃一輪要多久（在同一支 Python 裡，不起新行程）。

對每個 agent 家做「最便宜的偷看」：讀 state.json；batch 在途＝對每個還沒 done 的 call 查 K/requests、K/responses 兩個檔；
idle＝列 input 資料夾；另外看 paused 在不在。拿實驗 B 留下的 agent 家（300 個）重複掃，換算成每個 agent 的成本。
另量一次 listdir K/responses（方案 (d) 的「只看一個資料夾」）。

用法：python3 d_peek.py AGENTS_DIR K_DIR
"""
import json
import os
import statistics
import sys
import time
from pathlib import Path


def peek(home, kernel):
    try:
        st = json.loads((home / 'state.json').read_text())
    except (OSError, ValueError):
        return True  # 讀不懂就叫它起來，讓真 tick 去報錯
    if (home / 'paused').exists():
        return False
    if st.get('consuming') or st.get('sweep') or st.get('intake'):
        return True
    batch = st.get('batch')
    if batch:
        k = Path(batch['kernel'])
        return any(not (k / 'requests' / (c['name'] + '.json')).exists()
                   and (k / 'responses' / (c['name'] + '.json')).exists()
                   for c in batch['calls'] if c.get('name') and c.get('done') is None)
    if st.get('state', 'idle') != 'idle':
        return True
    src = st.get('input', 'input.json')
    p = home / src if isinstance(src, str) else None
    if p is None:
        return True  # 指示詞或陣列：偷看不了，保守叫醒
    return p.is_dir() and any(n.endswith('.json') for n in os.listdir(p)) or p.is_file()


def main():
    agents = sorted(Path(sys.argv[1]).iterdir())
    kernel = Path(sys.argv[2])
    rounds = []
    for _ in range(20):
        t = time.perf_counter()
        due = sum(peek(h, kernel) for h in agents)
        rounds.append((time.perf_counter() - t) * 1000)
    ls = []
    for _ in range(20):
        t = time.perf_counter()
        os.listdir(kernel / 'responses')
        ls.append((time.perf_counter() - t) * 1000)
    med = statistics.median(rounds)
    print(json.dumps({'agents': len(agents), 'due': due, 'scan_ms_median': round(med, 2),
                      'per_agent_us': round(med * 1000 / len(agents), 1),
                      'listdir_K_responses_ms': round(statistics.median(ls), 3),
                      'K_responses_entries': len(os.listdir(kernel / 'responses'))}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
