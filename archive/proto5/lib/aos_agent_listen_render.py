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
    """輸入封存（<原檔名>.<ns>-<pid>.done）照完整消費 id 分組：[(ns, 那次收的 user 內容…)]，照時間排。

    同一次收件裡照 input 路徑的順序、再照原檔名排（跟 intake 收的順序一樣）；只讀普通檔（不跟 symlink、不開 FIFO）。
    """
    groups = {}
    for order, (folder, name) in enumerate(_done_dirs(base, inputs)):
        try:
            entries = list(folder.iterdir())
        except OSError:
            continue
        for entry in entries:
            match = DONE_NAME.search(entry.name)
            original = entry.name[:match.start()] if match else None
            if not match or (name is not None and original != name):
                continue
            try:
                if entry.is_symlink() or not entry.is_file():
                    continue
            except OSError:
                continue
            key = (int(match.group(1)), int(match.group(2)))
            groups.setdefault(key, []).append((order, original, entry))
    return [(key[0], [c for _, _, entry in sorted(files) for c in _contents(entry)])
            for key, files in sorted(groups.items())]


def _stamp(ns):
    try:
        return datetime.fromtimestamp(ns / 1e9).strftime('%m-%d %H:%M:%S')
    except (OverflowError, OSError, ValueError):
        return None  # 檔名裡的數字不合理：這輪不印時間


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
                stamp = _stamp(groups[k][0])
                if stamp:
                    result[number] = stamp
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


def _flat(value):
    """任何值變成不含換行的字串：字串原樣、別的印 JSON；LF／CR 寫成 \\n／\\r。"""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            value = repr(value)
    return value.replace('\r', '\\r').replace('\n', '\\n')


def _value(value):
    return _cut(_flat(value), SHORT_VALUE)


def _function(call):
    function = call.get('function') if isinstance(call, dict) else None
    return function if isinstance(function, dict) else {}


def call_name(call):
    """工具名（形狀怪的寫 ?），一定不含換行。"""
    name = _function(call).get('name')
    return _flat(name) if isinstance(name, str) and name else '?'


def calls_of(message):
    """一則 assistant 的 tool_calls（不是陣列當沒有）。"""
    value = message.get('tool_calls') if isinstance(message, dict) else None
    return value if isinstance(value, list) else []


def tool_names(message):
    return ', '.join(call_name(c) for c in calls_of(message))


def _text(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False) if value is not None else ''


def call_line(call):
    """--show-calls 的一行：[呼叫 名 k=v …]，值長的截短。"""
    name, raw = call_name(call), _function(call).get('arguments', '')
    if not isinstance(raw, str):
        raw = _text(raw)
    try:
        args = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return '[呼叫 %s 參數不是 JSON：%s]' % (name, _value(raw))
    if isinstance(args, dict):
        text = ' '.join('%s=%s' % (_flat(k), _value(v)) for k, v in args.items())
    else:
        text = _value(args)
    return '[呼叫 %s%s]' % (name, ' ' + _cut(text, SHORT_ARGS) if text else '')


def result_line(name, content):
    """--show-calls 的一行：[結果 名：第一行]，多行就註明共幾行。"""
    lines = _text(content).splitlines()
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
    raw = _function(call).get('arguments', '')
    try:
        text = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    except (ValueError, TypeError):
        text = _text(raw)
    call_id = call.get('id', '?') if isinstance(call, dict) else '?'
    return ['[呼叫 %s id=%s]' % (call_name(call), _flat(call_id))] + _block(text)


def result_full(name, call_id, content):
    text = _text(content)
    return ['[結果 %s id=%s %d 行 %d 字]' % (name, _flat(call_id), len(text.splitlines()), len(text))] + _block(text)


def reply_text(message):
    """沒開 --show-calls 時一則回話的印法：content 原樣；只有 tool_calls 時印 (tool_calls: 名…)。"""
    if not message.get('content') and calls_of(message):
        return '(tool_calls: %s)' % tool_names(message)
    return _text(message.get('content'))


def note_calls(names, message):
    """看到一則 assistant 就更新 tool_call_id → 工具名；後面同 id 的呼叫蓋掉前面的。"""
    if isinstance(message, dict) and message.get('role') == 'assistant':
        for call in calls_of(message):
            if isinstance(call, dict) and isinstance(call.get('id'), str):
                names[call['id']] = call_name(call)


def call_names(history, end):
    """tool_call_id → 工具名：只看 end 以前，所以結果對到的是它之前最近的那個呼叫。"""
    names = {}
    for message in history[:end]:
        note_calls(names, message)
    return names


def event_lines(message, names, calls):
    """一格記憶的印法（calls＝'short'／'full'／None）；user 不印。"""
    if not isinstance(message, dict):
        return []
    role = message.get('role')
    if role == 'assistant':
        if not calls:
            return [reply_text(message)]
        lines = [_text(message['content'])] if message.get('content') else []
        if not calls_of(message) and not lines:
            lines = ['']
        for call in calls_of(message):
            lines.extend([call_line(call)] if calls == 'short' else call_full(call))
        return lines
    if role == 'tool' and calls:
        call_id = message.get('tool_call_id')
        name = names.get(call_id, '?') if isinstance(call_id, str) else '?'
        return [result_line(name, message.get('content'))] if calls == 'short' else \
            result_full(name, call_id, message.get('content'))
    return []


def render(history, indexes, *, calls=None, headers=True, times=None):
    """把記憶裡這些格印成行：換輪時先一行標頭（headers），user 不印。"""
    numbers, _ = rounds(history)
    indexes = list(indexes)
    wanted, names, out, shown = set(indexes), {}, [], None
    for i in range(max(indexes, default=-1) + 1):
        if i not in wanted:
            note_calls(names, history[i])
            continue
        lines = event_lines(history[i], names, calls)
        note_calls(names, history[i])
        if not lines:
            continue
        if headers and numbers[i] != shown:
            out.append(header(numbers[i], times or {}))
            shown = numbers[i]
        out.extend(lines)
    return out
