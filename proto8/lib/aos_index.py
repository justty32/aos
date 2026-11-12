"""aos_index - index_view：透過 index（視角）看節點，一行一項「鍵 TAB description」；index 放哪只寫在 spot() 一處。

使用者 11-12（thinking 2026-11/12/index-tools）：「index工具那塊，主要做視角就好，修改這塊應該不用做，因為他就是json，直接用json工具就好」、
「path和index可以同時給，指定的那一份有的，會覆蓋掉天然那份。開工吧」。
只讀 index 寫的內容：不查被描述的節點在不在、不附型別大小、不往上找、不解析鍵（圖紙 01 代定 I1～I19、施工結果 02 代定）。
三種給法：只 path＝看節點天然位置那份；只 index＝只看指定的那份；兩個都給＝天然那份為底、疊上指定那份，同名的鍵整項以指定那份為準。
讀檔經 aos_json（aos-json get），錯照轉它最後一行（C-52 例外 ⑤）；`[no index]`、`[no entry]`、`[more]` 退 0。"""
import os

import aos_json
import tool_io

NAME = "index_view"
VIEW_NOT_FACTS = "An index is a view, not a listing: use ls or json_ls to see what is really there."


def spot(t):
    """節點 → 它天然位置那份 index 的路徑（腦的寫法）。全系統只有這裡知道 _index.json／_index；搬進 _metainfo 時只改這裡。"""
    if not t.ptr and os.path.isdir(t.real):
        return os.path.join(t.file, "_index.json")      # 資料夾：DIR/_index.json 整份
    return t.shown(t.ptr + "/_index")                   # 整份 json 檔：FILE#/_index；json 內的物件：FILE#/PTR/_index


def read(t):
    """讀一格；錯照轉 aos-json，但拿掉 json 寫入工具才用得上的「先建檔」提示（這支只看）。"""
    aos_json.MULTI = True
    try:
        return aos_json.read(t)
    except aos_json.Failed as e:
        aos_json.MULTI = False
        tool_io.die(e.code, e.reason.split(" (create it first")[0])
    finally:
        aos_json.MULTI = False


def table(t, shown):
    v = read(t)
    if not isinstance(v, dict):
        tool_io.die("IndexBad", "%s is %s; an index must be a JSON object {KEY: {\"description\": ...}}" % (shown, aos_json.kind(v)))
    return v


def natural(path):
    """天然那份：回 (位置, 表或 None, 沒有時的句子)。節點本身不在或不是 JSON＝照轉 aos-json 的錯。"""
    t = aos_json.Target(path)
    where = spot(t)
    it = aos_json.Target(where)
    if not it.ptr:                                      # 資料夾那份是整份檔
        if not os.path.exists(it.real):
            return where, None, "%s does not exist" % where
        return where, table(it, where), None
    node = read(aos_json.Target(it.shown(it.parent_ptr())))
    name = it.toks[-1]
    if not isinstance(node, dict):
        if t.ptr:
            up, item = t.shown(t.parent_ptr()), t.toks[-1]
        else:
            up, item = os.path.dirname(t.file) or ".", os.path.basename(t.file) + "#"
        return where, None, ("%s is %s, it cannot hold %s. Entries about its items may sit in a parent's index (keys like %s/0): try index_view %s"
                             % (t.shown(), aos_json.kind(node), name, item, up))
    if name not in node:
        return where, None, "%s does not exist" % where
    v = node[name]
    if not isinstance(v, dict):
        tool_io.die("IndexBad", "%s is %s; an index must be a JSON object {KEY: {\"description\": ...}}" % (where, aos_json.kind(v)))
    return where, v, None


def entries(n):
    return "%d entr%s" % (n, "y" if n == 1 else "ies")


def line(key, entry):
    desc = entry.get("description") if isinstance(entry, dict) else None
    if not isinstance(desc, str):
        return key                                      # 項目壞掉或沒有 description：只印鍵（C-48，I14）
    return "%s\t%s" % (key, desc.replace("\r", " ").replace("\n", " ").replace("\t", " "))


def main():
    aos_json.start(NAME)
    args = tool_io.arguments()
    given = [k for k in ("path", "index") if k in args]
    if not given:
        tool_io.die("ArgumentsBad", "give path (a node), index (one index table), or both")
    for k in given + (["key"] if "key" in args else []):
        if not isinstance(args[k], str) or not args[k]:
            tool_io.die("ArgumentsBad", "%s must be a non-empty string" % k)
    offset = args.get("offset", 0)
    if type(offset) is not int or offset < 0:
        tool_io.die("ArgumentsBad", "offset must be a non-negative integer")
    cap = aos_json.limit(args, "limit", "AOS_JSON_MAX_ITEMS", aos_json.MAX_ITEMS)
    base, missing = None, None
    if "path" in args:
        where, base, missing = natural(args["path"])
    if "index" in args:
        mine = table(aos_json.Target(args["index"]), args["index"])
        merged = dict(base or {})
        merged.update(mine)                             # 同名的鍵整項以指定那份為準；天然那份的順序在前、只在指定那份的接在後面
        if "path" not in args:
            head = "[index] %s, %s" % (args["index"], entries(len(merged)))
        elif base is None:
            head = "[index] %s, %s (natural index: %s)" % (args["index"], entries(len(merged)), missing)
        else:
            head = "[index] %s + %s (on the same key %s wins), %s" % (where, args["index"], args["index"], entries(len(merged)))
        rows = merged
    else:
        if base is None:
            print("[no index] %s. %s" % (missing, VIEW_NOT_FACTS))
            return
        head, rows = "[index] %s, %s" % (where, entries(len(base))), base
    out = [head]
    if "key" in args:
        k = args["key"]
        out.append(line(k, rows[k]) if k in rows else "[no entry] %s" % k)
    else:
        lines = [line(k, v) for k, v in rows.items()]
        out += aos_json.page(lines, len(lines), offset, cap)
    print("\n".join(out))
