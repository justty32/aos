# suggest.py - metatable --suggest 的規則：套 plan/round2-collapse.md § 1 的判準，列出收攏候選（只列、不做）
"""每個真資料夾（不跟捷徑、跳過 . 開頭）看 _metainfo＋掃資料夾，先看「不縮」再看「併／縮」：

N-1 fs_needs 有 BLOCK 裡的（或有 _tooldef.json；mount 只在 agent／有 _tooldef.json 時擋，其餘標「要人判」）；kind 不是 data 卻有 git_tracked 也擋
N-2 伴隨檔（_entry、_metainfo 以外的檔）≥ 2——只數檔，不看 grow_level（grow_level 4 可能只是因為底下有 tools/）
N-3 callers ≥ 2 而且入口是腳本（同內容葉片先合計 callers：真身＝最淺那份）
A-1 沒有 _metainfo、沒有 _entry、只有一個子資料夾 → unwrap；例外：叫 tools/ 而且那個子資料夾有 _tooldef.json
B-4 同內容葉片（整個資料夾的檔名＋內容＋+x 一樣）→ 真身以外換捷徑
B-3 kind=data、fs_needs ⊆ {git_tracked}、沒有子資料夾、全是 JSON、合計 < 8 KB 且 < 300 行、讀者恰好一個 → table
B-2 _entry 是 +x 腳本、沒有伴隨檔、callers 1、呼叫方是 fsm.json／loop.json 的一格 → inline（kind=glue 多標 A-2）
N-4 有旁檔（ratings／stage／grad／rollup／human.json，round4 § 3.5）：照上面的規則本來是候選的，判準欄改「N-4（原 X）」、動作改「不縮」——
    數字算在這棵頭上；人硬要縮先把 val／stage／grad_total 寫進上一層 rollup.json.children[<名>]（collapsed_from）、刪旁檔、再 collapse
B-1 _entry 是單子（沒 +x）、沒有伴隨檔、fs_needs 空 → callers 1 內嵌、≥ 2 寫成 x.json

讀者：所有 _metainfo（含內嵌單子的）的 reads 裡「<根下資料夾名>:<路徑>」指到這個資料夾裡的，就算一個讀者。
呼叫方：所有 fsm.json／loop.json 裡 exec 是 "X" 或 ["aos-exec", "X", …] 的格，X 從那份檔的資料夾算、解開捷徑。"""
import hashlib, json, os

SIDECARS = ("ratings.json", "stage.json", "grad.json", "rollup.json", "human.json")
BLOCK = {"own_stack", "tool_json", "isolation", "lock", "shared_write", "permission", "large", "binary"}


def load(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def real_dirs(root):
    for here, subs, files in os.walk(root, followlinks=False):
        links = sorted(s for s in subs if os.path.islink(os.path.join(here, s)))
        subs[:] = sorted(s for s in subs if s not in links and not s.startswith("."))
        yield here, list(subs), sorted(f for f in files if not os.path.islink(os.path.join(here, f))), links


def inline_metas(doc, out):
    if isinstance(doc, dict):
        if "argv" in doc and isinstance(doc.get("_metainfo"), dict):
            out.append(doc["_metainfo"])
        for v in doc.values():
            inline_metas(v, out)
    elif isinstance(doc, list):
        for v in doc:
            inline_metas(v, out)


def cells(doc, ptr, out):
    """(指標, exec 值)：fsm 格的 exec、loop.json 的 exec"""
    if isinstance(doc, dict):
        for k, v in doc.items():
            p = ptr + "/" + k.replace("~", "~0").replace("/", "~1")
            if k == "exec":
                out.append((p, v))
            else:
                cells(v, p, out)


def target_of(v):
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and isinstance(v.get("argv"), list) and len(v["argv"]) >= 2 and v["argv"][0] == "aos-exec":
        rest = [a for a in v["argv"][1:] if isinstance(a, str) and not a.startswith("-")]
        return rest[0] if rest else None
    return None


def digest(d):
    h = hashlib.sha256()
    for here, subs, files in os.walk(d):
        subs.sort()
        for f in sorted(files):
            p = os.path.join(here, f)
            h.update(os.path.relpath(p, d).encode() + b"\0" + (b"x" if os.access(p, os.X_OK) else b"-"))
            if os.path.islink(p):
                h.update(b"L" + os.readlink(p).encode())
            else:
                with open(p, "rb") as fh:
                    h.update(fh.read())
    return h.hexdigest()


def suggest(root, nodes=None):
    root = os.path.abspath(root)
    rel = lambda p: os.path.relpath(p, root)     # noqa: E731
    dirs, metas, callers, links = [], [], {}, []
    for here, subs, files, lk in real_dirs(root):
        meta = load(os.path.join(here, "_metainfo")) if "_metainfo" in files else None
        dirs.append((here, subs, files, lk, meta))
        if isinstance(meta, dict):
            metas.append((rel(here), meta))
        for n in lk:
            links.append((os.path.join(here, n), os.path.realpath(os.path.join(here, n))))
        for f in ("fsm.json", "loop.json"):
            if f in files:
                doc = load(os.path.join(here, f))
                found = []
                inline_metas(doc, found)
                metas += [(rel(os.path.join(here, f)), m) for m in found]
                cs = []
                cells(doc, "", cs)
                for ptr, v in cs:
                    t = target_of(v)
                    if t:
                        callers.setdefault(os.path.realpath(os.path.join(here, t)), []).append(
                            "%s#%s" % (rel(os.path.join(here, f)), ptr))
    # B-4：同內容葉片
    groups = {}
    for here, subs, files, lk, meta in dirs:
        if "_entry" in files and here != root:
            groups.setdefault(digest(here), []).append(here)
    real_of, copies = {}, {}
    for g in groups.values():
        if len(g) >= 2:
            g.sort(key=lambda p: (rel(p).count(os.sep), p))
            for c in g[1:]:
                copies[c] = g[0]
            real_of[g[0]] = g
    rows = []

    def row(path, rule, action, why, who):
        side = [f for f in SIDECARS if os.path.isfile(os.path.join(path, f))]
        if side:                                                            # N-4：有旁檔的不縮（只標、不拿掉這行）
            rule, action, why = "N-4（原 %s）" % rule, "不縮", "有旁檔 %s；%s" % ("、".join(side), why)
        rows.append({"path": rel(path), "rule": rule, "action": action, "why": why, "callers": who})

    for here, subs, files, lk, meta in dirs:
        if here == root:
            continue
        name = os.path.basename(here)
        extra = [f for f in files if f not in ("_entry", "_metainfo")]
        if meta is None:
            if "_entry" in files or extra or lk or len(subs) != 1:
                continue
            if name == "tools" and os.path.isfile(os.path.join(here, subs[0], "_tooldef.json")):
                continue                                                    # A-1 例外（P-41）
            into = [rel(a) for a, t in links if t == os.path.join(here, subs[0]) or t.startswith(here + os.sep)]
            row(here, "A-1", "collapse unwrap %s（%s 上提一層）" % (rel(here), subs[0]),
                "沒有 _metainfo、沒有 _entry，只裝一個子資料夾", into or ["—"])
            continue
        if not isinstance(meta, dict):
            continue
        kind = meta.get("kind")
        fs = set(meta.get("fs_needs") or []) if isinstance(meta.get("fs_needs"), list) else set()
        block = fs & BLOCK
        if "_tooldef.json" in files:
            block.add("tool_json")
        if "git_tracked" in fs and kind != "data":
            block.add("git_tracked")
        notes = []
        if "mount" in fs:
            if kind == "agent" or "_tooldef.json" in files:
                block.add("mount")
            else:
                notes.append("要人判：fs_needs 有 mount（是掛別人還是被掛？）")
        if block:
            continue                                                        # N-1
        if here in copies:
            r = copies[here]
            row(here, "B-4", "換捷徑 → %s（collapse dedupe %s %s）" % (os.path.relpath(r, os.path.dirname(here)), rel(r), rel(here)),
                "跟 %s 內容一模一樣" % rel(r), callers.get(os.path.realpath(here), ["—"]))
            continue
        if kind != "data" and len(extra) >= 2:
            continue                                                        # N-2
        c = meta.get("callers") if isinstance(meta.get("callers"), int) else len(callers.get(os.path.realpath(here), []))
        if here in real_of:
            c = sum(m.get("callers", 0) if isinstance(m, dict) and isinstance(m.get("callers"), int) else 0
                    for m in (load(os.path.join(p, "_metainfo")) for p in real_of[here]))
        is_x = "_entry" in files and os.access(os.path.join(here, "_entry"), os.X_OK)
        if c >= 2 and is_x:
            continue                                                        # N-3
        if kind == "data":
            if subs or lk or not extra or not all(f.endswith(".json") for f in extra) or fs - {"git_tracked"}:
                continue
            size = lines = 0
            for f in extra:
                with open(os.path.join(here, f), "rb") as fh:
                    b = fh.read()
                size, lines = size + len(b), lines + b.count(b"\n")
            if size >= 8192 or lines >= 300:
                continue
            readers = []
            for path, m in metas:
                for r in m.get("reads") or []:
                    if isinstance(r, str) and ":" in r:
                        top, rest = r.split(":", 1)
                        p = os.path.normpath(os.path.join(root, top, rest.split("（")[0]))
                        if os.path.isdir(os.path.join(root, top)) and (p == here or p.startswith(here + os.sep)) \
                                and path not in readers:
                            readers.append(path)
            if len(readers) == 1:
                row(here, "B-3", "collapse table %s（→ %s.json）" % (rel(here), rel(here)),
                    "%d 個小 JSON、合計 %d bytes／%d 行、讀者只有一個" % (len(extra), size, lines), readers)
            continue
        if extra:
            continue                                                        # 有一個伴隨檔＝第 4 級，不在 B-1／B-2 範圍
        who = callers.get(os.path.realpath(here), [])
        if is_x and c == 1:
            if len(who) == 1:
                if kind == "glue":
                    notes.append("A-2：黏合格，叫的 agent 之後搬到它原來的位置")
                if subs:
                    notes.append("底下還有 %s，inline 之後用 unwrap 收" % "、".join(s + "/" for s in subs))
                row(here, "B-2", "collapse inline %s（→ %s.py／.sh＋內嵌單子）" % (who[0], name),
                    "；".join(["+x 腳本、沒有伴隨檔、callers 1"] + notes), who)
            else:
                row(here, "B-2（要人判）", "找呼叫方", "+x 腳本、callers 1，但 fsm.json／loop.json 裡找到 %d 處叫它" % len(who), who or ["—"])
        elif "_entry" in files and not is_x and not subs and not fs:
            row(here, "B-1", "縮成內嵌單子（_metainfo 進單子）" if c <= 1 else "縮成 %s.json" % name,
                "_entry 是單子、沒有伴隨檔、fs_needs 空", who or ["—"])
    rows.sort(key=lambda r: r["path"])
    return rows


def render_md(rows):
    out = ["## 收攏候選（metatable --suggest；判準 plan/round2-collapse.md § 1）", "",
           "| path | 判準 | 動作 | 理由 | 要改的呼叫方 |", "|---|---|---|---|---|"]
    for r in rows:
        out.append("| %s |" % " | ".join(str(x).replace("|", "\\|") for x in
                                         (r["path"], r["rule"], r["action"], r["why"], "、".join(r["callers"]))))
    if not rows:
        out.append("| （無） | | | | |")
    out.append("")
    out.append("候選 %d 個" % len(rows))
    return "\n".join(out)
