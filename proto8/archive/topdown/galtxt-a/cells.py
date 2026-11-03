#!/usr/bin/env python3
# cells - data/ 裡「格」的解析器（round4-data.md § 2.1、§ 3；根下伴隨檔、標準庫；brief、compose、judge、pick 共用）
# 格 id＝JSON key 路徑（C-72）：第一段＝data/ 下的資料夾，第二段＝檔名（不帶 .json），其餘＝檔內的 key 路徑，例 cast.yuzu.tic.03 ↔ data/cast/yuzu.json#/tic/03。
#   找不到 data/<1>/<2> 時退一層：第一段就是 data/ 根下的檔（styles.ng_marks ↔ data/styles.json#/ng_marks、lint_switches.contrast_order）。
#   別名：tpl.＝data/templates.json、tpld.＝data/templates.distilled.json（distill 唯一寫的那份）。
# 檔長成資料夾（data/cast/yuzu/，一個頂層 key 一個 <key>.json、檔內 _metainfo key 變成 _metainfo 檔）時，id 不變——
#   解析時先試資料夾、再補 .json（同 aos-exec N-61 找名字的順序；$ref "cast/yuzu.json" 也照這個順序找）。
# 一格＝有 text 的物件（可選 marker：lint 比對的字面，沒有＝同 text）；_metainfo、source 兩個 key 不是格、解析時跳過。
# 給步驟 5（grad.json 的 changed_cells）的介面：touched(舊, 新, 前綴) 列出兩版之間值不同的格 id；命令列 `cells.py diff 舊.json 新.json 前綴` 同一件事。
# 命令列：cells.py get <id>｜cells.py ls [前綴]｜cells.py diff <舊> <新> <前綴>；錯（CellMissing、RefBad、ArgumentsBad）stderr 一行「cells: 代號 原因」、退 1。
import json, os, re, sys

DATA = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")
ALIAS = {"tpl": "templates", "tpld": "templates.distilled"}
SKIP = ("_metainfo", "source")


class CellMissing(KeyError):
    pass


class RefBad(ValueError):
    pass


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_entity(base, file_first=False):
    """base＝不帶 .json 的路徑：資料夾在＝把每個 <key>.json（和 _metainfo）合成一個物件；否則讀 base.json；都沒有＝None。
    file_first：data/ 根下的檔（cast.json 跟放實體的 cast/ 資料夾並存）先試 .json"""
    if file_first and os.path.isfile(base + ".json"):
        return _read(base + ".json")
    if os.path.isdir(base):
        out = {}
        for n in sorted(os.listdir(base)):
            p = os.path.join(base, n)
            if n == "_metainfo":
                out[n] = _read(p)
            elif n.endswith(".json") and not n.startswith("."):
                out[n[:-5]] = _read(p)
        return out
    if os.path.isfile(base + ".json"):
        return _read(base + ".json")
    return None


def load_ref(obj, data=DATA):
    """{"$ref": "cast/yuzu.json"}（相對 data/）解一層；不是 $ref 就原樣回；指不到＝RefBad"""
    if not (isinstance(obj, dict) and isinstance(obj.get("$ref"), str)):
        return obj
    rel = obj["$ref"]
    base = os.path.join(data, rel[:-5] if rel.endswith(".json") else rel)
    got = load_entity(base)
    if got is None:
        raise RefBad("$ref 指不到：%s" % rel)
    return got


def _entities(segs, data):
    """id 的段 → [(實體路徑（不帶 .json）, 檔內 key 路徑, 先試檔)]，照找的順序"""
    first = ALIAS.get(segs[0], segs[0])
    out = []
    if len(segs) >= 2 and segs[0] not in ALIAS:
        out.append((os.path.join(data, first, segs[1]), segs[2:], False))
    out.append((os.path.join(data, first), segs[1:], True))
    return out


def _walk(obj, keys):
    for k in keys:
        if isinstance(obj, dict) and k in obj and k not in SKIP:
            obj = obj[k]
        else:
            raise KeyError(k)
    return obj


def resolve(cid, data=DATA):
    """格 id → (檔路徑, JSON pointer, 值)；檔路徑是最細那個檔（長成資料夾時是 <key>.json）。沒有＝CellMissing"""
    segs = cid.split(".")
    for base, keys, file_first in _entities(segs, data):
        ent = load_entity(base, file_first)
        if ent is None:
            continue
        try:
            val = _walk(ent, keys)
        except KeyError:
            raise CellMissing(cid)
        if not (file_first and os.path.isfile(base + ".json")) and os.path.isdir(base) and keys:
            return os.path.join(base, keys[0] + ".json"), "/" + "/".join(keys[1:]), val
        return base + ".json", "/" + "/".join(keys), val
    raise CellMissing(cid)


def is_cell(v):
    return isinstance(v, dict) and isinstance(v.get("text"), str)


def text(v):
    return v["text"] if is_cell(v) else v


def marker(v):
    return v.get("marker", v["text"]) if is_cell(v) else v


def kids(obj):
    """一張表的格（序號 key 照字串排）——跳過 _metainfo、source、退役的"""
    if not isinstance(obj, dict):
        return []
    return [(k, obj[k]) for k in sorted(obj) if k not in SKIP and not (isinstance(obj[k], dict) and obj[k].get("retired"))]


FLAG = re.compile(r"^(.*)\[(\w+)\]$")


def expand(pattern, data=DATA):
    """'cast.yuzu.gesture.*[reveal]' → 那張表裡 reveal 為真的格 id（照 id 排）；沒有 * 就是單一 id（要解得到）；解不到＝CellMissing"""
    m = FLAG.match(pattern)
    pat, flag = (m.group(1), m.group(2)) if m else (pattern, None)
    if not pat.endswith(".*"):
        resolve(pat, data)
        return [pat]
    head = pat[:-2]
    _, _, table = resolve(head, data)
    return ["%s.%s" % (head, k) for k, v in kids(table) if flag is None or (isinstance(v, dict) and v.get(flag))]


def must_groups(must):
    """評測題 guard.must：舊式 [[詞…]…] 原樣；拆格後 {"01": {"any": [詞…]}…} → 照 id 序的 [[詞…]…]"""
    if isinstance(must, dict):
        return [v["any"] for _, v in kids(must)]
    return must or []


def count_cells(obj):
    """檔內的格數（有 text 的物件；不往格裡面再數）"""
    if is_cell(obj):
        return 1
    if isinstance(obj, dict):
        return sum(count_cells(v) for k, v in obj.items() if k not in SKIP)
    return 0


def ids(obj, prefix):
    """{id: 格}——obj 裡每一格（prefix＝obj 自己的 id）"""
    out = {}
    if is_cell(obj):
        out[prefix] = obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k not in SKIP:
                out.update(ids(v, "%s.%s" % (prefix, k)))
    return out


def touched(old, new, prefix):
    """步驟 5 用（grad.json 的 changed_cells）：兩版同一個實體之間新增、刪掉、值變了的格 id（照 id 排）"""
    a, b = ids(old or {}, prefix), ids(new or {}, prefix)
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def _main(argv):
    def bad(code, why):
        print("cells: %s %s" % (code, why), file=sys.stderr)
        return 1
    try:
        if len(argv) == 2 and argv[0] == "get":
            path, ptr, v = resolve(argv[1])
            print(json.dumps({"id": argv[1], "path": os.path.relpath(path, os.path.dirname(DATA)), "pointer": ptr, "value": v},
                             ensure_ascii=False))
        elif len(argv) in (1, 2) and argv[0] == "ls":
            pre = argv[1] if len(argv) == 2 else ""
            found = {}
            for d, subs, files in os.walk(DATA):
                subs.sort()
                for n in sorted(files):
                    if not n.endswith(".json"):
                        continue
                    rel = os.path.relpath(os.path.join(d, n[:-5]), DATA).split(os.sep)
                    pid = ".".join(rel)
                    for a, real in ALIAS.items():
                        if pid == real:
                            pid = a
                    found.update(ids(_read(os.path.join(d, n)), pid))
            for k in sorted(found):
                if k.startswith(pre):
                    print(k)
        elif len(argv) == 4 and argv[0] == "diff":
            for k in touched(_read(argv[1]), _read(argv[2]), argv[3]):
                print(k)
        else:
            return bad("ArgumentsBad", "用法：cells.py get <id>｜ls [前綴]｜diff <舊> <新> <前綴>")
    except CellMissing as e:
        return bad("CellMissing", e)
    except (RefBad, OSError, ValueError) as e:
        return bad("RefBad", e)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
