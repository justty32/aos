# Compact agent-fsm conversations while preserving unanswered letters and original messages.
import datetime
import json
import os

from atomic_file import write_atomic
from aos.agentlib import tool_clear

ASK_PREFIX = "[aos] compact:"
MIN_ROWS = 4
ASK = ("[aos] compact: your conversation history is about to be replaced by one summary. "
       "Answer now with that summary and nothing else (you have no tools for this one answer). "
       "Write everything you will need to go on: who asked for what (letter names and where to reply), "
       "what is done, what you are in the middle of and the next step, everything still open, "
       "the files and paths that matter, the rules and decisions you must keep following, "
       "your todo and goal if you have them. Tasks you opened with do_task lose their start mark: "
       "a later do_task end will say MarkerMissing and fold nothing, which is expected. "
       "After your answer the messages before it are replaced by it; letters you have not answered "
       "yet stay as they are; the originals are kept in history_removed.jsonl and your summary "
       "is also saved to handoff.md in your stack.")
CONTINUE = ("[aos] compact: done. Go on with the work in progress described in the summary above; "
            "letters you have not answered yet are above.")
CLEARED = (" Before this request, %d old tool outputs were replaced by a one-line placeholder to make this request smaller; "
           "what you said and did about them is still above, and the originals are in history_removed.jsonl.")
SKIP = "compact not needed: only %d messages to fold (it takes at least %d); nothing was folded"


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def is_compact(content):
    if not isinstance(content, str):
        return False, ""
    parts = content.strip().split(None, 1)
    return (True, parts[1].strip() if len(parts) > 1 else "") if parts and parts[0] == "/compact" else (False, "")


def state(stack):
    try:
        with open(os.path.join(stack, "compact.json"), encoding="utf-8") as f:
            row = json.load(f)
        return row if isinstance(row, dict) else {}
    except (OSError, ValueError):
        return {}


def is_ask(row):
    return (row.get("role") == "user" and isinstance(row.get("content"), str)
            and row["content"].startswith(ASK_PREFIX) and row["content"] != CONTINUE)


def asking(stack, history):
    return state(stack).get("phase") == "asked" and any(is_ask(row) for row in history)


def keep_indices(history, pending):
    keep = {i for i, row in enumerate(history) if row.get("role") == "user"
            and isinstance(row.get("aos"), dict) and row["aos"].get("letter") in pending}
    for i in range(len(history) - 1, -1, -1):
        row = history[i]
        if row.get("role") != "user":
            break
        if not str(row.get("content", "")).startswith("[aos] summary:"):
            keep.add(i)
    return keep


def is_skip(row):
    aos = row.get("aos")
    return row.get("role") == "assistant" and isinstance(aos, dict) and aos.get("skipped") is True


def foldable(stack, history, aos_ws):
    # Answers to too-short /compact letters do not count, so repeated /compact letters never fill the threshold themselves.
    keep = keep_indices(history, aos_ws.letters_pending(stack))
    return sum(1 for i, row in enumerate(history) if i not in keep and not is_skip(row))


def skip(stack, history_path, letters, count, aos_ws, die):
    """Too little to fold (user 11-20: treat it as done normally): no brain call, no fold; one assistant answer
    shaped like compact done (answer_to, aos.compact) plus aos.skipped. No mailbox warning, nothing dropped.
    The caller closes the letters (aos-post done) and then calls aos_ws.letters_answered."""
    row = aos_ws.mark_answer({"role": "assistant", "content": SKIP % (count, MIN_ROWS)}, letters)
    row.setdefault("aos", {}).update(compact=True, skipped=True)
    try:
        aos_ws.letters_take(stack, letters)
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:
        die("WriteFailed", "cannot answer the compact letters: %s" % e)


def save_state(stack, row, die):
    write_atomic(os.path.join(stack, "compact.json"), json.dumps(row) + "\n", die)


def clear_old_tools(stack, history_path, warn):
    """Before asking for the summary: old tool outputs become one-line placeholders (tool_clear), originals go to
    history_removed.jsonl (op clear_tools). Read, write a temp file, rename only if history did not change (like fold);
    three tries, then give up clearing (one warning) and summarize as before. Returns (cleared, chars)."""
    for attempt in range(3):
        try:
            before, lines = read_lines(history_path)
            numbered = [(n, line) for n, line in enumerate(lines, 1) if line.strip()]
            history = [parse(line) for _, line in numbered]
        except (OSError, ValueError, UnicodeError) as e:
            warn("compact: old tool outputs not cleared: cannot read history: %s" % e)
            return 0, 0
        new, removed = tool_clear.clear(history)
        if not removed:
            return 0, 0
        changed = {i for i, _ in removed}
        out, k = [], 0
        for n, line in enumerate(lines, 1):
            if k < len(numbered) and numbered[k][0] == n:
                out.append(json.dumps(new[k], ensure_ascii=False) + "\n" if k in changed else line)
                k += 1
            else:
                out.append(line)
        try:
            if replace(stack, history_path, before, "".join(out),
                       [(numbered[i][0], row) for i, row in removed], "clear_tools"):
                return len(removed), sum(len(row["content"]) for _, row in removed)
        except OSError as e:
            warn("compact: old tool outputs not cleared: %s" % e)
            return 0, 0
    warn("compact: old tool outputs not cleared: history kept changing")
    return 0, 0


def ask(stack, history_path, letters, extra, aos_ws, die, mid_turn=False, warn=None):
    cleared, chars = clear_old_tools(stack, history_path, warn or (lambda line: None))
    row = aos_ws.mark_letter({"role": "user", "content": ASK + (CLEARED % cleared if cleared else "") + (
        " Extra instructions from the sender: " + extra if extra else "")}, letters[0] if letters else None)
    try:
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:
        die("WriteFailed", "cannot append compact request: %s" % e)
    save_state(stack, {"phase": "asked", "letters": letters, "asked_at": utc(), "mid_turn": mid_turn,
                       "cleared": cleared, "cleared_chars": chars}, die)


def waiting_letters(box, stage="new"):
    try:
        names = sorted(n for n in os.listdir(os.path.join(box, stage)) if not n.startswith("."))
    except (FileNotFoundError, NotADirectoryError):
        return []
    found = []
    for name in names:
        try:
            with open(os.path.join(box, stage, name, "letter.json"), encoding="utf-8") as f:
                body = json.load(f).get("body")
            if isinstance(body, dict) and body.get("role") == "user":
                yes, extra = is_compact(body.get("content"))
                if yes:
                    found.append((name, extra))
        except (OSError, ValueError, AttributeError):
            continue
    return found


def turn_open(history):
    if not history:
        return False
    if history[-1].get("role") == "user":
        return True
    if history[-1].get("role") != "tool":
        return False
    for i in range(len(history) - 1, -1, -1):
        calls = history[i].get("tool_calls") if history[i].get("role") == "assistant" else None
        if calls:
            ids = {m.get("tool_call_id") for m in history[i + 1:] if m.get("role") == "tool"}
            return all(c.get("id") in ids for c in calls)
    return False


def fingerprint(path):
    stat = os.stat(path)
    return stat.st_size, stat.st_mtime_ns


def read_lines(path):
    before = fingerprint(path)
    with open(path, encoding="utf-8") as f:
        return before, f.readlines()


def parse(line):
    row = json.loads(line)
    if not isinstance(row, dict):
        raise ValueError("history message is not an object")
    return row


def replace(stack, path, before, text, removed, op):
    tmp = os.path.join(os.path.dirname(path), ".history.jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    if fingerprint(path) != before:
        return False
    at = utc()
    with open(os.path.join(stack, "history_removed.jsonl"), "a", encoding="utf-8") as f:
        for number, message in removed:
            f.write(json.dumps({"removed_at": at, "op": op, "line": number,
                                "message": message}, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return True


def give_up(stack, history_path, reason, aos_ws, warn, die):
    rec = state(stack)
    for attempt in range(3):
        try:
            before, lines = read_lines(history_path)
            removed, kept = [], []
            for number, line in enumerate(lines, 1):
                try:
                    row = parse(line)
                except ValueError:
                    kept.append(line)
                    continue
                if is_ask(row):
                    removed.append((number, row))
                else:
                    kept.append(line)
            if not removed or replace(stack, history_path, before, "".join(kept), removed, "compact_failed"):
                break
        except OSError as e:
            die("WriteFailed", "cannot restore history after compact: %s" % e)
    else:
        die("WriteFailed", "history kept changing while removing the compact request")
    try:
        aos_ws.letters_drop(stack, rec.get("letters", []), "failed")
    except OSError as e:
        warn("cannot drop compact letters: %s" % e)
    save_state(stack, {"phase": "failed", "letters": rec.get("letters", []),
                       "failed_at": utc(), "reason": reason}, die)
    warn("compact: gave up: %s" % reason)
    return False


def fold(stack, history_path, message, aos_ws, warn, die):
    def failed(reason):
        return give_up(stack, history_path, reason, aos_ws, warn, die)

    summary = message.get("content")
    if not isinstance(summary, str) or not summary.strip() or message.get("tool_calls"):
        return failed("the brain answered with an empty summary or tool calls")
    summary = summary.strip()
    rec = state(stack)
    letters = rec.get("letters", [])
    for attempt in range(3):
        try:
            before, lines = read_lines(history_path)
            rows = [(i, parse(line)) for i, line in enumerate(lines, 1) if line.strip()]
            history = [m for _, m in rows]
            a = next((i for i in range(len(history) - 1, -1, -1) if is_ask(history[i])), None)
            if a is None:
                return failed("the compact request is missing from history")
            pending = [n for n in aos_ws.letters_pending(stack) if n not in letters]
            keep = keep_indices(history[:a], pending)
            tail = history[a + 1:]
            if tail and tail[0].get("role") == "tool":
                return failed("a tool result follows the compact request")
            removed = [rows[i] for i in range(a + 1) if i not in keep]
            at = utc()
            text = ("[aos] summary: lines 1-%d, %d messages. %s (Compacted by aos at %s; "
                    "the originals are in %s/history_removed.jsonl; a copy of this summary is in "
                    "%s/handoff.md; letters you have not answered yet follow unchanged.)" %
                    (rows[a][0], len(removed), summary, at, stack, stack))
            done = aos_ws.mark_answer({"role": "assistant", "content":
                "compact done: %d messages replaced by the summary above; the originals are in history_removed.jsonl" % len(removed)}, letters)
            done.setdefault("aos", {})["compact"] = True
            new = [{"role": "user", "content": text}, done] + [history[i] for i in sorted(keep)] + tail
            if rec.get("mid_turn"):
                new.append({"role": "user", "content": CONTINUE})
            content = "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in new)
            if replace(stack, history_path, before, content, removed, "compact"):
                break
        except (ValueError, UnicodeError):
            return failed("history contains an invalid message")
        except OSError as e:
            die("WriteFailed", "cannot compact history: %s" % e)
    else:
        return failed("history kept changing during compact")
    try:
        aos_ws.letters_answered(stack, letters)
    except OSError as e:
        warn("cannot mark compact letters answered: %s" % e)
    try:
        with open(os.path.join(stack, "handoff.md"), "a", encoding="utf-8") as f:
            f.write("## compact %s (%d messages)\n\n%s\n" % (at, len(removed), summary))
    except OSError as e:
        warn("cannot append compact summary to handoff.md: %s" % e)
    save_state(stack, {"phase": "done", "letters": letters, "done_at": at, "replaced": len(removed), "kept": len(keep),
                       "summary_chars": len(summary), "cleared": rec.get("cleared", 0),
                       "cleared_chars": rec.get("cleared_chars", 0)}, die)
    return True
