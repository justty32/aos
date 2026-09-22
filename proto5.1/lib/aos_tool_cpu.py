"""tool cpu：只跑 agent 已解好的 inst，不讀 agent、不解指示詞。"""
import argparse
import os
import sys

import aos_cpu
import aos_exec
from aos_agent_info import AgentError

__all__ = ["load", "execute", "tick", "main"]
DEFAULT_TIMEOUT_MS = 60000


def load(dir, env=None):
    return aos_cpu.load(dir, "tool_cpu", env=env)


def _timeout(req):
    value = req.get("timeout_ms")
    # 壞 payload 仍能在 execute 寫 ok:false；崩在認領後則以預設期限收屍。
    return value if type(value) is int and value > 0 else DEFAULT_TIMEOUT_MS


def _validate(req):
    """只驗 load_obj 回傳的執行形狀，絕不重新解析指示詞。"""
    def text(value):
        return isinstance(value, str) and "\0" not in value

    def path(value, empty=False):
        return text(value) and ((empty and value == "") or os.path.isabs(value))

    inst = req.get("inst")
    if not isinstance(inst, dict):
        raise ValueError("inst 必須是已解好的物件")
    argv = inst.get("argv")
    if not isinstance(argv, list) or not argv or not all(text(v) for v in argv) or not argv[0]:
        raise ValueError("inst.argv 必須是非空字串陣列")
    if not path(inst.get("cwd")):
        raise ValueError("inst.cwd 必須是絕對路徑")
    for key in ("cwd_mkdir", "envs_clear"):
        if type(inst.get(key)) is not bool:
            raise ValueError("inst.%s 必須是布林" % key)
    env = inst.get("envs")
    if not isinstance(env, dict) or not all(text(k) and k and "=" not in k and text(v) for k, v in env.items()):
        raise ValueError("inst.envs 必須是合法的環境字串表")
    for key, flags in (("stdin", ("inherit",)), ("stdout", ("append", "mkdir", "inherit")),
                       ("stderr", ("append", "mkdir", "inherit", "merge")), ("exit", ("append", "mkdir"))):
        stream = inst.get(key)
        if (not isinstance(stream, dict) or not path(stream.get("path"), empty=True)
                or any(type(stream.get(flag)) is not bool for flag in flags)):
            raise ValueError("inst.%s 必須是已解好的串流設定，路徑為絕對或空字串" % key)
    if not isinstance(req.get("stdin"), str):
        raise ValueError("stdin 必須是 arguments 字串")
    if type(req.get("timeout_ms")) is not int or req["timeout_ms"] <= 0:
        raise ValueError("timeout_ms 必須是正整數")


def execute(req):
    try:
        _validate(req)
        outcome = aos_exec.run_inst(req["inst"], req["stdin"], req["timeout_ms"])
        code, kind, stdout = outcome
        return {"ok": True, "code": code, "kind": kind,
                "timed_out": outcome.timed_out, "stdout": stdout}
    except (ValueError, OSError) as e:
        return {"ok": False, "error": "工具請求無法執行：%s" % e}


def tick(dir, env=None):
    return aos_cpu.tick(load(dir, env=env)["dir"], execute, timeout_ms=_timeout)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aos-tool-cpu", description="tool cpu 收屍並處理一份請求")
    ap.add_argument("dir", nargs="?", default=".", help="有 info.json 的 cpu 資料夾；留空＝.")
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if not os.path.isdir(a.dir):
        sys.stderr.write("aos-tool-cpu: %s 不是資料夾\n" % a.dir)
        return 2
    try:
        return tick(a.dir)
    except AgentError as e:
        sys.stderr.write("aos-tool-cpu: %s\n" % " ".join(str(e).split()))
        return 1


if __name__ == "__main__":
    sys.exit(main())
