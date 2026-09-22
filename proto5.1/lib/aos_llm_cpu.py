"""llm cpu：以共用 aos_cpu 佇列執行 aos_llm_ask.call。"""
import argparse
import os
import sys

import aos_agent_info
import aos_cpu
import aos_llm_ask
from aos_agent_info import AgentError

__all__ = ["load", "queue_lock", "tick", "main"]
queue_lock = aos_cpu.queue_lock


def load(dir, env=None):
    return aos_cpu.load(dir, "llm_cpu", env=env)


def _validate(req, path):
    engine = req.get("engine")
    if not isinstance(engine, dict):
        raise AgentError("EngineInvalid", "%s 的 engine 必須是物件" % path)
    for key in ("endpoint", "model"):
        if not isinstance(engine.get(key), str) or not engine[key]:
            raise AgentError("EngineInvalid", "%s 的 engine.%s 必須是非空字串" % (path, key))
    if not isinstance(engine.get("params", {}), dict):
        raise AgentError("EngineInvalid", "%s 的 engine.params 必須是物件" % path)
    if engine.get("api_key") is not None and not isinstance(engine["api_key"], str):
        raise AgentError("EngineInvalid", "%s 的 engine.api_key 必須是字串或 null" % path)
    timeout = engine.get("timeout_ms", aos_agent_info.DEFAULT_TIMEOUT_MS)
    if type(timeout) is not int or timeout <= 0:
        raise AgentError("EngineInvalid", "%s 的 engine.timeout_ms 必須是正整數" % path)
    if not isinstance(req.get("body"), dict):
        raise AgentError("FieldTypeMismatch", "%s 的 body 必須是物件" % path)


def _execute(req):
    try:
        return {"ok": True, "message": aos_llm_ask.call(req["engine"], req["body"])}
    except aos_llm_ask.EngineFailed as e:
        return {"ok": False, "error": e.msg}
    except ValueError as e:
        return {"ok": False, "error": "引擎請求無法送出：%s" % e}


def tick(dir, env=None):
    return aos_cpu.tick(load(dir, env=env)["dir"], _execute, validate=_validate,
                        timeout_ms=lambda req: req["engine"].get("timeout_ms", aos_agent_info.DEFAULT_TIMEOUT_MS))


def main(argv=None):
    """aos-llm-cpu [dir]；stdout 沒內容，讀驗錯誤一行 stderr。"""
    ap = argparse.ArgumentParser(prog="aos-llm-cpu", description="llm cpu 收屍並處理一份請求")
    ap.add_argument("dir", nargs="?", default=".", help="有 info.json 的 cpu 資料夾；留空＝.")
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if not os.path.isdir(a.dir):
        sys.stderr.write("aos-llm-cpu: %s 不是資料夾\n" % a.dir)
        return 2
    try:
        return tick(a.dir)
    except AgentError as e:
        sys.stderr.write("aos-llm-cpu: %s\n" % " ".join(str(e).split()))
        return 1


if __name__ == "__main__":
    sys.exit(main())
