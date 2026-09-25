#!/usr/bin/env python3
"""機械檢查：把 arknights 專案自己的檢查包成一支，逐人輸出 JSON。

用法：
    python mech_check.py <副本路徑> <角色名…>          # 看副本裡的詞條＋證據
    python mech_check.py <副本路徑> --golden [批號…]    # 看 golden/ 底下的標準答案（連結仍對照副本解析）

每人檢查（每條 pass/fail＋訊息）：
  entry_exists     詞條 lore/characters/<名>.md 存在
  evidence_exists  至少一個證據檔
  entry_links_evidence 詞條裡有連到自己的證據檔
  links            這人的檔案裡本地連結都指得到（規則同專案 scripts/check_links.py；解析基準是副本）
  simplified       專案 scripts/check_simplified.py 對這人的檔案＝簡體殘留 0
  evidence_size    每個證據檔 < 5KB（5120 位元組；專案規矩，早期批次沒有這條）
  whitespace       等同 git diff --check 對新檔的規則：行尾空白、空白後接 tab 的縮排、衝突標記、檔尾多餘空行
另外（非 golden 模式）整個副本跑一次：
  repo_links       python scripts/check_links.py .（全庫斷鏈 0）
  repo_diff_check  git diff --check（相對 HEAD，只看已追蹤檔的改動）
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import re
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evidence_check import evidence_files_for  # noqa: E402

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
LIMIT = 5120


def char_files(root: Path, name: str) -> tuple[Path, list[Path]]:
    return root / "lore/characters" / f"{name}.md", evidence_files_for(root, name)


def golden_chars(batches=None):
    spec = json.loads((HERE / "golden.json").read_text(encoding="utf-8"))
    for b in spec["batches"]:
        if batches and str(b["batch"]) not in [str(x) for x in batches]:
            continue
        for c in b["characters"]:
            root = HERE / "golden" / str(b["batch"])
            yield b["batch"], c["name"], root / c["entry_path"], [root / e for e in c["evidence_paths"]], root


def load_simplified(copy_root: Path):
    spec = importlib.util.spec_from_file_location("ak_check_simplified", copy_root / "scripts/check_simplified.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_links(files: list[Path], files_root: Path, link_root: Path) -> tuple[bool, str]:
    missing = []
    for md in files:
        rel_dir = md.parent.relative_to(files_root)
        for target in LINK_RE.findall(md.read_text(encoding="utf-8", errors="replace")):
            target = target.strip()
            if urlparse(target).scheme or target.startswith(("#", "mailto:")):
                continue
            path = unquote(target.split("#", 1)[0]).strip()
            if not path:
                continue
            if not ((md.parent / path).exists() or (link_root / rel_dir / path).exists()):
                missing.append(f"{md.name} -> {path}")
    return (not missing, f"斷鏈 {len(missing)}" + ("：" + "；".join(missing[:5]) if missing else ""))


def check_simplified(mod, files: list[Path], files_root: Path) -> tuple[bool, str]:
    mod.ROOT = files_root
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = mod.main.__wrapped__(files) if hasattr(mod.main, "__wrapped__") else _run_simplified(mod, files)
    out = buf.getvalue().strip().splitlines()
    return rc == 0, (out[0] if out else "") + ("；" + "；".join(l.strip() for l in out if ":" in l)[:300] if rc else "")


def _run_simplified(mod, files):
    old = sys.argv
    sys.argv = ["check_simplified.py", *[str(f) for f in files]]
    try:
        return mod.main()
    finally:
        sys.argv = old


def check_whitespace(files: list[Path]) -> tuple[bool, str]:
    probs = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        lines = text.split("\n")
        for i, ln in enumerate(lines, 1):
            if ln != ln.rstrip(" \t\r"):
                probs.append(f"{f.name}:{i} 行尾空白")
            if re.match(r"^ +\t", ln):
                probs.append(f"{f.name}:{i} 空白後接 tab")
            if re.match(r"^(<{7}|={7}|>{7})( |$)", ln):
                probs.append(f"{f.name}:{i} 衝突標記")
        if text.endswith("\n\n"):
            probs.append(f"{f.name} 檔尾多餘空行")
    return not probs, f"{len(probs)} 處" + ("：" + "；".join(probs[:5]) if probs else "")


def check_person(name, entry: Path, evid: list[Path], files_root: Path, link_root: Path, simp_mod) -> list[dict]:
    res = []

    def add(key, ok, msg=""):
        res.append({"check": key, "pass": bool(ok), "msg": msg})

    add("entry_exists", entry.exists(), str(entry.relative_to(files_root)) if entry.is_relative_to(files_root) else str(entry))
    add("evidence_exists", bool(evid), f"{len(evid)} 檔")
    files = ([entry] if entry.exists() else []) + evid
    if entry.exists():
        txt = entry.read_text(encoding="utf-8")
        add("entry_links_evidence", "evidence/characters/" in txt, "")
    if files:
        add("links", *check_links(files, files_root, link_root))
        add("simplified", *check_simplified(simp_mod, files, files_root))
        big = [f"{f.name} {f.stat().st_size}B" for f in evid if f.stat().st_size >= LIMIT]
        add("evidence_size", not big, "；".join(big) if big else f"最大 {max((f.stat().st_size for f in evid), default=0)}B")
        add("whitespace", *check_whitespace(files))
    return res


def repo_checks(copy_root: Path) -> list[dict]:
    out = []
    p = subprocess.run([sys.executable, "scripts/check_links.py", "."], cwd=copy_root, capture_output=True, text=True)
    out.append({"check": "repo_links", "pass": p.returncode == 0, "msg": (p.stdout.strip().splitlines() or [""])[0]})
    p = subprocess.run(["git", "diff", "--check", "HEAD"], cwd=copy_root, capture_output=True, text=True)
    out.append({"check": "repo_diff_check", "pass": p.returncode == 0, "msg": p.stdout.strip()[:300]})
    return out


def run(copy_root: Path, names=None, golden=None) -> dict:
    simp = load_simplified(copy_root)
    people = []
    if golden is not None:
        for batch, name, entry, evid, root in golden_chars(golden):
            people.append({"batch": batch, "name": name,
                           "checks": check_person(name, entry, evid, root, copy_root, simp)})
    for name in names or []:
        entry, evid = char_files(copy_root, name)
        people.append({"name": name, "checks": check_person(name, entry, evid, copy_root, copy_root, simp)})
    for p in people:
        p["passed"] = sum(c["pass"] for c in p["checks"])
        p["total"] = len(p["checks"])
    out = {"people": people}
    if golden is None:
        out["repo"] = repo_checks(copy_root)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("copy_root")
    ap.add_argument("names", nargs="*")
    ap.add_argument("--golden", nargs="*", default=None, metavar="批號")
    a = ap.parse_args(argv)
    out = run(Path(a.copy_root).resolve(), a.names, a.golden)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    ok = all(c["pass"] for p in out["people"] for c in p["checks"]) and all(c["pass"] for c in out.get("repo", []))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
