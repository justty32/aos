#!/usr/bin/env python3
"""第三波 W3-2 compact：機械版 vs --summarize 真跑對照（重建第一波 T4 那套，notes/2026-09-24-tool-era-memory.md §3）。

用法（repo 根目錄）：
  python3 proto5/notes/2026-09-24-tool-era/w3b/runs/compact/live.py [次數=5] [資料夾=~/tmp/w3b-compact]
真跑一律 LiteLLM http://localhost:4000/v1 的 deepseek-chat（不碰 LM Studio／ollama）。
一套 daemon＋kernel；每一次都用全新的 agent 家（init＋tools add base），跑完 stop，最後 aos down。
每次：①read 40 行的 long.txt ②記住芒果 ③④⑤三段長自我介紹 → compact（keep 1、上限＝「①②都封存」的最大值）
→ 問 long.txt 幾行 → 問最喜歡的水果。結果一次一行寫進 results.jsonl（同資料夾），摘要原文寫進同資料夾的 digests/。
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
CLI = REPO / 'proto5' / 'cli'
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
W = Path(os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else '~/tmp/w3b-compact'))
ENV = dict(os.environ, PATH='%s:%s' % (CLI, os.environ['PATH']), AOS_DAEMON_HOME=str(W / 'D'),
           AOS_KERNEL_HOME=str(W / 'K'), AOS_LLM_CONFIG=str(W / 'llm.json'), PYTHONDONTWRITEBYTECODE='1')

INTROS = [
    '我來做個很長的自我介紹，你聽完回一兩句就好。我叫阿明，在台中出生長大，小時候住在一條老街上，隔壁是一家開了四十年的麵店，'
    '每天放學都會聞到滷肉的味道。國中的時候迷上天文，常常半夜爬上頂樓看星星，還自己用紙箱做過一台很爛的望遠鏡。'
    '高中讀的是自然組，數學不錯但物理常常考不及格，老師說我太愛猜答案。大學考上資訊工程，第一次寫程式是用 C 寫井字遊戲，'
    '寫了三天才讓電腦不會走到已經有棋子的格子。畢業後在一家做物流系統的公司待了五年，每天處理倉庫的排程和貨車的路線，'
    '最常加班的時候是雙十一前後，整個辦公室都睡在公司。',
    '再講一段我的興趣，一樣回一兩句就好。我週末最喜歡騎腳踏車，從家裡沿著河堤一路騎到海邊，來回大概六十公里，'
    '中途會在一家小咖啡店停下來，老闆是退休的船員，常常講他以前跑遠洋的故事，什麼在南非遇到大浪、在阿根廷港口吃到超大塊的牛排。'
    '除了騎車，我也喜歡做菜，拿手菜是紅燒牛肉和三杯雞，最近在學做義大利麵，失敗了好幾次，麵條不是太軟就是太硬。'
    '我還養了一隻橘貓，叫做胖虎，很愛睡在鍵盤上，常常我一離開電腦，回來就發現文件裡多了一整排的字母。'
    '晚上睡前我會看半小時的書，最近在看一本講古代航海的歷史書，講人怎麼靠星星和海流找路。',
    '最後一段，講我最近的工作和計畫，一樣簡短回應就好。我現在換到一家做農業感測器的新創，負責寫後端的程式，'
    '感測器裝在田裡量土壤濕度和溫度，每十分鐘傳一次資料上來，我要把這些資料整理好給農夫看。'
    '最難的是田裡訊號很差，資料常常斷斷續續，要想辦法補齊。明年我想學日文，因為公司可能要去日本推產品，'
    '也想去北海道看看那邊的農場是怎麼做的。另外我在存錢，想買一台好一點的相機，把騎車看到的風景拍下來，'
    '順便把胖虎各種奇怪的睡姿都記錄下來，做成一本小相簿送給我媽，她很喜歡那隻貓。',
]
Q_LINES = '剛才 long.txt 幾行？不要再讀檔、不要用工具，照你的記憶回答；不記得就說不記得。'
Q_FRUIT = '我最喜歡什麼水果？不要用工具，照你的記憶回答。'


def sh(*args, check=True, timeout=600):
    p = subprocess.run(list(args), env=ENV, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError('%s 退 %d：%s %s' % (' '.join(args), p.returncode, p.stdout[-500:], p.stderr[-500:]))
    return p


def say(home, text):
    for attempt in range(3):
        p = sh('aos-agent', 'say', text, '--target', str(home), '--wait', check=False)
        if p.returncode == 0:
            return p.stdout.strip()
        time.sleep(2)
    raise RuntimeError('say 失敗：%s' % p.stderr[-500:])


def context(home):
    return json.loads(sh('aos-agent', 'context', '--json', '--target', str(home)).stdout)


def usage_rows(home):
    path = home / 'log' / 'usage.jsonl'
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()] if path.exists() else []


def idle(home):
    for _ in range(60):
        st = json.loads((home / 'state.json').read_text(encoding='utf-8'))
        if st.get('state') == 'idle' and st.get('batch') is None and st.get('intake') is None:
            return
        time.sleep(0.5)
    raise RuntimeError('等不到 idle')


def pick_limit(home):
    """keep 1 時「①②兩輪都封存」的最大上限（從記憶 token 往下每 20 試 dry-run）。"""
    tokens = context(home)['history']['tokens']
    for limit in range(tokens, 99, -20):
        p = sh('aos-agent', 'compact', '--keep-rounds', '1', '--max-tokens', str(limit), '--dry-run', '--json',
               '--target', str(home))
        rounds = json.loads(p.stdout.strip().splitlines()[-1])['rounds']
        if len(rounds) >= 2 and rounds[0]['action'] == 'seal' and rounds[1]['action'] == 'seal':
            return limit
    raise RuntimeError('找不到封存①②的上限')


def one(mode, i):
    home = W / ('%s-%d' % (mode, i))
    sh('aos-agent', 'init', '--target', str(home))
    sh('aos-agent', 'tools', 'add', 'base', '--target', str(home))
    info = json.loads((home / 'info.json').read_text(encoding='utf-8'))
    info['compact'] = False          # 關掉 tick 自動壓縮：只看人跑的那一次
    (home / 'info.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    (home / 'workspace').mkdir(exist_ok=True)
    (home / 'workspace' / 'long.txt').write_text(''.join('這是第 %d 行，內容是 item-%03d\n' % (k, k * 7)
                                                         for k in range(1, 41)), encoding='utf-8')
    sh('aos-agent', 'start', '--target', str(home))
    row = {'mode': mode, 'run': i}
    try:
        row['a1'] = say(home, '用 read 工具讀 long.txt，告訴我總共幾行。')
        row['a2'] = say(home, '記住：我最喜歡的水果是芒果。只要回「記住了」。')
        for text in INTROS:
            say(home, text)
        idle(home)
        before = context(home)
        row['before_tokens'] = before['history']['tokens']
        limit = pick_limit(home)
        row['limit'] = limit
        args = ['aos-agent', 'compact', '--keep-rounds', '1', '--max-tokens', str(limit), '--target', str(home)]
        if mode == 'sum':
            args.insert(2, '--summarize')
        t0 = time.monotonic()
        p = sh(*args)
        row['compact_s'] = round(time.monotonic() - t0, 2)
        row['compact_out'] = p.stdout.strip()
        ev = [json.loads(l) for l in (home / 'log' / 'events.jsonl').read_text(encoding='utf-8').splitlines()
              if '"compact"' in l][-1]
        row['summarize'] = ev.get('summarize')
        after = context(home)
        row['after_tokens'] = after['history']['tokens']
        hist = json.loads((home / 'prompts' / 'history.json').read_text(encoding='utf-8'))
        sealed = [m['content'] for m in hist if m['role'] == 'user' and m['content'].startswith('[aos 已封存')]
        (HERE / 'digests').mkdir(exist_ok=True)
        (HERE / 'digests' / ('%s-%d.txt' % (mode, i))).write_text('\n\n'.join(sealed), encoding='utf-8')
        row['digest_bytes'] = [len(s.encode('utf-8')) for s in sealed]
        if mode == 'sum':   # 同一份原文的機械版摘要（純函式重算），好對照模型有沒有編東西
            sys.path.insert(0, str(REPO / 'proto5' / 'lib'))
            import aos_agent_compact
            archive = sorted((home / 'prompts' / 'archive').glob('*.json'))[0]
            mech = aos_agent_compact.plan(json.loads(archive.read_text(encoding='utf-8')), keep_rounds=1,
                                          max_tokens=limit, archive=os.path.relpath(archive, home))['history']
            (HERE / 'digests' / ('%s-%d.mech.txt' % (mode, i))).write_text(
                '\n\n'.join(m['content'] for m in mech if m['content'].startswith('[aos 已封存')), encoding='utf-8')
        n = len(usage_rows(home))
        row['q_lines'] = say(home, Q_LINES)
        rows = [r for r in usage_rows(home)[n:] if not str(r.get('batch') or '').startswith('compact-summarize')]
        row['first_prompt_tokens'] = (rows[0].get('usage') or {}).get('prompt_tokens') if rows else None
        row['q_fruit'] = say(home, Q_FRUIT)
        row['ok_lines'] = bool(re.search(r'(?<!\d)40(?!\d)', row['q_lines']))
        row['ok_fruit'] = '芒果' in row['q_fruit']
    except Exception as exc:          # 記下來、下一次照跑
        row['error'] = str(exc)[:500]
    finally:
        sh('aos-agent', 'stop', '--target', str(home), check=False)
    return row


def main():
    W.mkdir(parents=True, exist_ok=True)
    (W / 'llm.json').write_text(json.dumps({'_metainfo': {'_type': 'llm_config', '_version': 1}, 'models': {
        'default': {'endpoint': 'http://localhost:4000/v1', 'model': 'deepseek-chat'}}}), encoding='utf-8')
    (W / 'kernel.json').write_text(json.dumps({'pools': {'default': {'count': 2}, 'llm': {
        'count': 1, 'envs': {'AOS_LLM_CONFIG': str(W / 'llm.json')}}}}), encoding='utf-8')
    if not (W / 'K').exists():
        sh('aos-kernel', 'init', '--config', str(W / 'kernel.json'))
    sh('aos', 'up')
    out = HERE / 'results.jsonl'
    try:
        for i in range(1, N + 1):
            for mode in ('mech', 'sum'):
                row = one(mode, i)
                with out.open('a', encoding='utf-8') as f:
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
                print(json.dumps({k: row.get(k) for k in ('mode', 'run', 'ok_lines', 'ok_fruit', 'after_tokens',
                                                          'first_prompt_tokens', 'compact_s', 'error')},
                                 ensure_ascii=False), flush=True)
    finally:
        sh('aos', 'down', check=False)


if __name__ == '__main__':
    main()
