"""llm_settings - agent-fsm 的腦設定（llm.json 疊 stack 那份）怎麼變成 kernel 請求信的 body：model 填 endpoint 欄、與快取無關的調整鍵放進 request。

使用者 11-10 晚：「3.把fsm認的endpoint這個key，也改名爲model吧」——agent 這邊叫 model，請求信 body 照舊是 endpoint（kernel 不動，「不用管kernel」）；不留舊名。
「4.基本上，model所指向的東西，他就是可以得到快取優勢的東西，然後agent能調的，就是一些與快取無關的。」——model 指的那包（腦與它固定的前綴）吃快取；
TUNING 只收不動到前綴（不讓快取失效）的取樣參數；system、tools、reasoning 類設定不開（代定，清單見 thinking/2026-11/10/self-tools/05）。
11-11 註：system 改由 aos-agent system／self_system 開放（使用者 11-11 選項框裁單獨一支工具，thinking/2026-11/11/self-system），仍不是這裡的鍵。
值可以是字串（aos-agent llm set 一律存字串）或 JSON 數字；轉不了＝ValueError（呼叫端報 CfgBad）。其他鍵不看（C-48）。
kernel 端 endpoint 包的 fixed 欄位照舊蓋過這裡（llm_http：request 先、fixed 蓋上）。"""
import json

TUNING = {"temperature": float, "top_p": float, "max_tokens": int, "seed": int,
          "presence_penalty": float, "frequency_penalty": float, "stop": "stop"}
KEYS = ("model",) + tuple(TUNING)       # interfaces.json 的 llm_keys 照這張抄（aos-agent llm set 對著提醒）


def _value(key, kind, v):
    if kind == "stop":                  # 一個字串＝一個停止句；寫成 JSON 字串陣列＝多個
        if isinstance(v, str) and v.startswith("["):
            try:
                v = json.loads(v)
            except ValueError:
                raise ValueError("%s in llm.json: not a JSON array of strings: %s" % (key, v)) from None
        if isinstance(v, str) and v:
            return [v]
        if isinstance(v, list) and v and all(isinstance(x, str) and x for x in v):
            return v
        raise ValueError("%s in llm.json must be a non-empty string or a JSON array of strings" % key)
    if isinstance(v, bool):
        raise ValueError("%s in llm.json must be a number, not %s" % (key, json.dumps(v)))
    try:
        n = kind(v.strip()) if isinstance(v, str) else kind(v) if isinstance(v, (int, float)) else None
    except ValueError:
        n = None
    if n is None or (kind is int and isinstance(v, float) and v != int(v)):
        raise ValueError("%s in llm.json must be %s, not %s" % (key, "an integer" if kind is int else "a number", json.dumps(v)))
    return n


def body_fields(cfg):
    """回 (endpoint 或 None, {request 調整鍵})。"""
    model = cfg.get("model")
    if "model" in cfg and (not isinstance(model, str) or not model):
        raise ValueError("model in llm.json must be a non-empty string (a brain pack name of the llm kernel)")
    params = {k: _value(k, kind, cfg[k]) for k, kind in TUNING.items() if k in cfg}
    return model, params
