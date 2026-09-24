"""aos-agent check（advice-r1，aos-agent.md §1.7）：從 aos-kernel check --agent 搬來的啟動前唯讀檢查。

K 不用人給：AOS_KERNEL_HOME（start 用的那個），沒設就用 tick.json 記的（上次 start 寫的）。
先整段跑 kernel 那份檢查，再查這個 agent 家；不問模型（--probe 才打 endpoint）、不拿鎖、不寫檔。
"""
import os
import shutil
import stat
import subprocess

import aos_agent_access
import aos_agent_info
import aos_jail
import aos_kernel_check
from aos_agent_home import AgentError
from aos_agent_runtime import KERNEL_ENV
from aos_agent_status import tick_binding


def find_kernel(base, env):
    """回 (K 或 None, 來源, 額外 bad 訊息或 None)。"""
    tick = os.path.join(base, 'tick.json')
    exists = os.path.lexists(tick)
    raw = tick_binding(base)[0] if exists else None
    bound = raw if isinstance(raw, str) and os.path.isabs(raw) else None
    value = env.get(KERNEL_ENV)
    if value:
        if not os.path.isabs(value):
            return None, KERNEL_ENV, '%s 不是絕對路徑：%s（start 也會拒絕）' % (KERNEL_ENV, value)
        # 跟 start 一樣（aos_agent._tick_inst）：tick.json 在，就要讀得到字串而且逐字相同。
        if exists and (not isinstance(raw, str) or raw != value):
            where = '綁在 %s' % raw if isinstance(raw, str) else '讀不到合法的 K（壞了、或沒有 envs.%s）' % KERNEL_ENV
            return value, KERNEL_ENV, ('%s 是 %s，但 %s %s；start 會拒絕（KernelMismatch），'
                                       '要換 K 就先 aos-agent stop 再刪 tick.json' % (KERNEL_ENV, value, tick, where))
        return value, KERNEL_ENV, None
    if bound is not None:
        return bound, 'tick.json', None
    if exists:
        return None, None, ('找不到 K：沒設 %s，%s 也讀不到合法的絕對路徑 K；'
                            'export %s=<kernel 家的絕對路徑> 再跑' % (KERNEL_ENV, tick, KERNEL_ENV))
    return None, None, ('找不到 K：沒設 %s，也沒有 tick.json（沒 start 過）；'
                        'export %s=<kernel 家的絕對路徑> 再跑' % (KERNEL_ENV, KERNEL_ENV))


def check(agent_dir, probe=False, env=None):
    env = os.environ if env is None else env
    base = os.path.abspath(agent_dir)
    checks = aos_kernel_check.Checks()
    home, source, problem = find_kernel(base, env)
    if home is not None:
        checks.report('ok', 'kernel', 'K＝%s（取自 %s）' % (home, source))
    if problem is not None:
        checks.report('bad', 'kernel', problem)
    pools, models, tool_env = None, set(), dict(env)
    if home is not None:
        pools, models, tool_env = aos_kernel_check.kernel_checks(
            checks, home, note='（K＝%s，取自 %s）' % (home, source), recorded_daemon=True)
    checks.agent(base, pools, models, tool_env)
    access_checks(checks, base, tool_env)
    return aos_kernel_check.finish(checks, probe, then='aos-agent start')


def bwrap_probe(env):
    """跑一次固定、無副作用的 bwrap（跟 aos-jail 同一組參數，程式是 true）；回 (ok, 白話)。"""
    bwrap = shutil.which('bwrap', path=env.get('PATH', os.defpath))
    if bwrap is None:
        return False, 'NoBwrap: 找不到 bwrap（bubblewrap）；Arch/Manjaro: sudo pacman -S bubblewrap，Debian/Ubuntu: sudo apt install bubblewrap'
    opts = aos_jail.parse_args(['--', 'true'])
    argv, _ = aos_jail.build_argv(opts, environ={}, bwrap=bwrap)
    try:
        r = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, 'bwrap 開不起來：%s' % exc
    if r.returncode != 0:
        return False, 'bwrap 開不起來（退 %s）：%s；user namespace 可能被關了' % (
            r.returncode, ' '.join(r.stderr.split())[:200])
    return True, '%s 開得起來' % bwrap


def _special_files(folder):
    """mount 頂層的 socket／FIFO（唯讀也擋不住連它們）。"""
    found = []
    try:
        for entry in os.scandir(folder):
            mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISSOCK(mode) or stat.S_ISFIFO(mode):
                found.append(entry.name)
    except OSError:
        pass
    return found


def access_checks(checks, base, env):
    """access.md：access 檔、bwrap、aos-jail、各工具在牢裡跑不跑得起來（靜態，查不到的 warn）。"""
    try:
        info = aos_agent_info.load(base, env=env)
    except (AgentError, OSError):
        info = None
    tools = info['tools_raw'] if info else []
    try:
        path = aos_agent_access.access_path(base, env=env)
        explicit = 'access' in aos_agent_access.read_info_doc(base).root
    except AgentError as exc:
        checks.report('bad', 'access', '%s；看 info.json 的 access 欄' % exc)
        return
    if path is None and not explicit:
        if tools:
            checks.report('warn', 'access', '沒有 access.json：工具不關牢（碰得到你碰得到的所有檔）；'
                          '要關：aos-agent access set ws workspace --cwd --target %s' % base)
        return
    try:
        table = aos_agent_access.load(base, env=env, info=info)
    except AgentError as exc:
        checks.report('bad', 'access', str(exc))
        table = None
    if table is not None:
        checks.report('ok', 'access', '%s 讀驗通過：%d 個 mount、起點 /work%s、net %s' % (
            path, len(table['mounts']), '/' + table['cwd'] if table['cwd'] else '',
            'on' if table['net'] else 'off'))
        for name, m in table['mounts'].items():
            odd = _special_files(m['path'])
            if odd:
                checks.report('warn', 'access/' + name, '頂層有 socket／FIFO（%s）：牢裡連得到它們，唯讀也擋不住'
                              % '、'.join(odd[:5]))
    ok, message = bwrap_probe(env)
    checks.report('ok' if ok else 'bad', 'access/bwrap', message)
    jail = shutil.which('aos-jail', path=env.get('PATH', os.defpath))
    checks.report('ok' if jail else 'bad', 'access/aos-jail',
                  '找得到 %s' % jail if jail else '找不到 aos-jail；開 daemon 前 export PATH=<proto5>/cli:$PATH')
    for tool in tools:
        item = 'agent/tool/' + tool['function']['name']
        if tool.get('_jail', True) is False:
            checks.report('warn', item, '_jail: false：這支不關牢，碰得到你碰得到的所有檔')
            continue
        argv = tool['_meta'].get('argv') if isinstance(tool.get('_meta'), dict) else None
        if not isinstance(argv, list) or not argv or not isinstance(argv[0], str) or '/' in argv[0]:
            continue
        found = shutil.which(argv[0], path=env.get('PATH', os.defpath))
        real = os.path.realpath(found) if found else None
        if real is None or not real.startswith('/usr/'):
            checks.report('warn', item, '%s 不在 /usr 下（%s）：牢裡只有 /usr，可能找不到；寫絕對路徑或裝到 /usr'
                          % (argv[0], real or '找不到'))
