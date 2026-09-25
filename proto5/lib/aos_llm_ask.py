"""多問一次模型（第三波 W3-2）：給工具的 `--describe-with-llm`／`--summarize`／`--suggest-with-llm` 共用。

不需要 agent 家：設定跟 `aos-llm call` 同一份（環境 `AOS_LLM_CONFIG`＝llm.json 的絕對路徑），
模型代號 `alias` 沒給＝`default`，沒有 `default` 就用 models 的第一個。
一律 temperature 0、不帶工具、不重試；失敗照 aos-llm call 的代號（EngineFailed／Timeout／ConfigInvalid…）。
回傳的 dict 帶 text、usage（端點原樣，沒回＝None）、ms、alias、model，呼叫的人自己決定記在哪。
"""
import json
import math
import os
import re
import time

from aos_agent_home import AgentError
import aos_llm_call


def pick(config, alias=None):
    """挑模型代號。回 (代號, 設定)。"""
    models = config['models']
    if alias is None:
        alias = 'default' if 'default' in models else next(iter(models), None)
    if alias is None or alias not in models:
        raise AgentError('UnknownModel', 'llm.json 的 models 裡沒有代號 %s（有：%s）'
                         % (alias, '、'.join(models) or '（無）'))
    return alias, models[alias]


def ask(system, user, *, alias=None, env=None, max_tokens=None):
    """問一次。system／user 是字串。回 {"text", "usage", "ms", "alias", "model"}。

    失敗丟 AgentError；HTTP 階段之後的錯另帶 answered（拿到 2xx JSON 沒）、usage、ms、alias、model 屬性。
    """
    env = os.environ if env is None else env
    config = aos_llm_call.load_config(aos_llm_call.config_path(env), env=env)
    alias, entry = pick(config, alias)
    body = {'model': entry['model'], 'temperature': 0,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
    if max_tokens:
        body['max_tokens'] = max_tokens
    seen, start = {}, time.monotonic()
    try:
        msg = aos_llm_call._post(body, entry, alias, seen)
    except AgentError as exc:
        # HTTP 2xx 回了 JSON 物件、但 message 驗不過時，端點已經算了 token：把用量掛在例外上給呼叫端記
        # （exc.answered＝有沒有拿到 2xx 的 JSON 物件；astra S2）
        exc.answered = 'usage' in seen
        exc.usage, exc.ms = seen.get('usage'), int((time.monotonic() - start) * 1000)
        exc.alias, exc.model = alias, entry['model']
        raise
    return {'text': msg.get('content') or '', 'usage': seen.get('usage'),
            'ms': int((time.monotonic() - start) * 1000), 'alias': alias, 'model': entry['model']}


FENCE = re.compile(r'```[ \t]*(?:json|JSON|json5|javascript|js)?[ \t]*\r?\n(.*?)\r?\n?[ \t]*```', re.S)


class _Suspicious(ValueError):
    """整份不收、不再往下找別段（astra S4／09-25 複審 M1、M3）：JSON 語法對但內容可疑
    （重複 key、NaN／Infinity、數字大到變無限大），或整段（某個圍欄）完整解出來只是純量。"""


def _pairs(items):
    out = {}
    for k, v in items:
        if k in out:
            raise _Suspicious('同一個物件裡 key %r 出現兩次' % k)
        out[k] = v
    return out


def _constant(name):
    raise _Suspicious('含 %s（不是標準 JSON）' % name)


def _float(s):
    v = float(s)
    if not math.isfinite(v):
        raise _Suspicious('數字 %s 太大（會變成無限大）' % s[:20])
    return v


_DECODER = json.JSONDecoder(object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)


def _load(t):
    """整段解成物件或陣列；語法錯＝ValueError；整段完整解出來是純量（數字、字串、true…）＝_Suspicious。"""
    val, end = _DECODER.raw_decode(t)
    if t[end:].strip():
        raise ValueError('後面還有字')
    if not isinstance(val, (dict, list)):
        raise _Suspicious('整段只是一個 %s，不是物件或陣列' % type(val).__name__)
    return val


def _top_level(text):
    """文字裡「最外層」的 { 或 [ 起點：一個起點解不開，它裡面的就都不試（深度回到 0 才試下一個）；
    深度 > 0 時 "…" 當字串，裡面的括號不算（09-25 複審 M1）。"""
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text):
        if in_str:
            esc, in_str = (not esc and ch == '\\'), (esc or ch != '"')
            continue
        if ch == '"' and depth:
            in_str = True
        elif ch in '{[':
            if depth == 0:
                yield i
            depth += 1
        elif ch in '}]' and depth:
            depth -= 1


def parse_json(text):
    """從模型回的文字抽出 JSON 物件或陣列：先試整段，再試 ``` 區塊（開了沒收尾的也試），
    再試最外層的 { 或 [ 起能解開的那段（前後多的話不管）。
    解不開、整段只是純量（數字、字串…）、有重複 key、有 NaN／Infinity（含大到溢位的數字）＝AgentError('BadModelOutput')。
    可疑的一碰到就整份不收；外層解不開也不往裡面撿一小塊當答案（astra S4、09-25 複審 M1、M3）。
    欄位對不對不在這裡管：呼叫端各自再驗形狀。"""
    text = (text or '').strip().lstrip('﻿').strip()
    tries = [text] + FENCE.findall(text)
    if text.startswith('```') and len(tries) == 1:        # 開了 ``` 沒收尾（常是被 max_tokens 截斷）
        tries.append(text.split('\n', 1)[1] if '\n' in text else '')
    try:
        for t in tries:
            try:
                return _load(t.strip())
            except _Suspicious:
                raise
            except ValueError:
                pass
        for i in _top_level(text):
            try:
                return _DECODER.raw_decode(text[i:])[0]
            except _Suspicious:
                raise
            except ValueError:
                continue
    except _Suspicious as e:
        raise AgentError('BadModelOutput', '模型回的 JSON 不收：%s' % e)
    raise AgentError('BadModelOutput', '模型回的不是 JSON：%s' % ' '.join(text.split())[:200])


def ask_json(system, user, **kw):
    """問一次、回 (JSON 值, ask 的回傳)。"""
    got = ask(system, user, **kw)
    return parse_json(got['text']), got


def usage_line(got):
    """一行白話：用了多少 token、幾毫秒（給人看）。"""
    u = got.get('usage') or {}
    return '模型 %s（%s）：prompt %s、completion %s token，%d ms' % (
        got.get('alias'), got.get('model'), u.get('prompt_tokens', '?'), u.get('completion_tokens', '?'),
        got.get('ms', 0))
