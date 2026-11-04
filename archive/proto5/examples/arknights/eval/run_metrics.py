#!/usr/bin/env python3
"""量測一次團隊跑：token、秒數、每一跳、模型呼叫次數，輸出一列 JSON。

用法：
    python run_metrics.py <團隊資料夾或其上層> [--hops AOS_HOPS檔] [--label 名稱]

吃 proto5 現有格式（見 spec/agent/events.md、spec/team/）：
  <team>/members/<名>/log/usage.jsonl（連輪換的 usage.N.jsonl）：一行＝一次模型呼叫，
      欄位 at／model／ms／usage.prompt_tokens／usage.completion_tokens
  <team>/members/<名>/log/events.jsonl（連輪換）：think_end.ms＝想的時間，act_end.ms＝動手時間（照 ev＋id 去重）
  <team>/team/tasks/*.json：單子 status／created_at／history[].at
  <team>/team/post/sent/*.json：寄出的信（只數封數）
  --hops：AOS_HOPS 環境變數指到的 jsonl，交給 lib/aos_hops.py 的 load/timeline/hops/summarize 算每一跳。
給的路徑底下若沒有 members/，會往下找所有含 members/ 的資料夾一起算（例如另一隊留在 ~/tmp/arknights-try/ 的紀錄）。
總秒數＝所有紀錄裡最早到最晚的時間差（usage.at、單子 created_at／history.at）。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE.parents[2] / "lib"   # proto5/lib


def read_jsonl_rotated(log_dir: Path, stem: str) -> list[dict]:
    files = sorted(log_dir.glob(f"{stem}.*.jsonl"), key=lambda p: -int(p.name.split(".")[1]) if p.name.split(".")[1].isdigit() else 0)
    files += [log_dir / f"{stem}.jsonl"]
    rows = []
    for f in files:
        if not f.exists():
            continue
        for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(ln)
            except ValueError:
                continue  # 寫到一半的壞行跳過（同 spec）
            if isinstance(d, dict):
                rows.append(d)
    return rows


def when(s):
    if not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def team_dirs(root: Path) -> list[Path]:
    if (root / "members").is_dir():
        return [root]
    return sorted({p.parent for p in root.rglob("members") if p.is_dir()})


def measure(root: Path, hops_file: Path | None = None, label: str | None = None) -> dict:
    out = {"label": label or root.name, "root": str(root), "teams": [], "calls": 0, "calls_by_model": {},
           "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls_without_usage": 0,
           "model_ms": 0, "think_ms": 0, "act_ms": 0, "tasks": 0, "tasks_by_status": {}, "mails": 0,
           "wall_s": None, "start": None, "end": None, "by_member": {}, "hops": None}
    times = []
    for team in team_dirs(root):
        out["teams"].append(str(team.relative_to(root)) if team != root else ".")
        for m in sorted((team / "members").iterdir()):
            if not (m / "log").is_dir():
                continue
            usage = read_jsonl_rotated(m / "log", "usage")
            events = read_jsonl_rotated(m / "log", "events")
            seen, think, act = set(), 0, 0
            for e in events:
                key = (e.get("ev"), e.get("id"))
                if e.get("id") is not None:
                    if key in seen:
                        continue
                    seen.add(key)
                if e.get("ev") == "think_end" and isinstance(e.get("ms"), (int, float)):
                    think += e["ms"]
                elif e.get("ev") == "act_end" and isinstance(e.get("ms"), (int, float)):
                    act += e["ms"]
                t = when(e.get("at"))
                if t:
                    times.append(t)
            mb = {"calls": len(usage), "tokens": 0}
            for u in usage:
                out["calls"] += 1
                mdl = u.get("model") or "?"
                out["calls_by_model"][mdl] = out["calls_by_model"].get(mdl, 0) + 1
                us = u.get("usage") if isinstance(u.get("usage"), dict) else None
                if not us:
                    out["calls_without_usage"] += 1
                else:
                    pt, ct = int(us.get("prompt_tokens") or 0), int(us.get("completion_tokens") or 0)
                    tt = int(us.get("total_tokens") or pt + ct)
                    out["prompt_tokens"] += pt
                    out["completion_tokens"] += ct
                    out["total_tokens"] += tt
                    mb["tokens"] += tt
                if isinstance(u.get("ms"), (int, float)):
                    out["model_ms"] += u["ms"]
                t = when(u.get("at"))
                if t:
                    times.append(t)
            out["think_ms"] += think
            out["act_ms"] += act
            out["by_member"][m.name] = mb
        for tf in sorted((team / "team" / "tasks").glob("*.json")) if (team / "team" / "tasks").is_dir() else []:
            try:
                t = json.loads(tf.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if not isinstance(t, dict) or "status" not in t:
                continue
            out["tasks"] += 1
            out["tasks_by_status"][t["status"]] = out["tasks_by_status"].get(t["status"], 0) + 1
            for s in [t.get("created_at")] + [h.get("at") for h in t.get("history") or [] if isinstance(h, dict)]:
                w = when(s)
                if w:
                    times.append(w)
        sent = team / "team" / "post" / "sent"
        if sent.is_dir():
            out["mails"] += len(list(sent.glob("*.json")))
    times = [t for t in times if t.tzinfo] or times
    if times:
        lo, hi = min(times), max(times)
        out["start"], out["end"] = lo.isoformat(), hi.isoformat()
        out["wall_s"] = round((hi - lo).total_seconds(), 1)
    if hops_file:
        sys.path.insert(0, str(LIB))
        import aos_hops  # noqa: E402
        recs = aos_hops.load(str(hops_file))
        hop_out = {}
        for agent in aos_hops.agent_names(recs):
            table, wall = aos_hops.hops(aos_hops.timeline(recs, agent))
            hop_out[agent] = aos_hops.summarize(table, wall)
        out["hops"] = hop_out
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--hops")
    ap.add_argument("--label")
    a = ap.parse_args(argv)
    root = Path(a.root).expanduser().resolve()
    print(json.dumps(measure(root, Path(a.hops) if a.hops else None, a.label), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
