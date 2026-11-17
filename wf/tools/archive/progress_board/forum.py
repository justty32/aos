"""Local forum store: append-only forum.jsonl events, permission table, and the post/admin command-line entry points."""

import datetime as dt
import fcntl
import json
import os
import re
import secrets
import sys
from pathlib import Path

BOARD = Path(os.environ.get("AOS_PROGRESS_DIR", "~/Desktop/aos-進度")).expanduser()
FORUM_DIR = BOARD / "data" / "forum"
EVENTS = FORUM_DIR / "forum.jsonl"
PERMS = FORUM_DIR / "perms.json"
MODERATOR = ["pin", "unpin", "feature", "unfeature", "delete", "restore"]
POST_ACTIONS = set(MODERATOR)
ROOT_ONLY = {"grant", "revoke"}
NAME = re.compile(r"[A-Za-z0-9._-]+")
DEFAULT_PERMS = {"contract": "forum-perms/1", "root": ["top"], "grants": {}}
MAX_BODY = 200000

POST_USAGE = ("forum_post.sh <line> <title> <body-file|-> [--tag TAG ...] [--source PATH]\n"
              "       forum_post.sh <line> --reply <post-id> <body-file|->")
ADMIN_USAGE = ("forum_admin.sh <pin|unpin|feature|unfeature|delete|restore> <post-id> [--reply <reply-id>] --as <line>\n"
               "       forum_admin.sh <grant|revoke> <line> <action|moderator> --as top\n"
               "       forum_admin.sh list [--all] | show <post-id> | perms")


def fail(prog, code, reason, usage):
    print(f"{prog}: error: {code} {reason} (usage: {usage})", file=sys.stderr)
    sys.exit(1)


def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def new_id(prefix):
    return f"{prefix}-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"


def read_events(path=EVENTS):
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, dict):
                    out.append(value)
    except FileNotFoundError:
        pass
    return out


def append_events(records, path=EVENTS):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()
        fcntl.flock(stream, fcntl.LOCK_UN)


def fold(events):
    """Fold forum events into {post_id: post} with replies and flags."""
    posts = {}
    flags = {"feature": ("featured", True), "unfeature": ("featured", False), "pin": ("pinned", True),
             "unpin": ("pinned", False), "delete": ("deleted", True), "restore": ("deleted", False)}
    for ev in events:
        kind, pid = ev.get("type"), ev.get("post")
        if kind == "post" and ev.get("id"):
            posts[ev["id"]] = {"id": ev["id"], "title": ev.get("title", ""), "author": ev.get("author", ""),
                               "ts": ev.get("ts", ""), "tags": ev.get("tags", []), "body": ev.get("body", ""),
                               "source_path": ev.get("source_path", ""), "via": ev.get("via", ""),
                               "featured": False, "pinned": False, "deleted": False, "replies": [],
                               "last_ts": ev.get("ts", "")}
        elif kind == "reply" and pid in posts:
            posts[pid]["replies"].append({"id": ev.get("id", ""), "author": ev.get("author", ""),
                                          "ts": ev.get("ts", ""), "body": ev.get("body", ""),
                                          "via": ev.get("via", ""), "deleted": False})
            posts[pid]["last_ts"] = ev.get("ts", posts[pid]["last_ts"])
        elif kind == "edit" and pid in posts:
            for key in ("title", "body", "tags", "source_path"):
                if key in ev:
                    posts[pid][key] = ev[key]
        elif kind == "admin" and pid in posts and ev.get("action") in flags:
            if ev.get("reply"):
                if ev["action"] in ("delete", "restore"):
                    for reply in posts[pid]["replies"]:
                        if reply["id"] == ev["reply"]:
                            reply["deleted"] = ev["action"] == "delete"
            else:
                key, value = flags[ev["action"]]
                posts[pid][key] = value
    return posts


def load_perms():
    try:
        value = json.loads(PERMS.read_text(encoding="utf-8"))
        if isinstance(value, dict) and isinstance(value.get("grants"), dict):
            value.setdefault("root", ["top"])
            return value
    except (OSError, ValueError):
        pass
    return json.loads(json.dumps(DEFAULT_PERMS))


def save_perms(perms):
    PERMS.parent.mkdir(parents=True, exist_ok=True)
    tmp = PERMS.with_suffix(".tmp")
    tmp.write_text(json.dumps(perms, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, PERMS)


def allowed(perms, who, action, post=None, reply=None):
    if who in perms.get("root", []):
        return True
    if action in ROOT_ONLY:
        return False
    if action in perms.get("grants", {}).get(who, []):
        return True
    # authors may soft-delete or restore their own post or reply
    if action in ("delete", "restore") and post is not None:
        if reply is not None:
            return reply.get("author") == who
        return post.get("author") == who
    return False


def read_body(prog, source, usage):
    try:
        text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    except OSError as error:
        fail(prog, "BodyUnreadable", f"{source}: {error.strerror}", usage)
    if not text.strip():
        fail(prog, "BodyEmpty", "body must be nonblank", usage)
    if len(text) > MAX_BODY:
        fail(prog, "BodyLarge", f"body must be at most {MAX_BODY} characters; post a summary and the source path", usage)
    return text.rstrip() + "\n"


def post_main(args):
    prog, usage = "forum_post", POST_USAGE
    if args and args[0] in ("-h", "--help"):
        print(f"Usage: {usage}\nAppends a post or reply to {EVENTS} and prints its id.")
        return
    if len(args) < 3:
        fail(prog, "ArgumentsBad", "at least three arguments are required", usage)
    line = args[0]
    if not NAME.fullmatch(line):
        fail(prog, "LineBad", "line must contain only A-Z, a-z, 0-9, dot, underscore or hyphen", usage)
    if args[1] == "--reply":
        if len(args) != 4:
            fail(prog, "ArgumentsBad", "reply takes exactly <line> --reply <post-id> <body-file|->", usage)
        pid, body = args[2], read_body(prog, args[3], usage)
        posts = fold(read_events())
        if pid not in posts or posts[pid]["deleted"]:
            fail(prog, "PostMissing", f"no live post {pid}", usage)
        rid = new_id("r")
        append_events([{"ts": now_iso(), "type": "reply", "id": rid, "post": pid, "author": line, "body": body}])
        print(f"forum_post: replied {rid} on {pid}")
        return
    title, source, rest = args[1], args[2], args[3:]
    if title.startswith("-") or not title.strip():
        fail(prog, "TitleBad", "title must be nonblank and not start with '-'", usage)
    tags, source_path = [], ""
    while rest:
        item = rest.pop(0)
        if item in ("--tag", "--source"):
            if not rest or rest[0].startswith("--") or not rest[0].strip():
                fail(prog, "ArgumentsBad", f"{item} requires a value", usage)
            value = rest.pop(0)
            if item == "--tag":
                tags.append(value)
            else:
                source_path = value
        else:
            fail(prog, "FlagUnknown", item, usage)
    body = read_body(prog, source, usage)
    pid = new_id("p")
    append_events([{"ts": now_iso(), "type": "post", "id": pid, "title": title.strip(), "author": line,
                     "tags": tags, "body": body, "source_path": source_path}])
    print(f"forum_post: posted {pid}")


def admin_main(args):
    prog, usage = "forum_admin", ADMIN_USAGE
    if not args or args[0] in ("-h", "--help"):
        print(f"Usage: {usage}\nmoderator = {', '.join(MODERATOR)}. Root lines are listed in {PERMS}.")
        return
    cmd = args[0]
    if cmd == "perms":
        print(json.dumps(load_perms(), ensure_ascii=False, indent=1))
        return
    posts = fold(read_events())
    if cmd == "list":
        show_all = "--all" in args[1:]
        ordered = sorted(posts.values(), key=lambda p: p["last_ts"], reverse=True)
        for post in sorted(ordered, key=lambda p: not p["pinned"]):
            if post["deleted"] and not show_all:
                continue
            marks = "".join(m for m, on in (("P", post["pinned"]), ("F", post["featured"]), ("D", post["deleted"])) if on)
            live = sum(1 for r in post["replies"] if not r["deleted"])
            print(f"{post['id']}\t{marks or '-'}\t{post['author']}\t{post['ts']}\treplies={live}\t{post['title']}")
        return
    if cmd == "show":
        if len(args) != 2 or args[1] not in posts:
            fail(prog, "PostMissing", "show takes one existing post id", usage)
        print(json.dumps(posts[args[1]], ensure_ascii=False, indent=1))
        return
    rest, who, reply_id = list(args[1:]), None, None
    positional = []
    while rest:
        item = rest.pop(0)
        if item in ("--as", "--reply"):
            if not rest:
                fail(prog, "ArgumentsBad", f"{item} requires a value", usage)
            value = rest.pop(0)
            if item == "--as":
                who = value
            else:
                reply_id = value
        elif item.startswith("--"):
            fail(prog, "FlagUnknown", item, usage)
        else:
            positional.append(item)
    if not who or not NAME.fullmatch(who):
        fail(prog, "AsMissing", "--as <line> is required", usage)
    perms = load_perms()
    if cmd in ROOT_ONLY:
        if len(positional) != 2:
            fail(prog, "ArgumentsBad", f"{cmd} takes <line> <action|moderator>", usage)
        target, what = positional
        actions = MODERATOR if what == "moderator" else [what]
        if not NAME.fullmatch(target) or any(a not in POST_ACTIONS for a in actions):
            fail(prog, "ActionBad", f"action must be moderator or one of {', '.join(MODERATOR)}", usage)
        if not allowed(perms, who, cmd):
            fail(prog, "Forbidden", f"{who} may not {cmd}; only root lines {perms.get('root')} may", usage)
        current = perms["grants"].setdefault(target, [])
        if cmd == "grant":
            current.extend(a for a in actions if a not in current)
        else:
            perms["grants"][target] = [a for a in current if a not in actions]
            if not perms["grants"][target]:
                del perms["grants"][target]
        save_perms(perms)
        append_events([{"ts": now_iso(), "type": "perm", "action": cmd, "line": target, "actions": actions, "by": who}])
        print(f"forum_admin: {cmd} {target} {','.join(actions)}")
        return
    if cmd not in POST_ACTIONS:
        fail(prog, "CommandBad", cmd, usage)
    if len(positional) != 1 or positional[0] not in posts:
        fail(prog, "PostMissing", f"{cmd} takes one existing post id", usage)
    post = posts[positional[0]]
    reply = None
    if reply_id is not None:
        if cmd not in ("delete", "restore"):
            fail(prog, "ReplyBad", "--reply works only with delete or restore", usage)
        reply = next((r for r in post["replies"] if r["id"] == reply_id), None)
        if reply is None:
            fail(prog, "ReplyMissing", f"no reply {reply_id} on {post['id']}", usage)
    if not allowed(perms, who, cmd, post, reply):
        fail(prog, "Forbidden", f"{who} may not {cmd}; ask top to grant it", usage)
    event = {"ts": now_iso(), "type": "admin", "action": cmd, "post": post["id"], "by": who}
    if reply_id:
        event["reply"] = reply_id
    append_events([event])
    print(f"forum_admin: {cmd} {post['id']}" + (f" reply {reply_id}" if reply_id else ""))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "post":
        post_main(sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == "admin":
        admin_main(sys.argv[2:])
    else:
        print("forum.py: error: CommandBad use forum_post.sh or forum_admin.sh", file=sys.stderr)
        sys.exit(1)
