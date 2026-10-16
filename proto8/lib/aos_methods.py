"""方法表 lib：fsm 的表（`start`＋`states`，每格＝一個 aos-inst TARGET）、找一格、跑一格、取 stdout 最後一份。純標準庫。

照 NORMS N-36、N-37、N-41（基礎實作；10-15 收工後瘦身版）。不含繼承：表一定明寫，不靠慣例檔名、沒有 extends、沒有搜尋路徑。

- `check_table(doc, ident)`：驗 `start`（字串）、`states`（非空物件，`start` 要在裡面）、`end`（選填，名字陣列，
  名字可以在表裡也可以不在，N-40）。
- `cell(states, name, ident, base=None)` → (inst 設定 dict, inst 的 id, 表上靜態 next 或 None)。格的寫法三種：
  字串＝aos-inst TARGET（檔、資料夾、可接 `#/位置`；照 aos-inst 的找法；相對路徑從 base 算＝fsm 設定檔所在的資料夾，
  base 是 None＝呼叫者的 cwd，N-36）、物件＝內嵌一張 inst、
  `{"val": 前兩種之一, "next": "<狀態名>"}`＝帶表上靜態 next（物件有 `val` 就算這種；原值固定叫 val，C-55）。查不到那格＝`StateUnknown`。
- `run_cell(inst, ident, args=None)`：stdout 蓋成暫存檔，在本行程用 `aos_inst.run()` 跑一次，回 (aos_inst 的結果 dict,
  子程式 stdout 最後一份完整 JSON 或 None)。args 是 None（fsm 跑格就是，N-37：fsm 不碰格的 stdin）＝stdin 照那張 inst
  自己寫的；給了 args（think 叫腦）＝stdin 蓋成一份寫著 args 的暫存檔（N-12：stdin＝參數）。
  stderr、exit、cwd、timeout_ms 照那張 inst 自己寫的——**格的 stderr 這裡不讀、不撿**（C-52 切乾淨：格的錯是格自己的，
  要留就在那張 inst 寫 `stderr` 檔；10-15 深夜使用者「拜託切乾淨」，原本撿成 `cell_error` 已拿掉）。
  inst 寫了 `stdout_inherit`（給了 args 時還有 `stdin_inherit`）＝Conflict。
  aos_inst 自己出錯丟 `MethodsError`（代號照 aos_inst 的）。暫存檔跑完刪掉。
  結果 dict 多一格 `cell_empty`＝格的 stdout 什麼都沒吐（只有空白也算；fsm 拿它分「沒輸出」與「吐了壞的」，N-38）。
- `last_json(text)`：JSON 串流的最後一份完整 JSON（半份不算，N-12）；沒有＝None。

錯誤一律 `MethodsError`（`CliError` 的子類，`code`／`msg`）。相依：aos_cli ← aos_inst ← aos_methods ← aos_fsm。
"""
import json
import os
import shutil
import tempfile

import aos_cli
import aos_inst
from aos_cli import CliError, target_id

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
        raise MethodsError("FieldType", "%s 的 end 要是名字（字串）的陣列，不是 %r" % (ident, end))
    return start, states, end


def cell(states, name, ident=None, base=None):
    """狀態名 → (inst 設定 dict, inst 的 id, 表上靜態 next 或 None)。查不到、寫法不對丟 MethodsError。
    ident＝fsm 設定的 id（內嵌的格拿它接 `#/states/<名>` 當 id；None＝沒有）。
    base＝字串格的相對路徑從哪算（fsm 設定檔所在的資料夾；None＝呼叫者的 cwd）。"""
    if name not in states:
        raise MethodsError("StateUnknown", "表裡沒有狀態 %r" % (name,))
    v, nxt = states[name], None
    if isinstance(v, dict) and "val" in v:                 # 展開形：原值在 val（C-55）；沒 val 的物件＝內嵌 inst
        v, nxt = v["val"], v.get("next")
        if not (nxt is None or isinstance(nxt, str)):
            raise MethodsError("FieldType", "格 %s 的 next 要是狀態名，不是 %r" % (name, nxt))
    if isinstance(v, str):
        if base and not os.path.isabs(v):
            v = os.path.join(base, v)
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


def run_cell(inst, ident, args=None):
    """跑一格：stdout 接到暫存檔；給了 args＝stdin 也蓋成寫著 args 的暫存檔；stderr 照那張 inst 自己的（不碰）。
    回 (aos_inst 結果 dict, stdout 最後一份或 None)。"""
    tmp = tempfile.mkdtemp(prefix="aos-fsm-")
    try:
        stdout = os.path.join(tmp, "out.json")
        doc = dict(inst, stdout=stdout, stdout_append=False, stdout_mkdir=False)
        if args is not None:
            doc["stdin"] = os.path.join(tmp, "args.json")
            with open(doc["stdin"], "w", encoding="utf-8") as f:
                json.dump(args, f, ensure_ascii=False)
        doc.setdefault("id", ident)
        try:
            result = aos_inst.run(doc)
        except aos_inst.InstError as e:
            raise MethodsError(e.code, e.msg)
        try:
            with open(stdout, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            text = ""
        result["cell_empty"] = not text.strip()       # stdout 什麼都沒吐（只有空白也算）
        return result, last_json(text)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
