"""agent 資料夾的讀、驗——「這個資料夾是不是 agent、它的人格／記憶／工具／引擎長什麼樣」。

規範：資料夾本身（`_metainfo`、指示詞解不解、共用代號）在 ../spec/agent.md §1～§3、§5；
`system`／`history`／`tools`／`engine` 四格與它們指到的檔在 ../spec/agent.md §3。
這個檔只讀、只驗、不寫任何檔，也**不碰 `state.json`**（那是 aos-agent 走格子時的事）；跑工具也不在這裡。

分兩種讀法（agent.md §2）：

- `info.json`（人寫的總表）**每一格都解指示詞**（含 `_metainfo`、`engine`），機制全交給
  aos_directives.py：中心路徑（`$ref` 的相對檔名從哪找）＝agent 資料夾；位置＝實體路徑
  （`/tools/0`…）；容器（`tools` 陣列、`engine`、`engine.params`）用 `resolve_located` 走進去，
  每個頂層欄位各自從空的循環鏈開始。agent.md 沒給任何 `$opt` 選項表，所以哪一格放了
  `$opt` 都是 `UnknownOption`。
- `system`／`history`／`tools` 指到的檔**原樣讀、不解指示詞**：那是內容（人格文字、模型吐出
  來的對話、工具的 schema 與 inst），裡面什麼 `$` 都可能有。

驗不過就丟 `AgentError(code, msg)`，`str(e)` 是「代號: 白話」；代號照 agent.md §5
（`NotAnAgent`、`ReadFailed`、`JsonSyntax`、`NotAnObject`、`NotAnArray`、`MetainfoInvalid`、
`UnsupportedVersion`、`FieldTypeMismatch`、`MessageInvalid`、`ToolInvalid`、`EngineInvalid`）；
指示詞機制丟的 `DirectiveError` 在 `load()` 裡包成同形狀的 `AgentError`（代號照 directives.md §6），
呼叫者只要接一種。

`load(dir)` 回一個 dict：

    dir           agent 資料夾的絕對路徑
    metainfo      {"_type": "llm_agent", "_version": 1}
    system        system prompt 本文（字串；檔不存在＝""）
    system_path   人格檔的絕對路徑
    history       記憶（陣列；檔不存在＝[]），每則照 agent.md §3.2 驗過、原樣
    history_path  記憶檔的絕對路徑
    tools         送模型用的工具表：所有檔接成一個陣列、每個元素去掉所有 `_` 開頭的 key
    tools_raw     原始工具表：同順序、含 `_meta` 與可選的 `_timeout_ms`／`_run`（跑工具時用）
    tool_paths    工具檔的絕對路徑，照 info.json 的順序
    tool_cpu      工具 cpu 絕對路徑；沒寫＝None，有 cpu 工具時必填
    engine        {"cpu", "model", "params"}
                  cpu 必填，相對 agent 解成絕對路徑；params 沒寫＝{}
"""
import json
import os

from aos_directives import Context, DirectiveError, Document, parse_options, resolve_located

__all__ = ["AgentError", "AGENT_TYPE", "AGENT_VERSION", "DEFAULT_SYSTEM", "DEFAULT_HISTORY",
           "DEFAULT_TIMEOUT_MS", "ROLES", "load", "strip_private"]

AGENT_TYPE = "llm_agent"
AGENT_VERSION = 1
DEFAULT_SYSTEM = os.path.join("prompts", "system.json")
DEFAULT_HISTORY = os.path.join("prompts", "history.json")
DEFAULT_TIMEOUT_MS = 120000
ROLES = ("user", "assistant", "tool")
_META_FORBIDDEN = ("stdin", "stdout")       # _meta 是 inst，但這兩格由 agent 自己接（aos-llm-ask.md §2.4）
_NO_OPTIONS = {}                            # agent.md 沒定義任何 $opt 選項：哪一格放了都是 UnknownOption


class AgentError(Exception):
    """這個 agent 資料夾被拒。不是程式炸了，是檔案有問題。

    `code` 是規範的錯誤代號（`NotAnAgent`、`ToolInvalid`、`ReferenceCycle`…），`msg` 是白話；
    `str(e)` 是「代號: 白話」。
    """

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg


def load(dir, env=None):
    """讀驗 `dir` 這個 agent 資料夾，回一個欄位都填好的 dict（形狀見模組說明）。

    `env` 是 `$env` 查的表（沒給＝`os.environ`，也就是執行者自己的環境）。
    沒有 `info.json`＝`NotAnAgent`；其他代號見 agent.md §5、aos-llm-ask.md §2 與 directives.md §6。
    """
    dir = os.path.abspath(dir)
    info_path = os.path.join(dir, "info.json")
    if not os.path.exists(info_path):
        raise AgentError("NotAnAgent", "%s 裡沒有 info.json，不是 agent 資料夾" % dir)
    obj = _read_json(info_path, "info.json")
    try:
        return _load(obj, Context(Document(info_path, obj), base_dir=dir, env=env), dir)
    except DirectiveError as e:
        raise AgentError(e.code, e.msg)


def strip_private(tool):
    """一個工具元素送模型前的樣子：去掉所有 `_` 開頭的 key（`_meta`、`_note`…），其他原樣。"""
    return {k: v for k, v in tool.items() if not (isinstance(k, str) and k.startswith("_"))}


# ---------------------------------------------------------------- info.json ----

def _load(obj, ctx, dir):
    """`obj` 是 info.json 的原始 JSON，`ctx` 的文件是 info.json 自己、中心路徑是 agent 資料夾。"""
    # 頂層整份也能是指示詞；經過 $ref 之後「目前文件」就換成被引用的那份，之後每格從 top 接下去。
    top = resolve_located(obj, ctx, [])
    obj = _no_options(top.value, top.position)
    if not isinstance(obj, dict):
        raise AgentError("NotAnObject", "info.json 必須是一個 JSON 物件，不是 %s" % type(obj).__name__)

    info = {"dir": dir, "metainfo": _metainfo(obj, top)}

    system_rel = _path_field(obj, "system", DEFAULT_SYSTEM, top)
    info["system_path"] = _abspath(dir, system_rel)
    info["system"] = _read_system(info["system_path"], system_rel)

    history_rel = _path_field(obj, "history", DEFAULT_HISTORY, top)
    info["history_path"] = _abspath(dir, history_rel)
    info["history"] = _read_history(info["history_path"], history_rel)

    rels = _tools_field(obj, top)
    info["tool_paths"] = [_abspath(dir, r) for r in rels]
    info["tools_raw"] = _read_tools(info["tool_paths"], rels)
    info["tools"] = [strip_private(t) for t in info["tools_raw"]]

    tool_cpu = _path_field(obj, "tool_cpu", None, top)
    if tool_cpu is None and any(t.get("_run", "sync") == "cpu" for t in info["tools_raw"]):
        raise AgentError("FieldTypeMismatch", "info.json 有 _run:cpu 的工具，必須寫 tool_cpu 路徑")
    info["tool_cpu"] = _abspath(dir, tool_cpu) if tool_cpu is not None else None

    info["engine"] = _engine(obj, top, dir)
    return info


def _fresh(ctx):
    """同一份文件、同一個中心路徑、同一個環境，循環鏈清空——每個頂層欄位從這裡開始。"""
    return Context(ctx.doc, base_dir=ctx.base_dir, env=ctx.env)


def _field(obj, key, top):
    """把頂層欄位 `key` 這一格解到底（含 `$opt` 檢查），回 `Located`；沒這個 key 回 None。"""
    if key not in obj:
        return None
    loc = resolve_located(obj[key], _fresh(top.ctx), top.position + [key])
    return loc._replace(value=_no_options(loc.value, loc.position))


def _inner(value, loc, key):
    """容器裡再往下解一格：`value` 是 `loc.value[key]`，位置＝`loc.position + [key]`，鏈照帶。"""
    sub = resolve_located(value, loc.ctx, loc.position + [key])
    return sub._replace(value=_no_options(sub.value, sub.position))


def _deep(value, loc, key):
    """把 `loc.value[key]` 整棵解到底：每個欄位、每個元素、每個值都解，解出來的容器也走進去。"""
    sub = _inner(value, loc, key)
    v = sub.value
    if isinstance(v, dict):
        return {k: _deep(x, sub, k) for k, x in v.items()}
    if isinstance(v, list):
        return [_deep(x, sub, str(i)) for i, x in enumerate(v)]
    return v


def _no_options(value, position):
    """agent.md 沒有任何 `$opt` 選項：解出來是選項物件就是 `UnknownOption`；不是就原樣回。"""
    return parse_options(value, position, _NO_OPTIONS)[1]


def _metainfo(obj, top):
    """`_metainfo`：這是不是 agent 資料夾的記號。必填、也解指示詞（跟 inst 不同）。

    沒有＝`NotAnAgent`；不是物件＝`MetainfoInvalid`；`_type` 沒有或解完不是 `"llm_agent"`＝
    `NotAnAgent`；缺 `_version`＝`MetainfoInvalid`；`_version` 不是整數 `1`＝`UnsupportedVersion`。
    """
    loc = _field(obj, "_metainfo", top)
    if loc is None:
        raise AgentError("NotAnAgent", "info.json 沒有 _metainfo，不是 agent 資料夾")
    mi = loc.value
    if not isinstance(mi, dict):
        raise AgentError("MetainfoInvalid", "info.json 的 _metainfo 必須是一個 JSON 物件，不是 %s"
                         % type(mi).__name__)
    if "_type" not in mi:
        raise AgentError("NotAnAgent", "info.json 的 _metainfo 沒有 _type，不是 agent 資料夾")
    t = _inner(mi["_type"], loc, "_type").value
    if not (isinstance(t, str) and t == AGENT_TYPE):
        raise AgentError("NotAnAgent", "info.json 的 _metainfo._type 是 %r，不是 %r，不是 agent 資料夾"
                         % (t, AGENT_TYPE))
    if "_version" not in mi:
        raise AgentError("MetainfoInvalid", "info.json 的 _metainfo 缺了 _version")
    v = _inner(mi["_version"], loc, "_version").value
    if not (isinstance(v, int) and not isinstance(v, bool) and v == AGENT_VERSION):
        raise AgentError("UnsupportedVersion", "info.json 的 _metainfo（llm_agent）的 _version 只認得 %d，不是 %r"
                         % (AGENT_VERSION, v))
    return {"_type": AGENT_TYPE, "_version": AGENT_VERSION}


def _path_field(obj, key, default, top):
    """`system`／`history`：路徑字串，沒寫用預設；解完不是字串＝`FieldTypeMismatch`。"""
    loc = _field(obj, key, top)
    if loc is None:
        return default
    if not isinstance(loc.value, str):
        raise AgentError("FieldTypeMismatch", "info.json 的 %s 要是路徑字串，不是 %s"
                         % (key, type(loc.value).__name__))
    return loc.value


def _tools_field(obj, top):
    """`tools`：路徑字串陣列，沒寫＝`[]`；整包與每個元素都能是指示詞；型別不對＝`FieldTypeMismatch`。"""
    loc = _field(obj, "tools", top)
    if loc is None:
        return []
    if not isinstance(loc.value, list):
        raise AgentError("FieldTypeMismatch", "info.json 的 tools 要是路徑陣列，不是 %s"
                         % type(loc.value).__name__)
    out = []
    for i, x in enumerate(loc.value):
        v = _inner(x, loc, str(i)).value
        if not isinstance(v, str):
            raise AgentError("FieldTypeMismatch", "info.json 的 tools[%d] 要是路徑字串，不是 %s"
                             % (i, type(v).__name__))
        out.append(v)
    return out


def _engine(obj, top, base):
    """agent 只選 CPU、模型代號與參數；連線設定在 CPU 家。"""
    loc = _field(obj, "engine", top)
    if loc is None:
        raise AgentError("EngineInvalid", "info.json 沒有 engine（必填：cpu 跟 model）")
    eng = loc.value
    if not isinstance(eng, dict):
        raise AgentError("FieldTypeMismatch", "info.json 的 engine 要是物件，不是 %s" % type(eng).__name__)
    out = {"params": {}}
    for key in ("cpu", "model"):
        if key not in eng:
            raise AgentError("EngineInvalid", "info.json 的 engine 缺了 %s（必填）" % key)
        v = _inner(eng[key], loc, key).value
        if not isinstance(v, str) or (key == "model" and not v):
            raise AgentError("EngineInvalid", "info.json 的 engine.%s 必須是%s字串" %
                             (key, "非空" if key == "model" else "路徑"))
        out[key] = _abspath(base, v) if key == "cpu" else v
    if "params" in eng:
        v = _deep(eng["params"], loc, "params")
        if not isinstance(v, dict):
            raise AgentError("EngineInvalid", "info.json 的 engine.params 要是物件，不是 %s" % type(v).__name__)
        out["params"] = v
    return out


# ---------------------------------------------------------------- 指到的檔（原樣讀）----

def _read_json(path, shown):
    """原樣讀一份 JSON 檔：讀不到＝`ReadFailed`、不是 JSON＝`JsonSyntax`。`shown` 是錯誤訊息裡叫它什麼。"""
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise AgentError("ReadFailed", "讀不到 %s（%s）：%s" % (shown, path, e))
    try:
        return json.loads(raw)
    except ValueError as e:
        raise AgentError("JsonSyntax", "%s（%s）不是合法 JSON：%s" % (shown, path, e))


def _read_system(path, rel):
    """人格檔 `{"content": "…"}`：不存在＝空字串；`content` 要是字串。"""
    if not os.path.exists(path):
        return ""
    obj = _read_json(path, "人格檔 %s" % rel)
    if not isinstance(obj, dict):
        raise AgentError("NotAnObject", "人格檔 %s 必須是一個 JSON 物件，不是 %s" % (rel, type(obj).__name__))
    content = obj.get("content")
    if not isinstance(content, str):
        raise AgentError("FieldTypeMismatch", "人格檔 %s 的 content 要是字串，不是 %s"
                         % (rel, type(content).__name__))
    return content


def _read_history(path, rel):
    """記憶檔：一個陣列，每則照 aos-llm-ask.md §2.3 驗；不存在＝`[]`。訊息原樣回，不認得的 key 照留。"""
    if not os.path.exists(path):
        return []
    msgs = _read_json(path, "記憶檔 %s" % rel)
    if not isinstance(msgs, list):
        raise AgentError("NotAnArray", "記憶檔 %s 必須是一個 JSON 陣列，不是 %s" % (rel, type(msgs).__name__))
    for i, m in enumerate(msgs):
        _check_message(m, "記憶檔 %s 第 %d 則" % (rel, i))
    return msgs


def _check_message(m, where):
    """一則訊息：`role` 只認 user／assistant／tool；user／tool 的 `content` 要字串；tool 要有
    `tool_call_id`（字串）；assistant 至少要有字串 `content` 或陣列 `tool_calls` 其中一個。"""
    if not isinstance(m, dict):
        raise AgentError("MessageInvalid", "%s 要是物件，不是 %s" % (where, type(m).__name__))
    role = m.get("role")
    if role not in ROLES:
        raise AgentError("MessageInvalid", "%s 的 role 是 %r，只認 %s" % (where, role, "／".join(ROLES)))
    if role in ("user", "tool") and not isinstance(m.get("content"), str):
        raise AgentError("MessageInvalid", "%s（%s）的 content 要是字串，不是 %s"
                         % (where, role, type(m.get("content")).__name__))
    if role == "tool" and not isinstance(m.get("tool_call_id"), str):
        raise AgentError("MessageInvalid", "%s（tool）一定要有 tool_call_id（字串）" % where)
    if role == "assistant" and not (isinstance(m.get("content"), str) or isinstance(m.get("tool_calls"), list)):
        raise AgentError("MessageInvalid", "%s（assistant）至少要有 content（字串）或 tool_calls（陣列）其中一個"
                         % where)


def _read_tools(paths, rels):
    """工具檔：每份一定要在（不存在＝`ReadFailed`）、是陣列；元素驗 `type`／`function.name`／`_meta`；
    全部接成一個陣列（照檔的順序），合併後同名＝`ToolInvalid`。回原始元素（含 `_meta`）。"""
    merged, seen = [], {}
    for path, rel in zip(paths, rels):
        arr = _read_json(path, "工具檔 %s" % rel)
        if not isinstance(arr, list):
            raise AgentError("ToolInvalid", "工具檔 %s 必須是一個 JSON 陣列（OpenAI tools），不是 %s"
                             % (rel, type(arr).__name__))
        for i, t in enumerate(arr):
            name = _check_tool(t, "工具檔 %s 第 %d 個工具" % (rel, i))
            if name in seen:
                raise AgentError("ToolInvalid", "工具 %r 重名：%s 跟 %s 都有，合併後不能同名"
                                 % (name, seen[name], rel))
            seen[name] = rel
            merged.append(t)
    return merged


def _check_tool(t, where):
    """一個工具元素：`type`（字串）、`function`（物件）、`function.name`（非空字串）、`_meta`（物件，
    不准有 `stdin`／`stdout`）、`_timeout_ms`（正整數）、`_run`（sync／cpu）。其他東西不驗、原樣。回工具名。"""
    if not isinstance(t, dict):
        raise AgentError("ToolInvalid", "%s 要是物件，不是 %s" % (where, type(t).__name__))
    if not isinstance(t.get("type"), str):
        raise AgentError("ToolInvalid", "%s 缺了 type（字串，通常是 \"function\"）" % where)
    fn = t.get("function")
    if not isinstance(fn, dict):
        raise AgentError("ToolInvalid", "%s 缺了 function（物件）" % where)
    name = fn.get("name")
    if not isinstance(name, str) or name == "":
        raise AgentError("ToolInvalid", "%s 的 function.name 要是非空字串" % where)
    meta = t.get("_meta")
    if not isinstance(meta, dict):
        raise AgentError("ToolInvalid", "%s（%s）的 _meta 要是一份 inst（物件），%s"
                         % (where, name, "缺了" if meta is None else "不是 %s" % type(meta).__name__))
    bad = [k for k in _META_FORBIDDEN if k in meta]
    if bad:
        raise AgentError("ToolInvalid", "%s（%s）的 _meta 不准寫 %s：參數從 stdin 進、結果從 stdout 出，由 agent 自己接"
                         % (where, name, "／".join(bad)))
    if "_timeout_ms" in t:
        v = t["_timeout_ms"]
        if not (isinstance(v, int) and not isinstance(v, bool) and v > 0):
            raise AgentError("ToolInvalid", "%s（%s）的 _timeout_ms 要是正整數（毫秒），不是 %r"
                             % (where, name, v))
    if t.get("_run", "sync") not in ("sync", "cpu"):
        raise AgentError("ToolInvalid", "%s（%s）的 _run 只認字面的 sync／cpu" % (where, name))
    return name


def _abspath(base, p):
    """info.json 裡的路徑：絕對的照字面用，相對的從 agent 資料夾起算。"""
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
