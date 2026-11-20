"""tool_spec - 工具說明書的內部零件：參數、_tooldef、_metainfo 怎麼組與怎麼驗，寫進「位置」（資料夾的兩個檔或 JSON 物件的兩個鍵），掃原始碼裡的 fn.fail 代號。

使用者 11-10 深夜（thinking 2026-11/10/tools-def）：「給python一種，順便弄個好用的lib，方便AI弄json schema, metainfo啥的。」
11-20 起寫工具的寫法是 aos.py.fn（@fn.tool＋fn.main，使用者選「新名字 fn」，線 aos-pylib-k1-1120）：入口 main() 與印結果搬去
aos/fn_run.py，fn.fail 也在那裡；這支留給 fn_mark、fn_run 與 tools_def（分階段 add_tooldef／add_metainfo、check）用，寫工具的人不直接 import。
純標準庫；接在 tool_io 上（錯誤行、--help、旗標、不認得的鍵＝ArgumentsBad 都走 tool_io，這裡不另拼）。

  param(name, type, description, ...)   → 一個參數（寫錯記成 bad，tooldef 再報 SpecBad）
  tooldef(description, params, errors)  → dict（OpenAI function 去掉 name，外加 tool_io 讀的 errors）
  metainfo(description, meta)            → dict（N-68 的通用 key，沒給的補保守預設）
  write(location, td, mi)                位置＝資料夾（寫 _tooldef.json／_metainfo.json，暫存檔＋改名；寫檔後端在 aos/spec_base）
                                         或 檔.json／檔.json#/指標（經 aos-json set 寫 _tooldef／_metainfo 鍵）
  errors_in(path)                        原始碼裡寫到的 fail("代號", …)（fn.fail 也認），照出現順序
  tooldef_problems／metainfo_problems     手寫的說明書有什麼毛病（tools_def check 用）"""
import json, os, re, subprocess

from aos import spec_base
from aos.spec_base import SpecBad  # noqa: F401（對外的名字 ts.SpecBad；跟 agent_spec 同一個類別，線 aos-pylib-k0-1120）

TYPES = ("string", "integer", "number", "boolean", "array", "object")
CODE_RE = re.compile(r"[A-Z][A-Za-z0-9]*\Z")
NAME_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
FAIL_RE = re.compile(r"""\bfail\(\s*["']([A-Z][A-Za-z0-9]*)["']""")
META_DEFAULTS = {"resource": "cpu", "side_effect": False, "idempotent": True, "deterministic": True,
                 "interrupt": "safe", "parallel": True, "arbitrary_exec": False,
                 "cost": {"time_ms": 100}, "timeout_ms": 10000}
META_BOOLS = ("side_effect", "idempotent", "deterministic", "parallel", "arbitrary_exec")
_NO = object()


def _matches(value, t):
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, {"string": str, "boolean": bool, "array": list, "object": dict}[t])


def param(name, type="string", description="", required=None, default=_NO, enum=None, items=None):
    """一個參數；寫錯不在這裡丟（模組最上層丟出會變 traceback），記成 bad，main／tooldef 再報 SpecBad。"""
    try:
        return _param(name, type, description, required, default, enum, items)
    except SpecBad as e:
        return {"name": name, "bad": str(e)}


def _param(name, type, description, required, default, enum, items):
    """一個參數。type：string／integer／number／boolean／array／object；items＝array 的元素型別；
    required 沒給＝沒有 default 就必填；給了 default＝選填、沒給時 run 拿到的是 default。"""
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise SpecBad("param name %r must be lower case letters, digits and _ (like \"max_items\")" % (name,))
    if type not in TYPES:
        raise SpecBad("param %s: type %r must be one of %s" % (name, type, ", ".join(TYPES)))
    if not isinstance(description, str) or not description.strip():
        raise SpecBad("param %s needs a description (one short sentence for the model)" % name)
    node = {"type": type, "description": description}
    if items is not None:
        if type != "array" or items not in TYPES:
            raise SpecBad("param %s: items only goes with type \"array\" and must be one of %s" % (name, ", ".join(TYPES)))
        node["items"] = {"type": items}
    if enum is not None:
        if not isinstance(enum, (list, tuple)) or not enum or not all(_matches(x, type) for x in enum):
            raise SpecBad("param %s: enum must be a non-empty list of %s values" % (name, type))
        node["enum"] = list(enum)
    if default is not _NO:
        if not _matches(default, type) or (enum is not None and default not in enum):
            raise SpecBad("param %s: default %r is not a %s%s" % (name, default, type, " from enum" if enum is not None else ""))
        node["default"] = default
    if required is None:
        required = default is _NO
    if required and default is not _NO:
        raise SpecBad("param %s: a param with a default cannot be required" % name)
    return {"name": name, "node": node, "required": bool(required)}


def tooldef(description, params=(), errors=()):
    """宣告 → _tooldef 的內容。errors 開頭固定 ArgumentsBad、結尾 RunFailed（tool_spec 自己會出的）。"""
    if not isinstance(description, str) or not description.strip():
        raise SpecBad("description must be a non-empty string: what the tool does, with one example call")
    props, required = {}, []
    for p in params:
        if isinstance(p, dict) and "bad" in p:
            raise SpecBad(p["bad"])
        if not isinstance(p, dict) or "node" not in p:
            raise SpecBad("each item of params must come from param(...), got %r" % (p,))
        if p["name"] in props:
            raise SpecBad("param %s is declared twice" % p["name"])
        props[p["name"]] = p["node"]
        if p["required"]:
            required.append(p["name"])
    codes = ["ArgumentsBad"]
    for c in list(errors) + ["RunFailed"]:
        if not isinstance(c, str) or not CODE_RE.match(c):
            raise SpecBad("error code %r must be CamelCase letters like \"CityMissing\"" % (c,))
        if c not in codes:
            codes.append(c)
    schema = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return {"description": description.strip(), "parameters": schema, "errors": codes}


def summary_of(description):
    """說明的第一句（到第一個「. 」或換行），給 metainfo 的 summary。"""
    first = description.strip().split("\n", 1)[0]
    m = re.search(r"\.\s", first + " ")
    return (first[:m.start()] if m else first).strip()


def metainfo(description, meta=None):
    """宣告 → _metainfo 的內容（N-68 通用 key）。meta 只寫跟預設不同的：例 {"side_effect": True}。"""
    if meta is not None and not isinstance(meta, dict):
        raise SpecBad("meta must be a dict like {\"side_effect\": True}")
    out = {"summary": summary_of(description)}
    out.update(json.loads(json.dumps(META_DEFAULTS)))
    for k, v in (meta or {}).items():
        out[k] = v
    problems = metainfo_problems(out)
    if problems:
        raise SpecBad("meta " + problems[0])
    return out


def metainfo_problems(mi):
    """一份 _metainfo 的毛病（英文句子串列，空＝沒毛病）；只查 N-68 通用 key 有寫的那些，其他 key 照收（C-14）。"""
    if not isinstance(mi, dict):
        return ["must be a JSON object"]
    out = []
    for k in META_BOOLS:
        if k in mi and not isinstance(mi[k], bool):
            out.append("%s must be true or false" % k)
    for k in ("summary", "resource", "interrupt"):
        if k in mi and (not isinstance(mi[k], str) or not mi[k]):
            out.append("%s must be a non-empty string" % k)
    t = mi.get("timeout_ms")
    if "timeout_ms" in mi and (not isinstance(t, int) or isinstance(t, bool) or t < 0):
        out.append("timeout_ms must be a whole number of milliseconds >= 0 (0 = no limit; the tool is killed after it)")
    if "cost" in mi and not isinstance(mi["cost"], dict):
        out.append("cost must be an object like {\"time_ms\": 100}")
    return out


def tooldef_problems(td):
    """一份 _tooldef 的毛病（英文句子串列）：模型要的 description、parameters 物件與各參數的 type／description。"""
    if not isinstance(td, dict):
        return ["must be a JSON object"]
    out = []
    if not isinstance(td.get("description"), str) or not td["description"].strip():
        out.append("description must be a non-empty string (what the tool does, with an example)")
    ps = td.get("parameters")
    if not isinstance(ps, dict) or ps.get("type") != "object":
        return out + ['parameters must be a JSON Schema object: {"type": "object", "properties": {...}}']
    props = ps.get("properties", {})
    if not isinstance(props, dict):
        return out + ["parameters.properties must be an object"]
    for k, node in props.items():
        t = node.get("type") if isinstance(node, dict) else None
        ts_ = t if isinstance(t, list) else [t]
        if not ts_ or not all(x in TYPES + ("null",) for x in ts_):
            out.append("parameter %s: type must be one of %s" % (k, ", ".join(TYPES)))
        if not isinstance(node, dict) or not isinstance(node.get("description"), str) or not node["description"].strip():
            out.append("parameter %s needs a description" % k)
    req = ps.get("required", [])
    if not isinstance(req, list) or not all(isinstance(x, str) and x in props for x in req):
        out.append("parameters.required must list names from properties")
    return out


def split_location(location):
    """「位置」→ (路徑, 指標)：資料夾或檔＝指標 None；檔.json#/a/b＝("檔.json", "/a/b")（第一個 # 就切，N-62）。"""
    path, sep, ptr = location.partition("#")
    if sep and ptr and not ptr.startswith("/"):
        raise SpecBad("location %r: after # write a JSON pointer starting with / (like file.json#/tools/mul)" % location)
    return path, (ptr if sep else None)


def write(location, td=None, mi=None):
    """把 td／mi 寫進位置；回寫了哪些（給人看的字串串列）。資料夾＝兩個檔（各自經 spec_base.write_files 暫存檔＋改名）；
    JSON 檔或 檔#/指標＝兩個鍵（aos-json set）。"""
    path, ptr = split_location(location)
    done = []
    for key, value in (("_tooldef", td), ("_metainfo", mi)):
        if value is None:
            continue
        if ptr is None and os.path.isdir(path):
            target = os.path.join(path, key + ".json")
            spec_base.write_files(path, {key + ".json": value})
        else:
            target = "%s#%s/%s" % (path, (ptr or "").rstrip("/"), key)
            r = subprocess.run(["aos-json", "set", "--parents", target, json.dumps(value, ensure_ascii=False)],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if r.returncode != 0:
                last = (r.stderr.strip().splitlines() or ["aos-json exited %d" % r.returncode])[-1]
                raise OSError("cannot write %s: %s" % (target, last))
        done.append(target)
    return done


def errors_in(path):
    """原始碼裡寫到的 fail("代號", …)（fn.fail 也是），照出現順序；讀不了＝[]。"""
    try:
        with open(path, encoding="utf-8") as f:
            return list(dict.fromkeys(FAIL_RE.findall(f.read())))
    except (OSError, UnicodeError):
        return []
