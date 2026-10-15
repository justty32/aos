#!/usr/bin/env python3
"""agent 的現成格庫：think（叫腦）、tool（跑工具）、route、intake、done，外加給 loop.json 用的 fsm。純標準庫。介面與邊緣狀況見同資料夾 agent.md
（實作慣例，還不是規範）。不是 agent 本體（agent＝fsm＋表）；只是表裡可以直接拿來用的幾格。（10-15 由 aos_agent.py 改名）

    python3 aos_agent_lib.py think
    python3 aos_agent_lib.py tool
    python3 aos_agent_lib.py route [--done 名]   （看最後一則 assistant：有 tool_calls＝next tool，否則 next idle（或 --done 給的名））
    python3 aos_agent_lib.py intake        （args.json 接進 history（沒有就生、有就接在後面），接完改名 args.taken.json）
    python3 aos_agent_lib.py done          （寫 ret.json＝最後一句；loop 停靠 fsm 結束那行＋loop 的 stop_on_end）
    python3 aos_agent_lib.py fsm [NAME]    （照 lookup() 找 NAME（預設 fsm.json），跑一拍 aos_fsm；定義資料夾的 loop.json 用它，
                                            不必寫自己的路徑）

PATH 上有 proto8/bin 時寫 `aos agent think` 等（C-50：葉子用指令名）。

**設定從哪來**（10-15 收工後：fsm 不再餵格 stdin，N-37）：stdin 那份（那張格 inst 自己的 `stdin` 指的檔；沒有＝空）的 key
優先，沒寫的照 frame（＝cwd）找——`lookup()`：先找 cwd，找不到照 cwd 裡 `frame.json` 的 `parent` 往上一層找（C-46）：
brain＝`brain.json`、tools＝`tools/*.json`（各層逐項合併、近的蓋過遠的；名字＝檔名去掉 .json）、system＝`system.md`（有才帶）、
history＝cwd 的 `history.json`、work＝cwd 的 `work/`。各 key：

    brain     腦的 aos-inst TARGET（或內嵌一張 inst）。腦＝一支 inst：stdin {"messages", "tools"} → stdout 最後一份＝OpenAI assistant 訊息
    tools     {工具名: aos-inst TARGET 或內嵌 inst}（選填）。工具的說明寫在那張 inst 的 `_tool`：{"description", "parameters"}
    history   對話檔（OpenAI messages 陣列）；只有方法程式寫它，寫法照 N-05
    system    系統提示檔的路徑（選填；文字／markdown）。think 每次叫腦都把內容當第一則 system 訊息插在 messages 前，
              不寫進 history（改檔下一拍就生效）；沒寫＝不帶；寫了但檔不存在或讀不了＝think 格出錯（N-29）
    work      工具每次在這裡開一個新號碼資料夾 work/<n>/ 跑（args.json＝引數、stdout.json＝工具的 stdout）；
              think.json、.tool-running.json 也放這裡

    halt_after  選填，預設 3：think 連錯幾次就不再報錯、改回 {"next": halt_state}（N-38：連錯停住是格自己的事）
    halt_state  選填，預設 "halted"

相對路徑從這格的 cwd 算（＝fsm 的 cwd，除非那張格 inst 自己寫了 cwd），跟指示詞、TARGET 一樣。

- think：讀 history、組 {"messages", "tools"}、蓋 stdin 跑腦、把回來的 assistant 訊息（拿掉頂層 `usage`）接進 history，
  stdout 吐 {"data": {"content", "tool_calls": [工具名...]}}（沒有 next：下一格寫在表上）。
  history 最後一則已經是 assistant（上一拍接好了才被殺）＝不再叫腦。
- tool：找 history 最後一則 assistant 還沒回的 tool_calls，一拍內照順序全部跑（10-15 使用者「都按照推薦」；原本只跑第一個、
  其餘回 Skipped）：每個都 mkdir 搶一個新號碼資料夾 work/<n>/，引數寫成那裡的 args.json 當 stdin、stdout 接到那裡的
  stdout.json，在那裡跑那張 inst（inst 自己寫了 cwd 就照它的），回 {"role": "tool", "tool_call_id", "content": JSON 字串＝
  aos_inst 的結果（N-30：id、code、signal、timed_out…）＋`result`（工具 stdout 最後一份 JSON）（截 8000 字）}；
  工具起不來、引數不是 JSON、工具名不認得＝content 是 N-29 形狀 {"error": {"code", "msg"}}（代號 InstError 的原代號、
  ArgumentsBad、ToolUnknown）。**agent 只看到工具清單**（名字、`_tool` 的說明與參數）：工具裡面是什麼（是不是另一個
  agent、它的 frame 放哪、綁什麼腦）這層不知道、不傳、不繼承（C-52 徹底切割，10-15 深夜使用者）。
- 腦與工具的 stderr 這層都不讀（C-52）：腦結束碼非 0＝BrainFailed「腦 X 結束碼 N」；要看原因就在那張 inst 寫 stderr 檔。
  每跑完一個就接進 history（中途被殺，跑完的不重跑）。上一拍被殺一半（work/.tool-running.json 還在、記的是還沒回的第一個
  tool_call id＝跑過一半）＝那個不重跑、回 {"error": {"code": "Interrupted", …}}，其餘照跑。
  stdout 的 data：{"tool": 第一個名, "result": 第一個結果, "tools": [名…], "results": [結果…]}。
- 出錯（設定不對、腦結束碼非 0、腦回的不是 assistant 訊息）：stderr 吐 {"error": {"code", "msg"}}、退出 1（格出錯）。
  think 連錯：次數記在 work/think.json（think 自己的私檔，成功一次就刪），到 halt_after 次＝不報錯，**自己**把要交出去的錯
  寫成 cwd 的 ret.json（{"error": {"code", "msg"}}），再吐 {"next": halt_state, "data": {"error"}}。halt_state 寫在表的 `end`、
  不寫進 `states`（N-40：next 不在表裡、在 end 裡＝這個 fsm 結束），不經 done 格——格之間不互看私檔（C-52；10-15 使用者
  「都同意。」，盤點第 8 條；原本 done 讀 think.json 寫錯誤的 ret.json）。

相依：aos_directives ← aos_cli ← aos_inst ← aos_methods ← aos_agent_lib（也借 aos_ctl_state.write_json、aos_frame 的 lookup；fsm 子命令才載 aos_fsm）。
"""
import json
import os
import sys

import aos_cli
import aos_inst
import aos_methods
from aos_cli import CliError
from aos_ctl_state import write_json
from aos_frame import chain, lookup, lookup_dir   # frame 查找拆到 aos_frame.py；這裡照樣 re-export

__all__ = ["AgentError", "LIMIT", "act", "chain", "done", "intake", "load_config", "lookup", "lookup_dir", "new_dir",
           "pending", "read_history", "route", "think", "tool_specs"]


LIMIT = 8000                                   # 工具結果回給模型最多幾個字
UNKNOWN = ("ToolUnknown", "不認得這個工具")
INTERRUPTED = ("Interrupted", "被中斷，沒重跑")


class AgentError(CliError):
    """設定不對、腦出錯。"""


def load_config(doc, need_brain=True):
    """設定（stdin 那份；None＝沒有）→ {"brain", "tools", "history", "work", ["system"]}。沒寫的照 frame（cwd）找。"""
    if doc is None:
        doc = {}
    if not isinstance(doc, dict):
        raise AgentError("ConfigMissing", "stdin 要是設定（物件），不是 %r" % (doc,))
    doc = dict(doc)
    if "brain" not in doc:
        doc["brain"] = lookup("brain.json")
    if "tools" not in doc:
        doc["tools"] = {n[:-5]: p for n, p in lookup_dir("tools").items() if n.endswith(".json")}
    if "system" not in doc:
        doc["system"] = lookup("system.md")
    doc.setdefault("history", "history.json")
    doc.setdefault("work", "work")
    cfg = {"brain": doc.get("brain"), "tools": doc.get("tools", {}),
           "halt_after": doc.get("halt_after", 3), "halt_state": doc.get("halt_state", "halted")}
    sysp = doc.get("system")
    if sysp is not None:
        if not (isinstance(sysp, str) and sysp):
            raise AgentError("FieldType", "system 要是檔案路徑字串，不是 %r" % (sysp,))
        cfg["system"] = os.path.abspath(sysp)
    if need_brain and not (isinstance(cfg["brain"], str) and cfg["brain"] or isinstance(cfg["brain"], dict)):
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
    if isinstance(target, dict):                 # 內嵌 inst
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


def think(cfg):
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
        if result["code"] != 0:                # 腦的 stderr 不讀（C-52 切乾淨）：要看原因就在 brain.json 寫 stderr 檔
            raise AgentError("BrainFailed", "腦 %s 結束碼 %s" % (cfg["brain"], result["code"]))
        if not (isinstance(reply, dict) and reply.get("role") == "assistant"):
            raise AgentError("ReplyBad", "腦 %s 回的最後一份不是 assistant 訊息：%r" % (cfg["brain"], reply))
        reply = {k: v for k, v in reply.items() if k != "usage"}      # 腦附的用量給 kernel 記額度，不進 history
        write_json(cfg["history"], msgs + [reply])
        try:
            os.remove(_fails_file(cfg))                              # 成功一次：連錯歸零
        except OSError:
            pass
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


def new_dir(base):
    """base/<n>/：挑第一個還沒有的號碼建起來（mkdir 原子，兩個同時叫不會撞），回絕對路徑。"""
    os.makedirs(base, exist_ok=True)
    n = 1
    while True:
        p = os.path.join(base, str(n))
        try:
            os.mkdir(p)
            return p
        except FileExistsError:
            n += 1


def _run_tool(cfg, call):
    """跑一個工具，回 tool 訊息的 content（字串）。每次在 work/<n>/ 新資料夾跑，引數寫成那裡的 args.json。"""
    fn = call.get("function", {})
    target = cfg["tools"].get(fn.get("name"))
    if target is None:
        return _err(UNKNOWN[0], "%s：%s" % (UNKNOWN[1], fn.get("name")))
    try:
        args = json.loads(fn.get("arguments") or "{}")
    except ValueError:
        return _err("ArgumentsBad", "arguments 不是 JSON：%s" % fn.get("arguments"))
    try:
        inst, ident = _load_inst(target)
    except AgentError as e:
        return _err(e.code, e.msg)
    d = new_dir(cfg["work"])
    call_file, out_file = os.path.join(d, "args.json"), os.path.join(d, "stdout.json")
    write_json(call_file, args)
    doc = dict(inst, stdin=call_file, stdout=out_file, stdout_append=False, stdout_mkdir=False,
               stdin_inherit=False, stdout_inherit=False)
    doc.setdefault("id", ident)
    doc.setdefault("cwd", d)                     # 工具在 work/<n>/ 跑（inst 自己寫了 cwd 就照它的）；裡面是什麼 agent 不管（C-52）
    try:
        result = aos_inst.run(doc)
    except aos_inst.InstError as e:
        return _err(e.code, e.msg)
    try:
        with open(out_file, encoding="utf-8", errors="replace") as f:
            last = aos_methods.last_json(f.read())
    except OSError:
        last = None
    return json.dumps(dict(result, result=last), ensure_ascii=False)[:LIMIT]


def act(cfg):
    """照順序跑完最後一則 assistant 還沒回的每個工具呼叫（一拍內），每跑完一個就把它的 tool 訊息接進 history；回這格的 data。
    上一拍被殺一半（.tool-running.json 還在、記的是還沒回的第一個 id）＝那個不重跑、回 Interrupted，其餘照跑。"""
    msgs = read_history(cfg["history"])
    calls = pending(msgs)
    if not calls:
        return {"tool": None}
    mark = os.path.join(cfg["work"], ".tool-running.json")     # 跑每個工具前寫、跑完刪：還在且同一個 id＝上一拍被殺一半
    interrupted = False
    try:
        with open(mark, encoding="utf-8") as f:
            interrupted = json.load(f).get("id") == calls[0].get("id")
    except (OSError, ValueError, AttributeError):
        pass
    os.makedirs(cfg["work"], exist_ok=True)
    names, results = [], []
    for i, call in enumerate(calls):
        if i == 0 and interrupted:
            content = _err(*INTERRUPTED)
        else:
            write_json(mark, {"id": call.get("id")})
            content = _run_tool(cfg, call)
        msgs = msgs + [_answer(call, content)]
        write_json(cfg["history"], msgs)                         # 一個一個接：中途被殺，跑完的不會重跑
        _rm(mark)
        names.append(call.get("function", {}).get("name"))
        results.append(content)
    return {"tool": names[0], "result": results[0], "tools": names, "results": results}


def route(cfg, done="idle"):
    """看 history 最後一則 assistant：有 tool_calls＝{"next": "tool"}，否則 {"next": done（預設 idle）, data.reply}。"""
    msgs = read_history(cfg["history"])
    last = msgs[-1] if msgs else {}
    if last.get("role") == "assistant" and last.get("tool_calls"):
        return {"next": "tool", "data": {"tool_calls": [c["function"]["name"] for c in last["tool_calls"]]}}
    return {"next": done, "data": {"reply": last.get("content")}}


def _rm(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _fails_file(cfg):
    return os.path.join(cfg["work"], "think.json")


def _think_failed(cfg, e):
    """think 出錯：記一次；到 halt_after 次＝自己寫好 ret.json 的錯、回 {"next": halt_state, "data": {"error"}}（不再報錯），
    否則回 None（照常報錯）。"""
    path = _fails_file(cfg)
    try:
        with open(path, encoding="utf-8") as f:
            n = int(aos_cli.expand(json.load(f)).get("val", 0))   # 計數長成物件：{"val": 次數, "error"}（C-55）
    except (OSError, ValueError, AttributeError, TypeError):
        n = 0
    n += 1
    err = {"code": e.code, "msg": e.msg}
    os.makedirs(cfg["work"], exist_ok=True)
    write_json(path, {"val": n, "error": err})
    limit = cfg.get("halt_after")
    if isinstance(limit, int) and not isinstance(limit, bool) and n >= limit:
        write_json("ret.json", {"error": err})        # 要交出去的錯 think 自己寫好（done 不讀 think 的私檔）
        return {"next": cfg.get("halt_state") or "halted", "data": {"error": err}}
    return None


TAKEN = "args.taken.json"                      # 接進 history 之後 args.json 改成這個名字（同一份不會接兩次）


def intake(cfg):
    """把 cwd 的 args.json（實引數）接進 history，接完改名成 args.taken.json（同一份不會接兩次），並刪掉上一輪的 ret.json：
    - {"history": [...]}＝history 換成它（呼叫方整段綁進來）；
    - {"question": "…"}＝frame 還沒有 history 就生一份 [user 訊息]，已經有就接在後面當一則新的 user 訊息（同一個 frame 續聊）；
      history 最後一則已經是同一句 user 訊息（上一拍接好了、改名前被殺）＝不再接。
    沒有 args.json：已經有 history＝照舊往下（呼叫方綁了 history，或接著上次的）；也沒有 history＝HistoryMissing。"""
    have = os.path.exists(cfg["history"])
    try:
        with open("args.json", encoding="utf-8") as f:
            arg = json.load(f)
    except FileNotFoundError:
        if have:
            return {}
        raise AgentError("HistoryMissing", "frame 沒有 history，也沒有 args.json")
    except OSError as e:
        raise AgentError("ReadFailed", "args.json 讀不了：%s" % e)
    except ValueError as e:
        raise AgentError("ArgumentsBad", "args.json 不是 JSON：%s" % e)
    hist = arg.get("history") if isinstance(arg, dict) else None
    if hist is None:
        q = arg.get("question") if isinstance(arg, dict) else None
        if not isinstance(q, str):
            raise AgentError("FieldType", "args.json 要有 question（字串）或 history")
        msg = {"role": "user", "content": q}
        hist = read_history(cfg["history"]) if have else []
        if not (hist and hist[-1] == msg):
            hist = hist + [msg]
    elif not isinstance(hist, list):
        raise AgentError("FieldType", "args.json 的 history 要是訊息陣列，不是 %r" % (hist,))
    write_json(cfg["history"], hist)
    os.replace("args.json", TAKEN)
    try:
        os.remove("ret.json")                    # 新的一問：上一輪的回傳清掉（這次沒跑完就沒有 ret.json）
    except FileNotFoundError:
        pass
    return {}


def _last_text(msgs):
    for m in reversed(msgs):
        if m.get("role") == "assistant" and m.get("content"):
            return m["content"]
    return None


def done(cfg):
    """收尾：寫 cwd 的 ret.json＝{"reply": 最後一句}。只看自己的輸入（history）；think 連錯停住時 ret.json 由 think 自己寫、
    不經 done。不碰 ctl：done 放在表的 end 裡，fsm 結束那行帶 `"end": true`，拍它的 loop 寫了 stop_on_end 就停（10-15 使用者）。"""
    try:
        msgs = read_history(cfg["history"])
    except (OSError, ValueError):
        msgs = []
    ret = {"reply": _last_text(msgs)}
    write_json("ret.json", ret)
    return {"data": ret}


def run_fsm(name="fsm.json"):
    """照 lookup() 找 name（frame → frame.json parent 鏈），跑一拍 aos_fsm；回退出碼。找不到＝FsmMissing、1（同 fsm 自己出錯）。"""
    path = lookup(name)
    if path is None:
        aos_cli.error("FsmMissing", "frame %s 與它的 parent 鏈裡都找不到 %s" % (os.getcwd(), name))
        return 1
    import aos_fsm                               # 只有這個子命令要 fsm；放這裡免得格庫平常多載一串
    return aos_fsm.main([path])


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd, opts = (argv[0] if argv else None), argv[1:]
    if cmd == "fsm" and len(opts) <= 1:
        return run_fsm(*opts)
    route_done = "idle"
    if cmd == "route" and len(opts) == 2 and opts[0] == "--done":
        route_done, opts = opts[1], []
    if cmd not in ("think", "tool", "route", "intake", "done") or opts:
        aos_cli.error("Usage", "aos_agent_lib.py think|tool|route [--done 名]|intake|done（設定＝stdin 那份＋frame 裡找）"
                               "｜fsm [NAME]")
        return 1
    cfg = None
    try:
        text = "" if sys.stdin is None or sys.stdin.closed else sys.stdin.read()
        args = aos_cli.read_stream(text)
        if text.strip() and not args:
            raise AgentError("ConfigMissing", "stdin 不是 JSON")
        arg = args[0] if args else None
        cfg = load_config(arg, need_brain=cmd == "think")
        if cmd == "route":
            aos_cli.emit(route(cfg, route_done))
            return 0
        if cmd == "intake":
            aos_cli.emit(intake(cfg))
            return 0
        if cmd == "done":
            aos_cli.emit(done(cfg))
            return 0
        data = (think if cmd == "think" else act)(cfg)
    except CliError as e:
        if cmd == "think" and cfg is not None and e.code != "SystemUnreadable":
            halt = _think_failed(cfg, e)
            if halt is not None:
                aos_cli.emit(halt)
                return 0
        aos_cli.error(e.code, e.msg)
        return 1
    except (OSError, ValueError) as e:
        aos_cli.error("ReadFailed", str(e))
        return 1
    aos_cli.emit({"data": data})
    return 0


if __name__ == "__main__":
    sys.exit(main())
