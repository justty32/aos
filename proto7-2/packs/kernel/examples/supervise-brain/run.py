"""監督 brain 範例：假 AI 卡住不回 → 監督者（kernel）先寄信給你、再 kill 那個 run → brain 重起從 task.json 接續。

從 repo 根跑：python3 proto7-2/packs/kernel/examples/supervise-brain/run.py [--house DIR] [--keep]
不連網、不花錢，約 1 分鐘。房子預設開在 /tmp/aos-kernel-demo.*，跑完停心跳並刪掉（--keep 留著看）。

情境（照 blueprint-kernel1 §6，頂層 10-09 修正）：
1. aos7-up 起 bob（假 AI），`aos7-ctl add` 裝 kernel keep 任務，設定照本資料夾 kernel.json（預設門檻 6／12 回合）。
2. 寄「做 5 回合的整理」；bob 做到第 2 步後，把 up.json 的 fake_delay 調成 3600 秒——假 AI 不再回，
   brain 卡在等 AI、不再寫 task.json（每回合都回「繼續」的 brain 不會停在同一步，它自己的「3 回合沒進展」也輪不到）。
3. 監督者：停滿 6 回合寄一封 NEEDS-USER 給 you，停滿 12 回合 kill 綁當時的 run（回條 ok）。
4. keep 重起 brain：它從 task.json 的同一步接續、不重問 AI（假 AI 受理次數仍是 1）。kill 後把 up.json 的
   deadline 調成 1 秒，示範 brain 不再等那筆不確定的 AI、回你「卡住」結案（不調就會等滿 600 秒，
   這段期間同信不再寄通知；再收掉前會等更久，同一步最多收掉 3 次）。
5. 還原 up.json，SIGKILL 監督者一次（keep 重起它，brain 照常），再寄正常的「做 4 回合的介紹」：
   一回合一步、照常回信，監督者零動作。
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
PACK = HERE.parents[1]
TOP = PACK.parents[1]
UP = TOP / 'modules/up/aos7-up'
MAIL = TOP / 'modules/mail/aos7-mail'
CTL = TOP / 'bin/aos7-ctl'
KERNEL = PACK / 'bin/aos7-kernel'
sys.path.insert(0, str(TOP / 'modules/mail'))
from aos7_mail import letter  # noqa: E402


class Fail(Exception):
    pass


def sh(*args):
    return subprocess.run([sys.executable, '-B', *map(str, args)], capture_output=True, text=True, timeout=120)


def load(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def wait(what, cond, limit=90):
    end = time.time() + limit
    while time.time() < end:
        got = cond()
        if got:
            return got
        time.sleep(0.1)
    raise Fail(f'等了 {limit} 秒還沒看到：{what}')


def say(msg):
    print(msg, flush=True)


def main():
    ap = argparse.ArgumentParser(description='監督 brain 範例（假 AI，不花錢）')
    ap.add_argument('--house', help='房子資料夾（預設 /tmp/aos-kernel-demo.*，要是空的或不存在）')
    ap.add_argument('--keep', action='store_true', help='跑完不刪房子')
    a = ap.parse_args()
    house = Path(a.house).resolve() if a.house else Path(tempfile.mkdtemp(prefix='aos-kernel-demo.'))
    existing = bool(a.house and house.exists())
    if existing and (not house.is_dir() or any(house.iterdir())):
        print(f'run.py: {house} 已存在且不是空目錄。請換一個 --house，原目錄保留', file=sys.stderr)
        return 2
    house.mkdir(parents=True, exist_ok=True)
    node = house / 'bob'
    started = False
    try:
        p = sh(UP, node, '-d')
        if p.returncode:
            raise Fail('aos7-up 起不來：' + (p.stderr.strip() or p.stdout.strip()))
        started = True
        say(f'1. bob 起好了（假 AI，不連網、不花錢）：{node}')
        code = check(house, node)
    except Fail as e:
        say(f'沒做到：{e}')
        code = 1
    finally:
        if started:
            sh(UP, 'stop', node)
        if a.keep:
            say(f'房子留著：{house}')
        elif not existing:
            shutil.rmtree(house, ignore_errors=True)
        else:
            for child in house.iterdir():
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
    return code


def check(house, node):
    slots = node / '.aos/tasks'
    kslot, bslot = slots / 'kernel', slots / 'brain'
    cfg = node / '.aos/up.json'

    def up_set(**kv):
        c = load(cfg)
        for k, v in kv.items():
            if v is None:
                c.pop(k, None)
            else:
                c[k] = v
        tmp = cfg.with_suffix('.tmp')
        tmp.write_text(json.dumps(c, ensure_ascii=False))
        os.replace(tmp, cfg)

    def mails():
        out = []
        for f in sorted((house / 'you/inbox').rglob('*.md')):
            try:
                out.append(letter(f))
            except Exception:
                pass
        return out

    def done(op, result=None):
        s = load(kslot / 'state.json') or {}
        return [d for d in s.get('done', []) if d.get('op') == op and (result is None or d.get('result') == result)]

    def send(title):
        body = house / 'body.txt'
        body.write_text(title + '\n')
        p = sh(MAIL, 'send', 'you', 'bob', 'REQUEST', title, body, '--root', house)
        if p.returncode:
            raise Fail('寄信失敗：' + p.stderr.strip())
        return json.loads(p.stdout)['id']

    def reply(ident):
        return next((m for m in mails() if m.get('re') == ident and m.get('from') == 'bob'), None)

    (node / 'kernel').mkdir(exist_ok=True)
    shutil.copy(HERE / 'kernel.json', node / 'kernel/kernel.json')
    item = dict(name='kernel', mode='keep', argv=['python3', str(KERNEL), 'run'])
    p = sh(CTL, 'add', node, json.dumps(item), '--by', 'supervise-brain-example')
    if p.returncode:
        raise Fail('aos7-ctl add 沒成功：' + (p.stderr.strip() or p.stdout.strip()))
    wait('監督者起來', lambda: (kslot / 'state.json').exists())
    say('2. 替 bob 裝好監督者：' + sh(KERNEL, 'status', node).stdout.strip())

    a = send('做 5 回合的整理')
    task = wait('bob 做到第 2 步', lambda: (lambda t: t if t and t.get('id') == a and t.get('step', 0) >= 2 else None)(
        load(node / 'brain/task.json')))
    up_set(fake_delay=3600, deadline=600)
    say(f'3. 寄「做 5 回合的整理」給 bob；做到第 {task["step"]} 步時，假 AI 故意不再回——bob 卡住了')

    note = wait('監督者寄信', lambda: done('notify', 'sent'), 60)[0]
    say(f'4. 卡了 {note["basis"]["age"]} 回合：監督者寄一封信給你（要你決定）：「{note.get("text")}」')
    kill = wait('監督者 kill', lambda: done('kill', 'ok'), 60)[0]
    up_set(deadline=1)
    say(f'5. 卡了 {kill["basis"]["age"]} 回合：監督者把卡住的 bob 收掉，bob 會自己重新起來')

    wait('brain 重起', lambda: (lambda b: b if b and b.get('run') != kill['run'] else None)(load(bslot / 'birth.json')))
    again = load(node / 'brain/task.json')
    if not again or again.get('id') != a:
        raise Fail(f'brain 重起後 task.json 不是同一封信：{again}')
    step = again['step']
    blocked = wait('卡住那封信結案', lambda: reply(a), 60)
    sends = (load(node / 'llmcall/fake-remote.json') or {}).get('sends', {})
    cid = a if step == 1 else f'{a}-s{step}'
    if sends.get(cid) != 1:
        raise Fail(f'第 {step} 步那筆 AI 被問了 {sends.get(cid)} 次（應該 1 次）')
    say(f'6. bob 回來了：從第 {step} 步接著做，沒有再問一次 AI；'
        f'等不到 AI，就回信跟你說「{blocked["title"]}」')

    up_set(fake_delay=None, deadline=None)
    pid = load(kslot / 'pid.json')
    try:
        os.killpg(pid['pgid'], signal.SIGKILL)
    except (ProcessLookupError, TypeError, KeyError):
        raise Fail(f'找不到監督者的程序：{pid}') from None
    b = send('做 4 回合的介紹')
    wait('監督者被殺後重起', lambda: (lambda q: q and q.get('run') != pid['run'])(load(kslot / 'pid.json')))
    ok = wait('正常那封信回信', lambda: reply(b), 60)
    time.sleep(3)
    notes = [m for m in mails() if m.get('from') == 'kernel']
    kills = done('kill')
    s = load(kslot / 'state.json')
    if ok['status'] != 'DONE':
        raise Fail(f'正常那封信回 {ok["status"]}：{ok["title"]}')
    if len(notes) != 1 or len(kills) != 1 or s['pending'] or s.get('last_error'):
        raise Fail(f'監督者多做了事：信 {len(notes)} 封、kill {len(kills)} 次、在途 {s["pending"]}、錯 {s.get("last_error")}')
    say('7. 強制關掉監督者一次（它會自己重新起來，bob 不受影響），再寄正常的「做 4 回合的介紹」：bob 照常回信，監督者什麼都沒做')
    say('   監督者現在：' + sh(KERNEL, 'status', node).stdout.strip())
    letters = next((l for l in sh(UP, 'status', node).stdout.splitlines() if l.startswith('信：')), '')
    say('   bob 的狀態：' + letters)
    say('全部做到：監督者寄信 1 封、收掉 1 次；bob 接著做、沒重問；正常的信沒被打擾')
    return 0


if __name__ == '__main__':
    sys.exit(main())
