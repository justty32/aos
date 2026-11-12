"""aos_index - index_view：透過 index（視角）看節點，一行一項「鍵 TAB description」；index 放哪只寫在 spot() 一處。

使用者 11-12（thinking 2026-11/12/index-tools）：「index工具那塊，主要做視角就好，修改這塊應該不用做，因為他就是json，直接用json工具就好」、
「path和index可以同時給，指定的那一份有的，會覆蓋掉天然那份。開工吧」。
只讀 index 寫的內容：不查被描述的節點在不在、不附型別大小、不往上找、不解析鍵（圖紙 01 代定 I1～I19、施工結果 02 代定）。
三種給法：只 path＝看節點天然位置那份；只 index＝只看指定的那份；兩個都給＝天然那份為底、疊上指定那份，同名的鍵整項以指定那份為準。
天然那份有兩處（11-12 metainfo，使用者「index_view也要認_metainfo。」，N-69 推薦讀法、M15）：_metainfo 裡的 index 為底、
疊上獨立的 _index；再給 index 就是三層，後面蓋前面，都是逐項整項覆蓋。只有獨立那份時輸出跟以前逐字一樣。
讀檔經 aos_json（aos-json get），錯照轉它最後一行（C-52 例外 ⑤）；`[no index]`、`[no entry]`、`[more]`、`[index link]` 退 0。
指到另一份 index 的路徑（11-12 晚，使用者「除了description之外，還可以放index，值必須是字串，必須是路徑，指向另一個_index或_index.json。」
「json object內的_index這個key……我希望能支援字串，同樣也是路徑」「不跟着往下走。路徑相對...以_index, _index.json的位置爲準。」）：
每項的 index 欄、檔內 _index 是字串，都只顯示路徑、不往下讀；相對路徑怎麼接只寫在 link() 一處（thinking 2026-11/12/index-link）。"""
import json
import os

import aos_json
import tool_io

NAME = "index_view"
VIEW_NOT_FACTS = "An index is a view, not a listing: use ls or json_ls to see what is really there."


def spot(t):
    """節點 → 天然那份 index 的兩個位置（裡面、外面；腦的寫法）。全系統只有這裡知道 _metainfo／_index 這些名字。"""
    if not t.ptr and os.path.isdir(t.real):             # 資料夾：DIR/_metainfo.json 的 index 鍵、DIR/_index.json 整份
        return os.path.join(t.file, "_metainfo.json") + "#/index", os.path.join(t.file, "_index.json")
    return t.shown(t.ptr + "/_metainfo/index"), t.shown(t.ptr + "/_index")   # 整份 json 檔：FILE#/_index；json 內的物件：FILE#/PTR/_index


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


SHAPE = "an index must be a JSON object {KEY: {\"description\": ...}}, or (as _index inside a JSON file) a path string to another index"


def link(where, value):
    """index 裡寫的路徑 → 腦的寫法（可直接給 index_view 的 index）；不是合法路徑＝None。
    相對路徑從寫著它的那份 index 所在的資料夾算（使用者 11-12 晚「以_index, _index.json的位置爲準」；檔內 _index 讀成該檔所在的資料夾）；
    絕對路徑照用；只接檔名那段，# 後的指標照字面。翻案只改這裡。"""
    if not isinstance(value, str):
        return None
    cut = value.find("#")
    file, ptr = (value, "") if cut < 0 else (value[:cut], value[cut:])
    if not file or (cut >= 0 and not ptr.startswith("#/")):
        return None                                     # 空字串、沒檔名、# 後不是 /（`x.json#` 也不收，同 json 工具）
    if not os.path.isabs(file):
        file = os.path.normpath(os.path.join(os.path.dirname(where.split("#", 1)[0]), file))
    return file + ptr


def table(t, shown):
    """明講的那一份：物件＝表；合法路徑字串＝一條連結（不往下讀）；其他＝IndexBad。"""
    v = read(t)
    return checked(v, shown)


def checked(v, where):
    if isinstance(v, dict) or (isinstance(v, str) and link(where, v) is not None):
        return v
    tool_io.die("IndexBad", "%s is %s; %s" % (where, "a string that is not a path" if isinstance(v, str) else aos_json.kind(v), SHAPE))


def whole(where):
    """整份檔的內容；檔不在＝None（沒有），讀不了照轉 aos-json 的錯。"""
    it = aos_json.Target(where)
    return read(it) if os.path.exists(it.real) else None


def dig(v, keys, where, text=False):
    """順著 keys 往下取；中途不是物件或沒有那個鍵＝None（這一處沒有）；取到的不是物件＝IndexBad（指明哪一處）。
    text：檔內的 _index 也可以是指到另一份 index 的路徑字串（11-12 晚）；資料夾的 _index.json 整份不收字串。"""
    for k in keys:
        if not isinstance(v, dict) or k not in v:
            return None
        v = v[k]
    if text:
        return checked(v, where)
    if not isinstance(v, dict):
        tool_io.die("IndexBad", "%s is %s; an index must be a JSON object {KEY: {\"description\": ...}}" % (where, aos_json.kind(v)))
    return v


def soft(meta, name):
    """_metainfo 裡的 index（使用者 11-12「_metainfo.json 壞掉時，index_view 對那個資料夾不該直接報錯。」）：
    回 (表或 None, 略過時的一句或 None)。_metainfo 不在或沒有 index＝(None, None)；不是物件、index 不是物件＝略過、不報錯。"""
    if meta is None:
        return None, None
    if not isinstance(meta, dict):
        return None, "%s is not an object, skipped" % name
    if "index" not in meta:
        return None, None
    if not isinstance(meta["index"], dict):
        return None, "%s index is not an object, skipped" % name
    return meta["index"], None


def meta_file(where):
    """資料夾的 _metainfo.json 整份；不在＝None，讀不了＝NO（交給 soft 前先換成略過的句子）。不經 aos-json，讀壞了不報錯。"""
    it = aos_json.Target(where)
    try:
        with open(it.real, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return NO


NO = object()


def natural(path):
    """天然那份：回 ([(位置, 表)…] 有的那幾層、裡面在前, 沒有時的句子, 上一層提示或 None, 略過的句子或 None)。節點本身不在或不是 JSON＝照轉 aos-json 的錯。
    沒有時的句子帶一句「上一層的 index 怎麼看這個節點」（只是提示，工具不自己往上找，I10）；只講獨立那份（11-12 M21）。
    裡面那份（_metainfo）壞了只略過、在標頭說一句；獨立那份壞了照舊報錯。"""
    t = aos_json.Target(path)
    inside, outside = spot(t)
    if t.ptr:
        up, item = t.shown(t.parent_ptr()), t.toks[-1]
    else:
        bare = t.file.rstrip("/") or t.file
        up, item = os.path.dirname(bare) or ".", os.path.basename(bare)
    about = 'What the index of %s says about it: {"path": "%s", "key": "%s"}' % (up, up, item)
    if not t.ptr and os.path.isdir(t.real):             # 資料夾：兩份都是檔（裡面那份再取 index 鍵）
        m = meta_file(inside.rsplit("#", 1)[0])
        mine, skipped = (None, "_metainfo.json could not be read, skipped") if m is NO else soft(m, "_metainfo.json")
        o = whole(outside)
        found = [(inside, mine), (outside, None if o is None else dig(o, [], outside))]
    else:
        node = read(aos_json.Target(t.shown()))
        if not isinstance(node, dict):
            if not t.ptr:
                item += "#"
            return [], ("%s is %s, it cannot hold _index. Entries about its items may sit in a parent's index (keys like %s/0): try index_view %s"
                        % (t.shown(), aos_json.kind(node), item, up)), None, None
        mine, skipped = soft(node.get("_metainfo"), "_metainfo")
        found = [(inside, mine), (outside, dig(node, ["_index"], outside, text=True))]
    layers = [(w, v) for w, v in found if v is not None]
    if not layers:
        return [], "%s does not exist" % outside, about, skipped
    return layers, None, None, skipped


def entries(n):
    return "%d entr%s" % (n, "y" if n == 1 else "ies")


def line(key, entry, where):
    """一項一行：鍵 TAB description，有 index 欄再接 TAB index: 路徑（只顯示、不往下讀）；index 欄壞了只在這一行標出來，其他項照常。"""
    desc = entry.get("description") if isinstance(entry, dict) else None
    out = key if not isinstance(desc, str) else "%s\t%s" % (key, desc.replace("\r", " ").replace("\n", " ").replace("\t", " "))
    if not isinstance(entry, dict) or "index" not in entry:
        return out                                      # 項目壞掉或沒有 description：只印鍵（C-48，I14）
    to = link(where, entry["index"])
    if to is None:
        to = "bad (%s; must be a path string to another index, e.g. sub/_index.json or a.json#/_index)" % (
            "not a path" if isinstance(entry["index"], str) else aos_json.kind(entry["index"]))
    return "%s%s\tindex: %s" % (out, "" if isinstance(desc, str) else "\t", to)


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
    layers, missing, about, skipped = [], None, None, None
    if "path" in args:
        layers, missing, about, skipped = natural(args["path"])
    if "index" in args:
        layers = layers + [(args["index"], table(aos_json.Target(args["index"]), args["index"]))]
    if not layers:
        print("[no index] %s. %s%s" % (missing, about + ". " if about else "", VIEW_NOT_FACTS))
        return
    links = [(w, link(w, v)) for w, v in layers if isinstance(v, str)]
    layers = [(w, v) for w, v in layers if isinstance(v, dict)]
    if not layers:                                      # 只有連結：印路徑、不往下讀（使用者「不跟着往下走」）
        print("\n".join('[index link] %s points to %s (not followed; to read it: {"index": "%s"})' % (w, to, to) for w, to in links))
        return
    rows = {}
    for w, v in layers:
        rows.update((k, (e, w)) for k, e in v.items())  # 同名的鍵整項以後面那層為準；前面那層的順序在前、只在後面那層的接在後面
    names = [w for w, _ in layers]
    head = names[0] if len(names) == 1 else "%s (on the same key %s wins)" % (
        " + ".join(names), names[-1] if len(names) == 2 else "the later one")
    head = "[index] %s, %s" % (head, entries(len(rows)))
    if missing and "index" in args:
        head += " (natural index: %s)" % missing
    for w, to in links:
        head += " (%s points to %s, not followed)" % (w, to)
    if skipped:
        head += " (%s)" % skipped                       # 壞掉的 _metainfo 只略過，標頭說一句（不帶絕對路徑）
    out = [head]
    if "key" in args:
        k = args["key"]
        out.append(line(k, *rows[k]) if k in rows else "[no entry] %s" % k)
    else:
        lines = [line(k, e, w) for k, (e, w) in rows.items()]
        out += aos_json.page(lines, len(lines), offset, cap)
    print("\n".join(out))
