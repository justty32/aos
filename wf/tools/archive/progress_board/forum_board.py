"""Build offline forum snapshots and accept validated user posts and replies from the board."""

import json
from pathlib import Path

from answers import AnswerError, timestamp, validate_headers
import forum


def events_path(board):
    return Path(board) / "data/forum/forum.jsonl"


def write_forum(board, atomic_write):
    posts = list(forum.fold(forum.read_events(events_path(board))).values())
    posts.sort(key=lambda post: (timestamp(post["last_ts"]).timestamp()
                                 if timestamp(post["last_ts"]) else 0), reverse=True)
    posts.sort(key=lambda post: not post["pinned"])
    for post in posts:
        post["replies"] = [reply for reply in post["replies"] if not reply["deleted"]]
    encoded = json.dumps({"posts": posts, "perms": forum.load_perms()}, ensure_ascii=False)
    data = Path(board) / "data"
    atomic_write(data / "forum.json", encoded + "\n")
    atomic_write(data / "forum.js", "window.AOS_FORUM = " + encoded + ";\n")


def append_submission(board, kind, body):
    keys = {"post", "body"} if kind == "reply" else {"title", "body"}
    if not isinstance(body, dict) or set(body) != keys:
        raise AnswerError(400, "BodyBad", "Body must contain exactly " + ", ".join(sorted(keys)))
    text = body["body"]
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise AnswerError(400, "BodyBad", "body must be nonblank and at most 20000 characters")
    record = {"ts": forum.now_iso(), "type": kind, "author": "user", "via": "board",
              "id": forum.new_id("r" if kind == "reply" else "p"), "body": text}
    if kind == "reply":
        pid = body["post"]
        if not isinstance(pid, str) or not pid:
            raise AnswerError(400, "PostBad", "post must be a nonblank string")
        post = forum.fold(forum.read_events(events_path(board))).get(pid)
        if post is None:
            raise AnswerError(404, "PostMissing", "post must identify an existing post")
        if post["deleted"]:
            raise AnswerError(409, "PostDeleted", "Deleted posts cannot receive replies")
        record["post"] = pid
    else:
        title = body["title"]
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise AnswerError(400, "TitleBad", "title must be nonblank and at most 200 characters")
        record.update(title=title.strip(), tags=[], source_path="")
    forum.append_events([record], events_path(board))
    return record


class ForumHandlerMixin:
    def do_POST(self):
        if self.path not in ("/api/forum/reply", "/api/forum/post"):
            return super().do_POST()
        try:
            length = validate_headers(self.headers, self.server.server_port)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise AnswerError(400, "BodyBad", "Body is shorter than Content-Length")
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeError, RecursionError):
                raise AnswerError(400, "JsonBad", "Body must be valid JSON") from None
            record = append_submission(self.board, self.path.rsplit("/", 1)[1], body)
            self.refresh_forum()
            self.answer_json(200, {"ok": True, "id": record["id"],
                                   "post": record.get("post", record["id"])})
        except AnswerError as exc:
            self.answer_json(exc.status, {"ok": False, "error": str(exc)})
        except OSError:
            self.answer_json(500, {"ok": False, "error": "WriteFailed Could not save the forum submission"})
        except Exception:
            self.answer_json(500, {"ok": False, "error": "RefreshFailed Could not refresh forum state"})
