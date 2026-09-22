"""llm cpu：以共用 aos_cpu 佇列執行 aos_llm_ask.call。"""
import argparse
import os
import sys

import aos_agent_info
import aos_cpu
import aos_llm_ask
from aos_agent_info import AgentError
from aos_directives import Context, DirectiveError, Document, resolve_located

__all__ = ["load", "tick", "main"]


def load(dir, env=None):
    info = aos_cpu.load(dir, "llm_cpu", env=env)
    path = os.path.join(info["dir"], "info.json")
    obj = aos_cpu._read_json(path)
    try:
        top = resolve_located(obj, Context(Document(path, obj), base_dir=info["dir"], env=env), [])
        if "models" not in top.value:
            raise AgentError("EngineInvalid", "llm cpu 的 info.json 缺少 models 表")
        models = aos_agent_info._deep(top.value["models"], top, "models")
    except DirectiveError as e:
        raise AgentError(e.code, e.msg)
    if not isinstance(models, dict):
        raise AgentError("EngineInvalid", "llm cpu 的 models 必須是物件")
    for alias, engine in models.items():
        if not alias or not isinstance(engine, dict):
            raise AgentError("EngineInvalid", "models 代號必須非空，設定必須是物件")
        for key in ("endpoint", "model"):
            if not isinstance(engine.get(key), str) or not engine[key]:
                raise AgentError("EngineInvalid", "models.%s.%s 必須是非空字串" % (alias, key))
        if engine.get("api_key") is not None and not isinstance(engine["api_key"], str):
            raise AgentError("EngineInvalid", "models.%s.api_key 必須是字串或 null" % alias)
        timeout = engine.get("timeout_ms", aos_agent_info.DEFAULT_TIMEOUT_MS)
        if type(timeout) is not int or timeout <= 0:
            raise AgentError("EngineInvalid", "models.%s.timeout_ms 必須是正整數" % alias)
        models[alias] = {"endpoint": engine["endpoint"], "model": engine["model"],
                         "api_key": engine.get("api_key"), "timeout_ms": timeout}
    info["models"] = models
    return info


def _validate(req, path):
    if not isinstance(req.get("model"), str) or not req["model"]:
        raise AgentError("EngineInvalid", "%s 的 model 必須是非空代號字串" % path)
    if not isinstance(req.get("body"), dict):
        raise AgentError("FieldTypeMismatch", "%s 的 body 必須是物件" % path)


def _execute(req, models):
    try:
        _validate(req, "請求")
    except AgentError as e:
        return {"ok": False, "code": "BadPayload", "msg": e.msg}
    engine = models.get(req["model"])
    if engine is None:
        return {"ok": False, "code": "UnknownModel", "msg": "不認識的模型代號"}
    try:
        body = dict(req["body"], model=engine["model"])
        return {"ok": True, "message": aos_llm_ask.call(engine, body)}
    except aos_llm_ask.EngineFailed as e:
        return {"ok": False, "code": e.code, "msg": e.msg}
    except ValueError as e:
        return {"ok": False, "code": "BadPayload", "msg": "引擎請求無法送出：%s" % e}


def _timeout(req, models):
    alias = req.get("model")
    return models.get(alias, {}).get("timeout_ms", aos_agent_info.DEFAULT_TIMEOUT_MS) \
        if isinstance(alias, str) else aos_agent_info.DEFAULT_TIMEOUT_MS


def tick(dir, env=None):
    info = load(dir, env=env)
    models = info["models"]
    return aos_cpu.tick(info["dir"], lambda req: _execute(req, models),
                        timeout_ms=lambda req: _timeout(req, models))


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
