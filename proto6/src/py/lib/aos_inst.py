"""inst.json（posix 第 1 版）的讀、驗、解——「格式」這一層，跟「怎麼跑」分開（跑在 aos_exec.py）。

規範是 ../spec/inst-posix/，指示詞（`$env`／`$fmt`／`$ref`／`$opt`）的機制全部交給
aos_directives.py（規範 ../spec/directives/），這個檔只做 inst 這個宿主自己的事：

- 讀檔、驗 `_metainfo`（沒寫＝posix v1；它的值不解指示詞）。
- 七個欄位照這個順序解：頂層整份 → `cwd` → `argv` → `envs` → `stdin`／`stdout`／`stderr`／`exit`。
  `$ref` 的中心路徑：頂層與 `cwd` 以 base（inst 的家）為中心，其餘以解出來的 `cwd` 為中心。
- 每個位置認得哪些 `$opt` 選項（`OPTIONS`），不吃選項的位置（`argv` 的元素、`envs` 的值、
  選項物件的 `$val` 裡面）放了 `$opt` 就是 `UnknownOption`。
- 解完才驗型別（頂層要物件、`argv` 要非空字串陣列、路徑欄要字串、`envs` 要物件）。

驗不過就丟 `InstError(code, msg)`，`str(e)` 是「代號: 白話」；指示詞機制丟的 `DirectiveError`
在 `load()` 裡包成同形狀的 `InstError`（代號照 directives.md 第 6 節），呼叫者只要接一種。

`load(path, base)` 回一個執行者能直接用的 dict（路徑都是絕對的，""＝沒寫）：

    argv       list
    stdin      {"path", "inherit"}
    stdout     {"path", "append", "mkdir", "inherit"}
    stderr     {"path", "append", "mkdir", "inherit", "merge"}
    exit       {"path", "append", "mkdir"}
    cwd        絕對路徑；另有 cwd_mkdir（bool）
    envs       dict；另有 envs_clear（bool）
    metainfo   {"_type": "posix", "_version": 1}
"""
import json
import os

from aos_directives import Context, DirectiveError, Document, parse_options, resolve, resolve_located

__all__ = ["InstError", "OPTIONS", "FIELDS", "PATH_FIELDS", "load", "load_obj"]

FIELDS = ("argv", "stdin", "stdout", "stderr", "exit", "cwd", "envs")
PATH_FIELDS = ("stdin", "stdout", "stderr", "exit")

# 各位置認得的選項（inst-posix.md 3.3），用 aos_directives.option_names 的表格式寫：
# val＝required（一定要帶 $val）／forbidden（不能帶）／optional，alone＝不能跟別的選項一起。
_REQ = {"val": "required"}
_ALONE = {"val": "forbidden", "alone": True}
OPTIONS = {
    "stdin": {"inherit": _ALONE},
    "stdout": {"append": _REQ, "mkdir": _REQ, "inherit": _ALONE},
    "stderr": {"append": _REQ, "mkdir": _REQ, "inherit": _ALONE, "merge": _ALONE},
    "exit": {"append": _REQ, "mkdir": _REQ},
    "cwd": {"mkdir": _REQ},
    "envs": {"clear": {"val": "optional"}},
}
_NO_OPTIONS = {}            # 不吃選項的位置：放了 $opt 就是 UnknownOption


class InstError(Exception):
    """這份 inst.json 被拒。不是程式炸了，是檔案有問題。

    `code` 是規範的錯誤代號（`EmptyArgv`、`ReferenceCycle`…），`msg` 是白話；
    `str(e)` 是「代號: 白話」。
    """

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg


def load(path, base, env=None):
    """讀 `path` 這份 inst.json，指示詞全解好、驗完，回一個欄位都填好的 dict（形狀見模組說明）。

    `base`＝這份 inst 的家（給資料夾就是那個資料夾，給 `.json` 就是它所在的資料夾）：頂層與
    `cwd` 以它為中心；`cwd` 解完之後其他欄位與它們的 `$ref` 一律以解出來的 `cwd` 為中心。
    `env` 是 `$env` 查的表（沒給＝`os.environ`）。

    讀不到＝`ReadFailed`、不是 JSON＝`JsonSyntax`；其他代號見 inst-posix.md 第 5 節與
    directives.md 第 6 節。
    """
    base = os.path.abspath(base)
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise InstError("ReadFailed", "讀不到 %s：%s" % (path, e))
    try:
        obj = json.loads(raw)
    except ValueError as e:
        raise InstError("JsonSyntax", "JSON 語法錯：%s" % e)
    try:
        return _load(obj, Context(Document(path, obj), base_dir=base, env=env), base)
    except DirectiveError as e:
        raise InstError(e.code, e.msg)


def load_obj(obj, base, env=None):
    """讀驗記憶體裡的一份 inst（例如工具的 `_meta`），回傳形狀與 `load()` 相同。

    `base` 是 inst 的家；`$ref:""` 指這份純記憶體文件，其他解析規則共用 `_load`。
    """
    base = os.path.abspath(base)
    try:
        return _load(obj, Context(Document(None, obj), base_dir=base, env=env), base)
    except DirectiveError as e:
        raise InstError(e.code, e.msg)


def _load(obj, ctx, base):
    """`obj` 是讀進來的原始 JSON，`ctx` 的文件是這份 inst.json 自己、中心路徑是 base。"""
    # 頂層整份也能是指示詞。經過 $ref 之後「目前文件」就換成被引用的那份檔，位置也跟著換，
    # 所以之後每個欄位都從 top 的文件／位置往下接。循環鏈是「每一格各自一條」（directives.md
    # 第 5 節）：每個欄位都用 _fresh() 從空鏈開始，只有走進容器（argv 的元素、envs 的值）時
    # 才把 resolve_located 回來的 ctx（鏈照帶）傳下去。
    top = resolve_located(obj, ctx, [])
    obj = _no_options(top.value, top.position)
    if not isinstance(obj, dict):
        raise InstError("NotAnObject", "inst.json 必須是一個 JSON 物件，不是 %s"
                        % type(obj).__name__)
    inst = {"argv": [],
            "stdin": {"path": "", "inherit": False},
            "stdout": {"path": "", "append": False, "mkdir": False, "inherit": False},
            "stderr": {"path": "", "append": False, "mkdir": False, "inherit": False,
                       "merge": False},
            "exit": {"path": "", "append": False, "mkdir": False},
            "cwd": "", "cwd_mkdir": False, "envs": {}, "envs_clear": False,
            "metainfo": _metainfo(obj.get("_metainfo"))}

    # cwd 最先解：它是其他相對路徑的中心，自己的相對路徑（與 $ref）以 base 為中心。
    cwd_raw = ""
    if "cwd" in obj:
        cwd_raw, names = _path(obj["cwd"], _fresh(top.ctx, base), top.position + ["cwd"], "cwd")
        inst["cwd_mkdir"] = "mkdir" in names
    cwd = _abspath(base, cwd_raw) if cwd_raw else base
    inst["cwd"] = cwd
    ctx = _fresh(top.ctx, cwd)                  # 之後的 $ref 都以解出來的 cwd 為中心

    inst["argv"] = _argv(obj.get("argv"), ctx, top.position + ["argv"])
    inst["envs"], inst["envs_clear"] = _envs(obj.get("envs", {}), ctx, top.position + ["envs"])

    for name in PATH_FIELDS:
        if name not in obj:
            continue
        v, names = _path(obj[name], ctx, top.position + [name], name)
        for n in names:
            inst[name][n] = True
        if v:
            inst[name]["path"] = _abspath(cwd, v)
    return inst


def _fresh(ctx, base_dir):
    """同一份文件、同一個環境，換中心路徑、循環鏈清空——每個欄位從這裡開始。"""
    return Context(ctx.doc, base_dir=base_dir, env=ctx.env)


def _metainfo(mi):
    """`_metainfo`：只講「這份 inst 是哪一種格式、第幾版」，不參與執行、不解指示詞。

    沒寫＝`{"_type": "posix", "_version": 1}`；要是物件、一定有 `_type` 與 `_version`（其他 key
    忽略）；`_type` 只認 `"posix"`、`_version` 只認整數 `1`（`true`／`false` 不算）。
    """
    if mi is None:
        return {"_type": "posix", "_version": 1}
    if not isinstance(mi, dict):
        raise InstError("MetainfoInvalid", "_metainfo 必須是一個 JSON 物件，不是 %s"
                        % type(mi).__name__)
    missing = [k for k in ("_type", "_version") if k not in mi]
    if missing:
        raise InstError("MetainfoInvalid",
                        "_metainfo 缺了 %s（_type 跟 _version 都必填）" % "、".join(missing))
    t, v = mi["_type"], mi["_version"]
    if not (isinstance(t, str) and t == "posix"):
        raise InstError("UnsupportedInstType", "_metainfo 的 _type 只認得 \"posix\"，不是 %r" % (t,))
    if not (isinstance(v, int) and not isinstance(v, bool) and v == 1):
        raise InstError("UnsupportedInstVersion",
                        "_metainfo（posix）的 _version 只認得 1，不是 %r" % (v,))
    return {"_type": "posix", "_version": 1}


def _no_options(value, position):
    """不吃選項的位置：解出來是選項物件（有 `$opt`）就是 `UnknownOption`；不是就原樣回。"""
    return parse_options(value, position, _NO_OPTIONS)[1]


def _str(value, position, what):
    """要字串的位置：解完不是字串＝`FieldTypeMismatch`（選項物件先被 `_no_options` 擋掉）。"""
    value = _no_options(value, position)
    if not isinstance(value, str):
        raise InstError("FieldTypeMismatch", "%s 要是字串，不是 %s" % (what, type(value).__name__))
    return value


def _argv(raw, ctx, position):
    """`argv`：整個陣列可以是指示詞，每個元素也可以；解完要是非空字串陣列、`argv[0]` 不能空。"""
    if raw is None:
        raise InstError("EmptyArgv", "argv 必填")
    loc = resolve_located(raw, ctx, position)
    argv = _no_options(loc.value, loc.position)
    if not isinstance(argv, list):
        raise InstError("FieldTypeMismatch", "argv 要是陣列，不是 %s" % type(argv).__name__)
    out = [_str(resolve(x, loc.ctx, loc.position + [str(i)]), loc.position + [str(i)], "argv[%d]" % i)
           for i, x in enumerate(argv)]
    if not out or out[0] == "":
        raise InstError("EmptyArgv", "argv 解出來是空的，或 argv[0] 是空字串")
    return out


def _envs(raw, ctx, position):
    """`envs`：普通的「變數名→值」物件，或清空型式 `{"$opt": "clear", "$val": {…}}`。回 `(dict, clear)`。

    整包（與 `$val`）都可以是指示詞解出來的；key 是純字串、不解指示詞，空或含 `=`＝`EnvKeyInvalid`
    （`$` 開頭的 key 走不到這裡：整包早被當成指示詞看了）；每個值解完要是字串。
    """
    loc = resolve_located(raw, ctx, position)
    names, val, has_val = parse_options(loc.value, loc.position, OPTIONS["envs"])
    clear = "clear" in names
    what = "envs"
    if names:
        what = "envs 的 $val"
        loc = resolve_located(val if has_val else {}, loc.ctx, loc.position + ["$val"])
        val = _no_options(loc.value, loc.position)
    if not isinstance(val, dict):
        raise InstError("FieldTypeMismatch", "%s 要是物件，不是 %s" % (what, type(val).__name__))
    out = {}
    for k, v in val.items():
        if k == "" or "=" in k:
            raise InstError("EnvKeyInvalid", "envs 的 key 不能是空字串或含 '='：%r" % (k,))
        out[k] = _str(resolve(v, loc.ctx, loc.position + [k]), loc.position + [k], "envs[%r]" % k)
    return out, clear


def _path(raw, ctx, position, name):
    """一個路徑欄（stdin／stdout／stderr／exit／cwd）：解指示詞、拆選項物件（照 `OPTIONS[name]`
    驗）、`$val` 再解一次、最後驗是字串。回 `(路徑字串, 選項名集合)`。

    `inherit`／`merge` 不帶 `$val`，路徑就是「沒寫」；`append`／`mkdir` 的 `$val` 不能是空字串
    （空字串在路徑欄的意思是「沒寫」＝/dev/null，跟「接在檔尾」「先建父目錄」兜不起來）＝`OptionConflict`。
    """
    loc = resolve_located(raw, ctx, position)
    names, val, has_val = parse_options(loc.value, loc.position, OPTIONS[name])
    if names and not has_val:                   # inherit／merge：不能帶 $val 的那幾個
        return "", names
    what = name
    if names:
        what = "%s 的 $val" % name
        position = loc.position + ["$val"]
        val = resolve(val, loc.ctx, position)
    val = _str(val, position, what)
    if names and val == "":
        raise InstError("OptionConflict", "%s 的 %s 要帶一個路徑，不能是空字串"
                        % (name, "／".join(sorted(names))))
    return val, names


def _abspath(base, p):
    """inst.json 裡的路徑：絕對的照字面用，相對的從 base 起算。"""
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
