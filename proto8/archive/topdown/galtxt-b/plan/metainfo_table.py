#!/usr/bin/env python3
# metainfo_table - 盤點 galtxt-b 整棵樹的 _metainfo，輸出一張表（JSON 給機器、markdown 給人）；--measure 把實跑的 measure.json 並到對應列旁
# 用法：python3 plan/metainfo_table.py [--root 樹根] [--out 輸出資料夾] [--measure out/<題名>/measure.json ...]
#   樹根預設＝本檔的上一層（galtxt-b/）、輸出預設＝本檔所在的 plan/（metainfo_table.json、metainfo_table.md）。純標準庫。
# 收哪些：每個資料夾的 _metainfo／_metainfo.json（兩個都在＝_metainfo 贏，照 10-24 metainfo 01 §1）、每份 *.json 裡任何一層帶 _metainfo 的物件
#   （fsm.json 的單子，路徑寫成 檔#/指標）、沒 +x 的 JSON `_entry` 單子（round3 起 director／critic 是這種；`_metainfo` 寫 {"$ref": …} 就照指的讀）、
#   捷徑（不跟進去，列一行指到哪）。plan/ 與 . 開頭的跳過（盤點工具與量測不是樹的一部分）。
# --measure：measure.json（deliver 寫的，一題一份）照 MEASURE_MAP 對到列：time_ms ← elapsed_ms、llm_calls ← counter_llm_calls、llm_tokens ← counter_tokens；
#   think 單子對「每次問腦」的平均。對不上的列空著。實測超過宣告的 max 記進 over_max；markdown 尾巴列「宣告 val 跟實測差最多」的幾列。
# 錯：stderr 一行「metainfo_table: 代號 原因」退 1——ArgumentsBad、RootMissing、MeasureBad。讀不懂的 _metainfo 不算錯，列成一行 bad。
import argparse, json, math, os, sys

NAME = "metainfo_table"
HERE = os.path.dirname(os.path.abspath(__file__))
STD = ["summary", "kind", "resource", "time_ms", "llm_calls", "llm_tokens", "deterministic", "side_effect", "interrupt", "parallel"]
NUMS = ["time_ms", "llm_calls", "llm_tokens"]
# measure.json 的哪一塊 → 哪一列（相對樹根的路徑）；值是 (列, 取數函數)
AGENTS = {"director": "draft/tools/director", "writer": "draft/tools/writer", "critic": "judge/tools/critic"}


def die(code, reason):
    print("%s: %s %s" % (NAME, code, reason), file=sys.stderr)
    sys.exit(1)


def num(x):
    """數量的雙形 → (val, max)；寫數字＝典型值、沒有 max。"""
    if isinstance(x, dict):
        return x.get("val"), x.get("max")
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return x, None
    return None, None


def row(path, kind, meta, source):
    r = {"path": path, "source": source, "kind": kind}
    if not isinstance(meta, dict):
        r.update(kind="bad", summary="_metainfo 不是 JSON 物件")
        return r
    r["kind"] = meta.get("kind") or kind
    for k in STD:
        if k != "kind" and k in meta:
            r[k] = meta[k]
    r["other"] = {k: v for k, v in meta.items() if k not in STD}
    return r


def embedded(value, pointer, out):
    """JSON 裡任何一層帶 _metainfo 的物件（單子、當資料夾的 JSON 物件）。"""
    if isinstance(value, dict):
        if "_metainfo" in value:
            out.append((pointer, value["_metainfo"]))
        for k, v in value.items():
            if k != "_metainfo":
                embedded(v, pointer + "/" + k.replace("~", "~0").replace("/", "~1"), out)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            embedded(v, "%s/%d" % (pointer, i), out)


def resolve_ref(meta, base):
    """單子裡 `_metainfo` 寫 {"$ref": "檔#/指標"}（M 01 §5）＝照指的讀；檔名從單子所在的資料夾算。讀不了就原樣回（列成 bad）。"""
    if not (isinstance(meta, dict) and set(meta) == {"$ref"} and isinstance(meta["$ref"], str)):
        return meta, None
    name, _, ptr = meta["$ref"].partition("#")
    try:
        with open(os.path.join(base, name), encoding="utf-8") as f:
            v = json.load(f)
        for k in [x.replace("~1", "/").replace("~0", "~") for x in ptr.split("/")[1:]]:
            v = v[int(k)] if isinstance(v, list) else v[k]
        return v, name
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None, name


def entry_single(path):
    """沒 +x 的 `_entry` 讀成 JSON（第一行 #! 跳過，同 aos-exec）；是帶 argv 的單子就回它，不是回 None。"""
    if os.access(path, os.X_OK):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if text.startswith("#!"):
            text = text.split("\n", 1)[1] if "\n" in text else ""
        v = json.loads(text)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return v if isinstance(v, dict) and "argv" in v else None


def walk(root):
    rows = []
    for d, dirs, files in os.walk(root):
        rel = os.path.relpath(d, root)
        dirs[:] = sorted(x for x in dirs if not x.startswith(".") and not (rel == "." and x == "plan"))
        for x in list(dirs):                      # 捷徑：列一行、不跟進去（os.walk 預設不跟，這裡把它挑出來）
            if os.path.islink(os.path.join(d, x)):
                dirs.remove(x)
                p = os.path.normpath(os.path.join(rel, x))
                rows.append({"path": p, "source": p, "kind": "link",
                             "summary": "捷徑 → %s" % os.readlink(os.path.join(d, x)), "other": {}})
        meta_file = next((n for n in ("_metainfo", "_metainfo.json") if n in files), None)
        kind = "fn" if "_entry" in files else "dir"
        if meta_file:
            try:
                with open(os.path.join(d, meta_file), encoding="utf-8") as f:
                    meta = json.load(f)
            except (OSError, ValueError) as e:
                meta = None
                rows.append({"path": rel, "source": os.path.join(rel, meta_file), "kind": "bad", "summary": "讀不了：%s" % e, "other": {}})
            if meta is not None:
                rows.append(row(rel, kind, meta, os.path.normpath(os.path.join(rel, meta_file))))
        else:
            rows.append({"path": rel, "source": "", "kind": kind, "summary": "（沒有 _metainfo）", "other": {}})
        single = entry_single(os.path.join(d, "_entry")) if "_entry" in files else None
        if single is not None and "_metainfo" in single:
            meta, ref = resolve_ref(single["_metainfo"], d)
            p = os.path.normpath(os.path.join(rel, "_entry"))
            rows.append(row(p, "單子", meta, os.path.normpath(os.path.join(rel, ref)) if ref else p))
        for n in sorted(files):
            if not n.endswith(".json") or n.startswith(".") or n == "_metainfo.json":
                continue
            try:
                with open(os.path.join(d, n), encoding="utf-8") as f:
                    value = json.load(f)
            except (OSError, ValueError):
                continue
            found = []
            embedded(value, "", found)
            for pointer, meta in found:
                p = "%s#%s" % (os.path.normpath(os.path.join(rel, n)), pointer)
                rows.append(row(p, "單子", meta, p))
    return rows


def measured_values(m):
    """一份 measure.json → {列的路徑: {time_ms, llm_calls, llm_tokens}}。"""
    out = {".": {"time_ms": m.get("elapsed_ms"), "llm_calls": m.get("counter_llm_calls"), "llm_tokens": m.get("counter_tokens")}}
    agents = m.get("agents") or {}
    for cell, c in (m.get("cells") or {}).items():
        out[cell] = {"time_ms": c.get("elapsed_ms")}
    for who, path in AGENTS.items():
        a = agents.get(who)
        if not a:
            continue
        out[path] = {"time_ms": a.get("elapsed_ms"), "llm_calls": a.get("counter_llm_calls"), "llm_tokens": a.get("counter_tokens")}
        calls = a.get("counter_llm_calls") or 0
        if calls:                                 # think 單子（round3 起單發的是 _entry 單子）是「問腦一次」：拿平均對
            per = {"time_ms": round(a.get("llm_elapsed_ms", 0) / calls), "llm_calls": 1, "llm_tokens": round(a.get("counter_tokens", 0) / calls)}
            out[path + "/fsm.json#/states/think/exec"] = per
            out[path + "/_entry"] = dict(per)
    for cell, whos in (("draft", ("director", "writer")), ("judge", ("critic",))):
        if cell in out and all(w in agents for w in whos):
            out[cell]["llm_calls"] = sum(agents[w].get("counter_llm_calls", 0) for w in whos)
            out[cell]["llm_tokens"] = sum(agents[w].get("counter_tokens", 0) for w in whos)
    return out


def fmt_num(x):
    v, mx = num(x)
    if v is None and mx is None:
        return ""
    return "%s/%s" % ("" if v is None else v, "" if mx is None else mx) if mx is not None else str(v)


def cell(s, width=None):
    s = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False)
    s = s.replace("|", "\\|").replace("\n", " ")
    return s[:width] + "…" if width and len(s) > width else s


def main():
    ap = argparse.ArgumentParser(prog=NAME, add_help=True)
    ap.add_argument("--root", default=os.path.dirname(HERE))
    ap.add_argument("--out", default=HERE)
    ap.add_argument("--measure", nargs="*", default=[])
    try:
        a = ap.parse_args()
    except SystemExit as e:
        if e.code:
            die("ArgumentsBad", "參數不對（見 --help）")
        raise
    if not os.path.isdir(a.root):
        die("RootMissing", "%s 不是資料夾" % a.root)
    rows = walk(a.root)
    labels = []
    for path in a.measure:
        try:
            with open(path, encoding="utf-8") as f:
                m = json.load(f)
            if not isinstance(m, dict):
                raise ValueError("不是物件")
        except (OSError, ValueError) as e:
            die("MeasureBad", "%s 讀不了：%s" % (path, e))
        label = m.get("name") or os.path.basename(os.path.dirname(os.path.abspath(path)))
        labels.append(label)
        vals = measured_values(m)
        for r in rows:
            got = {k: v for k, v in (vals.get(r["path"]) or {}).items() if v is not None}
            if got:
                r.setdefault("measured", {})[label] = got
                for k, v in got.items():
                    _, mx = num(r.get(k))
                    if mx is not None and v > mx:
                        r.setdefault("over_max", []).append("%s %s %s>%s" % (label, k, v, mx))
    # 差最多：實測／宣告 val 的倍數，取 log 的絕對值排
    gaps = []
    for r in rows:
        for label, got in (r.get("measured") or {}).items():
            for k, v in got.items():
                val, _ = num(r.get(k))
                if val and v:
                    gaps.append((abs(math.log(v / val)), r["path"], label, k, val, v))
    gaps.sort(reverse=True)

    os.makedirs(a.out, exist_ok=True)
    doc = {"root": os.path.relpath(a.root, a.out), "measures": labels, "counter_rows": len(rows), "rows": rows,
           "gaps": [{"path": p, "measure": lab, "key": k, "val": val, "measured": v, "ratio": round(v / val, 3)}
                    for _, p, lab, k, val, v in gaps[:15]]}
    with open(os.path.join(a.out, ".metainfo_table.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    os.replace(os.path.join(a.out, ".metainfo_table.json"), os.path.join(a.out, "metainfo_table.json"))

    def meas(r, k):
        return " ".join("%s:%s" % (lab.split("_")[0], got[k]) for lab, got in (r.get("measured") or {}).items() if k in got)

    head = ["路徑", "kind", "summary", "resource", "time_ms", "llm_calls", "llm_tokens"]
    if labels:
        head[5:5] = ["實測 time_ms"]
        head[7:7] = ["實測 llm_calls"]
        head.append("實測 llm_tokens")
    head += ["det", "side", "interrupt", "parallel", "其他 key"] + (["超過 max"] if labels else [])
    lines = ["# galtxt-b `_metainfo` 表", "",
             "由 `plan/metainfo_table.py` 產生（不要手改）。數量欄寫 `val/max`；實測欄 `題:值`（%s）。" % ("、".join(labels) or "沒給 --measure"),
             "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        res = r.get("resource")
        c = [cell(r["path"]), r.get("kind", ""), cell(r.get("summary", ""), 50), cell("、".join(res) if isinstance(res, list) else (res or "")),
             fmt_num(r.get("time_ms"))]
        if labels:
            c.append(meas(r, "time_ms"))
        c.append(fmt_num(r.get("llm_calls")))
        if labels:
            c.append(meas(r, "llm_calls"))
        c.append(fmt_num(r.get("llm_tokens")))
        if labels:
            c.append(meas(r, "llm_tokens"))
        c += ["" if r.get(k) is None else cell(r[k]) for k in ("deterministic", "side_effect", "interrupt", "parallel")]
        c.append(cell("、".join(sorted(r.get("other") or {})), 60))
        if labels:
            c.append(cell("；".join(r.get("over_max", []))))
        lines.append("| " + " | ".join(c) + " |")
    if gaps:
        lines += ["", "## 宣告 val 跟實測差最多的幾列", "", "| 路徑 | 題 | key | 宣告 val | 實測 | 倍數 |", "|---|---|---|---|---|---|"]
        lines += ["| %s | %s | %s | %s | %s | %.2f |" % (cell(p), lab, k, val, v, v / val) for _, p, lab, k, val, v in gaps[:15]]
    with open(os.path.join(a.out, ".metainfo_table.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(os.path.join(a.out, ".metainfo_table.md"), os.path.join(a.out, "metainfo_table.md"))
    print(json.dumps({"counter_rows": len(rows), "out": os.path.abspath(a.out)}, ensure_ascii=False))


main()
