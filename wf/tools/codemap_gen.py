#!/usr/bin/env python3
"""codemap_gen — 檔頭一句話的認法（函式庫，給 index_gen.py 寫逐檔 code map 用）；命令列是轉呼叫 index_gen.py 的薄殼。

  codemap_gen.py [--root REPO] [--apply] [--quiet]
    薄殼：照舊收這三個旗標，轉呼叫 `python3 wf/tools/index_gen.py`（它一次寫 _index.json 與 wf/knowledge/code-map/proto8/<夾>.json 逐檔表）。
    舊的 md 生成冊（common 底下的 code-map 夾與 code-map.md 轉址檔）11-13 晚刪了（使用者「舊的md版逐檔表和轉址檔可以刪。」）；沒人再跑本指令時刪命令列。

掃哪些檔：`git ls-files proto8`，去掉 thinking／archive／notes／user-advice／docs 夾、任何一層叫 archive／docs／
__pycache__ 的夾、.md（knowledge/ 除外）、.gitignore／.gitattributes、`_index.json`（資料夾的 index）、.vscode/（這份清單寫在 index_gen.json 的
codemap 段）。一個 proto8 頂層夾一份 json（照實際夾名），頂層單檔進 proto8.json；怎麼寫在 index_gen.codemap_tables。

一句話怎麼認（使用者 11-05 裁「逐檔表改生成」，thinking 2026-11-05 arch-refactor 03 § 4）：
  C/C++ 第一行註解；腳本（含 _entry）跳過 shebang 後第一行註解或 docstring；CMake 第一行註解；
  JSON 取 description／summary／$comment／title，`_entry` 形狀（argv）印成「入口：…」；knowledge 的 md 取第一個標題；
  捷徑印「→ 目標」。開頭若是檔名（或夾名）接 ` - `／` — `／`：`，連檔名一起去掉；`【模組】` 去掉；取到第一個句號。
  工具夾（有 _entry 又有 _tooldef.json 或 _metainfo.json）三個契約檔併成一列 `名/`。
依賴圖：各 `<夾>/<專案>/CMakeLists.txt` 的 target_link_libraries（略過 *_main）。
純標準庫；只讀檔頭，不跑任何程式。
"""
import json
import os
import re
import subprocess
import sys

with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "index_gen.json"), encoding="utf-8") as _f:
    CFG = json.load(_f)["codemap"]   # 掃描範圍只寫在 index_gen.json 的 codemap 段（11-13 線遷 code map 步 1）
SKIP_TOP = set(CFG["skip_top"])
SKIP_ANY_DIR = set(CFG["skip_any_dir"])
SKIP_NAMES = set(CFG["skip_names"])   # _index.json＝index_gen.py 生成的資料夾 index，不是程式檔
MD_DIRS = set(CFG["md_dirs"])         # 這些頂層夾的 .md 也列（出廠內容樹的說明）
TOOL_PARTS = ("_entry", "_tooldef.json", "_metainfo.json")
PROG = "codemap_gen"


def warn(msg):
    print(f"{PROG}: warning: {msg}", file=sys.stderr)


def tracked(proto):
    out = subprocess.run(["git", "-C", proto, "ls-files", "-z", "--", "."],
                         capture_output=True, check=True).stdout.decode()
    files = []
    for p in out.split("\0"):
        if not p:
            continue
        parts = p.split("/")
        if len(parts) > 1 and parts[0] in SKIP_TOP:
            continue
        if any(d in SKIP_ANY_DIR for d in parts[:-1]):
            continue
        name = parts[-1]
        if name in SKIP_NAMES:
            continue
        if name.endswith(".md") and not (len(parts) > 1 and parts[0] in MD_DIRS):
            continue
        if not os.path.lexists(os.path.join(proto, p)):
            continue
        files.append(p)
    return sorted(files)


def argv_text(argv):
    out = []
    for a in argv:
        if isinstance(a, dict) and "$env" in a:
            out.append("$" + str(a["$env"]))
        elif isinstance(a, dict) and "$ref" in a:
            out.append("$ref:" + str(a["$ref"]))
        else:
            out.append(str(a))
    return " ".join(out)


def json_desc(text, entry=False):
    try:
        d = json.loads(text)
    except ValueError:
        return ""
    if isinstance(d, list) and d:
        return ("入口：`" if entry else "argv：`") + argv_text(d) + "`"
    if isinstance(d, dict):
        for k in ("description", "summary", "$comment", "title"):
            if isinstance(d.get(k), str) and d[k].strip():
                return d[k]
        if isinstance(d.get("argv"), list):
            return "入口：`" + argv_text(d["argv"]) + "`"
        if isinstance(d.get("_entry"), list):
            return "入口 `" + argv_text(d["_entry"]) + "`；鍵：" + "、".join(k for k in d if k != "_entry")
        if d:
            return "設定（鍵：" + "、".join(list(d)[:6]) + ("…" if len(d) > 6 else "") + "）"
    return ""


COMMENT = re.compile(r'^\s*(//+|/\*+|\*+(?!/)|#+|--+|;+|"""|\'\'\')\s?(.*)$')


def text_desc(text, path):
    lines = text.splitlines()[:15]
    if path.endswith(".md"):
        for ln in lines:
            if ln.startswith("#"):
                return ln.lstrip("#").strip()
        return ""
    for i, ln in enumerate(lines):
        s = ln.strip()
        if i == 0 and s.startswith("#!"):
            continue
        if not s or s.startswith("cmake_minimum_required") or "coding" in s and s.startswith("#"):
            continue
        m = COMMENT.match(ln)
        if not m:
            return ""        # 第一個有意義的行就是程式碼：沒有一句話
        body = m.group(2).strip()
        body = re.sub(r'(\*/|"""|\'\'\')\s*$', "", body).strip()
        if body:
            return body
    return ""


def clean(desc, names):
    d = " ".join(desc.split())
    for n in sorted(names, key=len, reverse=True):
        if n and d.startswith(n):
            rest = d[len(n):]
            m = re.search(r"\s+[-—–]\s+|：|:\s", rest)
            if m and m.start() <= 120:
                d = rest[m.end():].strip()
            break
    d = re.sub(r"^【[^】]*】\s*", "", d)
    cut = d.find("。")
    if 0 <= cut < len(d) - 1:
        d = d[:cut + 1]
    if len(d) > 150:
        d = d[:149] + "…"
    return d.replace("|", "\\|")


def describe(proto, rel, follow=False, comment_only=False):
    full = os.path.join(proto, rel)
    if os.path.islink(full) and not follow:
        return "→ `" + os.readlink(full) + "`", False
    try:
        with open(full, encoding="utf-8", errors="replace") as f:
            text = f.read(16384)
    except OSError:
        return "", True
    base = os.path.basename(rel)
    stem = base.split(".")[0]
    parts = rel.split("/")
    names = {base, stem, "/".join(parts[-2:]), "/".join(parts[-3:])}   # 檔頭常寫 aos/post.hpp：…
    if base in ("_entry", "CMakeLists.txt"):
        names.add(parts[-2] if len(parts) > 1 else base)
    is_json = base.endswith(".json") or (base == "_entry" and text.lstrip()[:1] in "{[")
    if comment_only and is_json:
        return "", True
    if is_json:
        d = json_desc(text, base == "_entry")
    elif base.endswith(".txt") and base != "CMakeLists.txt":
        d = ""
    else:
        d = text_desc(text, rel)
    d = clean(d, names)
    bad = not d or d in names
    return d, bad


def units(proto, files):
    """回傳 [(rel 路徑或 'x/'、涵蓋的檔)]；工具夾三個契約檔併一列。"""
    fs = set(files)
    tooldirs = set()
    for f in files:
        dname, base = os.path.split(f)
        if base == "_entry" and (os.path.join(dname, "_tooldef.json") in fs or os.path.join(dname, "_metainfo.json") in fs):
            tooldirs.add(dname)
    out, seen = [], set()
    for f in files:
        dname, base = os.path.split(f)
        if dname in tooldirs and base in TOOL_PARTS:
            if dname not in seen:
                seen.add(dname)
                cov = [os.path.join(dname, p) for p in TOOL_PARTS if os.path.join(dname, p) in fs]
                out.append((dname + "/", cov))
        else:
            out.append((f, [f]))
    return out


def deps(proto, top, files):
    rows = []
    for f in files:
        parts = f.split("/")
        if len(parts) != 3 or parts[0] != top or parts[2] != "CMakeLists.txt":
            continue
        with open(os.path.join(proto, f), encoding="utf-8", errors="replace") as fh:
            text = re.sub(r"#[^\n]*", "", fh.read())
        pub, priv = [], []
        for m in re.finditer(r"target_link_libraries\s*\(([^)]*)\)", text):
            toks = m.group(1).split()
            if not toks or toks[0].endswith("_main"):
                continue
            mode = pub
            for t in toks[1:]:
                if t in ("PUBLIC", "INTERFACE"):
                    mode = pub
                elif t == "PRIVATE":
                    mode = priv
                elif t not in mode and not t.startswith("$"):
                    mode.append(t)
        if pub or priv:
            rows.append((parts[1], pub, priv))
    return rows


def unit_desc(proto, rel, cov):
    """一列（檔，或工具夾 'x/'）的一句話與「是不是沒取到」；index_gen 的逐檔表 json 用。"""
    if not rel.endswith("/"):
        return describe(proto, rel)
    # 工具夾：_entry 的註解 → _tooldef.description → _metainfo.summary（捷徑跟過去）→ _entry 的 argv
    d, bad = describe(proto, rel + "_entry", follow=True, comment_only=True)
    for alt, co in (("_tooldef.json", False), ("_metainfo.json", False), ("_entry", False)):
        if not bad:
            break
        if rel + alt in cov:
            d, bad = describe(proto, rel + alt, follow=True, comment_only=co)
    return d, bad


def main(argv):
    """過渡薄殼（11-13 線遷 code map 步 3，使用者裁 C3 甲）：照舊收 --root／--apply／--quiet，轉呼叫 index_gen.py。"""
    if "-h" in argv or "--help" in argv:
        print("\n".join(__doc__.split("\n")[:6]))
        return 0
    fwd = []
    it = iter(argv)
    for a in it:
        if a in ("--apply", "--quiet"):
            fwd.append(a)
        elif a == "-q":
            fwd.append("--quiet")
        elif a == "--root":
            v = next(it, None)
            if v is None:
                print(f"{PROG}: error: ArgumentsBad --root needs a path (usage: codemap_gen.py [--root REPO] [--apply] [--quiet])", file=sys.stderr)
                return 1
            fwd += ["--root", os.path.abspath(v)]
        else:
            print(f"{PROG}: error: FlagUnknown {a} (usage: codemap_gen.py [--root REPO] [--apply] [--quiet])", file=sys.stderr)
            return 1
    print(f"{PROG}: note: merged into index_gen.py; running `" + " ".join(["python3", "wf/tools/index_gen.py"] + fwd) + "`", file=sys.stderr)
    import index_gen
    return index_gen.main(fwd)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
