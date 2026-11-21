#!/usr/bin/env python3
"""kb_md — 把 knowledge 的長文章頁換成同名 `.md`（convert）、照對照表改寫舊路徑（rewrite）、逐篇比對換完讀不讀得到（verify）；可重跑。

  kb_md.py convert SRC DST [--map FILE] [--keep PATH]… [--force-md PATH]…
    SRC 是一個 knowledge 夾（底下有 aos/、wf/…），整份抄到 DST（不存在的新夾）再換：一頁（`_index.json` 以外的 .json）裡的文字
    都是有 `#` 標題的文章（文字＝字串或字串陣列，文章＝第一行是標題），就換成同名 .md、移掉那份 .json。頁可以是整份一篇；或物件，
    值全是文章、或指到別份檔的 {"$ref": …}，外加最多一個沒標題的 `_description`（放在 md 最上面當開頭一段）；至少一篇文章。其餘整頁原樣留 json。
    md＝（開頭那段＋空行）＋各篇照鍵的順序、篇與篇之間一個空行、每篇結尾恰好一個換行；整份一篇＝原樣。不加任何標記。
    同一頁兩篇標題一樣、或標題叫 `_`＝那頁留 json、印 warning。`_index.json` 的鍵跟著改名。對照表 {"舊路徑": "新路徑"}（從 knowledge 根算）
    預設寫到 DST/../kb_md_map.json。--keep／--force-md 蓋過判準（PATH 從 knowledge 根算；--force-md 把沒標題的文字當普通段落收進去）。
  kb_md.py rewrite MAP PATH… [--dry-run]
    把檔或夾（遞迴）裡出現的舊路徑照表換成新路徑：只換完整的一條（左右不是路徑字元、長的優先）；`#/鍵` 表裡沒有的換檔名、印 warning；
    新路徑有空白而原處不在反引號裡的照換、印 warning。json 檔只換字串值（照原縮排寫回）；沒換到的檔不重寫。印每個檔換了幾處。
  kb_md.py verify OLD NEW MAP
    OLD 每一頁的每一篇文章照表到 NEW 用 mdpath 讀出來逐字比（舊文字先套同一張表的路徑替換），分「一樣／只差結尾一個換行／不一樣／尋不到」四類；
    留 json 的頁要沒變（除了換掉的路徑）；NEW 裡所有 aos/…、wf/… 的 md 路徑（同 proto8/py/tests/test_knowledge_paths.py 的找法）都要讀得到。
    不一樣、尋不到、留 json 的頁變了、路徑讀不到，任一非空就退 1。
  規劃：proto8/thinking/2026-11/21/知識庫-骨架加md-規劃-1121/04、06。純標準庫＋proto8/py/aos 的 mdpath。
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "proto8", "py"))
from aos import mdpath  # noqa: E402  md 照標題尋

PROG = "kb_md"
USAGE = "(usage: kb_md.py convert SRC DST [--map FILE] [--keep PATH]... [--force-md PATH]... | rewrite MAP PATH... [--dry-run] | verify OLD NEW MAP)"
PATHCH = r"A-Za-z0-9_/.\-"
TICKED = re.compile(r"`((?:aos|wf)/[^`\s#]+\.(?:json|md))(#/[^`]*)?`")
BARE = re.compile(r"(?<![\w/.-])((?:aos|wf)/[A-Za-z0-9_/.-]+\.(?:json|md))")


def fail(code, msg):
    print(f"{PROG}: error: {code} {msg} {USAGE}", file=sys.stderr)
    return 1


def warn(msg):
    print(f"{PROG}: warning: {msg}", file=sys.stderr)


def esc(k):
    return k.replace("~", "~0").replace("/", "~1")


def as_text(v):
    """一段文字：字串照用、字串陣列用換行接起來；其他＝None。"""
    if isinstance(v, str):
        return v
    if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
        return "\n".join(v)
    return None


def title(t):
    """文章的標題（第一行是 # 標題）；不是文章＝None。"""
    m = mdpath.HEAD.match(t.split("\n", 1)[0])
    return mdpath._title(m.group(2)) or None if m else None


def one_nl(t):
    return t.rstrip("\n") + "\n"


def pages(root):
    """knowledge 夾裡每一頁（`_index.json` 以外的 .json）的相對路徑，排好序。"""
    out = []
    for cur, dirs, names in os.walk(root):
        dirs.sort()
        out += [os.path.relpath(os.path.join(cur, n), root).replace(os.sep, "/") for n in sorted(names)
                if n.endswith(".json") and n != "_index.json"]
    return out


def plan(rel, doc, force):
    """一頁 → ("md", md 文字, {舊路徑: 新路徑}) 或 ("json", 原因)。"""
    new = rel[:-5] + ".md"
    whole = as_text(doc)
    if whole is not None:
        return ("md", whole, {rel: new}) if title(whole) else ("json", "the whole page is text without a heading")
    if not isinstance(doc, dict):
        return "json", "the page is %s" % ("an array record" if isinstance(doc, list) else "a %s" % type(doc).__name__)
    lead, parts, links = None, [], {}
    for k, v in doc.items():
        t = as_text(v)
        if isinstance(v, dict) and set(v) == {"$ref"} and isinstance(v["$ref"], str) and "#" not in v["$ref"]:
            links[k] = v["$ref"]
        elif k == "_index":
            return "json", "it has _index"
        elif t is None:
            return "json", "%s is %s" % (k, "an object" if isinstance(v, dict) else "an array" if isinstance(v, list) else "a number or other value")
        elif title(t):
            parts.append((k, t, title(t)))
        elif k == "_description" and lead is None:
            lead = t
        elif force:
            parts.append((k, t, None))                  # --force-md：沒標題的文字照鍵的順序當普通段落
        else:
            return "json", "%s is text without a heading" % k
    if not any(n for _k, _t, n in parts):
        return "json", "no article with a heading"
    names = [n for _k, _t, n in parts if n]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup or "_" in names:
        warn("%s stays json: %s" % (rel, "two articles have the same heading %s" % ", ".join(dup) if dup else "an article is headed _"))
        return "json", "same heading twice" if dup else "a heading named _"
    pieces = ([one_nl(lead)] if lead is not None else []) + [one_nl(t) for _k, t, _n in parts]
    m = {rel: new}
    if lead is not None:
        m[rel + "#/_description"] = new + "#/_"
    for k, _t, n in parts:
        if n:
            m["%s#/%s" % (rel, esc(k))] = "%s#/%s" % (new, esc(n))
    base = os.path.dirname(rel)
    for k, ref in links.items():
        target = os.path.normpath(os.path.join(base, ref)).replace(os.sep, "/")
        m["%s#/%s" % (rel, esc(k))] = target         # 指到的那份檔的新路徑：最後跟整張表對過再定
    return "md", "\n".join(pieces), m


def convert(src, dst, map_file, keep, force):
    if not os.path.isdir(src):
        return fail("PathBad", "%s is not a folder" % src)
    if os.path.lexists(dst):
        return fail("PathBad", "%s already exists (give a new folder)" % dst)
    shutil.copytree(src, dst, symlinks=True)
    table, kept, done = {}, [], []
    for rel in pages(dst):
        path = os.path.join(dst, rel)
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except ValueError as e:
            kept.append((rel, "not JSON (%s)" % e))
            continue
        got = ("json", "--keep") if rel in keep else plan(rel, doc, rel in force)
        if got[0] == "json":
            if rel in force:
                warn("%s cannot be forced to md: %s" % (rel, got[1]))
            kept.append((rel, got[1]))
            continue
        with open(os.path.join(dst, got[2][rel]), "w", encoding="utf-8") as f:
            f.write(got[1])
        os.remove(path)
        table.update(got[2])
        done.append(rel)
    files = {k: v for k, v in table.items() if "#" not in k}
    for k, v in list(table.items()):                    # $ref 那幾項：指到的檔換了就用新檔名
        if "#" in k and "#" not in v and v.endswith(".json"):
            table[k] = files.get(v, v)
    for cur, _dirs, names in os.walk(dst):              # `_index.json` 的鍵跟著改名
        if "_index.json" in names:
            rename_keys(dst, os.path.join(cur, "_index.json"), table)
    map_file = map_file or os.path.join(os.path.dirname(os.path.abspath(dst)), "kb_md_map.json")
    with open(map_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(table, ensure_ascii=False, indent=1) + "\n")
    for top in sorted({r.split("/")[0] + "/" if "/" in r else "(root)" for r in done + [k for k, _ in kept]}):
        def mine(r):
            return (r.split("/")[0] + "/" if "/" in r else "(root)") == top
        print("%s: %s %d pages to md, %d kept as json" % (PROG, top, sum(map(mine, done)), sum(1 for r, _ in kept if mine(r))))
    for rel, why in kept:
        print("%s: kept %s: %s" % (PROG, rel, why))
    print("%s: %d pages to md, %d kept as json; map %s (%d paths)" % (PROG, len(done), len(kept), map_file, len(table)))
    return 0


def rename_keys(dst, path, table):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    doc = json.loads(raw)
    if not isinstance(doc, dict):
        return
    folder = os.path.relpath(os.path.dirname(path), dst)
    out, changed = {}, False
    for k, v in doc.items():                            # 鍵是從這一夾算的路徑（可以是 ../x.json#/k）：換成從 knowledge 根算再查表，查到再換回從這一夾算
        f, sep, ptr = k.partition("#")
        new = map_one(table, os.path.normpath(os.path.join(folder, f)).replace(os.sep, "/") + sep + ptr) if f else None
        if new is not None:
            nf, nsep, nptr = new[0].partition("#")
            out[os.path.relpath(nf, folder).replace(os.sep, "/") + nsep + nptr] = v
            changed = True
        else:
            out[k] = v
    if changed:
        write_json(path, raw, out)


def map_one(table, path):
    """一條舊路徑 → (新路徑, warning 或 None)；檔不在表裡＝None。帶 #/ 時取表裡最長的前綴，多出來的段接在後面。"""
    f, sep, ptr = path.partition("#")
    if f not in table:
        return None
    segs = ptr.split("/") if sep else []
    for n in range(len(segs), 1, -1):
        k = f + "#" + "/".join(segs[:n])
        if k in table:
            rest = "/".join(segs[n:])
            return table[k] + ("/" + rest if rest else ""), ("deeper than the map: %s" % path if rest else None)
    if not sep:
        return table[f], None
    return table[f] + sep + ptr, "%s: the map has no such key, only the file name was changed" % path


def indent_of(raw):
    for line in raw.split("\n")[1:]:
        if line.strip():
            return len(line) - len(line.lstrip(" ")) or None
    return None


def write_json(path, raw, doc):
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=indent_of(raw)) + "\n")


class Rewriter:
    """照表把文字裡的舊路徑換成新路徑（只換完整的一條，長的優先）。"""
    def __init__(self, table):
        self.table = table
        files = sorted((k for k in table if "#" not in k and "/" in k), key=len, reverse=True)
        bare = sorted(k for k in table if "#" not in k and "/" not in k)
        if bare:
            warn("not rewritten (a bare file name is too common a word): %s" % ", ".join(bare))
        self.rx = re.compile(r"(?<![%s])(%s)(#(?:/[A-Za-z0-9_~\-]+(?:\.[A-Za-z0-9_~\-]+)*)*/?)?(?![\w/\-])(?!\.\w)"
                             % (PATHCH, "|".join(map(re.escape, files)))) if files else None

    def sub(self, text, where=""):
        """→ (新文字, 換了幾處, [warning])。"""
        if self.rx is None:
            return text, 0, []
        notes, n = [], [0]

        def one(m):
            new, note = map_one(self.table, m.group(0))
            if note:
                notes.append("%s: %s" % (where, note))
            if " " in new:
                line_start = text.rfind("\n", 0, m.start()) + 1
                if text.count("`", line_start, m.start()) % 2 == 0:
                    notes.append("%s:%d: %s has a space but is not inside backticks" % (where, text.count("\n", 0, m.start()) + 1, new))
            n[0] += 1
            return new
        return self.rx.sub(one, text), n[0], notes

    def value(self, v, where):
        if isinstance(v, str):
            return self.sub(v, where)
        if isinstance(v, list):
            got = [self.value(x, where) for x in v]
            return [g[0] for g in got], sum(g[1] for g in got), [w for g in got for w in g[2]]
        if isinstance(v, dict):
            got = {k: self.value(x, where) for k, x in v.items()}
            return {k: g[0] for k, g in got.items()}, sum(g[1] for g in got.values()), [w for g in got.values() for w in g[2]]
        return v, 0, []


def load_map(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rewrite(map_file, paths, dry):
    rw = Rewriter(load_map(map_file))
    total, files = 0, []
    for p in paths:
        if os.path.isdir(p):
            for cur, dirs, names in os.walk(p):
                dirs.sort()
                files += [os.path.join(cur, n) for n in sorted(names)]
        elif os.path.isfile(p):
            files.append(p)
        else:
            return fail("PathBad", "%s does not exist" % p)
    for path in files:
        if os.path.abspath(path) == os.path.abspath(map_file) or os.path.islink(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
        except (UnicodeDecodeError, OSError):
            continue
        doc = None
        if path.endswith(".json"):
            try:
                doc = json.loads(raw)
            except ValueError:
                doc = None
        if doc is not None:
            new, n, notes = rw.value(doc, path)
        else:
            new, n, notes = rw.sub(raw, path)
        for w in notes:
            warn(w)
        if not n:
            continue
        total += n
        print("%s: %s %d path%s%s" % (PROG, path, n, "" if n == 1 else "s", " (dry run)" if dry else ""))
        if not dry:
            if doc is not None:
                write_json(path, raw, new)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new)
    print("%s: %d paths rewritten%s" % (PROG, total, " (dry run, nothing written)" if dry else ""))
    return 0


def reach(root, path, place):
    """NEW 裡一條路徑讀不讀得到：None＝到了，否則一句原因（json 半路是 {"$ref": …} 就算到）。"""
    f = os.path.join(root, path)
    if not os.path.isfile(f):
        return "no such file"
    if not place:
        return None
    toks = mdpath.split(path + place)[1]
    with open(f, encoding="utf-8") as h:
        text = h.read()
    if f.endswith(".md"):
        try:
            mdpath.get(text, toks)
            return None
        except mdpath.Missing as e:
            return e.reason
    cur = json.loads(text)
    for tok in toks:
        if isinstance(cur, dict) and "$ref" in cur:
            return None
        if isinstance(cur, dict) and tok in cur:
            cur = cur[tok]
        elif isinstance(cur, list) and tok.isdigit() and int(tok) < len(cur):
            cur = cur[int(tok)]
        else:
            return "there is no %s" % tok
    return None


def verify(old, new, map_file):
    table = load_map(map_file)
    rw = Rewriter(table)
    kinds = {"same": [], "trailing newline": [], "different": [], "not found": []}
    changed_json = []
    for rel in pages(old):
        with open(os.path.join(old, rel), encoding="utf-8") as f:
            raw = f.read()
        doc = json.loads(raw)
        if not table.get(rel, "").endswith(".md"):     # 留 json 的頁：沒變，或只差換掉的路徑
            try:
                with open(os.path.join(new, rel), encoding="utf-8") as f:
                    now = f.read()
            except OSError:
                changed_json.append(rel + " (gone)")
                continue
            if now != raw and json.loads(now) != rw.value(doc, rel)[0]:
                changed_json.append(rel)
            continue
        arts = [(rel, as_text(doc))] if as_text(doc) is not None else [
            ("%s#/%s" % (rel, esc(k)), as_text(v)) for k, v in doc.items() if as_text(v) is not None]
        for key, text in arts:
            dest = table.get(key)
            if dest is None:
                kinds["not found"].append("%s (not in the map)" % key)
                continue
            f, toks = mdpath.split(dest)
            try:
                with open(os.path.join(new, f), encoding="utf-8") as h:
                    got = mdpath.get(h.read(), toks)
            except (OSError, mdpath.Missing) as e:
                kinds["not found"].append("%s -> %s (%s)" % (key, dest, getattr(e, "reason", None) or e))
                continue
            want = rw.sub(text)[0]
            k = ("same" if got == want else "trailing newline" if isinstance(got, str) and got.rstrip("\n") == want.rstrip("\n")
                 else "different")                      # md 每篇結尾恰好一個換行：原文結尾沒換行或多個換行都歸這類
            kinds[k].append("%s -> %s" % (key, dest))
    bad_paths = []
    for cur, dirs, names in os.walk(new):
        dirs.sort()
        for n in sorted(names):
            if not n.endswith((".md", ".json", ".txt")):
                continue
            p = os.path.join(cur, n)
            with open(p, encoding="utf-8") as h:
                text = h.read()
            if n.endswith(".json"):
                text = "\n".join(strings(json.loads(text)))
            seen = {(m.group(1), m.group(2) or "") for m in TICKED.finditer(text)} | {(m.group(1), "") for m in BARE.finditer(text)}
            for path, place in sorted(seen):
                if not path.endswith(".md"):            # 只查 md 的路徑（wf/ 庫的 .json 路徑多半是工作區裡的檔）
                    continue
                why = reach(new, path, place)
                if why:
                    bad_paths.append("%s: %s%s (%s)" % (os.path.relpath(p, new), path, place, why))
    for k in ("different", "not found"):
        for line in kinds[k]:
            print("%s: %s: %s" % (PROG, k, line))
    for line in kinds["trailing newline"]:
        print("%s: only a trailing newline differs: %s" % (PROG, line))
    for line in changed_json:
        print("%s: a page kept as json changed beyond the rewritten paths: %s" % (PROG, line))
    for line in bad_paths:
        print("%s: path not found: %s" % (PROG, line))
    print("%s: articles: %d same, %d only a trailing newline, %d different, %d not found; %d json pages changed; %d paths not found"
          % (PROG, len(kinds["same"]), len(kinds["trailing newline"]), len(kinds["different"]), len(kinds["not found"]),
             len(changed_json), len(bad_paths)))
    return 1 if kinds["different"] or kinds["not found"] or changed_json or bad_paths else 0


def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)
    elif isinstance(v, dict):
        for x in v.values():
            yield from strings(x)


def main(argv):
    if not argv:
        return fail("ArgumentsBad", "give a command")
    if argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest, pos, opts = argv[0], iter(argv[1:]), [], {"--map": None, "--keep": [], "--force-md": [], "--dry-run": False}
    for a in rest:
        if a in ("--map", "--keep", "--force-md"):
            v = next(rest, None)
            if v is None:
                return fail("ArgumentsBad", "%s needs a value" % a)
            if a == "--map":
                opts[a] = v
            else:
                opts[a].append(v)
        elif a == "--dry-run":
            opts[a] = True
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        elif a.startswith("-"):
            return fail("FlagUnknown", a)
        else:
            pos.append(a)
    if cmd == "convert" and len(pos) == 2:
        return convert(pos[0], pos[1], opts["--map"], set(opts["--keep"]), set(opts["--force-md"]))
    if cmd == "rewrite" and len(pos) >= 2:
        return rewrite(pos[0], pos[1:], opts["--dry-run"])
    if cmd == "verify" and len(pos) == 3:
        return verify(*pos)
    if cmd not in ("convert", "rewrite", "verify"):
        return fail("CommandUnknown", cmd)
    return fail("ArgumentsBad", "wrong number of arguments for %s" % cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
