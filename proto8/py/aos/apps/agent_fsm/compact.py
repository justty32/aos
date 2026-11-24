# Compact (/compact) or clear (/clear) agent-fsm conversations, keeping the original messages in history_removed.jsonl.
# Hooks before_compact / after_compact (declared in hooks.json, line top-1121-compact4; the user 11-21 "2.都開":
# adjust, add back, replace): this file keeps their rules itself (the engine aos.hook_run only runs handlers, the user's
# fourth layer). Hooks run in name order and each sees what the earlier ones changed; exit 10 blocks before_compact;
# exit 0 (or 10 on after_compact) with a JSON object on stdout changes the keys in HOOK_POINTS; a failing hook (other exit
# code, timed out, cannot start, bad stdout) is one warning line and the next hook runs, on both points.
# Too-short /compact letters (compact not needed) fire neither point.
# /clear (line top-1121-apiclear) lives here too because it rewrites history the same way (replace): see clear().
import copy
import datetime
import json
import os

from atomic_file import write_atomic
from aos import flags as aos_flags
from aos import hook_run
from aos.agentlib import agent_hooks, tool_clear

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
BLOCKED = "compact blocked by hook %s%s; nothing was folded"
RESTORED = "[aos] restored after compact: "
CLEAR = "/clear"
CLEARED_NOTE = "/clear: %d messages moved to history_removed.jsonl; the next message starts a new conversation"   # eca's words
# The rules of the two points (py/tests/test_hook_points_match.py compares them with hooks.json): block = exit 10 blocks;
# change = the keys a hook's stdout may set.
HOOK_POINTS = {
    "before_compact": {"field": None, "block": True, "change": ("instructions", "clear", "summary", "restore")},
    "after_compact": {"field": None, "block": False, "change": ("summary", "restore")},
}
CHANGE_OK = {
    "instructions": (lambda v: isinstance(v, str), "a string"),
    "clear": (lambda v: isinstance(v, bool), "true or false"),
    "summary": (lambda v: isinstance(v, str) and bool(v.strip()), "a non-empty string"),
    "restore": (lambda v: v is None or isinstance(v, str), "a string or null"),
}


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
    _answer(stack, history_path, letters, SKIP % (count, MIN_ROWS), {}, aos_ws, die)


def blocked(stack, history_path, letters, plan, aos_ws, die):
    """before_compact blocked it (idle): nothing cleared or folded, no brain call; one answer shaped like skip with
    aos.blocked = the hook's name and the hook's stdout in the text. The caller closes the letters as for skip."""
    text = plan["text"].strip()
    _answer(stack, history_path, letters, BLOCKED % (plan["blocked"], (": " + text) if text else ""),
            {"blocked": plan["blocked"]}, aos_ws, die)
    save_state(stack, {"phase": "blocked", "letters": letters, "blocked_at": utc(), "hook": plan["blocked"],
                       "mid_turn": False}, die)


def _answer(stack, history_path, letters, text, more, aos_ws, die):
    row = aos_ws.mark_answer({"role": "assistant", "content": text}, letters)
    row.setdefault("aos", {}).update(dict({"compact": True, "skipped": True}, **more))
    try:
        aos_ws.letters_take(stack, letters)
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:
        die("WriteFailed", "cannot answer the compact letters: %s" % e)


def _hooked(stack, event, die, warn):
    """The entries in effect and the names hooked on event (the agent's hookeds lists, stack copy on top)."""
    H = agent_hooks.open(os.environ.get("AOS_CD") or ".", stack, fail=die, warn=warn)
    entries = H.load()
    return entries, hook_run.names(entries, event)


def run_hooks(event, data, stack, die, warn, hooked=None):
    """Run the hooks on event (before_compact / after_compact) with this file's rules (see the top of the file).
    Returns (data after the hooks, the blocking hook's name or None, its stdout, {key: name of the last hook that set it})."""
    point = HOOK_POINTS[event]
    entries, names = hooked or _hooked(stack, event, die, warn)
    data, setters = copy.deepcopy(data), {}
    for name in names:
        r = hook_run.run(name, entries[name], event, data, stack)
        try:
            if r["error"]:
                raise ValueError(r["error"])
            if r["code"] == hook_run.BLOCK and point["block"]:
                return data, name, r["stdout"], setters
            if r["code"] not in (0, hook_run.BLOCK):
                raise ValueError("exited %d" % r["code"])
            got = {}
            if r["stdout"].strip():
                try:
                    reply = json.loads(r["stdout"])
                except ValueError as e:
                    raise ValueError("stdout is not JSON: %s" % e) from None
                if not isinstance(reply, dict):
                    raise ValueError("stdout is not a JSON object")
                for key in point["change"]:
                    if key in reply:
                        ok, what = CHANGE_OK[key]
                        if not ok(reply[key]):
                            raise ValueError("%s in stdout must be %s" % (key, what))
                        got[key] = reply[key]
        except ValueError as e:
            warn("hook %s (event %s) failed: %s; going on without it" % (name, event, e))
            continue
        for key, v in got.items():
            data[key] = v.strip() if key == "summary" else v
            setters[key] = name
    return data, None, "", setters


def before(stack, letters, asked, count, die, warn, mid_turn=False):
    """Fire before_compact once the letters are enough to fold (idle, or brain in the middle of a turn). Returns the plan:
    {"blocked": hook name or None, "text": its stdout, "instructions", "clear", "summary": None or the hook's,
    "restore": None or text, "by": "brain" or the name of the hook that gave the summary}. No hook = the plain plan."""
    plan = {"blocked": None, "text": "", "instructions": asked, "clear": True, "summary": None, "restore": None, "by": "brain"}
    hooked = _hooked(stack, "before_compact", die, warn)
    if not hooked[1]:
        return plan
    data = {"letters": list(letters), "asked": asked, "instructions": asked, "mid_turn": mid_turn, "foldable": count,
            "clear": True, "summary": None, "restore": None}
    data, hook, text, setters = run_hooks("before_compact", data, stack, die, warn, hooked)
    if hook:
        return dict(plan, blocked=hook, text=text)
    plan.update({k: data[k] for k in ("instructions", "clear", "summary", "restore")})
    if plan["summary"]:
        plan["by"] = setters.get("summary", "brain")
    return plan


def after(stack, rec, summary, die, warn):
    """Fire after_compact before history is rewritten. Returns (summary, restore text or None)."""
    restore = rec.get("restore") if isinstance(rec.get("restore"), str) else None
    hooked = _hooked(stack, "after_compact", die, warn)
    if not hooked[1]:
        return summary, restore
    data = {"letters": rec.get("letters", []), "summary": summary, "by": rec.get("by", "brain"),
            "mid_turn": bool(rec.get("mid_turn")), "cleared": rec.get("cleared", 0), "restore": restore}
    data, _, _, _ = run_hooks("after_compact", data, stack, die, warn, hooked)
    return data["summary"], data["restore"]


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


def ask(stack, history_path, letters, extra, aos_ws, die, mid_turn=False, warn=None, plan=None):
    """Add the request (after clearing old tool outputs, unless the plan from before() says clear false or gives a summary)
    and record phase asked. Returns the summary a before_compact hook gave (the caller folds it with fold() after closing
    the letters; the brain is not asked), or None."""
    plan = plan or {"instructions": extra, "clear": True, "summary": None, "restore": None, "by": "brain"}
    given = plan["summary"]
    if plan["clear"] and not given:
        cleared, chars = clear_old_tools(stack, history_path, warn or (lambda line: None))
    else:
        cleared, chars = 0, 0
    words = plan["instructions"]
    lead = " Extra instructions from the sender: " if words == extra else " Extra instructions: "
    row = aos_ws.mark_letter({"role": "user", "content": ASK + (CLEARED % cleared if cleared else "") + (
        lead + words if words else "")}, letters[0] if letters else None)
    try:
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:
        die("WriteFailed", "cannot append compact request: %s" % e)
    rec = {"phase": "asked", "letters": letters, "asked_at": utc(), "mid_turn": mid_turn,
           "cleared": cleared, "cleared_chars": chars, "by": plan["by"] if given else "brain"}
    if isinstance(plan["restore"], str):
        rec["restore"] = plan["restore"]
    save_state(stack, rec, die)
    return given


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
        for number, message in removed:                  # a str = a line that is not a JSON object (kept as raw, like aos-agent history)
            f.write(json.dumps({"removed_at": at, "op": op, "line": number,
                                "raw" if isinstance(message, str) else "message": message}, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return True


def is_clear(content):
    """A /clear letter: the content, stripped, is exactly /clear (nothing after it, unlike /compact)."""
    return isinstance(content, str) and content.strip() == CLEAR


def clear(stack, history_path, letter, content, aos_ws, die):
    """/clear (line top-1121-apiclear, as eca does it): every message in history moves to history_removed.jsonl
    (op clear, one row per message, numbered like aos-agent history), and history becomes this exchange only:
    the /clear letter (aos.letter) and one answer CLEARED (aos.answer_to, aos.clear). No brain call, no hooks.
    Written like fold: a temp file renamed only if history did not change, three tries. Returns how many moved.
    The caller records the letter as taken before and closes it (aos-post done, letters_answered) after."""
    rows = [aos_ws.mark_letter({"role": "user", "content": content}, letter)]
    for attempt in range(3):
        try:
            try:
                before, lines = read_lines(history_path)
            except FileNotFoundError:
                before, lines = None, []
            removed = []
            for number, line in enumerate((l for l in lines if l.strip()), 1):
                try:
                    removed.append((number, parse(line)))
                except (ValueError, UnicodeError):
                    removed.append((number, line.rstrip("\n")))
            done = aos_ws.mark_answer({"role": "assistant", "content": aos_flags.aos_note("slash", CLEARED_NOTE % len(removed))}, [letter])
            done.setdefault("aos", {})["clear"] = True
            text = "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in rows + [done])
            if before is None:
                write_atomic(history_path, text, die)
                return 0
            if replace(stack, history_path, before, text, removed, "clear"):
                return len(removed)
        except OSError as e:
            die("WriteFailed", "cannot clear history: %s" % e)
    die("WriteFailed", "history kept changing while clearing it")


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
    summary, restore = after(stack, rec, summary, die, warn)      # after_compact: may change the summary, give restore
    restored = [{"role": "user", "content": RESTORED + restore.strip()}] if restore and restore.strip() else []
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
            new = [{"role": "user", "content": text}] + restored + [done] + [history[i] for i in sorted(keep)] + tail
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
                       "cleared_chars": rec.get("cleared_chars", 0), "by": rec.get("by", "brain"),
                       "restored_chars": len(restored[0]["content"]) - len(RESTORED) if restored else 0}, die)
    return True
