#!/usr/bin/env python3
"""一鍵評分（eval.sh 叫這支）：機械檢查＋證據檢查＋評審＋量測 → results/<時間>.json 與 .md。

用法：
    python eval_run.py <副本路徑> <批號…> [--team 團隊紀錄夾] [--hops 檔] [--no-judge] [--cand-root 目錄] [--label 名]
      批號＝golden.json 的批（30 60 79 100 143）；那批的人就是要評的人。
      待評預設讀 <副本路徑>/lore/...；--cand-root 可改讀別處（例如拿 golden/<批號> 自評做煙霧測試）。
      --team 給了才算量測（run_metrics.py）；--no-judge 不叫 opus（省額度，評審欄留空）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evidence_check  # noqa: E402
import judge  # noqa: E402
import mech_check  # noqa: E402
import run_metrics  # noqa: E402

AXES = judge.AXES
AXIS_ZH = {"coverage": "覆蓋", "no_invention": "沒多編", "boundary": "邊界", "citation": "出處"}


def people_of(batches) -> list[tuple[str, str]]:
    spec = json.loads((HERE / "golden.json").read_text(encoding="utf-8"))
    out = []
    for b in spec["batches"]:
        if str(b["batch"]) in [str(x) for x in batches]:
            out += [(str(b["batch"]), c["name"]) for c in b["characters"]]
    return out


def run(copy_root: Path, batches, team=None, hops=None, do_judge=True, cand_root=None, label=None) -> dict:
    people = people_of(batches)
    if not people:
        raise SystemExit(f"golden.json 沒有這些批：{batches}")
    corpus = evidence_check.Corpus(copy_root)
    simp = mech_check.load_simplified(copy_root)
    rows = []
    for batch, name in people:
        root = (cand_root / batch if (cand_root / batch).is_dir() else cand_root) if cand_root else copy_root
        entry, evid = mech_check.char_files(root, name)
        mech = mech_check.check_person(name, entry, evid, root, copy_root, simp)
        ev = evidence_check.run(root, files=evid, corpus=corpus) if evid else {"files": [], "summary": {"checked_rows": 0, "ok": 0, "ok_loose": 0, "by_status": {}}}
        rows.append({"batch": batch, "name": name, "cand_root": str(root),
                     "mech": {"passed": sum(c["pass"] for c in mech), "total": len(mech),
                              "failed": [c for c in mech if not c["pass"]]},
                     "evidence": {**ev["summary"], "bad_rows": [
                         {"file": f["file"].split("/lore/")[-1], **{k: r[k] for k in ("line", "status", "detail")}}
                         for f in ev["files"] for r in f["rows"] if r["status"] not in ("ok", "skip")]}})
    if do_judge:
        def one(row):
            try:
                return judge.judge_one(copy_root, row["batch"], row["name"], Path(row["cand_root"]), corpus,
                                       tag=f"{label or 'run'}-{row['batch']}/{row['name']}")
            except Exception as e:  # noqa: BLE001
                return {"error": str(e)}
        with ThreadPoolExecutor(4) as ex:
            for row, j in zip(rows, ex.map(one, rows)):
                row["judge"] = j
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "label": label, "copy_root": str(copy_root),
           "batches": [str(b) for b in batches], "judge_model": judge.MODEL if do_judge else None,
           "people": rows, "repo": mech_check.repo_checks(copy_root) if not cand_root else [],
           "metrics": run_metrics.measure(Path(team).expanduser().resolve(), Path(hops) if hops else None) if team else None}
    scored = [r for r in rows if r.get("judge", {}).get("scores")]
    out["lowest3"] = [{"batch": r["batch"], "name": r["name"], "total": r["judge"]["scores"]["total"],
                       "reason": r["judge"]["scores"].get("reason", "")}
                      for r in sorted(scored, key=lambda r: (r["judge"]["scores"]["total"], r["evidence"]["ok"] - r["evidence"]["checked_rows"]))[:3]]
    return out


def to_markdown(res: dict) -> str:
    L = [f"# 評分結果 {res['at']}" + (f"（{res['label']}）" if res.get("label") else ""), "",
         f"副本：`{res['copy_root']}`；批：{'、'.join(res['batches'])}；評審：{res['judge_model'] or '沒叫'}", "",
         "| 批 | 人 | 機械 | 證據列 ok（寬鬆） | " + " | ".join(AXIS_ZH[a] for a in AXES) + " | 評審總分 | 理由 |",
         "|---|---|---|---|" + "---|" * len(AXES) + "---|---|"]
    for r in res["people"]:
        e = r["evidence"]
        s = r.get("judge", {}).get("scores") or {}
        reason = s.get("reason") or r.get("judge", {}).get("error", "")
        L.append(f"| {r['batch']} | {r['name']} | {r['mech']['passed']}/{r['mech']['total']} | "
                 f"{e['ok']}/{e['checked_rows']}（{e.get('ok_loose', e['ok'])}） | "
                 + " | ".join(str(s.get(a, "–")) for a in AXES)
                 + f" | {s.get('total', '–')}/8 | {str(reason).replace('|', '／')} |")
    tot_m = sum(r["mech"]["passed"] for r in res["people"]), sum(r["mech"]["total"] for r in res["people"])
    tot_e = sum(r["evidence"]["ok"] for r in res["people"]), sum(r["evidence"]["checked_rows"] for r in res["people"])
    L += ["", f"合計：機械 {tot_m[0]}/{tot_m[1]}；證據列 {tot_e[0]}/{tot_e[1]}"]
    if res.get("lowest3"):
        L += ["", "## 評審分最低的 3 個（請抽查）", ""]
        L += [f"{i}. 第 {x['batch']} 批 {x['name']}：{x['total']}/8——{x['reason']}" for i, x in enumerate(res["lowest3"], 1)]
    bad = [(r, b) for r in res["people"] for b in r["evidence"]["bad_rows"]]
    if bad:
        L += ["", "## 證據列沒過的", ""]
        L += [f"- {r['name']}｜{b['file']}:{b['line']}｜{b['status']}｜{b['detail'][:80]}" for r, b in bad]
    fails = [(r, c) for r in res["people"] for c in r["mech"]["failed"]]
    if fails:
        L += ["", "## 機械檢查沒過的", ""]
        L += [f"- {r['name']}｜{c['check']}｜{c['msg'][:100]}" for r, c in fails]
    if res.get("repo"):
        L += ["", "## 全庫", ""] + [f"- {c['check']}：{'過' if c['pass'] else '沒過'}　{c['msg'][:100]}" for c in res["repo"]]
    m = res.get("metrics")
    if m:
        L += ["", "## 量測", "", f"模型呼叫 {m['calls']} 次（{m['calls_by_model']}）；token 入 {m['prompt_tokens']}／出 {m['completion_tokens']}；"
              f"總秒數 {m['wall_s']}；想 {m['think_ms'] / 1000:.1f}s、動手 {m['act_ms'] / 1000:.1f}s；單子 {m['tasks']}（{m['tasks_by_status']}）；信 {m['mails']} 封"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("copy_root")
    ap.add_argument("batches", nargs="+")
    ap.add_argument("--team")
    ap.add_argument("--hops")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--cand-root")
    ap.add_argument("--label")
    ap.add_argument("--out-dir", default=str(HERE / "results"))
    a = ap.parse_args(argv)
    res = run(Path(a.copy_root).expanduser().resolve(), a.batches, a.team, a.hops, not a.no_judge,
              Path(a.cand_root).resolve() if a.cand_root else None, a.label)
    od = Path(a.out_dir)
    od.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S") + (f"-{a.label}" if a.label else "")
    (od / f"{stamp}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    md = to_markdown(res)
    (od / f"{stamp}.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"→ {od / stamp}.json／.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
