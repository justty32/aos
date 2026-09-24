"""kernel 啟動前的唯讀檢查；不解任意 inst 指示詞、不啟動工具或模型。"""
import os
from pathlib import Path
import shutil

import aos_agent_info
import aos_daemon
import aos_home
import aos_llm_call
from aos_agent_home import AgentError

COMMANDS = ('aos-exec', 'aos-cpu', 'aos-kernel', 'aos-agent', 'aos-llm')
SHELL_NOTE = '（目前 shell 的 PATH；daemon 以開它那一刻的 PATH 為準）'
ERRORS = (aos_home.HomeError, AgentError, OSError, ValueError, TypeError)


def daemon_environment(daemon, alive):
    """flock 證實活著才採用 /proc；無法讀就清楚標示 shell fallback。"""
    if alive:
        try:
            pid = aos_daemon.read_state(daemon).get('pid')
            if type(pid) is int and pid > 0:
                raw = Path('/proc/%d/environ' % pid).read_bytes()
                env = dict(os.fsdecode(item).split('=', 1) for item in raw.split(b'\0') if b'=' in item)
                return env, '（daemon 的 PATH）'
        except ERRORS:
            pass
    return dict(os.environ), SHELL_NOTE


def _literal(value, env):
    if isinstance(value, str):
        return value, True
    if isinstance(value, dict) and set(value) == {'$env'} and isinstance(value['$env'], str):
        return env.get(value['$env']), True
    return None, False


class Checks:
    def __init__(self):
        self.bad = False

    def report(self, level, item, message):
        self.bad |= level == 'bad'
        print('%-4s %s: %s' % (level, item, str(message).replace('\n', ' ')))

    def path(self, path, note, item='path'):
        missing = [name for name in COMMANDS if shutil.which(name, path=path) is None]
        cli = Path(__file__).resolve().parents[1] / 'cli'
        message = ('找不到 %s；開 daemon 前 export PATH=%s:$PATH' % (', '.join(missing), cli)
                   if missing else '五支 CLI 都找得到')
        self.report('bad' if missing else 'ok', item, message + note)

    def dirs(self, home):
        missing = [str(home / name) + '/' for name in ('requests', 'responses', 'cpus')
                   if not (home / name).is_dir()]
        self.report('bad' if missing else 'ok', 'dirs',
                    '缺 %s；手建的家請 mkdir -p 補上（aos-kernel init 會建）' % '、'.join(missing)
                    if missing else 'requests/、responses/、cpus/ 都在')

    def cpus(self, home, info, daemon):
        state = aos_home.read_state(home, {})
        if state.get('phase') not in ('running', 'stopping'):
            return
        names = dict.fromkeys([*info['cpus'], *([state['kcpu']] if state.get('kcpu') else [])])
        base = str(home / 'cpus') + os.sep
        # 與 stop 一致：同名但 target 屬於別家的孩子不算。
        owned = {name for name, child in aos_daemon.read_state(daemon)['children'].items()
                 if name in names and child['target'].startswith(base)
                 and os.path.abspath(child['target']).startswith(base)}
        missing = [name for name in names if name not in owned]
        self.report('bad' if missing else 'ok', 'cpus',
                    'daemon 重開過／cpu 不在（%s）：執行 aos-kernel boot --target %s --daemon-target %s' %
                    (', '.join(missing), home, daemon) if missing else '帳本裡的 cpu 都在 daemon 孩子表')

    def envs(self, home, name, config):
        expected = config.get('envs', {})
        inst = home / 'cpus' / name / 'inst.json'
        effective = expected
        if inst.exists():
            try:
                raw = aos_home.read_json(inst)
                if not isinstance(raw, dict):
                    raise ValueError('inst.json 必須是物件')
                effective = raw.get('envs', {})
            except ERRORS as exc:
                self.report('bad', 'llm/' + name if config['pool'] == 'llm' else 'path/' + name,
                            '%s；請修正 %s' % (exc, inst))
                return None
            if effective != expected:
                self.report('warn', 'envs/' + name, 'inst.json 已建，改 info 不生效，要 aos-kernel halt 後改 inst.json')
        return effective

    def llm(self, name, effective, env):
        item = 'llm/' + name
        if not isinstance(effective, dict) or any(k.startswith('$') for k in effective):
            self.report('warn', item, 'envs 無法靜態判斷；請確認 inst.json 的 AOS_LLM_CONFIG')
            return set()
        if 'AOS_LLM_CONFIG' not in effective:
            self.report('bad', item, '沒設 AOS_LLM_CONFIG；請在 cpu envs 設成 llm.json 的絕對路徑')
            return set()
        path, known = _literal(effective['AOS_LLM_CONFIG'], env)
        if not known:
            self.report('warn', item, 'AOS_LLM_CONFIG 無法靜態判斷；請確認指示詞執行結果')
            return set()
        try:
            path = aos_llm_call.config_path({'AOS_LLM_CONFIG': path})
            actual_env = dict(env)
            for key, value in effective.items():
                value, known = _literal(value, env)
                if known and value is not None:
                    actual_env[key] = value
            cfg = aos_llm_call.load_config(path, env=actual_env)
        except ERRORS as exc:
            self.report('bad', item, '%s；請修正 AOS_LLM_CONFIG 與 llm.json' % exc)
            return set()
        models = set(cfg['models'])
        self.report('ok', item, '模型代號：' + (', '.join(sorted(models)) or '（空）'))
        return models

    def agent(self, directory, pools, models, env):
        try:
            info = aos_agent_info.load(directory, env=env)
        except ERRORS as exc:
            self.report('bad', 'agent', '%s；請修正 agent 家 %s' % (exc, directory))
            return
        self.report('ok', 'agent', 'agent 設定讀驗通過')
        for field in ('tick', 'llm'):
            pool = info[field]['pool']
            exists = pool in pools
            self.report('ok' if exists else 'bad', 'agent/' + field + '.pool',
                        '池 %s 存在' % pool if exists else '池 %s 不存在；請修改 agent info 或補 cpu 池' % pool)
        model = info['llm']['model']
        exists = model in models
        self.report('ok' if exists else 'bad', 'agent/llm.model',
                    '模型 %s 存在' % model if exists else '模型 %s 不在 llm 設定；請修正模型代號或 llm.json' % model)
        for tool in info['tools_raw']:
            item = 'agent/tool/' + tool['function']['name']
            argv = tool['_meta'].get('argv')
            if not isinstance(argv, list) or not argv or not isinstance(argv[0], str):
                self.report('warn', item, '_meta.argv[0] 無法靜態判斷；請確認工具的執行目標')
                continue
            command = argv[0]
            if '/' in command:
                path = Path(directory).absolute() / command
                exists = path.is_file() and os.access(path, os.X_OK)
            else:
                exists = shutil.which(command, path=env.get('PATH', os.defpath)) is not None
            self.report('ok' if exists else 'bad', item,
                        '可執行 %s' % command if exists else '找不到可執行的 %s；請修正工具路徑、執行權限或 PATH' % command)


def check(home, agent=None, daemon=None):
    # 延後 import，讓 kernel CLI 僅需接線，不形成模組初始化循環。
    from aos_kernel import load_info
    home = Path(home).absolute()
    checks = Checks()
    try:
        info = load_info(home)
    except ERRORS as exc:
        checks.report('bad', 'info', '%s；請修正 %s/info.json' % (exc, home))
        return 1
    checks.report('ok', 'info', 'kernel 設定讀驗通過')
    checks.dirs(home)
    daemon = str(aos_daemon.daemon_home(daemon))
    try:
        alive = aos_daemon.is_alive(daemon)
    except OSError:
        alive = False
    checks.report('ok' if alive else 'warn', 'daemon',
                  'daemon 活著：%s' % daemon if alive else
                  'daemon 沒在跑；先開 daemon：aos-daemon boot --target %s' % daemon)
    recorded = info.get('daemon')
    if recorded and os.path.abspath(recorded) != daemon:
        checks.report('warn', 'daemon', 'info.json 記的 daemon 是 %s（上次 boot 寫的），這次查的是 %s；'
                      '要查那個就加 --daemon-target %s' % (recorded, daemon, recorded))
    if alive:
        checks.cpus(home, info, daemon)
    env, note = daemon_environment(daemon, alive)
    checks.path(env.get('PATH', os.defpath), note)
    pools = {config['pool'] for config in info['cpus'].values()}
    checks.report('ok', 'pools', '池：' + ', '.join(sorted(pools)))
    if 'default' not in pools:
        checks.report('warn', 'pools', 'default 池沒有 cpu；一般工作需要時請補 default cpu')
    if 'llm' not in pools:
        checks.report('bad', 'pools', 'llm 池沒有 cpu；在 info.json（或 init 的 --config 檔）的 cpus 加 {"llm": {"pool": "llm", "envs": {"AOS_LLM_CONFIG": …}}}')
    models = set()
    for name, config in info['cpus'].items():
        effective = checks.envs(home, name, config)
        if effective is None:
            continue
        if isinstance(effective, dict) and isinstance(effective.get('PATH'), str):
            checks.path(effective['PATH'], '（cpu envs 的 PATH）', 'path/' + name)
        if config['pool'] == 'llm':
            models.update(checks.llm(name, effective, env))
    if agent is not None:
        checks.agent(agent, pools, models, env)
    return int(checks.bad)
