#!/usr/bin/env python3
"""檢查 proto6 的條號引用（P-/B-/S-/A-/H-/C-/T-）是否都有定義處。

用法（從 repo 根目錄）：python3 proto6/spec/check_ids.py
掃 proto6/spec 與 proto6/notes（不含 notes/archive）的 .md。
定義處＝標題行開頭（如 `## P-101．...`）、或條列／表格列開頭的條號
（如 `- A-501（已刪…）`、`| P-001 |`、`| H-036 |`）。
引用範圍 `P-500～507`、`P-104／110`、`B-601、603` 會展開，逐一檢查。
找不到定義時列出「檔:行 條號」並以結束碼 1 離開；全過結束碼 0。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # proto6/
SCAN = [ROOT / "spec", ROOT / "notes"]
ID = re.compile(r"(?<![A-Za-z0-9])([PBSAHCT])-(\d{2,3})((?:[～~／]\d{2,3}|、\d{2,3}(?![\d-]))*)")
DEF = re.compile(r"^(?:#+\s+|[-*]\s+|\|\s*)\**([PBSAHCT])-(\d{2,3})\b")


def files():
    for base in SCAN:
        for p in sorted(base.rglob("*.md")):
            if "archive" in p.relative_to(ROOT).parts:
                continue
            yield p


def expand(letter, first, tail):
    """回傳這個引用涵蓋的條號集合（範圍只檢查兩端點）。"""
    out = [f"{letter}-{first}"]
    for m in re.finditer(r"([～~／、])(\d{2,3})", tail):
        out.append(f"{letter}-{m.group(2)}")
    return out


def main():
    defined = set()
    for p in files():
        for line in p.read_text(encoding="utf-8").splitlines():
            m = DEF.match(line)
            if m:
                defined.add(f"{m.group(1)}-{m.group(2)}")
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
    for p, n, i in missing:
        print(f"{p}:{n}: {i}")
    print(f"引用 {total} 個，定義 {len(defined)} 個，找不到 {len(missing)} 個")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
