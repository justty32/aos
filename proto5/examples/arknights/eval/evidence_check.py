#!/usr/bin/env python3
"""證據表格逐列核對原文（arknights 專案最核心、原本沒程式管的品質點）。

用法：
    python evidence_check.py <副本路徑> <角色名…>             # 看副本裡該角色的證據檔
    python evidence_check.py <副本路徑> --golden [批號…]      # 看 golden/ 底下的標準答案
    python evidence_check.py <副本路徑> --files a.md b.md     # 直接指定證據檔
    加 --summary 只印統計＋不過的列；預設印整份 JSON。離開碼 0＝全部 ok。

<副本路徑> 是 arknights 的工作樹（要有 corpus/raw 與 corpus/extracted）。

比對規則（寫死、不猜）：
1. 只看 markdown 表格列（以 | 開頭），跳過分隔列。
2. 行號：`L數字` 或 `L數字-數字`／`L數字-L數字`；緊跟在後、用「, ，、」隔開的「數字-數字」也算同一串。
   一列沒有任何行號就不檢查（skip）。
3. 檔名：列中 `xxx.txt`／`.md`／`.json`／`.tsv` 的 token（可帶路徑前綴）。markdown 連結 `](x.md)` 裡的不算。
   只有「在原文庫找得到」或「後面緊跟行號」的檔名才算出處；找不到又沒跟行號的（例如「另建檔`W.md`」）忽略。
4. 配對：每段行號配「它前面最近的出處檔名」；本列前面沒有就沿用同一證據檔上一列最後的出處（「同檔 L..」）。
5. 找檔：在 corpus/extracted 與 corpus/raw/ArknightsGameData/zh_CN/gamedata 底下按檔名找（帶前綴時比對路徑結尾）；
   同名多份時任一份過就算過。
6. 超界：某段的起 > 訖，或訖 > 檔案總行數（所有同名候選都超才算）。
7. 引文：第 2 格之後（第 1 格是節點名）「」『』“”包住的字句。兩邊都
   (a) 引文用 opencc tw2s 轉簡體（吃掉簡繁與台灣異體字差異）；原文本來就是 zh_CN 簡體，不轉
       （轉了反而會把「什么」弄成「什幺」）。兩邊再過一張小異體表 FOLD（帐→账 等）。
   (b) 只留中日韓字與英數字（標點、空白、省略號拿掉；原文的 [name="…"] 標記也只剩字，所以 speaker 名可以比到），
   再看引文是否出現在「本列所有 檔名＋行號 範圍」合起來的原文裡（每段範圍各自串接、段與段不相連）。
   引文中有「……」「…」「...」「／」時切段，每段都要找到。處理後少於 2 個字的段不檢查。
   找不到時：範圍內有一段連續相同的字 ≥ 引文段長的 60% 且 ≥ 4 字＝「引文近似」（作者改了一兩個字、加了主詞）；
   否則看本列那幾個檔的全文：有＝「引文在範圍外」，沒有＝「引文找不到」。
   檔名比對時忽略引號種類（證據常把 “还魂” 寫成 "还魂"）。
狀態：ok／引文近似／skip（無行號）／無檔名／檔不存在／超界／引文在範圍外／引文找不到。
嚴格過＝ok；寬鬆過＝ok＋引文近似。
「引文找不到」不一定是錯：作者常在「」裡放自己的概括或詞條用的稱呼。它是「值得人看一眼」，不是「一定錯」。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW_SUB = Path("corpus/raw/ArknightsGameData/zh_CN/gamedata")

FILE_PAT = r"[^\s|`；;，,、（）()「」『』：:<>*]+?\.(?:txt|md|json|tsv)"
RANGE_PAT = r"L(\d+)(?:\s*[-–~～]\s*L?(\d+))?((?:\s*[,，、]\s*L?\d+(?:\s*[-–~～]\s*L?\d+)?)*)"
TOKEN_RE = re.compile(rf"(?P<link>\]\([^)]*\))|(?P<file>{FILE_PAT})|(?P<range>{RANGE_PAT})")
MORE_RE = re.compile(r"L?(\d+)(?:\s*[-–~～]\s*L?(\d+))?")
QUOTE_RE = re.compile(r"「([^「」]+)」|『([^『』]+)』|“([^“”]+)”")
KEEP_RE = re.compile(r"[^0-9A-Za-z一-鿿㐀-䶿]")
SPLIT_RE = re.compile(r"……|\.\.\.|…|／")
FOLD = str.maketrans({"帐": "账", "幺": "么", "着": "著"})
NAME_FOLD = str.maketrans({c: "" for c in "\"'“”‘’「」"})


def opencc_many(texts: list[str], config: str = "tw2s") -> list[str]:
    """一次呼叫 opencc 轉多段文字（段內換行先換成空白）。"""
    if not texts:
        return []
    joined = "\n".join(t.replace("\n", " ") for t in texts)
    out = subprocess.run(["opencc", "-c", config], input=joined,
                         capture_output=True, text=True, check=True).stdout
    parts = out.split("\n")
    if len(parts) == len(texts) + 1 and parts[-1] == "":
        parts = parts[:-1]
    if len(parts) != len(texts):
        return [subprocess.run(["opencc", "-c", config], input=t, capture_output=True,
                               text=True, check=True).stdout for t in texts]
    return parts


def norm(s: str) -> str:
    return KEEP_RE.sub("", s).lower().translate(FOLD)


class Corpus:
    def __init__(self, copy_root: Path):
        self.root = copy_root
        self.index: dict[str, list[Path]] = {}
        for base in (copy_root / "corpus/extracted", copy_root / RAW_SUB):
            if not base.exists():
                continue
            for dirpath, dirnames, filenames in os.walk(base, followlinks=True):
                dirnames[:] = [d for d in dirnames if d != ".git"]
                for fn in filenames:
                    self.index.setdefault(fn.translate(NAME_FOLD), []).append(Path(dirpath) / fn)
        self._lines: dict[Path, list[str]] = {}
        self._norm: dict[Path, list[str]] = {}

    def find(self, name: str) -> list[Path]:
        name = name.strip("`'\" ")
        base = re.split(r"[/／]", name)[-1].translate(NAME_FOLD)
        cands = self.index.get(base, [])
        if "/" in name:
            tail = name.lstrip("./")
            narrowed = [p for p in cands if str(p).endswith(tail)]
            cands = narrowed or cands
        return sorted(cands, key=lambda p: ("[uc]" in str(p), str(p)))

    def lines(self, p: Path) -> list[str]:
        if p not in self._lines:
            self._lines[p] = p.read_text(encoding="utf-8", errors="replace").splitlines()
        return self._lines[p]

    def norm_lines(self, p: Path) -> list[str]:
        if p not in self._norm:
            raw = self.lines(p)
            self._norm[p] = [norm(x) for x in raw]
        return self._norm[p]


def table_rows(md_text: str):
    for i, line in enumerate(md_text.splitlines(), 1):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c) :
            continue
        yield i, cells


def parse_citations(text: str, corpus: Corpus, last_file: str | None):
    """回傳 ([(檔名或None, [(起,訖)…])…], 新的 last_file)。"""
    groups: list[tuple[str | None, list[tuple[int, int]]]] = []
    cur = last_file
    for m in TOKEN_RE.finditer(text):
        if m.group("link"):
            continue
        if m.group("file"):
            f = m.group("file")
            follow = text[m.end():m.end() + 3].lstrip("` ")
            if corpus.find(f) or follow.startswith("L"):
                cur = f
            continue
        a, b, more = m.group(4), m.group(5), m.group(6)  # 1=link 2=file 3=range
        rs = [(int(a), int(b) if b else int(a))]
        for mm in MORE_RE.finditer(more or ""):
            rs.append((int(mm.group(1)), int(mm.group(2)) if mm.group(2) else int(mm.group(1))))
        if groups and groups[-1][0] == cur:
            groups[-1][1].extend(rs)
        else:
            groups.append((cur, rs))
    return groups, cur


def quotes_in(cells: list[str]) -> list[str]:
    out = []
    for c in cells[1:] if len(cells) > 1 else cells:
        for m in QUOTE_RE.finditer(c):
            out.append(next(g for g in m.groups() if g))
    return out


def check_file(corpus: Corpus, md_path: Path, label: str | None = None) -> dict:
    text = md_path.read_text(encoding="utf-8")
    rows, pending = [], []
    last = None
    for lineno, cells in table_rows(text):
        groups, last = parse_citations(" | ".join(cells), corpus, last)
        row = {"line": lineno, "node": cells[0][:30] if cells else "",
               "cites": [{"file": f, "ranges": r} for f, r in groups], "status": None, "detail": ""}
        rows.append(row)
        if not groups:
            row["status"] = "skip"
            continue
        if any(f is None for f, _ in groups):
            row["status"], row["detail"] = "無檔名", "行號前面找不到出處檔名"
            continue
        resolved = []
        missing = [f for f, _ in groups if not corpus.find(f)]
        if missing:
            row["status"], row["detail"] = "檔不存在", "、".join(missing)
            continue
        for f, rs in groups:
            resolved.append((corpus.find(f), rs))
        pending.append((row, resolved, quotes_in(cells)))

    allq = [q for _, _, qs in pending for q in qs]
    conv = iter(opencc_many(allq))
    for row, resolved, qs in pending:
        nq = [next(conv) for _ in qs]
        row["status"], row["detail"] = judge_row(corpus, resolved, qs, nq)
    return {"file": label or str(md_path), "rows": rows}


def judge_row(corpus: Corpus, resolved, quotes, nquotes):
    spans, wholes, bad = [], [], []
    for cands, rs in resolved:
        ok_cands = [p for p in cands if all(1 <= a <= b <= len(corpus.lines(p)) for a, b in rs)]
        if not ok_cands:
            n = len(corpus.lines(cands[0]))
            bad.append(f"{cands[0].name} " + ",".join(f"L{a}-L{b}" for a, b in rs if not (1 <= a <= b <= n)) + f"（檔長 {n}）")
            ok_cands = cands
        for p in ok_cands:
            nl = corpus.norm_lines(p)
            spans += ["".join(nl[a - 1:b]) for a, b in rs]
            wholes.append("".join(nl))
    if bad:
        return "超界", "；".join(bad)
    missing, outside, near = [], [], []
    for q, nqs in zip(quotes, nquotes):
        segs = [s for s in (norm(x) for x in SPLIT_RE.split(nqs)) if len(s) >= 2]
        if not segs or all(any(s in sp for sp in spans) for s in segs):
            continue
        if all(any(s in sp for sp in spans) or is_near(s, spans) for s in segs):
            near.append(q)
        elif all(any(s in w for w in wholes) for s in segs):
            outside.append(q)
        else:
            missing.append(q)
    if missing:
        return "引文找不到", "「" + "」「".join(missing[:5]) + "」"
    if outside:
        return "引文在範圍外", "「" + "」「".join(outside[:5]) + "」"
    if near:
        return "引文近似", "「" + "」「".join(near[:5]) + "」"
    return "ok", ""


def is_near(seg: str, spans: list[str]) -> bool:
    need = max(4, -(-len(seg) * 6 // 10))
    if len(seg) < 4:
        return False
    for sp in spans:
        m = SequenceMatcher(None, seg, sp, autojunk=False).find_longest_match(0, len(seg), 0, len(sp))
        if m.size >= need:
            return True
    return False


def evidence_files_for(copy_root: Path, name: str) -> list[Path]:
    d = copy_root / "lore/evidence/characters"
    out = []
    for cand in [d / f"{name}.md", *sorted(d.glob(f"{name}_*.md")), *sorted(d.glob(f"*_{name}.md"))]:
        if cand.exists() and cand not in out:
            out.append(cand)
    if (d / name).is_dir():
        out += sorted((d / name).rglob("*.md"))
    return out


def golden_files(batches=None, names=None) -> list[Path]:
    spec = json.loads((HERE / "golden.json").read_text(encoding="utf-8"))
    out = []
    for b in spec["batches"]:
        if batches and str(b["batch"]) not in [str(x) for x in batches]:
            continue
        for c in b["characters"]:
            if names and c["name"] not in names:
                continue
            out += [HERE / "golden" / str(b["batch"]) / e for e in c["evidence_paths"]]
    return out


def summarize(results: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for r in results:
        for row in r["rows"]:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
    checked = sum(v for k, v in counts.items() if k != "skip")
    return {"checked_rows": checked, "ok": counts.get("ok", 0),
            "ok_loose": counts.get("ok", 0) + counts.get("引文近似", 0), "by_status": counts}


def run(copy_root: Path, names=None, files=None, corpus: Corpus | None = None) -> dict:
    corpus = corpus or Corpus(copy_root)
    results, targets = [], [(Path(f), str(f)) for f in (files or [])]
    for name in names or []:
        found = evidence_files_for(copy_root, name)
        if not found:
            results.append({"file": f"(找不到 {name} 的證據檔)", "rows": [
                {"line": 0, "node": name, "cites": [], "status": "檔不存在", "detail": "沒有證據檔"}]})
        targets += [(f, str(f.relative_to(copy_root))) for f in found]
    for f, label in targets:
        results.append(check_file(corpus, f, label))
    return {"files": results, "summary": summarize(results)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("copy_root")
    ap.add_argument("names", nargs="*")
    ap.add_argument("--files", nargs="*", default=[])
    ap.add_argument("--golden", nargs="*", default=None, metavar="批號")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args(argv)
    files = list(a.files)
    names = a.names
    if a.golden is not None:
        files += golden_files(a.golden, names or None)
        names = []
    out = run(Path(a.copy_root).resolve(), names, files)
    if a.summary:
        print(json.dumps(out["summary"], ensure_ascii=False))
        for r in out["files"]:
            short = r["file"].split("/golden/")[-1]
            for row in r["rows"]:
                if row["status"] not in ("ok", "skip"):
                    fs = ",".join(str(c["file"]) for c in row["cites"])
                    print(f"{short}:{row['line']}  {row['status']}  {fs[:60]}  {row['detail'][:120]}")
    else:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    s = out["summary"]
    return 0 if s["checked_rows"] == s["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
