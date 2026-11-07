"""Collect local progress, handoffs, commits, and host samples into the progress board state."""

import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
STATUSES = {"start", "progress", "done", "blocked", "decision", "handoff"}


def board_path():
    return Path(os.environ.get("AOS_PROGRESS_DIR", "~/Desktop/aos-進度")).expanduser().resolve()


def load_config():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def iso_now():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def parse_ts(value):
    try:
        return dt.datetime.fromisoformat(value).astimezone()
    except (TypeError, ValueError):
        return None


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as out:
            name = out.name
            out.write(text)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def copy_assets(board_dir):
    board = Path(board_dir)
    board.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "app.js", "style.css"):
        shutil.copyfile(ROOT / "web" / name, board / name)
    shutil.copyfile(ROOT / "README.md", board / "README.md")


def read_jsonl(path, warnings=None):
    records, bad = [], 0
    try:
        with Path(path).open(encoding="utf-8", errors="replace") as src:
            for line in src:
                try:
                    records.append(json.loads(line))
                except (ValueError, TypeError):
                    bad += 1
    except FileNotFoundError:
        pass
    except OSError:
        if warnings is not None:
            warnings.append(f"Could not read {Path(path).name}.")
    if bad and warnings is not None:
        warnings.append(f"Skipped {bad} invalid lines in {Path(path).name}.")
    return records


def handoff_path(cfg, value):
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path(cfg["aos_repo"]).expanduser() / path


def host_state():
    host = dict(zip(("load1", "load5", "load15"), os.getloadavg()))
    host.update(ncpu=os.cpu_count() or 1, mem_total_mb=0, mem_avail_mb=0)
    try:
        memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        host.update(mem_total_mb=int(memory["MemTotal"].split()[0]) / 1024,
                    mem_avail_mb=int(memory["MemAvailable"].split()[0]) / 1024)
    except (OSError, KeyError, ValueError):
        pass
    candidates = {"codex": {}, "claude": {}}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            args = (entry / "cmdline").read_bytes().split(b"\0")
            name = os.path.basename(os.fsdecode(args[0]))
            if name.startswith("node") and len(args) > 1:
                name = os.path.basename(os.fsdecode(args[1]))
            if name == "codex" and b"app-server" in args:
                continue  # resident app-server daemon, not a working codex line
            if name in candidates:
                parent = int((entry / "stat").read_text().rsplit(")", 1)[1].split()[1])
                candidates[name][int(entry.name)] = parent
        except (OSError, ValueError, IndexError):
            continue
    for name, processes in candidates.items():
        host[name + "_procs"] = sum(parent not in processes for parent in processes.values())
    return host


def handoff_state(cfg, line):
    if not line.get("handoff"):
        return None
    path = handoff_path(cfg, line["handoff"])
    result = {"path": str(path), "exists": False, "mtime": None, "updated_line": None}
    try:
        result.update(exists=path.is_file(), mtime=dt.datetime.fromtimestamp(
            path.stat().st_mtime).astimezone().isoformat(timespec="seconds"))
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        updated = next((row for row in content if "更新時間" in row), None)
        if updated is None:
            updated = next((row for row in content if row.startswith("## ")), None)
        if updated is not None:
            result["updated_line"] = updated.replace("**", "").replace("`", "").strip()[:200]
    except OSError:
        pass
    return result


def line_state(line, events, cfg, now):
    ordered = sorted(events, key=lambda event: parse_ts(event["ts"]))
    latest = ordered[-1] if ordered else None
    handoff = handoff_state(cfg, line)
    timestamps = [event["ts"] for event in ordered[-1:]]
    if handoff and handoff["mtime"]:
        timestamps.append(handoff["mtime"])
    last = max(timestamps, key=parse_ts) if timestamps else None
    doing = next((event["text"] for event in reversed(ordered)
                  if event["status"] in {"start", "progress", "handoff", "done"}), "")
    return {"id": line["id"], "title": line.get("title", line["id"]),
            "status": latest["status"] if latest else "none", "doing": doing,
            "last_ts": last, "stale": bool(last and (now - parse_ts(last)).total_seconds()
                                                 > cfg.get("stale_after_min", 120) * 60),
            "events": list(reversed(ordered[-8:])),
            "timeline": [[event["ts"], event["status"]] for event in ordered
                         if now - dt.timedelta(hours=24) <= parse_ts(event["ts"]) <= now],
            "decisions": [event for event in reversed(ordered) if event["status"] == "decision"
                          and now - dt.timedelta(hours=48) <= parse_ts(event["ts"]) <= now],
            "blocked": latest if latest and latest["status"] == "blocked" else None,
            "handoff": handoff}


def git_commits(cfg, warnings):
    commits = []
    for repo in cfg.get("repos", []):
        try:
            result = subprocess.run(["git", "-C", str(Path(repo["path"]).expanduser()), "log",
                                     "-10", "--format=%h%x09%cI%x09%s"], capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=10,
                                    check=True)
            for row in result.stdout.splitlines():
                commit_hash, stamp, subject = row.split("\t", 2)
                commits.append({"repo": repo["name"], "hash": commit_hash,
                                "ts": stamp, "subject": subject})
        except (OSError, ValueError, subprocess.SubprocessError):
            warnings.append(f"Git log failed for repository {repo['name']}; skipped repository.")
    return sorted(commits, key=lambda item: parse_ts(item["ts"]) or dt.datetime.min.astimezone(),
                  reverse=True)


def summary_stamp(path):
    match = re.match(r"<!-- summary (\S+) model=", path.read_text(encoding="utf-8"))
    return match[1] if match else dt.datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def summary_state(board, cfg, now, warnings):
    folder, options = board / "summary", cfg.get("summary", {})
    latest, stamp, history = "", None, []
    try:
        latest = (folder / "latest.md").read_text(encoding="utf-8")
        stamp = summary_stamp(folder / "latest.md")
    except OSError:
        pass
    for path in (folder / "history").glob("*.md"):
        try:
            history.append({"ts": summary_stamp(path), "file": str(path.relative_to(board))})
        except OSError:
            continue
    history.sort(key=lambda item: parse_ts(item["ts"]) or now, reverse=True)
    costs = [item for item in read_jsonl(folder / "cost.jsonl", warnings) if isinstance(item, dict)]
    today = [item for item in costs if parse_ts(item.get("ts"))
             and parse_ts(item["ts"]).date() == now.date()]
    next_ts = None
    try:
        cursor = json.loads((folder / "cursor.json").read_text(encoding="utf-8"))
        last_run = parse_ts(cursor.get("last_run"))
        if last_run:
            next_ts = (last_run + dt.timedelta(minutes=options.get("min_interval_min", 15))).isoformat(timespec="seconds")
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return {"enabled": bool(options.get("enabled", False)), "latest_md": latest,
            "latest_ts": stamp, "history": history[:30],
            "cost": {"runs_today": len(today),
                     "tokens_today": sum(item.get("total_tokens", 0) for item in today
                                         if isinstance(item.get("total_tokens"), (int, float))),
                     "seconds_today": sum(item.get("seconds", 0) for item in today
                                          if isinstance(item.get("seconds"), (int, float))),
                     "last": costs[-1] if costs else None},
            "next_eligible_ts": next_ts, "running": False}


def collect(board_dir, cfg):
    board, warnings = Path(board_dir), []
    copy_assets(board)
    now = dt.datetime.now().astimezone()
    grouped, bad = {}, 0
    for event in read_jsonl(board / "data/progress.jsonl", warnings):
        if (not isinstance(event, dict) or not isinstance(event.get("line"), str)
                or not isinstance(event.get("status"), str) or event["status"] not in STATUSES
                or not parse_ts(event.get("ts"))
                or not isinstance(event.get("text"), str)
                or not isinstance(event.get("links"), list)
                or not all(isinstance(link, str) for link in event["links"])):
            bad += 1
            continue
        grouped.setdefault(event["line"], []).append(event)
    if bad:
        warnings.append(f"Skipped {bad} invalid progress records.")
    configured = list(cfg.get("lines", []))
    ids = {line["id"] for line in configured}
    configured += [{"id": name, "title": name} for name in grouped if name not in ids]
    host = host_state()
    history_path = board / "data/load_history.jsonl"
    history = [sample for sample in read_jsonl(history_path, warnings)
               if isinstance(sample, list) and len(sample) == 4]
    history.append([iso_now(), host["load1"], host["mem_avail_mb"], host["codex_procs"]])
    history = history[-720:]
    atomic_write(history_path, "".join(json.dumps(sample, ensure_ascii=False) + "\n"
                                      for sample in history))
    return {"generated_at": now.isoformat(), "server": False,
            "host": host, "load_history": history[-240:],
            "lines": [line_state(line, grouped.get(line["id"], []), cfg, now)
                      for line in configured],
            "commits": git_commits(cfg, warnings), "links": cfg.get("links", []),
            "summary": summary_state(board, cfg, now, warnings), "warnings": warnings}


def write_state(board_dir, state):
    encoded = json.dumps(state, ensure_ascii=False)
    data = Path(board_dir) / "data"
    atomic_write(data / "state.json", encoded + "\n")
    atomic_write(data / "state.js", "window.AOS_STATE = " + encoded + ";\n")


def main():
    usage = "python3 collect.py [--help]"
    if sys.argv[1:]:
        if sys.argv[1:] in (["--help"], ["-h"]):
            print(f"Usage: {usage}\nCollect one static progress board snapshot.")
            return 0
        code = "FlagUnknown" if sys.argv[1].startswith("-") else "CommandUnknown"
        print(f"collect: error: {code} unexpected argument (usage: {usage})", file=sys.stderr)
        return 1
    try:
        board = board_path()
        write_state(board, collect(board, load_config()))
        print(board / "index.html")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        reason = " ".join(str(error).splitlines())
        print(f"collect: error: CollectFailed {reason} (usage: {usage})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
