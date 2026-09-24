"""實驗 C：kernel 帳本整份存一次要多久（proto5 的 kernel 每收一則回音、每派一件都存一次）。

拿實驗 B（300 個在等的 agent）結束時的真帳本當樣本，照「一個 agent＝一筆 tick 行程＋一筆在排隊的 llm once」
複製成 N 個 agent 的大小，量 aos_home.write_state（kernel 真的在用的那支）與讀一次的時間。

用法：python3 c_ledger.py SAMPLE_K_STATE_JSON OUT_DIR
"""
import copy
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / 'proto5' / 'lib'))
import aos_home  # noqa: E402


def scaled(sample, n):
    agents = [k for k in sample['procs'] if k.startswith('agent-')]
    onces = [k for k in sample['procs'] if not k.startswith('agent-')]
    st = copy.deepcopy(sample)
    st['procs'], st['queue'] = {}, []
    for i in range(n):
        a = copy.deepcopy(sample['procs'][agents[i % len(agents)]])
        a['target'] = a['target'].replace(agents[i % len(agents)][6:], 'x%05d' % i)
        st['procs']['agent-x%05d' % i] = a
        st['queue'].append('agent-x%05d' % i)
        o = copy.deepcopy(sample['procs'][onces[i % len(onces)]])
        st['procs']['aw-x%05d-1' % i] = o
        st['queue'].append('aw-x%05d-1' % i)
    return st


def main():
    sample = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for n in (100, 300, 1000, 3000):
        st = scaled(sample, n)
        times = []
        for _ in range(20):
            t = time.perf_counter()
            aos_home.write_state(out, st)
            times.append((time.perf_counter() - t) * 1000)
        reads = []
        for _ in range(20):
            t = time.perf_counter()
            aos_home.read_state(out)
            reads.append((time.perf_counter() - t) * 1000)
        rows.append({'agents': n, 'ledger_kb': round((out / 'state.json').stat().st_size / 1024),
                     'save_ms': round(statistics.median(times), 2), 'read_ms': round(statistics.median(reads), 2)})
    print(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
