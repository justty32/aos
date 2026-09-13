#!/usr/bin/env python3
"""aos-agent 的四格狀態機。"""

import json
import os
from pathlib import Path

from agent_tools import (ToolConfigError, load_tools, looks_like_text_call,
                         recover_text_call, run_tool)
from common import atomic_json, read_json
from mailbox import collect_user_mail, write_outbox


DEFAULT_STATE = {
    "state": "idle", "epoch": 0, "question": 0, "step": 0, "request": None,
    "checks": 0, "errors": 0, "idle_since_error": 0,
    "stuck": False, "last_error": None, "outbox_n": 0,
}


class AgentError(Exception):
    pass


def load_agent(agent_dir):
    path = Path(agent_dir) / "agent.json"
    try:
        config = read_json(path)
        for key in ("name", "system", "K"):
            if not isinstance(config[key], str) or not config[key]:
                raise ValueError(key)
        for key, default in (("max_steps_per_question", 60), ("tool_output_limit", 8000)):
            config.setdefault(key, default)
            if isinstance(config[key], bool) or not isinstance(config[key], int) or config[key] < 1:
                raise ValueError(key)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise AgentError(f"agent.json 壞了：{path}") from exc
    if config.get("stop") is not True and not Path(config["K"]).is_dir():
        raise AgentError(f"K 不存在：{config['K']}")
    return config


def load_state(agent_dir):
    path = Path(agent_dir) / "state.json"
    if not path.exists():
        return dict(DEFAULT_STATE)
    try:
        value = read_json(path)
        state = dict(DEFAULT_STATE)
        state.update(value)
        if state["state"] not in ("idle", "ask", "wait", "act"):
            raise ValueError
        if (isinstance(state["epoch"], bool) or not isinstance(state["epoch"], int)
                or state["epoch"] < 0):
            raise ValueError
        return state
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AgentError(f"state.json 壞了：{path}") from exc


def load_messages(agent_dir):
    path = Path(agent_dir) / "messages.json"
    try:
        messages = read_json(path)
        if not isinstance(messages, list):
            raise ValueError
        return messages
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AgentError(f"messages.json 壞了：{path}") from exc


def _save(agent_dir, state, messages=None):
    if messages is not None:
        atomic_json(Path(agent_dir) / "messages.json", messages)
    atomic_json(Path(agent_dir) / "state.json", state)


def _record_error(agent_dir, state, message):
    state["errors"] += 1
    state["last_error"] = message
    state["idle_since_error"] = 0
    state["checks"] = 0
    state["state"] = "idle"
    if state["errors"] >= 5:
        state["stuck"] = True
        write_outbox(agent_dir, state, "連錯 5 次，這句先放著（stuck）；回我一句再試")


def _dangling(messages):
    return bool(messages and isinstance(messages[-1], dict)
                and messages[-1].get("role") in ("user", "tool"))


def do_idle(agent_dir, config, state, messages):
    incoming, handled_mail = collect_user_mail(agent_dir, state)
    if incoming:
        messages.extend(incoming)
        state.update({
            "state": "ask", "question": state["question"] + 1, "step": 0,
            "request": None, "checks": 0, "errors": 0,
            "idle_since_error": 0, "stuck": False, "last_error": None,
        })
        _save(agent_dir, state, messages)
        return 0
    if handled_mail:
        _save(agent_dir, state)
        return 0
    if _dangling(messages) and not state["stuck"]:
        state["idle_since_error"] += 1
        if state["idle_since_error"] >= 20:
            state["state"] = "ask"
            state["idle_since_error"] = 0
            _save(agent_dir, state)
            return 0
    _save(agent_dir, state)
    return 101


def do_ask(agent_dir, config, state, messages, aos_py):
    state["step"] += 1
    limit = config["max_steps_per_question"]
    if state["step"] > limit:
        write_outbox(agent_dir, state,
                     f"這題走了 {limit} 格到上限，先停（stuck）；回我一句就從頭算")
        state.update({"state": "idle", "stuck": True, "request": None, "checks": 0})
        _save(agent_dir, state)
        return 0
    tools = load_tools(agent_dir)
    request = {"messages": [{"role": "system", "content": config["system"]}, *messages]}
    if tools:
        request["tools"] = list(tools.values())
    atomic_json(Path(agent_dir) / "req.json", request)
    name = (f"{config['name']}-e{state['epoch']}-q{state['question']}"
            f"-s{state['step']}")
    helper_request = Path(agent_dir) / f"{name}.req.json"
    old_cwd = Path.cwd()
    try:
        os.chdir(agent_dir)
        try:
            state["request"] = aos_py.llm_submit(config["K"], request, name)
        finally:
            os.chdir(old_cwd)
            helper_request.unlink(missing_ok=True)
    except Exception as exc:
        _record_error(agent_dir, state, f"submit: {exc}")
        _save(agent_dir, state)
        return 0
    state.update({"state": "wait", "checks": 0})
    _save(agent_dir, state)
    return 0


def _read_result(path):
    try:
        result = read_json(path)
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AgentError(f"結果檔壞了：{path}") from exc


def _assistant_from_result(result):
    raw = result.get("raw")
    choices = raw.get("choices") if isinstance(raw, dict) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    message = choices[0].get("message")
    return message if isinstance(message, dict) else None


def do_wait(agent_dir, config, state, messages):
    path = Path(state["request"] or "")
    if not state["request"]:
        raise AgentError("wait 沒有 request")
    if not path.exists():
        state["checks"] += 1
        if state["checks"] < 600:
            _save(agent_dir, state)
            return 101
        _record_error(agent_dir, state, "timeout: 等結果超過 600 格")
        _save(agent_dir, state)
        return 0
    result = _read_result(path)
    if result.get("ok") is not True:
        error = result.get("error") if isinstance(result.get("error"), dict) else {}
        _record_error(agent_dir, state, f"{error.get('kind', 'llm')}: {error.get('msg', '模型失敗')}")
    else:
        assistant = _assistant_from_result(result)
        if assistant is None:
            _record_error(agent_dir, state, "bad_response: 沒有 choices")
        elif not assistant.get("tool_calls") and not str(result.get("text") or "").strip():
            _record_error(agent_dir, state, "empty_reply: 空白回覆")
        else:
            state.update({"state": "act", "checks": 0, "last_error": None})
    _save(agent_dir, state)
    return 0


def do_act(agent_dir, config, state, messages, aos_py):
    result = _read_result(state["request"])
    assistant = _assistant_from_result(result)
    if assistant is None:
        _record_error(agent_dir, state, "bad_response: 沒有 choices")
        _save(agent_dir, state)
        return 0
    tools = load_tools(agent_dir)
    calls = assistant.get("tool_calls")
    text = str(result.get("text") or "")
    if not calls and looks_like_text_call(text):
        calls = recover_text_call(text, tools, state["step"])
        if calls is None:
            _record_error(agent_dir, state, "tool_call: 文字工具呼叫救不回來")
            _save(agent_dir, state)
            return 0
        assistant = {"role": "assistant", "content": text, "tool_calls": calls}
    if calls:
        messages.append(assistant)
        for call in calls:
            messages.append({
                "role": "tool", "tool_call_id": call.get("id", ""),
                "content": run_tool(agent_dir, call, config["tool_output_limit"], aos_py),
            })
        state.update({"state": "ask", "request": None, "checks": 0})
    else:
        messages.append({"role": "assistant", "content": text})
        write_outbox(agent_dir, state, text)
        state.update({"state": "idle", "request": None, "checks": 0,
                      "idle_since_error": 0})
    _save(agent_dir, state, messages)
    return 0


def step(agent_dir, aos_py):
    agent_dir = Path(agent_dir).resolve()
    config = load_agent(agent_dir)
    if config.get("stop") is True:
        return 100
    state = load_state(agent_dir)
    messages = load_messages(agent_dir)
    handlers = {"idle": do_idle, "ask": do_ask, "wait": do_wait, "act": do_act}
    handler = handlers[state["state"]]
    if state["state"] in ("ask", "act"):
        return handler(agent_dir, config, state, messages, aos_py)
    return handler(agent_dir, config, state, messages)
