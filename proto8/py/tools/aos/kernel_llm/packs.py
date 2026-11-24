# 問腦的設定與能力包：讀 kernel.json（指示詞用到才解）、查代號、釘死的參數、思考程度（reasoning_efforts）、窗 endpoints.json。
import json
import os
import subprocess

from aos import refpath as aos_refpath
import budget
import runner
from budget import MAX, dumps, is_count
from aos.tool_io import Error

TOP_KEYS = ("slots", "reserved", "aging_cycles", "budget", "exec", "endpoint", "timeout_ms", "backends")
PACK_KEYS = ("exec", "slots", "budget", "speed", "backend", "session_key", "reasoning_efforts")   # kernel 看的，不交給端點函數
WINDOW_KEYS = ("slots", "budget", "speed", "cost", "context", "summary", "fixed", "backend", "reasoning_efforts")
# 思考程度（11-21 使用者「或是llm kernel要接受的請求中，允許添加思考程度這個key，然後具體的則由llm kernel處理」「走乙吧」
# 「effort...改叫reasoning_effort吧，說清楚」）：信的 body 寫 "reasoning_effort": 程度名（跟 endpoint 並排，給 kernel 看；
# 不是 request 裡送上游的同名參數）。包的 reasoning_efforts＝它收哪些程度（名字陣列；"forward"＝不在這層查、交給下一層 kernel）。
# 收了＝request.json 頂層多 reasoning_effort，怎麼送上游是端點函數的事（llm_http：api responses 接 configuration_update、chat 填參數）。
# 包沒寫 reasoning_efforts＝不認這個鍵、照原樣送（C-48）；寫了但不收那個程度＝RequestBad。
SPEEDS = ("fast", "normal", "slow")


def has_directive(value):
    if isinstance(value, dict):
        return any(key.startswith("$") or has_directive(item) for key, item in value.items())
    return isinstance(value, list) and any(has_directive(item) for item in value)


def resolve(value, base):
    """有指示詞才叫 aos-directive；base＝(相對 $ref 的起點夾, 這格所在的檔)。解不開丟它自己的代號與原因。"""
    if not has_directive(value):
        return value
    try:
        result = subprocess.run(["aos-directive", "--file", base[1]], input=json.dumps(value, ensure_ascii=False),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=base[0])
    except OSError as error:
        raise Error("CommandMissing", "aos-directive failed to start (must be on PATH): %s" % error) from None
    if result.returncode != 0:
        raise Error(*runner.error_of(result.stderr, "aos-directive",
                                     ("DirectiveBad", "aos-directive exited %d" % result.returncode)))
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise Error("DirectiveBad", "aos-directive printed no JSON") from None


def split_hash(spec):
    path, mark, pointer = spec.partition("#")
    if mark and not pointer.startswith("/"):
        raise Error("CfgBad", "address must be FILE#/POINTER (# must be followed by /): " + spec)
    return path, pointer


def target_abs(target, base):
    """aos-exec 的目標（資料夾、檔、`檔#/指標`）：相對的從 base 算、轉成絕對。"""
    path, pointer = split_hash(target)
    path = os.path.abspath(os.path.join(base, path))
    return path + "#" + pointer if pointer else path


def _at(doc, pointer):
    for part in pointer.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    return doc


def _load(spec):
    try:
        path, pointer = split_hash(spec)
    except Error:
        raise Error("CfgBad", "config %s: # must be followed by /" % spec) from None
    try:
        with open(path, "rb") as stream:
            doc = json.loads(stream.read())
    except FileNotFoundError:
        raise Error("CfgMissing", "cannot read %s: No such file or directory" % path) from None
    except OSError as error:
        raise Error("CfgBad", "cannot read %s: %s" % (path, error.strerror)) from None
    except (ValueError, UnicodeError):
        raise Error("CfgBad", "not JSON: " + path) from None
    if pointer:
        try:
            doc = _at(doc, pointer)
        except (KeyError, IndexError, ValueError, TypeError):
            raise Error("CfgMissing", "config pointer not found: " + spec) from None
    return doc, os.path.abspath(path)


def _endpoints(raw, base):
    """表本身只換一層（整張可以是 {"$ref": 檔}），每組裡的指示詞留到用的時候才解。"""
    if isinstance(raw, dict) and set(raw) == {"$ref"} and isinstance(raw["$ref"], str):
        try:                                             # 跟 index 同一支（11-13 ref-path-rules）；寫法不合或算不出來交給 aos-directive
            file, toks = aos_refpath.spot(raw["$ref"], file=base[1], folder=base[0])
        except ValueError:
            return resolve(raw, base), base
        try:
            with open(file, "rb") as stream:
                table = json.loads(stream.read())
            if toks:
                table = _at(table, "".join("/" + tok for tok in toks))
        except (OSError, ValueError, UnicodeError, KeyError, IndexError, TypeError):
            return resolve(raw, base), base              # 讀不了交給 aos-directive 說原因
        if not (isinstance(table, dict) and any(key.startswith("$") for key in table)):
            return table, (os.path.dirname(file), file)
    if isinstance(raw, dict) and any(key.startswith("$") for key in raw):
        return resolve(raw, base), base                  # 其他寫法：整張一次解開
    return raw, base


def parse_pack(group, name, backends):
    """讀一組的 slots／budget／speed／backend 與窗裡那幾格；形狀不對丟 CfgBad。"""
    at = "kernel.json endpoints." + name
    pack = {"backend": None, "slots": None, "max_calls": None, "max_tokens": None, "speed": 1, "attrs": {},
            "session_key": None}
    if "backend" in group:
        backend = group["backend"]
        if not isinstance(backend, str) or backend not in backends:
            raise Error("CfgBad", "%s.backend must name a declared backend, got %s" % (at, dumps(backend)))
        pack["backend"] = pack["attrs"]["backend"] = backend
    slots = group.get("slots")
    if slots is not None:
        if not is_count(slots) or not 1 <= slots <= MAX:
            raise Error("CfgBad", "%s.slots must be a positive integer (letters of this endpoint in flight at once), "
                                  "got %s" % (at, dumps(slots)))
        pack["slots"] = pack["attrs"]["slots"] = slots
    limits = group.get("budget")
    if limits is not None:
        if not isinstance(limits, dict):
            raise Error("CfgBad", '%s.budget must be {"max_calls", "max_tokens"}, got %s' % (at, dumps(limits)))
        for key in ("window", "spent"):
            if key in limits:
                raise Error("CfgBad", "%s.budget.%s is not allowed: an endpoint budget uses the kernel's budget.%s "
                                      "(only max_calls, max_tokens here)" % (at, key, key))
        for key in ("max_calls", "max_tokens"):
            if limits.get(key) is None:
                continue
            if not is_count(limits[key]):
                raise Error("CfgBad", "%s.budget.%s must be a non-negative integer (limit per window), got %s"
                            % (at, key, dumps(limits[key])))
            pack[key] = limits[key]
    speed = group.get("speed")
    if speed is not None:
        if not isinstance(speed, str) or speed not in SPEEDS:
            raise Error("CfgBad", '%s.speed must be "fast", "normal" or "slow", got %s' % (at, dumps(speed)))
        pack["speed"] = SPEEDS.index(speed)
    pack["attrs"]["speed"] = SPEEDS[pack["speed"]]
    for key in ("cost", "context", "summary"):
        if key in group:
            pack["attrs"][key] = group[key]
    session_key = group.get("session_key")
    if session_key is not None:
        if not isinstance(session_key, str) or not session_key:
            raise Error("CfgBad", "%s.session_key must be a non-empty string (the request key that carries a fixed "
                                  "session id per sender, e.g. litellm_session_id), got %s" % (at, dumps(session_key)))
        pack["session_key"] = session_key
    fixed = group.get("fixed")
    if fixed is not None and not isinstance(fixed, dict):
        raise Error("CfgBad", "%s.fixed must be an object (sampling parameters pinned by this endpoint), got %s"
                    % (at, dumps(fixed)))
    if "reasoning_efforts" in group:
        pack["reasoning_efforts"] = pack["attrs"]["reasoning_efforts"] = check_efforts(group["reasoning_efforts"], at)
    return pack


def check_efforts(efforts, at):
    """reasoning_efforts＝程度名的非空陣列（不重複）或 "forward"；回原值，形狀不對丟 CfgBad。"""
    if efforts == "forward":
        return efforts
    if (not isinstance(efforts, list) or not efforts or len(set(map(str, efforts))) != len(efforts)
            or not all(isinstance(level, str) and level for level in efforts)):
        raise Error("CfgBad", '%s.reasoning_efforts must be a non-empty array of distinct effort names, or "forward" '
                              '(hand the letter\'s reasoning_effort to the next kernel unchecked), got %s'
                    % (at, dumps(efforts)))
    return list(efforts)


def accepted_effort(pack, body, name):
    """信的 body.reasoning_effort 這包收不收：收＝回程度名（寫進 request.json 頂層）；信沒寫或包沒寫 reasoning_efforts＝None。
    寫壞或這包不收＝丟 RequestBad。"""
    if "reasoning_effort" not in body:
        return None
    level = body["reasoning_effort"]
    if not isinstance(level, str) or not level:
        raise Error("RequestBad", "body.reasoning_effort must be a non-empty string (an effort name the endpoint offers, "
                                  "see aos-llm ls --json; not the request's own reasoning_effort parameter), got "
                    + dumps(level))
    efforts = pack.get("reasoning_efforts")
    if efforts is None:
        return None
    if efforts != "forward" and level not in efforts:
        raise Error("RequestBad", "reasoning_effort %s is not offered by endpoint %s (it offers: %s)"
                    % (dumps(level), name, ", ".join(efforts)))
    return level


def _read_packs(endpoints, base, backends):
    """每組只解窗與格數要看的那幾格；某組解不開或壞了＝記 error，那組的信照樣回錯。"""
    subsets = {name: ({key: raw[key] for key in WINDOW_KEYS if key in raw} if isinstance(raw, dict) else raw)
               for name, raw in endpoints.items()}
    try:
        resolved = resolve(subsets, base)
    except Error:
        resolved = None                                  # 有一組解不開：逐組解，才知道是哪一組
    packs = {}
    for name in sorted(endpoints):
        try:
            group = resolved[name] if resolved is not None else resolve(subsets[name], base)
            if not isinstance(group, dict):
                raise Error("CfgBad", "kernel.json endpoints.%s must be an object (llm settings), got %s"
                            % (name, dumps(group)))
            packs[name] = parse_pack(group, name, backends)
        except Error as error:
            packs[name] = {"error": "%s %s" % (error.code, error)}
    return packs


def read_cfg(spec, stack):
    """讀問腦的 kernel.json。頂層的格先解；endpoints 每組到用的時候才解。壞了丟 CfgMissing／CfgBad／指示詞自己的代號。"""
    doc, file = _load(spec)
    base = (os.path.dirname(file), file)
    if isinstance(doc, dict):
        top = resolve({key: doc[key] for key in TOP_KEYS if key in doc}, base)
        doc = dict(doc, **top)
    else:
        raise Error("CfgBad", spec + " must be a JSON object")
    cfg = {"base": base[0], "file": file, "slots": 1, "reserved_high": 0, "aging_cycles": 3,
           "backends": {}, "endpoint": None, "timeout_ms": None, "hooks": {}, "groups": {}}   # hooks：_entry 照定義夾的 hookeds 讀（11-21）
    if "aging_cycles" in doc:
        aging = doc["aging_cycles"]
        if not is_count(aging) or not 1 <= aging <= MAX:
            raise Error("CfgBad", "aging_cycles must be a positive integer (cycles per priority level), got "
                        + dumps(aging))
        cfg["aging_cycles"] = aging
    slots = doc.get("slots")
    if slots is not None:
        if not is_count(slots) or not 1 <= slots <= MAX:
            raise Error("CfgBad", "slots must be a positive integer (letters run at once), got " + dumps(slots))
        cfg["slots"] = slots
    if "reserved" in doc:
        reserved = doc["reserved"]
        if not isinstance(reserved, dict):
            raise Error("CfgBad", "reserved must be an object with only an optional high count, got " + dumps(reserved))
        for key in reserved:
            if key != "high":
                raise Error("CfgBad", "reserved has an unknown key: %s (only high is allowed)" % key)
            if not is_count(reserved[key]) or reserved[key] >= cfg["slots"]:
                raise Error("CfgBad", "reserved.high must be a non-negative integer smaller than slots, got "
                            + dumps(reserved[key]))
            cfg["reserved_high"] = reserved[key]
    if "backends" in doc:
        if not isinstance(doc["backends"], dict):
            raise Error("CfgBad", "backends must be an object of backend limits")
        for name in doc["backends"]:
            limits = doc["backends"][name]
            if not isinstance(limits, dict) or not is_count(limits.get("slots")) or not 1 <= limits["slots"] <= MAX:
                raise Error("CfgBad", "backends.%s.slots must be a positive integer" % name)
            backend = {"slots": limits["slots"], "max_packs": None}
            if "max_packs" in limits:
                if not is_count(limits["max_packs"]) or not 1 <= limits["max_packs"] <= MAX:
                    raise Error("CfgBad", "backends.%s.max_packs must be a positive integer" % name)
                backend["max_packs"] = limits["max_packs"]
            cfg["backends"][name] = backend
    cfg["budget"] = budget.parse(doc.get("budget"), base[0], stack)
    budget.warn(cfg["budget"], stack)
    target = doc.get("exec")
    if not isinstance(target, str) or not target:
        raise Error("CfgBad", "exec must be a non-empty string (the endpoint function: a directory, a file or "
                              "`file#/pointer`, relative to kernel.json's directory), got " + dumps(target))
    cfg["exec"] = target_abs(target, base[0])
    if "endpoints" not in doc:
        raise Error("CfgBad", "missing endpoints (name -> llm settings)")
    endpoints, cfg["endpoints_base"] = _endpoints(doc["endpoints"], base)
    if not isinstance(endpoints, dict) or not endpoints:
        raise Error("CfgBad", "endpoints must be a non-empty object (name -> llm settings), got " + dumps(endpoints))
    cfg["endpoints"] = endpoints
    cfg["packs"] = _read_packs(endpoints, cfg["endpoints_base"], cfg["backends"])
    default = doc.get("endpoint")
    if default is not None:
        if not isinstance(default, str) or default not in endpoints:
            raise Error("CfgBad", "endpoint (the default name) must be a name in endpoints, got " + dumps(default))
        cfg["endpoint"] = default
    timeout = doc.get("timeout_ms")
    if timeout is not None:
        if not is_count(timeout) or timeout > MAX:
            raise Error("CfgBad", "timeout_ms must be a non-negative integer (time limit for the endpoint function), "
                                  "got " + dumps(timeout))
        cfg["timeout_ms"] = timeout or None
    return cfg


def window(packs):
    """窗 endpoints.json 的內容：每個代號的屬性；壞的那組＝{"error": "代號 原因"}。"""
    return {name: ({"error": pack["error"]} if "error" in pack else pack["attrs"]) for name, pack in packs.items()}


def write_window(stack, packs):
    path = os.path.join(stack, "endpoints.json")
    doc = window(packs)
    try:
        with open(path, "rb") as stream:
            if json.loads(stream.read()) == doc:
                return
    except (OSError, ValueError, UnicodeError):
        pass
    try:
        runner.write_json(path, doc)
    except runner.Failed as error:
        raise Error(error.code, error.msg) from None


def limits(cfg):
    """窗 slots.json 的內容：整台的格數（kernel.json 頂層 slots、reserved、backends，解完的值）。"""
    doc = {"slots": cfg["slots"], "reserved": {"high": cfg["reserved_high"]}}
    if cfg["backends"]:
        doc["backends"] = {name: {key: value for key, value in limit.items() if value is not None}
                           for name, limit in sorted(cfg["backends"].items())}
    return doc


def write_limits(stack, cfg):
    """寫窗 slots.json（給 aos-llm ls 印整台那行）；跟現有的一樣就不寫。"""
    path = os.path.join(stack, "slots.json")
    doc = limits(cfg)
    try:
        with open(path, "rb") as stream:
            if json.loads(stream.read()) == doc:
                return
    except (OSError, ValueError, UnicodeError):
        pass
    try:
        runner.write_json(path, doc)
    except runner.Failed as error:
        raise Error(error.code, error.msg) from None


def group_of(cfg, name):
    """那個代號整組解開（同一輪只解一次）；解不開丟指示詞自己的代號。"""
    if name not in cfg["groups"]:
        try:
            cfg["groups"][name] = resolve(cfg["endpoints"][name], cfg["endpoints_base"])
        except Error as error:
            cfg["groups"][name] = error
    if isinstance(cfg["groups"][name], Error):
        raise cfg["groups"][name]
    return cfg["groups"][name]


def fixed_clash(group, request, name):
    """信的 request 撞到包釘死的參數時回原因；沒撞回 None。"""
    fixed = group["fixed"] if isinstance(group.get("fixed"), dict) else {}
    keys = [key for key in request if key in fixed or (key == "model" and "model" in group)]
    if not keys:
        return None
    one = len(keys) == 1
    return "%s %s fixed by endpoint %s (remove %s from the request; to change %s pick another endpoint name)" % (
        ", ".join(keys), "is" if one else "are", name, "it" if one else "them", "it" if one else "them")


def pick(cfg, body):
    """查代號、解那組、定端點函數。回 (代號, 包, 交給函數的那組, 端點函數)；不行丟要回給那封信的代號與原因。"""
    if "endpoint" in body:
        name = body["endpoint"]
    elif cfg["endpoint"] is not None:
        name = cfg["endpoint"]
    else:
        raise Error("EndpointMissing", "the letter has no endpoint (name) and kernel.json has no default endpoint")
    if name not in cfg["endpoints"]:
        raise Error("EndpointUnknown", "endpoint %s is not in kernel.json endpoints" % name)
    try:
        group = group_of(cfg, name)
    except Error as error:
        raise Error(error.code, "kernel.json endpoints.%s: %s" % (name, error)) from None
    if not isinstance(group, dict):
        raise Error("CfgBad", "kernel.json endpoints.%s must be an object (llm settings), got %s" % (name, dumps(group)))
    target = cfg["exec"]
    if "exec" in group:
        if not isinstance(group["exec"], str) or not group["exec"]:
            raise Error("CfgBad", "kernel.json endpoints.%s.exec must be a non-empty string, got %s"
                        % (name, dumps(group["exec"])))
        target = target_abs(group["exec"], cfg["base"])
    pack = parse_pack(group, name, cfg["backends"])
    pack["reasoning_effort"] = accepted_effort(pack, body, name)
    clash = fixed_clash(group, body["request"], name)
    if clash:
        raise Error("RequestBad", clash)
    return name, pack, {key: value for key, value in group.items() if key not in PACK_KEYS}, target


def target_for(cfg, proc):
    """重掛時照 proc.json 記的代號從現在的 kernel.json 再算端點函數；算不出來用 proc.json 記的。"""
    kept = proc.get("exec", cfg["exec"])
    name = proc.get("endpoint")
    if not isinstance(name, str) or name not in cfg["endpoints"]:
        return kept
    try:
        group = group_of(cfg, name)
        if not isinstance(group, dict):
            return kept
        if "exec" not in group:
            return cfg["exec"]
        if not isinstance(group["exec"], str) or not group["exec"]:
            return kept
        return target_abs(group["exec"], cfg["base"])
    except Error:
        return kept
