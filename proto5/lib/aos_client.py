"""交件者的取名、放單、等回音、讀與 ack（cpu.md §3、§6.3）。

call() 回完整 JSON-RPC response；要先記帳再 ack 的交件者可用 acknowledge=False，
或分別使用 submit()、wait_response()、ack()。逾時不取消已放出去的工作。
"""
import os
from pathlib import Path
import time

from aos_home import HomeError, post_request, read_json, validate_name


class ClientError(HomeError):
    pass


def new_name(prefix="client"):
    return validate_name("%s-%d-%d.json" % (prefix, time.time_ns(), os.getpid()))


def submit(home, method, params=None, *, name=None, client="client"):
    name = new_name(client) if name is None else validate_name(name)
    obj = {"jsonrpc": "2.0", "id": name[:-5], "method": method}
    if params is not None:
        obj["params"] = params
    post_request(home, name, obj)
    return name


def wait_response(home, name, *, timeout_ms=None, poll_ms=20):
    """原單還在便繼續等；一定先查原單再查回音，避免將寫到一半的收尾看成完成。"""
    if type(poll_ms) is not int or poll_ms <= 0:
        raise ClientError("FieldTypeMismatch", "poll_ms 必須是正整數")
    if timeout_ms is not None and (type(timeout_ms) is not int or timeout_ms < 0):
        raise ClientError("FieldTypeMismatch", "timeout_ms 必須是非負整數或 None")
    home = Path(home)
    name = validate_name(name)
    deadline = None if timeout_ms is None else time.monotonic() + timeout_ms / 1000
    while True:
        if not (home / "requests" / name).exists():
            if (home / "responses" / name).exists():
                return read_json(home / "responses" / name)
        if deadline is not None and time.monotonic() >= deadline:
            raise ClientError("ReadFailed", "等回音逾時：%s" % (home / "responses" / name))
        delay = poll_ms / 1000
        if deadline is not None:
            delay = min(delay, max(0, deadline - time.monotonic()))
        time.sleep(delay)


def ack(home, name):
    name = validate_name(name)
    ack_name = new_name("ack")
    post_request(home, ack_name, {"jsonrpc": "2.0", "method": "ack", "params": {"name": name}})
    return ack_name


def call(home, method, params=None, *, name=None, client="client", timeout_ms=None,
         poll_ms=20, acknowledge=True):
    """完成五步並回完整 response；protocol error 也回給交件者自行判定。"""
    name = submit(home, method, params, name=name, client=client)
    response = wait_response(home, name, timeout_ms=timeout_ms, poll_ms=poll_ms)
    if acknowledge:
        ack(home, name)
    return response
