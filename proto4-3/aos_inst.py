#!/usr/bin/env python3
"""inst.json 的讀、驗、解指示詞——「格式」那一層，跟「怎麼跑」分開（跑在 aos_exec.py）。

格式是 posix v1（`proto5/spec/inst-posix.md`；源頭是 proto4 筆記第 11 節、凍結分支
`core/inst` 的 SPEC §C-3～§C-6）：一份 inst.json 是嚴格一個 JSON 物件、**七個**欄位、
只有 `argv` 必填，**不認得的頂層 key 一律忽略**（2026-09-21 起；以前是拒絕）。頂層另外
允許一個可選的 `_metainfo`：只講這份 inst 是哪一種格式、第幾版，不參與執行、沒寫就當
`{"_type":"posix","_version":1}`；它裡面 `_type`／`_version` 以外的 key 也忽略。

    argv     字串（或指示詞）陣列，必填；argv[0] 走疊加後 env 的 PATH
    stdin    檔案當標準輸入，沒寫＝/dev/null；選項 inherit＝繼承 aos-exec 的
    stdout   標準輸出寫到這個檔（建立並清空），沒寫＝/dev/null；選項 append／mkdir／inherit
    stderr   同上；多一個選項 merge＝跟 stdout 同一條（照 stdout 的設定走），沒寫＝/dev/null
    exit     跑完把結束碼寫進去，沒寫＝不寫；選項 append／mkdir
    cwd      工作目錄，沒寫＝xxx 本身；選項 mkdir
    envs     物件，疊在 aos-exec 的環境上只加不減；選項 clear＝從空環境開始只放 $val 的；
             整包也可以用 $ref 從別的檔拿

**選項物件**：一格本來要寫值的地方改寫 `{"$opt": "名字"}`、`{"$opt": "名字", "$val": 值}`
或 `{"$opt": ["名字1", "名字2"], "$val": 值}`。`$val` 就是「本來要直接寫在那一格的值」，
型別照那一格驗、**自己還能再是指示詞**；哪個位置認哪些名字、哪些要帶／不能帶 `$val`、
哪些互斥，都在 `aos_inst_resolve.OPTIONS` 與 `options()`（錯了＝`UnknownOption`／
`OptionConflict`）。選項物件只認 `$opt`、`$val`，其他 key 一律忽略——舊的 `$envs` 不再
認得，`{"$opt":"clear","$envs":{…}}` 會安靜地清成空環境。

**先解、再驗**：inst.json 裡**任何一個值的位置**都能改寫一個指示詞——頂層整份、每個
欄位、`argv` 整個陣列與它的每個元素、`envs` 整個物件與它的每個值、選項物件的 `$val`。
指示詞解出來的東西就當成本來寫在那個位置，**解出來又是指示詞就繼續解**（巢狀），最後
才照那個位置該有的型別驗（頂層要物件、argv 要非空字串陣列、路徑欄要字串、envs 要物件）。
型別不對就是 `NotAnObject`／`FieldTypeMismatch`／`EmptyArgv` 那些代號。

指示詞三種：`{"$env":"NAME"}`、`{"$ref":"file.json#/pointer"}`、
`{"$fmt":{"$val":"模板", 變數名: 值, …}}`（模板裡 `${name}` 只查那張本地變數表，變數值
可以再是指示詞；沒有 `${env:…}` 這種 namespace）。**一個 dict 只要有 `$` 開頭的 key 就當
指示詞物件看**，裡面其他不認得的 key 忽略；好幾個指示詞 key 一起出現只跑優先序最高的
（`$opt` > `$ref` > `$fmt` > `$env`）。所以環境變數名不能是 `$` 開頭的。

**循環**：`$ref` 沿著一條鏈記「檔案 realpath ＋ pointer」，任何深度都記；同一條鏈再遇到
同一個身分＝`ReferenceCycle`（頂層 `{"$ref":"自己"}` 也擋得到）。

相對路徑的中心是**解出來的 cwd**，只有頂層與 `cwd` 自己以 `xxx`（base）為中心，所以順序
是：先解頂層 → 解 `cwd` → 其餘欄位。

驗不過就丟 InstError；`str(e)` 是「代號: 白話」，aos-exec 原樣印一行到 stderr、退出碼
125（aos-exec 自己失敗，不是子程式的碼）。
"""
import json
import os

from aos_inst_resolve import OPTIONS, InstError, _envs, _resolve, _str, abspath, options

FIELDS = ("argv", "stdin", "stdout", "stderr", "exit", "cwd", "envs")
PATH_FIELDS = ("stdin", "stdout", "stderr", "exit")
def load(path, base):
    """讀 path 這份 inst.json，指示詞全解好，回一個欄位都填好的 dict。

    base ＝ `xxx`（資料夾本身，或那份 `.json` 所在的資料夾）：頂層與 `cwd` 用它當起點。
    `cwd` 解完之後，其他欄位與它們的 `$ref` 一律以**解出來的 cwd** 為中心。

    回傳的 dict（路徑都是絕對的，""＝沒寫；bool 都是那一格的選項有沒有開）：

        argv      list
        stdin     {"path", "inherit"}
        stdout    {"path", "append", "mkdir", "inherit"}
        stderr    {"path", "append", "mkdir", "inherit", "merge"}
        exit      {"path", "append", "mkdir"}
        cwd       絕對路徑；另有 cwd_mkdir（bool）
        envs      dict；另有 envs_clear（bool）
        metainfo  dict，沒寫 `_metainfo` 就是 {"_type":"posix","_version":1}
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
    obj = _resolve(obj, base, "inst.json", [])          # 頂層整份也能是指示詞
    if not isinstance(obj, dict):
        raise InstError("NotAnObject", "inst.json 必須是一個 JSON 物件，不是 %s"
                        % type(obj).__name__)

    # 七個欄位＋ _metainfo 以外的頂層 key 一律忽略（不拒絕，也不傳給子程式）。
    inst = {"argv": [],
            "stdin": {"path": "", "inherit": False},
            "stdout": {"path": "", "append": False, "mkdir": False, "inherit": False},
            "stderr": {"path": "", "append": False, "mkdir": False, "inherit": False,
                       "merge": False},
            "exit": {"path": "", "append": False, "mkdir": False},
            "cwd": "", "cwd_mkdir": False, "envs": {}, "envs_clear": False,
            "metainfo": _metainfo(obj.get("_metainfo"))}

    # cwd 先解：它是所有相對路徑的中心，自己的相對路徑則以 base（xxx）為中心。
    cwd_raw = ""
    if "cwd" in obj:
        cwd_raw, opts = _path(obj["cwd"], base, "cwd")
        inst["cwd_mkdir"] = "mkdir" in opts
    cwd = abspath(base, cwd_raw) if cwd_raw else base
    inst["cwd"] = cwd

    argv = _resolve(obj.get("argv"), cwd, "argv", [])
    if argv is None:
        raise InstError("EmptyArgv", "argv 必填")
    if not isinstance(argv, list):
        raise InstError("FieldTypeMismatch", "argv 要是陣列，不是 %s" % type(argv).__name__)
    inst["argv"] = [_str(_resolve(x, cwd, "argv[%d]" % i, []), "argv[%d]" % i)
                    for i, x in enumerate(argv)]

    _envs(_resolve(obj.get("envs", {}), cwd, "envs", []), cwd, inst)

    for name in PATH_FIELDS:
        if name not in obj:
            continue
        v, opts = _path(obj[name], cwd, name)
        for o in opts:
            inst[name][o] = True
        if v:
            inst[name]["path"] = abspath(cwd, v)

    if not inst["argv"] or inst["argv"][0] == "":
        raise InstError("EmptyArgv", "argv 解出來是空的，或 argv[0] 是空字串")
    return inst


def _metainfo(mi):
    """`_metainfo`：可選的頂層鍵，只講「這份 inst 是哪一種格式、第幾版」，不參與執行，
    不解指示詞（它的值原樣看，不丟進 _resolve），也不會傳給子程式。沒寫就當
    {"_type":"posix","_version":1}；`_type`／`_version` 以外的 key 忽略；
    proto5/spec/inst-posix.md 第 1 節。
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
    mi_type = mi["_type"]
    if not (isinstance(mi_type, str) and mi_type == "posix"):
        raise InstError("UnsupportedInstType",
                        "_metainfo 的 _type 只認得 \"posix\"，不是 %r" % (mi_type,))
    mi_version = mi["_version"]
    if not (isinstance(mi_version, int) and not isinstance(mi_version, bool)
            and mi_version == 1):
        raise InstError("UnsupportedInstVersion",
                        "_metainfo（posix）的 _version 只認得 1，不是 %r" % (mi_version,))
    return {"_type": "posix", "_version": 1}


def _path(raw, base, name):
    """一個路徑欄（stdin／stdout／stderr／exit／cwd）：解指示詞、拆選項物件、`$val` 再解
    一次、最後驗是字串。回 `(路徑字串, 選項名集合)`。

    帶路徑的選項（append／mkdir）`$val` 不能是空字串——空字串在這裡的意思是「沒寫」
    （＝/dev/null／不寫），跟「接在檔尾」「先建父目錄」兜不起來，算 `OptionConflict`。
    """
    v = _resolve(raw, base, name, [])
    opts, v, _ = options(v, name, OPTIONS[name])
    if not opts:
        return _str(v, name), opts
    if opts & {"inherit", "merge"}:         # 不能帶 $val 的：路徑就是「沒寫」
        return "", opts
    where = "%s 的 $val" % name
    v = _str(_resolve(v, base, where, []), where)
    if v == "":
        raise InstError("OptionConflict", "%s 的 %s 要帶一個路徑，不能是空字串"
                        % (name, "／".join(sorted(opts))))
    return v, opts
