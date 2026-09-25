#!/usr/bin/env python3
"""把 golden.json 列的標準答案從 arknights 各 commit 抽出來，存到 golden/<批號>/<repo 相對路徑>。

用法：python build_golden.py <arknights repo 或副本路徑>
只讀 git 物件（git show），不碰對方工作樹。已存在的檔會覆寫成 commit 版本。
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    repo = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path("~/tmp/arknights-eval").expanduser()
    spec = json.loads((HERE / "golden.json").read_text(encoding="utf-8"))
    n = 0
    for b in spec["batches"]:
        for c in b["characters"]:
            for rel in [c["entry_path"], *c["evidence_paths"]]:
                blob = subprocess.run(["git", "-C", str(repo), "show", f"{b['commit']}:{rel}"],
                                      capture_output=True, check=True).stdout
                out = HERE / "golden" / str(b["batch"]) / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(blob)
                n += 1
    print(f"抽出 {n} 檔到 {HERE / 'golden'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
