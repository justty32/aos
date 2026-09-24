"""T-crystal 真跑：訓練組。把 sentences.json 的 train 一句一句 aos-team ask 給真團隊，等領隊處理完（開了單／回信／發問，
或 150 秒沒動靜）才送下一句，這樣「哪句開出哪張單」對得清楚。

用法（先 . ~/tmp/w3b-crystal/env.sh，團隊已 start、worker 可停）：
  python3 train.py            # 建專案檔、逐句送
結果：團隊資料夾自己的 route.log、post/sent、tasks；這裡另寫 train-log.jsonl（每句送出時刻、等了幾秒、看到什麼）。
"""
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
TEAM = Path(os.environ['AOS_TEAM_HOME'])
PROJ = TEAM.parent / 'proj'


def seed_project():
    PROJ.mkdir(exist_ok=True)
    for n in 'abcd':
        (PROJ / (n + '.md')).write_text('# %s\n\n內容 %s\n' % (n, n), encoding='utf-8')
    for n in 'efgh':
        (PROJ / (n + '.md')).write_text(''.join('第 %d 行\n' % i for i in range(1, 7)), encoding='utf-8')
    for n, k in (('poem', 4), ('story', 7), ('list', 3), ('notes', 5)):
        (PROJ / (n + '.md')).write_text(''.join('%s 第 %d 行\n' % (n, i) for i in range(1, k + 1)), encoding='utf-8')


def snapshot():
    t = TEAM / 'team'
    sent = [p.name for p in (t / 'post' / 'sent').glob('*.json')]
    return {'tasks': len(list((t / 'tasks').glob('t-*.json'))),
            'lead_out': len([s for s in sent if s.split('.')[0].endswith('-lead')]),
            'wait': len(list((t / 'wait-user').glob('*.json')))}


def main():
    seed_project()
    data = json.loads((HERE / 'sentences.json').read_text(encoding='utf-8'))
    log = open(HERE / 'train-log.jsonl', 'a', encoding='utf-8')
    for s in data['train']:
        before = snapshot()
        t0 = time.time()
        r = subprocess.run(['aos-team', 'ask', s], capture_output=True, text=True)
        seen = None
        while time.time() - t0 < 150:
            time.sleep(3)
            now = snapshot()
            if now != before:
                time.sleep(12)          # 領隊一次可能開不只一張，多等一下
                seen = snapshot()
                break
        rec = {'text': s, 'ask_rc': r.returncode, 'ask_out': r.stdout.strip() + r.stderr.strip(),
               'waited_s': round(time.time() - t0, 1), 'before': before, 'after': seen or snapshot()}
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        log.write(json.dumps(rec, ensure_ascii=False) + '\n')
        log.flush()


if __name__ == '__main__':
    main()
