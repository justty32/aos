#!/usr/bin/env python3
"""aos-agent：先看 waits 這道門，再把 agent 資料夾走一格。

規範在 ../spec/aos-agent.md 與 ../spec/agent.md。info.json 的讀驗交給 aos_agent_info；
think 問模型交給 aos_llm_ask；act 用 aos_inst／aos_exec 跑工具，不開 aos-exec 子進程。

`step(dir, env=None)` 回 0（做了一格）或 101（還在等），讀驗錯丟 AgentError。
state.json 留原始 JSON，只換 state／waits／errors；記憶整份寫。寫檔先 .tmp 再 os.replace，
走格的順序是記憶 → input rename .done → state。think／act 看記憶尾巴自癒；沒有鎖，
同一個 agent 不要同時跑兩份。工具預設 60 秒；引擎連敗三次等 continue.json。
engine.cpu 有填就用 requests／ask-result.json 分兩格問模型。
"""
import contextlib
import io
import json
import os
import sys
import time

import aos_agent_info
import aos_exec
import aos_inst
import aos_llm_ask
import aos_llm_cpu
from aos_agent_info import AgentError
from aos_directives import (Context, DirectiveError, Document, is_directive,
                            is_option_object, parse_options, resolve_located)

__all__ = ["AgentError", "step", "main"]

WAIT_OPTIONS = {name: {"val": "required"} for name in ("exists", "mtime", "consume", "any", "all")}


def _paths(value, ctx, position, where):
    """路徑或路徑陣列：容器與元素各自解指示詞，帶著被引用文件的實體位置。"""
    loc = resolve_located(value, ctx, position)
    val = parse_options(loc.value, loc.position, {})[1]
    if isinstance(val, str):
        return [val]
    if isinstance(val, list):
        out = []
        for i, v in enumerate(val):
            sub = resolve_located(v, loc.ctx, loc.position + [str(i)])
            v = parse_options(sub.value, sub.position, {})[1]
            if not isinstance(v, str):
                raise AgentError("FieldTypeMismatch", "%s 的第 %d 個路徑要是字串" % (where, i))
            out.append(v)
        return out
    raise AgentError("FieldTypeMismatch", "%s 要是路徑字串或字串陣列" % where)


def _read_state(base, env):
    """讀驗 state.json，但留原始物件與 waits 條目，寫回時不把指示詞展開。"""
    path = os.path.join(base, "state.json")
    raw = aos_agent_info._read_json(path, "state.json") if os.path.lexists(path) else {}
    if not isinstance(raw, dict):
        raise AgentError("NotAnObject", "%s 必須是一個 JSON 物件" % path)
    if is_directive(raw):
        raise AgentError("FieldTypeMismatch", "%s 頂層必須是字面物件，才能寫回" % path)
    state = raw.get("state", "idle")
    if not isinstance(state, str) or state not in ("idle", "think", "act"):
        raise AgentError("StateInvalid", "%s 的 state 要是字面的 idle／think／act" % path)
    errors = raw.get("errors", 0)
    if type(errors) is not int or errors < 0:
        raise AgentError("FieldTypeMismatch", "%s 的 errors 要是字面非負整數" % path)
    ctx = Context(Document(path, raw), base_dir=base, env=env)
    try:
        inputs = _paths(raw.get("input", "input.json"), ctx, ["input"], "state.json 的 input")
        entries = raw.get("waits", [])
        if isinstance(entries, list):
            positions = [["waits", str(i)] for i in range(len(entries))]
        elif isinstance(entries, str) or is_option_object(entries):
            entries, positions = [entries], [["waits"]]
        else:
            raise AgentError("FieldTypeMismatch", "%s 的 waits 要是字面陣列、路徑或 $opt 物件" % path)
        waits = []
        for entry, position in zip(entries, positions):
            loc = resolve_located(entry, ctx, position)
            names, val, _ = parse_options(loc.value, loc.position, WAIT_OPTIONS)
            if {"exists", "mtime"} <= names or {"any", "all"} <= names:
                raise AgentError("OptionConflict", "%s 的 waits：exists／mtime、any／all 不能一起用" % path)
            since = loc.value.get("since") if names else None
            if "mtime" in names and (not isinstance(since, (int, float)) or isinstance(since, bool)):
                raise AgentError("FieldTypeMismatch", "%s 的 waits：mtime 一定要有數字 since" % path)
            pos = loc.position + ["$val"] if names else loc.position
            paths = _paths(val, loc.ctx, pos, "state.json 的 waits")
            waits.append((names, paths, since))
    except DirectiveError as e:
        raise AgentError(e.code, "%s：%s" % (path, e.msg))
    return raw, state, inputs, entries, waits


def _files(base, path, excluded=()):
    """單檔照路徑；資料夾取當時的 *.json 普通檔，照檔名排序，不遞迴。"""
    path = os.path.abspath(os.path.join(base, path))
    if os.path.isdir(path):
        paths = [os.path.join(path, name) for name in sorted(os.listdir(path))
                 if name.endswith(".json") and os.path.isfile(os.path.join(path, name))]
    else:
        paths = [path] if os.path.exists(path) else []
    return [p for p in paths if p not in excluded]


def _gate(base, entries, waits):
    """先算門的結果與 consume 清單，不寫檔；後面的條目看不到前面已排定 consume 的檔。"""
    remaining, consumed, excluded = [], [], set()
    for entry, (names, paths, since) in zip(entries, waits):
        groups = [_files(base, p, excluded) for p in paths]
        arrived = [any(os.path.getmtime(p) > since for p in files) if "mtime" in names else bool(files)
                   for files in groups]
        ready = any(arrived) if "any" in names else all(arrived)
        if not ready:
            remaining.append(entry)
        elif "consume" in names:
            for files, reached in zip(groups, arrived):
                if reached:
                    for p in files:
                        if p not in excluded:
                            consumed.append(p)
                            excluded.add(p)
    return remaining, consumed


def _inputs(base, paths, excluded):
    """輸入原樣讀，三種內容都變成訊息陣列；全部驗好才准寫記憶或 rename。"""
    messages, read, seen = [], [], set(excluded)
    for path in paths:
        for p in _files(base, path, seen):
            obj = aos_agent_info._read_json(p, "輸入檔")
            if isinstance(obj, str):
                msgs = [{"role": "user", "content": obj}]
            else:
                msgs = obj if isinstance(obj, list) else [obj]
            for i, msg in enumerate(msgs):
                aos_agent_info._check_message(msg, "輸入檔 %s 第 %d 則" % (p, i))
            messages.extend(msgs)
            read.append(p)
            seen.add(p)
    return messages, read


def _write_json(path, obj):
    """整份 UTF-8 JSON 加換行，先寫 .tmp 再原子替換；初次使用時建立父目錄。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    os.replace(path + ".tmp", path)


def _consume(paths):
    """讀完／等到的檔換成 .done；舊的 .done 直接蓋掉。"""
    for path in paths:
        os.replace(path, path + ".done")


def _calls(history):
    """只有尾巴的 assistant 帶非空 tool_calls 陣列才有工具要跑。"""
    if history and history[-1].get("role") == "assistant":
        calls = history[-1].get("tool_calls")
        if isinstance(calls, list) and calls:
            return calls
    return []


def _tool_result(call, info, env):
    """一個 call 對一則 tool 訊息；工具失敗變成給模型看的結果，不中斷其他 call。"""
    # 記憶驗法只驗 tool_calls 是陣列；殘缺的 call 當找不到名字，不讓 AttributeError 炸掉整格。
    call = call if isinstance(call, dict) else {}
    fn = call.get("function")
    fn = fn if isinstance(fn, dict) else {}
    name = fn.get("name", "")
    arguments = fn.get("arguments", "")
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments)
    tool = next((t for t in info["tools_raw"] if t["function"]["name"] == name), None)
    if tool is None:
        content = "沒有這個工具：%s" % name
    else:
        try:
            inst = aos_inst.load_obj(tool["_meta"], base=info["dir"], env=env)
            errors = io.StringIO()
            timeout_ms = tool.get("_timeout_ms", 60000)
            with contextlib.redirect_stderr(errors):
                result = aos_exec.run_inst(inst, arguments, timeout_ms=timeout_ms)
            code, kind, out = result
            if result.timed_out:
                content = "工具 %s 逾時（%d ms）：%s" % (name, timeout_ms, out)
            elif kind == aos_exec.AOS:
                content = "工具 %s 跑不起來：%s" % (name, " ".join(errors.getvalue().split()))
            elif code:
                content = "工具 %s 失敗（exit %d）：%s" % (name, code, out)
            else:
                content = out
        except aos_inst.InstError as e:
            content = "工具 %s 跑不起來：%s" % (name, " ".join(str(e).split()))
    call_id = call.get("id", "")
    return {"role": "tool", "tool_call_id": call_id if isinstance(call_id, str) else str(call_id),
            "content": content}


def _read_result(path):
    """結果當資料讀，不解指示詞；全部驗完才准劃 waits 或 rename。"""
    try:
        result = aos_agent_info._read_json(path, "模型結果")
    except UnicodeDecodeError as e:
        raise AgentError("JsonSyntax", "%s 不是合法 UTF-8 JSON：%s" % (path, e))
    if not isinstance(result, dict):
        raise AgentError("NotAnObject", "%s 要是 JSON 物件" % path)
    if type(result.get("ok")) is not bool:
        raise AgentError("FieldTypeMismatch", "%s 的 ok 要是布林值" % path)
    if not result["ok"]:
        if not isinstance(result.get("error"), str):
            raise AgentError("FieldTypeMismatch", "%s 的 error 要是字串" % path)
        return result
    message = result.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise AgentError("MessageInvalid", "%s 的 message 要是 assistant 訊息" % path)
    if message.get("content") is None and not message.get("tool_calls"):
        message["content"] = ""
    aos_agent_info._check_message(message, "%s 的 message" % path)
    if "tool_calls" in message and not isinstance(message["tool_calls"], list):
        raise AgentError("MessageInvalid", "%s 的 message.tool_calls 要是陣列" % path)
    return result


def _submit(info):
    """agent 已解好 engine；與 cpu 共用短鎖，三個階段都沒有同名才發布。"""
    cpu = info["engine"]["cpu"]
    name = "%s-%d.json" % (os.path.basename(info["dir"]), time.time_ns())
    request = {"engine": info["engine"], "body": aos_llm_ask.request_from_info(info),
               "result": os.path.join(info["dir"], "ask-result.json")}
    with aos_llm_cpu.queue_lock(cpu):
        if any(os.path.lexists(os.path.join(cpu, stage, name))
               for stage in ("requests", "running", "done")):
            raise FileExistsError("llm cpu 三處已有同名請求：%s" % os.path.join(cpu, name))
        _write_json(os.path.join(cpu, "requests", name), request)


def _failure(base, raw, error):
    """引擎失敗累計；舊的繼續信號封存，下一輪三敗仍能停住。"""
    _err("engine: %s" % error)
    raw["errors"] = raw.get("errors", 0) + 1
    if raw["errors"] >= 3:
        resume = os.path.join(base, "continue.json")
        if os.path.lexists(resume):
            _consume([resume])
        raw["errors"] = 0
        raw.setdefault("waits", []).append("continue.json")
        _err("stuck: 引擎連敗 3 次，touch continue.json 繼續")


def step(dir, env=None):
    """先讀驗、再判門、最後走一格；0＝做了事，101＝在等。讀驗錯誤丟 AgentError。"""
    info = aos_agent_info.load(dir, env=env)
    base = info["dir"]
    raw, state, inputs, entries, waits = _read_state(base, env)
    remaining, consumed = _gate(base, entries, waits)
    history = info["history"]
    result_path = os.path.join(base, "ask-result.json")
    result = None
    healed_result = False
    if state == "think" and not remaining and info["engine"].get("cpu"):
        if _calls(history):
            # 自癒優先；只封存確定已接到記憶的同一則結果，壞檔不擋 act。
            if os.path.lexists(result_path):
                try:
                    previous = _read_result(result_path)
                    healed_result = previous["ok"] and previous["message"] == history[-1]
                except AgentError:
                    pass
        elif os.path.lexists(result_path):
            result = _read_result(result_path)
        else:
            aos_llm_cpu.load(info["engine"]["cpu"], env=env)
    # 門開了才讀輸入，但讀驗仍要在 consume／寫 waits 之前完成：壞訊息不能留下半次寫入。
    messages, read = _inputs(base, inputs, consumed) if state == "idle" and not remaining else ([], [])
    state_path = os.path.join(base, "state.json")
    if entries:
        _consume(consumed)
        raw["waits"] = remaining
        _write_json(state_path, raw)
    if remaining:
        return 101

    if state == "idle":
        if not messages:
            return 101
        history.extend(messages)
        _write_json(info["history_path"], history)
        _consume(read)
        next_state = "think"
    elif state == "think":
        if _calls(history):
            if healed_result:
                _consume([result_path])
                raw["errors"] = 0
            next_state = "act"
        else:
            if info["engine"].get("cpu") and result is None:
                _submit(info)
                raw.setdefault("waits", []).append("ask-result.json")
                _write_json(state_path, raw)
                return 0
            try:
                if result is not None:
                    if not result["ok"]:
                        raise aos_llm_ask.EngineFailed(result["error"])
                    message = result["message"]
                else:
                    message = aos_llm_ask.call(info["engine"], aos_llm_ask.request_from_info(info))
            except aos_llm_ask.EngineFailed as e:
                _failure(base, raw, e.msg)
                if result is not None:
                    _consume([result_path])
                _write_json(state_path, raw)
                return 0
            if message.get("content") is None and not message.get("tool_calls"):
                message["content"] = ""
            history.append(message)
            _write_json(info["history_path"], history)
            if result is not None:
                _consume([result_path])
            raw["errors"] = 0
            calls = message.get("tool_calls")
            next_state = "act" if isinstance(calls, list) and calls else "idle"
    else:
        calls = _calls(history)
        if calls:
            history.extend(_tool_result(call, info, env) for call in calls)
            _write_json(info["history_path"], history)
        next_state = "think"
    raw["state"] = next_state
    _write_json(state_path, raw)
    return 0


def _err(msg):
    """stderr 一行白話；檔名或引擎訊息裡的換行壓成空白。"""
    sys.stderr.write("aos-agent: %s\n" % " ".join(str(msg).split()))


def main(argv=None):
    """命令列只有可省的 dir；用法錯 2、讀驗錯 1，其他回 step 的 0／101。"""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 1 or any(a.startswith("-") for a in args):
        _err("usage: aos-agent [dir]，只有一個資料夾參數，沒有旗標")
        return 2
    dir = args[0] if args else "."
    if not os.path.isdir(dir):
        _err("usage: %s 不是資料夾" % dir)
        return 2
    try:
        return step(dir)
    except (AgentError, aos_inst.InstError) as e:
        _err(str(e))
        return 1
    except OSError as e:
        _err("io: 檔案操作失敗：%s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
