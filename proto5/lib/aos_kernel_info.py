"""kernel 的設定讀驗、初始帳本、行程判定與共用工具。"""
import copy
import os
from pathlib import Path
import time

import aos_home
from aos_directives import Context, DirectiveError, Document, parse_options, resolve_located

CLI = Path(__file__).resolve().parents[1] / "cli" / "aos-kernel"
CPU_CLI = CLI.with_name("aos-cpu")
DEFAULTS = {"tick_ms": 1000, "interval_ms": 1000, "timeout_ms": 0, "done_exit": 100, "bad_after": 10}


class KernelError(aos_home.HomeError):
    def __init__(self, code, msg, rpc_code=-32000, position=None):
        super().__init__(code, msg)
        self.rpc_code, self.position = rpc_code, position


class CLIUsage(KernelError):
    def __init__(self, msg):
        super().__init__("Usage", msg)


def _name(value):
    return isinstance(value, str) and value not in ("", ".", "..") and "/" not in value and "\0" not in value


def _bad(msg, position):
    raise KernelError("FieldTypeMismatch", msg, -32602, position)


def load_info(home):
    home = Path(home).absolute()
    return _parse_info(home, aos_home.read_json(home / "info.json"))


def _parse_info(home, raw):
    path = home / "info.json"
    if not isinstance(raw, dict) or any(k.startswith("$") for k in raw):
        _bad("info 頂層必須是字面物件", [])
    def expand(value, ctx, position, field=()):
        if len(field) == 3 and field[0] == "cpus" and field[2] == "envs":
            return copy.deepcopy(value)
        loc = resolve_located(value, ctx, position)
        value = parse_options(loc.value, loc.position, {})[1]
        if isinstance(value, dict):
            return {k: expand(v, loc.ctx, loc.position + [k], field + (k,)) for k, v in value.items()}
        if isinstance(value, list):
            return [expand(v, loc.ctx, loc.position + [str(i)], field + (str(i),)) for i, v in enumerate(value)]
        return value
    try:
        info = expand(raw, Context(Document(str(path), raw), base_dir=str(home)), [])
    except DirectiveError as exc:
        raise KernelError(exc.code, exc.msg) from exc
    return _validate_info(info)


def _validate_info(info):
    mi = info.get("_metainfo")
    if (not isinstance(mi, dict) or mi.get("_type") != "kernel" or
            type(mi.get("_version")) is not int or mi["_version"] != 1):
        raise KernelError("NotAHome", "不是 kernel 第 1 版的家")
    cpus = info.get("cpus")
    if not isinstance(cpus, dict):
        _bad("cpus 必須是物件", ["cpus"])
    for name, config in cpus.items():
        if not _name(name) or not isinstance(config, dict):
            _bad("cpu 名稱或設定不合法", ["cpus", name])
        if not isinstance(config.setdefault("pool", "default"), str):
            _bad("pool 必須是字串", ["cpus", name, "pool"])
        if "envs" in config and not isinstance(config["envs"], dict):
            _bad("envs 必須是物件", ["cpus", name, "envs"])
    if sum(c["pool"] == "kernel" for c in cpus.values()) != 1:
        _bad("恰好一顆 cpu 的 pool 必須是 kernel", ["cpus"])
    for key, default in DEFAULTS.items():
        value = info.setdefault(key, default)
        if type(value) is not int or value < 0 or (key == "done_exit" and value > 255):
            _bad("%s 必須是合法非負整數" % key, [key])
    if "daemon" in info and (not isinstance(info["daemon"], str) or
                              not os.path.isabs(info["daemon"]) or "\0" in info["daemon"]):
        _bad("daemon 必須是絕對路徑", ["daemon"])
    return info


CONFIG_EXAMPLE = ('{"cpus": {"0": {}, "llm": {"pool": "llm", '
                  '"envs": {"AOS_LLM_CONFIG": "/abs/llm.json"}}}}')


def info_from_config(config):
    """init --config（09-24 fix-r4）：設定檔就是 info.json 要寫的那幾格；補 _metainfo、預設值與 k。"""
    if not isinstance(config, dict) or any(k.startswith("$") for k in config):
        _bad("--config 的頂層必須是字面物件", [])
    if "daemon" in config:
        _bad("--config 不能寫 daemon（那格是 boot 寫的）", ["daemon"])
    cpus = config.get("cpus")
    if not isinstance(cpus, dict) or not cpus or any(k.startswith("$") for k in cpus):
        _bad("--config 要有 cpus（字面物件，至少一顆），例：" + CONFIG_EXAMPLE, ["cpus"])
    cpus = copy.deepcopy(cpus)
    if not any(isinstance(c, dict) and c.get("pool") == "kernel" for c in cpus.values()):
        if "k" in cpus:
            _bad("沒有 pool 是 kernel 的 cpu，而 k 已被別的池用；請把一顆標成 {\"pool\": \"kernel\"}", ["cpus", "k"])
        cpus = {"k": {"pool": "kernel"}, **cpus}
    info = {"_metainfo": copy.deepcopy(config.get("_metainfo", {"_type": "kernel", "_version": 1})), "cpus": cpus}
    for key, default in DEFAULTS.items():
        info[key] = copy.deepcopy(config.get(key, default))
    for key, value in config.items():
        info.setdefault(key, copy.deepcopy(value))
    return info


def init(home, cpus=None, config=None):
    home = Path(home).absolute()
    if (home / "info.json").exists():
        raise KernelError("AlreadyExists", "拒絕覆蓋既有的家：%s" % home)
    if config is not None:
        info = info_from_config(config)
    else:
        info = {"_metainfo": {"_type": "kernel", "_version": 1},
                "cpus": cpus if cpus is not None else {"k": {"pool": "kernel"}, "0": {}, "1": {}, "2": {}}, **DEFAULTS}
    _parse_info(home, copy.deepcopy(info))
    home.mkdir(parents=True, exist_ok=True)
    aos_home.ensure_queue(home)
    (home / "cpus").mkdir(exist_ok=True)
    aos_home.write_json(home / "info.json", info)
    return str(home)


def _idle():
    return {"req": None, "proc": None, "discard": False}


def new_state(info, chain, kcpu, cli):
    return {"chain": chain, "kcpu": kcpu, "cli": str(cli), "last_seq": 0, "phase": "running",
            "cpus": {c: _idle() for c, config in info["cpus"].items()
                     if c != kcpu and config.get("pool", "default") != "kernel"},
            "queue": [], "procs": {}, "acks": [], "replies": [], "stops": [], "deletes": []}


def classify(proc, response, info, now=None):
    """§4 反覆行程判定表；不動輸入，回新的行程紀錄。"""
    proc = copy.deepcopy(proc)
    result = response.get("result", {})
    if result.get("stopped") is True:
        proc["status"] = "queued"
        return proc
    if "error" in response:
        proc["fails"] += 1
    else:
        proc["runs"] += 1
        if result.get("kind") == "aos":
            proc["fails"] += 1
        elif info["done_exit"] != 0 and result.get("code") == info["done_exit"]:
            proc.update(fails=0, status="done")
            return proc
        elif result.get("code") in (0, 101):
            proc["fails"] = 0
        else:
            proc["fails"] += 1
    if info["bad_after"] != 0 and proc["fails"] >= info["bad_after"]:
        proc["status"] = "bad"
    else:
        proc.update(status="queued", not_before=(time.time() if now is None else now) + proc["interval_ms"] / 1000)
    return proc


def _put(home, name, obj):
    try:
        aos_home.post_request(home, name, obj)
    except aos_home.RequestExists:
        pass


def _body_error(code, msg):
    return {"error": {"code": -32000, "message": msg, "data": {"code": code}}}
