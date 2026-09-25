#!/usr/bin/env python3
"""品管部：評「不在基準集裡的人」（評分器程式一行不改，只在外面包一層）。

用法：
    python score_nongolden.py <副本> <快照夾> <批標籤> <名…> [--judge] [--label 名]
      快照夾：先把副本裡這些人的 lore 檔原樣複製過來（副本會被下一次試跑退回基線）；
              快照夾底下要有 lore/characters/<名>.md、lore/evidence/characters/<名>(.md|/)。
      --judge：每人叫一次評審（claude-opus-5，走 LiteLLM）。沒有 golden，所以「參照」改用
               副本 aos-drafts/<名>/ 的草稿——分數只能說「比草稿好不好」，不能跟 golden 基準的 8/8 直接比。
    另外把草稿本身也跑一次證據檢查（不叫模型），當「交件前」對照。
出：評分器的 results/<時間>-<label>.json／.md（格式同 eval_run.py）。
"""
import argparse
import json
import sys
import time
from pathlib import Path

EV = Path(__file__).resolve().parents[3] / "examples" / "arknights" / "eval"
sys.path.insert(0, str(EV))
import eval_run  # noqa: E402
import evidence_check  # noqa: E402
import judge  # noqa: E402
import mech_check  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("copy_root")
    ap.add_argument("snap")
    ap.add_argument("batch")
    ap.add_argument("names", nargs="+")
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--label", default="qa")
    a = ap.parse_args(argv)
    copy_root, snap = Path(a.copy_root).expanduser().resolve(), Path(a.snap).resolve()
    corpus = evidence_check.Corpus(copy_root)
    simp = mech_check.load_simplified(copy_root)
    drafts = {n: (copy_root / "aos-drafts" / n / "詞條草稿.md", [copy_root / "aos-drafts" / n / "證據草稿.md"])
              for n in a.names}
    judge.golden_person = lambda batch, name: drafts[name]   # 參照＝草稿（這些人沒有 golden）
    rows = []
    for name in a.names:
        entry, evid = mech_check.char_files(snap, name)
        mech = mech_check.check_person(name, entry, evid, snap, copy_root, simp)
        ev = (evidence_check.run(snap, files=evid, corpus=corpus) if evid else
              {"files": [], "summary": {"checked_rows": 0, "ok": 0, "ok_loose": 0, "by_status": {}}})
        dev = evidence_check.run(copy_root, files=drafts[name][1], corpus=corpus)
        row = {"batch": a.batch, "name": name, "cand_root": str(snap),
               "mech": {"passed": sum(c["pass"] for c in mech), "total": len(mech),
                        "failed": [c for c in mech if not c["pass"]]},
               "evidence": {**ev["summary"], "bad_rows": [
                   {"file": f["file"].split("/lore/")[-1], **{k: r[k] for k in ("line", "status", "detail")}}
                   for f in ev["files"] for r in f["rows"] if r["status"] not in ("ok", "skip")]},
               "draft_evidence": dev["summary"]}
        if a.judge and entry.exists():
            try:
                row["judge"] = judge.judge_one(copy_root, a.batch, name, snap, corpus, tag=f"{a.label}-{a.batch}/{name}")
            except Exception as e:  # noqa: BLE001
                row["judge"] = {"error": str(e)}
        rows.append(row)
    scored = [r for r in rows if r.get("judge", {}).get("scores")]
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "label": a.label, "copy_root": str(copy_root),
           "batches": [a.batch], "judge_model": judge.MODEL if a.judge else None,
           "judge_reference": "aos-drafts 草稿（非 golden）", "people": rows, "repo": [], "metrics": None,
           "lowest3": [{"batch": r["batch"], "name": r["name"], "total": r["judge"]["scores"]["total"],
                        "reason": r["judge"]["scores"].get("reason", "")}
                       for r in sorted(scored, key=lambda r: (r["judge"]["scores"]["total"],
                                                              r["evidence"]["ok"] - r["evidence"]["checked_rows"]))[:3]]}
    od = EV / "results"
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{a.label}"
    (od / f"{stamp}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    md = eval_run.to_markdown(out)
    (od / f"{stamp}.md").write_text(md, encoding="utf-8")
    print(md)
    print(json.dumps({r["name"]: r["draft_evidence"] for r in rows}, ensure_ascii=False))
    print(f"→ {od / stamp}.json／.md")


if __name__ == "__main__":
    main()
