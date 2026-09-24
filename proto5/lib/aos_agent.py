#!/usr/bin/env python3
"""aos-agent tick／start／stop；按規範持久化，再執行可重做的副作用。"""
import os
from pathlib import Path

import aos_agent_info
import aos_client
import aos_home
from aos_agent_batch import META, collect, make_batch, send
from aos_agent_home import AgentError, resolve_field
from aos_agent_inputs import finish_consuming, gate, intake
from aos_agent_runtime import KERNEL_ENV, Runtime, manual_paused, report, tick_lock, unique_id
from aos_directives import Context, Document, is_directive

WAIT_TIMEOUT_MS = 10000
PARK_EXIT = 102  # 09-24 停車：批在途什麼都沒到、idle 沒輸入（aos-agent tick.md §12）


def _hook(step_name):
    """持久化完成後的單一測試掛鉤；正式執行時不做任何事。"""


def _other_home(base):
    """info.json 字面寫著別種家（kernel、daemon…）就不是 agent 家：不建鎖檔、不看 paused，交給讀驗報 NotAnAgent。

    讀不懂或 _type 是指示詞的，當作壞掉的 agent 設定照常拿鎖（壞設定也要能 pause）。
    """
    try:
        meta = aos_home.read_json(base / 'info.json').get('_metainfo')
        kind = meta.get('_type') if isinstance(meta, dict) else None
    except (aos_home.HomeError, AttributeError):
        return False
    # fix-r5：回那個 _type（真值），讓 NotAnAgent 能說「這是 kernel 家」。
    return kind if isinstance(kind, str) and kind != 'llm_agent' else False


def _environment(env):
    env = os.environ if env is None else env
    kernel = env.get(KERNEL_ENV)
    if not isinstance(kernel, str) or not os.path.isabs(kernel):
        raise AgentError('Usage', KERNEL_ENV + ' 必須設成 kernel 家的絕對路徑')
    return env, kernel


def _error(exc, note=''):
    code = 'io' if isinstance(exc, OSError) or getattr(exc, 'code', '') == 'WriteFailed' else exc.code
    report(code, getattr(exc, 'msg', str(exc)) + (note if code == 'NotAnAgent' else ''))
    return 2 if code == 'Usage' else 1


def tick(agent_dir, env=None, note=''):
    lock = None
    try:
        env, kernel = _environment(env)
        base = Path(os.path.abspath(agent_dir))
        if (base / 'info.json').exists() and not _other_home(base):
            # aos-agent.md §2.1：同一個家同時只有一個 tick 做事；被佔就讓掉，不動任何檔。
            got, lock = tick_lock(base)
            if not got:
                report('busy', '另一個 tick 正在跑（pid %s），這格不做事' % (lock or '不明'))
                lock = None
                return 101
            if manual_paused(base) is not None:
                return 0
        # 此段讀驗全部完成前不建立 work，不做任何寫入。
        info = aos_agent_info.load(agent_dir, env=env)
        st = aos_agent_info.load_state(agent_dir, env=env)
        run = Runtime(info, st, env, _hook)
        finish_consuming(run)
        run.sweep()
        if not gate(run):
            return 101
        if st['batch'] is not None:
            return _park(collect(run))
        if st['state'] == 'idle':
            # spec/agent/compact.md：自動壓縮在同一把 tick 鎖裡做（不另拿鎖）；做了事這格就到這裡
            if st['intake'] is None:
                import aos_agent_compact
                if aos_agent_compact.auto(run):
                    return 0
            return _park(intake(run))
        history = info['history']
        if st['state'] == 'act' and not (history and history[-1]['role'] == 'assistant'
                                        and history[-1].get('tool_calls')):
            st['state'] = 'think'
            run.save('state.act_empty')
            return 0
        make_batch(run, kernel)
        return send(run)
    except (AgentError, aos_home.HomeError, OSError) as exc:
        return _error(exc, note)
    finally:
        if lock is not None:
            os.close(lock)


def _park(code):
    """collect／intake 的 101（什麼都沒到、沒輸入）改退 102 停車；門關著、鎖被佔的 101 不經過這裡。"""
    return PARK_EXIT if code == 101 else code


def _compatible(kernel, env):
    path = Path(kernel) / 'info.json'
    try:
        raw = aos_home.read_json(path)
    except aos_home.HomeError as exc:
        raise AgentError('NotAHome', exc.msg) from exc
    if not isinstance(raw, dict) or is_directive(raw):
        raise AgentError('NotAHome', 'K/info.json 頂層必須是字面物件')
    doc = Document(path, raw)
    ctx = Context(doc, base_dir=kernel, env=env)
    values = {}
    for key, default in [('done_exit', 100), ('bad_after', 10)]:
        value = resolve_field(doc, ctx, [key]) if key in raw else default
        if type(value) is not int or value < 0 or (key == 'done_exit' and value > 255):
            raise AgentError('FieldTypeMismatch', '%s 必須是規定範圍的整數' % key)
        values[key] = value
    if values['done_exit'] in (1, 101, PARK_EXIT):
        raise AgentError('KernelIncompatible', 'kernel 的 done_exit 與 agent 退出碼衝突')
    # 09-24 停車：舊 kernel 把 102 當失敗（十次就 bad）。帳本讀得到而沒有 park 能力＝不登記；還沒 boot（沒帳本、沒 chain）或讀不懂就不擋。
    # 09-24 one-boot：帳本換成 K/ledger.sqlite；還是舊的 K/state.json＝舊 kernel（kernel cpu 那一版）寫的，先 aos up 換過再 start。
    import aos_kernel_store
    if aos_kernel_store.legacy(kernel):
        raise AgentError('KernelIncompatible', 'K 的帳本還是舊的 state.json（sqlite 之前的 kernel）；'
                         'aos up（或 aos-kernel boot）一次換成 sqlite 再 start')
    try:
        ledger = aos_kernel_store.meta(kernel, 'chain', 'features')
    except aos_home.HomeError:
        return
    features = ledger.get('features')
    if 'chain' in ledger and not (isinstance(features, list) and 'park' in features):
        raise AgentError('KernelIncompatible', 'K 的帳本是不認得停車（退出碼 102）的舊 kernel 寫的；'
                         '升級 kernel 後 aos up（或 aos-kernel boot）一次再 start')


def _tick_inst(run, kernel):
    from aos_agent_status import tick_binding
    path = run.base / 'tick.json'
    if path.exists():
        value, legacy = tick_binding(run.base)
        if not isinstance(value, str) or value != kernel:
            raise AgentError('KernelMismatch', 'tick.json 綁在另一個 K，要換就刪掉 tick.json 再 start')
        if not legacy:
            return str(path)
    # 沒有、或是 fix-r4 前的舊版（位置參數＋AOS_K）：照新格式寫。
    run.write(path, {'_metainfo': dict(META), 'argv': ['aos-agent', 'tick', '--target', str(run.base)],
                     'cwd': str(run.base), 'envs': {KERNEL_ENV: kernel},
                     'stderr': {'$opt': ['append', 'mkdir'],
                                '$val': str(run.base / 'log' / 'agent.err')}}, 'tick.inst')
    return str(path)


def _register(agent_dir, env, starting, note=''):
    try:
        env = os.environ if env is None else env
        from aos_agent_status import tick_binding, tick_kernel
        if not starting and not env.get(KERNEL_ENV):
            bound = tick_kernel(agent_dir)
            if bound is None:
                raise AgentError('Usage', '沒設 %s，tick.json 也沒記' % KERNEL_ENV)
            env = dict(env, **{KERNEL_ENV: bound})
        env, kernel = _environment(env)
        if starting:
            info = aos_agent_info.load(agent_dir, env=env)
        else:
            base = Path(os.path.abspath(agent_dir))
            if not base.is_dir():
                raise AgentError('NotAnAgent', '%s 不是存在的資料夾' % base)
            bound = tick_binding(base)[0]
            if isinstance(bound, str) and bound != kernel:
                raise AgentError('KernelMismatch', '%s 綁在 %s' % (base / 'tick.json', bound))
            info = {'dir': str(base)}
        run = Runtime(info, None, env, _hook)
        params = {'name': 'agent-' + run.base.name}
        if starting:
            _compatible(kernel, env)
            params.update(target=_tick_inst(run, kernel), pool=info['tick']['pool'])
            if info['tick']['interval_ms'] is not None:
                params['interval_ms'] = info['tick']['interval_ms']
        name = 'aa-%s-%s.json' % (run.base.name, unique_id())
        run.submit(kernel, name, 'add' if starting else 'rm', params)
        try:
            response = aos_client.wait_response(kernel, name, timeout_ms=WAIT_TIMEOUT_MS)
        except aos_client.ClientError as exc:
            if exc.code != 'ReadFailed':
                raise
            raise AgentError('ReadFailed', '等回音逾時，回音會出現在 %s/responses/%s，讀完自己放 ack（cpu.md §3.3）'
                             % (kernel, name)) from exc
        run.ack(kernel, name, 0)
        if isinstance(response, dict) and isinstance(response.get('error'), dict):
            from aos_agent_results import error_code
            error = response['error']
            code, message = str(error_code(error)), error.get('message', 'kernel 退件')
            if starting and code == 'AlreadyExists':
                already = _already(kernel, params)
                if already is None:
                    print('already started ' + params['name'])
                    return 0
                message = '%s；%s' % (message, already)
            raise AgentError(code, message)
        if (not isinstance(response, dict) or not isinstance(response.get('result'), dict)
                or not isinstance(response['result'].get('name'), str)):
            raise AgentError('ReadFailed', 'kernel 回音缺少 result.name')
        print(('started ' if starting else 'stopped ') + params['name'])
        return 0
    except (AgentError, aos_home.HomeError, OSError) as exc:
        return _error(exc, note)


def _already(kernel, params):
    """start 撞 AlreadyExists（aos-agent.md §11，fix-r5）：就是這個家、正常登記著＝None（退 0）；否則回補充說明。"""
    from aos_agent_runtime import kernel_proc
    try:
        # one-boot：查一筆行程走 aos-kernel proc 同一支 lib（K/ledger.sqlite）；discard＝上次 stop 的那格還在 cpu 上。
        found = kernel_proc(kernel, params['name'])
        proc = found['proc'] if found else None
        discarded = bool(found and found['discard'])
    except (AgentError, aos_home.HomeError, OSError, ValueError):
        return '帳本讀不到，確認不了是不是同一個家'
    if not isinstance(proc, dict):
        return '帳本裡沒這筆（可能剛被 stop），等一下再 start'
    if proc.get('target') != params['target']:
        return '同名行程是 %s，改資料夾名' % proc.get('target')
    if discarded:
        return '上次 stop 的那格還在跑，等它跑完再 start'
    if proc.get('status') == 'bad':
        return '已登記但被判 bad，看 log/agent.err 修好後 stop 再 start'
    return None


def start(agent_dir, env=None, note=''):
    return _register(agent_dir, env, True, note)


def stop(agent_dir, env=None, note=''):
    return _register(agent_dir, env, False, note)


def main(argv=None):
    """命令列在 aos_agent_cli.py；這裡留入口給 cli/aos-agent 與測試。"""
    from aos_agent_cli import main as cli_main
    return cli_main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
