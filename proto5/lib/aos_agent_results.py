"""aos-agent.md §6 的兩張表：依序取第一個命中的結果。"""
import json
import os
from pathlib import Path

from aos_agent_home import AgentError, check_message

UNKNOWN = json.dumps({'ok': False, 'error': '結果不明：工具可能已經跑了，也可能沒有'}, ensure_ascii=False)


def model_message(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8').rstrip('\n'))
        check_message(value, from_model=True)
        return value
    except (OSError, ValueError, UnicodeError, AgentError) as exc:
        raise AgentError('MessageInvalid', '模型輸出不合規：%s' % exc) from exc


def error_code(error):
    data = error.get('data')
    return data.get('code', error['code']) if isinstance(data, dict) else error['code']


def response_parts(response):
    if not isinstance(response, dict) or response.get('jsonrpc') != '2.0':
        raise AgentError('ReadFailed', '回音不是 JSON-RPC 物件')
    result, error = response.get('result'), response.get('error')
    if isinstance(result, dict) and 'error' not in response:
        if (result.get('kind') not in ('child', 'aos') or type(result.get('code')) is not int
                or type(result.get('stopped')) is not bool or type(result.get('timed_out')) is not bool):
            raise AgentError('ReadFailed', '回音 result 形狀不合')
        return result, None
    if isinstance(error, dict) and type(error.get('code')) is int and 'result' not in response:
        return None, error_code(error)
    raise AgentError('ReadFailed', '回音缺少 result／error')


def success(result):
    return (result['kind'] == 'child' and result['code'] == 0
            and not result['timed_out'] and not result['stopped'])


def llm_log(path):
    log = path.absolute().parent.parent / 'log' / 'llm.err'
    try:
        lines = [line.strip() for line in log.read_text(encoding='utf-8', errors='replace').splitlines()
                 if line.strip()]
    except OSError:
        lines = []
    return str(log) + ('：' + lines[-1][:300] if lines else '')


def cpu_logs(kernel, pool):
    base = Path(kernel)
    try:
        raw = json.loads((base / 'info.json').read_text(encoding='utf-8'))
        cpus = raw.get('cpus', {})
        names = [name for name, cpu in cpus.items() if isinstance(cpu, dict)
                 and cpu.get('pool', 'default') == pool]
    except (OSError, ValueError, AttributeError):
        names = []
    return '、'.join(str(base / 'cpus' / name / 'cpu.log') for name in names or ['*'])


def exec_failure(path, code):
    argv0, cwd = '?', '?'
    try:
        inst = json.loads(path.with_suffix('.inst.json').read_text(encoding='utf-8'))
        argv = inst.get('argv')
        if isinstance(argv, list) and argv and isinstance(argv[0], str):
            argv0 = argv[0]
        cwd = inst.get('cwd', '?')
        if isinstance(cwd, dict):
            cwd = cwd.get('$val', '?')
    except (OSError, ValueError, AttributeError):
        pass
    reason = ('找不到程式 argv[0]=%s' if code == 127 else
              '不能執行 argv[0]=%s，看有沒有執行權限、是不是可執行檔') % argv0
    detail = 'exit %s：%s' % (code, reason)
    if argv0 != '?' and not os.path.isabs(argv0):
        detail += '（相對 cwd %s；不含 / 的照跑它那顆 cpu 的 PATH 找）' % cwd
    return detail


def think_done(response, path, timeout, *, kernel, pool):
    result, code = response_parts(response)
    count = True
    if result is not None:
        if success(result):
            try:
                model_message(path)
                return {'ok': True}
            except AgentError as exc:
                return {'fail': str(exc), 'count': True}
        if result['stopped']:
            fail, count = '被強制停', False
        elif result['timed_out']:
            fail = ('逾時（%s ms，是 info.llm.timeout_ms；要更久就改 agent 的 info.json；llm.err 在 %s）'
                    % (timeout, path.absolute().parent.parent / 'log/llm.err'))
        elif result['kind'] == 'aos':
            fail = 'aos-llm-call 沒跑起來（kind=aos），看 ' + cpu_logs(kernel, pool)
        else:
            fail = 'aos-llm-call exit %s，看 %s' % (result['code'], llm_log(path))
    elif code == 'Stopping':
        fail, count = 'kernel 停機時取消，沒跑', False
    elif code in ('Interrupted', 'Removed'):
        fail = '結果不明（%s）' % code
    else:
        fail = 'kernel 退件：%s' % code
    return {'fail': fail, 'count': count}


def act_done(response, path, tool, timeout):
    result, code = response_parts(response)

    def output():
        try:
            return path.read_bytes().decode('utf-8', errors='replace')
        except FileNotFoundError:
            return ''

    if result is not None:
        if success(result):
            content = output()
        elif result['stopped']:
            content = UNKNOWN
        elif result['timed_out']:
            content = '工具 %s 逾時（%s ms）：%s' % (tool, timeout, output())
        elif result['kind'] == 'aos':
            content = '工具 %s 無法執行（kind=aos），詳情在跑它那顆 cpu 的 cpu.log' % tool
        elif result['code'] in (126, 127):
            content = '工具 %s 失敗（%s）：%s' % (tool, exec_failure(path, result['code']), output())
        else:
            content = '工具 %s 失敗（exit %s）：%s' % (tool, result['code'], output())
    elif code in ('Interrupted', 'Removed'):
        content = UNKNOWN
    elif code == 'Stopping':
        content = '工具 %s 沒跑：kernel 停機時取消' % tool
    else:
        content = '工具 %s 沒跑：kernel 退件（%s）' % (tool, code)
    return {'content': content}
