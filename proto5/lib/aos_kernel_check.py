"""kernel 啟動前的唯讀檢查；不解任意 inst 指示詞、不啟動工具或模型（kernel-cli.md 的 check）。"""
import os
from pathlib import Path
import shutil

import aos_agent_info
import aos_daemon
import aos_home
import aos_llm_call
from aos_agent_home import AgentError
from aos_kernel_info import KERNEL_POOL, load_info, pool_location

COMMANDS = ('aos-exec', 'aos-cpu', 'aos-kernel', 'aos-agent', 'aos-llm')
DIRS = ('requests', 'responses', 'pools')
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


PROBE_LIMIT_MS = 10000


def probe_endpoint(entry):
    """fix-r5：對一個模型設定打一次最小請求；回 (level, 一句話)。

    先 GET <endpoint>/models；404／405 再退回 POST chat/completions 一句話（max_tokens 1）。
    """
    import http.client
    import json
    import urllib.error
    import urllib.request
    base = entry['endpoint'].rstrip('/')
    timeout = min(entry.get('timeout_ms', 120000), PROBE_LIMIT_MS) / 1000
    headers = {'Accept': 'application/json'}
    if entry.get('api_key'):
        headers['Authorization'] = 'Bearer ' + entry['api_key']

    def hide(text):
        text = ' '.join(str(text).split())[:200]
        return text.replace(entry['api_key'], '[已隱藏]') if entry.get('api_key') else text

    def fetch(url, body=None):
        data = None if body is None else json.dumps(body).encode('utf-8')
        extra = {} if body is None else {'Content-Type': 'application/json'}
        request = urllib.request.Request(url, data=data, headers={**headers, **extra},
                                         method='GET' if body is None else 'POST')
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()

    where = '（endpoint %s，模型 %s）' % (entry['endpoint'], entry['model'])
    try:
        try:
            raw = fetch(base + '/models')
        except urllib.error.HTTPError as exc:
            if exc.code not in (404, 405):
                raise
            exc.close()
            fetch(base + '/chat/completions', {'model': entry['model'], 'max_tokens': 1,
                                               'messages': [{'role': 'user', 'content': 'hi'}]})
            return 'ok', '模型回了一句話' + where
        try:
            data = json.loads(raw).get('data')
            if not isinstance(data, list):
                raise TypeError
            listed = {m.get('id') for m in data if isinstance(m, dict)}
        except (ValueError, AttributeError, TypeError):
            return 'ok', 'endpoint 通' + where
        if entry['model'] not in listed:  # 空清單也算沒有（astra 審查）
            return 'warn', 'endpoint 通，但模型清單裡沒有 %s%s' % (entry['model'], where)
        return 'ok', 'endpoint 通，模型清單裡有 %s%s' % (entry['model'], where)
    except urllib.error.HTTPError as exc:
        return 'bad', 'HTTP %d%s' % (exc.code, where)
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as exc:
        reason = getattr(exc, 'reason', exc)
        return 'bad', '連不上：%s%s；改 llm.json 的 endpoint' % (hide(reason), where)


class Checks:
    def __init__(self):
        self.bad = False
        self.configs = []   # fix-r5：--probe 要打的 (代號, 模型設定)
        self.home = None       # 納入：kernel_checks 填，agent 項的提示要用
        self.pools_effective = {}   # 納入：各池有效 envs（kernel_checks 填）
        self.pool_models = {}  # 納入：各池 llm.json 的模型代號（kernel_checks 填）
        self.pool_envs = {}    # 納入審查 P1：各池用哪個 daemon 的環境解 $env（kernel_checks 填）

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
        missing = [str(home / name) + '/' for name in DIRS if not (home / name).is_dir()]
        self.report('bad' if missing else 'ok', 'dirs',
                    '缺 %s；手建的家請 mkdir -p 補上（aos-kernel init 會建）' % '、'.join(missing)
                    if missing else 'requests/、responses/、pools/ 都在')

    def cpus(self, home, info, alive):
        """帳本 phase 是 running／stopping 時，看各池摘要（同 ls 的 health 判定）；daemon 沒活的池略過。"""
        from aos_kernel_rows import _Alive, pool_rows
        state = aos_home.read_state(home, {})
        if state.get('phase') not in ('running', 'stopping') or not state.get('pools'):
            return
        rows = pool_rows(home, info, state, alive=_Alive(alive))
        boot = 'aos-kernel boot --target %s' % home
        problems, warns, fine, seen = [], [], [], 0
        for pool, row in rows.items():
            if not row['declared'] or not row['daemon'] or not row['daemon_alive']:
                continue
            seen += 1
            summary = row['summary'] or {}
            if pool == KERNEL_POOL:
                if summary.get('running', 0) == 0:
                    problems.append('kernel cpu 不在（daemon 重開過或還在拉）')
                else:
                    fine.append('kernel 1')
            elif row['error']:
                problems.append('池 %s：%s（%s）' % (pool, row['error'].get('code'), row['error'].get('message') or '-'))
            elif row['gone']:
                problems.append('池 %s：池不見了' % pool)
            elif row['sent'] and summary.get('running', 0) < row['sent']:
                warns.append('池 %s 少 %d 顆（daemon 在補；看 aos-daemon ls --target %s --pool %s）' % (
                    pool, row['sent'] - summary.get('running', 0), row['daemon'], row['dpool']))
            else:
                fine.append('%s %s' % (pool, summary.get('running', 0)))
        if problems:
            self.report('bad', 'cpus', '%s：執行 %s' % ('；'.join(problems), boot))
        for text in warns:
            self.report('warn', 'cpus', text)
        if not problems and not warns and seen:
            self.report('ok', 'cpus', '各池都在 daemon 那邊（%s）' % ('、'.join(fine) or '沒有已宣告的池'))

    def envs(self, home, pool, config):
        """池的有效 envs：K/pools/<池>/envs.json 在就讀它，否則讀 info（kernel-cli check）。"""
        expected = config.get('envs', {})
        path = home / 'pools' / pool / 'envs.json'
        if not path.exists():
            return expected
        try:
            effective = aos_home.read_json(path)
            if not isinstance(effective, dict):
                raise ValueError('envs.json 必須是物件')
        except ERRORS as exc:
            self.report('bad', 'envs/' + pool, '%s；kernel 在跑時下一格會重寫，沒在跑就 boot 重寫（或刪掉 %s）' % (exc, path))
            return None
        if effective != expected:
            self.report('warn', 'envs/' + pool, '%s 跟 info 的 envs 不同：kernel 在跑就下一格重寫，沒在跑就等 boot；'
                        '活著的 cpu 要換新環境用 aos-daemon kill --pool <dpool> --all' % path)
        return effective

    def llm(self, name, effective, env):
        item = 'llm/' + name
        if not isinstance(effective, dict) or any(k.startswith('$') for k in effective):
            self.report('warn', item, 'envs 無法靜態判斷；請確認池 envs（K/pools/%s/envs.json）的 AOS_LLM_CONFIG' % name)
            return set()
        if 'AOS_LLM_CONFIG' not in effective:
            self.report('bad', item, '沒設 AOS_LLM_CONFIG；請在 info.json 的 pools.%s.envs 設成 llm.json 的絕對路徑' % name)
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
        self.configs.extend(cfg['models'].items())
        return models

    def probe(self):
        seen = set()
        for alias, entry in self.configs:
            key = (entry['endpoint'], entry['model'], entry.get('api_key'))
            if key in seen:
                continue
            seen.add(key)
            level, message = probe_endpoint(entry)
            self.report(level, 'probe/' + alias, message)

    def agent(self, directory, pools, models, env):
        """由 aos-agent check 呼叫（advice-r1）；pools 是 None＝K 讀不到，池與模型不查。

        池式（proto5-2 納入）：pools 是 info 的池表；tick／llm／tool_pool 三個池都查，模型只看 agent 的 llm 池。
        """
        try:
            info = aos_agent_info.load(directory, env=env)
        except ERRORS as exc:
            self.report('bad', 'agent', '%s；請修正 agent 家 %s' % (exc, directory))
            return None
        self.report('ok', 'agent', 'agent 設定讀驗通過')
        if pools is None:
            self.report('warn', 'agent/pools', 'K 讀不到，池與模型代號沒查；先修好上面的 kernel 項')
        else:
            home = self.home
            for item, pool in (('tick.pool', info['tick']['pool']), ('llm.pool', info['llm']['pool']),
                               ('tool_pool', info['tool_pool'])):
                if pool == KERNEL_POOL:
                    self.report('bad', 'agent/' + item, '池 %s 是 kernel 池，不能派工作；請修改 agent info' % pool)
                elif pool not in pools:
                    self.report('bad', 'agent/' + item, '池 %s 不在 pools；請修改 agent info，或 aos-kernel cpu add --target %s --pool %s'
                                % (pool, home, pool))
                elif pools[pool]['count'] == 0:
                    self.report('warn', 'agent/' + item, '池 %s 的 count 是 0，工作會一直排隊；aos-kernel cpu add --target %s --pool %s'
                                % (pool, home, pool))
                else:
                    self.report('ok', 'agent/' + item, '池 %s 存在（count %d）' % (pool, pools[pool]['count']))
            self.agent_model(info, pools, models, env)
        self.agent_tools(directory, info, env)
        return info

    def agent_model(self, info, pools, models, env):
        """llm.model 要在 agent 的 llm 池的 llm.json 裡；那池沒被 kernel_checks 查過（沒設 AOS_LLM_CONFIG）就在這裡查。"""
        pool = info['llm']['pool']
        if pool in pools and pool != KERNEL_POOL:
            if pool not in self.pool_models and self.pools_effective.get(pool) is not None:
                self.pool_models[pool] = self.llm(pool, self.pools_effective[pool], self.pool_envs.get(pool, env))
            models = self.pool_models.get(pool, set())
        model = info['llm']['model']
        exists = model in models
        self.report('ok' if exists else 'bad', 'agent/llm.model',
                    '模型 %s 存在' % model if exists else '模型 %s 不在 llm 設定；請修正模型代號或 llm.json' % model)

    def agent_tools(self, directory, info, env):
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


def kernel_checks(checks, home, daemon=None, note='', recorded_daemon=False):
    """kernel 那一段；回 (pools, models, env)，info 讀不到回 (None, set(), shell env)。

    池式（proto5-2 納入）：daemon 家從池表（info 頂層或各池的 daemon）拿，--daemon-target 再多查一個，
    所以不再需要「沒給 D 就用 info 記的 daemon」。recorded_daemon＝True 的只有 aos-agent check，
    池式下改當「agent 模式」：llm 項不逐池查，只在 checks.agent() 查那個 agent 的 llm 池（kernel-cli check）。
    """
    for_agent = recorded_daemon
    home = Path(home).absolute()
    checks.home = home
    try:
        info = load_info(home)
    except ERRORS as exc:
        checks.report('bad', 'info', '%s；請修正 %s/info.json%s' % (exc, home, note))
        return None, set(), dict(os.environ)
    checks.report('ok', 'info', 'kernel 設定讀驗通過')
    checks.dirs(home)
    # daemon 項：池表裡提到的每個 daemon 家都查；--daemon-target 再多查一個。
    homes = {}
    for pool in info['pools']:
        location = pool_location(info, pool)
        if location[0] is None:
            checks.report('bad', 'daemon', '池 %s 解不出 daemon 家（boot 會報 NoDaemon）；在 info.json 寫 daemon'
                          '（頂層或該池），或重新 init --daemon D' % pool)
        else:
            homes.setdefault(location[0], []).append(pool)
    if daemon is not None:
        daemon = os.path.abspath(os.path.expanduser(daemon))
        homes.setdefault(daemon, [])
    alive = {}
    for home_d, pools in homes.items():
        try:
            alive[home_d] = aos_daemon.is_alive(home_d)
        except OSError:
            alive[home_d] = False
        if not pools:
            where = '（--daemon-target，池表沒用到）'
        elif alive[home_d]:
            # run.md 碰到的問題 5：`pools` 是 kernel 設定的池表，不是 daemon 那邊真的有的池；daemon 剛開、
            # 還沒拿到任何一張 scale 單時兩者對不上，「daemon 活著（池 …）」會被讀成「daemon 已經有這些池」。
            # 只逐一查 kernel 設定的池（team-rules 的約定：只准用 pool_summary／pool_kid／is_alive），
            # 分清楚「設定了什麼」跟「daemon 現在真的有什麼」。
            current = []
            for pool in pools:
                dpool = pool_location(info, pool)[1]
                try:
                    has = aos_daemon.pool_summary(home_d, dpool) is not None
                except OSError:
                    has = False
                if has:
                    current.append(pool)
            where = '（kernel 設定的池：%s；daemon 目前有：%s）' % (
                '、'.join(pools), '、'.join(current) if current else '還沒有')
        else:
            where = '（池 %s）' % '、'.join(pools)
        checks.report('ok' if alive[home_d] else 'warn', 'daemon',
                      'daemon 活著：%s%s' % (home_d, where) if alive[home_d] else
                      'daemon 沒在跑：%s%s；先開 daemon：aos-daemon boot --target %s' % (home_d, where, home_d))
    checks.cpus(home, info, alive)
    # PATH 看哪個 daemon：--daemon-target 優先，否則 kernel 池的 daemon。
    kernel_daemon = pool_location(info, KERNEL_POOL)[0]
    env_daemon = daemon or kernel_daemon
    env, note = daemon_environment(env_daemon, bool(env_daemon) and alive.get(env_daemon, False))
    checks.path(env.get('PATH', os.defpath), note)
    pools = info['pools']
    checks.report('ok', 'pools', '池：' + '、'.join('%s %d' % (p, c['count']) for p, c in pools.items()))
    effective = {}
    for pool, config in pools.items():
        value = checks.envs(home, pool, config)
        effective[pool] = value
        if isinstance(value, dict) and isinstance(value.get('PATH'), str):
            checks.path(value['PATH'], '（池 %s envs 的 PATH）' % pool, 'path/' + pool)
    checks.pools_effective = effective
    # 納入審查 P1：池 envs 的 $env 要照「拉這池的那個 daemon」的環境解，不是一律用 kernel 池的 daemon。
    by_daemon = {env_daemon: env}
    for pool in pools:
        pool_daemon = pool_location(info, pool)[0]
        if pool_daemon not in by_daemon:
            by_daemon[pool_daemon] = daemon_environment(
                pool_daemon, bool(pool_daemon) and alive.get(pool_daemon, False))[0]
        checks.pool_envs[pool] = by_daemon[pool_daemon]
    models = set()
    for pool, value in effective.items():
        if not for_agent and isinstance(value, dict) and 'AOS_LLM_CONFIG' in value:
            checks.pool_models[pool] = checks.llm(pool, value, checks.pool_envs[pool])
            models.update(checks.pool_models[pool])
    return pools, models, env


def finish(checks, probe, then='boot'):
    if probe:
        checks.probe()
    # fix-r5（kernel.md §6 check）：講清楚這次保證到哪裡。
    print('有 bad，照上面的提示修好再 ' + then if checks.bad else
          '設定檢查通過；模型連線也測過' if probe else '設定檢查通過；未測模型連線（--probe 會測）')
    return int(checks.bad)


def check(home, daemon=None, note='', probe=False):
    """aos-kernel check：只驗 kernel（advice-r1 起 agent 搬到 aos-agent check）。"""
    checks = Checks()
    pools, _, _ = kernel_checks(checks, home, daemon, note)
    if pools is None:
        return 1
    return finish(checks, probe)
