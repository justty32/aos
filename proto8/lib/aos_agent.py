#!/usr/bin/env python3
"""agent 的兩格膠水：think（叫腦）、tool（跑工具）。純標準庫。介面與邊緣狀況見同資料夾 agent.md（實作慣例，還不是規範）。

    python3 aos_agent.py think AGENT.json        （fsm 的格：stdin 讀 fsm 給的 {"state", "step", "prev"}）
    python3 aos_agent.py tool  AGENT.json

AGENT.json（可接 `#/位置`，通常就是外層 fsm 那份；fsm 不認得這幾個 key、會忽略）：

    brain     腦的 aos-inst TARGET。腦＝一支 inst：stdin {"messages", "tools"} → stdout 最後一份＝OpenAI assistant 訊息
    tools     {工具名: aos-inst TARGET}（選填）。工具的說明寫在那張 inst 的 `_tool`：{"description", "parameters"}
    history   對話檔（OpenAI messages 陣列）；只有方法程式寫它，寫法照 N-05
    work      放 N-call.json（工具的引數）、N-ret.json（工具的 stdout）的資料夾

- think：讀 history、組 {"messages", "tools"}、蓋 stdin 跑腦、把回來的 assistant 訊息接進 history，
  stdout 吐 {"data": {"content", "tool_calls": [工具名...]}}（沒有 next：下一格寫在表上）。
  history 最後一則已經是 assistant（上一拍接好了才被殺）＝不再叫腦。
- tool：找 history 最後一則 assistant 還沒回的 tool_calls，只跑第一個：引數寫成 work/N-call.json 當 stdin、
  跑那張 inst，回 {"role": "tool", "tool_call_id", "content": JSON 字串 {"code", "result"}（截 8000 字）}；
  其餘的回「基礎實作一次只跑一個，這個沒跑」＋stderr 警告。工具名不認得＝回「不認得這個工具」。
  上一拍被殺一半（prev.interrupted）＝不重跑，全回「被中斷」。
- 出錯（設定不對、腦結束碼非 0、腦回的不是 assistant 訊息）：stderr 吐 {"error": {"code", "msg"}}、退出 1（格出錯）。

相依：aos_directives ← aos_cli ← aos_inst ← aos_methods ← aos_agent（也借 aos_ctl_state.write_json）。
"""
import json
import os
import sys

import aos_cli
import aos_inst
import aos_methods
from aos_cli import CliError
from aos_ctl_state import write_json

__all__ = ["AgentError", "LIMIT", "act", "load_config", "pending", "read_history", "think", "tool_specs"]

LIMIT = 8000                                   # 工具結果回給模型最多幾個字
SKIPPED = "基礎實作一次只跑一個，這個沒跑"
UNKNOWN = "不認得這個工具"
INTERRUPTED = "被中斷"


class AgentError(CliError):
    """設定不對、腦出錯。"""


def load_config(target):
    """AGENT.json（TARGET）→ {"brain", "tools", "history", "work"}；history、work 轉絕對路徑。"""
    try:
        doc, _ = aos_cli.load_target(target)
    except CliError as e:
        raise AgentError(e.code, e.msg)
    cfg = {"brain": doc.get("brain"), "tools": doc.get("tools", {})}
    if not (isinstance(cfg["brain"], str) and cfg["brain"]):
        raise AgentError("FieldType", "brain 要是 aos-inst TARGET（字串），不是 %r" % (cfg["brain"],))
    if not (isinstance(cfg["tools"], dict) and all(isinstance(v, str) for v in cfg["tools"].values())):
        raise AgentError("FieldType", "tools 要是 {工具名: aos-inst TARGET}，不是 %r" % (cfg["tools"],))
    for k in ("history", "work"):
        v = doc.get(k)
        if not (isinstance(v, str) and v):
            raise AgentError("FieldType", "%s 要是路徑字串，不是 %r" % (k, v))
        cfg[k] = os.path.abspath(v)
    return cfg


def read_history(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_inst(target):
    try:
        return aos_cli.load_target(target, aos_inst._file)
    except CliError as e:
        raise AgentError(e.code, e.msg)


def tool_specs(tools):
    """{名: TARGET} → OpenAI 的 tools 陣列（說明讀各 inst 的 `_tool`；沒寫＝空說明、不收引數）。"""
    out = []
    for name, target in tools.items():
        t = _load_inst(target)[0].get("_tool") or {}
        out.append({"type": "function", "function": {
            "name": name, "description": t.get("description", ""),
            "parameters": t.get("parameters", {"type": "object", "properties": {}})}})
    return out


def think(cfg, prev=None):
    """叫一次腦，回這格的 data。"""
    msgs = read_history(cfg["history"])
    if msgs and msgs[-1].get("role") == "assistant":         # 上一拍已經接好了（被殺在吐結果之前）
        reply = msgs[-1]
    else:
        req = {"messages": msgs}
        specs = tool_specs(cfg["tools"])
        if specs:
            req["tools"] = specs
        inst, ident = _load_inst(cfg["brain"])
        try:
            result, reply = aos_methods.run_cell(inst, ident, req)
        except CliError as e:
            raise AgentError(e.code, "腦 %s：%s" % (cfg["brain"], e.msg))
        if result["code"] != 0:
            raise AgentError("BrainFailed", "腦 %s 結束碼 %s" % (cfg["brain"], result["code"]))
        if not (isinstance(reply, dict) and reply.get("role") == "assistant"):
            raise AgentError("BadReply", "腦 %s 回的最後一份不是 assistant 訊息：%r" % (cfg["brain"], reply))
        write_json(cfg["history"], msgs + [reply])
    calls = reply.get("tool_calls") or []
    return {"content": reply.get("content"), "tool_calls": [c["function"]["name"] for c in calls]}


def pending(msgs):
    """最後一則 assistant 的 tool_calls 裡，還沒有 tool 訊息回的那些。"""
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].get("role") == "assistant":
            done = {m.get("tool_call_id") for m in msgs[i + 1:] if m.get("role") == "tool"}
            return [c for c in msgs[i].get("tool_calls") or [] if c.get("id") not in done]
    return []


def _answer(call, content):
    return {"role": "tool", "tool_call_id": call["id"], "content": content}


def _run_tool(cfg, call, n):
    """跑一個工具，回 tool 訊息的 content（字串）。"""
    fn = call.get("function", {})
    target = cfg["tools"].get(fn.get("name"))
    if target is None:
        return "%s：%s" % (UNKNOWN, fn.get("name"))
    try:
        args = json.loads(fn.get("arguments") or "{}")
    except ValueError:
        return json.dumps({"code": None, "error": "arguments 不是 JSON：%s" % fn.get("arguments")}, ensure_ascii=False)
    os.makedirs(cfg["work"], exist_ok=True)
    call_file, ret_file = (os.path.join(cfg["work"], "%d-%s.json" % (n, k)) for k in ("call", "ret"))
    write_json(call_file, args)
    inst, ident = _load_inst(target)
    doc = dict(inst, stdin=call_file, stdout=ret_file, stdout_append=False, stdout_mkdir=False,
               stdin_inherit=False, stdout_inherit=False)
    doc.setdefault("id", ident)
    try:
        result = aos_inst.run(doc)
    except aos_inst.InstError as e:
        return json.dumps({"code": None, "error": str(e)}, ensure_ascii=False)
    try:
        with open(ret_file, encoding="utf-8", errors="replace") as f:
            last = aos_methods.last_json(f.read())
    except OSError:
        last = None
    return json.dumps({"code": result["code"], "result": last}, ensure_ascii=False)[:LIMIT]


def act(cfg, prev=None):
    """跑還沒回的第一個工具呼叫，其餘回「沒跑」；回這格的 data。"""
    msgs = read_history(cfg["history"])
    calls = pending(msgs)
    if not calls:
        return {"tool": None}
    if isinstance(prev, dict) and prev.get("interrupted"):
        write_json(cfg["history"], msgs + [_answer(c, INTERRUPTED) for c in calls])
        return {"tool": calls[0]["function"]["name"], "result": INTERRUPTED}
    first, rest = calls[0], calls[1:]
    if rest:
        aos_cli.warn("ToolCallsSkipped", "一次回了 %d 個工具呼叫，基礎實作只跑第一個（%s）"
                     % (len(calls), first["function"]["name"]))
    content = _run_tool(cfg, first, len(msgs))
    write_json(cfg["history"], msgs + [_answer(first, content)] + [_answer(c, SKIPPED) for c in rest])
    return {"tool": first["function"]["name"], "result": content}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] not in ("think", "tool"):
        aos_cli.error("Usage", "aos_agent.py think|tool AGENT.json")
        return 2
    try:
        args = aos_cli.read_stream(sys.stdin.read())
        prev = args[0].get("prev") if args and isinstance(args[0], dict) else None
        cfg = load_config(argv[1])
        data = (think if argv[0] == "think" else act)(cfg, prev)
    except CliError as e:
        aos_cli.error(e.code, e.msg)
        return 1
    except (OSError, ValueError) as e:
        aos_cli.error("ReadFailed", str(e))
        return 1
    aos_cli.emit({"data": data})
    return 0


if __name__ == "__main__":
    sys.exit(main())
