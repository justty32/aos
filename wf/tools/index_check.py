#!/usr/bin/env python3
"""index_check — 查 aos 的 index（`_index.json`）跟實際的樹對不對得上：列了但不在、在但沒列、連結指不到、形狀不對。

  index_check.py [--root DIR] [--fs] [--view] [--quiet] [PATH…]
    PATH    要查的夾（相對 --root；預設整個 root），底下每一份 `_index.json` 都查；被 `index` 連到的檔內 `_index` 也查。
    --root  樹的根（預設這份腳本所在的 repo）。
    --fs    「在但沒列」照磁碟上有什麼算（給不在 git 裡的樹用，例如裝好的 knowledge）；預設照 `git ls-files`（root 不是 git 的樹時自動照磁碟算）。
    --view  不查「在但沒列」（index 是視角、本來就可以只列一部分；只想查列的東西與連結對不對時用）。
  每個問題一行 `index_check: error: 代號 哪一份: 說明`，最後一行總數；有問題退 1，沒有退 0。只讀、不改任何檔。
  不靜默跳過（11-13 假綠實測，proto8/thinking/2026-11/13/index-check-false-green.md）：PATH 在 root 外＝PathBad；某夾沒有任何檔在 git 裡＝印 warning、照磁碟算；
  照名字不走的夾（SKIP）裡有 `_index.json`、`archive/` 底下任何一層的 `_index.json`（封存不維護內部連結；上一層那一項也不必帶 `index`）＝印 warning、總數行加「N skipped」；PATH 底下一份 `_index.json` 都沒有＝印 warning。warning 不改退出碼。
  不查（範圍外）：節點內容裡的引用（md 連結、json 字串裡的路徑、`$ref`）、`index` 指到的那份不往下跟（檔內 `_index` 除外）。
  代號：IndexBad（整份或某項形狀不對：要 `{名: {"description": "…", "index": "路徑"}}`，description 非空字串，
        或字串陣列——一行一個元素、接起來不是空的；空陣列、含非字串元素都算形狀不對）、
        EntryGone（列了但不在）、EntryMissing（在但沒列）、
        LinkBad（`index` 指不到另一份 index：指到的要是 `_index.json` 整份（物件）、檔內 `_index` 鍵、或 `_metainfo` 的 index；巢太深讀不了的 json 也算讀不了）、
        LinkMissing（子夾自己有 `_index.json`，上一層那一項卻沒帶 `index`）。
  路徑算法照 proto8/lib/aos_index.py 的 link()，這裡只做資料夾的 `_index.json` 用得到的部分（相對所在夾、`檔#/指標`、`#/指標`＝本檔）。
  規格：proto8/thinking/2026-11/13/index-build.md。生成用 index_gen.py。純標準庫。
"""
import json
import os
import subprocess
import sys

PROG = "index_check"
NAME = "_index.json"
SKIP = {".git", "__pycache__", "build", "install", "vcpkg_installed", "node_modules", ".cache"}
ARCHIVE = "archive"     # 封存夾：不維護內部連結（wf/STRUCTURE「archive 規則」），裡面的 index 不查、只計數（使用者 11-13 15:18「都按照推薦」）
USAGE ="(usage: index_check.py [--root DIR] [--fs] [--view] [--quiet] [PATH…])"


class JsonTooDeep(ValueError):
    pass


def load(path):
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except RecursionError:                          # 巢得太深的 json：當成讀不了，不讓整支崩
            raise JsonTooDeep(path) from None


def warn(msg):
    print(f"{PROG}: warning: {msg}", file=sys.stderr)


def is_index_spot(lpath, lptr):
    """index 欄指到的地方是不是一份 index：`_index.json` 整份、檔內 `_index` 鍵、`_metainfo.json#/index`、`…/_metainfo/index`（docs/01）。"""
    if not lptr:
        return os.path.basename(lpath) == NAME
    return (lptr.endswith("/_index") or lptr.endswith("/_metainfo/index")
            or (os.path.basename(lpath) == "_metainfo.json" and lptr == "/index"))


def pointer(doc, ptr):
    """JSON Pointer（/a/b）→ (找到沒, 值)。"""
    cur = doc
    for tok in ptr.split("/")[1:] if ptr else []:
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict) and tok in cur:
            cur = cur[tok]
        elif isinstance(cur, list) and tok.isdigit() and int(tok) < len(cur):
            cur = cur[int(tok)]
        else:
            return False, None
    return True, cur


def children(root, d, fs, cache):
    """夾 d（相對 root）底下實際有的名字。"""
    if fs or cache.get("fs"):
        try:
            return {n for n in os.listdir(os.path.join(root, d)) if n not in SKIP and n != NAME}
        except OSError:
            return set()
    if "kids" not in cache:
        got = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True)
        if got.returncode:                              # 不是 git 的樹：照磁碟算
            print(f"{PROG}: warning: {root} is not in git, counting what is on disk (same as --fs)", file=sys.stderr)
            cache["fs"] = True
            return children(root, d, True, cache)
        out = got.stdout.decode()
        kids = {}
        for p in out.split("\0"):
            if not p or not os.path.lexists(os.path.join(root, p)):
                continue
            parts = p.split("/")
            for i in range(len(parts)):
                kids.setdefault("/".join(parts[:i]) or ".", set()).add(parts[i])
        cache["kids"] = kids
    if d not in cache["kids"]:                          # 這夾沒有任何檔在 git 裡（解開的快照、還沒 add 的夾）：照磁碟算並說出來，不靜默當成空的
        warn(f"{d} has no files in git, counting what is on disk (same as --fs)")
        return children(root, d, True, cache)
    here = set(cache["kids"][d])
    try:                                                # 還沒進 git 的 `_index.json` 所在的夾也算在（剛生成、還沒 commit）
        for n in os.listdir(os.path.join(root, d)):
            if os.path.isfile(os.path.join(root, d, n, NAME)):
                here.add(n)
    except OSError:
        pass
    here.discard(NAME)
    return here


def text(v):
    """一段文字：字串，或字串陣列（一行一個元素，用換行接起來）；其他形狀＝None。同 proto8/lib/aos_index.py 的 text()。"""
    if isinstance(v, str):
        return v
    if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
        return "\n".join(v)
    return None


def check_table(table, where, problems):
    """形狀：回 True＝是物件、可以往下查各項。"""
    if not isinstance(table, dict):
        problems.append(("IndexBad", where, "is not a JSON object"))
        return False
    for k, e in table.items():
        if not isinstance(e, dict):
            problems.append(("IndexBad", where, "entry %s is not an object {\"description\": ...}" % k))
        elif not (text(e.get("description")) or "").strip():
            problems.append(("IndexBad", where, "entry %s has no description" % k))
        elif "index" in e and (not isinstance(e["index"], str) or not e["index"]):
            problems.append(("IndexBad", where, "entry %s: index is not a path string" % k))
    return True


def check_dir(root, d, fs, view, cache, problems, seen_inner):
    where = NAME if d == "." else d + "/" + NAME
    base = os.path.join(root, d)
    try:
        table = load(os.path.join(base, NAME))
    except (OSError, ValueError) as e:
        problems.append(("IndexBad", where, "cannot be read as JSON (%s)" % type(e).__name__))
        return 0
    if not check_table(table, where, problems):
        return 0
    have = children(root, d, fs, cache)
    for k, e in table.items():
        f, _, ptr = k.partition("#")
        target = os.path.join(base, f)
        if not os.path.lexists(target):
            problems.append(("EntryGone", where, "%s is listed but not there" % k))
            continue
        if ptr:
            try:
                ok, _v = pointer(load(target), ptr)
            except (OSError, ValueError):
                ok = False
            if not ok:
                problems.append(("EntryGone", where, "%s is listed but that place is not in the file" % k))
        if not isinstance(e, dict):
            continue
        link = e.get("index")
        if isinstance(link, str) and link:
            lf, _, lptr = link.partition("#")
            lpath = os.path.join(base, NAME) if not lf else os.path.normpath(os.path.join(base, lf))
            if "#" in link and not lptr.startswith("/"):
                problems.append(("LinkBad", where, "%s: index %s is not a path (after # comes /)" % (k, link)))
            elif not os.path.isfile(lpath):
                problems.append(("LinkBad", where, "%s: index %s points to nothing" % (k, link)))
            else:
                try:
                    ok, v = pointer(load(lpath), lptr)
                except (OSError, ValueError):
                    ok, v = False, None
                if not ok or not is_index_spot(lpath, lptr) or not isinstance(v, dict if not lptr else (dict, str)):
                    problems.append(("LinkBad", where, "%s: index %s does not hold an index "
                                     "(an index is a %s table, a _index key, or a _metainfo index)" % (k, link, NAME)))
                elif lptr and isinstance(v, dict) and (lpath, lptr) not in seen_inner:
                    seen_inner.add((lpath, lptr))       # 檔內的 _index：它列的鍵要在裝著它的那個物件裡
                    inner_where = os.path.relpath(lpath, root) + "#" + lptr
                    if check_table(v, inner_where, problems):
                        if os.path.basename(lpath) == "_metainfo.json" and lptr == "/index":   # 資料夾的 _metainfo index：列的是那個夾
                            gone = [ik for ik in v if not os.path.lexists(os.path.join(os.path.dirname(lpath), ik.partition("#")[0]))]
                        else:                           # FILE#/P/_index、FILE#/P/_metainfo/index：列的是物件 P
                            up = lptr.rsplit("/", 2)[0] if lptr.endswith("/_metainfo/index") else lptr.rsplit("/", 1)[0]
                            _ok, holder = pointer(load(lpath), up)
                            gone = [ik for ik in v if not isinstance(holder, dict) or ik not in holder]
                        for ik in gone:
                            problems.append(("EntryGone", inner_where, "%s is listed but not in that object" % ik))
        elif os.path.isfile(os.path.join(target, NAME)) and "#" not in k and k != ARCHIVE:   # archive 裡的 index 不查，上一層不必連過去
            problems.append(("LinkMissing", where, "%s has its own %s but the entry has no index" % (k, NAME)))
    if not view:
        listed = {k.partition("#")[0].split("/")[0] for k in table}
        for n in sorted(have - listed):
            problems.append(("EntryMissing", where, "%s is there but not listed" % n))
    return len(table)


def main(argv):
    root, fs, view, quiet, paths = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), False, False, False, []
    it = iter(argv)
    for a in it:
        if a == "--fs":
            fs = True
        elif a == "--view":
            view = True
        elif a == "--quiet":
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
    problems, cache, seen_inner, files, entries, skipped = [], {}, set(), 0, 0, []
    for p in paths or ["."]:
        top = os.path.realpath(os.path.join(root, p))
        if not os.path.isdir(top) or os.path.relpath(top, root).split(os.sep)[0] == "..":
            print(f"{PROG}: error: PathBad {p} is not a folder under the root {root} {USAGE}", file=sys.stderr)
            return 1
        before = files
        for cur, dirs, names in os.walk(top):
            for x in dirs:                              # 照名字不走的夾（build、node_modules…）裡有 index：說出來，不靜默跳過
                if x in SKIP and os.path.isfile(os.path.join(cur, x, NAME)):
                    skipped.append(os.path.relpath(os.path.join(cur, x), root))
                    warn(f"{skipped[-1]}/{NAME} is not checked (folders named {x} are not walked)")
                elif x == ARCHIVE:                      # archive 底下每一層的 index 都數
                    for acur, adirs, anames in os.walk(os.path.join(cur, x)):
                        adirs[:] = sorted(a for a in adirs if a not in SKIP)
                        if NAME in anames:
                            skipped.append(os.path.relpath(acur, root))
                            warn(f"{skipped[-1]}/{NAME} is not checked (archive keeps no inner links)")
            dirs[:] = sorted(x for x in dirs if x not in SKIP and x != ARCHIVE)
            if NAME in names:
                files += 1
                entries += check_dir(root, os.path.relpath(cur, root), fs, view, cache, problems, seen_inner)
        if files == before:
            warn(f"no {NAME} under {p}, nothing was checked there")
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
