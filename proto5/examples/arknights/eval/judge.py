#!/usr/bin/env python3
"""模型評審：固定 claude-opus-5（走 LiteLLM http://localhost:4000/v1，溫度 0），拿待評與標準答案比。

用法：
    python judge.py <副本路徑> <批號> <角色名…> [--cand-root 目錄] [--out 檔.json]
      待評預設讀 <副本路徑>/lore/...；--cand-root 可改讀別處（校準時拿 golden/ 或 calib/broken/）。
      標準答案讀 golden/<批號>/。原文摘錄從副本的 corpus 取。

每次呼叫記一行到 results/judge_calls.jsonl（時間、角色、token、秒數），用來數 opus 用了幾次。
環境變數 JUDGE_MODEL 可換評審（預設 claude-opus-5；換了分數就不能跟舊結果比）。
JUDGE_BUDGET＝整個 judge_calls.jsonl 最多幾行，超過就不呼叫、直接報錯（預設 40）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evidence_check import Corpus, evidence_files_for, parse_citations, table_rows  # noqa: E402

BASE = os.environ.get("LITELLM_BASE", "http://localhost:4000/v1")
MODEL = os.environ.get("JUDGE_MODEL", "claude-opus-5")
BUDGET = int(os.environ.get("JUDGE_BUDGET", "40"))
CALLS = HERE / "results" / "judge_calls.jsonl"
AXES = ["coverage", "no_invention", "boundary", "citation"]
MAX_LINES_PER_RANGE = 80
MAX_SOURCE_CHARS = 60000


def golden_person(batch, name):
    spec = json.loads((HERE / "golden.json").read_text(encoding="utf-8"))
    for b in spec["batches"]:
        if str(b["batch"]) == str(batch):
            for c in b["characters"]:
                if c["name"] == name:
                    root = HERE / "golden" / str(b["batch"])
                    return root / c["entry_path"], [root / e for e in c["evidence_paths"]]
    raise SystemExit(f"golden.json 沒有第 {batch} 批的 {name}")


def cat(files: list[Path], root: Path | None = None) -> str:
    parts = []
    for f in files:
        label = str(f.relative_to(root)) if root and f.is_relative_to(root) else f.name
        parts.append(f"--- {label} ---\n{f.read_text(encoding='utf-8')}" if f.exists() else f"--- {label}（不存在）---")
    return "\n".join(parts) if parts else "（沒有檔案）"


def source_excerpt(corpus: Corpus, evid_files: list[Path]) -> str:
    seen, chunks, total = set(), [], 0
    for f in evid_files:
        if not f.exists():
            continue
        last = None
        for _, cells in table_rows(f.read_text(encoding="utf-8")):
            groups, last = parse_citations(" | ".join(cells), corpus, last)
            for fname, ranges in groups:
                cands = corpus.find(fname) if fname else []
                if not cands:
                    continue
                p = cands[0]
                lines = corpus.lines(p)
                for a, b in ranges:
                    b = min(b, a + MAX_LINES_PER_RANGE - 1, len(lines))
                    for i in range(max(a, 1), b + 1):
                        key = (p, i)
                        if key in seen:
                            continue
                        seen.add(key)
                        s = f"{p.name} L{i}: {lines[i - 1]}"
                        total += len(s)
                        if total > MAX_SOURCE_CHARS:
                            chunks.append("…（摘錄過長，截斷）")
                            return "\n".join(chunks)
                        chunks.append(s)
    return "\n".join(chunks) if chunks else "（沒有可解析的出處）"


def calls_so_far() -> int:
    return sum(1 for _ in CALLS.open(encoding="utf-8")) if CALLS.exists() else 0


def call_model(prompt: str, tag: str) -> tuple[str, dict]:
    if calls_so_far() >= BUDGET:
        raise RuntimeError(f"評審呼叫已達上限 {BUDGET}（{CALLS}）")
    body = json.dumps({"model": MODEL, "temperature": 0, "max_tokens": 8000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.load(r)
    sec = round(time.time() - t0, 1)
    usage = data.get("usage", {})
    CALLS.parent.mkdir(exist_ok=True)
    with CALLS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": MODEL, "tag": tag,
                             "sec": sec, "usage": usage}, ensure_ascii=False) + "\n")
    return data["choices"][0]["message"]["content"] or "", {"sec": sec, "usage": usage}


def parse_scores(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("評審沒回 JSON：" + text[:200])
    d = json.loads(m.group(0))
    for k in AXES:
        d[k] = int(d.get(k, 0))
        if d[k] not in (0, 1, 2):
            raise ValueError(f"{k} 分數不是 0/1/2：{d[k]}")
    d["total"] = sum(d[k] for k in AXES)
    return d


def judge_one(copy_root: Path, batch, name, cand_root: Path | None = None, corpus: Corpus | None = None,
              tag: str = "") -> dict:
    corpus = corpus or Corpus(copy_root)
    cand_root = cand_root or copy_root
    c_entry = cand_root / "lore/characters" / f"{name}.md"
    c_evid = evidence_files_for(cand_root, name)
    g_entry, g_evid = golden_person(batch, name)
    prompt = (HERE / "judge_prompt.md").read_text(encoding="utf-8")
    fill = {
        "cand_entry": cat([c_entry], cand_root), "cand_evidence": cat(c_evid, cand_root),
        "gold_entry": cat([g_entry]), "gold_evidence": cat(g_evid),
        "source": source_excerpt(corpus, c_evid + g_evid),
    }
    for k, v in fill.items():
        prompt = prompt.replace("{" + k + "}", v)
    text, meta = call_model(prompt, tag or f"{batch}/{name}")
    out = {"batch": batch, "name": name, "model": MODEL, "prompt_chars": len(prompt), **meta}
    try:
        out["scores"] = parse_scores(text)
    except Exception as e:  # 回應壞了照記，不重叫（省額度）
        out["error"], out["raw"] = str(e), text[:2000]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("copy_root")
    ap.add_argument("batch")
    ap.add_argument("names", nargs="+")
    ap.add_argument("--cand-root")
    ap.add_argument("--tag", default="")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    copy_root = Path(a.copy_root).resolve()
    corpus = Corpus(copy_root)
    res = [judge_one(copy_root, a.batch, n, Path(a.cand_root).resolve() if a.cand_root else None, corpus,
                     tag=f"{a.tag}{a.batch}/{n}") for n in a.names]
    s = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(s, encoding="utf-8")
    print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
