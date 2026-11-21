#!/usr/bin/env python3
"""kb_md_shape — 把 knowledge 裡「資料形狀」的 json 頁換成同名 `.md`：鍵變標題、短字串物件變字典式清單、字串陣列變清單或段落、記錄陣列變編號小節、只適合當資料的留 json 區塊；每個葉值都讀回來核對。

kb_md_shape.py convert DIR [--write] [--map FILE] [--keep PATH]…
  DIR 是一個 knowledge 庫的夾（例 proto8/knowledge/wf）。夾裡每一份 `_index.json` 以外的 `.json` 頁照下面的規則換成 md；
  不帶 --write 只印會怎麼換（每頁一行：幾個葉值、哪幾個鍵退回 json 區塊），帶了才寫 `.md`、移掉 `.json`、改 `_index.json` 的鍵。
  --keep PATH（從 DIR 算）那一頁不換。--map FILE 把「舊路徑 → 新路徑」寫成 json（路徑從 DIR 的上一層算，例 wf/x.json#/a → wf/x.md#/a）。
規則（一頁是物件時；每個鍵一個 `#` 標題，巢狀再深一級）：
  `_description`（字串或字串陣列）  放最上面當開頭一段，不加標題（用 `#/_` 讀）。
  字串                              標題底下一段字（用 `#/鍵/_` 讀；`#/鍵` 拿到含標題行的整節）。
  字串陣列                          每個元素一行的清單 `- …`（`#/鍵/0`）；元素看起來本來就是 md（有空行、縮排、清單記號、圍欄）就整段照放（`#/鍵/_`）。
  值全是單行字串的物件              字典式清單 `- 鍵: 值`（`#/鍵/子鍵`）。
  其他物件                          每個子鍵一個小標題。
  物件陣列                          每筆一個小標題，標題字是它的號碼（`#/鍵/0/欄`）。
  `{"$ref": 路徑}`                   一行 `→ \\`路徑\\``（路徑寫成從庫根算的完整路徑）。
  `skeleton`、數字、布林、null、空的物件或陣列、其他形狀   一個 ```json 區塊（`#/鍵` 拿到原值，可以照 json 往下尋）。
  整頁就是一段文字                  整份 md 就是那段字。
每頁換完用 proto8/py/aos/mdpath.py 把舊 json 的每個葉值從新 md 讀回來比（文字比到結尾換行之前）；哪個鍵底下有葉值讀不回來，那個鍵整個退回 json 區塊再比一次。
跟 kb_md.py 的分工：kb_md.py 搬「有標題的文章」（內容逐字不動）；這支換「沒有標題的資料」的形狀（字不少，但排法變了）。
出處：使用者 11-21 晚「wf/剩下的也換一換」；規劃 proto8/thinking/2026-11/21/知識庫-骨架加md-規劃-1121/15。純標準庫＋aos.mdpath。"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "proto8", "py"))
from aos import mdpath  # noqa: E402

PROG = "kb_md_shape"
SIMPLE_KEY = re.compile(r"^[A-Za-z0-9_.\-]+$")


def strarr(v):
    return isinstance(v, list) and bool(v) and all(isinstance(x, str) for x in v)


def has_heading(lines):
    return bool(mdpath._heads(lines))


def md_like(items):
    """字串陣列的元素本來就是 md 的行（空行、縮排、清單記號、圍欄、表格、引用）＝整段照放，不逐個加 `- `。"""
    return any(x == "" or x != x.strip() or x.startswith(("```", "~~~", "|", ">")) or mdpath.ITEM.match(x) for x in items)


def block(v):
    return ["```json"] + json.dumps(v, ensure_ascii=False, indent=1).split("\n") + ["```"]


class Page:
    """一頁的轉換：lines＝md 的行；leaves＝[(舊 token 串, 新 token 串, 值, 比法)]，比法 exact／text／ref。"""
    def __init__(self, lib_dir, forced):
        self.lines, self.leaves, self.lib_dir, self.forced = [], [], lib_dir, forced

    def leaf(self, old, new, value, how="exact"):
        self.leaves.append((list(old), list(new), value, how))

    def json_block(self, v, toks):
        self.lines += block(v) + [""]
        self.leaf(toks, toks, v)

    def body(self, v, lvl, toks, top):
        if top in self.forced:
            return self.json_block(v, toks)
        if isinstance(v, str):
            ls = v.split("\n")
            if not v.strip() or v != v.strip() or has_heading(ls):
                return self.json_block(v, toks)
            self.lines += ls + [""]
            return self.leaf(toks, toks + ["_"], v, "text")
        if strarr(v):
            if any("\n" in x for x in v) or has_heading(v):
                return self.json_block(v, toks)
            if md_like(v):
                self.lines += v + [""]
                return self.leaf(toks, toks + ["_"], "\n".join(v), "text")
            for i, x in enumerate(v):
                self.lines.append("- " + x)
                self.leaf(toks + [str(i)], toks + [str(i)], x)
            self.lines.append("")
            return None
        if isinstance(v, dict):
            if set(v) == {"$ref"} and isinstance(v["$ref"], str):
                full = os.path.normpath(os.path.join(self.lib_dir, v["$ref"].partition("#")[0])) + ("#" + v["$ref"].partition("#")[2] if "#" in v["$ref"] else "")
                self.lines += ["→ `%s`" % full, ""]
                return self.leaf(toks, toks + ["_"], full, "ref")
            if not v or toks[-1:] == ["skeleton"]:
                return self.json_block(v, toks)
            if all(isinstance(x, str) and "\n" not in x and x == x.strip() for x in v.values()) and all(SIMPLE_KEY.match(k) and not mdpath.INT.match(k) for k in v):
                for k, x in v.items():
                    self.lines.append("- %s: %s" % (k, x) if x else "- %s:" % k)
                    self.leaf(toks + [k], toks + [k], x)
                self.lines.append("")
                return None
            if lvl < 6 and all(k.strip() == k and k and k != "_" and "\n" not in k for k in v):
                for k, x in v.items():
                    self.key(k, x, lvl + 1, toks + [k], top)
                return None
            return self.json_block(v, toks)
        if isinstance(v, list) and v and all(isinstance(x, dict) and x for x in v) and lvl < 6:
            for i, x in enumerate(v):
                self.key(str(i), x, lvl + 1, toks + [str(i)], top)
            return None
        return self.json_block(v, toks)

    def key(self, name, v, lvl, toks, top):
        self.lines += ["#" * lvl + " " + name, ""]
        self.body(v, lvl, toks, top)


def render(doc, lib_dir, forced=()):
    p = Page(lib_dir, set(forced))
    if isinstance(doc, str) or strarr(doc):
        text = doc if isinstance(doc, str) else "\n".join(doc)
        p.lines = text.split("\n")
        p.leaf([], [], text, "whole")
        return p
    if not isinstance(doc, dict):
        return None
    for k, v in doc.items():
        if k == "_description" and (isinstance(v, str) or strarr(v)) and not has_heading(v.split("\n") if isinstance(v, str) else v):
            text = v if isinstance(v, str) else "\n".join(v)
            p.lines = text.split("\n") + [""] + p.lines if not p.lines else p.lines + text.split("\n") + [""]
            p.leaf([k], ["_"], text, "text")
        elif k.strip() != k or not k or k == "_" or "\n" in k:
            return None
        else:
            p.key(k, v, 1, [k], k)
    while p.lines and p.lines[-1] == "":
        p.lines.pop()
    return p


def failed(p):
    """讀回來不對的葉值 → 它們的頂層鍵。"""
    text, bad = "\n".join(p.lines) + "\n", set()
    for old, new, value, how in p.leaves:
        try:
            got = mdpath.get(text, new)
        except mdpath.Missing:
            got = mdpath
        if how == "whole":
            ok = got.rstrip("\n") == value.rstrip("\n")
        elif how == "text":
            ok = isinstance(got, str) and got.rstrip("\n") == value.rstrip("\n")
        elif how == "ref":
            ok = isinstance(got, str) and got.strip() == "→ `%s`" % value
        else:
            ok = got == value and type(got) is type(value)
        if not ok:
            bad.add(old[0] if old else "")
    return bad


def convert_page(doc, lib_dir):
    """回 (Page 或 None, 退回 json 區塊的頂層鍵)。None＝這頁換不了（留 json）。"""
    forced = set()
    for _ in range(3):
        p = render(doc, lib_dir, forced)
        if p is None:
            return None, forced
        bad = failed(p)
        if not bad:
            return p, forced
        if "" in bad or bad <= forced:
            return None, forced
        forced |= bad
    return None, forced


def ptr(toks):
    return "".join("/" + t.replace("~", "~0").replace("/", "~1") for t in toks)


def main(argv):
    if len(argv) < 2 or argv[0] != "convert":
        print("usage: kb_md_shape.py convert DIR [--write] [--map FILE] [--keep PATH]...", file=sys.stderr)
        return 1
    root, write, mapf, keep = argv[1].rstrip("/"), False, None, set()
    it = iter(argv[2:])
    for a in it:
        if a == "--write":
            write = True
        elif a == "--map":
            mapf = next(it)
        elif a == "--keep":
            keep.add(next(it))
        else:
            print("%s: error: ArgumentsBad unknown argument %s" % (PROG, a), file=sys.stderr)
            return 1
    lib = os.path.basename(root)
    table, done, kept, renamed = {}, 0, [], {}
    for d, _dirs, files in sorted(os.walk(root)):
        for fn in sorted(files):
            rel = os.path.relpath(os.path.join(d, fn), root)
            if not fn.endswith(".json") or fn == "_index.json":
                continue
            if rel in keep:
                kept.append((rel, "--keep"))
                continue
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                doc = json.load(f)
            page, forced = convert_page(doc, os.path.join(lib, os.path.dirname(rel)))
            if page is None:
                kept.append((rel, "could not be read back from markdown"))
                continue
            new = rel[:-5] + ".md"
            if os.path.exists(os.path.join(root, new)):
                kept.append((rel, "%s already exists" % new))
                continue
            done += 1
            print("%s: %s -> %s, %d values read back%s" % (PROG, rel, new, len(page.leaves),
                                                         "; kept as json blocks: %s" % ", ".join(sorted(forced)) if forced else ""))
            table["%s/%s" % (lib, rel)] = "%s/%s" % (lib, new)
            for old, nw, _v, how in page.leaves:
                if old:
                    table["%s/%s#%s" % (lib, rel, ptr(old))] = "%s/%s#%s" % (lib, new, ptr(nw[:-1] if how in ("text", "ref") and nw != ["_"] else nw))
                    for n in range(1, len(old)):        # 中間那幾層（物件、陣列）路徑不變
                        table.setdefault("%s/%s#%s" % (lib, rel, ptr(old[:n])), "%s/%s#%s" % (lib, new, ptr(old[:n])))
            renamed[os.path.join(d, fn)] = new
            if write:
                with open(os.path.join(root, new), "w", encoding="utf-8") as f:
                    f.write("\n".join(page.lines) + "\n")
                os.remove(os.path.join(d, fn))
    if write:                                           # 夾的 _index.json：鍵跟著改名
        for d, _dirs, files in os.walk(root):
            if "_index.json" not in files:
                continue
            path = os.path.join(d, "_index.json")
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            idx = json.loads(raw)
            out = {}
            for k, v in idx.items():
                name, sep, rest = k.partition("#")
                full = os.path.normpath(os.path.join(d, name))
                out[(name[:-5] + ".md" + sep + rest) if full in renamed else k] = v
            if list(out) != list(idx):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    if mapf:
        with open(mapf, "w", encoding="utf-8") as f:
            json.dump(table, f, ensure_ascii=False, indent=1)
            f.write("\n")
    for rel, why in kept:
        print("%s: kept %s: %s" % (PROG, rel, why))
    print("%s: %d pages to md, %d kept as json%s" % (PROG, done, len(kept), "" if write else " (dry run; --write to do it)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
