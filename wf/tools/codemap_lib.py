#!/usr/bin/env python3
"""codemap_lib — 檔頭一句話的認法（函式庫，給 index_gen.py 寫逐檔 code map 用；沒有命令列）。

掃哪些檔：`git ls-files proto8`，去掉 thinking／archive／docs 夾、任何一層叫 archive／docs／
__pycache__ 的夾、.md（knowledge/ 除外）、.gitignore／.gitattributes、`_index.json`（資料夾的 index）、.vscode/（這份清單寫在 index_gen.json 的
codemap 段）。一個 proto8 頂層夾一份 json（照實際夾名），頂層單檔進 proto8.json；怎麼寫在 index_gen.codemap_tables。

一句話怎麼認（使用者 11-05 裁「逐檔表改生成」，thinking 2026-11-05 arch-refactor 03 § 4）：
  C/C++ 第一行註解；腳本（含 _entry）跳過 shebang 後第一行註解或 docstring；Makefile 第一行註解；
  JSON 取 description／summary／$comment／title，再來是 `_description`（knowledge 的節點）或整份就是一段 md（字串或字串陣列：
  knowledge 的 `_description.json`、aos/rules.md 這類）的第一個標題；`_entry` 形狀（argv）印成「入口：…」；knowledge 的 md 取第一個標題；
  捷徑印「→ 目標」（看 git 記的 mode 120000，core.symlinks=false 的 Windows 複本也一樣）。
  開頭若是檔名（或夾名）接 ` - `／` — `／`：`，連檔名一起去掉；`【模組】` 去掉；取到第一個句號。
  工具夾（有 _entry 又有 _tooldef.json 或 _metainfo.json）三個契約檔併成一列 `名/`。
依賴表（C++ 誰連誰、Python 誰 import 誰、bin 指令對原始碼）不在這裡，在 codemap_deps.py。
純標準庫；只讀檔頭，不跑任何程式。
"""
import json
import os
import posixpath
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
PROG = "codemap_lib"
LINKS = {}                            # proto 路徑 → git 記成捷徑（mode 120000）的相對路徑集合；tracked() 填
TRACKED = {}                          # proto 路徑 → git ls-files 的全部相對路徑（捷徑只跟進到這裡面的檔）；tracked() 填


def warn(msg):
    print(f"{PROG}: warning: {msg}", file=sys.stderr)


def tracked(proto):
    out = subprocess.run(["git", "-C", proto, "ls-files", "-s", "-z", "--", "."],
                         capture_output=True, check=True).stdout.decode()
    files, links, every = [], set(), set()
    for ent in out.split("\0"):
        if "\t" not in ent:
            continue
        mode, p = ent.split(" ", 1)[0], ent.split("\t", 1)[1]
        every.add(p)
        if mode == "120000":
            links.add(p)
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
    LINKS[proto], TRACKED[proto] = links, every
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


def md_title(v):
    """一段 md（字串，或一行一個元素的字串陣列）的第一個標題；沒有標題取第一行有字的；不是這種形狀回 ""。"""
    if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
        v = "\n".join(v)
    if not isinstance(v, str):
        return ""
    rows = [ln.strip() for ln in v.splitlines() if ln.strip()]
    return next((ln.lstrip("#").strip() for ln in rows if ln.startswith("#")), rows[0] if rows else "")


def json_desc(text, entry=False):
    try:
        d = json.loads(text)
    except ValueError:
        return ""
    if isinstance(d, str) or (not entry and isinstance(d, list) and d and all(isinstance(x, str) for x in d)
                              and any(x.startswith("#") for x in d)):
        return md_title(d)                              # 整份就是一段 md（knowledge 的正文檔）
    if isinstance(d, list) and d:
        return ("入口：`" if entry else "argv：`") + argv_text(d) + "`"
    if isinstance(d, dict):
        for k in ("description", "summary", "$comment", "title"):
            if isinstance(d.get(k), str) and d[k].strip():
                return d[k]
        if md_title(d.get("_description")):            # knowledge 的節點：_description 是一段 md
            return md_title(d["_description"])
        if isinstance(d.get("argv"), list):
            return "入口：`" + argv_text(d["argv"]) + "`"
        if isinstance(d.get("_entry"), list):
            return "入口 `" + argv_text(d["_entry"]) + "`；鍵：" + "、".join(k for k in d if k != "_entry")
        if d:
            return "設定（鍵：" + "、".join(list(d)[:6]) + ("…" if len(d) > 6 else "") + "）"
        return "設定（空的 {}：全用預設）"               # 內容就是 {} 的設定檔（程式會讀，不能往裡面加說明鍵）
    return ""


COMMENT = re.compile(r'^\s*(//+|/\*+|\*+(?!/)|#+|--+|;+|"""|\'\'\')\s?(.*)$')


def text_desc(text, path):
    lines = text.splitlines()[:15]
    if path.endswith(".md"):
        first = next((ln.strip() for ln in lines if ln.strip()), "")
        if first and not first.startswith(("#", "←", ">", "[", "|", "<", "```")):
            return first                                # 開頭是一段話的 md（知識庫的頁：最上面那段就是它的簡介；鍵名當標題的頁標題只是 when、steps）
        for ln in lines:
            if ln.startswith("#"):
                return ln.lstrip("#").strip()
        return first if not first.startswith(("←", ">", "[", "|", "<", "```")) else ""
    for i, ln in enumerate(lines):
        s = ln.strip()
        if i == 0 and s.startswith("#!"):
            continue
        if not s or s.startswith("cmake_minimum_required") or re.match(r"#.*?coding[:=]", s):    # 只跳 PEP 263 的編碼宣告；「pi coding agent」這種一句話照收
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
    if os.path.islink(full) or rel in LINKS.get(proto, ()):
        try:
            if os.path.islink(full):
                target = os.readlink(full)
            else:                                       # git 記成捷徑、複本抄成「內容＝目標」的小檔（Windows）
                with open(full, encoding="utf-8") as f:
                    target = f.read().strip()
        except (OSError, UnicodeDecodeError):
            return "", True
        if not follow:
            return "→ `" + target + "`", False
        dest = posixpath.normpath(posixpath.join(posixpath.dirname(rel), target))
        if proto in TRACKED and dest not in TRACKED[proto]:
            return "", True                             # 指到樹外（如裝好的 lib/）：不跟，免得有沒有跑過 install.py 結果不同
        full = os.path.join(proto, dest)
    try:
        with open(full, encoding="utf-8", errors="replace") as f:
            text = f.read() if full.endswith(".json") else f.read(16384)   # json 要整份才解得開
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
    elif base.endswith((".html", ".htm")):
        m = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
        d = m.group(1).strip() if m else ""
    else:
        d = text_desc(text, rel)
    d = clean(d, names)
    bad = not d or d in names
    return d, bad


def units(proto, files):
    """回傳 [(rel 路徑或 'x/'、涵蓋的檔)]；工具夾三個契約檔併一列（git 的路徑一律 /，Windows 上也用 posixpath 接）。"""
    fs = set(files)
    tooldirs = set()
    for f in files:
        dname, base = posixpath.split(f)
        if base == "_entry" and (posixpath.join(dname, "_tooldef.json") in fs or posixpath.join(dname, "_metainfo.json") in fs):
            tooldirs.add(dname)
    out, seen = [], set()
    for f in files:
        dname, base = posixpath.split(f)
        if dname in tooldirs and base in TOOL_PARTS:
            if dname not in seen:
                seen.add(dname)
                cov = [posixpath.join(dname, p) for p in TOOL_PARTS if posixpath.join(dname, p) in fs]
                out.append((dname + "/", cov))
        else:
            out.append((f, [f]))
    return out


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
