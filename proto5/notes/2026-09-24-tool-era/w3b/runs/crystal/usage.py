"""訓練組那 20 句，領隊（和工人）每次問模型的用量原始紀錄：從 ~/tmp/w3b-crystal/myteam/members/*/log/usage.jsonl 抽出
訓練時間窗裡的行（第一句 ask 起、批准試驗 approve.txt 的第一句之前），原樣寫進 train-usage.jsonl（多一格 member），印加總。
時間窗：起＝out/route.log 第一行的 at；止＝out/approve.txt 之後那兩句的時間（團隊的 route.log 第 21 行的 at）。
"""
import datetime
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEAM = Path.home() / 'tmp' / 'w3b-crystal' / 'myteam'


def at(s):
    return datetime.datetime.fromisoformat(s)


def main():
    train = [json.loads(l) for l in (HERE / 'out' / 'route.log').read_text(encoding='utf-8').splitlines()]
    full = [json.loads(l) for l in (TEAM / 'team' / 'route.log').read_text(encoding='utf-8').splitlines()]
    lo = at(train[0]['at'])
    hi = at(full[len(train)]['at']) if len(full) > len(train) else None
    rows, total = [], {}
    for home in sorted((TEAM / 'members').iterdir()):
        f = home / 'log' / 'usage.jsonl'
        if not f.is_file():
            continue
        for line in f.read_text(encoding='utf-8').splitlines():
            r = json.loads(line)
            t = at(r['at'])
            if t < lo or (hi is not None and t >= hi):
                continue
            r = dict(r, member=home.name)
            rows.append(r)
            u = r.get('usage') or {}
            s = total.setdefault(home.name, {'calls': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'ms': 0})
            s['calls'] += 1
            s['prompt_tokens'] += u.get('prompt_tokens', 0)
            s['completion_tokens'] += u.get('completion_tokens', 0)
            s['ms'] += r.get('ms', 0)
    rows.sort(key=lambda r: r['at'])
    with open(HERE / 'train-usage.jsonl', 'w', encoding='utf-8') as out:
        for r in rows:
            out.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(json.dumps({'window': [str(lo), str(hi)], 'by_member': total}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
