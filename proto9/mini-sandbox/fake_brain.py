"""The scripted fake brain of mini's llm kernel (upstream "fake"; copied from pi-sandbox/fake_brain.py, unchanged): answers an OpenAI chat request with the tool call or text a script says, so the whole path is tested without calling a model."""

import json
import time


def step(script, req):
    """Pick the script whose "when" is in the first user message, take step N (N = assistant messages so far).
    A step is {"tool": name, "args": {...}} or {"text": "..."}; past the end it says it is done."""
    msgs = req.get("messages", [])
    first = next((m.get("content") for m in msgs if m.get("role") == "user"), "")
    first = first if isinstance(first, str) else json.dumps(first)
    n = sum(1 for m in msgs if m.get("role") == "assistant")
    for s in script:
        if s["when"] in first:
            return s["steps"][n] if n < len(s["steps"]) else {"text": "FAKE DONE (scripted fake brain)"}
    return {"text": "FAKE OK (llm kernel in fake mode; no model was called)"}


def body(script, model, req):
    st = step(script, req)
    usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
    if "tool" in st:
        call = {"index": 0, "id": "call_fake_%d" % int(time.monotonic() * 1000), "type": "function",
                "function": {"name": st["tool"], "arguments": json.dumps(st["args"])}}
        delta, finish = {"role": "assistant", "content": None, "tool_calls": [call]}, "tool_calls"
        msg = {"role": "assistant", "content": None, "tool_calls": [{k: v for k, v in call.items() if k != "index"}]}
    else:
        delta = {"role": "assistant", "content": st["text"]}
        msg, finish = {"role": "assistant", "content": st["text"]}, "stop"
    if not req.get("stream"):
        return "application/json", json.dumps({
            "id": "fake", "object": "chat.completion", "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "message": msg, "finish_reason": finish}], "usage": usage}).encode()
    out = b""
    for c in ({"choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
              {"choices": [{"index": 0, "delta": {}, "finish_reason": finish}]}, {"choices": [], "usage": usage}):
        c.update({"id": "fake", "object": "chat.completion.chunk", "created": int(time.time()), "model": model})
        out += b"data: " + json.dumps(c).encode() + b"\n\n"
    return "text/event-stream", out + b"data: [DONE]\n\n"
