# responses_api.py - llm_http 的 Responses API 寫法（endpoint.api＝"responses"）：chat completions 的請求換成 /responses 的 body、回覆換回 chat 的樣子。
# 11-21 線 top-1121-effort：使用者「換了思考程度就沒了快取，不對吧，理論上應該是要可以的，去想辦法」。上游換頂層 reasoning.effort
# 會改掉藏起來的系統指示、整段前綴快取作廢；OpenAI 文件說改在 input 最後接一個 configuration_update 項目就能換程度、前綴照留
# （developers.openai.com/api/docs/guides/prompt-caching）。chat completions 帶不了這種項目，所以要換程度又要接上快取就走這支。
import json


def _text_parts(content, kind):
    """chat 的 content（字串或分段陣列）→ Responses 的分段；kind＝input_text 或 output_text。"""
    if content is None:
        return []
    if isinstance(content, str):
        return [{"type": kind, "text": content}]
    if not isinstance(content, list):
        raise ValueError("message content must be a string or an array")
    parts = []
    for part in content:
        if not isinstance(part, dict):
            raise ValueError("message content parts must be objects")
        if part.get("type") == "text":
            parts.append({"type": kind, "text": part.get("text", "")})
        elif part.get("type") == "image_url":
            image = part.get("image_url")
            parts.append({"type": "input_image", "image_url": image.get("url") if isinstance(image, dict) else image})
        else:
            parts.append(part)                             # 已是 Responses 的寫法或不認得的：原樣交出去
    return parts


def _tool(tool):
    """chat 的 {"type": "function", "function": {...}} → Responses 的 {"type": "function", "name", ...}；其他種類原樣。
    沒寫 strict 的 function tool 補 "strict": false：Responses 沒帶 strict 就當 true，把每個屬性都改成必填、
    模型只好把選填參數硬填上（11-23 線 eca-aos-core-1123 對 LiteLLM 的 chatgpt 後端實測：回顯 strict true、
    required 列滿全部屬性；帶 false 就只給要的參數）。chat completions 的 strict 預設本來就是 false，補上才跟它一致。"""
    if isinstance(tool, dict) and tool.get("type") == "function" and isinstance(tool.get("function"), dict):
        tool = dict({"type": "function"}, **tool["function"])
    if isinstance(tool, dict) and tool.get("type") == "function" and "strict" not in tool:
        tool = dict(tool, strict=False)
    return tool


def _tool_choice(choice):
    if isinstance(choice, dict) and choice.get("type") == "function" and isinstance(choice.get("function"), dict):
        return {"type": "function", "name": choice["function"].get("name")}
    return choice


def body(request, reasoning_effort=None):
    """chat completions 的 request（已蓋上 fixed、model）→ /responses 的 body。
    system 訊息併成 instructions；reasoning_effort（llm kernel 給的思考程度）＝input 最後接一個 configuration_update，
    頂層的 reasoning 不動，前綴快取才接得上。request 自己的 reasoning_effort（送上游的參數）＝頂層 reasoning.effort。"""
    instructions, items = [], []
    for message in request["messages"]:
        if not isinstance(message, dict):
            raise ValueError("messages must be objects")
        role = message.get("role")
        if role == "system":
            content = message.get("content")
            instructions.append(content if isinstance(content, str)
                                else "".join(p.get("text", "") for p in content if isinstance(p, dict)))
        elif role == "tool":
            content = message.get("content")
            items.append({"type": "function_call_output", "call_id": message.get("tool_call_id"),
                          "output": content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)})
        elif role == "assistant":
            parts = _text_parts(message.get("content"), "output_text")
            if parts:
                items.append({"type": "message", "role": "assistant", "content": parts})
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                items.append({"type": "function_call", "call_id": call.get("id"), "name": function.get("name"),
                              "arguments": function.get("arguments", "")})
        else:
            items.append({"type": "message", "role": role, "content": _text_parts(message.get("content"), "input_text")})
    if reasoning_effort is not None:
        items.append({"type": "configuration_update", "reasoning": {"effort": reasoning_effort}})
    out = {key: value for key, value in request.items() if key not in ("messages", "tools", "tool_choice",
                                                                       "max_tokens", "reasoning_effort")}
    out["input"] = items
    if instructions:
        out["instructions"] = "\n\n".join(instructions)
    if "tools" in request:
        out["tools"] = [_tool(tool) for tool in request["tools"]]
    if "tool_choice" in request:
        out["tool_choice"] = _tool_choice(request["tool_choice"])
    if "max_tokens" in request:
        out["max_output_tokens"] = request["max_tokens"]
    if "reasoning_effort" in request:
        out["reasoning"] = dict(out.get("reasoning") or {}, effort=request["reasoning_effort"])
    return out


def reply(data):
    """/responses 的回覆 → (chat 的 assistant 訊息, chat 寫法的 usage)。形狀不對丟 ValueError／KeyError／TypeError。"""
    if not isinstance(data.get("output"), list):
        raise ValueError("output is not an array")
    texts, calls = [], []
    for item in data["output"]:
        if not isinstance(item, dict):
            raise ValueError("output items must be objects")
        if item.get("type") == "message":
            texts += [part.get("text", "") for part in item.get("content") or []
                      if isinstance(part, dict) and part.get("type") == "output_text"]
        elif item.get("type") == "function_call":
            calls.append({"id": item["call_id"], "type": "function",
                          "function": {"name": item["name"], "arguments": item.get("arguments", "")}})
    message = {"role": "assistant", "content": "".join(texts) if texts else None}
    if calls:
        message["tool_calls"] = calls
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return message, None
    out = {"prompt_tokens": usage.get("input_tokens"), "completion_tokens": usage.get("output_tokens"),
           "total_tokens": usage.get("total_tokens")}
    cached = (usage.get("input_tokens_details") or {}).get("cached_tokens")
    if cached is not None:
        out["prompt_tokens_details"] = {"cached_tokens": cached}
    reasoning = (usage.get("output_tokens_details") or {}).get("reasoning_tokens")
    if reasoning is not None:
        out["completion_tokens_details"] = {"reasoning_tokens": reasoning}
    return message, out
