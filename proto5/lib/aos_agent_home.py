"""agent 家的共用內容讀驗層：只讀、不寫、不執行工具，也不讀 state.json。

依 agent.md §1～§3、§5 驗人格、記憶、工具與錯誤代號；依 aos-llm-call.md §3
只解 info.json 的六格。resolve_field 保留 directives.md §3.2 的原文件與位置，
被指到的內容檔不解指示詞，供 aos-llm-call 與 aos-agent 共用。
"""
import json
import os
from pathlib import Path

from aos_directives import Context, DirectiveError, Document, is_directive, resolve_located


class AgentError(Exception):
    """讀驗失敗；code 是代號、msg 是白話。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code, self.msg = code, msg


def check_metainfo(value):
    """驗 agent.md §3 的身分記號（bool 不是版本整數）。"""
    if not isinstance(value, dict) or any(k not in value for k in ("_type", "_version")):
        raise AgentError("MetainfoInvalid", "_metainfo 要是物件，且必填 _type 與 _version")
    if value["_type"] != "llm_agent":
        raise AgentError("NotAnAgent", "_metainfo._type 只認 llm_agent")
    if type(value["_version"]) is not int or value["_version"] != 1:
        raise AgentError("UnsupportedVersion", "_metainfo._version 只認整數 1")


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, UnicodeError) as e:
        raise AgentError("JsonSyntax", "%s 不是合法 JSON：%s" % (path, e)) from e
    except OSError as e:
        raise AgentError("ReadFailed", "讀不到 %s：%s" % (path, e)) from e


def read_info_doc(agent_dir):
    """讀原始 info.json；頂層不接受指示詞物件。"""
    path = Path(agent_dir) / "info.json"
    try:
        value = _read_json(path)
    except AgentError as e:
        if isinstance(e.__cause__, FileNotFoundError):
            raise AgentError("NotAnAgent", "%s 沒有 info.json" % agent_dir) from e
        raise
    if not isinstance(value, dict):
        raise AgentError("NotAnObject", "info.json 頂層必須是物件")
    if is_directive(value):
        raise AgentError("FieldTypeMismatch", "info.json 頂層必須是字面物件")
    return Document(path, value)


class _ContentContext(Context):
    """在每個實際求值位置拒絕選項，含解析器內部走到的 $fmt 變數。

    只檢查正在走的原文件位置，不掃未使用欄位或被指示詞優先序忽略的鍵。
    child／_visited 保留 Context 的文件與循環鏈語意。
    """

    def child(self, doc=None, base_dir=None, env=None):
        return _ContentContext(self.doc if doc is None else doc,
                               self.base_dir if base_dir is None else base_dir,
                               self.env if env is None else env, self._chain)

    def _visited(self, ident):
        value = self.doc.root
        for key in ident[1]:
            value = value[int(key)] if isinstance(value, list) else value[key]
        if isinstance(value, dict) and "$opt" in value:
            raise AgentError("UnknownOption", "這個位置沒有任何 $opt 選項")
        return _ContentContext(self.doc, self.base_dir, self.env, self._chain + (ident,))


def _deep(value, ctx, position):
    loc = resolve_located(value, ctx, position)
    value = loc.value
    if isinstance(value, dict):
        if "$opt" in value:
            raise AgentError("UnknownOption", "這個位置沒有任何 $opt 選項")
        return {k: _deep(v, loc.ctx, loc.position + [k]) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep(v, loc.ctx, loc.position + [str(i)]) for i, v in enumerate(value)]
    return value


def resolve_field(doc, ctx, position):
    """從完整文件取一格再遞迴解析，保留引用後的文件、位置與循環鏈。"""
    value = doc.root
    for key in position:
        value = value[int(key)] if isinstance(value, list) else value[key]
    try:
        return _deep(value, _ContentContext(doc, base_dir=ctx.base_dir, env=ctx.env), list(position))
    except DirectiveError as e:
        raise AgentError(e.code, e.msg) from e


def _single_file(path):
    if Path(path).is_dir():
        raise AgentError("FieldTypeMismatch", "%s 必須是單一檔案，不能是資料夾" % path)


def _optional_json(path, default):
    _single_file(path)
    try:
        return _read_json(path)
    except AgentError as e:
        if isinstance(e.__cause__, FileNotFoundError):
            return default
        raise


def read_system(path):
    """人格原樣讀；不存在＝空字串。"""
    value = _optional_json(path, {"content": ""})
    if not isinstance(value, dict) or not isinstance(value.get("content"), str):
        raise AgentError("MessageInvalid", "人格檔必須是含字串 content 的物件")
    return value["content"]


def read_history(path):
    """記憶原樣讀；不存在＝空陣列，驗證不改寫任何訊息。"""
    value = _optional_json(path, [])
    if not isinstance(value, list):
        raise AgentError("NotAnArray", "記憶檔必須是陣列")
    for message in value:
        check_message(message)
    return value


def _nonempty(value):
    return isinstance(value, str) and bool(value)


def check_message(m, *, from_model=False):
    """agent.md §3.2：驗 role、content 與每個工具呼叫，不解指示詞。"""
    def require(ok, msg):
        if not ok:
            raise AgentError("MessageInvalid", msg)

    require(isinstance(m, dict), "message 必須是物件")
    role = m.get("role")
    require(role in ("user", "tool", "assistant"), "role 只認 user／tool／assistant")
    require(not from_model or role == "assistant", "模型回覆的 role 必須是 assistant")
    calls = m.get("tool_calls", [])
    require(isinstance(calls, list), "tool_calls 必須是陣列")
    seen = set()
    for c in calls:
        require(isinstance(c, dict), "tool_calls 每項必須是物件")
        require(_nonempty(c.get("id")), "tool_calls.id 必須是非空字串")
        require(c["id"] not in seen, "同一則 message 的 tool_calls.id 不能重複")
        seen.add(c["id"])
        require(c.get("type") == "function", "tool_calls.type 必須是 function")
        fn = c.get("function")
        require(isinstance(fn, dict), "tool_calls.function 必須是物件")
        require(_nonempty(fn.get("name")), "tool_calls.function.name 必須是非空字串")
        require(isinstance(fn.get("arguments"), str), "tool_calls.function.arguments 必須是字串")
    content = m.get("content")
    require("content" in m and (isinstance(content, str) or
            (role == "assistant" and content is None and bool(calls))),
            "content 必須是字串；assistant 的 null 必須搭配非空 tool_calls")
    if role == "tool":
        require(_nonempty(m.get("tool_call_id")), "tool.tool_call_id 必須是非空字串")


def strip_private(tool):
    """去掉所有底線開頭頂層鍵的淺拷貝。"""
    return {k: v for k, v in tool.items() if not k.startswith("_")}


def read_tools(paths):
    """合併已展開的工具檔路徑；內容錯一律 ToolInvalid，不解 _meta。"""
    merged, seen = [], {}
    for path in paths:
        path = os.path.abspath(path)
        values = _read_json(path)
        if not isinstance(values, list):
            raise AgentError("ToolInvalid", "%s 的工具頂層必須是陣列" % path)
        for i, t in enumerate(values):
            where = "%s 第 %d 個元素：" % (path, i)
            if not isinstance(t, dict) or t.get("type") != "function":
                raise AgentError("ToolInvalid", where + "工具必須是 type 為 function 的物件")
            fn, meta = t.get("function"), t.get("_meta")
            if not isinstance(fn, dict) or not _nonempty(fn.get("name")):
                raise AgentError("ToolInvalid", where + "工具 function 必須有非空字串 name")
            for key, typ in (("description", str), ("parameters", dict)):
                if key in fn and not isinstance(fn[key], typ):
                    raise AgentError("ToolInvalid", where + "工具 function.%s 型別不對" % key)
            if not isinstance(meta, dict) or any(k in meta for k in ("stdin", "stdout")):
                raise AgentError("ToolInvalid", where + "工具 _meta 必須是物件，且不能寫 stdin／stdout")
            timeout = t.get("_timeout_ms", 60000)
            if type(timeout) is not int or timeout < 0:
                raise AgentError("ToolInvalid", where + "工具 _timeout_ms 必須是非負整數（bool 不算）")
            if fn["name"] in seen:
                raise AgentError("ToolInvalid", "合併後工具同名：%s（%s、%s 第 %d 個）" %
                                 (fn["name"], seen[fn["name"]], path, i))
            seen[fn["name"]] = "%s 第 %d 個" % (path, i)
            merged.append(t)
    return merged


def _expand_tools(paths):
    out = []
    for path in paths:
        try:
            if Path(path).is_dir():
                out.extend(str(p) for p in sorted(Path(path).iterdir(), key=lambda p: p.name)
                           if p.name.endswith(".json") and not p.name.endswith(".done") and p.is_file())
            else:
                out.append(path)
        except OSError as e:
            raise AgentError("ReadFailed", "讀不到工具資料夾 %s：%s" % (path, e)) from e
    return out


def load_llm_view(agent_dir, env=None):
    """只解驗模型輸入六格；回絕對路徑、原始內容與送模型用的工具表。"""
    base = os.path.abspath(agent_dir)
    doc = read_info_doc(base)
    obj, ctx = doc.root, Context(doc, base_dir=base, env=env)
    check_metainfo(resolve_field(doc, ctx, ["_metainfo"]) if "_metainfo" in obj else None)
    out = {"dir": base}
    for key, default, reader in (("system", "prompts/system.json", read_system),
                                 ("history", "prompts/history.json", read_history)):
        value = resolve_field(doc, ctx, [key]) if key in obj else default
        if not isinstance(value, str):
            raise AgentError("FieldTypeMismatch", "%s 必須是路徑字串" % key)
        path = os.path.abspath(os.path.join(base, value))
        out[key + "_path"], out[key] = path, reader(path)
    paths = resolve_field(doc, ctx, ["tools"]) if "tools" in obj else []
    if not isinstance(paths, list) or any(not isinstance(p, str) for p in paths):
        raise AgentError("FieldTypeMismatch", "tools 必須是路徑字串陣列")
    out["tool_paths"] = _expand_tools([os.path.abspath(os.path.join(base, p)) for p in paths])
    out["tools_raw"] = read_tools(out["tool_paths"])
    out["tools"] = [strip_private(t) for t in out["tools_raw"]]
    if "llm" not in obj:
        raise AgentError("LlmInvalid", "info.json 缺了 llm")
    llm = obj["llm"]
    if not isinstance(llm, dict) or is_directive(llm):
        raise AgentError("FieldTypeMismatch", "llm 必須是字面物件")
    if "model" not in llm:
        raise AgentError("LlmInvalid", "llm 缺了 model")
    out["model"] = resolve_field(doc, ctx, ["llm", "model"])
    out["params"] = resolve_field(doc, ctx, ["llm", "params"]) if "params" in llm else {}
    if not _nonempty(out["model"]):
        raise AgentError("FieldTypeMismatch", "llm.model 必須是非空字串")
    if not isinstance(out["params"], dict):
        raise AgentError("FieldTypeMismatch", "llm.params 必須是物件")
    return out
