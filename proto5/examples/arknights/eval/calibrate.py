#!/usr/bin/env python3
"""評審校準：標準答案自評 3 人＋故意弄壞版 3 人（共 6 次 opus 呼叫），結果寫 calib/results.json。

用法：python make_broken.py && python calibrate.py <副本路徑>
過關標準：標準答案平均 ≥ 7/8，壞版本平均比標準答案低 ≥ 2 分。
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evidence_check import Corpus  # noqa: E402
from judge import judge_one  # noqa: E402

PEOPLE = [("100", "伊萬"), ("143", "羅索"), ("79", "奧克里·珀森斯")]


def main() -> int:
    copy_root = Path(sys.argv[1]).expanduser().resolve()
    corpus = Corpus(copy_root)
    jobs = []
    for batch, name in PEOPLE:
        jobs.append(("gold", batch, name, HERE / "golden" / batch))
        jobs.append(("broken", batch, name, HERE / "calib" / "broken" / batch))
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda j: {"kind": j[0], **judge_one(copy_root, j[1], j[2], j[3], corpus,
                                                                 tag=f"calib-{j[0]}-{j[1]}/{j[2]}")}, jobs))
    out = HERE / "calib" / "results.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for kind in ("gold", "broken"):
        tot = [r["scores"]["total"] for r in res if r["kind"] == kind and "scores" in r]
        print(kind, tot, "平均", round(sum(tot) / len(tot), 2) if tot else None)
    for r in res:
        s = r.get("scores", {})
        print(r["kind"], r["batch"], r["name"], {k: s.get(k) for k in ("coverage", "no_invention", "boundary", "citation")},
              s.get("reason") or r.get("error"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
