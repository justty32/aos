"""LiteLLM OpenAI 相容非串流傳輸：送一次，不重試、不寫遠端計數。"""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

GATEWAY = "llm.litellm"
METER = "litellm.total_tokens/1"
ENDPOINT = "http://localhost:4000/v1"
MAX_TEXT = 64 * 1024
NOT_BILLED = range(400, 500)        # 4xx 且回應沒帶 usage＝provider 拒絕未計費；408／429 除外


class NoRedirect(HTTPRedirectHandler):
    """不跟重新導向：第一端點可能已受理，3xx 一律當計費未知。"""

    def redirect_request(self, *args, **kw):
        return None


OPENER = build_opener(NoRedirect)
DIRECT = build_opener(NoRedirect, ProxyHandler({}))   # 本機目標一律不走環境 proxy
LOCAL = {"localhost", "127.0.0.1", "::1"}


def urlopen(req, timeout):
    local = (urlsplit(req.full_url).hostname or "").lower() in LOCAL
    return (DIRECT if local else OPENER).open(req, timeout=timeout)


def clean(obj):
    """孤立 surrogate 換成 U+FFFD，保證 raw 能以 UTF-8 存下（其餘原樣）。"""
    return json.loads(json.dumps(obj, ensure_ascii=False).encode("utf-16", "surrogatepass").decode("utf-16", "replace"))


def content_of(choice):
    message = choice.get("message") if isinstance(choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    return content if isinstance(content, str) else None


def pick(choices):
    """取最後一個 content 非空的 choice；LiteLLM 把 sol 的開場白／答案拆成多個 choice。

    全空時退回 choices[0]（原行為）。回 (choice 或 None, 被略過的非空 choice [{index, chars, head}])。
    """
    last = next((i for i in range(len(choices) - 1, -1, -1) if content_of(choices[i])), None)
    if last is None:
        return (choices[0] if choices and isinstance(choices[0], dict) else None), []
    skipped = [{"index": i, "chars": len(content_of(c)), "head": content_of(c)[:80]}
               for i, c in enumerate(choices[:last]) if content_of(c)]
    return choices[last], skipped


def base_url():
    return os.environ.get("AOS7_LITELLM_URL", ENDPOINT)


def send(node, call_id, request, deadline):
    """只有確定拒絕或未送達才退款；其他連線例外交給閘道保留 intent。"""
    start = time.monotonic()
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("AOS7_LITELLM_KEY")
    if key:
        headers["Authorization"] = "Bearer " + key
    req = Request(base_url().rstrip("/") + "/chat/completions",
                  data=json.dumps(request["litellm"], ensure_ascii=False).encode("utf-8"),
                  headers=headers, method="POST")
    try:
        try:
            with urlopen(req, timeout=deadline) as response:
                code, data = response.status, response.read()
        except HTTPError as e:
            with e:
                code, data = e.code, e.read()
    except (ConnectionRefusedError, URLError) as e:
        if not isinstance(e, ConnectionRefusedError) and not isinstance(e.reason, ConnectionRefusedError):
            raise
        return {"status": "reject", "billed": False, "body": "連線被拒，未送達", "usage": None,
                "model": None, "finish_reason": None, "http": None,
                "elapsed": round(time.monotonic() - start, 3), "response": None,
                "choices_n": 0, "skipped": []}
    text = data.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
        response = data[:MAX_TEXT].decode("utf-8", errors="replace")
    else:
        response = parsed
    obj = parsed if isinstance(parsed, dict) else {}
    usage = obj.get("usage") if isinstance(obj.get("usage"), dict) else None
    choices = obj.get("choices") if isinstance(obj.get("choices"), list) else []
    choice, skipped = pick(choices)
    message = choice.get("message") if choice else None
    body = message.get("content") if isinstance(message, dict) else None
    reject = code in NOT_BILLED and code not in (408, 429) and usage is None
    return clean({"status": "reject" if reject else "ok" if code == 200 and choice is not None else "error",
            "billed": not reject, "body": data[:MAX_TEXT].decode("utf-8", errors="replace") if reject else
            body if isinstance(body, str) else None, "usage": None if reject else usage,
            "model": obj.get("model"), "finish_reason": choice.get("finish_reason") if choice else None,
            "http": code, "elapsed": round(time.monotonic() - start, 3), "response": response,
            "choices_n": len(choices), "skipped": skipped})
