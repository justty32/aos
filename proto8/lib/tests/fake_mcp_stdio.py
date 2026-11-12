"""Provide a standard-library MCP stdio server with tools and failure modes for client tests."""

import json
import os
import sys
import time


PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGP4"
    "DwQACfsD/fteaysAAAAASUVORK5CYII="
)
TOOLS = [
    {"name": "echo", "description": "Return the supplied text.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}}},
    {"name": "fail", "description": "Return a tool error result.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "image", "description": "Return a one-pixel PNG image.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "sleep", "description": "Sleep for the supplied number of seconds.",
     "inputSchema": {"type": "object", "properties": {"seconds": {"type": "number"}}}},
    {"name": "big", "description": "Return 200 KiB of text.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "refschema", "description": "Return text declared through a local schema reference.",
     "inputSchema": {"type": "object", "properties": {"text": {"$ref": "#/$defs/text"}},
                     "$defs": {"text": {"type": "string", "description": "Text to return."}}}},
    {"name": "show_env", "description": "Report whether named environment variables are present.",
     "inputSchema": {"type": "object", "properties": {
         "names": {"type": "array", "items": {"type": "string"}}}}},
]


def send(message):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def error(request_id, code, message):
    send({"jsonrpc": "2.0", "id": request_id,
          "error": {"code": code, "message": message}})


def text_result(text, is_error=False):
    result = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return result


def call_tool(name, arguments):
    if name in ("echo", "refschema"):
        return text_result(arguments.get("text", ""))
    if name == "fail":
        return text_result("the fake tool failed", is_error=True)
    if name == "image":
        return {"content": [{"type": "image", "mimeType": "image/png", "data": PNG_BASE64}]}
    if name == "sleep":
        time.sleep(arguments.get("seconds", 0))
        return text_result("sleep finished")
    if name == "big":
        return text_result("x" * (200 * 1024))
    if name == "show_env":
        return text_result(json.dumps({name: name in os.environ
                                      for name in arguments.get("names", [])}))
    raise ValueError("unknown tool")


def sampling_rejected():
    request_id = "fake-sampling-1"
    send({"jsonrpc": "2.0", "id": request_id, "method": "sampling/createMessage",
          "params": {"messages": [], "maxTokens": 1}})
    for line in sys.stdin:
        reply = json.loads(line)
        if reply.get("id") == request_id:
            return reply.get("error", {}).get("code") == -32601
    return False


def main():
    mode = os.environ.get("FAKE_MODE", "")
    if mode == "garbage":
        for _ in range(100):
            sys.stdout.write("fake server startup noise\n")
        sys.stdout.flush()
        for _ in sys.stdin:
            pass
        return

    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        request_id = request["id"]
        method = request.get("method")
        params = request.get("params", {})
        if method == "initialize":
            if mode == "init_fail":
                error(request_id, -32603, "fake initialize failed")
                continue
            result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "fake-mcp-stdio", "version": "1.0"}}
        elif method == "tools/list":
            tools = [dict(tool) for tool in TOOLS]
            if mode == "changed_desc":
                tools[0]["description"] = "Echo text with a changed description."
            result = {"tools": tools}
            if mode == "two_pages":
                if params.get("cursor") == "page-2":
                    result = {"tools": tools[3:]}
                else:
                    result = {"tools": tools[:3], "nextCursor": "page-2"}
        elif method == "tools/call":
            if mode == "die":
                os._exit(0)
            if mode == "ask_sampling" and not sampling_rejected():
                error(request_id, -32603, "sampling was not rejected with method not found")
                continue
            try:
                result = call_tool(params.get("name"), params.get("arguments", {}))
            except (TypeError, ValueError):
                error(request_id, -32602, "invalid tool name or arguments")
                continue
        else:
            error(request_id, -32601, "method is not supported")
            continue
        send({"jsonrpc": "2.0", "id": request_id, "result": result})


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
