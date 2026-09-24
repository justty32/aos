"""listen 的印法（aos-agent.md §1.5）：挑最後 N 則回話、輪次標頭、工具呼叫的簡化／完整行。

記憶本身沒有時間戳；每輪的時間取自輸入封存檔名裡的消費 id（收下那輪輸入的時刻），對不上就不印時間。
"""
from datetime import datetime
import json
import os
from pathlib import Path
import re

SHORT_VALUE = 40     # --show-calls：每個參數值最多幾字
SHORT_ARGS = 120     # --show-calls：整段參數最多幾字
SHORT_RESULT = 60    # --show-calls：結果第一行最多幾字
FULL_LIMIT = 4000    # --show-calls-full：參數／結果各最多幾字

DONE_NAME = re.compile(r'\.(\d+)-(\d+)\.done$')


def is_reply(message):
    """「回話」＝assistant 有字，或沒叫工具（空字串也算）；只叫工具的那則不算。"""
    content = message.get('content')
    return bool(content) or not message.get('tool_calls')


def pick(history, n):
    """最後 n 則回話的索引（照時間順序）與要印的起點（上一則回話的下一格）。

    最後一則 assistant 只有 tool_calls（輪還沒走完）時也算一則，跟以前的 --last 一樣。
    """
    assist = [i for i, m in enumerate(history) if isinstance(m, dict) and m.get('role') == 'assistant']
    replies = [i for i in assist if is_reply(history[i])]
    if assist and (not replies or replies[-1] != assist[-1]):
        replies.append(assist[-1])
    picked = replies[-n:]
    start = replies[-n - 1] + 1 if len(replies) > n else 0
    return picked, start, len(replies)


def rounds(history):
    """每格屬第幾輪：連續的 user 算一輪的開頭；回 [輪次…] 與每輪第一句 user 的內容。"""
    numbers, openers, current, previous = [], {}, 0, None
    for message in history:
        role = message.get('role') if isinstance(message, dict) else None
        if role == 'user' and previous != 'user':
            current += 1
            openers[current] = message.get('content')
        numbers.append(current)
        previous = role
    return numbers, openers


def _done_dirs(base, inputs):
    for value in inputs:
        path = Path(os.path.abspath(os.path.join(base, value)))
        if path.is_dir():
            yield path / 'done', None
        else:
            yield path.parent / 'done', path.name


def _contents(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        return []
    values = value if isinstance(value, list) else [value]
    return [v if isinstance(v, str) else v.get('content') for v in values
            if isinstance(v, str) or (isinstance(v, dict) and v.get('role') == 'user')]


def intake_times(base, inputs):
    """輸入封存（<原檔名>.<ns>-<pid>.done）照消費 id 分組：[(ns, 那次收的 user 內容…)]，照時間排。"""
    groups = {}
    for folder, name in _done_dirs(base, inputs):
        try:
            entries = sorted(folder.iterdir())
        except OSError:
            continue
        for entry in entries:
            match = DONE_NAME.search(entry.name)
            if not match or (name is not None and entry.name[:match.start()] != name):
                continue
            groups.setdefault(int(match.group(1)), []).extend(_contents(entry))
    return sorted(groups.items())


def round_times(history, base, inputs):
    """每輪開頭那句對到封存裡同內容的那次收件（往後找、不回頭），回 {輪次: 'MM-DD HH:MM:SS'}。"""
    if base is None or not inputs:
        return {}
    groups = intake_times(base, inputs)
    _, openers = rounds(history)
    result, j = {}, 0
    for number in sorted(openers):
        for k in range(j, len(groups)):
            if groups[k][1] and groups[k][1][0] == openers[number]:
                result[number] = datetime.fromtimestamp(groups[k][0] / 1e9).strftime('%m-%d %H:%M:%S')
                j = k + 1
                break
    return result


def header(number, times):
    if number == 0:
        return '── 記憶開頭（還沒有你的話）──'
    stamp = times.get(number)
    return '── 第 %d 輪 · 收話 %s ──' % (number, stamp) if stamp else '── 第 %d 輪 ──' % number


def _cut(text, limit):
    return text if len(text) <= limit else text[:limit] + '…'


def _value(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return _cut(text.replace('\n', '\\n'), SHORT_VALUE)


def call_line(call):
    """--show-calls 的一行：[呼叫 名 k=v …]，值長的截短。"""
    function = call.get('function') or {}
    name, raw = function.get('name', '?'), function.get('arguments', '')
    try:
        args = json.loads(raw) if raw.strip() else {}
    except (ValueError, AttributeError):
        return '[呼叫 %s 參數不是 JSON：%s]' % (name, _value(str(raw)))
    if isinstance(args, dict):
        text = ' '.join('%s=%s' % (k, _value(v)) for k, v in args.items())
    else:
        text = _value(args)
    return '[呼叫 %s%s]' % (name, ' ' + _cut(text, SHORT_ARGS) if text else '')


def result_line(name, content):
    """--show-calls 的一行：[結果 名：第一行]，多行就註明共幾行。"""
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    lines = text.splitlines()
    first = next((l.strip() for l in lines if l.strip()), '')
    if not first:
        return '[結果 %s：（空）]' % name
    count = '' if len(lines) <= 1 else ' %d 行' % len(lines)
    return '[結果 %s%s：%s]' % (name, count, _cut(first, SHORT_RESULT))


def _block(text):
    full = len(text)
    if full > FULL_LIMIT:
        text = text[:FULL_LIMIT]
    parts = text.split('\n')
    if len(parts) > 1 and parts[-1] == '':
        parts.pop()  # 結尾換行不另印一行空白
    lines = ['  ' + line for line in parts]
    if full > FULL_LIMIT:
        lines.append('  …（截斷：共 %d 字，只印前 %d 字；全文在記憶檔）' % (full, FULL_LIMIT))
    return lines


def call_full(call):
    function = call.get('function') or {}
    raw = function.get('arguments', '')
    try:
        text = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    except (ValueError, TypeError):
        text = str(raw)
    return ['[呼叫 %s id=%s]' % (function.get('name', '?'), call.get('id', '?'))] + _block(text)


def result_full(name, call_id, content):
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    return ['[結果 %s id=%s %d 行 %d 字]' % (name, call_id, len(text.splitlines()), len(text))] + _block(text)


def reply_text(message):
    """沒開 --show-calls 時一則回話的印法：content 原樣；只有 tool_calls 時印 (tool_calls: 名…)。"""
    if not message.get('content') and message.get('tool_calls'):
        return '(tool_calls: %s)' % ', '.join(c['function']['name'] for c in message['tool_calls'])
    return message.get('content') or ''


def call_names(history, end):
    """tool_call_id → 工具名（看 end 以前所有 assistant 的 tool_calls）。"""
    names = {}
    for message in history[:end]:
        if isinstance(message, dict) and message.get('role') == 'assistant':
            for call in message.get('tool_calls') or []:
                names[call.get('id')] = (call.get('function') or {}).get('name', '?')
    return names


def event_lines(message, names, calls):
    """一格記憶的印法（calls＝'short'／'full'／None）；user 不印。"""
    role = message.get('role')
    if role == 'assistant':
        if not calls:
            return [reply_text(message)]
        lines = [message['content']] if message.get('content') else []
        if not message.get('tool_calls') and not lines:
            lines = ['']
        for call in message.get('tool_calls') or []:
            lines.extend([call_line(call)] if calls == 'short' else call_full(call))
        return lines
    if role == 'tool' and calls:
        call_id = message.get('tool_call_id')
        name = names.get(call_id, '?')
        return [result_line(name, message.get('content'))] if calls == 'short' else \
            result_full(name, call_id, message.get('content'))
    return []


def render(history, indexes, *, calls=None, headers=True, times=None):
    """把記憶裡這些格印成行：換輪時先一行標頭（headers），user 不印。"""
    numbers, _ = rounds(history)
    names = call_names(history, len(history))
    out, shown = [], None
    for i in indexes:
        lines = event_lines(history[i], names, calls)
        if not lines:
            continue
        if headers and numbers[i] != shown:
            out.append(header(numbers[i], times or {}))
            shown = numbers[i]
        out.extend(lines)
    return out
