"""Export board and forum snapshots for the phone artifact and write pulled artifact answers back locally."""

import argparse
import datetime as dt
import fcntl
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BOARD = Path(os.environ.get("AOS_PROGRESS_DIR", "~/Desktop/aos-進度")).expanduser()
DATA = BOARD / "data"
FORUM = DATA / "forum" / "forum.jsonl"
SEEN = DATA / "remote_seen.json"
DECIDE_GLOBS = ["proto8/thinking/**/decide_*.json", "wf/**/decide_*.json"]
OPEN_STATES = ("", "missing", "pending")
DECISION_HOURS = 36


def fail(code, reason):
    print(f"remote_sync: error: {code} {reason}", file=sys.stderr)
    sys.exit(1)


def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def parse_ts(value):
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone()
    except (TypeError, ValueError):
        return None


def read_jsonl(path):
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except FileNotFoundError:
        pass
    return out


def append_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()
        fcntl.flock(stream, fcntl.LOCK_UN)


def fold_forum(events):
    """Fold forum.jsonl events into posts with replies and flags."""
    posts = {}
    for ev in events:
        kind = ev.get("type")
        if kind == "post" and ev.get("id"):
            posts[ev["id"]] = {"id": ev["id"], "title": ev.get("title", ""), "author": ev.get("author", ""),
                               "ts": ev.get("ts", ""), "tags": ev.get("tags", []), "body": ev.get("body", ""),
                               "source_path": ev.get("source_path", ""), "featured": False, "pinned": False,
                               "deleted": False, "replies": [], "last_ts": ev.get("ts", "")}
        elif kind == "reply" and ev.get("post") in posts:
            post = posts[ev["post"]]
            post["replies"].append({"id": ev.get("id", ""), "author": ev.get("author", ""), "ts": ev.get("ts", ""),
                                    "body": ev.get("body", ""), "deleted": False})
            post["last_ts"] = ev.get("ts", post["last_ts"])
        elif kind == "edit" and ev.get("post") in posts:
            for key in ("title", "body", "tags", "source_path"):
                if key in ev:
                    posts[ev["post"]][key] = ev[key]
        elif kind == "admin" and ev.get("post") in posts:
            action, post = ev.get("action"), posts[ev["post"]]
            flags = {"feature": ("featured", True), "unfeature": ("featured", False), "pin": ("pinned", True),
                     "unpin": ("pinned", False), "delete": ("deleted", True), "restore": ("deleted", False)}
            if action in flags and not ev.get("reply"):
                post[flags[action][0]] = flags[action][1]
            elif action in ("delete", "restore") and ev.get("reply"):
                for reply in post["replies"]:
                    if reply["id"] == ev["reply"]:
                        reply["deleted"] = action == "delete"
    return posts


def open_decide_rows():
    rows = []
    for pattern in DECIDE_GLOBS:
        for path in sorted(REPO.glob(pattern)):
            try:
                table = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if table.get("kind") != "decide-page/1":
                continue
            for row in table.get("rows", []):
                if row.get("answer_state", "") not in OPEN_STATES:
                    continue
                options = [{"key": o.get("key", ""), "text": f"{o.get('key', '')}：{o.get('label', '')}"
                            + (f"（{o['consequence']}）" if o.get("consequence") else "")} for o in row.get("options", [])]
                rows.append({"id": f"decide:{table.get('batch')}:{row.get('id')}", "line": table.get("line", ""),
                             "batch": table.get("batch", ""), "question": row.get("question", ""),
                             "eli5": row.get("eli5", ""), "options": options, "recommend": row.get("recommend") or None,
                             "why": row.get("why", ""), "details": [str(d) for d in row.get("details", [])][:6],
                             "ts": table.get("extracted", ""), "decide_file": str(path.relative_to(REPO))})
    return rows


def export(out):
    out = Path(out)
    (out / "snap").mkdir(parents=True, exist_ok=True)
    (out / "posts").mkdir(parents=True, exist_ok=True)
    try:
        state = json.loads((DATA / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        fail("StateBad", f"cannot read state.json: {error}")
    cutoff = dt.datetime.now().astimezone() - dt.timedelta(hours=DECISION_HOURS)
    lines, decisions, blocked = [], [], []
    for line in state.get("lines", []):
        title = line.get("title") or line.get("id")
        lines.append({"id": line.get("id"), "title": title, "status": line.get("status"),
                      "doing": line.get("doing", ""), "last_ts": line.get("last_ts", "")})
        for ev in line.get("events", []):
            ts = parse_ts(ev.get("ts"))
            if ev.get("status") == "decision" and ts and ts >= cutoff:
                decisions.append({"line": line.get("id"), "line_title": title, "text": ev.get("text", ""), "ts": ev.get("ts")})
        if line.get("blocked"):
            blocked.append({"line": line.get("id"), "line_title": title, "text": line["blocked"].get("text", "")})
    lines.sort(key=lambda l: l.get("last_ts") or "", reverse=True)
    decisions.sort(key=lambda d: d["ts"] or "", reverse=True)
    summary_md, overview = "", ""
    try:
        summary_md = (BOARD / "summary" / "latest.md").read_text(encoding="utf-8")
        parts = summary_md.split("## 一句話總覽", 1)
        if len(parts) == 2:
            overview = parts[1].strip().split("\n\n", 1)[0].strip()
    except OSError:
        pass
    summary = state.get("summary") or {}
    board = {"generated_at": now_iso(), "summary_at": summary.get("latest_ts", ""), "overview": overview,
             "lines": lines, "decisions": decisions[:30], "blocked": blocked, "summary_md": summary_md[:60000]}
    asks = []
    for ask in state.get("asks", []):
        if ask.get("answer"):
            continue
        eli5 = ask.get("eli5")
        asks.append({"id": ask["id"], "line": ask.get("line", ""), "question": ask.get("text", ""),
                     "eli5": eli5.get("text", "") if isinstance(eli5, dict) else (eli5 or ""),
                     "options": ask.get("options", []), "recommend": ask.get("recommend"), "ts": ask.get("ts", ""),
                     "details": [str(link) for link in ask.get("links", [])]})
    asks += open_decide_rows()
    posts = fold_forum(read_jsonl(FORUM))
    listing = []
    for post in posts.values():
        replies = [r for r in post["replies"] if not r["deleted"]]
        excerpt = " ".join(post["body"].replace("#", "").split())[:90]
        listing.append({"id": post["id"], "title": post["title"], "author": post["author"], "ts": post["ts"],
                        "last_ts": post["last_ts"], "tags": post["tags"], "featured": post["featured"],
                        "pinned": post["pinned"], "deleted": post["deleted"], "replies": len(replies), "excerpt": excerpt})
    writes = []

    def put(collection, doc_id, body):
        path = out / collection / f"{doc_id}.json"
        path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        writes.append({"op": "set", "collection": collection, "doc_id": doc_id, "file_path": str(path)})

    put("snap", "board", board)
    put("snap", "asks", {"generated_at": now_iso(), "items": asks})
    try:
        synced = sorted(json.loads(SEEN.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        synced = []
    put("snap", "forum", {"generated_at": now_iso(), "posts": listing, "synced_inbox": synced})
    for post in posts.values():
        if post["deleted"]:
            writes.append({"op": "delete", "collection": "posts", "doc_id": post["id"]})
            continue
        body = dict(post, replies=[r for r in post["replies"] if not r["deleted"]])
        put("posts", post["id"], body)
    batches = [writes[i:i + 50] for i in range(0, len(writes), 50)]
    (out / "writes.json").write_text(json.dumps(batches, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"out": str(out), "asks": len(asks), "lines": len(lines), "posts": len(listing),
                      "batches": len(batches), "writes_file": str(out / "writes.json")}, ensure_ascii=False))


def pull(src, dry):
    inbox = Path(src) / "inbox"
    if not inbox.is_dir():
        fail("InboxMissing", f"{inbox} not found; run read_db list on collection inbox with out_dir {src}")
    try:
        seen = set(json.loads(SEEN.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        seen = set()
    docs = []
    for path in sorted(inbox.glob("*.json")):
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        body = body.get("data", body) if isinstance(body.get("data"), dict) else body
        docs.append((path.stem, body))
    docs.sort(key=lambda item: str(item[1].get("ts", "")))
    answers, forum, decide, report = [], [], {}, []
    local_ts = now_iso()
    for doc_id, body in docs:
        if doc_id in seen:
            continue
        kind, target = body.get("kind"), body.get("target", "")
        ts = body.get("ts", "")
        if kind == "answer" and target.startswith("decide:"):
            _, batch, row = target.split(":", 2)
            choice = body.get("choice") or "-"
            note = body.get("comment", "").replace("\n", " / ")
            decide.setdefault(batch, {})[row] = f"{row}:{choice}" + (f"（備註：{note}）" if note else "")
            report.append(f"decide {batch} {row} -> {choice}")
        elif kind == "answer":
            answers.append({"ts": local_ts, "id": target, "line": body.get("line", ""), "choice": body.get("choice"),
                            "comment": (body.get("comment") or "") + f"（手機看板 {ts}）".strip(), "via": "artifact"})
            report.append(f"answer {target} -> {body.get('choice')}")
        elif kind == "reply":
            forum.append({"ts": ts or local_ts, "type": "reply", "id": f"r-artifact-{doc_id}", "post": target,
                          "author": "user", "body": body.get("body", ""), "via": "artifact"})
            report.append(f"reply on {target}")
        elif kind == "post":
            forum.append({"ts": ts or local_ts, "type": "post", "id": f"p-artifact-{doc_id}", "title": body.get("title", ""),
                          "author": "user", "tags": ["使用者"], "body": body.get("body", ""), "via": "artifact"})
            report.append(f"post {body.get('title', '')}")
        else:
            report.append(f"skip {doc_id}: unknown kind {kind}")
        seen.add(doc_id)
    decide_files = {}
    for batch, rows in decide.items():
        line = f"[{batch}] " + "、".join(rows.values())
        path = Path(src) / f"decide_{batch}.txt"
        path.write_text(line + "\n", encoding="utf-8")
        decide_files[batch] = str(path)
    if not dry:
        if answers:
            append_jsonl(DATA / "answers.jsonl", answers)
        if forum:
            append_jsonl(FORUM, forum)
        SEEN.write_text(json.dumps(sorted(seen)), encoding="utf-8")
    print(json.dumps({"dry_run": dry, "answers": len(answers), "forum": len(forum), "decide_reply_files": decide_files,
                      "items": report}, ensure_ascii=False, indent=1))
    batch_files = {}
    for pattern in DECIDE_GLOBS:
        for found in REPO.glob(pattern):
            try:
                batch_files[json.loads(found.read_text(encoding="utf-8")).get("batch")] = found.relative_to(REPO)
            except (OSError, ValueError, AttributeError):
                pass
    for batch, path in decide_files.items():
        target = batch_files.get(batch, f"<decide file of {batch}>")
        print(f"next: python3 wf/tools/decide_page/decide_page.py parse {target} {path}  (then apply)")


def main():
    parser = argparse.ArgumentParser(description="Sync the phone artifact with the local board.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export", help="write snapshot docs and writes.json for write_db batches")
    ex.add_argument("out")
    pl = sub.add_parser("pull", help="write inbox docs saved by read_db back to answers.jsonl and forum.jsonl")
    pl.add_argument("src")
    pl.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.cmd == "export":
        export(args.out)
    else:
        pull(args.src, args.dry_run)


if __name__ == "__main__":
    main()
