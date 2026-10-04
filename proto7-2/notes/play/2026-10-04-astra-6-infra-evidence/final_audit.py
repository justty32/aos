#!/usr/bin/env python3
"""Read-only final QA integrity and link audit; outputs only within this evidence directory."""
import datetime, hashlib, json, pathlib, re, subprocess
E = pathlib.Path(__file__).resolve().parent
ROOT = E.parents[3]
REPORT = E.parent / "2026-10-04-astra-6-infra.md"
baseline = json.loads((E / "baseline.json").read_text())
changed = []
for name, sha in baseline["sha256"].items():
    p = ROOT / name
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != sha:
        changed.append(name)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
status = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True)
ps = subprocess.check_output(["ps", "-eo", "pid,ppid,pgid,sid,stat,lstart,args"], text=True)
(E / "ps-final.txt").write_text(ps)
missing_links = []
for p in [REPORT, *E.rglob("summary.md")]:
    if not p.is_file():
        missing_links.append(str(p))
        continue
    for target in re.findall(r"\]\(([^)]+)\)", p.read_text()):
        target = target.split("#", 1)[0]
        if not target or "://" in target:
            continue
        if not (p.parent / target).exists():
            missing_links.append({"file": str(p.relative_to(ROOT)), "target": target})
result = {"at": datetime.datetime.now().astimezone().isoformat(),
          "head_before": baseline["head"], "head_after": head,
          "head_unchanged": head == baseline["head"],
          "tracked_files_checked": len(baseline["sha256"]), "tracked_changes": changed,
          "git_status": status, "missing_report_summary_links": missing_links,
          "process_evidence": "ps-final.txt; each line's cleanup JSON is the PID-specific source"}
(E / "final-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False, indent=2))
