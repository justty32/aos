#!/usr/bin/env python3
"""agent 的現成格庫：think（叫腦）、tool（跑工具）。純標準庫。介面與邊緣狀況見同資料夾 agent.md（實作慣例，還不是規範）。
不是 agent 本體（agent＝fsm＋表）；只是表裡可以直接拿來用的兩格。（10-15 由 aos_agent.py 改名，使用者定）

    python3 aos_agent_lib.py think        （fsm 的格：stdin＝fsm 設定本身＋`fsm_state`（state 窗整份），N-37）
    python3 aos_agent_lib.py tool
    python3 aos_agent_lib.py route        （看最後一則 assistant：有 tool_calls＝next tool，否則 next idle）
    python3 aos_agent_lib.py ask [--frame DIR] [--max-ticks N] bob/agent.json   （agent 當工具，見 aos_agent_call）

設定就是 stdin 那份（＝跑這格的那份 fsm 設定整份，10-15 使用者選乙；fsm 不認得這幾個 key、會忽略）：

    brain     腦的 aos-inst TARGET（或內嵌一張 inst）。腦＝一支 inst：stdin {"messages", "tools"} → stdout 最後一份＝OpenAI assistant 訊息
    tools     {工具名: aos-inst TARGET 或內嵌 inst}（選填）。工具跑的時候環境多一個 AOS_WORK＝這裡的 work。工具的說明寫在那張 inst 的 `_tool`：{"description", "parameters"}
    history   對話檔（OpenAI messages 陣列）；只有方法程式寫它，寫法照 N-05
    system    系統提示檔的路徑（選填；文字／markdown）。think 每次叫腦都把內容當第一則 system 訊息插在 messages 前，
              不寫進 history（改檔下一拍就生效）；沒寫＝不帶；寫了但檔不存在或讀不了＝think 格出錯（N-29）
    work      放 N-call.json（工具的引數）、N-ret.json（工具的 stdout）的資料夾

相對路徑從這格的 cwd 算（＝fsm 的 cwd，除非那張格 inst 自己寫了 cwd），跟指示詞、TARGET 一樣。
巢狀時 stdin 是內層 fsm 的設定，內層沒寫的 key 從外層 cfg 來（N-40：外層 cfg 當預設），所以內層不必再寫一次 brain、history…。

- think：讀 history、組 {"messages", "tools"}、蓋 stdin 跑腦、把回來的 assistant 訊息（拿掉頂層 `usage`）接進 history，
  stdout 吐 {"data": {"content", "tool_calls": [工具名...]}}（沒有 next：下一格寫在表上）。
  history 最後一則已經是 assistant（上一拍接好了才被殺）＝不再叫腦。
- tool：找 history 最後一則 assistant 還沒回的 tool_calls，只跑第一個：引數寫成 work/N-call.json 當 stdin、
  跑那張 inst，回 {"role": "tool", "tool_call_id", "content": JSON 字串＝aos_inst 的結果（N-30：id、code、signal、timed_out…）
  ＋`result`（工具 stdout 最後一份 JSON）（截 8000 字）}；工具起不來、引數不是 JSON、工具名不認得＝content 是 N-29 形狀
  {"error": {"code", "msg"}}（代號 InstError 的原代號、BadArguments、UnknownTool）。
  其餘的回 {"error": {"code": "Skipped", …}}＋stderr 警告。上一拍被殺一半（fsm_state.running 為 true）＝不重跑，
  全回 {"error": {"code": "Interrupted", …}}。
- 出錯（設定不對、腦結束碼非 0、腦回的不是 assistant 訊息）：stderr 吐 {"error": {"code", "msg"}}、退出 1（格出錯）。
  腦出錯時 msg 帶腦自己 stderr 的錯誤（例 `HttpError: … 回 400：…does not support tools`），fsm 會把它記進 last_error。

相依：aos_directives ← aos_cli ← aos_inst ← aos_methods ← aos_agent_lib（也借 aos_ctl_state.write_json）。
"""
import json
import os
import sys

import aos_cli
import aos_inst
import aos_methods
from aos_cli import CliError
from aos_ctl_state import write_json

__all__ = ["AgentError", "LIMIT", "act", "load_config", "pending", "read_history", "route", "think", "tool_specs"]

LIMIT = 8000                                   # 工具結果回給模型最多幾個字
SKIPPED = ("Skipped", "基礎實作一次只跑一個，這個沒跑")
UNKNOWN = ("UnknownTool", "不認得這個工具")
INTERRUPTED = ("Interrupted", "被中斷，沒重跑")


class AgentError(CliError):
    """設定不對、腦出錯。"""


def load_config(doc):
    """stdin 那份（fsm 的設定整份）→ {"brain", "tools", "history", "work"}；history、work 轉絕對路徑（從 cwd 算）。"""
    if not isinstance(doc, dict):
        raise AgentError("NoConfig", "stdin 要是 fsm 的設定（物件），不是 %r" % (doc,))
    cfg = {"brain": doc.get("brain"), "tools": doc.get("tools", {})}
    sysp = doc.get("system")
    if sysp is not None:
        if not (isinstance(sysp, str) and sysp):
            raise AgentError("FieldType", "system 要是檔案路徑字串，不是 %r" % (sysp,))
        cfg["system"] = os.path.abspath(sysp)
    if not (isinstance(cfg["brain"], str) and cfg["brain"] or isinstance(cfg["brain"], dict)):
        raise AgentError("FieldType", "brain 要是 aos-inst TARGET（字串）或一張 inst，不是 %r" % (cfg["brain"],))
    if not (isinstance(cfg["tools"], dict) and all(isinstance(v, (str, dict)) for v in cfg["tools"].values())):
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
    if isinstance(target, dict):                 # 內嵌 inst（aos_agent_call 攤開定義時給的）
        return target, target.get("id")
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


def _with_system(cfg, msgs):
    """有 system 就在最前面插一則 system 訊息（每次現讀檔，不進 history）。"""
    path = cfg.get("system")
    if not path:
        return msgs
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise AgentError("SystemUnreadable", "system 檔 %s 讀不了：%s" % (path, e))
    return [{"role": "system", "content": text}] + msgs


def think(cfg, interrupted=False):
    """叫一次腦，回這格的 data。"""
    msgs = read_history(cfg["history"])
    if msgs and msgs[-1].get("role") == "assistant":         # 上一拍已經接好了（被殺在吐結果之前）
        reply = msgs[-1]
    else:
        req = {"messages": _with_system(cfg, msgs)}
        specs = tool_specs(cfg["tools"])
        if specs:
            req["tools"] = specs
        inst, ident = _load_inst(cfg["brain"])
        try:
            result, reply = aos_methods.run_cell(inst, ident, req)
        except CliError as e:
            raise AgentError(e.code, "腦 %s：%s" % (cfg["brain"], e.msg))
        if result["code"] != 0:
            be = result.get("cell_error")      # 腦 stderr 的 N-29 錯誤＝真正原因，接進自己的錯誤讓 fsm 看得到
            raise AgentError("BrainFailed", "%s: %s" % (be["code"], be["msg"]) if be
                             else "腦 %s 結束碼 %s" % (cfg["brain"], result["code"]))
        if not (isinstance(reply, dict) and reply.get("role") == "assistant"):
            raise AgentError("BadReply", "腦 %s 回的最後一份不是 assistant 訊息：%r" % (cfg["brain"], reply))
        reply = {k: v for k, v in reply.items() if k != "usage"}      # 腦附的用量給 kernel 記額度，不進 history
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


def _err(code, msg):
    """tool 訊息的 content：N-29 形狀的錯誤（JSON 字串）。"""
    return json.dumps({"error": {"code": code, "msg": msg}}, ensure_ascii=False)


def _run_tool(cfg, call, n):
    """跑一個工具，回 tool 訊息的 content（字串）。"""
    fn = call.get("function", {})
    target = cfg["tools"].get(fn.get("name"))
    if target is None:
        return _err(UNKNOWN[0], "%s：%s" % (UNKNOWN[1], fn.get("name")))
    try:
        args = json.loads(fn.get("arguments") or "{}")
    except ValueError:
        return _err("BadArguments", "arguments 不是 JSON：%s" % fn.get("arguments"))
    os.makedirs(cfg["work"], exist_ok=True)
    call_file, ret_file = (os.path.join(cfg["work"], "%d-%s.json" % (n, k)) for k in ("call", "ret"))
    write_json(call_file, args)
    inst, ident = _load_inst(target)
    doc = dict(inst, stdin=call_file, stdout=ret_file, stdout_append=False, stdout_mkdir=False,
               stdin_inherit=False, stdout_inherit=False)
    doc.setdefault("id", ident)
    doc["envs"] = dict(inst.get("envs") or {}, AOS_WORK=cfg["work"])    # agent 當工具時，子 agent 的 frame 預設放這裡
    try:
        result = aos_inst.run(doc)
    except aos_inst.InstError as e:
        return _err(e.code, e.msg)
    try:
        with open(ret_file, encoding="utf-8", errors="replace") as f:
            last = aos_methods.last_json(f.read())
    except OSError:
        last = None
    return json.dumps(dict(result, result=last), ensure_ascii=False)[:LIMIT]


def act(cfg, interrupted=False):
    """跑還沒回的第一個工具呼叫，其餘回「沒跑」；回這格的 data。interrupted＝上一拍被殺一半（不重跑）。"""
    msgs = read_history(cfg["history"])
    calls = pending(msgs)
    if not calls:
        return {"tool": None}
    if interrupted:
        content = _err(*INTERRUPTED)
        write_json(cfg["history"], msgs + [_answer(c, content) for c in calls])
        return {"tool": calls[0]["function"]["name"], "result": content}
    first, rest = calls[0], calls[1:]
    if rest:
        aos_cli.warn("ToolCallsSkipped", "一次回了 %d 個工具呼叫，基礎實作只跑第一個（%s）"
                     % (len(calls), first["function"]["name"]))
    content = _run_tool(cfg, first, len(msgs))
    write_json(cfg["history"], msgs + [_answer(first, content)] + [_answer(c, _err(*SKIPPED)) for c in rest])
    return {"tool": first["function"]["name"], "result": content}


def route(cfg, interrupted=False):
    """看 history 最後一則 assistant：有 tool_calls＝{"next": "tool"}，否則 {"next": "idle", data.reply}。"""
    msgs = read_history(cfg["history"])
    last = msgs[-1] if msgs else {}
    if last.get("role") == "assistant" and last.get("tool_calls"):
        return {"next": "tool", "data": {"tool_calls": [c["function"]["name"] for c in last["tool_calls"]]}}
    return {"next": "idle", "data": {"reply": last.get("content")}}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "ask":
        import aos_agent_call                    # 只有 ask 要 fsm；放這裡免得格庫平常多載一串
        out, code = aos_agent_call.ask(argv[1:], sys.stdin.read())
        aos_cli.emit(out)
        return code
    if len(argv) != 1 or argv[0] not in ("think", "tool", "route"):
        aos_cli.error("Usage", "aos_agent_lib.py think|tool|route（設定＝stdin 那份）｜ask [--frame DIR] [--max-ticks N] AGENT.json")
        return 2
    try:
        args = aos_cli.read_stream(sys.stdin.read())
        arg = args[0] if args else None
        win = arg.get("fsm_state") if isinstance(arg, dict) else None
        interrupted = isinstance(win, dict) and win.get("running") is True      # 上一拍被殺一半（N-38）
        cfg = load_config(arg)
        if argv[0] == "route":
            aos_cli.emit(route(cfg, interrupted))
            return 0
        data = (think if argv[0] == "think" else act)(cfg, interrupted)
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
