#!/usr/bin/env python3
"""aos-agent：先看 waits 這道門，再把 agent 資料夾走一格。

規範在 ../spec/aos-agent.md 與 ../spec/agent.md。info.json 的讀驗交給 aos_agent_info；
think 問模型交給 aos_llm_ask；act 用 aos_inst／aos_exec 跑工具，不開 aos-exec 子進程。

`step(dir, env=None)` 回 0（做了一格）或 101（還在等），讀驗錯丟 AgentError。
state.json 留原始 JSON，只換 state／waits；記憶整份寫。寫檔先 .tmp 再 os.replace，
走格的順序是記憶 → input rename .done → state。think／act 看記憶尾巴自癒；沒有鎖，
同一個 agent 不要同時跑兩份。工具不限時；引擎失敗留在 think，下一次再試。
"""
import contextlib
import io
import json
import os
import sys

import aos_agent_info
import aos_exec
import aos_inst
import aos_llm_ask
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
            with contextlib.redirect_stderr(errors):
                code, kind, out = aos_exec.run_inst(inst, arguments)
            if kind == aos_exec.AOS:
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


def step(dir, env=None):
    """先讀驗、再判門、最後走一格；0＝做了事，101＝在等。讀驗錯誤丟 AgentError。"""
    info = aos_agent_info.load(dir, env=env)
    base = info["dir"]
    raw, state, inputs, entries, waits = _read_state(base, env)
    remaining, consumed = _gate(base, entries, waits)
    # 門開了才讀輸入，但讀驗仍要在 consume／寫 waits 之前完成：壞訊息不能留下半次寫入。
    messages, read = _inputs(base, inputs, consumed) if state == "idle" and not remaining else ([], [])
    state_path = os.path.join(base, "state.json")
    if entries:
        _consume(consumed)
        raw["waits"] = remaining
        _write_json(state_path, raw)
    if remaining:
        return 101

    history = info["history"]
    if state == "idle":
        if not messages:
            return 101
        history.extend(messages)
        _write_json(info["history_path"], history)
        _consume(read)
        next_state = "think"
    elif state == "think":
        if _calls(history):
            next_state = "act"
        else:
            try:
                message = aos_llm_ask.call(info["engine"], aos_llm_ask.request_from_info(info))
            except aos_llm_ask.EngineFailed as e:
                _err("engine: %s" % e.msg)
                return 0
            if message.get("content") is None and not message.get("tool_calls"):
                message["content"] = ""
            history.append(message)
            _write_json(info["history_path"], history)
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
