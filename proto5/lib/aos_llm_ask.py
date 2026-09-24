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
    """問一次。system／user 是字串。回 {"text", "usage", "ms", "alias", "model"}。"""
    env = os.environ if env is None else env
    config = aos_llm_call.load_config(aos_llm_call.config_path(env), env=env)
    alias, entry = pick(config, alias)
    body = {'model': entry['model'], 'temperature': 0,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
    if max_tokens:
        body['max_tokens'] = max_tokens
    seen, start = {}, time.monotonic()
    msg = aos_llm_call._post(body, entry, alias, seen)
    return {'text': msg.get('content') or '', 'usage': seen.get('usage'),
            'ms': int((time.monotonic() - start) * 1000), 'alias': alias, 'model': entry['model']}


FENCE = re.compile(r'```(?:json)?\s*\n(.*?)\n\s*```', re.S)


def parse_json(text):
    """從模型回的文字抽出 JSON：先試整段，再試 ``` 區塊，再試第一個 { 或 [ 起能解開的那段。
    解不開＝AgentError('BadModelOutput')。"""
    text = (text or '').strip()
    for t in [text] + FENCE.findall(text):
        try:
            return json.loads(t)
        except ValueError:
            pass
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch in '{[':
            try:
                return dec.raw_decode(text[i:])[0]
            except ValueError:
                continue
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
