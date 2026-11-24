#!/usr/bin/env python3
"""codemap_deps — code map 的三張依賴表（C++ 誰連誰、Python 誰 import 誰、bin/ 每支指令對到哪個原始碼）的認法；給 index_gen.py 用，沒有命令列。

  cpp 表：讀 proto8/cpp/Makefile 的文字（`LIBS`、`BINS`、`DEPS_<專案>`、明寫的 `$(LIBDIR)/libaos-*.a|so` 目標），不呼叫 make。
          DEPS_<專案> 是連結順序上它要的全部 .a（已含間接的），所以 links 欄＝全部、不分直接間接。
  py 表：靜態掃 `from aos… import …`、`import aos…` 行（含縮排在函式裡的、括號跨行的），不 import、不跑程式；
         一個單位＝py/aos/apps/<名>、py/aos 的一個子套件或模組、py/tools 的一個工具夾、templates 的一個範本夾；tests 不掃。
  bin 表：py/entries.json 的 commands（Python 入口）＋ Makefile 的 BINS（C++ 執行檔），就是 install.py 往 bin/ 放的東西。
三張表都是 wf-table/1 形狀（columns＋rows，值都是字串，多個值用空白隔開），tabledb.py 讀得動；路徑從 repo 根算。純標準庫。
"""
import json
import os
import re

FROM = re.compile(r"^[ \t]*from[ \t]+(aos(?:\.\w+)*)[ \t]+import[ \t]+(\([^)]*\)|[^\n#;]+)", re.M)
IMPORT = re.compile(r"^[ \t]*import[ \t]+(aos[^\n#;]*)", re.M)


def makefile_vars(text):
    """Makefile 的 `名 := 值`／`?=`／`=`（行尾 \\ 接續、# 註解去掉；recipe 行與 define 裡的 `$(1)_x` 不算）→ {名: 值}。"""
    out = {}
    for ln in text.replace("\\\n", " ").splitlines():
        if ln.startswith("\t"):
            continue
        m = re.match(r"^([A-Za-z_]\w*)\s*(?::=|\?=|=)\s*(.*)$", ln.split("#", 1)[0])
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def cpp_rows(proto, files):
    """回 (Makefile 的 proto8 相對路徑, [列])；沒有 Makefile 回 (None, [])。"""
    text = read(os.path.join(proto, "cpp", "Makefile"))
    if text is None:
        return None, []
    v = makefile_vars(text)
    libs, bins = v.get("LIBS", "").split(), v.get("BINS", "").split()
    deps = {k[5:]: val.split() for k, val in v.items() if k.startswith("DEPS_")}
    explicit = sorted(set(re.findall(r"^\$\(LIBDIR\)/(libaos-[\w-]+\.(?:a|so))\s*:", text, re.M)))
    dirs = {f.split("/")[1][4:] for f in files if f.startswith("cpp/aos-") and f.count("/") >= 2}
    rows = []
    for p in sorted(dirs | set(libs) | set(bins) | set(deps)):
        products = (["libaos-%s.a" % p] if p in libs else []) + [x for x in explicit if x.startswith("libaos-%s." % p)]
        products = list(dict.fromkeys(products)) + (["bin/aos-%s" % p] if p in bins else [])
        lang = "C" if any(f.startswith("cpp/aos-%s/" % p) and f.endswith(".c") for f in files) else "C++"
        rows.append({"project": "aos-" + p, "lang": lang, "products": " ".join(products),
                     "links": " ".join("aos-" + d for d in deps.get(p, [])),
                     "used_by": " ".join(sorted("aos-" + q for q, ds in deps.items() if p in ds)),
                     "dir": "proto8/cpp/aos-" + p})
    return "cpp/Makefile", rows


def is_python(proto, rel):
    if rel.endswith(".py"):
        return True
    base = os.path.basename(rel)
    if "." in base or os.path.islink(os.path.join(proto, rel)):
        return False
    head = (read(os.path.join(proto, rel)) or "")[:200]
    return head.startswith("#!") and "python" in head.splitlines()[0]


TEMPLATE_KINDS = ("agents", "kernels", "orgs", "daemons", "starts", "tools")   # templates 底下的類別夾


def unit_of(rel):
    """proto8 相對路徑 → (單位路徑, 種類, 單位自己的模組名或 "")；不掃的回 None。"""
    parts = rel.split("/")
    if "tests" in parts or "fixtures" in parts:
        return None
    if parts[:3] == ["py", "aos", "apps"]:                # apps/__init__.py 只是套件記號，不算一個單位
        return ("/".join(parts[:4]), "app", "aos.apps." + parts[3]) if len(parts) > 4 else None
    if parts[:2] == ["py", "aos"] and len(parts) > 3:
        return "/".join(parts[:3]), "lib", "aos." + parts[2]
    if parts[:2] == ["py", "aos"] and len(parts) == 3:
        mod = parts[2][:-3]
        return rel, "lib", "aos" if mod == "__init__" else "aos." + mod
    if parts[:2] == ["py", "tools"] and len(parts) > 3:
        return "/".join(parts[:4]), "tool", ""
    if parts[0] == "templates" and len(parts) > 3 and parts[1] in TEMPLATE_KINDS:   # templates/<類別>/<範本>/…（11-24 三分）
        return "/".join(parts[:3]), "template", ""
    if parts[0] == "templates" and len(parts) > 2:
        return "/".join(parts[:2]), "template", ""
    return None


def modules(files):
    """py/aos 底下每個 .py 的模組名（套件的 __init__.py＝套件名）。"""
    out = set()
    for f in files:
        if f.startswith("py/aos/") and f.endswith(".py"):
            name = f[3:-3].replace("/", ".")
            out.add(name[:-9] if name.endswith(".__init__") else name)
    return out


def imports(text, mods):
    """一個 Python 檔 import 到的 aos 模組（`from aos.x import y` 的 y 是模組就記 aos.x.y，否則記 aos.x）。"""
    used = set()
    for m in FROM.finditer(text):
        base = m.group(1)
        for name in m.group(2).strip("() \t\n").replace("\n", ",").split(","):
            name = name.split()[0] if name.split() else ""
            if name and name != "*" and base + "." + name in mods:
                used.add(base + "." + name)
            elif name:
                used.add(base)
    for m in IMPORT.finditer(text):
        for part in m.group(1).split(","):
            name = part.split()[0] if part.split() else ""
            if name == "aos" or name.startswith("aos."):
                used.add(name)
    return used


def py_rows(proto, files):
    mods = modules(files)
    units = {}
    for f in files:
        u = unit_of(f)
        if not u or not is_python(proto, f):
            continue
        text = read(os.path.join(proto, f)) or ""
        row = units.setdefault(u[0], {"unit": "proto8/" + u[0], "kind": u[1], "module": u[2], "uses": set()})
        own = u[2]
        row["uses"] |= {m for m in imports(text, mods) if not own or (m != own and not m.startswith(own + "."))}
    rows = []
    for key in sorted(units):
        r = units[key]
        if not r["uses"] and r["kind"] not in ("app", "lib"):    # 指令與共用模組每個都列；工具、範本沒用到 aos 的不列
            continue
        mod = r["module"]
        users = sorted(o["unit"] for o in units.values()
                       if mod and mod != "aos" and o is not r and any(x == mod or x.startswith(mod + ".") for x in o["uses"]))
        rows.append({"unit": r["unit"], "kind": r["kind"], "module": mod, "uses": " ".join(sorted(r["uses"])),
                     "used_by": " ".join(users)})
    return rows


def module_file(mod, files):
    rel = "py/" + mod.replace(".", "/")
    for cand in (rel + ".py", rel + "/__init__.py"):
        if cand in files:
            return "proto8/" + cand
    return ""


def bin_rows(proto, files, cpp):
    """bin/ 的每支指令：Python 的照 py/entries.json，C++ 的照 Makefile 的 BINS（cpp＝cpp_rows 的列）。"""
    fs = set(files)
    rows = []
    try:
        cmds = json.loads(read(os.path.join(proto, "py", "entries.json")) or "{}").get("commands", {})
    except ValueError:
        cmds = {}
    for name, mod in sorted(cmds.items()):
        rows.append({"command": name, "lang": "Python", "source": module_file(mod, fs), "module": mod,
                     "from": "proto8/py/entries.json"})
    for r in cpp:
        if "bin/" + r["project"] in r["products"].split():
            main = "cpp/%s/src/main.cpp" % r["project"]
            rows.append({"command": r["project"], "lang": r["lang"], "source": "proto8/" + main if main in fs else "",
                         "module": "", "from": "proto8/cpp/Makefile"})
    return sorted(rows, key=lambda r: r["command"])


def tables(proto, files, gen_by):
    """回 {檔名: 表}：cpp.json、py.json、bin.json（wf-table/1）；某張沒有東西就不出。"""
    src, cpp = cpp_rows(proto, files)
    py = py_rows(proto, files)
    bins = bin_rows(proto, files, cpp)
    tail = "生成物，別手改；要改去改 Makefile／import 行／entries.json，再跑 python3 wf/tools/index_gen.py --apply。多個值用空白隔開。"
    out = {}
    if cpp:
        out["cpp.json"] = {
            "contract": "wf-table/1", "generated_by": gen_by, "source": "proto8/" + src,
            "description": "C／C++ 專案誰連誰：一個專案一列，讀 proto8/cpp/Makefile 的 LIBS、BINS、DEPS_<專案>（不跑 make）。"
                           "products＝它產出的函式庫與 bin/ 執行檔；links＝連結時要的全部 aos 函式庫（照連結順序，已含間接的；"
                           "include 路徑也照這張）；used_by＝反過來誰要它。" + tail,
            "columns": ["project", "lang", "products", "links", "used_by", "dir"], "rows": cpp}
    if py:
        out["py.json"] = {
            "contract": "wf-table/1", "generated_by": gen_by, "source": "proto8/py",
            "description": "Python 誰用到 aos 套件的哪些模組：靜態掃 import 行（不跑程式）。一列一個單位——kind app＝py/aos/apps/<名>（每支都列）、"
                           "lib＝py/aos 的子套件或模組（每個都列）、tool＝py/tools 的工具夾、template＝templates 的範本夾（這兩種只列用到 aos 的）；tests 不掃。"
                           "uses＝它 import 的 aos 模組（自己單位裡的不算）；used_by＝反過來哪些單位 import 它（只有 app、lib 有）。" + tail,
            "columns": ["unit", "kind", "module", "uses", "used_by"], "rows": py}
    if bins:
        out["bin.json"] = {
            "contract": "wf-table/1", "generated_by": gen_by, "source": "proto8/py/entries.json",
            "description": "install.py 往 $AOS_HOME/bin/ 放的每支指令對到哪個原始碼：Python 的照 proto8/py/entries.json（module＝bin/ 入口當 __main__ 跑的模組），"
                           "C++ 的照 proto8/cpp/Makefile 的 BINS（source＝該專案的 src/main.cpp，連哪些庫看 cpp.json）。"
                           "前端外掛的 frontend/bin/aos-frontend 不在 bin/，不列。" + tail,
            "columns": ["command", "lang", "source", "module", "from"], "rows": bins}
    return out
