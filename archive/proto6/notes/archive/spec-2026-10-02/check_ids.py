#!/usr/bin/env python3
"""檢查 proto6 的條號（P-/B-/S-/A-/H-/C-/T-/V-）：引用都有定義、沒有重號、沒有只剩索引列。

用法（從 repo 根目錄）：python3 proto6/spec/check_ids.py [--strict]
掃 proto6/spec 與 proto6/notes（不含 notes/archive 與 notes/reviews：審稿紀錄會照原樣引用已刪條號）的 .md。
定義處＝標題行開頭（如 `## P-101．...`）、或條列／表格列開頭的條號
（如 `- A-501（已刪…）`、`| P-001 |`、`| H-036 |`）。
引用範圍 `P-500～507`、`P-104／110`、`B-601、603` 會展開，逐一檢查。

錯誤（結束碼 1）：
- 引用找不到定義處。
- 同一條號有兩個以上的標題（重號）。
- 條號只出現在表格列、沒有標題或條列正文（只剩索引列）。預留表的列除外。
預留表＝緊接在 `<!-- check_ids:reserved -->` 那行之後的表格（在 conformance.md V-01）：
預留的新條號還沒寫出正文時只提醒；加 `--strict` 才算錯（收尾時用）。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # proto6/
SCAN = [ROOT / "spec", ROOT / "notes"]
LETTERS = "PBSAHCTV"
ID = re.compile(rf"(?<![A-Za-z0-9])([{LETTERS}])-(\d{{2,3}})((?:[～~／]\d{{2,3}}|、\d{{2,3}}(?![\d-]))*)")
DEF = re.compile(rf"^(?:(#+)\s+|([-*])\s+|(\|)\s*)\**([{LETTERS}])-(\d{{2,3}})\b")
RESERVED_MARK = "<!-- check_ids:reserved -->"


def files():
    for base in SCAN:
        for p in sorted(base.rglob("*.md")):
            if {"archive", "reviews"} & set(p.relative_to(ROOT).parts):
                continue
            yield p


def expand(letter, first, tail):
    """回傳這個引用涵蓋的條號集合（範圍只檢查兩端點）。"""
    out = [f"{letter}-{first}"]
    for m in re.finditer(r"([～~／、])(\d{2,3})", tail):
        out.append(f"{letter}-{m.group(2)}")
    return out


def main(argv):
    strict = "--strict" in argv
    heads = {}      # 條號 → [檔:行]（標題）
    bodies = set()  # 有標題或條列正文的條號
    tables = {}     # 條號 → [檔:行]（表格列，不含預留表）
    reserved = {}   # 條號 → 檔:行
    for p in files():
        rel = p.relative_to(ROOT.parent)
        in_reserved = False
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip() == RESERVED_MARK:
                in_reserved = True
                continue
            if in_reserved and not line.lstrip().startswith("|"):
                in_reserved = False
            m = DEF.match(line)
            if not m:
                continue
            i = f"{m.group(4)}-{m.group(5)}"
            where = f"{rel}:{n}"
            if m.group(1):
                heads.setdefault(i, []).append(where)
                bodies.add(i)
            elif m.group(2):
                bodies.add(i)
            elif in_reserved:
                reserved[i] = where
            else:
                tables.setdefault(i, []).append(where)
    defined = bodies | set(tables) | set(reserved)

    missing = []
    total = 0
    for p in files():
        in_code = False
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            for m in ID.finditer(line):
                for i in expand(m.group(1), m.group(2), m.group(3)):
                    total += 1
                    if i not in defined:
                        missing.append((p.relative_to(ROOT.parent), n, i))

    errors = 0
    for p, n, i in missing:
        print(f"{p}:{n}: {i} 找不到定義")
    errors += len(missing)
    dups = {i: w for i, w in heads.items() if len(w) > 1}
    for i, w in sorted(dups.items()):
        print(f"重號 {i}：{'、'.join(w)}")
    errors += len(dups)
    index_only = sorted(i for i in tables if i not in bodies and i not in reserved)
    for i in index_only:
        print(f"只剩索引列 {i}：{'、'.join(tables[i])}")
    errors += len(index_only)
    pending = sorted(i for i in reserved if i not in bodies)
    for i in pending:
        tag = "錯誤" if strict else "提醒"
        print(f"{tag}：預留條號 {i} 還沒寫正文（{reserved[i]}）")
    if strict:
        errors += len(pending)

    print(f"引用 {total} 個，定義 {len(defined)} 個，找不到 {len(missing)} 個，"
          f"重號 {len(dups)} 個，只剩索引列 {len(index_only)} 個，預留未寫 {len(pending)} 個")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
