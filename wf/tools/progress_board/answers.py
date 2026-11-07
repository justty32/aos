"""Read board questions and answers, validate local submissions, and append locked answers."""

import datetime as dt
import fcntl
import json
from pathlib import Path
import re

MAX_BODY = 8192


def timestamp(value):
    try:
        return dt.datetime.fromisoformat(value).astimezone()
    except (TypeError, ValueError, OverflowError):
        return None


def records(path, warnings=None):
    result, bad = [], 0
    try:
        with Path(path).open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    result.append(json.loads(line))
                except ValueError:
                    bad += 1
    except FileNotFoundError:
        pass
    except OSError:
        if warnings is not None:
            warnings.append(f"Could not read {Path(path).name}.")
    if bad and warnings is not None:
        warnings.append(f"Skipped {bad} invalid lines in {Path(path).name}.")
    return result


def valid_ask(value):
    if not isinstance(value, dict) or value.get("status") != "ask":
        return False
    if (not all(isinstance(value.get(key), str) and value[key]
                for key in ("id", "line", "text")) or not timestamp(value.get("ts"))
            or not isinstance(value.get("links"), list)
            or not all(isinstance(link, str) for link in value["links"])
            or not isinstance(value.get("options"), list)):
        return False
    keys = []
    for option in value["options"]:
        if (not isinstance(option, dict) or not isinstance(option.get("key"), str)
                or not re.fullmatch(r"[A-Za-z0-9]{1,8}", option["key"])
                or not isinstance(option.get("text"), str) or option["key"] in keys):
            return False
        keys.append(option["key"])
    return value.get("recommend") is None or value["recommend"] in keys


def read_asks(board, warnings=None):
    return [value for value in records(Path(board) / "data/progress.jsonl", warnings)
            if valid_ask(value)]


def valid_answer(value):
    return (isinstance(value, dict) and bool(timestamp(value.get("ts")))
            and all(isinstance(value.get(key), str) for key in ("id", "line", "comment"))
            and (value.get("choice") is None or isinstance(value["choice"], str)))


def read_answers(board, warnings=None):
    values = records(Path(board) / "data/answers.jsonl", warnings)
    answers = [value for value in values if valid_answer(value)]
    if len(answers) != len(values) and warnings is not None:
        warnings.append(f"Skipped {len(values) - len(answers)} invalid answer records.")
    return answers


def asks_state(asks, answers, now, titles=None):
    latest = {answer["id"]: answer for answer in answers}
    titles = titles or {}
    result = [{"id": ask["id"], "line": ask["line"],
               "line_title": titles.get(ask["line"], ask["line"]), "ts": ask["ts"],
               "text": ask["text"], "links": ask["links"], "options": ask["options"],
               "recommend": ask.get("recommend"), "answer": latest.get(ask["id"])}
              for ask in asks if now - dt.timedelta(days=7) <= timestamp(ask["ts"]) <= now]
    result.sort(key=lambda ask: (ask["answer"] is None,
                                timestamp((ask["answer"] or ask)["ts"])), reverse=True)
    return result


class AnswerError(Exception):
    def __init__(self, status, code, reason):
        super().__init__(f"{code} {reason}")
        self.status = status


def validate_headers(headers, port):
    if headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
        raise AnswerError(403, "HostBad", "Host must name this loopback server")
    if headers.get("X-AOS-Board") != "1":
        raise AnswerError(403, "BoardHeaderBad", "X-AOS-Board: 1 is required")
    if not headers.get("Content-Type", "").lower().startswith("application/json"):
        raise AnswerError(415, "ContentTypeBad", "Content-Type must be application/json")
    raw_length = headers.get("Content-Length")
    if raw_length is None:
        raise AnswerError(411, "LengthRequired", "Content-Length is required")
    if not re.fullmatch(r"[0-9]+", raw_length):
        raise AnswerError(400, "LengthBad", "Content-Length must be a nonnegative integer")
    normalized = raw_length.lstrip("0") or "0"
    if len(normalized) > 4 or int(normalized) > MAX_BODY:
        raise AnswerError(413, "BodyTooLarge", "Body must not exceed 8192 bytes")
    return int(normalized)


def append_answer(board, body):
    if not isinstance(body, dict) or set(body) != {"id", "choice", "comment"}:
        raise AnswerError(400, "BodyBad", "Body must contain exactly id, choice, comment")
    if not isinstance(body["id"], str):
        raise AnswerError(400, "IdBad", "id must be a string")
    ask = next((ask for ask in reversed(read_asks(board)) if ask["id"] == body["id"]), None)
    if ask is None:
        raise AnswerError(404, "AskUnknown", "id does not identify an existing question")
    choice, comment = body["choice"], body["comment"]
    if choice is not None and (not isinstance(choice, str)
                               or choice not in [option["key"] for option in ask["options"]]):
        raise AnswerError(400, "ChoiceBad", "choice must be null or an option key")
    if not isinstance(comment, str) or len(comment) > 4000:
        raise AnswerError(400, "CommentBad", "comment must be a string of at most 4000 characters")
    if choice is None and not comment.strip():
        raise AnswerError(400, "AnswerEmpty", "Choose an option or enter a nonblank comment")
    answer = {"ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
              "id": ask["id"], "line": ask["line"], "choice": choice, "comment": comment}
    path = Path(board) / "data/answers.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(answer, ensure_ascii=False) + "\n").encode("utf-8")
    with path.open("ab", buffering=0) as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        if stream.write(payload) != len(payload):
            raise OSError("Incomplete answer write")
    return answer


class AnswerHandlerMixin:
    def answer_json(self, status, payload):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        try:
            if self.path != "/api/answer":
                raise AnswerError(404, "PathUnknown", "Unknown POST path")
            length = validate_headers(self.headers, self.server.server_port)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise AnswerError(400, "BodyBad", "Body is shorter than Content-Length")
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeError, RecursionError):
                raise AnswerError(400, "JsonBad", "Body must be valid JSON") from None
            append_answer(self.board, body)
            self.refresh_answers()
            self.answer_json(200, {"ok": True})
        except AnswerError as exc:
            self.answer_json(exc.status, {"ok": False, "error": str(exc)})
        except OSError:
            self.answer_json(500, {"ok": False, "error": "WriteFailed Could not save the answer"})
        except Exception:
            self.answer_json(500, {"ok": False, "error": "RefreshFailed Could not refresh board state"})
