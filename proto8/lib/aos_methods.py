"""方法表 lib：fsm 的表（`start`＋`states`，每格＝一個 aos-inst TARGET）、找一格、跑一格、取 stdout 最後一份。純標準庫。

照 NORMS N-36、N-37、N-41（基礎實作）。不含繼承：表一定明寫，不靠慣例檔名、沒有 extends、沒有搜尋路徑。

- `check_table(doc, ident)`：驗 `start`（字串）、`states`（非空物件，`start` 要在裡面）、`end`（選填，字串陣列，N-40）。
- `cell(states, name, ident)` → (inst 設定 dict, inst 的 id, 表上靜態 next 或 None)。格的寫法三種：
  字串＝aos-inst TARGET（檔、資料夾、可接 `#/位置`；照 aos-inst 的找法）、物件＝內嵌一張 inst、
  `{"target": 前兩種之一, "next": "<狀態名>"}`＝帶表上靜態 next（物件有 `target` 就算這種）。查不到那格＝`UnknownState`。
- `run_cell(inst, ident, args)`：把那張 inst 的 stdin 蓋成一份寫著 args 的暫存檔、stdout 蓋成暫存檔（N-12：stdin＝參數），
  在本行程用 `aos_inst.run()` 跑一次，回 (aos_inst 的結果 dict, 子程式 stdout 最後一份完整 JSON 或 None)。
  stderr、exit、cwd、timeout_ms 照那張 inst 自己寫的。inst 寫了 `stdin_inherit`／`stdout_inherit`＝Conflict（fsm 一定蓋這兩個）。
  aos_inst 自己出錯丟 `MethodsError`（代號照 aos_inst 的）。暫存檔跑完刪掉。
  結果 dict 多一格 `cell_error`＝格 stderr 裡最後一份 N-29 錯誤 `{"code", "msg"}`（沒有＝None）：沒寫 stderr 的格
  （本來接 /dev/null）改接暫存檔撿；格自己寫了 stderr 檔就讀那個檔；inherit／merge 的撿不到。（10-15 146 試跑後補）
- `last_json(text)`：JSON 串流的最後一份完整 JSON（半份不算，N-12）；沒有＝None。

錯誤一律 `MethodsError`（`CliError` 的子類，`code`／`msg`）。相依：aos_directives ← aos_cli ← aos_inst ← aos_methods ← aos_fsm。
"""
import json
import os
import shutil
import tempfile

import aos_cli
import aos_inst
from aos_cli import CliError
from aos_directives import target_id

__all__ = ["MethodsError", "cell", "check_table", "last_json", "run_cell"]


class MethodsError(CliError):
    """表或格不對、aos_inst 自己出錯。`code`＝錯誤代號，`msg`＝白話。"""


def check_table(doc, ident):
    """驗表的三個 key，回 (start, states, end)。不對丟 MethodsError("FieldType", ...)。"""
    start, states, end = doc.get("start"), doc.get("states"), doc.get("end", [])
    if not (isinstance(states, dict) and states):
        raise MethodsError("FieldType", "%s 的 states 要是非空物件（狀態名 → 格），不是 %r" % (ident, states))
    if not (isinstance(start, str) and start in states):
        raise MethodsError("FieldType", "%s 的 start 要是 states 裡的狀態名，不是 %r" % (ident, start))
    if not (isinstance(end, list) and all(isinstance(e, str) for e in end)):
        raise MethodsError("FieldType", "%s 的 end 要是狀態名的陣列，不是 %r" % (ident, end))
    return start, states, end


def cell(states, name, ident=None):
    """狀態名 → (inst 設定 dict, inst 的 id, 表上靜態 next 或 None)。查不到、寫法不對丟 MethodsError。
    ident＝fsm 設定的 id（內嵌的格拿它接 `#/states/<名>` 當 id；None＝沒有）。"""
    if name not in states:
        raise MethodsError("UnknownState", "表裡沒有狀態 %r" % (name,))
    v, nxt = states[name], None
    if isinstance(v, dict) and "target" in v:
        v, nxt = v["target"], v.get("next")
        if not (nxt is None or isinstance(nxt, str)):
            raise MethodsError("FieldType", "格 %s 的 next 要是狀態名，不是 %r" % (name, nxt))
    if isinstance(v, str):
        try:
            doc, inst_id = aos_cli.load_target(v, aos_inst._file)
        except CliError as e:
            raise MethodsError(e.code, "格 %s：%s" % (name, e.msg))
        return doc, inst_id, nxt
    if isinstance(v, dict):
        return v, (target_id(ident, ("states", name)) if ident else None), nxt
    raise MethodsError("FieldType", "格 %s 要是 aos-inst TARGET（字串）或一張 inst（物件），不是 %r" % (name, v))


def last_json(text):
    """JSON 串流的最後一份（壞尾丟掉＝半份不算）；沒有＝None。"""
    docs = aos_cli.read_stream(text)
    return docs[-1] if docs else None


def _stderr_error(doc, cwd):
    """格 stderr 裡最後一份 N-29 錯誤 {"code", "msg"}；沒有、讀不到＝None。stderr 是格自己寫的檔也照讀。"""
    path = doc.get("stderr")
    if not path:
        return None
    if not os.path.isabs(path) and isinstance(cwd, str):
        path = os.path.join(cwd, path)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            docs = aos_cli.read_stream(f.read())
    except (OSError, ValueError):
        return None
    for d in reversed(docs):
        e = d.get("error") if isinstance(d, dict) else None
        if isinstance(e, dict) and isinstance(e.get("code"), str):
            return {"code": e["code"], "msg": str(e.get("msg", ""))}
    return None


def run_cell(inst, ident, args):
    """跑一格：stdin＝args（寫成暫存檔）、stdout 接到暫存檔。回 (aos_inst 結果 dict, stdout 最後一份或 None)。"""
    tmp = tempfile.mkdtemp(prefix="aos-fsm-")
    try:
        stdin, stdout = os.path.join(tmp, "args.json"), os.path.join(tmp, "out.json")
        with open(stdin, "w", encoding="utf-8") as f:
            json.dump(args, f, ensure_ascii=False)
        doc = dict(inst, stdin=stdin, stdout=stdout, stdout_append=False, stdout_mkdir=False)
        doc.setdefault("id", ident)
        if not (doc.get("stderr") or doc.get("stderr_inherit") or doc.get("stderr_merge")):
            doc["stderr"] = os.path.join(tmp, "err.json")     # 沒寫 stderr 的格：本來接 /dev/null，改接暫存檔撿錯
        try:
            result = aos_inst.run(doc)
        except aos_inst.InstError as e:
            raise MethodsError(e.code, e.msg)
        try:
            with open(stdout, encoding="utf-8", errors="replace") as f:
                ret = last_json(f.read())
        except OSError:
            ret = None
        result["cell_error"] = _stderr_error(doc, inst.get("cwd"))
        return result, ret
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
