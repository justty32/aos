"""aos-agent.md §6 的兩張表：依序取第一個命中的結果。"""
import json

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


def think_done(response, path, timeout):
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
            fail = '逾時（%s ms）' % timeout
        elif result['kind'] == 'aos':
            fail = 'aos-llm-call 沒跑起來（kind=aos），看 llm 池 cpu 的 cpu.log'
        else:
            fail = 'aos-llm-call exit %s，看 log/llm.err' % result['code']
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
        else:
            content = '工具 %s 失敗（exit %s）：%s' % (tool, result['code'], output())
    elif code in ('Interrupted', 'Removed'):
        content = UNKNOWN
    elif code == 'Stopping':
        content = '工具 %s 沒跑：kernel 停機時取消' % tool
    else:
        content = '工具 %s 沒跑：kernel 退件（%s）' % (tool, code)
    return {'content': content}
