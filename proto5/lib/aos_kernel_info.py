"""kernel 的池表讀驗（info.json 第 2 版）、成員公式、初始帳本、行程判定與共用工具。

規範：proto5-2/spec/kernel-info.md、kernel-cli.md 的 init、kernel-ledger.md。
"""
import copy
import os
from pathlib import Path
import re
import time

import aos_home
from aos_directives import Context, DirectiveError, Document, parse_options, resolve_located

CLI = Path(__file__).resolve().parents[1] / "cli" / "aos-kernel"
CPU_CLI = CLI.with_name("aos-cpu")
DEFAULTS = {"tick_ms": 1000, "interval_ms": 1000, "timeout_ms": 0, "done_exit": 100, "bad_after": 10}
SWEEP = 32
PARK_MS = 300000   # 09-24 停車：info 沒寫 park_ms 的預設（init 不寫進 info）
PARK_EXIT = 102    # 反覆行程退這個碼＝停車（kernel/echo.md）
AGAIN_EXIT = 103   # 09-24 tick-gap：做了事、下一步馬上能做＝馬上再排（kernel/echo.md）
# 帳本 features：aos-agent start 靠它確認這個 kernel 認得 102（park）、103（again）（kernel/ledger.md）
FEATURES = ["park", "again"]
TICK_TIMEOUT_MS = 60000  # one-boot：一格最久跑多久，daemon 逾時整組 KILL、tick 自己也設鬧鐘（init 不寫進 info）
CPU_DEFAULTS = {"poll_ms": 200, "timeout_ms": 0}
KERNEL_POOL = "kernel"   # 保留名：one-boot 起沒有 kernel 池了，但一般池仍不准叫這個名字（舊 info 寫了就略過）
MAX_COUNT = 1000000
_POOL_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")


class KernelError(aos_home.HomeError):
    def __init__(self, code, msg, rpc_code=-32000, position=None):
        super().__init__(code, msg)
        self.rpc_code, self.position = rpc_code, position


class CLIUsage(KernelError):
    def __init__(self, msg):
        super().__init__("Usage", msg)


def _name(value):
    return isinstance(value, str) and value not in ("", ".", "..") and "/" not in value and "\0" not in value


def pool_name_ok(value):
    """kernel-info §5：1～64 bytes、只用 A-Z a-z 0-9 _ . -、不是 . 或 ..（也就不含 { } # /）。"""
    return isinstance(value, str) and value not in (".", "..") and _POOL_RE.fullmatch(value) is not None


def _int(value):
    return type(value) is int


def _bad(msg, position):
    raise KernelError("FieldTypeMismatch", msg, -32602, position)


# ---- 成員公式（kernel-info §3） ----

def members(count, skip):
    """M(count, skip)：不在 skip 裡的最小 count 個非負整數（遞增）。"""
    skip, out, i = set(skip), [], 0
    while len(out) < count:
        if i not in skip:
            out.append(i)
        i += 1
    return out


def is_member(i, count, skip):
    """i ∈ M(count, skip)？O(len(skip))，不展開整個集合。"""
    if i < 0 or i in skip:
        return False
    return i - sum(1 for s in skip if s < i) < count


def encode(numbers):
    """任一組非負整數 → (count, skip)：最大號以下的空洞全放進 skip。"""
    numbers = set(numbers)
    if not numbers:
        return 0, []
    top = max(numbers)
    return len(numbers), [i for i in range(top) if i not in numbers]


def member_set(spec):
    """帳本裡 {"count", "skip"} 那種小格 → 成員集合；None 當空集合。"""
    return set() if spec is None else set(members(spec["count"], spec["skip"]))


def cpu_key(pool, i):
    return "%s/%d" % (pool, i)


def split_key(key):
    """'P/<i>' → (P, i)；i 必須是不帶前導 0 的十進位，不合回 None。"""
    pool, sep, num = key.rpartition("/")
    if not sep or not pool_name_ok(pool) or not num.isascii() or not num.isdecimal() or len(num) > 18:
        return None
    if num != str(int(num)):
        return None
    return pool, int(num)


# ---- info 讀驗 ----

def load_info(home):
    home = Path(home).absolute()
    return _parse_info(home, aos_home.read_json(home / "info.json"))


def _parse_info(home, raw):
    path = Path(home) / "info.json"
    if not isinstance(raw, dict) or any(k.startswith("$") for k in raw):
        _bad("info 頂層必須是字面物件", [])
    mi = raw.get("_metainfo")
    if isinstance(mi, dict) and mi.get("_type") == "kernel" and _int(mi.get("_version")) and mi["_version"] == 1:
        raise KernelError("InfoVersion", "info.json 是 proto5 的第 1 版（cpus 表）；請照 proto5/spec/kernel/info.md 改寫成第 2 版的 pools 表")

    def expand(value, ctx, position, field=()):
        if len(field) == 3 and field[0] == "pools" and field[2] == "envs":
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


def _abs_path(value):
    return isinstance(value, str) and value != "" and "\0" not in value and os.path.isabs(value)


def _validate_pool(name, config, top_daemon):
    pos = ["pools", name]
    if not pool_name_ok(name):
        _bad("池名不合法（1～64 字、只用 A-Z a-z 0-9 _ . -）：%r" % name, pos)
    if not isinstance(config, dict):
        _bad("池的設定必須是物件", pos)
    if "count" not in config:
        _bad("count 必填", pos + ["count"])
    count = config["count"]
    if not _int(count) or count < 0 or count > MAX_COUNT:
        _bad("count 必須是 0～%d 的整數" % MAX_COUNT, pos + ["count"])
    skip = config.setdefault("skip", [])
    if (not isinstance(skip, list) or any(not _int(s) or s < 0 for s in skip)
            or len(set(skip)) != len(skip)):
        _bad("skip 必須是不重複的非負整數陣列", pos + ["skip"])
    if "daemon" in config and not _abs_path(config["daemon"]):
        _bad("daemon 必須是絕對路徑", pos + ["daemon"])
    if not pool_name_ok(config.setdefault("dpool", name)):
        _bad("dpool 不合法（同池名規則）", pos + ["dpool"])
    envs = config.setdefault("envs", {})
    if not isinstance(envs, dict):
        _bad("envs 必須是物件", pos + ["envs"])
    return config.get("daemon", top_daemon)


def _validate_info(info):
    mi = info.get("_metainfo")
    if (not isinstance(mi, dict) or mi.get("_type") != "kernel" or
            not _int(mi.get("_version")) or mi["_version"] != 2):
        raise KernelError("NotAHome", "不是 kernel 第 2 版的家（_metainfo 要是 {\"_type\": \"kernel\", \"_version\": 2}）")
    if "daemon" in info and not _abs_path(info["daemon"]):
        _bad("daemon 必須是絕對路徑", ["daemon"])
    pools = info.get("pools")
    if not isinstance(pools, dict):
        _bad("pools 必須是物件", ["pools"])
    seen = {}
    for name, config in pools.items():
        daemon = _validate_pool(name, config, info.get("daemon"))
        key = (daemon, config["dpool"])
        if key in seen:
            _bad("同一個 daemon 底下兩個池的 dpool 撞名：%s 與 %s" % (seen[key], name), ["pools", name, "dpool"])
        seen[key] = name
    cpu = info.setdefault("cpu", {})
    if not isinstance(cpu, dict):
        _bad("cpu 必須是物件", ["cpu"])
    for key, default in CPU_DEFAULTS.items():
        value = cpu.setdefault(key, default)
        if not _int(value) or value < (1 if key == "poll_ms" else 0):
            _bad("cpu.%s 必須是%s整數" % (key, "正" if key == "poll_ms" else "非負"), ["cpu", key])
    for key, default in DEFAULTS.items():
        value = info.setdefault(key, default)
        if not _int(value) or value < 0 or (key == "done_exit" and value > 255):
            _bad("%s 必須是合法非負整數" % key, [key])
    timeout = info.setdefault("tick_timeout_ms", TICK_TIMEOUT_MS)
    if not _int(timeout) or timeout < 0:
        _bad("tick_timeout_ms 必須是非負整數", ["tick_timeout_ms"])
    park = info.setdefault("park_ms", PARK_MS)
    if not _int(park) or park < 0:
        _bad("park_ms 必須是非負整數", ["park_ms"])
    sweep = info.setdefault("sweep", SWEEP)
    if not _int(sweep) or sweep < 1:
        _bad("sweep 必須是正整數", ["sweep"])
    return info


def ticker_daemon(info):
    """one-boot：替這個 kernel 開 tick 的 daemon 家——舊 info 的 kernel 池自己寫了 daemon 就用它，否則頂層 daemon；都沒有回 None。"""
    legacy = info["pools"].get(KERNEL_POOL) or {}
    return legacy.get("daemon") or info.get("daemon")


def work_pools(info):
    """工作池名（kernel 這個保留名略過：舊 info 留下的 kernel 池不再有 cpu）。"""
    return [p for p in info["pools"] if p != KERNEL_POOL]


def pool_location(info, pool):
    """池 P 在 info 裡的位置 (daemon 或 None, dpool)；池不在 info 回 None。"""
    config = info["pools"].get(pool)
    if config is None:
        return None
    return config.get("daemon", info.get("daemon")), config["dpool"]


# ---- init（kernel-cli init） ----

CONFIG_EXAMPLE = ('{"pools": {"default": {"count": 2}, "llm": {"count": 1, '
                  '"envs": {"AOS_LLM_CONFIG": "/abs/llm.json"}}}}')


def info_from_config(config, home=None, daemon=None, env=None):
    """init：config 只放 kernel 參數＋池；補 _metainfo、預設值、daemon。回（已驗的）要寫的 info。"""
    home = Path(home or ".").absolute()
    env = os.environ if env is None else env
    if config is None:
        config = {}
    if not isinstance(config, dict) or any(k.startswith("$") for k in config):
        _bad("--config 的頂層必須是字面物件（JSON null、陣列、字串都不行）", [])
    if "cpus" in config:
        # 納入後文件組實測：舊格式 {"cpus": …} 會被默默忽略、只剩 kernel 池；改成明講。
        _bad("cpus 是 proto5 舊格式（逐顆列 cpu）；改寫成 pools 池表，例：" + CONFIG_EXAMPLE, ["cpus"])
    info = copy.deepcopy(config)
    info.setdefault("_metainfo", {"_type": "kernel", "_version": 2})
    pools = info.setdefault("pools", {})
    if not isinstance(pools, dict) or any(k.startswith("$") for k in pools):
        _bad("pools 必須是字面物件，例：" + CONFIG_EXAMPLE, ["pools"])
    if KERNEL_POOL in pools:
        _bad("kernel 是保留名：one-boot 起 kernel 不再有自己的池（tick 由 daemon 開），池表別寫它", ["pools", KERNEL_POOL])
    for key, value in DEFAULTS.items():
        info.setdefault(key, value)
    if daemon:
        info["daemon"] = os.path.abspath(os.path.expanduser(daemon))
    elif "daemon" not in info and env.get("AOS_DAEMON_HOME"):
        info["daemon"] = os.path.abspath(os.path.expanduser(env["AOS_DAEMON_HOME"]))
    _parse_info(home, copy.deepcopy(info))
    return info


def init(home, config=None, daemon=None):
    home = Path(home).absolute()
    if (home / "info.json").exists():
        raise KernelError("AlreadyExists", "拒絕覆蓋既有的家：%s" % home)
    info = info_from_config(config, home, daemon)
    home.mkdir(parents=True, exist_ok=True)
    aos_home.ensure_queue(home)
    (home / "pools").mkdir(exist_ok=True)
    aos_home.write_json(home / "info.json", info)
    return str(home)


# ---- 帳本 ----

def new_state(chain, cli):
    return {"chain": chain, "cli": str(cli), "last_seq": 0, "phase": "running", "halting": False,
            "pools": {}, "busy": {}, "on": {}, "recent": [], "ready": {}, "delayed": [], "stale": {},
            "procs": {}, "acks": [], "replies": [], "deletes": [], "sends": [], "features": list(FEATURES)}


def new_pool(daemon, dpool):
    """帳本裡新池的一格（kernel-pools §2 第 0 步）。want＝None 表示還沒處理過 info。"""
    return {"daemon": daemon, "dpool": dpool, "want": None, "sent": {"count": 0, "skip": []}, "pending": None,
            "free": [], "draining": 0, "dirty": True, "redeclare": True,
            "envs_digest": None, "error": None, "retry_at": None, "acquired": False, "boot_redeclare": False}


def chain_epoch(chain):
    return int(str(chain).split("-", 1)[0])


def classify(proc, response, info, now=None):
    """proto5 §4 反覆行程判定表；不動輸入，回新的行程紀錄。

    09-24 停車：102＝停車（not_before 推到 park_ms 後、記 parked）。woken 判完一律清掉。
    09-24 tick-gap：103＝做了事、馬上再排（not_before＝現在）；退 0／101／102 而這格跑著時被叫醒過（woken）也馬上再排
    （以前當 101 等 interval_ms）。失敗的列照舊等 interval_ms，不因為被叫醒就連環重試。
    """
    proc = copy.deepcopy(proc)
    woken = proc.pop("woken", False)
    proc.pop("parked", None)
    park = soon = False
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
            soon = woken
        elif result.get("code") == PARK_EXIT:
            proc["fails"] = 0
            park, soon = not woken, woken
        elif result.get("code") == AGAIN_EXIT:
            proc["fails"] = 0
            soon = True
        else:
            proc["fails"] += 1
    if info["bad_after"] != 0 and proc["fails"] >= info["bad_after"]:
        proc["status"] = "bad"
    else:
        delay = proc.get("park_ms", info.get("park_ms", PARK_MS)) if park else 0 if soon else proc["interval_ms"]
        proc.update(status="queued", not_before=(time.time() if now is None else now) + delay / 1000)
        if park:
            proc["parked"] = True
    return proc


def _put(home, name, obj):
    try:
        aos_home.post_request(home, name, obj)
    except aos_home.RequestExists:
        pass


def _body_error(code, msg):
    return {"error": {"code": -32000, "message": msg, "data": {"code": code}}}


def error_code(response):
    """回音的錯誤碼：看 data.code，沒有就用 str(code)（D-3）。"""
    error = response.get("error") or {}
    data = error.get("data")
    if isinstance(data, dict) and isinstance(data.get("code"), str):
        return data["code"]
    return str(error.get("code"))
