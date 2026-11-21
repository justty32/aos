#!/usr/bin/env python3
"""index_check — 查 aos 的夾 index（`_index.json`，沒有才看 `_index.md`）寫得對不對：形狀、列的東西在不在、`index` 欄指不指得到、子夾的 index 有沒有連過去。

  index_check.py [--root DIR] [--quiet] [PATH…]
    PATH    要查的夾（相對 --root；預設整個 root），底下每一夾的 index 都查。
    --root  樹的根（預設這份腳本所在的 repo）。
    --quiet 不印最後一行總數。
  夾的 index 是哪一份：有 `_index.json` 用它；沒有才用 `_index.md`（整份當字典式清單：一項 `鍵: 一句話`）。
  每個問題一行 `index_check: error: 代號 哪一份: 說明`，最後一行總數；有問題退 1，沒有退 0。只讀、不改任何檔。
  只查四種（使用者 11-21「index_check感覺是毒瘤，實作的時候拜託整個重寫」，規劃 proto8/thinking/2026-11/21/知識庫-骨架加md-規劃-1121/10-index_check.md）：
    IndexBad     那份 index 讀不出來、或最上層不是物件（`_index.md`＝沒有任何 `鍵: 值` 的項）；某一項不是「非空字串」（＝description）、
                 不是「帶非空 description（字串或字串陣列）的物件」、也不是 `{"$ref": …}`（description 寫成 `{"$ref": …}` 也算）；`index` 欄有寫但不是非空字串。
    EntryGone    鍵 `#` 左邊的檔或夾不在；鍵帶 `#/位置` 時那個位置讀不到（json 照 RFC 6901，`.md` 照 proto8/py/aos/mdpath.py）。
    LinkBad      `index` 欄不是合法路徑、指到的東西不在或讀不出來、或讀出來不符合 index 格式（json：一個物件；md：json 區塊是物件，或字典式清單）。
    LinkMissing  子夾自己有 `_index.json`，上一層那一項卻沒帶 `index`（`archive` 例外；`$ref` 的項不查，它的欄位在別處）。
  不查：夾裡在但沒列的東西（index 是視角，可以只列一部分）、`index` 指到的那份表裡每一項、`$ref` 指到的東西、節點內容裡的引用。
  不靜默跳過：PATH 在 root 外＝PathBad；照名字不走的夾（SKIP）裡有 index、`archive/` 底下任何一層的 index＝印 warning、總數行加「N skipped」；
  PATH 底下一份 index 都沒有＝印 warning。warning 不改退出碼。
  路徑算法跟 `$ref`、index_view 同一支 proto8/py/aos/refpath.py；md 一律經 proto8/py/aos/mdpath.py 讀。生成用 index_gen.py。純標準庫。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "proto8", "py"))
from aos import mdpath  # noqa: E402  md 照標題／清單／表格／json 區塊尋
from aos import refpath  # noqa: E402  路徑字串怎麼算：$ref 與 index 共用一支

PROG = "index_check"
NAMES = ("_index.json", "_index.md")    # 夾的 index：前面那份在就不看後面那份
SKIP = {".git", "__pycache__", "build", "install", "vcpkg_installed", "node_modules", ".cache"}
ARCHIVE = "archive"     # 封存夾：不維護內部連結，裡面的 index 不查、只計數
USAGE = "(usage: index_check.py [--root DIR] [--quiet] [PATH…])"


class Unreadable(Exception):
    """讀不出來（檔不在、不是 UTF-8、不是 json、巢太深、位置尋不到）；訊息是英文一句。"""


def warn(msg):
    print(f"{PROG}: warning: {msg}", file=sys.stderr)


def read_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise Unreadable(getattr(e, "strerror", None) or type(e).__name__) from None


def at(path, toks):
    """一個檔的一格（toks＝已還原的 token 串，[]＝整份）：json 照 RFC 6901、.md 照 mdpath。讀不到丟 Unreadable。"""
    text = read_text(path)
    if path.endswith(".md"):
        try:
            return mdpath.get(text, toks)
        except mdpath.Missing as e:
            raise Unreadable(e.reason) from None
    try:
        cur = json.loads(text)
    except (ValueError, RecursionError) as e:
        raise Unreadable("not JSON (%s)" % type(e).__name__) from None
    for tok in toks:
        if isinstance(cur, dict) and tok in cur:
            cur = cur[tok]
        elif isinstance(cur, list) and tok.isdigit() and str(int(tok)) == tok and int(tok) < len(cur):
            cur = cur[int(tok)]
        else:
            raise Unreadable("there is no %s" % tok)
    return cur


def md_table(text, toks):
    """md 的一格當 index 表：json 區塊是物件＝表；字典式清單（有 `鍵: 值` 的項）＝{鍵: 值}；都不是＝None（同 proto8/py/aos/index.py）。"""
    v = mdpath.get(text, toks)
    if isinstance(v, dict) or not isinstance(v, str):
        return v if isinstance(v, dict) else None
    base = list(toks) + (["_"] if mdpath._walk(text, list(toks))[0] == "scope" else [])
    out = {}
    for n in mdpath.ls(text, base):
        if not mdpath.INT.match(n) and n not in out:
            out[n] = mdpath.get(text, base + [n])
    return out or None


def index_at(path, toks):
    """一格讀成 index 表：json 要是物件；md 要是 json 區塊的物件或字典式清單。回 (表或 None, 不是表時的一句)；讀不到丟 Unreadable。"""
    if path.endswith(".md"):
        try:
            tab = md_table(read_text(path), toks)
        except mdpath.Missing as e:
            raise Unreadable(e.reason) from None
        return tab, "it is neither a ```json block holding an object nor a list of `key: value` items"
    v = at(path, toks)
    return (v, None) if isinstance(v, dict) else (None, "it is not a JSON object")


def text(v):
    """一段文字：字串，或字串陣列（一行一個元素，用換行接起來）；其他形狀＝None。同 proto8/py/aos/index.py 的 text()。"""
    if isinstance(v, str):
        return v
    if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
        return "\n".join(v)
    return None


def is_ref(v):
    return isinstance(v, dict) and "$ref" in v


def shape_ok(e):
    if isinstance(e, str):
        return bool(e.strip())
    if is_ref(e):
        return True
    return isinstance(e, dict) and (is_ref(e.get("description")) or bool((text(e.get("description")) or "").strip()))


def check_dir(root, d, name, problems):
    """一夾的 index（name＝_index.json 或 _index.md）；回列了幾項。"""
    base = os.path.join(root, d)
    where = name if d == "." else d + "/" + name
    file = os.path.join(base, name)
    try:
        table, why = index_at(file, [])
    except Unreadable as e:
        problems.append(("IndexBad", where, "cannot be read (%s)" % e))
        return 0
    if table is None:
        problems.append(("IndexBad", where, "has no `key: value` list items" if name.endswith(".md") else "is not a JSON object"))
        return 0
    for k, e in table.items():
        if not shape_ok(e):
            problems.append(("IndexBad", where, "entry %s is not a non-empty string, an object with a non-empty description, or {\"$ref\": ...}" % k))
        elif isinstance(e, dict) and not is_ref(e) and "index" in e and (not isinstance(e["index"], str) or not e["index"]):
            problems.append(("IndexBad", where, "entry %s: index is not a non-empty string" % k))
        f, hash_, _ = k.partition("#")
        target = os.path.join(base, f)
        if not os.path.lexists(target):
            problems.append(("EntryGone", where, "%s is listed but not there" % k))
        elif hash_:
            try:
                at(target, mdpath.split(k)[1])
            except (Unreadable, ValueError) as err:
                problems.append(("EntryGone", where, "%s is listed but that place cannot be read (%s)" % (k, err)))
        link = e.get("index") if isinstance(e, dict) and not is_ref(e) else None
        if isinstance(link, str) and link:
            bad = check_link(link, file, k)
            if bad:
                problems.append(("LinkBad", where, "%s: index %s %s" % (k, link, bad)))
        elif (not is_ref(e) and not hash_ and k != ARCHIVE and os.path.isfile(os.path.join(target, NAMES[0]))):
            problems.append(("LinkMissing", where, "%s has its own %s but the entry has no index" % (k, NAMES[0])))
    return len(table)


def check_link(link, file, key):
    """index 欄 → 問題的一句或 None。路徑同 $ref（寫在 _index 的 /KEY 那一項裡）；最後要讀得出 index 格式。"""
    try:
        path, toks = refpath.spot(link, file, [key.replace("~", "~0").replace("/", "~1")])
    except ValueError as e:
        return "is not a path (%s)" % e
    if not os.path.lexists(path):
        return "points to nothing"
    if os.path.isdir(path):
        return "points to a folder, not to an index"
    try:
        table, why = index_at(path, [t.replace("~1", "/").replace("~0", "~") for t in toks or []])
    except Unreadable as e:
        return "cannot be read (%s)" % e
    return None if table is not None else "does not hold an index (%s)" % why


def index_name(names):
    return next((n for n in NAMES if n in names), None)


def main(argv):
    root, quiet, paths = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), False, []
    it = iter(argv)
    for a in it:
        if a == "--quiet":
            quiet = True
        elif a == "--root":
            root = next(it, None)
            if root is None:
                print(f"{PROG}: error: ArgumentsBad --root needs a value {USAGE}", file=sys.stderr)
                return 1
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        elif a.startswith("-"):
            print(f"{PROG}: error: FlagUnknown {a} {USAGE}", file=sys.stderr)
            return 1
        else:
            paths.append(a)
    root = os.path.realpath(os.path.expanduser(root))
    problems, files, entries, skipped = [], 0, 0, []
    for p in paths or ["."]:
        top = os.path.realpath(os.path.join(root, p))
        if not os.path.isdir(top) or os.path.relpath(top, root).split(os.sep)[0] == "..":
            print(f"{PROG}: error: PathBad {p} is not a folder under the root {root} {USAGE}", file=sys.stderr)
            return 1
        before = files
        for cur, dirs, names in os.walk(top):
            for x in dirs:                              # 照名字不走的夾（build、node_modules…）裡有 index：說出來，不靜默跳過
                if x in SKIP and index_name(os.listdir(os.path.join(cur, x))):
                    skipped.append(os.path.relpath(os.path.join(cur, x), root))
                    warn(f"{skipped[-1]}/{index_name(os.listdir(os.path.join(cur, x)))} is not checked (folders named {x} are not walked)")
                elif x == ARCHIVE:                      # archive 底下每一層的 index 都數
                    for acur, adirs, anames in os.walk(os.path.join(cur, x)):
                        adirs[:] = sorted(a for a in adirs if a not in SKIP)
                        if index_name(anames):
                            skipped.append(os.path.relpath(acur, root))
                            warn(f"{skipped[-1]}/{index_name(anames)} is not checked (archive keeps no inner links)")
            dirs[:] = sorted(x for x in dirs if x not in SKIP and x != ARCHIVE)
            name = index_name(names)
            if name:
                files += 1
                entries += check_dir(root, os.path.relpath(cur, root), name, problems)
        if files == before:
            warn(f"no _index.json or _index.md under {p}, nothing was checked there")
    for code, where, msg in problems:
        print(f"{PROG}: error: {code} {where}: {msg}", file=sys.stderr)
    if not quiet:
        kinds = {}
        for code, _w, _m in problems:
            kinds[code] = kinds.get(code, 0) + 1
        print("%s: %d index files, %d entries, %d problems%s%s" % (
            PROG, files, entries, len(problems),
            "" if not problems else " (" + ", ".join("%s %d" % kv for kv in sorted(kinds.items())) + ")",
            "" if not skipped else "; %d skipped (not walked: %s)" % (len(skipped), ", ".join(skipped))))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
