#!/usr/bin/env python3
"""index_gen — 從各檔檔頭的一句話，替 repo 的資料夾生成 aos 的 index（東西多的夾一份 `_index.json`：`{名: {"description": …, "index": …}}`）。

  index_gen.py [--root REPO] [--apply] [--out DIR] [--stage N] [--config FILE] [--quiet]
    不帶 --apply：檢查。生成結果跟磁碟上的 `_index.json` 一致就退 0；不一致（缺、內容不同、多出不該有的）每份印一行 error、退 1。
    --apply      把生成結果寫進 repo（只寫範圍內的 `_index.json`；範圍內多出來、已不對應的生成份刪掉）。
    --out DIR    不碰 repo，把生成結果照同樣的相對路徑寫到 DIR（先在暫存夾看）。
    --stage N    只用設定檔裡 stage ≤ N 的範圍（預設全部）。
    --config FILE 改用另一份範圍設定（預設同夾的 index_gen.json；試新範圍時用）。
  某一項取不到一句話：印 `index_gen: error: DescMissing 路徑`、退 1（補檔頭，或寫進 index_gen_desc.json）。

範圍、不建的夾、手寫不生成的 index（hand_indexes，如 knowledge 既有的三份）寫在同夾的 index_gen.json；取不到檔頭一句話的（圖、紀錄檔、沒有 README 的夾）手寫在 index_gen_desc.json（路徑 → 一句話，手寫的優先）。
門檻：夾裡直接的東西（進版控的檔與子夾，`_index.json` 自己不算）超過設定檔的 more_than 個才放；不到的夾不放，上一層那一項也不帶 `index`
（使用者 11-13「index範圍按照11-12的門檻。」；11-12 的門檻＝超過 15 個，出處 proto8/knowledge/README.md、thinking/2026-11/12/knowledge-removal.md）。
列哪些：`git ls-files` 有的檔，與裡面有這種檔的夾；`_index.json` 自己不列。夾的那一項，在範圍內就帶 `index` 連到它自己的 `_index.json`。
一句話怎麼認：md 取第一個標題（分檔取導航行的「涵蓋：…」）；夾取它的 README.md／INDEX.md（工具夾取 _tooldef.json／_metainfo.json），沒有就取同名 `夾.md` 的（分檔夾）；
都沒有時用設定檔的通用句（usual_dirs／usual_files：tests、src、.gitignore 這類名字就說明用途的）；json 取 description／summary／$comment／title（knowledge 節點取 `_description` 那段的標題；`_description.json` 整份是一段正文、同樣取標題），
一段文字寫成字串或字串陣列（一行一個元素）都認（使用者 11-13，proto8/thinking/2026-11/13/text-as-string-array.md）：description 那幾個鍵是陣列時取第一行有字的；
夾沒有 README.md／INDEX.md 時取它的 `_description.json`；
wf-table 資料檔寫出處與欄位；程式檔照 codemap_lib 的認法；html 取 <title>。連結語法、粗體去掉，只留字。
同一次也寫逐檔 code map：proto8 每個頂層夾一份 wf/knowledge/code-map/proto8/<夾>.json（tree 巢狀、葉子＝檔頭一句話；範圍在 index_gen.json 的 codemap 段；
跟檔頭對不上＝CodemapStale、退 1；舊的 md 冊 11-13 刪了；
認法函式在 `codemap_lib.py`；規劃 proto8/thinking/2026-11/13/wf-into-aos-plan/08-fable-codemap規劃.md）。
格式出處：proto8/thinking/2026-11/12/index.md、index-link.md；規格與代定：proto8/thinking/2026-11/13/index-build.md。查對用 index_check.py。
純標準庫；只讀檔頭，不跑任何程式。
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import codemap_lib  # noqa: E402  共用檔頭一句話的認法

PROG = "index_gen"
NAME = "_index.json"
LIMIT = 200          # 一句話的長度上限（字）


def fail(code, msg):
    print(f"{PROG}: error: {code} {msg}", file=sys.stderr)


def tracked(root):
    out = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, check=True).stdout.decode()
    return sorted(p for p in out.split("\0") if p and os.path.lexists(os.path.join(root, p)))


def plain(s):
    """markdown 的一行 → 只留字。"""
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = s.replace("**", "").replace("__", "")
    s = " ".join(s.split())
    return s.strip(" ｜|←→・")


def cut(s):
    s = " ".join(s.split())
    return s if len(s) <= LIMIT else s[:LIMIT - 1] + "…"


def md_desc(text):
    lines = text.splitlines()[:40]
    for ln in lines[:6]:
        m = re.search(r"涵蓋(?:的段落?)?：(.+?)(?:｜|$)", ln)
        if m and ln.lstrip().startswith(("←", "[")):
            return "涵蓋：" + plain(m.group(1))
    fence = False
    for ln in lines:
        if ln.startswith("```"):
            fence = not fence
        if not fence and re.match(r"#{1,6}\s+\S", ln):
            return plain(ln.lstrip("#"))
    for ln in lines:                                    # 沒有標題：第一行有字的（封存註記、導航行、註解跳過）
        s = plain(ln.lstrip(">").strip())
        if s and not ln.lstrip().startswith(("←", "<!--", "---", "```", "|")):
            return s
    return ""


def lines(v):
    """一段文字：字串，或字串陣列（一行一個元素，用換行接起來）；其他形狀或接起來是空的＝""。同 proto8/lib/aos_index.py 的 text()。"""
    if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
        v = "\n".join(v)
    return v if isinstance(v, str) and v.strip() else ""


def json_desc(text, name):
    try:
        d = json.loads(text)
    except ValueError:
        return ""
    if name == "_description.json":                     # 資料夾自己的正文：整份是一段 md（字串或字串陣列），取它的標題
        return md_desc(lines(d))
    if isinstance(d, dict):
        for k in ("description", "summary", "$comment", "title"):
            if isinstance(d.get(k), str) and d[k].strip():
                return d[k]
            if isinstance(d.get(k), list) and lines(d[k]):          # 寫成字串陣列的檔頭：取第一行有字的
                return next(x for x in d[k] if x.strip())
        if lines(d.get("_description")):                # knowledge 的節點：_description 是一段 md（字串或字串陣列），取它的標題
            return md_desc(lines(d["_description"]))
        if str(d.get("contract", "")).startswith("wf-table/"):
            cols = "、".join(str(c) for c in d.get("columns", [])[:8])
            src = d.get("source")
            return "資料表（%s）：%s%d 列，欄位 %s" % (d["contract"], "抽自 %s，" % src if isinstance(src, str) and src else "",
                                                 len(d.get("rows", [])), cols)
    return ""


def file_desc(root, path):
    name = os.path.basename(path)
    full = os.path.join(root, path)
    if os.path.islink(full):
        return "捷徑 → " + os.readlink(full)
    try:
        with open(full, encoding="utf-8") as f:
            text = f.read(65536) if not name.endswith(".json") else f.read()
    except (OSError, UnicodeDecodeError):
        return ""
    if name.endswith(".md"):
        return md_desc(text)
    if name.endswith(".json"):
        return json_desc(text, name) or codemap_lib.clean(codemap_lib.json_desc(text, name == "_entry"), [name])
    if name.endswith((".html", ".htm")):
        m = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
        return plain(m.group(1)) if m else ""
    if name.endswith(".csv"):
        head = text.splitlines()[0] if text.strip() else ""
        return "資料表（csv）：欄位 " + "、".join(c.strip().strip('"') for c in head.split(",")[:8]) if head else ""
    if name.endswith((".txt", ".log", ".jsonl", ".err")):
        return ""
    stem = os.path.splitext(name)[0]
    return codemap_lib.clean(codemap_lib.text_desc(text, path), [name, stem])


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


def build(root, stage=None, config=None):
    """回 ({相對路徑/_index.json: 表}, [取不到一句話的路徑])。"""
    cfg, hand = load(config or "index_gen.json"), load("index_gen_desc.json")["desc"]
    scopes = [s for s in cfg["scopes"] if stage is None or s.get("stage", 1) <= stage]
    skip_names, skip_paths = set(cfg["skip_dir_names"]), set(cfg["skip_dirs"])
    keep = set(cfg.get("hand_indexes", []))
    more_than = cfg.get("more_than", 0)

    def skipped(d):                                     # 這個夾裡面不建、也不往下列
        return d in skip_paths or any(p in skip_names for p in d.split("/")) or any(d.startswith(s + "/") for s in skip_paths)

    def in_scope(d):
        if d != "." and skipped(d):
            return False
        for s in scopes:
            p = s["path"]
            if d == p or (s.get("deep") and (p == "." or d.startswith(p + "/"))):
                return True
        return False

    kids = {}                                           # 夾 → {子項名: 是不是夾}
    files = tracked(root)
    fileset = set(files)
    for p in files:
        parts = p.split("/")
        for i in range(len(parts)):
            d = "/".join(parts[:i]) or "."
            kids.setdefault(d, {})[parts[i]] = i < len(parts) - 1
    out, missing = {}, []

    def usual(table, path):                             # 到處都有、名字就說明用途的（tests、src、.gitignore…）：設定檔裡的通用句
        name = os.path.basename(path)
        up = os.path.basename(os.path.dirname(path)) or "repo 根"
        return table.get(name, "").replace("{parent}", up)

    def desc_of(path, is_dir):
        if path in hand:
            return hand[path]
        if not is_dir:
            return file_desc(root, path) or usual(cfg.get("usual_files", {}), path)
        for entry in ("README.md", "INDEX.md", "_tooldef.json", "_metainfo.json", "_description.json"):
            if entry in kids.get(path, {}):
                d = file_desc(root, path + "/" + entry)
                if d:
                    return d
        if path + ".md" in fileset:                     # x.md 拆出來的同名分檔夾
            d = file_desc(root, path + ".md")
            if d:
                return "分檔夾：" + d
        return usual(cfg.get("usual_dirs", {}), path)

    for d in sorted(kids):
        if not in_scope(d) or d in keep:                # keep：手寫的 index，不生成、不蓋掉（上一層照樣連過去）
            continue
        if len([n for n in kids[d] if n != NAME]) <= more_than:     # 門檻：夾裡的東西超過這個數才放（_index.json 自己不算）
            continue
        table = {}
        for name in sorted(kids[d]):
            if name == NAME:
                continue
            path = name if d == "." else d + "/" + name
            is_dir = kids[d][name]
            text = cut(desc_of(path, is_dir))
            if not text:
                missing.append(path + ("/" if is_dir else ""))
            item = {"description": text}
            if is_dir and in_scope(path):
                item["index"] = name + "/" + NAME
            table[name] = item
        if table:
            out[NAME if d == "." else d + "/" + NAME] = table
    for rel, table in out.items():                      # 子夾沒有 index（不到門檻）就不連
        base = os.path.dirname(rel)
        for name, item in table.items():
            if "index" in item and ((base + "/" if base else "") + item["index"]) not in out and ((base + "/" if base else "") + name) not in keep:
                del item["index"]
    gone = [p for p in hand if not os.path.lexists(os.path.join(root, p))]
    if gone:                                            # 被 .gitignore 的（如 wf/temp）在乾淨的複本裡本來就不在，不算缺
        ign = subprocess.run(["git", "-C", root, "check-ignore", "--no-index", "--stdin", "-z"], input="\0".join(gone + [p + "/" for p in gone]).encode(),
                             capture_output=True).stdout.decode().split("\0")
        for path in gone:
            if path not in ign and path + "/" not in ign:
                missing.append(path + "  (in index_gen_desc.json but not in the repo)")
    return out, missing, scopes, lambda d: in_scope(d) and d not in keep


def dump(table):
    return json.dumps(table, ensure_ascii=False, indent=1) + "\n"


GEN_BY = "wf/tools/index_gen.py"


def codemap_tables(root, cfg):
    """逐檔 code map：proto8 每個頂層夾一份 `<夾>.json`（頂層單檔進 proto8.json），回 ({檔名: 表}, 取不到一句話的列)。
    形狀（11-13 線遷 code map，proto8/thinking/2026-11/13/wf-into-aos-plan/08-fable-codemap規劃.md §1.2）：
    `tree` 照資料夾巢狀，字串＝檔、物件＝夾，值＝檔頭一句話（取不到＝""）；工具夾三個契約檔併成一格 `名/`；
    有 CMake 專案的夾多一個 `deps`＝{專案: {public, private}}。掃描範圍與認法照 codemap_lib（同一份設定、同一次掃描）。"""
    proto = os.path.join(root, "proto8")
    if not os.path.isdir(proto):
        return {}, []
    groups = {}
    for f in codemap_lib.tracked(proto):
        groups.setdefault(f.split("/")[0] if "/" in f else "", []).append(f)
    out, warns = {}, []
    for top in sorted(groups):
        tree = {}
        for rel, cov in codemap_lib.units(proto, groups[top]):
            d, bad = codemap_lib.unit_desc(proto, rel, cov)
            if bad:
                warns.append(rel)
            parts = (rel[len(top) + 1:] if top else rel).rstrip("/").split("/")
            node = tree
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1] + ("/" if rel.endswith("/") else "")] = d.replace("\\|", "|")
        what = "proto8/" + top if top else "proto8 頂層單檔"
        table = {"description": f"{what} 逐檔表（生成物，別手改）：tree 照資料夾巢狀，字串＝檔、物件＝夾，值＝那個檔檔頭的一句話；"
                                "工具夾的 _entry／_tooldef.json／_metainfo.json 併成一格「名/」。要改說明去改檔頭，再跑 "
                                "python3 wf/tools/index_gen.py --apply。",
                 "generated_by": GEN_BY, "tree": tree}
        dep = codemap_lib.deps(proto, top, groups[top]) if top else []
        if dep:
            table["description"] += "deps＝各專案 CMakeLists.txt 的 target_link_libraries（略過 *_main）。"
            table["deps"] = {p: {"public": pub, "private": priv} for p, pub, priv in dep}
        out[(top or "proto8") + ".json"] = table
    return out, warns


def codemap_dump(table):
    return json.dumps(table, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def codemap_sync(root, cfg, apply, out_dir):
    """寫／查逐檔表 json；回 stale 數（--apply 或 --out 時恆 0）。"""
    rel_dir = (cfg.get("codemap") or load("index_gen.json")["codemap"])["out"]   # --config 試範圍的那份沒有 codemap 段：用預設那份
    want, warns = codemap_tables(root, cfg)
    want = {n: codemap_dump(t) for n, t in want.items()}
    if out_dir:
        dst = os.path.join(out_dir, rel_dir)
        os.makedirs(dst, exist_ok=True)
        for n, text in want.items():
            with open(os.path.join(dst, n), "w", encoding="utf-8") as f:
                f.write(text)
        return 0, len(want), len(warns)
    outdir = os.path.join(root, rel_dir)
    have = {}
    if os.path.isdir(outdir):
        for n in sorted(os.listdir(outdir)):
            p = os.path.join(outdir, n)
            if n.endswith(".json") and os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    t = f.read()
                if '"generated_by": "%s"' % GEN_BY in t:      # 只管自己生成的；手寫的不碰
                    have[n] = t
    diff = sorted(n for n in want if have.get(n) != want[n])
    stale = sorted(n for n in have if n not in want)
    if apply:
        os.makedirs(outdir, exist_ok=True)
        for n in diff:
            tmp = os.path.join(outdir, n + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(want[n])
            os.replace(tmp, os.path.join(outdir, n))
        for n in stale:
            os.remove(os.path.join(outdir, n))
        return 0, len(want), len(warns)
    for n in diff:
        fail("CodemapStale", "%s/%s %s (run index_gen.py --apply)" % (rel_dir, n, "is missing" if n not in have else "differs from the file headers"))
    for n in stale:
        fail("CodemapStale", "%s/%s no longer generated (run index_gen.py --apply)" % (rel_dir, n))
    return len(diff) + len(stale), len(want), len(warns)


def main(argv):
    root, apply, out_dir, stage, quiet, config = os.path.dirname(os.path.dirname(HERE)), False, None, None, False, None
    it = iter(argv)
    for a in it:
        if a == "--apply":
            apply = True
        elif a == "--quiet":
            quiet = True
        elif a in ("--root", "--out", "--stage", "--config"):
            v = next(it, None)
            if v is None:
                fail("ArgumentsBad", f"{a} needs a value (usage: index_gen.py [--root REPO] [--apply] [--out DIR] [--stage N] [--config FILE] [--quiet])")
                return 1
            if a == "--root":
                root = v
            elif a == "--out":
                out_dir = v
            elif a == "--config":
                config = os.path.abspath(v)
            else:
                stage = int(v)
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            fail("FlagUnknown", f"{a} (usage: index_gen.py [--root REPO] [--apply] [--out DIR] [--stage N] [--config FILE] [--quiet])")
            return 1
    tables, missing, scopes, in_scope = build(root, stage, config)
    for m in missing:
        fail("DescMissing", m)
    bad = 0
    old = [p for p in tracked(root) if os.path.basename(p) == NAME and in_scope(os.path.dirname(p) or ".") and p not in tables]
    if out_dir:
        for rel, table in tables.items():
            dst = os.path.join(out_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "w", encoding="utf-8") as f:
                f.write(dump(table))
    else:
        for rel, table in tables.items():
            dst, new = os.path.join(root, rel), dump(table)
            try:
                with open(dst, encoding="utf-8") as f:
                    cur = f.read()
            except OSError:
                cur = None
            if cur == new:
                continue
            if apply:
                with open(dst, "w", encoding="utf-8") as f:
                    f.write(new)
            else:
                bad += 1
                fail("IndexStale", "%s %s (run index_gen.py --apply)" % (rel, "is missing" if cur is None else "differs from the file headers"))
        for rel in old:
            if apply:
                os.remove(os.path.join(root, rel))
            else:
                bad += 1
                fail("IndexStale", "%s no longer matches any folder with entries (run index_gen.py --apply)" % rel)
    cstale, cbooks, cwarn = codemap_sync(root, load(config or "index_gen.json"), apply, out_dir)
    bad += cstale
    if not quiet:
        print("%s: %d index files, %d entries, %d without a description%s" % (
            PROG, len(tables), sum(len(t) for t in tables.values()), len(missing),
            "" if not out_dir else ", written under " + out_dir))
        print("%s: code map %d books, %d stale, %d units without a one-line header" % (PROG, cbooks, cstale, cwarn))
    return 1 if bad or missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
