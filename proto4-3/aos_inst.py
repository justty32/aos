#!/usr/bin/env python3
"""inst.json 的讀、驗、解指示詞——「格式」那一層，跟「怎麼跑」分開（跑在 aos_exec.py）。

格式是 proto4 筆記第 11 節那套（凍結分支 `core/inst` 的 SPEC §C-3～§C-6 改過來的）：
一份 inst.json 是嚴格一個 JSON 物件、**七個**欄位、只有 `argv` 必填、**未知的 key
一律拒絕**（不是忽略）。

    argv     字串（或指示詞）陣列，必填；argv[0] 走疊加後 env 的 PATH
    stdin    檔案當標準輸入，沒寫＝/dev/null
    stdout   標準輸出寫到這個檔（建立並清空），沒寫＝/dev/null
    stderr   同上；或 {"$opt":"merge"}＝跟 stdout 同一條，沒寫＝/dev/null
    exit     跑完把結束碼寫進去，沒寫＝不寫
    cwd      工作目錄，沒寫＝xxx 本身
    envs     物件，疊在 aos-exec 的環境上只加不減；或 {"$opt":"clear","$envs":{…}}＝
             從空環境開始只放 $envs 的；整包也可以用 $ref 從別的檔拿

**先解、再驗**：inst.json 裡**任何一個值的位置**都能改寫一個指示詞——頂層整份、每個
欄位、`argv` 整個陣列與它的每個元素、`envs` 整個物件與它的每個值、`$envs`。指示詞解
出來的東西就當成本來寫在那個位置，**解出來又是指示詞就繼續解**（巢狀），最後才照那個
位置該有的型別驗（頂層要物件、argv 要非空字串陣列、路徑欄要字串、envs 要物件）。型別
不對就是 `NotAnObject`／`FieldTypeMismatch`／`EmptyArgv` 那些代號。

指示詞三種：`{"$env":"NAME"}`、`{"$ref":"file.json#/pointer"}`、`{"$fmt":"模板"}`，
外加兩個位置專用的 `$opt`：`stderr` 的 `merge`、`envs` 的 `clear`。**一個 dict 只要有
`$` 開頭的 key 就當指示詞看**，所以環境變數名不能是 `$` 開頭的。`$fmt` 的模板寫法沿用
repo 既有的那套（`wf/workflows/common/data-files-fmt.md`），只有 `env:` 一個 namespace。

**循環**：`$ref` 沿著一條鏈記「檔案 realpath ＋ pointer」，任何深度都記；同一條鏈再遇到
同一個身分＝`ReferenceCycle`（頂層 `{"$ref":"自己"}` 也擋得到）。

相對路徑的中心是**解出來的 cwd**，只有頂層與 `cwd` 自己以 `xxx`（base）為中心，所以順序
是：先解頂層 → 解 `cwd` → 其餘欄位。

驗不過就丟 InstError；`str(e)` 是「代號: 白話」，aos-exec 原樣印一行到 stderr、退出碼
125（aos-exec 自己失敗，不是子程式的碼）。
"""
import json
import os

from aos_inst_resolve import InstError, _envs, _opt, _resolve, _str, abspath

FIELDS = ("argv", "stdin", "stdout", "stderr", "exit", "cwd", "envs")
PATH_FIELDS = ("stdin", "stdout", "stderr", "exit")
def load(path, base):
    """讀 path 這份 inst.json，指示詞全解好，回一個欄位都填好的 dict。

    base ＝ `xxx`（資料夾本身，或那份 `.json` 所在的資料夾）：頂層與 `cwd` 用它當起點。
    `cwd` 解完之後，其他欄位與它們的 `$ref` 一律以**解出來的 cwd** 為中心。

    回傳的 dict：`argv`（list）、`stdin`／`stdout`／`stderr`／`exit`（絕對路徑，
    ""＝沒寫）、`cwd`（絕對路徑）、`envs`（dict）、`envs_clear`（bool）、
    `stderr_merge`（bool）。
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
    for k in obj:
        if k not in FIELDS:
            raise InstError("UnknownKey", "不認得的欄位 %r，只有這七個：%s"
                            % (k, "、".join(FIELDS)))

    inst = {"argv": [], "stdin": "", "stdout": "", "stderr": "", "exit": "",
            "cwd": "", "envs": {}, "envs_clear": False, "stderr_merge": False}

    # cwd 先解：它是所有相對路徑的中心，自己的相對路徑則以 base（xxx）為中心。
    cwd_raw = _str(_resolve(obj["cwd"], base, "cwd", []), "cwd") if "cwd" in obj else ""
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
        v = _resolve(obj[name], cwd, name, [])
        if name == "stderr" and isinstance(v, dict) and "$opt" in v:
            _opt(v, name, "merge")              # {"$opt":"merge"}＝跟 stdout 同一條
            inst["stderr_merge"] = True
            continue
        v = _str(v, name)
        if v:
            inst[name] = abspath(cwd, v)

    if not inst["argv"] or inst["argv"][0] == "":
        raise InstError("EmptyArgv", "argv 解出來是空的，或 argv[0] 是空字串")
    return inst
