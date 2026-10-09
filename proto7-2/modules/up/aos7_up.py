"""把既有公開指令組成第一次使用入口。"""
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

from aos7_up_status import P, alive, call, read, skill_count, watch, atomic, config, UpError


def run(path, *args, cwd=None):
    result = call(path, *args, cwd=cwd)
    if result.returncode:
        summary = (result.stderr or result.stdout).strip().splitlines()
        detail = summary[-1] if summary else f'退出 {result.returncode}'
        code = 3 if result.returncode == 3 else 1
        prefix = '不確定：' if code == 3 else ''
        raise UpError(code, f'{prefix}{path} 沒完成（{detail}）。已裝的留著，照原樣再跑一次會接續')
    return result.stdout


def preflight(node, model):
    previous = config(node)
    model = previous.get('model') if model is None else model
    gateway = 'llm.litellm' if model else 'llm.fake'
    grant_path = node / 'budget/llm/grant.json'
    grant = read(grant_path)
    if grant is not None and grant.get('gateway') != gateway:
        old = '假 AI' if grant.get('gateway') == 'llm.fake' else '真 AI'
        raise UpError(2, f'這個 node 已經用{old}開過帳，不能換。要換請另起一個 node，例如 aos7-up /tmp/aos/new')
    return previous, model, gateway, grant_path, grant


def prepare(node, model):
    previous, model, gateway, grant_path, grant = preflight(node, model)
    home = Path(os.environ.get('AOS7_WF_HOME', '~/repo/workflows')).expanduser()
    if not (node / 'AGENTS.md').is_file() and not (home / 'tools/wf-init.sh').is_file():
        raise UpError(1, '缺工作流模板。git clone git@github.com:justty32/workflows.git ~/repo/workflows 或設 AOS7_WF_HOME')
    if not (node / 'AGENTS.md').is_file():
        run('modules/wfnode/aos7-wfnode', 'init', node)
    settings = dict(v=1, node=str(node), house=str(node.parent), name=node.name,
                  you='you', mail_root=str(node.parent), model=model,
                  litellm_url=os.environ.get('AOS7_LITELLM_URL', previous.get('litellm_url', 'http://localhost:4000/v1')),
                  budget='budget/llm', holder='brain', gateway=gateway)
    atomic(node / '.aos/up.json', settings)
    if grant is None:
        grant = dict(v=1, grant='up-llm', budget='llm', holder='brain',
                     resource='llm.tokens', gateway=gateway, amount=10000000,
                     clock='completed_tock', until=1000000000, delegate=False)
        grant['from'] = 0
        atomic(grant_path, grant)
    if not (node / 'budget/llm/ledger.json').exists():
        run('packs/budget/bin/aos7-budget', 'init', 'budget/llm', cwd=node)
    skills = node / 'skills'
    skills.mkdir(exist_ok=True)
    for book in (P / 'modules/skills/library').iterdir():
        target = skills / book.name
        if not os.path.lexists(target):
            target.symlink_to(book, target_is_directory=True)
    run('modules/skills/aos7-skills', 'index', node)
    names = {t['name'] for t in read(node / '.aos/tasks.json', {'tasks': []})['tasks']}
    commands = {
        'budget-llm': ['python3', '-B', str(P / 'packs/budget/bin/aos7-budget'), 'ledger', 'budget/llm'],
        'brain': ['python3', '-B', str(P / 'modules/up/aos7-up'), 'brain', str(node)],
        'compact': ['python3', '-B', str(P / 'modules/compact/aos7-compact'), 'watch'],
    }
    for name, argv in commands.items():
        if name not in names:
            run('bin/aos7-ctl', 'add', node, json.dumps(dict(name=name, mode='keep', argv=argv)))
    (node.parent / 'you/inbox').mkdir(parents=True, exist_ok=True)
    run('bin/aos7-ctl', 'daemon', node.parent, 'register', node.name)
    return settings


def stop(node):
    if alive(node.parent):
        run('bin/aos7-ctl', 'daemon', node.parent, 'stop', '--kill')
        end = time.monotonic() + 30
        while alive(node.parent):
            if time.monotonic() >= end:
                raise UpError(3, f'不確定：心跳等了 30 秒還沒停，檔案都留著。請看 {node.parent}/.aosd/up-daemon.log 再重試 stop')
            time.sleep(.1)
    print('心跳停了')
    print(f'檔案都留著：{node}、{node.parent}/you；要全清就刪這兩個資料夾（{node.parent}/.aosd 是心跳的紀錄，房子裡沒別的 node 也可刪）')
    return 0


def node_round(node):
    data = read(node / '.aos/round.json', {})
    value = data.get('round') if isinstance(data, dict) else None
    return value if type(value) is int else 0


def up(node, model, detached):
    # Validate before creating even the lock file.
    preflight(node, model)
    before = node_round(node)
    (node / '.aos').mkdir(parents=True, exist_ok=True)
    daemon = None
    handed = False
    try:
        with (node / '.aos/up.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            settings = prepare(node, model)
            if not alive(node.parent):
                log = node.parent / '.aosd/up-daemon.log'
                with log.open('a') as stream:
                    daemon = subprocess.Popen(['python3', '-B', str(P / 'bin/aos7-daemon'), str(node.parent)],
                        stdout=stream, stderr=stream, start_new_session=True)
                end = time.monotonic() + 10
                while not alive(node.parent):
                    if daemon.poll() is not None or time.monotonic() > end:
                        raise UpError(1, f'心跳起不來。請看 {log} 後重跑')
                    time.sleep(.02)
            end = time.monotonic() + 15
            while not (node_round(node) >= 1 and node_round(node) > before):
                if time.monotonic() >= end:
                    raise UpError(3, f'不確定：15 秒內沒看到 {node.name} 被叫醒，已裝的檔案留著。照原樣再跑 aos7-up {node} 會接續')
                time.sleep(.05)
        ai = f'AI：{settings["model"]}' if settings['model'] else '假 AI（要真的加 --model）'
        print(f'{node.name} 起好了：工作簿 ✓ 信箱 ✓ 技能 {skill_count(node)} 本 ✓ {ai}', flush=True)
        print(f"另開一個終端機問它：aos7-up ask {node} '一句話'", flush=True)
        print(f'看狀態：aos7-up status {node}　停：' + (f'aos7-up stop {node}' if detached else 'Ctrl-C'), flush=True)
        handed = True
        if detached:
            return 0
        try:
            watch(node, daemon)
        except KeyboardInterrupt:
            pass
    finally:
        old_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
        old_term = signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            if daemon is not None and (not handed or not detached):
                if daemon.poll() is None:
                    daemon.send_signal(signal.SIGINT)
                try:
                    daemon.wait(30)
                except subprocess.TimeoutExpired:
                    daemon.kill()
                    daemon.wait()
                    raise UpError(3, f'不確定：心跳沒在 30 秒內停，已強制結束；它的工作可能還在跑。再跑一次 aos7-up {node} 會接手並收掉舊的') from None
                if handed:
                    print(f'心跳停了；檔案都留著，再跑 aos7-up {node} 就接上', flush=True)
            elif handed and not detached:
                print(f'只停了觀看；心跳還在跑，停它用 aos7-up stop {node}', flush=True)
        finally:
            signal.signal(signal.SIGINT, old_int)
            signal.signal(signal.SIGTERM, old_term)
    return 0


def main(argv=None):
    from aos7_up_cli import main as entry
    return entry(argv)
