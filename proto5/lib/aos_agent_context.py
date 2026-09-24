"""送給模型的東西多大（spec/aos-agent/cli-context.md）：aos-agent context 與 talk 的 /context 共用這一份算法。

字數＝人格全文＋每則記憶的 content 與工具參數＋工具表（拿掉 _ 開頭 key 後的 JSON）；
token 是**粗估**（不叫 tokenizer）：ASCII 每 4 字算 1、其他字（中文等）每字算 1，逐段取整後加總。
"""
import json
import math
import os

import aos_agent_info
from aos_agent_listen_render import call_line, call_names, result_line

PREVIEW = 80
RECENT = 3


def tokens(text):
    """粗估 token：ASCII 4 字 1 個、其他每字 1 個。"""
    if not text:
        return 0
    ascii_n = sum(1 for ch in text if ord(ch) < 128)
    return math.ceil(ascii_n / 4) + (len(text) - ascii_n)


def message_size(m):
    """一則記憶的 (字數, token)：content＋每個工具呼叫的 arguments。"""
    parts = [m.get('content') or '']
    parts += [c['function']['arguments'] for c in m.get('tool_calls') or []]
    return sum(len(p) for p in parts), sum(tokens(p) for p in parts)


def history_tokens(history):
    return sum(message_size(m)[1] for m in history)


def rounds(history):
    """把記憶切成輪：一段連續的 user 開一輪，到下一段 user 之前；第一個 user 之前的算第 0 段（start 0）。

    回 [(start, end)]（end 不含），相連、蓋滿整份記憶。
    """
    cuts = [i for i, m in enumerate(history)
            if m['role'] == 'user' and (i == 0 or history[i - 1]['role'] != 'user')]
    if not cuts or cuts[0] != 0:
        cuts = [0] + cuts
    cuts = [c for c in cuts if c < len(history)]
    return [(s, cuts[k + 1] if k + 1 < len(cuts) else len(history)) for k, s in enumerate(cuts)]


def measure(info):
    """回一份 dict：模型、池、system／history／tools 各多大、合計。info＝aos_agent_info.load() 的結果。"""
    history, system, tools = info['history'], info['system'], info['tools']
    roles, chars, toks = {'user': 0, 'assistant': 0, 'tool': 0}, 0, 0
    for m in history:
        roles[m['role']] = roles.get(m['role'], 0) + 1
        c, t = message_size(m)
        chars, toks = chars + c, toks + t
    tool_text = json.dumps(tools, ensure_ascii=False) if tools else ''
    out = {
        'model': info['model'], 'pool': info['llm']['pool'],
        'system': {'chars': len(system), 'tokens': tokens(system)},
        'history': {'count': len(history), 'chars': chars, 'tokens': toks, 'roles': roles,
                    'rounds': len(rounds(history)) if history else 0},
        'tools': {'count': len(tools), 'chars': len(tool_text), 'tokens': tokens(tool_text),
                  'names': [t['function']['name'] for t in tools]},
    }
    out['total'] = {k: out['system'][k] + out['history'][k] + out['tools'][k] for k in ('chars', 'tokens')}
    return out


def by_round(history):
    """每輪一筆：第幾輪、則數範圍、字數、token、開頭那句、最胖的工具結果。"""
    names = call_names(history, len(history))
    out = []
    for n, (s, e) in enumerate(rounds(history), 1):
        part = history[s:e]
        sizes = [message_size(m) for m in part]
        fat = None
        for i, (m, (c, _)) in enumerate(zip(part, sizes)):
            if m['role'] == 'tool' and (fat is None or c > fat['chars']):
                fat = {'tool': names.get(m.get('tool_call_id'), '?'), 'chars': c, 'index': s + i + 1}
        first = next((m.get('content') or '' for m in part if m['role'] == 'user'), '')
        out.append({'round': n, 'from': s + 1, 'to': e, 'count': e - s,
                    'chars': sum(c for c, _ in sizes), 'tokens': sum(t for _, t in sizes),
                    'tools': sum(1 for m in part if m['role'] == 'tool'),
                    'first': ' '.join(first.split()), 'fattest': fat})
    return out


def _cut(text, limit=PREVIEW):
    return text if len(text) <= limit else text[:limit] + '…'


def brief(m, names, full=False):
    """一則一行：user／assistant 帶角色，工具結果印成 [結果 …]；full＝內容不折行不截。"""
    if m.get('role') == 'tool':
        return result_line(names.get(m.get('tool_call_id'), '?'), m.get('content'))
    text = m.get('content') or ''
    parts = [text if full else ' '.join(text.split())] if text else []
    parts += [call_line(c) for c in m.get('tool_calls') or []]
    return '%s: %s' % (m.get('role'), ' '.join(parts))


def last_usage(base):
    """log/usage.jsonl 最後一筆有 prompt_tokens 的：{"prompt", "at"}；沒有＝None。只讀檔尾一段。"""
    path = os.path.join(base, 'log', 'usage.jsonl')
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 65536))
            tail = f.read().decode('utf-8', 'replace').splitlines()
    except OSError:
        return None
    for line in reversed(tail):
        try:
            row = json.loads(line)
            prompt = row['usage']['prompt_tokens']
        except (ValueError, KeyError, TypeError):
            continue
        if str(row.get('batch') or '').startswith('compact-summarize'):
            continue    # compact --summarize 那一問不是送給這個 agent 的記憶（第三波 W3-2）
        if type(prompt) is int:
            return {'prompt': prompt, 'at': str(row.get('at', '?'))[:19].replace('T', ' ')}
    return None


def lines(info, recent=RECENT):
    """人看的幾行（talk /context 與 aos-agent context 印的同一份）。"""
    m = measure(info)
    h, t, s = m['history'], m['tools'], m['system']
    out = ['model  %s（池 %s）' % (m['model'], m['pool']),
           'system %d 字，約 %d token' % (s['chars'], s['tokens']),
           'history %d 則，%d 字，約 %d token，%d 輪（user %d／assistant %d／tool %d）' % (
               h['count'], h['chars'], h['tokens'], h['rounds'], h['roles'].get('user', 0),
               h['roles'].get('assistant', 0), h['roles'].get('tool', 0)),
           'tools  %d 個，%d 字，約 %d token：%s' % (t['count'], t['chars'], t['tokens'], ', '.join(t['names']) or '-'),
           '合計約 %d 字、約 %d token，每次問模型整份送出（token 是粗估；記憶要縮用 aos-agent compact）' % (
               m['total']['chars'], m['total']['tokens'])]
    real = last_usage(info['dir'])
    if real is not None:
        out.append('上一次問模型，端點回報 prompt %s token（log/usage.jsonl %s）' % (real['prompt'], real['at']))
    history = info['history']
    if history and recent:
        names = call_names(history, len(history))
        out.append('最近 %d 則：' % min(recent, len(history)))
        out += ['  ' + _cut(brief(x, names)) for x in history[-recent:]]
    return out


def round_lines(history):
    rows = by_round(history)
    if not rows:
        return ['（記憶是空的）']
    out = ['輪  則        字數   token  工具  開頭']
    for r in rows:
        fat = r['fattest']
        tail = '  最胖：%s %d 字（第 %d 則）' % (fat['tool'], fat['chars'], fat['index']) if fat else ''
        out.append('%-3d %-8s %6d %6d %5d  %s%s' % (r['round'], '%d-%d' % (r['from'], r['to']), r['chars'],
                                                  r['tokens'], r['tools'], _cut(r['first'], 30), tail))
    return out


def main(agent_dir, *, as_json=False, by_rounds=False, recent=RECENT, env=None):
    """aos-agent context：唯讀，不拿鎖、不寫檔。"""
    env = os.environ if env is None else env
    info = aos_agent_info.load(agent_dir, env=env)
    if as_json:
        value = measure(info)
        value['last_usage'] = last_usage(info['dir'])
        if by_rounds:
            value['rounds'] = by_round(info['history'])
        print(json.dumps(value, ensure_ascii=False))
        return 0
    for line in lines(info, recent=recent):
        print(line)
    if by_rounds:
        for line in round_lines(info['history']):
            print(line)
    return 0
