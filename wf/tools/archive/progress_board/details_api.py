"""Serve read-only progress details, filtered commits, process information, and allowed files."""

import glob
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import parse_qs, urlsplit

from codex_api import codex_processes
from collect import handoff_path, load_config, parse_ts
from safe_files import ApiError, file_payload, safe_read


def _repo(cfg, name):
    match = next((repo for repo in cfg.get("repos", []) if repo["name"] == name), None)
    if match is None:
        raise ApiError(400, "RepoUnknown", "repo must name a configured repository")
    return str(Path(match["path"]).expanduser())


def _git(path, args):
    try:
        result = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=10, check=True)
        return result.stdout
    except subprocess.CalledProcessError:
        raise ApiError(404, "GitMissing", "Requested git data was not found") from None
    except (OSError, subprocess.TimeoutExpired):
        raise ApiError(400, "GitFailed", "Git command could not complete") from None


def line_commits(cfg, line, cache=None):
    commits = {}
    for rule in line.get("commit_filters", []):
        try:
            path = _repo(cfg, rule.get("repo"))
            args = ["log", "-n", "30", "--format=%h%x09%cI%x09%s"]
            if rule.get("path"):
                args += ["--", rule["path"]]
            key = (path, tuple(args))
            if cache is None:
                rows = _git(path, args).splitlines()
            else:
                if key not in cache:
                    cache[key] = _git(path, args).splitlines()
                rows = cache[key]
        except ApiError:
            continue
        for row in rows:
            parts = row.split("\t", 2)
            if len(parts) != 3:
                continue
            commit_hash, timestamp, subject = parts
            if rule.get("grep") and rule["grep"].casefold() not in subject.casefold():
                continue
            commits[(rule["repo"], commit_hash)] = {"repo": rule["repo"], "hash": commit_hash,
                                                    "ts": timestamp, "subject": subject}
    return sorted(commits.values(), key=lambda item: _seconds(item["ts"]), reverse=True)[:40]


def _seconds(value):
    stamp = parse_ts(value)
    return stamp.timestamp() if stamp else 0


def line_detail(board, cfg, line_id):
    line = next((item for item in cfg.get("lines", []) if item["id"] == line_id), None)
    events = []
    path = Path(board) / "data/progress.jsonl"
    try:
        # The timeline is deliberately unbounded: every posted event is returned.
        content = safe_read(cfg, path, path.stat().st_size)["text"]
    except (FileNotFoundError, ApiError) as exc:
        if isinstance(exc, ApiError) and exc.status != 404:
            raise
        content = ""
    for row in content.splitlines():
        try:
            value = json.loads(row)
        except ValueError:
            continue
        if isinstance(value, dict) and value.get("line") == line_id:
            events.append(value)
    if line is None and not events:
        raise ApiError(404, "LineUnknown", "id does not identify an existing line")
    line = line or {"id": line_id, "title": line_id}
    handoff = None
    if line.get("handoff"):
        try:
            handoff = file_payload(safe_read(cfg, handoff_path(cfg, line["handoff"]), 300 * 1024))
        except ApiError as exc:
            if exc.status != 404:
                raise
    return {"ok": True, "line": {"id": line_id, "title": line.get("title", line_id)},
            "events": sorted(events, key=lambda item: _seconds(item.get("ts"))),
            "handoff": handoff, "commits": line_commits(cfg, line)}


def commit_detail(cfg, repo, commit_hash):
    path = _repo(cfg, repo)
    if not re.fullmatch(r"[0-9a-f]{4,40}", commit_hash):
        raise ApiError(400, "HashBad", "hash must contain 4 to 40 lowercase hexadecimal digits")
    output = _git(path, ["show", "--no-color", "--format=%H%x09%cI%x09%an%x09%s",
                         "--name-status", commit_hash])
    rows = output.splitlines()
    header = rows[0].split("\t", 3) if rows else []
    if len(header) != 4:
        raise ApiError(404, "CommitMissing", "Commit metadata was not found")
    files = []
    for row in rows[1:]:
        parts = row.split("\t", 1)
        if len(parts) == 2:
            files.append({"status": parts[0], "path": parts[1]})
    return {"ok": True, "hash": header[0], "ts": header[1], "author": header[2],
            "subject": header[3], "files": files[:300], "truncated": len(files) > 300}


def reports(cfg):
    found = {}
    for pattern in cfg.get("report_globs", []):
        for path in glob.iglob(os.path.expanduser(pattern)):
            try:
                value = safe_read(cfg, path, 0)
            except ApiError:
                continue
            path = Path(value["path"])
            found[str(path)] = {"path": str(path), "name": path.name, "dir": str(path.parent),
                                "mtime": value["mtime"], "size": value["size"]}
    return sorted(found.values(), key=lambda value: _seconds(value["mtime"]), reverse=True)[:200]


def dispatch(board, cfg, url):
    """Return one endpoint payload, raising ApiError with an HTTP status on refusal."""
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)

    def parameter(name):
        values = query.get(name, [])
        if len(values) != 1 or not values[0]:
            raise ApiError(400, "QueryBad", f"Exactly one nonempty {name} is required")
        return values[0]

    if parsed.path == "/api/line":
        return line_detail(board, cfg, parameter("id"))
    if parsed.path == "/api/commit":
        return commit_detail(cfg, parameter("repo"), parameter("hash"))
    if parsed.path == "/api/codex":
        return {"ok": True, "processes": codex_processes(cfg)}
    if parsed.path == "/api/reports":
        return {"ok": True, "reports": reports(cfg)}
    if parsed.path == "/api/file":
        path = parameter("path")
        if not Path(path).is_absolute():
            raise ApiError(400, "PathBad", "path must be absolute")
        try:
            value = safe_read(cfg, path, 512 * 1024)
        except ApiError as exc:
            raise ApiError(403, "FileRefused", str(exc)) from None
        return {"ok": True, **file_payload(value)}
    raise ApiError(404, "PathUnknown", "Unknown GET endpoint")


class DetailHandlerMixin:
    def do_GET(self):
        if urlsplit(self.path).path.startswith("/api/"):
            try:
                port = self.server.server_port
                if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                    raise ApiError(403, "HostBad", "Host must name this loopback server")
                payload = dispatch(self.board, load_config(), self.path)
                status = 200
            except ApiError as exc:
                status, payload = exc.status, {"ok": False, "error": str(exc)}
            except (OSError, ValueError):
                status, payload = 400, {"ok": False, "error": "ReadFailed Could not read detail data"}
            self.answer_json(status, payload)
            return
        super().do_GET()
