"""多問一次模型（第三波 W3-2）：給工具的 `--describe-with-llm`／`--summarize`／`--suggest-with-llm` 共用。

不需要 agent 家：設定跟 `aos-llm call` 同一份（環境 `AOS_LLM_CONFIG`＝llm.json 的絕對路徑），
模型代號 `alias` 沒給＝`default`，沒有 `default` 就用 models 的第一個。
一律 temperature 0、不帶工具、不重試；失敗照 aos-llm call 的代號（EngineFailed／Timeout／ConfigInvalid…）。
回傳的 dict 帶 text、usage（端點原樣，沒回＝None）、ms、alias、model，呼叫的人自己決定記在哪。
"""
import json
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
    """JSON 語法對，但內容可疑（重複 key、NaN／Infinity）：整份不收，不再往下找別段（astra S4）。"""


def _pairs(items):
    out = {}
    for k, v in items:
        if k in out:
            raise _Suspicious('同一個物件裡 key %r 出現兩次' % k)
        out[k] = v
    return out


def _constant(name):
    raise _Suspicious('含 %s（不是標準 JSON）' % name)


_DECODER = json.JSONDecoder(object_pairs_hook=_pairs, parse_constant=_constant)


def _load(t):
    """整段解成物件或陣列；語法錯＝ValueError；純量（數字、字串、true…）也算解不開。"""
    val, end = _DECODER.raw_decode(t)
    if t[end:].strip():
        raise ValueError('後面還有字')
    if not isinstance(val, (dict, list)):
        raise ValueError('不是物件或陣列')
    return val


def parse_json(text):
    """從模型回的文字抽出 JSON 物件或陣列：先試整段，再試 ``` 區塊（開了沒收尾的也試），
    再試第一個 { 或 [ 起能解開的那段（前後多的話不管）。
    解不開、只有純量（數字、字串…）、有重複 key、有 NaN／Infinity＝AgentError('BadModelOutput')。
    重複 key 與 NaN 一碰到就整份不收、不往後找別段，免得撿到裡面一小塊當答案（astra S4）。
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
        for i, ch in enumerate(text):
            if ch in '{[':
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
