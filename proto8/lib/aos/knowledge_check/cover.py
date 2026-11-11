"""knowledge_check 的覆蓋與代號檢查：登記在 lib/packs 的工具、cmd 的 aos-* 指令、impls 的執行檔各有沒有自己的節點，tooldef 宣告的錯誤代號在不在庫裡、結尾合不合 C-54。

工具、指令清單一律從磁碟動態讀（lib/packs/*.json、cmd/*/bin/aos-*、impls/*/CMakeLists.txt），不寫死名字。
"""
import glob
import json
import os
import re

import knowledge_fs as fs
from checks import DETAILS_RE, ENDINGS, Problem, branches

EXE_RE = re.compile(r"add_executable\((aos-[A-Za-z0-9-]+?)_main\b")


def pack_tools(home):
    """lib/packs/*.json → [(工具名, 包檔名, tooldef 路徑或 None, 原因)]；同名在多包＝各列一次。"""
    out = []
    for pf in sorted(glob.glob(os.path.join(home, "lib", "packs", "*.json"))):
        try:
            with open(pf, encoding="utf-8") as h:
                tools = json.load(h).get("tools", {})
        except (OSError, ValueError, AttributeError) as e:
            out.append((None, os.path.basename(pf), None, "cannot read the pack: %s" % e))
            continue
        for name, entry in (tools.items() if isinstance(tools, dict) else ()):
            path = entry.get("path") if isinstance(entry, dict) else entry
            if isinstance(path, dict) and isinstance(path.get("$env"), str):
                base = home if path["$env"] == "AOS_HOME" else os.environ.get(path["$env"], "")
                folder = (base + path.get("$path", "")) if base else None
            elif isinstance(path, str):
                folder = os.path.normpath(os.path.join(os.path.dirname(pf), path))
            else:
                folder = None
            if folder is None:
                out.append((name, os.path.basename(pf), None, "its path %s cannot be resolved" % json.dumps(path)))
            elif os.path.isdir(folder):
                td = os.path.join(folder, "_tooldef.json")
                out.append((name, os.path.basename(pf), td if os.path.isfile(td) else None, "%s has no _tooldef.json" % folder))
            elif folder.endswith(".json") and os.path.isfile(folder):
                out.append((name, os.path.basename(pf), folder, ""))
            else:
                out.append((name, os.path.basename(pf), None, "%s is not a tool folder or JSON tool" % folder))
    return out


def tooldef(path):
    try:
        with open(path, encoding="utf-8") as h:
            td = json.load(h)
        return td if isinstance(td, dict) else {}
    except (OSError, ValueError):
        return {}


def check_tools(tree):
    out = []
    for name, pack, td, why in pack_tools(tree.home):
        where = "tool %s (%s)" % (name, pack) if name else pack
        if td is None:
            out.append(Problem("error", "tools", "ToolDefMissing", where, why))
            continue
        desc = tooldef(td).get("description", "")
        details = [m.rstrip(".,;:)") for m in DETAILS_RE.findall(desc if isinstance(desc, str) else "")]
        if not details:
            out.append(Problem("error", "tools", "ToolNodeMissing", where, "its _tooldef.json description has no 'Details: knowledge_read PATH'"))
            continue
        for d in details:
            try:
                ok = tree.exists(fs.join(fs.Loc(tree.root, None), d, False))
            except fs.ToolError:
                ok = False
            if not ok:
                out.append(Problem("error", "tools", "ToolNodeMissing", where, "Details: knowledge_read %s does not resolve" % d))
    return out


def index_descriptions(tree):
    """樹裡每張表（_index.json 與 _index key）每一格的 _description。"""
    out = []
    for d in tree.folders():
        table, _ = tree.json(os.path.join(d, "_index.json")) if os.path.isfile(os.path.join(d, "_index.json")) else ({}, None)
        out += [c.get("_description") for c in (table or {}).values() if isinstance(c, dict)]
    for f in tree.files():
        value, _ = tree.json(f)
        for _, obj in branches(value, ()):
            if isinstance(obj["_index"], dict):
                out += [c.get("_description") for c in obj["_index"].values() if isinstance(c, dict)]
    return [s for s in out if isinstance(s, str)]


def mentioned(names, texts):
    return {n for n in names if any(re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(n), t) for t in texts)}


def check_cmds(tree, kind):
    """kind＝cmds（cmd/*/bin/aos-*，錯誤）或 impls（impls 的執行檔，提醒）；有節點＝某張表某一格的 _description 寫出完整指令名。"""
    if kind == "cmds":
        names = sorted({os.path.basename(p) for p in glob.glob(os.path.join(tree.home, "cmd", "*", "bin", "aos-*")) if os.path.isfile(p)})
    else:
        names = set()
        for cm in glob.glob(os.path.join(tree.home, "impls", "*", "CMakeLists.txt")):
            with open(cm, encoding="utf-8", errors="replace") as h:
                names |= set(EXE_RE.findall(h.read()))
        names = sorted(names)
    found = mentioned(names, index_descriptions(tree))
    level, code = ("error", "CmdNodeMissing") if kind == "cmds" else ("warning", "")
    return [Problem(level, kind, code, "command %s" % n, "no index entry's _description names it") for n in names if n not in found]


def check_codes(tree):
    """tooldef 宣告的錯誤代號：庫裡全文找不到、結尾不在 C-54 表＝提醒（一個代號一行，附宣告它的工具）。"""
    declared = {}
    for name, _, td, _ in pack_tools(tree.home):
        errors = tooldef(td).get("errors", []) if td else []
        for code in errors if isinstance(errors, list) else []:
            if isinstance(code, str):
                declared.setdefault(code, []).append(name)
    text = ""
    for f in tree.files():
        try:
            with open(f, encoding="utf-8") as h:
                text += h.read() + "\n"
        except (OSError, UnicodeDecodeError):
            pass
    out = []
    for code in sorted(declared):
        tools = ", ".join(sorted(set(declared[code])))
        if not re.search(r"\b%s\b" % re.escape(code), text):
            out.append(Problem("warning", "codes", "", "code %s" % code, "declared by %s; not found in the knowledge base" % tools))
        if code != "Internal" and not code.endswith(ENDINGS):
            out.append(Problem("warning", "codes", "", "code %s" % code, "declared by %s; its ending is not one of C-54's (%s, Internal)" % (tools, ", ".join(ENDINGS))))
    return out
