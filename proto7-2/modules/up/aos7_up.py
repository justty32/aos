"""把既有公開指令組成第一次使用入口。"""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from aos7_up_status import P, alive, call, read, skill_count, watch, atomic, config, UpError, cleanup_hint


def run(path, *args, cwd=None):
    result = call(path, *args, cwd=cwd)
    if result.returncode:
        summary = (result.stderr or result.stdout).strip().splitlines()
        detail = summary[-1] if summary else '工具沒完成'
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
        old = '練習用的 AI' if grant.get('gateway') == 'llm.fake' else '真 AI'
        raise UpError(2, f'這個 node 已經用{old}起過，不能換。要換請另起一個 node，例如 aos7-up /tmp/aos/new')
    return previous, model, gateway, grant_path, grant


def prepare(node, model, beat=None):
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
    # 節拍（ADVANCED「心跳節拍」）：給過才有欄位，沒給沿用 up.json 舊值；從沒給過就不碰 timeline（核心預設 1 秒固定）
    for key in ('interval_ms', 'early_tock'):
        if key in (beat or {}):
            settings[key] = beat[key]
        elif key in previous:
            settings[key] = previous[key]
    atomic(node / '.aos/up.json', settings)
    changed = sync_timeline(node, settings)
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
        'brain': ['python3', str(P / 'modules/up/aos7-up'), 'brain', str(node)],  # 凍結 argv
        'compact': ['python3', '-B', str(P / 'modules/compact/aos7-compact'), 'watch'],
        'routines': ['python3', '-B', str(P / 'modules/routines/aos7-routines')],
    }
    for name, argv in commands.items():
        if name not in names:
            run('bin/aos7-ctl', 'add', node, json.dumps(dict(name=name, mode='keep', argv=argv)))
    for box in (node / 'events', node.parent / 'you/inbox', node.parent / 'you/events'):
        box.mkdir(parents=True, exist_ok=True)
    run('bin/aos7-ctl', 'daemon', node.parent, 'register', node.name)
    if alive(node.parent) and (changed or settings.get('interval_ms', 1000) > 1000):
        # 已在跑的心跳：叫醒好讓新節拍馬上生效、長間隔也不必等滿一拍才看到醒來；沒叫成只是慢一點
        call('bin/aos7-ctl', 'daemon', node.parent, 'wake', node.name)
    return settings


def sync_timeline(node, settings):
    """把 up.json 的節拍欄寫進核心的 timeline.json（其他欄保留）。回傳有沒有改。"""
    beat = {k: settings[k] for k in ('interval_ms', 'early_tock') if k in settings}
    if not beat:
        return False
    path = node / '.aos/timeline.json'
    try:
        current = json.loads(path.read_text())
    except FileNotFoundError:
        current = {}
    except ValueError:
        current = {}   # 核心也當它壞了、全用預設；照 up.json 重寫
    if not isinstance(current, dict):
        current = {}
    want = dict(current, **beat)
    if want == current:
        return False
    atomic(path, want)
    return True


def stop(node):
    if not alive(node.parent):
        print('心跳已經停了，不用再停')
    else:
        _halt(node)
    if node.is_dir():
        print(cleanup_hint(node))
    return 0


def _halt(node):
    run('bin/aos7-ctl', 'daemon', node.parent, 'stop', '--kill')
    end = time.monotonic() + 30
    while alive(node.parent):
        if time.monotonic() >= end:
            raise UpError(3, f'不確定：心跳等了 30 秒還沒停，檔案都留著。請看 {node.parent}/.aosd/up-daemon.log 再重試 stop')
        time.sleep(.1)
    print('心跳停了')


def node_round(node):
    data = read(node / '.aos/round.json', {})
    value = data.get('round') if isinstance(data, dict) else None
    return value if type(value) is int else 0


def up(node, model, detached, beat=None):
    # Validate before creating even the lock file.
    preflight(node, model)
    before = node_round(node)
    (node / '.aos').mkdir(parents=True, exist_ok=True)
    daemon = None
    handed = False
    try:
        with (node / '.aos/up.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            settings = prepare(node, model, beat)
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
            wait = 15 + -(-max(settings.get('interval_ms', 1000) - 1000, 0) // 1000)   # 長間隔多等一拍；預設照舊 15 秒
            end = time.monotonic() + wait
            while not (node_round(node) >= 1 and node_round(node) > before):
                if time.monotonic() >= end:
                    raise UpError(3, f'不確定：{wait} 秒內沒看到 {node.name} 被叫醒，已裝的檔案留著。照原樣再跑 aos7-up {node} 會接續')
                time.sleep(.05)
        ai = f'AI：{settings["model"]}' if settings['model'] else '練習用的 AI'
        # 心跳已起、node 已醒：先記交棒，三行 print 中途被中斷也照交棒後收尾
        handed = True
        try:
            print(f'{node.name} 起好了：工作簿 ✓ 信箱 ✓ 技能 {skill_count(node)} 本 ✓ {ai}', flush=True)
            print(f"另開一個終端機問它：aos7-up ask {node} '一句話'", flush=True)
            print(f'看狀態：aos7-up status {node}　停：' + (f'aos7-up stop {node}' if detached else 'Ctrl-C'), flush=True)
            if detached:
                return 0
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
