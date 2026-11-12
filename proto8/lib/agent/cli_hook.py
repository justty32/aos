# cli_hook.py - cli_session 的畫面 hook（CLI 講完一輪時叫）：跟上對話 id、/clear／/compact 時同步 aos 的 history、codex 壓縮跟上
import json, os, re, sys

if __package__:
    from .cli_base import now
    from .cli_cell import Cell, link_transcript, mark_session, transcripts
else:
    from cli_base import now
    from cli_cell import Cell, link_transcript, mark_session, transcripts


# ---------------------------------------------------------------- hook（互動畫面講完一輪時 CLI 叫的）

def last_text_from_transcript(path):
    """claude 的 transcript（jsonl）裡最後一則 assistant 的文字。"""
    text = ""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                if m.get("type") != "assistant":
                    continue
                content = (m.get("message") or {}).get("content")
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                    if parts:
                        text = "".join(parts)
    except OSError:
        pass
    return text


def follow_session(kind, cell, sid):
    """畫面上的 CLI 現在用的對話 id 跟 session.txt 不同（第一輪、/clear、codex 的 /new 之後、/resume 到別段）＝改記它（11-12 eca-slash：
    CLI 那邊為主，aos 跟上；原本只在 session.txt 空著時寫，/clear 後 aos 還記舊 id，畫面一關就接回清之前的對話）。"""
    if not sid or sid == cell.read("session.txt"):
        return
    ws = cell.read("ws.txt")                       # 記號檔要工作區：從小格的 ws.txt 解相對路徑（不知道就只寫 session.txt，
    if ws:                                         # 下一次 session_here 走過渡補丁補寫）
        mark_session(kind, cell, os.path.normpath(os.path.join(cell.path, ws)), sid)
    else:
        cell.write("session.txt", sid + "\n")


HISTORY, REMOVED = "history.jsonl", "history_removed.jsonl"


def replace_history(cell, op, summary=None, stack=None, keep_tail=False, rows=()):
    """把這隻 eca 的 history 換掉（11-12 eca-slash，使用者「連 aos 那邊的歷史也要一起清」「3.要動，希望能同步」）：history＝小格 stack.txt
    指的 stack 裡的 history.jsonl（工具形 stack＝小格本身、沒有 history＝不動）。被換掉的原文照 aos-agent history rm 的規矩接到旁邊的
    history_removed.jsonl（每則一行 {"removed_at", "op": op, "line", "message"|"raw"}），先寫那份再換 history：
    summary＝None 換成空檔（/clear）；給了＝換成一則 user「[aos] summary: lines 1-N, N messages. 摘要」（/compact，同 history summarize 的格式；
    lib 不 import py，這裡自己拼）；rows＝接在那則之後的訊息（codex 的 /compact：從它壓縮後的 replacement_history 撈出來的對話）。
    keep_tail＝最後一則 assistant 之後的 user（剛交出去、還沒答的那幾則）留著不動。
    刪小格的 .history_sum（aos-eca-turn ⑩ 的記號，沒有＝不比，免得下一輪當成「history 被改過」又丟掉新對話）。回換掉幾則。
    stack＝呼叫者直接給（aos-eca-turn）；沒給＝照 stack.txt（hook）。"""
    if stack is None:
        rel = cell.read("stack.txt")
        stack = os.path.normpath(os.path.join(cell.path, rel)) if rel else cell.path
    stack = os.path.abspath(stack)
    if stack == cell.path:
        return 0
    path = os.path.join(stack, HISTORY)
    try:
        with open(path, encoding="utf-8") as f:
            lines = [l.rstrip("\n") for l in f if l.strip()]
    except FileNotFoundError:
        lines = []
    tail = []
    if keep_tail:
        while lines:
            try:
                last = json.loads(lines[-1])
            except ValueError:
                break
            if not isinstance(last, dict) or last.get("role") != "user":
                break
            tail.insert(0, lines.pop())
    if lines:
        at = now()
        with open(os.path.join(stack, REMOVED), "a", encoding="utf-8") as f:
            for i, l in enumerate(lines, 1):
                try:
                    row = {"removed_at": at, "op": op, "line": i, "message": json.loads(l)}
                except ValueError:
                    row = {"removed_at": at, "op": op, "line": i, "raw": l}
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        head = []
        if summary is not None:
            note = "[aos] summary: lines 1-%d, %d messages. %s" % (len(lines), len(lines), summary)
            head = [json.dumps({"role": "user", "content": note}, ensure_ascii=False)]
        head += [json.dumps(r, ensure_ascii=False) for r in rows]
        tmp = os.path.join(stack, "." + HISTORY)       # N-05：先寫暫存再改名
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("".join(l + "\n" for l in head + tail))
        os.replace(tmp, path)
    try:
        os.remove(cell.file(".history_sum"))
    except FileNotFoundError:
        pass
    return len(lines)


def clear_history(cell, stack=None, keep_tail=False):
    """/clear：history 清空（原文搬到 history_removed.jsonl、op clear）。"""
    return replace_history(cell, "clear", None, stack, keep_tail)


def compact_summary(path):
    """claude 的 transcript（jsonl）裡最後一則 compact 摘要（isCompactSummary 的 user 訊息）的文字；沒有＝None。
    11-12 實測 claude 2.1.322：/compact 後 transcript 多一行 system compact_boundary、一行 user isCompactSummary（內容是摘要）。"""
    text = None
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                if not (isinstance(m, dict) and m.get("isCompactSummary")):
                    continue
                c = (m.get("message") or {}).get("content")
                if isinstance(c, list):
                    c = "".join(x.get("text", "") for x in c if isinstance(x, dict))
                if isinstance(c, str) and c.strip():
                    text = c.strip()
    except OSError:
        pass
    return text


def compact_history(cell, transcript, stack=None):
    """/compact：history 換成 CLI 給的摘要一則（原文搬走、op compact）；transcript 裡找不到摘要＝不動、回 None。"""
    summary = compact_summary(transcript) if transcript else None
    if summary is None:
        return None
    return replace_history(cell, "compact", summary, stack)


COMPACT_SEEN = ".compact_seen"       # 小格裡：{"thread", "compacted"}＝aos 已跟上的 codex 壓縮次數（11-12 Q5）


def codex_compacted(sid):
    """(這段 thread 的 rollout 裡 compacted 幾次, 最後一次的 payload)；找不到檔＝(0, None)。"""
    n, last = 0, None
    for path in transcripts("codex", sid)[:1]:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if '"compacted"' not in line:
                        continue
                    try:
                        m = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(m, dict) and m.get("type") == "compacted":
                        n, last = n + 1, m.get("payload")
        except OSError:
            pass
    return n, last


_CODEX_INJECTED = re.compile(r"^\s*<[a-z_]+>")


def codex_compact_rows(payload):
    """codex 壓縮後留下的 replacement_history（11-12 實測 0.167：developer 訊息、工具定義、user 訊息、一個 compaction 項，
    assistant 的話不留、摘要不給文字）裡撈出對話：type message、role user／assistant 的文字（各 part 的 text 接起來）；
    developer／system、工具定義、工具呼叫與結果、compaction 項都略過；codex 自己塞的 user 區塊（`<environment_context>` 這種
    以 `<小寫標籤>` 開頭的）也略過。回 [{"role", "content"}]；認不得或撈不到＝None（呼叫者不動 history、只留標記）。"""
    items = payload.get("replacement_history") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return None
    rows = []
    for it in items:
        if not isinstance(it, dict) or it.get("type") != "message" or it.get("role") not in ("user", "assistant"):
            continue
        parts = it.get("content")
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str)) \
            if isinstance(parts, list) else (parts if isinstance(parts, str) else "")
        if not text.strip() or (it["role"] == "user" and _CODEX_INJECTED.match(text)):
            continue
        rows.append({"role": it["role"], "content": text})
    return rows or None


def codex_note_compacts(cell, sid):
    """記下這段 thread 現在壓過幾次（基準）：畫面開起來時、每輪跟上之後。"""
    n, _ = codex_compacted(sid)
    cell.write(COMPACT_SEEN, json.dumps({"thread": sid, "compacted": n}) + "\n")
    return n


def codex_sync_compact(cell, sid, stack=None):
    """codex 的 /compact 跟上（使用者 Q5「從那串結構化資料裡撈出對話文字，當成新的歷史」）：同一段 thread、rollout 的 compacted
    比小格 .compact_seen 記的多＝壓過了 → history 換成「[aos] summary: … codex compacted …」一則＋撈出來的對話（原文搬走、op compact；
    最後一則 assistant 之後的 user 留著）。回 ("synced", 搬走幾則)／("unrecognized", None)＝壓了但撈不到、history 不動／None＝沒新壓縮。
    .compact_seen 不在或記的是別段 thread＝只記基準、不動（不回頭補以前的）。"""
    try:
        seen = json.loads(cell.read(COMPACT_SEEN) or "null")
    except ValueError:
        seen = None
    n, payload = codex_compacted(sid)
    cell.write(COMPACT_SEEN, json.dumps({"thread": sid, "compacted": n}) + "\n")
    if not isinstance(seen, dict) or seen.get("thread") != sid or not isinstance(seen.get("compacted"), int) or n <= seen["compacted"]:
        return None
    rows = codex_compact_rows(payload)
    if rows is None:
        return ("unrecognized", None)
    moved = replace_history(cell, "compact", "codex compacted the conversation; it keeps the messages below (its own summary is not shown)",
                            stack, keep_tail=True, rows=rows)
    return ("synced", moved)


def codex_turns(sid):
    """codex 這段 thread 的 rollout 裡講完了幾輪（task_complete 事件數）；找不到檔＝0。
    11-12 實測 codex 0.167：畫面 /clear 後的新 thread 第一輪 notify 時只有 1；/resume 到的舊 thread 會帶著以前的輪數。"""
    n = 0
    for path in transcripts("codex", sid)[:1]:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if '"task_complete"' in line:
                        n += 1
        except OSError:
            pass
    return n


def hook_main(kind, cell_path, payload_arg=None):
    """claude：stdin 一份 hook JSON（SessionStart／UserPromptSubmit／Stop）；codex：notify 把 JSON 放在最後一個參數。
    對話 id 跟 session.txt 不同就改記（follow_session）；claude 的 SessionStart source clear＝clear_history（11-12 eca-slash）。
    hook 不准讓 CLI 出錯：任何問題都吞掉、退 0。"""
    try:
        cell = Cell(cell_path)
        raw = payload_arg if kind == "codex" else sys.stdin.read()
        p = json.loads(raw)
        if kind == "claude":
            event, sid = p.get("hook_event_name"), p.get("session_id")
            if event == "SessionStart":                    # 11-12 eca-slash：開畫面、/clear、/compact、/resume 都會叫；/clear＝aos 的 history 跟著清
                if p.get("source") != "startup":           # 畫面開新對話（startup）照舊等第一輪才記：ask 看 session.txt 空著才接 reseed
                    follow_session(kind, cell, sid)
                if p.get("source") == "clear":
                    clear_history(cell)
                elif p.get("source") == "compact":         # 使用者「3.要動，希望能同步」：history 換成 claude 的摘要
                    compact_history(cell, p.get("transcript_path"))
                return
            if event == "UserPromptSubmit":
                follow_session(kind, cell, sid)
                cell.write("busy.txt", now() + "\n")
                return
            if event != "Stop":
                return
            text = p.get("last_assistant_message")
            if not isinstance(text, str):
                text = last_text_from_transcript(p.get("transcript_path") or "")
        else:
            if p.get("type") != "agent-turn-complete":
                return
            text = p.get("last-assistant-message") or ""
            sid = p.get("thread-id") or p.get("thread_id")
            if sid and not transcripts(kind, sid):         # 11-12 實測：codex 替畫面取標題的旁支 thread 也叫 notify，它沒存檔：不是這段對話，不記
                return
            old = cell.read("session.txt")
            if sid and old and sid != old and codex_turns(sid) <= 1:
                # 換到一段剛開的 thread（/clear、/new）＝新對話：aos 的 history 跟著清（使用者 Q1「1.要。」），剛交出去還沒答的 user 留著；
                # 換到有舊輪數的（/resume 到別段）＝只跟 id、history 不動（不把那段併進來）
                clear_history(cell, keep_tail=True)
            if sid and sid == old:
                codex_sync_compact(cell, sid)               # 同一段 thread 被壓過（畫面上打的 /compact、或它自己壓）＝history 跟上（Q5）
            elif sid:
                codex_note_compacts(cell, sid)              # 換了 thread：只記基準
        follow_session(kind, cell, sid)
        link_transcript(cell, kind)
        with open(cell.file("turns.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"answered_at": now(), "text": text}, ensure_ascii=False) + "\n")
        if os.path.exists(cell.file("busy.txt")):
            os.remove(cell.file("busy.txt"))
    except Exception:            # noqa: BLE001 —— hook 壞了也不能卡住 CLI
        pass
