"""從真 brain 抽 fixture：起假 AI node（aos7-up -d），寄兩封信，中途連同 llmcall 一起 SIGKILL brain 一次，
每個來源回合記一筆 {completed_tock, run, task}（task＝brain/task.json 原文；沒有＝null；壞＝"bad"）。不花錢、不連網。

從 repo 根跑：systemd-run --user --scope -p TasksMax=300 python3 -B proto7-2/packs/kernel/tests/fixtures/brain/capture.py OUT.jsonl
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

TOP = Path(__file__).resolve().parents[5]
UP, MAIL = TOP / 'modules/up/aos7-up', TOP / 'modules/mail/aos7-mail'
LETTERS = ['會議紀錄整理，分 4 回合做：決議、待辦、風險、總結各一回合', '週報一直沒進展，請接著寫']


def sh(*args):
    return subprocess.run([sys.executable, '-B', *map(str, args)], capture_output=True, text=True)


def read(path):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return 'bad'


def main(out):
    house = Path(tempfile.mkdtemp(prefix='aos-kr1-capture.'))
    node = house / 'bob'
    try:
        assert sh(UP, node, '-d').returncode == 0
        cfg = json.loads((node / '.aos/up.json').read_text())
        (node / '.aos/up.json').write_text(json.dumps(dict(cfg, fake_delay=1.5, deadline=6)))
        for i, title in enumerate(LETTERS):
            body = house / f'body-{i}.md'
            body.write_text('（fixture 用）\n')
            assert sh(MAIL, 'send', 'you', 'bob', 'REQUEST', title, body, '--root', house).returncode == 0
        rows, last, killed, t0 = [], None, False, time.time()
        while time.time() - t0 < 240:
            rnd = read(node / '.aos/round.json')
            if isinstance(rnd, dict) and isinstance(rnd.get('round'), int):
                ct = rnd['round'] - 1 if rnd.get('open') else rnd['round']
                birth = read(node / '.aos/tasks/brain/birth.json')
                row = dict(completed_tock=ct, run=birth.get('run') if isinstance(birth, dict) else None,
                           task=read(node / 'brain/task.json'))
                if ct != last:
                    rows.append(row)
                    last = ct
                task = row['task']
                if not killed and isinstance(task, dict) and task.get('step') == 2:
                    pids = subprocess.run(['pgrep', '-f', str(node / 'brain')], capture_output=True, text=True).stdout.split()
                    pids += subprocess.run(['pgrep', '-f', f'brain {node}'], capture_output=True, text=True).stdout.split()
                    for pid in set(pids):
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    killed = True
                    rows.append(dict(event='SIGKILL brain', pids=len(set(pids)), completed_tock=ct))
            seen = [r['task']['id'] for r in rows if isinstance(r.get('task'), dict)]
            if len(set(seen)) >= 2 and all(r.get('task') is None for r in rows[-5:]):
                break   # 兩封都做過、task.json 連 5 個回合都不在＝兩封都結案
            time.sleep(0.2)
        Path(out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    finally:
        sh(UP, 'stop', node)
        shutil.rmtree(house, ignore_errors=True)


if __name__ == '__main__':
    main(sys.argv[1])
